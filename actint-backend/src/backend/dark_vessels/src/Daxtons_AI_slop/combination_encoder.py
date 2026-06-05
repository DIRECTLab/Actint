"""
AIS Combined Encoder
=====================
Fuses two input streams into a single latent vector:

    DynamicEncoder  — bidirectional LSTM over AIS track sequence
                      (lat, lon, SOG, COG, heading, ROT, msg_gap, ...)

    StaticEncoder   — dense MLP over vessel profile
                      (length, width, draught, vessel_type, flag, age, ...)

    CombinedEncoder — takes both outputs, lets them interact via a small
                      fusion network, produces one fixed-size latent vector
                      ready for a Transformer classifier

Pipeline:

    track  (B, T, dyn_features)  ──► DynamicEncoder ──► (B, dyn_latent)  ─┐
                                                                             ├─► FusionNet ──► (B, combined_dim)
    static (B, stat_features)    ──► StaticEncoder  ──► (B, stat_latent) ─┘

The combined vector is what each ship is represented by when it enters
the Transformer. The Transformer then attends across all ships in an area.
"""

import torch
import torch.nn as nn
import numpy as np
from backend.dark_vessels.src.Daxtons_AI_slop.dynamic_encoder import DynamicEncoder, pad_tracks, normalise_track
from backend.dark_vessels.src.Daxtons_AI_slop.static_encoder import StaticEncoder


# ─────────────────────────────────────────────────────────────────────────────
# STATIC FEATURE CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

# Continuous static features and their normalisation ranges
STATIC_CONTINUOUS_RANGES = {
    "length":       (0.0,   500.0),   # metres
    "width":        (0.0,    80.0),   # metres
    "draught":      (0.0,    25.0),   # metres
    "gross_tonnage":(0.0, 200000.0),  # GT
    "ship_age":     (0.0,    60.0),   # years since build
}

# Categorical features — each maps to an embedding
# (name → number of unique categories)
STATIC_CATEGORICAL = {
    "vessel_type": 30,    # AIS vessel type codes (0–29 simplified)
    "flag_state":  200,   # ISO country codes — ~180 active + unknown
}

def normalise_static(raw: dict) -> np.ndarray:
    """
    Normalise one ship's static features to [0,1] for the continuous ones.
    Categorical features are returned as integer indices (for embedding).

    Args:
        raw : dict with keys matching STATIC_CONTINUOUS_RANGES and
              STATIC_CATEGORICAL. Missing keys get 0.0 / 0 (unknown).

    Returns:
        continuous : np.ndarray  (n_continuous,)   float32 in [0,1]
        categorical: np.ndarray  (n_categorical,)  int64 indices
    """
    continuous = []
    for feat, (lo, hi) in STATIC_CONTINUOUS_RANGES.items():
        val = raw.get(feat, 0.0)
        continuous.append(np.clip((val - lo) / (hi - lo), 0.0, 1.0))

    categorical = []
    for feat, n_cats in STATIC_CATEGORICAL.items():
        idx = int(raw.get(feat, 0))
        categorical.append(np.clip(idx, 0, n_cats - 1))

    return (np.array(continuous,  dtype=np.float32),
            np.array(categorical, dtype=np.int64))


# ─────────────────────────────────────────────────────────────────────────────
# STATIC ENCODER
# ─────────────────────────────────────────────────────────────────────────────

