"""
AIS Activity Detection — Gymnasium Environment

Wraps the AIS feature pipeline as a Gymnasium environment for training
a sequential activity classification agent.

Each episode is one vessel track from the synthetic simulator.  At every
step the agent observes the current segment's feature vector and must
predict the activity class.  Rewards are shaped to penalise missing
high-value events (STS, transshipment, bunkering) more than ordinary
misclassifications.

Usage::

    from src.rl_env import AISActivityEnv
    from src.rl_env import make_env

    env = make_env("brazil_eez", seed=42)
    obs, info = env.reset()
    obs, reward, terminated, truncated, info = env.step(env.action_space.sample())
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import gymnasium as gym
from gymnasium import spaces
from typing import Optional

from .classifier import ACTIVITY_FEATURES, ACTIVITY_LABELS

# ── Label index mapping ────────────────────────────────────────────────────────

LABEL_LIST = sorted(ACTIVITY_LABELS.keys())   # deterministic ordering
LABEL_TO_IDX = {lbl: i for i, lbl in enumerate(LABEL_LIST)}
IDX_TO_LABEL = {i: lbl for i, lbl in enumerate(LABEL_LIST)}
N_ACTIONS = len(LABEL_LIST)

# ── Reward shaping ─────────────────────────────────────────────────────────────

# Activities where a miss is costly (sanctions / IUU / unreported transfer)
HIGH_VALUE = {"sts", "transshipment", "bunkering"}

# Reward table: (pred == true, activity_class) → scalar
REWARD_CORRECT_BASE  =  1.0
REWARD_CORRECT_HV    =  2.5   # bonus for catching high-value events
REWARD_WRONG_BASE    = -0.5
REWARD_WRONG_MISS_HV = -2.0   # miss on a real high-value event
REWARD_WRONG_FA_HV   = -1.0   # false alarm on high-value


def shaped_reward(pred_label: str, true_label: str) -> float:
    """Compute shaped reward for one step."""
    correct = (pred_label == true_label)
    if correct:
        if true_label in HIGH_VALUE:
            return REWARD_CORRECT_BASE + REWARD_CORRECT_HV
        return REWARD_CORRECT_BASE
    else:
        base = REWARD_WRONG_BASE
        if true_label in HIGH_VALUE:
            base += REWARD_WRONG_MISS_HV
        if pred_label in HIGH_VALUE and true_label not in HIGH_VALUE:
            base += REWARD_WRONG_FA_HV
        return base


# ── Feature normalisation ──────────────────────────────────────────────────────

class RunningNormaliser:
    """Online mean/variance normaliser (Welford).  Applied per feature."""

    def __init__(self, n_features: int, eps: float = 1e-6):
        self.n = 0
        self.mean = np.zeros(n_features, dtype=np.float64)
        self.M2   = np.ones(n_features,  dtype=np.float64)
        self.eps  = eps

    def update(self, x: np.ndarray) -> None:
        self.n += 1
        delta  = x - self.mean
        self.mean += delta / self.n
        delta2 = x - self.mean
        self.M2 += delta * delta2

    def normalise(self, x: np.ndarray) -> np.ndarray:
        if self.n < 2:
            return x.astype(np.float32)
        std = np.sqrt(self.M2 / max(self.n - 1, 1) + self.eps)
        return ((x - self.mean) / std).astype(np.float32)

    def fit(self, X: np.ndarray) -> "RunningNormaliser":
        for row in X:
            self.update(row)
        return self


# ══════════════════════════════════════════════════════════════════════════════
# Core environment
# ══════════════════════════════════════════════════════════════════════════════

class AISActivityEnv(gym.Env):
    """
    Sequential AIS activity classification as a Gymnasium MDP.

    Observation
    -----------
    Feature vector of length ``len(ACTIVITY_FEATURES)`` (≈27 floats)
    for the current sliding-window segment, normalised by a RunningNormaliser
    fitted on training data.

    Action
    ------
    Integer index into ``LABEL_LIST`` (11 classes after Track B extension).

    Reward
    ------
    Shaped reward: correct +1 (high-value +2.5 bonus), wrong -0.5
    (-2 additional for missing a real high-value event).

    Episode
    -------
    One vessel's full sequence of segment windows, length varies by track.
    Terminated when all segments are consumed.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        feature_df: pd.DataFrame,
        normaliser: Optional[RunningNormaliser] = None,
        seed: Optional[int] = None,
        hv_oversample_factor: float = 5.0,
    ):
        # init for the gym class.
        super().__init__()

        n_feat = len(ACTIVITY_FEATURES)
        self.observation_space = spaces.Box(
            low=-10.0, high=10.0, shape=(n_feat,), dtype=np.float32
        )
        self.action_space = spaces.Discrete(N_ACTIONS)

        # Drop rows with unknown labels so the agent always has ground truth
        valid_labels = set(LABEL_LIST)
        df = feature_df.dropna(subset=["true_activity"])
        df = df[df["true_activity"].isin(valid_labels)].copy()
        df = df.reset_index(drop=True)

        # Group into per-vessel episodes by mmsi; each group = one episode
        self._episodes: list[pd.DataFrame] = [
            ep.reset_index(drop=True)
            for _, ep in df.groupby("mmsi", sort=False)
            if len(ep) >= 2
        ]

        if not self._episodes:
            raise ValueError("feature_df has no usable episodes (need ≥2 segments per mmsi).")

        self._normaliser = normaliser or RunningNormaliser(n_feat)
        self._rng = np.random.default_rng(seed)

        self._hv_oversample_factor = hv_oversample_factor
        self._episode_weights: np.ndarray = self._compute_episode_weights()

        self._step_idx = 0
        self._current: Optional[pd.DataFrame] = None

        # Metrics collected across the current episode
        self._ep_rewards: list[float] = []
        self._ep_correct: int = 0
        self._ep_hv_correct: int = 0
        self._ep_hv_total: int = 0

    # ── Gymnasium interface ────────────────────────────────────────────────────

    # ── Curriculum control ─────────────────────────────────────────────────────

    def set_curriculum_stage(self, t: float) -> None:
        """
        Update the HV oversample factor based on training progress t ∈ [0, 1].

        Phase schedule:
          t < 0.30  →  α = 20  (HV-heavy warm-up)
          t < 0.70  →  α = 8   (gradual broadening)
          t ≥ 0.70  →  α = 2   (near-uniform)
        """
        if t < 0.30:
            self._hv_oversample_factor = 20.0
        elif t < 0.70:
            self._hv_oversample_factor = 8.0
        else:
            self._hv_oversample_factor = 2.0
        self._episode_weights = self._compute_episode_weights()

    def _compute_episode_weights(self) -> np.ndarray:
        """Weight each episode by its HV segment count."""
        weights = np.array([
            1.0 + self._hv_oversample_factor * int(
                ep["true_activity"].isin(HIGH_VALUE).sum()
            )
            for ep in self._episodes
        ], dtype=np.float64)
        weights /= weights.sum()
        return weights

    # ── Gymnasium interface ────────────────────────────────────────────────────

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[dict] = None,
    ):
        super().reset(seed=seed)
        if seed is not None:
            self._rng = np.random.default_rng(seed)

        # Weighted episode sampling (Fix 1 + Fix 2 curriculum)
        ep_idx = int(self._rng.choice(len(self._episodes), p=self._episode_weights))
        self._current  = self._episodes[ep_idx]
        self._step_idx = 0
        self._ep_rewards   = []
        self._ep_correct   = 0
        self._ep_hv_correct = 0
        self._ep_hv_total   = 0

        return self._obs(), {}

    def step(self, action: int):
        assert self._current is not None, "Call reset() before step()."

        row = self._current.iloc[self._step_idx]
        true_lbl = str(row["true_activity"])
        pred_lbl = IDX_TO_LABEL.get(int(action), "transit")

        reward = shaped_reward(pred_lbl, true_lbl)
        self._ep_rewards.append(reward)
        if pred_lbl == true_lbl:
            self._ep_correct += 1
        if true_lbl in HIGH_VALUE:
            self._ep_hv_total += 1
            if pred_lbl == true_lbl:
                self._ep_hv_correct += 1

        self._step_idx += 1
        terminated = self._step_idx >= len(self._current)
        truncated  = False

        obs = self._obs() if not terminated else np.zeros(
            self.observation_space.shape, dtype=np.float32
        )

        info = {
            "true_activity": true_lbl,
            "pred_activity": pred_lbl,
            "correct": pred_lbl == true_lbl,
        }
        if terminated:
            n = len(self._ep_rewards)
            info.update({
                "episode_return":    float(sum(self._ep_rewards)),
                "episode_accuracy":  self._ep_correct / max(n, 1),
                "hv_recall":         self._ep_hv_correct / max(self._ep_hv_total, 1),
                "episode_length":    n,
            })

        return obs, reward, terminated, truncated, info

    # ── Internals ─────────────────────────────────────────────────────────────

    def _obs(self) -> np.ndarray:
        row  = self._current.iloc[self._step_idx]
        feat = row[ACTIVITY_FEATURES].fillna(0.0).values.astype(np.float64)
        self._normaliser.update(feat)
        return self._normaliser.normalise(feat)


