"""
AIS Suspicious Ship Detection: Autoencoder + Transformer
=========================================================
Architecture:
  1. Autoencoder  — compresses each ship's 6 AIS features into a 3-dim
                    latent vector and learns what "normal" looks like.
                    Reconstruction error is an anomaly signal.
  2. Transformer  — takes the latent vectors of ALL ships in a local
                    area as a sequence and uses self-attention to decide
                    which ships are suspicious *in context of each other*.

Both components are trained end-to-end on synthetic data.
"""

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import random

torch.manual_seed(42)
np.random.seed(42)
random.seed(42)



FEATURE_NAMES = ["lat", "lon", "speed_kn", "course_deg", "heading_deg", "msg_gap_s"]

# Normalisation ranges (min, max) per feature
FEAT_RANGES = [
    (48.0,  52.0),   # lat
    (1.0,   10.0),   # lon
    (0.0,   35.0),   # speed
    (0.0,   360.0),  # course
    (0.0,   360.0),  # heading
    (5.0,   600.0),  # message gap
]

def normalise(raw: np.ndarray) -> np.ndarray:
    out = np.zeros_like(raw, dtype=np.float32)
    for i, (lo, hi) in enumerate(FEAT_RANGES):
        out[:, i] = (raw[:, i] - lo) / (hi - lo)
    return np.clip(out, 0.0, 1.0)

class Autoencoder(nn.Module):
    """
    Encodes 6 AIS features → 3-dim latent space → reconstructs 6 features.
    Trained to minimise reconstruction error on normal ships only.
    """
    def __init__(self, input_dim=6, latent_dim=3):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 32), nn.ReLU(),
            nn.Linear(32, 16),        nn.ReLU(),
            nn.Linear(16, latent_dim)
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 16), nn.ReLU(),
            nn.Linear(16, 32),         nn.ReLU(),
            nn.Linear(32, input_dim),  nn.Sigmoid()
        )

    def forward(self, x):
        z = self.encoder(x)
        return self.decoder(z), z

    def reconstruction_error(self, x):
        recon, _ = self.forward(x)
        return ((recon - x) ** 2).mean(dim=1)


class ShipTransformerClassifier(nn.Module):
    """
    Takes a sequence of latent vectors (one per ship in the area) plus
    their reconstruction errors and uses a Transformer encoder to
    classify each ship as suspicious (1) or normal (0).

    The self-attention lets each ship attend to every other ship in the
    same area — capturing relational / contextual anomalies.
    """
    def __init__(self, latent_dim=3, d_model=32, nhead=4, num_layers=2):
        super().__init__()
        # project (latent + recon_error) → d_model
        self.input_proj = nn.Linear(latent_dim + 1, d_model)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead,
            dim_feedforward=64, dropout=0.1, batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.classifier  = nn.Sequential(
            nn.Linear(d_model, 16), nn.ReLU(),
            nn.Linear(16, 1),       nn.Sigmoid()
        )

    def forward(self, z, recon_errors):
        """
        z            : (batch, seq_len, latent_dim)
        recon_errors : (batch, seq_len, 1)
        """
        x = torch.cat([z, recon_errors], dim=-1)   # (B, S, latent+1)
        x = self.input_proj(x)                      # (B, S, d_model)
        x = self.transformer(x)                     # (B, S, d_model)
        return self.classifier(x).squeeze(-1)       # (B, S)


# ─────────────────────────────────────────────
# 3.  TRAINING
# ─────────────────────────────────────────────

def train_autoencoder(ae, X_normal_norm, epochs=200, lr=1e-3):
    """Train AE on normal ships only — unsupervised."""
    opt = optim.Adam(ae.parameters(), lr=lr)
    t   = torch.tensor(X_normal_norm)
    losses = []
    for ep in range(epochs):
        ae.train()
        opt.zero_grad()
        recon, _ = ae(t)
        loss = nn.MSELoss()(recon, t)
        loss.backward()
        opt.step()
        losses.append(loss.item())
    return losses


