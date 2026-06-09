"""
DQN Agent for AIS Activity Detection

Implements a Double-DQN with a Dueling network architecture and
prioritised-ish experience replay (uniform for now, easy to upgrade).

Key design choices
------------------
* Dueling head (value + advantage streams) reduces variance on the many
  "transit" majority-class steps.
* Double DQN: action selected with online net, value evaluated with target
  net — prevents Q overestimation.
* Shaped reward from rl_env penalises misses on high-value events more
  strongly, so the agent learns to be conservative on rare classes.
* Layer-norm after the first linear layer stabilises training on the
  diverse range of feature magnitudes from AIS data.

Usage::

    from src.rl_agent import DQNAgent
    from src.rl_env   import AISActivityEnv, make_env, N_ACTIONS, LABEL_LIST

    env   = make_env("brazil_eez")
    agent = DQNAgent(obs_dim=len(ACTIVITY_FEATURES), n_actions=N_ACTIONS)
    agent.train(env, total_steps=200_000)
    agent.save("outputs/rl/dqn_activity.pt")
"""

from __future__ import annotations

import math
import random
from collections import deque
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from .classifier import ACTIVITY_FEATURES
from .rl_env import (
    AISActivityEnv, IDX_TO_LABEL, LABEL_LIST, N_ACTIONS, shaped_reward
)


# ══════════════════════════════════════════════════════════════════════════════
# Replay buffer
# ══════════════════════════════════════════════════════════════════════════════

class ReplayBuffer:
    """
    Fixed-capacity circular replay buffer backed by pre-allocated NumPy arrays.
    Supports batched sampling for vectorised GPU training.
    """

    def __init__(self, capacity: int, obs_dim: int):
        self.capacity = capacity
        self.obs_dim  = obs_dim
        self.pos      = 0
        self.size     = 0

        self.obs      = np.zeros((capacity, obs_dim), dtype=np.float32)
        self.next_obs = np.zeros((capacity, obs_dim), dtype=np.float32)
        self.actions  = np.zeros(capacity,            dtype=np.int64)
        self.rewards  = np.zeros(capacity,            dtype=np.float32)
        self.dones    = np.zeros(capacity,            dtype=np.float32)

    def add(
        self,
        obs:      np.ndarray,
        action:   int,
        reward:   float,
        next_obs: np.ndarray,
        done:     bool,
    ) -> None:
        self.obs[self.pos]      = obs
        self.next_obs[self.pos] = next_obs
        self.actions[self.pos]  = action
        self.rewards[self.pos]  = reward
        self.dones[self.pos]    = float(done)
        self.pos  = (self.pos + 1) % self.capacity
        self.size = min(self.size + 1, self.capacity)

    def sample(self, batch_size: int, device: torch.device):
        idx = np.random.choice(self.size, batch_size, replace=False)
        return (
            torch.FloatTensor(self.obs[idx]).to(device),
            torch.LongTensor(self.actions[idx]).to(device),
            torch.FloatTensor(self.rewards[idx]).to(device),
            torch.FloatTensor(self.next_obs[idx]).to(device),
            torch.FloatTensor(self.dones[idx]).to(device),
        )

    def __len__(self) -> int:
        return self.size


# ══════════════════════════════════════════════════════════════════════════════
# Dueling DQN network
# ══════════════════════════════════════════════════════════════════════════════

class DuelingQNetwork(nn.Module):
    """
    Dueling DQN architecture:
        shared encoder → value stream V(s)
                       → advantage stream A(s,a)
        Q(s,a) = V(s) + A(s,a) - mean_a A(s,a)

    The dueling decomposition helps when many actions have similar value
    (e.g., most AIS segments are "transit" and all actions give similar Q).
    """

