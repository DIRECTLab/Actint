"""
AIS Dynamic Feature Encoder
============================
Encodes a sequence of AIS dynamic messages (lat, lon, COG, SOG, + optional
extras) into a single fixed-size latent vector using a bidirectional LSTM.

This module is designed to be one half of a dual-encoder pipeline:

    DynamicEncoder  ──┐
                       ├──► combined latent ──► Transformer classifier
    StaticEncoder   ──┘

Usage:
    encoder = DynamicEncoder(input_features=6, hidden_size=64, latent_dim=128)
    latent  = encoder(track_tensor)   # (batch, seq_len, features) → (batch, 128)

The output latent vector is a fixed-size summary of the entire voyage track
regardless of how many timesteps were in the input sequence.
"""

from backend.mcp_servers.utils.distance_calculation import haversine_distance_nm, calculate_bearing

import numpy as np

def dynamic_preparation(AIS_dynamic):
    prepared_tracks = []

    for track in AIS_dynamic:
        n = len(track)

        features = np.zeros((n, 3))

        for i in range(n):

            if i == 0:
                lat_lon_distance = 0.0
                lat_lon_angle = 0.0
                msg_gap = 0.0
            else:
                lat_lon_distance = haversine_distance_nm(
                    track[i, 0], track[i, 1],
                    track[i-1, 0], track[i-1, 1]
                )
                lat_lon_angle = calculate_bearing(
                    track[i-1, 0], track[i-1, 1],
                    track[i, 0], track[i, 1]
                )
                msg_gap = track[i, 4] - track[i-1, 4]
            features[i] = [lat_lon_distance, np.sin(lat_lon_angle), np.cos(lat_lon_angle), msg_gap]
        prepared_tracks.append(features)
    return prepared_tracks
#pad_tracks(prepared_tracks, FEATURE_NAMES)



import torch
from torch.utils.data import Dataset

class AISDataset(Dataset):
    def __init__(self, tracks, ship_ids):
        self.tracks = tracks
        self.ship_ids = ship_ids

    def __len__(self):
        return len(self.tracks)

    def __getitem__(self, idx):
        x = torch.tensor(self.tracks[idx], dtype=torch.float32)
        ship_id = torch.tensor(self.ship_ids[idx], dtype=torch.long)
        return x, ship_id









import torch
import torch.nn as nn

class AISModel(nn.Module):
    def __init__(self, num_ship_ids, emb_dim=16, hidden=128):
        super().__init__()

        # sequence encoder (your ship behavior)
        self.gru = nn.GRU(
            input_size=3,
            hidden_size=hidden,
            batch_first=True
        )

        # ship ID embedding
        self.ship_embedding = nn.Embedding(num_ship_ids, emb_dim)

        # fusion network
        self.fc = nn.Sequential(
            nn.Linear(hidden + emb_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64)   # final embedding
        )

    def forward(self, seq, ship_id):

        # seq: (batch, time, 3)
        _, h = self.gru(seq)
        seq_emb = h.squeeze(0)

        # ship id embedding
        id_emb = self.ship_embedding(ship_id)

        # combine
        x = torch.cat([seq_emb, id_emb], dim=1)

        return self.fc(x)


import torch
import torch.nn as nn
import numpy as np


# ─────────────────────────────────────────────────────────────────────────────
# DYNAMIC ENCODER
# ─────────────────────────────────────────────────────────────────────────────