def make_area_batches(X_norm, y, ae, group_size=8, n_batches=200):
    """
    Create synthetic 'area groups' for transformer training:
    randomly sample group_size ships (ensuring some suspicious ones),
    run through AE to get latent + recon_error, return as batches.
    """
    ae.eval()
    t    = torch.tensor(X_norm)
    with torch.no_grad():
        _, Z    = ae(t)
        E       = ae.reconstruction_error(t).unsqueeze(1)

    Z = Z.numpy()
    E = E.numpy()
    y_np = y.numpy() if isinstance(y, torch.Tensor) else y

    normal_idx = np.where(y_np == 0)[0]
    susp_idx   = np.where(y_np == 1)[0]

    zs, es, ys = [], [], []
    for _ in range(n_batches):
        n_s = random.randint(1, min(3, len(susp_idx)))
        n_n = group_size - n_s
        chosen = np.concatenate([
            np.random.choice(normal_idx, n_n, replace=True),
            np.random.choice(susp_idx,   n_s, replace=True)
        ])
        np.random.shuffle(chosen)
        zs.append(Z[chosen])
        es.append(E[chosen])
        ys.append(y_np[chosen])

    return (torch.tensor(np.stack(zs)),
            torch.tensor(np.stack(es)),
            torch.tensor(np.stack(ys)))


def train_transformer(tf, Z_bat, E_bat, Y_bat, epochs=150, lr=1e-3):
    """Train transformer classifier on area batches."""
    opt = optim.Adam(tf.parameters(), lr=lr)
    losses = []
    for ep in range(epochs):
        tf.train()
        opt.zero_grad()
        preds = tf(Z_bat, E_bat)            # (B, S)
        loss  = nn.BCELoss()(preds, Y_bat)
        loss.backward()
        opt.step()
        losses.append(loss.item())
    return losses


# ─────────────────────────────────────────────
# 4.  INFERENCE HELPER
# ─────────────────────────────────────────────

def predict_fleet(ae, tf, X_norm, group_size=None):
    """
    Run a full fleet through the pipeline.
    Returns reconstruction errors and transformer suspicion scores.
    """
    ae.eval(); tf.eval()
    t = torch.tensor(X_norm)
    with torch.no_grad():
        _, Z = ae(t)
        E    = ae.reconstruction_error(t)

    n = len(X_norm)
    if group_size is None:
        group_size = n

    # single group — all ships attend to each other
    Z_b = Z.unsqueeze(0)                   # (1, N, 3)
    E_b = E.unsqueeze(0).unsqueeze(-1)     # (1, N, 1)
    with torch.no_grad():
        scores = tf(Z_b, E_b).squeeze(0)  # (N,)

    return E.numpy(), scores.numpy()


# ─────────────────────────────────────────────
# 5.  VISUALISATION
# ─────────────────────────────────────────────

