import torch
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from backend.dark_vessels.src.Daxtons_AI_slop.dynamic_encoder import DynamicEncoder, pad_tracks
from backend.mcp_servers.ais.helpers.vessel_query import get_all_mmsis, get_vessel_position_history_helper

FEATURE_NAMES = ["lat", "lon", "sog", "cog", "heading"]
MAX_WORKERS   = 16    # tune this — start at 16, go higher if DB can handle it


def history_to_track(messages):
    if not messages:
        return None
    messages = sorted(messages, key=lambda m: m["basedatetime"])

    rows = []
    for msg in messages:
        if any(msg.get(f) is None for f in ["lat", "lon", "sog", "cog"]):
            continue
        rows.append([
            msg["lat"],
            msg["lon"],
            msg["sog"],
            msg["cog"],
            msg["heading"] if msg.get("heading") is not None else msg["cog"],
        ])
    if len(rows) < 5:
        return None
    return np.array(rows, dtype=np.float32)


def fetch_and_process(mmsi):
    """Fetches and converts one vessel — runs in a worker thread."""
    try:
        messages = get_vessel_position_history_helper(mmsi)
        track    = history_to_track(messages)
        if track is not None:
            return mmsi, track
    except Exception as e:
        print(f"  Warning: MMSI {mmsi} failed — {e}")
    return mmsi, None


def load_all_tracks(mmsis, max_workers=MAX_WORKERS):
    tracks       = []
    valid_mmsis  = []
    failed       = 0
    print_lock   = Lock()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_and_process, mmsi): mmsi for mmsi in mmsis}

        for i, future in enumerate(as_completed(futures), 1):
            mmsi, track = future.result()

            if track is not None:
                tracks.append(track)
                valid_mmsis.append(mmsi)
            else:
                failed += 1

            # Progress every 50 vessels
            if i % 50 == 0 or i == len(mmsis):
                with print_lock:
                    print(f"  {i}/{len(mmsis)} processed — "
                          f"{len(tracks)} valid, {failed} skipped")

    return tracks, valid_mmsis


# ── Main ──────────────────────────────────────────────────────────────────────


mmsis = get_all_mmsis()
print(f"Fetching tracks for {len(mmsis)} vessels with {MAX_WORKERS} threads...")

tracks, valid_mmsis = load_all_tracks(mmsis)
print(f"Loaded {len(tracks)} valid tracks from {len(mmsis)} vessels")

# ── Encode in batches instead of all at once ──────────────────────────────────
BATCH_SIZE = 32   # lower this to 16 if it still gets killed

encoder = DynamicEncoder(input_features=5, hidden_size=64, latent_dim=128)
encoder.eval()



all_latents = []

print(f"Encoding {len(tracks)} tracks in batches of {BATCH_SIZE}...")

with torch.no_grad():
    for i in range(0, len(tracks), BATCH_SIZE):
        batch_tracks = tracks[i : i + BATCH_SIZE]

        # Pad only this batch — much smaller tensor than padding everything
        batch_tensor, batch_lengths = pad_tracks(batch_tracks, FEATURE_NAMES)

        latent = encoder(batch_tensor, lengths=batch_lengths)
        all_latents.append(latent)

        print(f"  Batch {i // BATCH_SIZE + 1}/{(len(tracks) + BATCH_SIZE - 1) // BATCH_SIZE} done")

# Concatenate all batch outputs into one tensor
latent = torch.cat(all_latents, dim=0)
print(f"Latent output: {tuple(latent.shape)}")  # (352, 128)