class DynamicEncoder(nn.Module):
    """
    Encodes a variable-length AIS track into a fixed-size latent vector.

    Architecture:
        Input projection  — linear layer to normalise feature scale before LSTM
        Bidirectional LSTM — reads track forwards AND backwards simultaneously
        Output projection  — compresses concatenated hidden states to latent_dim

    Args:
        input_features : number of dynamic features per timestep
                         minimum recommended: 4  (lat, lon, COG, SOG)
                         extended recommended: 7  (+ ROT, heading, msg_gap)
        hidden_size    : LSTM hidden state size per direction
                         bidirectional doubles this internally, so the
                         raw LSTM output is hidden_size * 2
        latent_dim     : size of the final output vector handed to transformer
        num_layers     : depth of the LSTM stack (2 is a good default)
        dropout        : dropout between LSTM layers (only applies if
                         num_layers > 1)
    """

    def __init__(
        self,
        input_features: int = 6,
        hidden_size: int    = 64,
        latent_dim: int     = 128,
        num_layers: int     = 2,
        dropout: float      = 0.1,
    ):
        super().__init__()

        self.input_features = input_features
        self.hidden_size    = hidden_size
        self.latent_dim     = latent_dim
        self.num_layers     = num_layers

        # ── Input projection ──────────────────────────────────────────────
        # Projects raw (normalised) features into a richer representation
        # before the LSTM sees them. Gives the model a chance to learn
        # useful feature combinations (e.g. COG-heading delta) implicitly.
        self.input_proj = nn.Sequential(
            nn.Linear(input_features, input_features),
            nn.ReLU(),
            nn.Linear(input_features, hidden_size),
            nn.ReLU(),
            nn.LayerNorm(hidden_size),
            nn.ReLU(),
        )

        # self.input_proj = nn.Sequential(
        #     nn.Linear(input_features, hidden_size),
        #     nn.LayerNorm(hidden_size),
        #     nn.ReLU(),
        # )

        # ── Bidirectional LSTM ────────────────────────────────────────────
        # Reads the track in both directions simultaneously.
        # Forward pass  → summarises "where the ship came from"
        # Backward pass → summarises "where the ship is going"
        # Both perspectives are captured in the final hidden state.
        self.lstm = nn.LSTM(
            input_size  = hidden_size,       # matches input_proj output
            hidden_size = hidden_size,
            num_layers  = num_layers,
            batch_first = True,              # input shape: (batch, seq, feat)
            bidirectional = True,
            dropout = dropout if num_layers > 1 else 0.0,
        )

        # ── Output projection ─────────────────────────────────────────────
        # The final LSTM hidden state is hidden_size * 2 (bidirectional).
        # This projects it down to latent_dim — the vector the transformer
        # will receive. Also adds a non-linearity so the latent space is
        # not purely linear.
        self.output_proj = nn.Sequential(
            nn.Linear(hidden_size * 2, latent_dim),
            nn.LayerNorm(latent_dim),
            nn.Tanh(),           # bounds output to (-1, 1) — stable for
                                 # downstream transformer input
        )

    def forward(self, x: torch.Tensor, lengths: torch.Tensor = None) -> torch.Tensor:
        """
        Args:
            x       : (batch_size, seq_len, input_features)
                      The AIS track — one row per timestep.
                      Features should be normalised to roughly [0, 1]
                      before being passed in (see normalise_track below).

            lengths : (batch_size,) optional
                      Actual track length per ship in the batch.
                      If provided, the LSTM uses packed sequences so padding
                      tokens at the end of shorter tracks don't pollute the
                      hidden state. Pass this whenever tracks in a batch have
                      different lengths.

        Returns:
            latent  : (batch_size, latent_dim)
                      Fixed-size voyage summary — ready to concatenate with
                      the static encoder output and feed to the transformer.
        """

        # ── 1. Project input features ─────────────────────────────────────
        x = self.input_proj(x)          # (B, T, hidden_size)

        # ── 2. Pack sequences if lengths provided ─────────────────────────
        # Packing tells the LSTM to ignore padding at the end of shorter
        # tracks — important when tracks in a batch have different lengths.
        if lengths is not None:
            x = nn.utils.rnn.pack_padded_sequence(
                x, lengths.cpu(), batch_first=True, enforce_sorted=False
            )

        # ── 3. Run bidirectional LSTM ─────────────────────────────────────
        # hidden shape: (num_layers * 2, batch, hidden_size)
        # The *2 is because bidirectional produces two hidden states per layer
        _, (hidden, _) = self.lstm(x)

        # ── 4. Extract final layer hidden states ──────────────────────────
        # hidden[-2] = final forward  hidden state of last LSTM layer
        # hidden[-1] = final backward hidden state of last LSTM layer
        # Concatenating gives a vector that summarises the track from
        # both ends simultaneously.
        forward_h  = hidden[-2]                              # (B, hidden_size)
        backward_h = hidden[-1]                              # (B, hidden_size)
        combined   = torch.cat([forward_h, backward_h], dim=-1)  # (B, hidden*2)

        # ── 5. Project to latent space ────────────────────────────────────
        latent = self.output_proj(combined)                  # (B, latent_dim)

        return latent


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE NORMALISATION HELPER
# ─────────────────────────────────────────────────────────────────────────────

# Expected dynamic features and their approximate real-world ranges.
# Extend this dict if you add more features.
DYNAMIC_FEATURE_RANGES = {
    "lat":      (-90.0,   90.0),
    "lon":      (-180.0, 180.0),
    "sog":      (0.0,     35.0),   # knots — 35 is very fast for a vessel
    "cog":      (0.0,    360.0),   # degrees
    "heading":  (0.0,    360.0),   # degrees
    "msg_gap":  (0.0,    600.0),   # seconds between messages
}