def plot_results(X_raw, y_true, atypes, recon_errors, tf_scores,
                 ae_losses, tf_losses, threshold=0.5):

    fig = plt.figure(figsize=(18, 12), facecolor='#0d1117')
    fig.suptitle('AIS Suspicious Ship Detection  ·  Autoencoder + Transformer',
                 color='white', fontsize=15, fontweight='bold', y=0.98)
    gs = GridSpec(3, 3, figure=fig, hspace=0.45, wspace=0.35)

    DARK   = '#0d1117'
    PANEL  = '#161b22'
    GRID   = '#21262d'
    GREEN  = '#3fb950'
    RED    = '#f85149'
    BLUE   = '#58a6ff'
    AMBER  = '#e3b341'
    WHITE  = '#e6edf3'
    MUTED  = '#8b949e'

    def style_ax(ax, title):
        ax.set_facecolor(PANEL)
        ax.spines[:].set_color(GRID)
        ax.tick_params(colors=MUTED, labelsize=8)
        ax.set_title(title, color=WHITE, fontsize=9, fontweight='bold', pad=6)
        ax.xaxis.label.set_color(MUTED)
        ax.yaxis.label.set_color(MUTED)
        for spine in ax.spines.values():
            spine.set_linewidth(0.5)

    colors_true = [GREEN if l == 0 else RED for l in y_true]

    # ── (0,0) Training losses ────────────────────────────────────────
    ax = fig.add_subplot(gs[0, 0])
    style_ax(ax, 'Training losses')
    ax.plot(ae_losses,  color=BLUE,  lw=1.2, label='Autoencoder (MSE)')
    ax.plot(tf_losses,  color=AMBER, lw=1.2, label='Transformer (BCE)')
    ax.set_xlabel('Epoch'); ax.set_ylabel('Loss')
    ax.legend(fontsize=7, labelcolor=MUTED,
              facecolor=PANEL, edgecolor=GRID)

    # ── (0,1) Reconstruction error per ship ─────────────────────────
    ax = fig.add_subplot(gs[0, 1])
    style_ax(ax, 'AE reconstruction error')
    xpos = np.arange(len(recon_errors))
    ax.bar(xpos, recon_errors, color=colors_true, width=0.8, alpha=0.85)
    ax.axhline(threshold * recon_errors.max(), color=AMBER,
               lw=1, ls='--', label=f'threshold')
    ax.set_xlabel('Ship index'); ax.set_ylabel('Recon error (MSE)')
    ax.legend(fontsize=7, labelcolor=MUTED,
              facecolor=PANEL, edgecolor=GRID)

    # ── (0,2) Transformer suspicion score ───────────────────────────
    ax = fig.add_subplot(gs[0, 2])
    style_ax(ax, 'Transformer suspicion score')
    bar_colors = [RED if s > 0.5 else GREEN for s in tf_scores]
    ax.bar(xpos, tf_scores, color=bar_colors, width=0.8, alpha=0.85)
    ax.axhline(0.5, color=AMBER, lw=1, ls='--', label='0.5 threshold')
    ax.set_ylim(0, 1)
    ax.set_xlabel('Ship index'); ax.set_ylabel('Suspicion score')
    ax.legend(fontsize=7, labelcolor=MUTED,
              facecolor=PANEL, edgecolor=GRID)

    # ── (1,0:2) Spatial map ─────────────────────────────────────────
    ax = fig.add_subplot(gs[1, 0:2])
    style_ax(ax, 'Fleet spatial view  (colour = ground truth,  size = suspicion score)')
    lats = X_raw[:, 0]; lons = X_raw[:, 1]
    sizes = 40 + tf_scores * 200
    sc = ax.scatter(lons, lats, c=colors_true, s=sizes,
                    alpha=0.85, edgecolors=GRID, linewidths=0.4, zorder=3)
    ax.set_xlabel('Longitude'); ax.set_ylabel('Latitude')
    ax.grid(color=GRID, lw=0.4, zorder=0)
    legend_handles = [
        mpatches.Patch(color=GREEN, label='Normal'),
        mpatches.Patch(color=RED,   label='Suspicious (true)'),
    ]
    ax.legend(handles=legend_handles, fontsize=7, labelcolor=MUTED,
              facecolor=PANEL, edgecolor=GRID)

    # ── (1,2) Recon error vs transformer score scatter ───────────────
    ax = fig.add_subplot(gs[1, 2])
    style_ax(ax, 'AE error vs transformer score')
    ax.scatter(recon_errors, tf_scores, c=colors_true,
               s=30, alpha=0.85, edgecolors=GRID, linewidths=0.3)
    ax.axvline(threshold * recon_errors.max(), color=AMBER,
               lw=0.8, ls='--', alpha=0.7)
    ax.axhline(0.5, color=BLUE, lw=0.8, ls='--', alpha=0.7)
    ax.set_xlabel('Recon error'); ax.set_ylabel('Suspicion score')
    ax.set_ylim(0, 1)

    # ── (2,0:3) Per-ship summary table ──────────────────────────────
    ax = fig.add_subplot(gs[2, :])
    ax.set_facecolor(PANEL)
    ax.axis('off')
    ax.set_title('Per-ship inference summary', color=WHITE,
                 fontsize=9, fontweight='bold', pad=6)

    col_labels = ['Ship', 'Type', 'Speed (kn)', 'Msg gap (s)',
                  'Recon error', 'Suspicion', 'Flagged', 'Correct?']
    table_data = []
    for i, (atype, re, ts, lab) in enumerate(
            zip(atypes, recon_errors, tf_scores, y_true)):
        flagged  = '⚑ YES' if ts > 0.5 else 'no'
        correct  = '✓' if (ts > 0.5) == (lab == 1) else '✗'
        table_data.append([
            f'V-{i+1:03d}', atype,
            f'{X_raw[i, 2]:.1f}', f'{X_raw[i, 5]:.0f}',
            f'{re:.4f}', f'{ts:.3f}', flagged, correct
        ])

    tbl = ax.table(cellText=table_data, colLabels=col_labels,
                   cellLoc='center', loc='center', bbox=[0, 0, 1, 1])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7.5)

    for (row, col), cell in tbl.get_celld().items():
        cell.set_facecolor(PANEL)
        cell.set_edgecolor(GRID)
        cell.set_linewidth(0.4)
        if row == 0:
            cell.set_text_props(color=WHITE, fontweight='bold')
        else:
            atype_val = table_data[row - 1][1]
            flagged_val = table_data[row - 1][6]
            correct_val = table_data[row - 1][7]
            if atype_val == 'normal':
                cell.set_text_props(color=GREEN)
            elif flagged_val == '⚑ YES':
                cell.set_text_props(color=RED)
            else:
                cell.set_text_props(color=MUTED)
            if col == 7:
                cell.set_text_props(
                    color=GREEN if correct_val == '✓' else RED)

    plt.savefig('/home/daxtonb/Actint/actint-backend/src/backend/dark_vessels/src/Daxtons_AI_slop/ais_detection_results.png',
                dpi=150, bbox_inches='tight', facecolor=DARK)
    print("Saved: ais_detection_results.png")
    plt.close()