# The neural network splits of into two different heads with one head (V) correlating to how interesting/suspicious the vessel is and the other head (A) is the most likely readons why the situation is interesting.
# Q is the combination of both of those. 

    def __init__(self, obs_dim: int, n_actions: int, hidden: int = 256):
        super().__init__()

        self.encoder = nn.Sequential(
            nn.Linear(obs_dim, hidden),
            nn.LayerNorm(hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden // 2),
            nn.ReLU(),
        )

        half = hidden // 2
        self.value_head = nn.Sequential(
            nn.Linear(half, half // 2),
            nn.ReLU(),
            nn.Linear(half // 2, 1),
        )
        self.adv_head = nn.Sequential(
            nn.Linear(half, half // 2),
            nn.ReLU(),
            nn.Linear(half // 2, n_actions),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h   = self.encoder(x)
        V   = self.value_head(h)                        # (B, 1)
        A   = self.adv_head(h)                          # (B, n_actions)
        Q   = V + A - A.mean(dim=1, keepdim=True)       # dueling combination
        return Q


# ══════════════════════════════════════════════════════════════════════════════
# DQN Agent
# ══════════════════════════════════════════════════════════════════════════════

class DQNAgent:
    """
    Double-DQN agent for sequential AIS activity classification.

    Training loop
    -------------
    Call ``train(env, total_steps)`` to run the full training loop.
    Alternatively call ``select_action`` / ``store`` / ``update`` manually
    for integration with custom training harnesses.
    """

    def __init__(
        self,
        obs_dim:         int  = len(ACTIVITY_FEATURES),
        n_actions:       int  = N_ACTIONS,
        hidden:          int  = 256,
        lr:              float = 3e-4,
        gamma:           float = 0.95,
        buffer_capacity: int  = 100_000,
        batch_size:      int  = 128,
        target_update:   int  = 500,     # hard-update every N gradient steps
        eps_start:       float = 1.0,
        eps_end:         float = 0.05,
        eps_decay_steps: int  = 50_000,
        warmup_steps:    int  = 2_000,
        device:          Optional[str] = None,
    ):
        self.n_actions  = n_actions
        self.gamma      = gamma
        self.batch_size = batch_size
        self.target_update = target_update
        self.warmup_steps  = warmup_steps

        self.eps_start = eps_start
        self.eps_end   = eps_end
        self.eps_decay_steps = eps_decay_steps

        self.device = torch.device(
            device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        )

        self.q_net     = DuelingQNetwork(obs_dim, n_actions, hidden).to(self.device)
        self.target_net= DuelingQNetwork(obs_dim, n_actions, hidden).to(self.device)
        self.target_net.load_state_dict(self.q_net.state_dict())
        self.target_net.eval()

        self.optimizer = torch.optim.Adam(self.q_net.parameters(), lr=lr)
        self.buffer    = ReplayBuffer(buffer_capacity, obs_dim)

        self._grad_steps = 0
        self._total_steps = 0

    # ── Action selection ───────────────────────────────────────────────────────

    def epsilon(self) -> float:
        t = min(self._total_steps, self.eps_decay_steps)
        frac = t / self.eps_decay_steps
        return self.eps_end + (self.eps_start - self.eps_end) * math.exp(-5 * frac)

    def select_action(self, obs: np.ndarray, greedy: bool = False) -> int:
        if not greedy and random.random() < self.epsilon():
            return random.randint(0, self.n_actions - 1)
        with torch.no_grad():
            t_obs = torch.FloatTensor(obs).unsqueeze(0).to(self.device)
            q     = self.q_net(t_obs)
            return int(q.argmax(dim=1).item())

    # ── Learning ──────────────────────────────────────────────────────────────

    def store(
        self,
        obs:      np.ndarray,
        action:   int,
        reward:   float,
        next_obs: np.ndarray,
        done:     bool,
    ) -> None:
        self.buffer.add(obs, action, reward, next_obs, done)
        self._total_steps += 1

    def update(self) -> Optional[float]:
        """One gradient step.  Returns loss or None if buffer not warm."""
        if len(self.buffer) < self.warmup_steps:
            return None

        obs, actions, rewards, next_obs, dones = self.buffer.sample(
            self.batch_size, self.device
        )

        with torch.no_grad():
            # Double DQN: online net picks action, target net evaluates value

            # Gets the incidies of the best action for each pair of ovservations
            next_actions = self.q_net(next_obs).argmax(dim=1, keepdim=True)

            # Take the next actions and get the Q values from the FROZEN network. 
            next_q = self.target_net(next_obs).gather(1, next_actions).squeeze(1)

            #The reason for this little bit of extra added complexty from the last two commands is to keep the neural network grounded for a few hundred steps so it doesn't move too drasically

            #calculate what the Q value should have been using rewards/punishments. (0 if done, epsilon is a constant which slightly decreases the pull of q on the whole system.)
            # Because the confidence gets larger, the reward is relatively smaller (becuase it is constant)
            target_q = rewards + self.gamma * next_q * (1 - dones)

        # Get the Q for what the AI actually predicted. 
        current_q = self.q_net(obs).gather(1, actions.unsqueeze(1)).squeeze(1)

        # Calculates how far off the predictions were from what q was calculated to have been. 
        loss = F.smooth_l1_loss(current_q, target_q)

        # Clear gradiant from previous update. 
        self.optimizer.zero_grad()

        # trace back through the neural network and calculate how much each neuron contributed to the error
        loss.backward()

        # For safety so gradients can't be massively changed. Too large of a change can cause problems.
        nn.utils.clip_grad_norm_(self.q_net.parameters(), 10.0)

        # Actually modify the weights in a way that lessens the error.
        self.optimizer.step()

        self._grad_steps += 1

        # make the target network a copy of the learning network every few hundred steps.
        if self._grad_steps % self.target_update == 0:
            self.target_net.load_state_dict(self.q_net.state_dict())

        return float(loss.item())

    # ── Full training loop ────────────────────────────────────────────────────

    def train(
        self,
        env:              AISActivityEnv,
        total_steps:      int  = 200_000,
        eval_every:       int  = 5_000,
        eval_env:         Optional[AISActivityEnv] = None,
        log_every:        int  = 1_000,
        save_dir:         Optional[str] = None,
        step_callback=    None,
    ) -> dict:
        """
        Train the agent for ``total_steps`` environment steps.

        Parameters
        ----------
        env : AISActivityEnv
            Training environment.
        total_steps : int
            Total env steps to run.
        eval_every : int
            Evaluate on ``eval_env`` every N training steps.
        eval_env : AISActivityEnv, optional
            Separate evaluation environment (held-out data).  If None,
            evaluation is skipped.
        log_every : int
            Print a progress line every N steps.
        save_dir : str, optional
            If provided, save the best checkpoint to ``<save_dir>/dqn_best.pt``.

        Returns
        -------
        dict
            Training history: lists of losses, returns, accuracies.
        """
        history = {
            "steps": [], "loss": [], "ep_return": [],
            "ep_accuracy": [], "hv_recall": [],
            "eval_accuracy": [], "eval_hv_recall": [],
        }
        best_eval_acc = -1.0
        save_path     = Path(save_dir) / "dqn_best.pt" if save_dir else None
        if save_dir:
            Path(save_dir).mkdir(parents=True, exist_ok=True)

        obs, _ = env.reset()
        ep_losses = []

        step = 0
        #This just loops through and trains. Stores the result, stores the loss and gets the next step every loop. Fairly basic function. There is a lot of printing and logging though.
        while step < total_steps:
            action  = self.select_action(obs)
            next_obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated

            self.store(obs, action, reward, next_obs, done)
            loss = self.update()
            if loss is not None:
                ep_losses.append(loss)

            if done:
                if "episode_return" in info:
                    history["steps"].append(step)
                    history["ep_return"].append(info["episode_return"])
                    history["ep_accuracy"].append(info["episode_accuracy"])
                    history["hv_recall"].append(info["hv_recall"])
                    if ep_losses:
                        history["loss"].append(float(np.mean(ep_losses)))
                    ep_losses = []

                    if step % log_every < 500:
                        print(
                            f"  step={step:>7d}  eps={self.epsilon():.3f}"
                            f"  ret={info['episode_return']:+.1f}"
                            f"  acc={info['episode_accuracy']:.3f}"
                            f"  hv_recall={info['hv_recall']:.3f}"
                            f"  loss={history['loss'][-1]:.4f}"
                            if history["loss"] else
                            f"  step={step:>7d}  [warming up replay buffer]"
                        )

                obs, _ = env.reset()
            else:
                obs = next_obs

            # Curriculum / periodic callback
            if step_callback is not None and step > 0 and step % eval_every == 0:
                step_callback(step)

            # Periodic evaluation
            if eval_env is not None and step > 0 and step % eval_every == 0:
                eval_metrics = self.evaluate(eval_env, n_episodes=20)
                history["eval_accuracy"].append(eval_metrics["accuracy"])
                history["eval_hv_recall"].append(eval_metrics["hv_recall"])
                print(
                    f"\n  [EVAL @ {step}]  acc={eval_metrics['accuracy']:.4f}"
                    f"  hv_recall={eval_metrics['hv_recall']:.4f}\n"
                )
                if save_path and eval_metrics["accuracy"] > best_eval_acc:
                    best_eval_acc = eval_metrics["accuracy"]
                    self.save(str(save_path))
                    print(f"  → New best checkpoint saved ({best_eval_acc:.4f})")

            step += 1

        return history

    # ── Evaluation ────────────────────────────────────────────────────────────

# Returns information about the training
    def evaluate(
        self,
        env:         AISActivityEnv,
        n_episodes:  int = 50,
    ) -> dict:
        """
        Greedy evaluation over ``n_episodes`` episodes.

        Returns
        -------
        dict
            accuracy, hv_recall, per_class_accuracy, confusion dict.
        """
        from collections import defaultdict

        all_true  = []
        all_pred  = []
        total_ret = 0.0
        hv_correct = hv_total = 0

        for _ in range(n_episodes):
            obs, _ = env.reset()
            done   = False
            while not done:
                action = self.select_action(obs, greedy=True)
                obs, reward, terminated, truncated, info = env.step(action)
                done = terminated or truncated

                all_true.append(info["true_activity"])
                all_pred.append(info["pred_activity"])
                if "episode_return" in info:
                    total_ret += info["episode_return"]
                if info["true_activity"] in {"sts", "transshipment", "bunkering"}:
                    hv_total  += 1
                    if info["correct"]:
                        hv_correct += 1

        accuracy = float(np.mean([t == p for t, p in zip(all_true, all_pred)]))

        # Per-class accuracy
        per_class: dict[str, list] = defaultdict(list)
        for t, p in zip(all_true, all_pred):
            per_class[t].append(t == p)
        per_class_acc = {k: float(np.mean(v)) for k, v in per_class.items()}

        return {
            "accuracy":        accuracy,
            "hv_recall":       hv_correct / max(hv_total, 1),
            "per_class_acc":   per_class_acc,
            "n_steps":         len(all_true),
            "mean_return":     total_ret / n_episodes,
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        torch.save({
            "q_net_state":    self.q_net.state_dict(),
            "target_state":   self.target_net.state_dict(),
            "optimizer_state": self.optimizer.state_dict(),
            "grad_steps":     self._grad_steps,
            "total_steps":    self._total_steps,
            "label_list":     LABEL_LIST,
        }, path)
        print(f"  Saved checkpoint → {path}")

    @classmethod
    def load(cls, path: str, **kwargs) -> "DQNAgent":
        data   = torch.load(path, weights_only=False)
        agent  = cls(**kwargs)
        agent.q_net.load_state_dict(data["q_net_state"])
        agent.target_net.load_state_dict(data["target_state"])
        agent.optimizer.load_state_dict(data["optimizer_state"])
        agent._grad_steps  = data.get("grad_steps", 0)
        agent._total_steps = data.get("total_steps", 0)
        return agent

    def predict(self, obs: np.ndarray) -> tuple[str, np.ndarray]:
        """
        Single-step greedy prediction.

        Returns
        -------
        label : str
            Predicted activity label.
        q_values : np.ndarray
            Raw Q-values for all classes (proxy for confidence).
        """
        with torch.no_grad():
            t_obs = torch.FloatTensor(obs).unsqueeze(0).to(self.device)
            q     = self.q_net(t_obs).squeeze(0).cpu().numpy()
        label = IDX_TO_LABEL[int(q.argmax())]
        return label, q