class StaticEncoder(nn.Module):
    """
    Encodes fixed vessel profile features into a latent vector.

    Handles two types of static feature:
      - Continuous  (length, width, draught, ...) — normalised floats
      - Categorical (vessel_type, flag_state, ...) — integer indices
                                                     passed through embeddings

    Embeddings let the model learn that e.g. bulk carriers and container ships
    are more similar to each other than either is to a fishing vessel —
    automatically, from data, without you having to specify it.

    Args:
        n_continuous    : number of continuous static features
        categorical_dims: list of (n_categories, embed_dim) per categorical
                          feature. embed_dim is how many neurons represent
                          each category.
        latent_dim      : size of output vector
        hidden_size     : width of hidden MLP layers
    """

    def __init__(
        self,
        n_continuous:     int   = 5,
        categorical_dims: list  = None,   # [(n_cats, embed_dim), ...]
        latent_dim:       int   = 64,
        hidden_size:      int   = 64,
    ):
        super().__init__()

        if categorical_dims is None:
            # Default: vessel_type (30 cats → 8 dim), flag_state (200 → 16 dim)
            categorical_dims = [(30, 8), (200, 16)]

        # ── Embedding layers for categorical features ─────────────────────
        # Each categorical feature gets its own embedding table.
        # nn.ModuleList registers them properly so PyTorch tracks parameters.
        self.embeddings = nn.ModuleList([
            nn.Embedding(n_cats, embed_dim)
            for n_cats, embed_dim in categorical_dims
        ])

        # Total input size to the MLP:
        # continuous features + all embedding dimensions combined
        embed_total = sum(ed for _, ed in categorical_dims)
        mlp_input   = n_continuous + embed_total

        # ── MLP encoder ───────────────────────────────────────────────────
        # Simple feedforward network — static features have no time dimension
        # so no LSTM needed. Two hidden layers with residual-style depth.
        self.mlp = nn.Sequential(
            nn.Linear(mlp_input, hidden_size),
            nn.LayerNorm(hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.LayerNorm(hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, latent_dim),
            nn.LayerNorm(latent_dim),
            nn.Tanh(),
        )

    def forward(
        self,
        continuous:  torch.Tensor,   # (B, n_continuous)
        categorical: torch.Tensor,   # (B, n_categorical)  integer indices
    ) -> torch.Tensor:
        """
        Args:
            continuous  : (batch, n_continuous) normalised float features
            categorical : (batch, n_categorical) integer category indices

        Returns:
            latent : (batch, latent_dim)
        """

        # ── 1. Embed each categorical feature ─────────────────────────────
        # Each column of categorical gets its own embedding lookup
        embedded = [
            emb(categorical[:, i])
            for i, emb in enumerate(self.embeddings)
        ]   # list of (B, embed_dim) tensors

        # ── 2. Concatenate continuous + all embeddings ────────────────────
        parts = [continuous] + embedded
        x = torch.cat(parts, dim=-1)    # (B, n_continuous + embed_total)

        # ── 3. Encode through MLP ─────────────────────────────────────────
        return self.mlp(x)              # (B, latent_dim)


# ─────────────────────────────────────────────────────────────────────────────
# COMBINED ENCODER
# ─────────────────────────────────────────────────────────────────────────────

class CombinedEncoder(nn.Module):
    """
    Fuses the dynamic (trajectory) and static (vessel profile) encoders
    into a single latent vector per ship.

    The fusion network is not just a concatenation — it has its own learned
    layers that allow the two streams to interact. This is important because
    the suspicious signal often lives in the *relationship* between the two:

        "A tanker (static) moving like a fishing vessel (dynamic)"
        "A vessel with no declared cargo (static) on a drug-route path (dynamic)"

    Args:
        dynamic_encoder  : DynamicEncoder instance
        static_encoder   : StaticEncoder instance
        combined_dim     : size of the final fused output vector
        dropout          : dropout in fusion layers
    """

    def __init__(
        self,
        dynamic_encoder: DynamicEncoder,
        static_encoder:  StaticEncoder,
        combined_dim:    int   = 128,
        dropout:         float = 0.1,
    ):
        super().__init__()

        self.dynamic_encoder = dynamic_encoder
        self.static_encoder  = static_encoder

        # Size of the concatenated input to the fusion network
        fusion_input = (dynamic_encoder.latent_dim +
                        static_encoder.mlp[-3].out_features
                        if hasattr(static_encoder.mlp[-3], 'out_features')
                        else combined_dim)

        # Derive static latent dim from the MLP output layer
        # Walk back through Sequential to find the last Linear
        stat_latent = None
        for layer in reversed(list(static_encoder.mlp)):
            if isinstance(layer, nn.Linear):
                stat_latent = layer.out_features
                break
        dyn_latent  = dynamic_encoder.latent_dim
        fusion_input = dyn_latent + stat_latent

        # ── Fusion network ────────────────────────────────────────────────
        # Two-layer MLP that takes the concatenated latent vectors and
        # produces a single fused representation.
        #
        # Layer 1: full concatenation → hidden  (cross-stream interaction)
        # Layer 2: hidden → combined_dim         (final compression)
        #
        # The LayerNorm between them keeps gradients stable during training.
        self.fusion = nn.Sequential(
            nn.Linear(fusion_input, fusion_input),
            nn.LayerNorm(fusion_input),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(fusion_input, combined_dim),
            nn.LayerNorm(combined_dim),
            nn.Tanh(),
        )

    def forward(
        self,
        track:       torch.Tensor,          # (B, T, dyn_features)
        continuous:  torch.Tensor,          # (B, n_continuous)
        categorical: torch.Tensor,          # (B, n_categorical) int indices
        lengths:     torch.Tensor = None,   # (B,) actual track lengths
    ) -> dict:
        """
        Args:
            track       : (batch, seq_len, dyn_features)  padded AIS track
            continuous  : (batch, n_continuous)           normalised static floats
            categorical : (batch, n_categorical)          integer category indices
            lengths     : (batch,)                        real track lengths (optional)

        Returns dict with:
            "combined"       : (batch, combined_dim)  — the fused latent vector,
                               ready for the Transformer
            "dynamic_latent" : (batch, dyn_latent)    — dynamic stream alone
            "static_latent"  : (batch, stat_latent)   — static stream alone
        """

        # ── 1. Encode each stream independently ───────────────────────────
        dynamic_latent = self.dynamic_encoder(track, lengths=lengths)
        static_latent  = self.static_encoder(continuous, categorical)

        # ── 2. Concatenate streams ────────────────────────────────────────
        # At this point we have two separate voyage descriptions:
        #   dynamic_latent : "what this ship DID"
        #   static_latent  : "what kind of ship this IS"
        # Concatenation puts them side by side so the fusion layer can
        # learn how they relate to each other.
        cat = torch.cat([dynamic_latent, static_latent], dim=-1)

        # ── 3. Fuse ───────────────────────────────────────────────────────
        # The fusion MLP lets the two streams interact — learning things like
        # "a tanker with these trajectory features is suspicious" vs
        # "a fishing vessel with these trajectory features is normal"
        combined = self.fusion(cat)

        return {
            "combined":       combined,        # → Transformer
            "dynamic_latent": dynamic_latent,  # → useful for debugging / viz
            "static_latent":  static_latent,   # → useful for debugging / viz
        }


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — build a default CombinedEncoder in one call
# ─────────────────────────────────────────────────────────────────────────────

def build_combined_encoder(
    dyn_input_features: int = 6,
    dyn_hidden_size:    int = 64,
    dyn_latent_dim:     int = 128,
    stat_n_continuous:  int = 5,
    stat_categorical_dims: list = None,
    stat_latent_dim:    int = 64,
    combined_dim:       int = 128,
) -> CombinedEncoder:
    """
    Convenience function — builds a fully configured CombinedEncoder
    with sensible defaults matching the AIS feature sets defined above.

    Returns:
        CombinedEncoder ready for training or inference
    """
    if stat_categorical_dims is None:
        stat_categorical_dims = [(30, 8), (200, 16)]

    dyn_enc  = DynamicEncoder(
        input_features = dyn_input_features,
        hidden_size    = dyn_hidden_size,
        latent_dim     = dyn_latent_dim,
    )
    stat_enc = StaticEncoder(
        n_continuous     = stat_n_continuous,
        categorical_dims = stat_categorical_dims,
        latent_dim       = stat_latent_dim,
    )
    return CombinedEncoder(
        dynamic_encoder = dyn_enc,
        static_encoder  = stat_enc,
        combined_dim    = combined_dim,
    )


# ─────────────────────────────────────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    print("=" * 60)
    print("Combined Encoder — shape walkthrough")
    print("=" * 60)

    np.random.seed(42)
    torch.manual_seed(42)
    BATCH = 4

    # ── Build encoder ────────────────────────────────────────────────────
    enc = build_combined_encoder(
        dyn_input_features    = 6,     # lat, lon, sog, cog, heading, msg_gap
        dyn_hidden_size       = 64,
        dyn_latent_dim        = 128,
        stat_n_continuous     = 5,     # length, width, draught, tonnage, age
        stat_categorical_dims = [(30, 8), (200, 16)],  # vessel_type, flag
        stat_latent_dim       = 64,
        combined_dim          = 128,
    )

    total = sum(p.numel() for p in enc.parameters())
    print(f"\nTotal parameters   : {total:,}")

    # ── Simulate dynamic tracks (variable length) ─────────────────────────
    print(f"\nSimulating {BATCH} ships...")
    DYNAMIC_FEATURES = ["lat", "lon", "sog", "cog", "heading", "msg_gap"]
    raw_tracks = [
        np.column_stack([
            np.random.uniform(50.5, 51.5, n),
            np.random.uniform(2.0,  4.0,  n),
            np.random.uniform(9.0,  15.0, n),
            np.random.uniform(45.0, 75.0, n),
            np.random.uniform(43.0, 77.0, n),
            np.random.uniform(8.0,  18.0, n),
        ])
        for n in [200, 134, 91, 178]
    ]
    track_tensor, lengths = pad_tracks(raw_tracks, DYNAMIC_FEATURES)

    # ── Simulate static features ──────────────────────────────────────────
    # Continuous: length, width, draught, gross_tonnage, ship_age
    cont_raw = np.array([
        [185.0, 28.0, 11.2, 35000.0, 12.0],   # normal cargo
        [312.0, 48.0, 14.5, 98000.0,  8.0],   # large tanker
        [ 24.0,  6.5,  3.1,   450.0, 22.0],   # small fishing vessel
        [220.0, 32.0, 12.8, 52000.0, 15.0],   # container ship
    ], dtype=np.float32)

    # Normalise continuous
    cont_norm = np.zeros_like(cont_raw)
    for i, (lo, hi) in enumerate(STATIC_CONTINUOUS_RANGES.values()):
        cont_norm[:, i] = np.clip((cont_raw[:, i] - lo) / (hi - lo), 0, 1)
    cont_tensor = torch.tensor(cont_norm)

    # Categorical: vessel_type index, flag_state index
    cat_tensor = torch.tensor([
        [1,  76],    # cargo, Panama
        [4,  58],    # tanker, Marshall Islands
        [6, 103],    # fishing, Norway
        [1,  44],    # cargo, Cyprus
    ], dtype=torch.long)

    # ── Forward pass ──────────────────────────────────────────────────────
    enc.eval()
    with torch.no_grad():
        out = enc(track_tensor, cont_tensor, cat_tensor, lengths=lengths)

    print(f"\nInput shapes:")
    print(f"  Track (padded)   : {tuple(track_tensor.shape)}")
    print(f"  Track lengths    : {lengths.tolist()}")
    print(f"  Continuous static: {tuple(cont_tensor.shape)}")
    print(f"  Categorical      : {tuple(cat_tensor.shape)}")

    print(f"\nOutput shapes:")
    print(f"  dynamic_latent   : {tuple(out['dynamic_latent'].shape)}"
          f"   ← LSTM voyage summary")
    print(f"  static_latent    : {tuple(out['static_latent'].shape)}"
          f"    ← vessel profile")
    print(f"  combined         : {tuple(out['combined'].shape)}"
          f"   ← fused, ready for Transformer")

    print(f"\nCombined vector stats (per ship):")
    for i in range(BATCH):
        v = out['combined'][i]
        print(f"  Ship {i+1}: "
              f"mean={v.mean():.4f}  "
              f"std={v.std():.4f}  "
              f"min={v.min():.4f}  "
              f"max={v.max():.4f}")

    print(f"\n{'─'*60}")
    print(f"Each ship is now a single {out['combined'].shape[1]}-dim vector.")
    print(f"Stack {BATCH} ships → ({BATCH}, 128) input to Transformer.")
    print(f"{'─'*60}")

    # ── Show parameter breakdown ──────────────────────────────────────────
    print(f"\nParameter breakdown:")
    dyn_params  = sum(p.numel() for p in enc.dynamic_encoder.parameters())
    stat_params = sum(p.numel() for p in enc.static_encoder.parameters())
    fus_params  = sum(p.numel() for p in enc.fusion.parameters())
    print(f"  DynamicEncoder  : {dyn_params:>8,}")
    print(f"  StaticEncoder   : {stat_params:>8,}")
    print(f"  Fusion network  : {fus_params:>8,}")
    print(f"  Total           : {total:>8,}")