# ─────────────────────────────────────────────
# 6.  MAIN
# ─────────────────────────────────────────────

if __name__ == '__main__':
    print("=" * 60)
    print("AIS AE + Transformer Detection Pipeline")
    print("=" * 60)

    # ── Generate data ───────────────────────────────────────────────
    print("\n[1/5] Generating synthetic fleet data...")
    X_raw, y, atypes = generate_fleet(n_normal=60, n_suspicious=10, seed=42)
    X_norm = normalise(X_raw)
    print(f"      {len(X_raw)} ships total  "
          f"({int(y.sum())} suspicious, {int((y==0).sum())} normal)")

    # ── Train autoencoder on normal ships only ───────────────────────
    print("\n[2/5] Training Autoencoder (unsupervised, normal ships only)...")
    ae = Autoencoder(input_dim=6, latent_dim=3)
    normal_mask = y == 0
    ae_losses = train_autoencoder(
        ae, X_norm[normal_mask], epochs=300, lr=1e-3)
    print(f"      Final AE loss: {ae_losses[-1]:.6f}")

    # ── Build area-group batches ─────────────────────────────────────
    print("\n[3/5] Building area-group batches for transformer...")
    X_t = torch.tensor(X_norm)
    y_t = torch.tensor(y)
    Z_bat, E_bat, Y_bat = make_area_batches(
        X_norm, y_t, ae, group_size=8, n_batches=400)
    print(f"      {len(Z_bat)} batches of 8 ships each")

    # ── Train transformer ────────────────────────────────────────────
    print("\n[4/5] Training Transformer classifier...")
    tf = ShipTransformerClassifier(latent_dim=3, d_model=32, nhead=4, num_layers=2)
    tf_losses = train_transformer(tf, Z_bat, E_bat, Y_bat, epochs=200, lr=1e-3)
    print(f"      Final Transformer loss: {tf_losses[-1]:.6f}")

    # ── Inference on full fleet ──────────────────────────────────────
    print("\n[5/5] Running inference on full fleet...")
    recon_errors, tf_scores = predict_fleet(ae, tf, X_norm)

    # ── Print summary ────────────────────────────────────────────────
    flagged   = tf_scores > 0.5
    true_pos  = int(( flagged & (y == 1)).sum())
    false_pos = int(( flagged & (y == 0)).sum())
    false_neg = int((~flagged & (y == 1)).sum())
    precision = true_pos / max(flagged.sum(), 1)
    recall    = true_pos / max((y == 1).sum(), 1)
    f1        = 2 * precision * recall / max(precision + recall, 1e-9)

    print(f"\n  True positives : {true_pos}")
    print(f"  False positives: {false_pos}")
    print(f"  False negatives: {false_neg}")
    print(f"  Precision      : {precision:.2%}")
    print(f"  Recall         : {recall:.2%}")
    print(f"  F1 score       : {f1:.2%}")

    # ── Plot ─────────────────────────────────────────────────────────
    print("\nGenerating visualisation...")
    plot_results(X_raw, y, atypes, recon_errors, tf_scores,
                 ae_losses, tf_losses)

    print("\nDone.")