# ══════════════════════════════════════════════════════════════════════════════
# Factory helper
# ══════════════════════════════════════════════════════════════════════════════

def make_env(
    region_key: str = "brazil_eez",
    n_extra_regions: int = 3,
    seed: int = 42,
) -> AISActivityEnv:
    """
    Build a training environment by simulating all four regions and
    computing segment features.

    Parameters
    ----------
    region_key : str
        Primary region to generate.
    n_extra_regions : int
        Number of additional regions to include for diversity (0-3).
    seed : int
        RNG seed for reproducibility.

    Returns
    -------
    AISActivityEnv
    """
    from .simulator import simulate_region
    from .features  import compute_segment_features

    all_regions = ["brazil_eez", "philippines_eez", "strait_of_malacca", "gulf_of_guinea"]
    regions_to_use = [region_key]
    for r in all_regions:
        if r != region_key and len(regions_to_use) <= n_extra_regions:
            regions_to_use.append(r)

    dfs = []
    for rk in regions_to_use:
        raw = simulate_region(rk)
        feats = compute_segment_features(raw, region_key=rk)
        dfs.append(feats)

    feat_df = pd.concat(dfs, ignore_index=True)

    # Fit normaliser on training data
    n_feat = len(ACTIVITY_FEATURES)
    norm = RunningNormaliser(n_feat)
    X = feat_df[ACTIVITY_FEATURES].fillna(0).values
    norm.fit(X)

    return AISActivityEnv(feat_df, normaliser=norm, seed=seed)