def normalise_track(track: np.ndarray, feature_names: list) -> np.ndarray:
    """
    Normalises a raw AIS track to [0, 1] per feature.

    Args:
        track         : (seq_len, n_features) raw AIS values
        feature_names : list of feature names matching DYNAMIC_FEATURE_RANGES
                        e.g. ["lat", "lon", "sog", "cog"]

    Returns:
        normalised track of same shape, dtype float32
    """
    out = np.zeros_like(track, dtype=np.float32)
    for i, name in enumerate(feature_names):
        if name not in DYNAMIC_FEATURE_RANGES:
            raise ValueError(
                f"Unknown feature '{name}'. "
                f"Add it to DYNAMIC_FEATURE_RANGES or normalise manually."
            )
        lo, hi = DYNAMIC_FEATURE_RANGES[name]
        out[:, i] = (track[:, i] - lo) / (hi - lo)
    return np.clip(out, 0.0, 1.0)


def pad_tracks(tracks: list, feature_names: list):
    """
    Takes a list of variable-length tracks, normalises them, pads shorter
    ones with zeros so they can be batched together, and returns lengths
    for use with pack_padded_sequence.

    Args:
        tracks        : list of np.ndarrays, each (seq_len_i, n_features)
        feature_names : feature names for normalisation

    Returns:
        padded  : torch.Tensor  (n_ships, max_seq_len, n_features)
        lengths : torch.Tensor  (n_ships,) actual length of each track
    """
    normed  = [normalise_track(t, feature_names) for t in tracks]
    lengths = torch.tensor([len(t) for t in normed], dtype=torch.long)
    max_len = int(lengths.max())
    n_feat  = normed[0].shape[1]

    padded = torch.zeros(len(normed), max_len, n_feat)
    for i, t in enumerate(normed):
        padded[i, :len(t)] = torch.tensor(t)

    return padded, lengths


# ─────────────────────────────────────────────────────────────────────────────
# QUICK DEMO — shows exactly what shapes go in and out
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    print("=" * 60)
    print("Dynamic Encoder — shape walkthrough")
    print("=" * 60)

    FEATURE_NAMES = ["lat", "lon", "sog", "cog", "heading", "msg_gap"]
    N_FEATURES    = len(FEATURE_NAMES)

    # ── Build encoder ────────────────────────────────────────────────────
    encoder = DynamicEncoder(
        input_features = N_FEATURES,
        hidden_size    = 64,
        latent_dim     = 128,
        num_layers     = 2,
        dropout        = 0.1,
    )

    total_params = sum(p.numel() for p in encoder.parameters())
    print(f"\nEncoder parameters : {total_params:,}")
    print(f"Input features     : {N_FEATURES}  {FEATURE_NAMES}")
    print(f"LSTM hidden size   : 64  (× 2 bidirectional = 128)")
    print(f"Output latent dim  : 128")

    # ── Simulate a batch of 4 ships with different track lengths ─────────
    print("\n" + "─" * 60)
    print("Simulating batch of 4 ships with variable track lengths...")

    np.random.seed(0)
    raw_tracks = [
        # Each track is (seq_len, n_features) — raw unnormalised AIS values
        np.column_stack([
            np.random.uniform(50.5, 51.5, size=length),   # lat
            np.random.uniform(2.0,  4.0,  size=length),   # lon
            np.random.uniform(9.0,  15.0, size=length),   # sog
            np.random.uniform(45.0, 75.0, size=length),   # cog
            np.random.uniform(43.0, 77.0, size=length),   # heading
            np.random.uniform(8.0,  18.0, size=length),   # msg_gap
        ])
        for length in [200, 150, 87, 213]   # different voyage lengths
    ]

    print(f"\nRaw track lengths  : {[len(t) for t in raw_tracks]}")

    # ── Pad and normalise ─────────────────────────────────────────────────
    padded, lengths = pad_tracks(raw_tracks, FEATURE_NAMES)
    print(f"After padding      : {tuple(padded.shape)}  "
          f"(batch=4, max_seq=213, features={N_FEATURES})")
    print(f"Lengths tensor     : {lengths.tolist()}")

    # ── Run encoder ───────────────────────────────────────────────────────
    encoder.eval()
    with torch.no_grad():
        latent = encoder(padded, lengths=lengths)

    print(f"\nLatent output      : {tuple(latent.shape)}  "
          f"(batch=4, latent_dim=128)")
    print(f"Latent min/max     : {latent.min():.4f} / {latent.max():.4f}  "
          f"(tanh bounded to (-1, 1))")

    print("\n" + "─" * 60)
    print("Each ship's 200-point voyage is now a single 128-dim vector.")
    print("Ready to concatenate with static encoder output.")
    print("─" * 60)

    # ── Show what the transformer will receive ────────────────────────────
    print("\nExample: combining with a 64-dim static encoder output")
    static_placeholder = torch.zeros(4, 64)   # pretend static encoder output
    combined = torch.cat([latent, static_placeholder], dim=-1)
    print(f"Combined vector    : {tuple(combined.shape)}  "
          f"(batch=4, 128 dynamic + 64 static = 192 total)")
    print("\nThis combined vector feeds directly into the Transformer.")