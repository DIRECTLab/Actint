"""
Transformer-based Full-Track Sequence Classifier

PyTorch Transformer encoder (RTX 4080 Laptop, CUDA) that ingests variable-
length AIS ping sequences and jointly predicts:
  - Activity class (fishing / transit / anchored / loitering / sts / port)
  - Vessel type   (12-class unified taxonomy)

Architecture:
  - Per-ping feature embedding (linear projection + positional encoding)
  - 4-layer Transformer encoder with 8 heads
  - CLS-token pooling → dual classification heads
  - Optional: cross-attend to partial-track XGBoost logits for ensemble

Usage:
    from src.sequence_classifier import SequenceClassifier, PingFeatureExtractor
    feat = PingFeatureExtractor()
    clf  = SequenceClassifier(device="cuda")
    clf.fit(tracks_df, epochs=30)
    preds = clf.predict(tracks_df)
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Tuple

log = logging.getLogger(__name__)

# ── Activity / type labels (must match classifier.py) ─────────────────────────
ACTIVITY_LABELS = ["fishing", "transit", "anchored", "loiter", "sts", "port"]
VESSEL_LABELS   = [
    "fishing", "cargo", "tanker", "passenger", "tug",
    "naval", "support_vessel", "sailing", "pleasure_craft",
    "hsc", "other", "unknown",
]

# ── Ping-level features fed to the transformer ────────────────────────────────
PING_FEATURES = [
    "sog", "cog_sin", "cog_cos", "heading_sin", "heading_cos",
    "lat_norm", "lon_norm", "hour_sin", "hour_cos",
    "turning_rate", "acceleration",
    "length_norm", "draught_norm",
    "nav_status_enc",
]

_D_MODEL   = 64    # transformer embedding dim
_N_HEADS   = 8
_N_LAYERS  = 4
_D_FF      = 256
_DROPOUT   = 0.1
_MAX_SEQ   = 256   # max pings per window (longer tracks are strided)


# ══════════════════════════════════════════════════════════════════════════════
# Ping-level feature extractor
# ══════════════════════════════════════════════════════════════════════════════

class PingFeatureExtractor:
    """
    Convert raw AIS ping DataFrame (one row per ping) into a 3-D tensor
    (batch, seq_len, n_features) suitable for the Transformer.
    """

    def extract_track(self, df: pd.DataFrame) -> np.ndarray:
        """
        Args:
            df: sorted ping-level DataFrame for a single vessel track.
        Returns:
            (T, n_features) float32 array; NaN → 0 (XGBoost handles NaN natively
            but Transformer needs imputation here).
        """
        T = len(df)
        out = np.zeros((T, len(PING_FEATURES)), dtype=np.float32)

        # SOG normalised to [0,1] (max ~30 kn)
        if "sog" in df.columns:
            out[:, 0] = np.clip(df["sog"].values / 30.0, 0, 1)

        # COG sin/cos
        if "cog" in df.columns:
            rad = np.radians(df["cog"].fillna(0).values)
            out[:, 1] = np.sin(rad)
            out[:, 2] = np.cos(rad)

        # Heading sin/cos
        if "heading" in df.columns:
            rad = np.radians(df["heading"].fillna(0).values)
            out[:, 3] = np.sin(rad)
            out[:, 4] = np.cos(rad)

        # Lat/Lon normalised to [-1, 1]
        if "lat" in df.columns:
            out[:, 5] = df["lat"].fillna(0).values / 90.0
        if "lon" in df.columns:
            out[:, 6] = df["lon"].fillna(0).values / 180.0

        # Time-of-day
        if "timestamp" in df.columns:
            ts = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
            hours = ts.dt.hour + ts.dt.minute / 60.0
            out[:, 7] = np.sin(2 * np.pi * hours / 24)
            out[:, 8] = np.cos(2 * np.pi * hours / 24)

        # Turning rate (degrees/min)
        if "cog" in df.columns and "timestamp" in df.columns:
            ts_s = pd.to_datetime(df["timestamp"], utc=True, errors="coerce").astype(np.int64) / 1e9

        # These are bug fixes for my machine/version of python, if it causes you errors, try setting it back
            # dt   = np.diff(ts_s, prepend=ts_s[0])
            dt = np.diff(ts_s, prepend=ts_s.iloc[0])
            # dcog = np.diff(df["cog"].fillna(method="ffill").values, prepend=0)
            dcog = np.diff(df["cog"].ffill().values, prepend=0)
        
            dcog = (dcog + 180) % 360 - 180   # wrap to [-180, 180]

            # tr   = np.where(dt > 0, dcog / (dt / 60.0), 0.0)
            tr = np.divide(dcog, dt / 60.0, out=np.zeros_like(dcog), where=dt > 0)
            
            out[:, 9] = np.clip(tr / 30.0, -1, 1)   # normalise

        # Acceleration
        if "sog" in df.columns and "timestamp" in df.columns:
            ts_s = pd.to_datetime(df["timestamp"], utc=True, errors="coerce").astype(np.int64) / 1e9

        # These are bug fixes for my machine/version of python, if it causes you errors, try setting it back
            # dt   = np.diff(ts_s, prepend=ts_s[0])
            dt = np.diff(ts_s, prepend=ts_s.iloc[0])
            # dsog = np.diff(df["sog"].fillna(method="ffill").values, prepend=0)
            dsog = np.diff(df["sog"].ffill().values, prepend=0)
            # acc  = np.where(dt > 0, dsog / (dt / 60.0), 0.0)
            acc = np.divide(dsog, dt / 60.0, out=np.zeros_like(dsog), where=dt > 0)


            out[:, 10] = np.clip(acc / 2.0, -1, 1)

        # Vessel dims
        if "length" in df.columns:
            out[:, 11] = np.clip(df["length"].fillna(0).values / 400.0, 0, 1)
        if "draught" in df.columns:
            out[:, 12] = np.clip(df["draught"].fillna(0).values / 25.0, 0, 1)

        # Nav status (0–15 → normalised)
        if "nav_status" in df.columns:
            ns = pd.to_numeric(df["nav_status"], errors="coerce").fillna(0).values
            out[:, 13] = np.clip(ns / 15.0, 0, 1)

        return out


# ══════════════════════════════════════════════════════════════════════════════
# Transformer model (PyTorch)
# ══════════════════════════════════════════════════════════════════════════════

def _build_model(n_ping_features: int,
                 n_act_classes: int,
                 n_type_classes: int,
                 d_model: int    = _D_MODEL,
                 n_heads: int    = _N_HEADS,
                 n_layers: int   = _N_LAYERS,
                 d_ff: int       = _D_FF,
                 dropout: float  = _DROPOUT):
    """Construct the dual-head Transformer model."""
    import torch
    import torch.nn as nn

    class PositionalEncoding(nn.Module):
        def __init__(self, d, max_len=_MAX_SEQ):
            super().__init__()
            pe = torch.zeros(max_len, d)
            pos = torch.arange(0, max_len).unsqueeze(1).float()
            div = torch.exp(torch.arange(0, d, 2).float() * (-np.log(10000.0) / d))
            pe[:, 0::2] = torch.sin(pos * div)
            pe[:, 1::2] = torch.cos(pos * div)
            self.register_buffer("pe", pe.unsqueeze(0))  # (1, max_len, d)

        def forward(self, x):   # x: (B, T, d)
            return x + self.pe[:, :x.size(1)]

    class DualHeadTransformer(nn.Module):
        def __init__(self):
            super().__init__()
            self.embed   = nn.Linear(n_ping_features, d_model)
            self.pos_enc = PositionalEncoding(d_model)
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=d_model, nhead=n_heads, dim_feedforward=d_ff,
                dropout=dropout, batch_first=True,
            )
            self.encoder  = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
            self.act_head = nn.Linear(d_model, n_act_classes)
            self.typ_head = nn.Linear(d_model, n_type_classes)
            self.dropout  = nn.Dropout(dropout)

        def forward(self, x, padding_mask=None):
            # x: (B, T, n_ping_features)
            x = self.pos_enc(self.embed(x))       # (B, T, d_model)
            x = self.encoder(x, src_key_padding_mask=padding_mask)
            # CLS = mean-pool over non-padding positions
            if padding_mask is not None:
                mask = (~padding_mask).float().unsqueeze(-1)
                x    = (x * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
            else:
                x = x.mean(dim=1)
            x = self.dropout(x)
            return self.act_head(x), self.typ_head(x)

    return DualHeadTransformer()


# ══════════════════════════════════════════════════════════════════════════════
# Dataset helper
# ══════════════════════════════════════════════════════════════════════════════

class _TrackDataset:
    def __init__(self, records: list, act_enc: dict, type_enc: dict,
                 max_seq: int = _MAX_SEQ):
        self.records  = records
        self.act_enc  = act_enc
        self.type_enc = type_enc
        self.max_seq  = max_seq

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        import torch
        r   = self.records[idx]
        seq = r["features"][:self.max_seq]   # (T, F)
        T   = len(seq)
        pad = self.max_seq - T

        x = np.zeros((self.max_seq, seq.shape[1]), dtype=np.float32)
        x[:T] = seq
        mask = np.ones(self.max_seq, dtype=bool)
        mask[:T] = False   # True = padding in PyTorch convention

        act_label  = self.act_enc.get(r.get("true_activity", "transit"), 0)
        type_label = self.type_enc.get(r.get("vessel_type_key", "unknown"), 0)

        return (torch.from_numpy(x),
                torch.from_numpy(mask),
                torch.tensor(act_label,  dtype=torch.long),
                torch.tensor(type_label, dtype=torch.long))


# ══════════════════════════════════════════════════════════════════════════════
# SequenceClassifier
# ══════════════════════════════════════════════════════════════════════════════

class SequenceClassifier:
    """
    Full-track Transformer classifier.

    Complements PartialTrackClassifier: use this when ≥20 pings are available
    and you want richer temporal pattern recognition (set-haul cycles, etc.).
    """

    def __init__(self,
                 device: Optional[str] = None,
                 max_seq: int           = _MAX_SEQ,
                 d_model: int           = _D_MODEL,
                 n_layers: int          = _N_LAYERS):
        self._extractor = PingFeatureExtractor()
        self._max_seq   = max_seq
        self._d_model   = d_model
        self._n_layers  = n_layers
        self._trained   = False

        try:
            import torch
            if device is None:
                device = "cuda" if torch.cuda.is_available() else "cpu"
            self._device = torch.device(device)
            log.info("[seq_clf] Device: %s", self._device)
        except ImportError:
            self._device = None
            log.warning("[seq_clf] PyTorch not available – SequenceClassifier disabled")

        self.activity_labels = ACTIVITY_LABELS
        self.vessel_labels   = VESSEL_LABELS
        self._act_enc  = {k: i for i, k in enumerate(ACTIVITY_LABELS)}
        self._type_enc = {k: i for i, k in enumerate(VESSEL_LABELS)}
        self._model    = None

    # ──────────────────────────────────────────────────────────────────────────
    def _check_torch(self):
        if self._device is None:
            raise RuntimeError("PyTorch not available. Install with: pip install torch")

    # ──────────────────────────────────────────────────────────────────────────
    def fit(self, df: pd.DataFrame,
            epochs: int     = 20,
            batch_size: int = 32,
            lr: float       = 1e-3) -> "SequenceClassifier":
        """
        Train on a DataFrame of AIS pings.
        Requires columns: mmsi, timestamp, lat, lon, sog, cog,
                          true_activity, vessel_type_key.
        """
        self._check_torch()
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader

        records = self._build_records(df)
        if not records:
            log.warning("[seq_clf] No training records built")
            return self

        n_feat = records[0]["features"].shape[1]
        self._model = _build_model(
            n_feat, len(ACTIVITY_LABELS), len(VESSEL_LABELS),
            d_model=self._d_model, n_layers=self._n_layers,
        ).to(self._device)

        dataset    = _TrackDataset(records, self._act_enc, self._type_enc, self._max_seq)
        loader     = DataLoader(dataset, batch_size=batch_size, shuffle=True,
                                num_workers=0, pin_memory=(str(self._device) == "cuda"))
        optimizer  = torch.optim.AdamW(self._model.parameters(), lr=lr, weight_decay=1e-4)
        scheduler  = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
        loss_fn    = nn.CrossEntropyLoss(label_smoothing=0.05)

        for epoch in range(1, epochs + 1):
            self._model.train()
            total_loss = 0.0
            for x, mask, act_lbl, type_lbl in loader:
                x        = x.to(self._device)
                mask     = mask.to(self._device)
                act_lbl  = act_lbl.to(self._device)
                type_lbl = type_lbl.to(self._device)

                act_logits, type_logits = self._model(x, padding_mask=mask)
                loss = loss_fn(act_logits, act_lbl) + 0.5 * loss_fn(type_logits, type_lbl)

                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self._model.parameters(), 1.0)
                optimizer.step()
                total_loss += loss.item()

            scheduler.step()
            if epoch % 5 == 0 or epoch == 1:
                log.info("[seq_clf] Epoch %d/%d  loss=%.4f", epoch, epochs,
                         total_loss / max(len(loader), 1))

        self._trained = True
        return self

    # ──────────────────────────────────────────────────────────────────────────
    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Predict activity + vessel type for each unique MMSI in df.
        Returns DataFrame with mmsi, pred_activity, pred_vessel_type,
        activity_confidence, vessel_confidence.
        """
        self._check_torch()
        if not self._trained:
            raise RuntimeError("Call fit() before predict()")
        import torch

        self._model.eval()
        records = self._build_records(df, require_labels=False)
        results = []

        with torch.no_grad():
            for r in records:
                seq = r["features"][:self._max_seq]
                T   = len(seq)
                x   = np.zeros((1, self._max_seq, seq.shape[1]), dtype=np.float32)
                x[0, :T] = seq
                mask    = np.ones((1, self._max_seq), dtype=bool)
                mask[0, :T] = False

                x_t    = torch.from_numpy(x).to(self._device)
                mask_t = torch.from_numpy(mask).to(self._device)

                act_logits, type_logits = self._model(x_t, padding_mask=mask_t)

                act_probs  = torch.softmax(act_logits,  dim=-1).cpu().numpy()[0]
                type_probs = torch.softmax(type_logits, dim=-1).cpu().numpy()[0]

                results.append({
                    "mmsi":                r["mmsi"],
                    "pred_activity":       ACTIVITY_LABELS[int(act_probs.argmax())],
                    "pred_vessel_type":    VESSEL_LABELS[int(type_probs.argmax())],
                    "activity_confidence": float(act_probs.max()),
                    "vessel_confidence":   float(type_probs.max()),
                    **{f"act_prob_{ACTIVITY_LABELS[i]}": float(p)
                       for i, p in enumerate(act_probs)},
                })

        return pd.DataFrame(results)

    # ──────────────────────────────────────────────────────────────────────────
    def save(self, path: str):
        """Save model weights."""
        import torch
        if self._model is None:
            raise RuntimeError("No model to save")
        torch.save({
            "state_dict":      self._model.state_dict(),
            "activity_labels": self.activity_labels,
            "vessel_labels":   self.vessel_labels,
            "d_model":         self._d_model,
            "n_layers":        self._n_layers,
        }, path)
        log.info("[seq_clf] Model saved to %s", path)

    def load(self, path: str):
        """Load model weights."""
        import torch
        ckpt = torch.load(path, map_location=self._device)
        n_feat = len(PING_FEATURES)
        self._model = _build_model(
            n_feat,
            len(ckpt["activity_labels"]),
            len(ckpt["vessel_labels"]),
            d_model=ckpt["d_model"],
            n_layers=ckpt["n_layers"],
        ).to(self._device)
        self._model.load_state_dict(ckpt["state_dict"])
        self._trained = True
        log.info("[seq_clf] Model loaded from %s", path)

    # ──────────────────────────────────────────────────────────────────────────
    def _build_records(self, df: pd.DataFrame,
                       require_labels: bool = True) -> list:
        """Convert ping DataFrame into list of {mmsi, features, labels} dicts."""
        records = []
        for mmsi, grp in df.groupby("mmsi"):
            grp = grp.sort_values("timestamp")
            if len(grp) < 2:
                continue
            feat = self._extractor.extract_track(grp)
            rec  = {"mmsi": mmsi, "features": feat}
            if "true_activity" in grp.columns:
                mode_act = grp["true_activity"].mode()
                rec["true_activity"] = mode_act.iloc[0] if len(mode_act) > 0 else "transit"
            elif require_labels:
                continue
            if "vessel_type_key" in grp.columns:
                mode_vt = grp["vessel_type_key"].mode()
                rec["vessel_type_key"] = mode_vt.iloc[0] if len(mode_vt) > 0 else "unknown"
            records.append(rec)
        return records
    

    def ais_to_dataframe(self, ais_data):
        """
        Convert a list of AIS pings (dicts) into a DataFrame suitable for
        SequenceClassifier.predict().
        
        Takes input from the AIS database and produces a pandas dataframe.
        
        Output DataFrame columns:
        ['mmsi', 'timestamp', 'lat', 'lon', 'sog', 'cog']
        """
        
        # Map the dictionary keys to the columns expected by SequenceClassifier
        records = []
        for ping in ais_data:
            record = {
                "mmsi": ping["mmsi"],
                "timestamp": ping["basedatetime"],
                "lat": ping["lat"],
                "lon": ping["lon"],
                "sog": ping["sog"],
                "cog": ping["cog"],
            }
            records.append(record)
        
        df = pd.DataFrame(records)
        
        # Sort by MMSI and timestamp, just in case
        df.sort_values(by=["mmsi", "timestamp"], inplace=True)
        df.reset_index(drop=True, inplace=True)
        
        return df



