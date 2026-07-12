"""Deterministic SB3 training for the STOM portfolio env (Stage B).

This is the Stage-B trainer that turns the Stage-A Gymnasium adapter
(:func:`stom_rl.portfolio_sb3_adapter.make_portfolio_sb3_env`) into a *trained*,
deterministic SB3 ``PPO``/``DQN`` policy, then exposes that policy as a
``PolicyFn`` for the ``portfolio_walk_forward._fit_policy`` seam (the
``trained_ppo`` baseline).

REUSED from ``stom_rl.sb3_smoke`` (cited):
    * ``_sb3_imports`` (:79)  -> :func:`_sb3_imports` here (same import shim).
    * ``_torch_runtime`` (:86) -> determinism pins + runtime probe.
    * ``_check_env`` (:111)    -> the ``check_env`` invocation pattern.
    * ``_train_model`` (:130)  -> the PPO/DQN construction + ``model.learn`` loop
      and the bounded ``n_steps``/``batch_size`` clamping.
    * ``_evaluate_model`` (:354) -> the ``model.predict(deterministic=True)`` eval
      pattern (here folded into the masked obs-decode ``PolicyFn``).

NET-NEW here (not in ``sb3_smoke``):
    * Determinism HARDENING: ``torch.use_deterministic_algorithms(True)``,
      ``torch.set_num_threads(1)``, ``device="cpu"``, all RNGs seeded, plus a
      reproducibility assertion within an explicit ``atol=1e-6, rtol=1e-5`` on
      eval metrics (sb3_smoke never asserts byte/metric reproducibility).
    * A *portfolio* obs-decode ``PolicyFn`` (:func:`make_trained_policy_fn`) that
      respects the multi-asset ``action_mask`` by selecting the best *valid*
      action — sb3_smoke's single-symbol eval has no portfolio masking.
    * An eval **invalid-action rate** measurement feeding the MaskablePPO trigger
      (penalty-PPO-first; ``sb3-contrib`` is NOT installed here — only the trigger
      is recorded per the plan's Option-C decision).

Determinism is enforced, not hoped for: SB3+torch is not bit-reproducible by
default, so the pins above are applied at import-of-torch time inside
:func:`apply_determinism`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .portfolio_env import ACTION_HOLD, PortfolioEnv
from .daily_portfolio_sb3_dataset import (
    DailyPortfolioSb3DatasetConfig,
    build_daily_portfolio_sb3_dataset,
    write_daily_portfolio_sb3_dataset,
)
from .portfolio_sb3_adapter import PortfolioSb3GymEnv, make_portfolio_sb3_env
from .rl_events import RlLiveEventWriter, summarize_live_event_file


# Live-event semantics for the SB3 *training loop* (Story A): the trainer streams
# per-rollout telemetry into the SAME ``rl_live_events.jsonl`` schema the
# deterministic ``portfolio_train`` smoke emits, so the dashboard's realtime
# follow/replay view watches the model learn.  ``algorithm`` is the per-algorithm
# label the dashboard groups by; ``phase`` is always "train" for this stream.
PORTFOLIO_TRAIN_LIVE_ALGORITHM = {"ppo": "portfolio_ppo", "dqn": "portfolio_dqn"}
PORTFOLIO_TRAIN_LIVE_PHASE = "train"
# Dashboard signature file written into the train run dir so the existing
# ``iter_run_dirs``/``_detect_artifact_type`` recognises the directory as a run
# and serves the ``rl_live_events.jsonl`` through ``/table/events``.
SB3_SMOKE_SIGNATURE_FILE = "sb3_smoke_summary.json"


# Stage-B trigger threshold (Section 1 Decision, Option C "penalty-PPO-first"):
# adopt sb3-contrib MaskablePPO ONLY if the eval invalid-action rate exceeds this
# OR training reward fails to beat no_trade across >=2 seeds.  We never install
# sb3-contrib here; we only RECORD whether the trigger fired.
MASKABLE_PPO_INVALID_ACTION_TRIGGER: float = 0.05

DEFAULT_DEEP_RL_TRAIN_OUTPUT_DIR = Path(".omx") / "artifacts" / "deep_rl" / "stageB_train"


DEFAULT_DAILY_PORTFOLIO_SB3_OUTPUT_DIR = Path("webui") / "rl_runs" / "daily_ohlcv_portfolio_sb3"


@dataclass(frozen=True)
class PortfolioSb3TrainConfig:
    """Bounded, deterministic SB3 training config for the portfolio env."""

    candidate_path: Optional[str] = None
    output_dir: str = str(DEFAULT_DEEP_RL_TRAIN_OUTPUT_DIR)
    algorithm: str = "ppo"  # "ppo" | "dqn"
    total_timesteps: int = 5_000
    top_k_candidates: int = 3
    max_positions: int = 2
    initial_cash: float = 1_000_000.0
    buy_fraction: float = 0.25
    cost_bps: float = 25.0
    slippage_bps: float = 0.0
    invalid_action_penalty: float = 0.001
    # Cost-aware reward: must be > 0 for Stage B (the env teaches the policy to
    # trade only when worth the execution cost).
    turnover_penalty_lambda: float = 1.0
    seed: int = 100
    device: str = "cpu"  # pinned for determinism (see apply_determinism)
    ppo_n_steps: int = 256
    ppo_batch_size: int = 64
    ppo_n_epochs: int = 4
    dqn_learning_starts: int = 64
    dqn_buffer_size: int = 4_096
    dqn_batch_size: int = 64
    max_eval_steps: int = 64
    write_artifacts: bool = True
    # Story A: stream per-rollout training telemetry into ``rl_live_events.jsonl``
    # so the dashboard can watch the model learn in real time.  Default-on, but
    # write-only (a pure side-effect): the callback never touches the env, RNG, or
    # the gradient step, so determinism (V4) is preserved.  Events are only written
    # when this flag is on AND ``write_artifacts`` yields a real output path.
    write_training_events: bool = True


# --------------------------------------------------------------------------- #
# REUSE: sb3_smoke import shim + runtime probe.
# --------------------------------------------------------------------------- #
def _sb3_imports():
    """Mirror ``sb3_smoke._sb3_imports`` (:79): lazy SB3 import shim."""

    from stable_baselines3 import DQN, PPO
    from stable_baselines3.common.env_checker import check_env

    return DQN, PPO, check_env


def apply_determinism(seed: int, *, device: str = "cpu") -> Dict[str, Any]:
    """Pin every RNG + torch flag so the same seed reproduces eval metrics.

    NET-NEW vs sb3_smoke (which never pins these).  Applies, in order:
      * ``random.seed`` / ``np.random.seed`` / ``torch.manual_seed``.
      * ``torch.use_deterministic_algorithms(True)`` (raises on nondeterministic
        kernels rather than silently diverging).
      * ``torch.set_num_threads(1)`` (multi-thread reductions are nondeterministic).
      * ``device="cpu"`` for the determinism rerun (CUDA is not bit-reproducible).

    Returns the runtime probe (mirrors ``sb3_smoke._torch_runtime`` :86) plus the
    pins applied, for evidence logging.
    """

    import random as _random

    import torch

    _random.seed(int(seed))
    np.random.seed(int(seed))
    torch.manual_seed(int(seed))
    if torch.cuda.is_available():  # pragma: no cover - CPU CI has no CUDA
        torch.cuda.manual_seed_all(int(seed))
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)
    return {
        "torch_version": torch.__version__,
        "cuda_available": bool(torch.cuda.is_available()),
        "device_pinned": device,
        "use_deterministic_algorithms": True,
        "num_threads": 1,
        "seed": int(seed),
    }


def _bounded(value: int, *, lo: int, hi: int) -> int:
    return max(lo, min(int(value), hi))


def _make_training_callback(
    algorithm: str,
    *,
    event_writer: RlLiveEventWriter,
) -> Any:
    """Build an SB3 ``BaseCallback`` that streams per-rollout training telemetry.

    Story A (NET-NEW): ``model.learn`` runs silently by default.  This callback
    reads the rollout stats SB3 already maintains and appends one ``RlLiveEvent``
    per rollout (and a final flush at training end) so the dashboard's realtime
    follow/replay view watches the model learn — the "watch it learn" experience.

    Stats emitted per event:
      * ``global_step`` = ``self.num_timesteps`` (monotonic across rollouts).
      * ``reward``      = mean episode reward over ``ep_info_buffer`` (the rolling
        window SB3 logs as ``rollout/ep_rew_mean``); falls back to the latest
        logged value, then 0.0 if no episode has finished yet.
      * ``loss``        = the most recent ``train/loss`` (PPO) /
        ``train/loss``-equivalent from ``logger.name_to_value`` if the optimiser
        has stepped, else ``None`` (first rollout hasn't trained yet).
      * ``equity``      = OMITTED — no cheap mid-train NAV is available without a
        full eval rollout, which would perturb determinism; left ``None``.
      * ``info``        = ``{timesteps, iterations, ep_count}`` for context.

    The callback is WRITE-ONLY: it never reads/writes the env, RNG, or gradient,
    so a fixed seed still reproduces eval metrics (determinism V4 preserved).
    """

    from stable_baselines3.common.callbacks import BaseCallback

    live_algorithm = PORTFOLIO_TRAIN_LIVE_ALGORITHM.get(
        algorithm.lower(), f"portfolio_{algorithm.lower()}"
    )

    class RlLiveEventTrainingCallback(BaseCallback):
        """Append-only RL live-event emitter driven by SB3 rollout hooks."""

        def __init__(self) -> None:
            super().__init__(verbose=0)
            self._iterations = 0

        def _mean_episode_reward(self) -> Optional[float]:
            buffer = getattr(self.model, "ep_info_buffer", None)
            if buffer:
                rewards = [ep.get("r") for ep in buffer if ep.get("r") is not None]
                if rewards:
                    return float(np.mean(rewards))
            logged = self.logger.name_to_value.get("rollout/ep_rew_mean") if self.logger else None
            return float(logged) if logged is not None else None

        def _latest_loss(self) -> Optional[float]:
            if not self.logger:
                return None
            values = self.logger.name_to_value
            for key in ("train/loss", "train/value_loss", "train/policy_gradient_loss"):
                value = values.get(key)
                if value is not None:
                    try:
                        candidate = float(value)
                    except (TypeError, ValueError):
                        continue
                    if np.isfinite(candidate):
                        return candidate
            return None

        def _ep_count(self) -> int:
            buffer = getattr(self.model, "ep_info_buffer", None)
            return int(len(buffer)) if buffer else 0

        def _emit(self) -> None:
            reward = self._mean_episode_reward()
            event_writer.write_step(
                algorithm=live_algorithm,
                phase=PORTFOLIO_TRAIN_LIVE_PHASE,
                global_step=int(self.num_timesteps),
                reward=reward if reward is not None else 0.0,
                loss=self._latest_loss(),
                source="portfolio_sb3_train",
                info={
                    "timesteps": int(self.num_timesteps),
                    "iterations": int(self._iterations),
                    "ep_count": self._ep_count(),
                },
            )

        def _on_step(self) -> bool:  # noqa: D401 - SB3 hook
            return True

        def _on_rollout_end(self) -> None:  # noqa: D401 - SB3 hook
            self._iterations += 1
            self._emit()

        def _on_training_end(self) -> None:  # noqa: D401 - SB3 hook
            # Final flush so short runs (no completed rollout boundary) still
            # produce at least one terminal event carrying the last stats.
            self._emit()

    return RlLiveEventTrainingCallback()


def _make_train_env(
    config: PortfolioSb3TrainConfig,
    *,
    candidates: Optional[pd.DataFrame] = None,
) -> PortfolioSb3GymEnv:
    """Build the Stage-A Gym env for training (cost-aware reward via λ>0)."""

    return make_portfolio_sb3_env(
        candidate_path=config.candidate_path,
        candidates=candidates,
        top_k_candidates=config.top_k_candidates,
        max_positions=config.max_positions,
        initial_cash=config.initial_cash,
        buy_fraction=config.buy_fraction,
        cost_bps=config.cost_bps,
        slippage_bps=config.slippage_bps,
        invalid_action_penalty=config.invalid_action_penalty,
        turnover_penalty_lambda=config.turnover_penalty_lambda,
        seed=config.seed,
    )


def check_train_env(config: PortfolioSb3TrainConfig) -> Dict[str, Any]:
    """REUSE: sb3_smoke ``_check_env`` (:111) pattern on the portfolio adapter."""

    _, _, check_env = _sb3_imports()
    env = _make_train_env(config)
    try:
        check_env(env, warn=True, skip_render_check=True)
        return {
            "passed": True,
            "observation_space": str(env.observation_space),
            "action_space": str(env.action_space),
        }
    finally:
        env.close()


def train_portfolio_model(
    config: PortfolioSb3TrainConfig,
    *,
    candidates: Optional[pd.DataFrame] = None,
    live_events_path: Optional[Path] = None,
) -> Tuple[Any, Dict[str, Any]]:
    """Train a deterministic SB3 PPO/DQN model on the Stage-A env.

    REUSE: the PPO/DQN construction + bounded ``n_steps``/``batch_size`` clamping
    and the ``model.learn`` loop mirror ``sb3_smoke._train_model`` (:130).
    NET-NEW: determinism pins applied BEFORE model construction; ``device`` pinned.

    Story A: when ``live_events_path`` is given AND ``config.write_training_events``
    is on, a write-only ``RlLiveEventTrainingCallback`` streams per-rollout
    telemetry into ``live_events_path`` during ``model.learn``.  The callback is a
    pure side-effect (no env/RNG/gradient interaction), so determinism (V4) holds.
    Passing no path (the default, used by ``assert_reproducible``) emits nothing.
    """

    runtime = apply_determinism(config.seed, device=config.device)
    DQN, PPO, _ = _sb3_imports()
    env = _make_train_env(config, candidates=candidates)
    policy_kwargs = {"net_arch": [64, 32]}
    algorithm = config.algorithm.lower()
    try:
        if algorithm == "dqn":
            learning_starts = _bounded(
                config.dqn_learning_starts, lo=1, hi=max(1, config.total_timesteps // 4)
            )
            model = DQN(
                "MlpPolicy",
                env,
                seed=config.seed,
                device=config.device,
                verbose=0,
                learning_starts=learning_starts,
                buffer_size=max(int(config.dqn_buffer_size), int(config.total_timesteps), 64),
                batch_size=_bounded(config.dqn_batch_size, lo=2, hi=max(2, config.total_timesteps)),
                train_freq=4,
                gradient_steps=1,
                target_update_interval=64,
                exploration_fraction=0.4,
                exploration_final_eps=0.05,
                policy_kwargs=policy_kwargs,
            )
        elif algorithm == "ppo":
            n_steps = _bounded(config.ppo_n_steps, lo=8, hi=max(8, config.total_timesteps))
            model = PPO(
                "MlpPolicy",
                env,
                seed=config.seed,
                device=config.device,
                verbose=0,
                n_steps=n_steps,
                batch_size=_bounded(config.ppo_batch_size, lo=2, hi=n_steps),
                n_epochs=max(1, int(config.ppo_n_epochs)),
                policy_kwargs=policy_kwargs,
            )
        else:
            raise ValueError(f"Unknown algorithm: {config.algorithm!r}; expected 'ppo' or 'dqn'.")

        callback = None
        if config.write_training_events and live_events_path is not None:
            event_writer = RlLiveEventWriter(live_events_path, run_id=Path(live_events_path).parent.name)
            event_writer.reset()
            callback = _make_training_callback(algorithm, event_writer=event_writer)

        model.learn(
            total_timesteps=int(config.total_timesteps),
            progress_bar=False,
            callback=callback,
        )
        return model, runtime
    finally:
        env.close()


def _predict_action(model: Any, observation: np.ndarray) -> int:
    """REUSE: sb3_smoke ``model.predict(deterministic=True)`` (:354) pattern."""

    action, _ = model.predict(observation, deterministic=True)
    return int(np.asarray(action).item())


def _best_valid_action(predicted: int, mask: Sequence[int]) -> int:
    """Pick the model's action if valid, else the best valid fallback.

    NET-NEW (no sb3_smoke analog): the portfolio env masks invalid actions, so a
    plain (non-Maskable) PPO/DQN can emit a masked action.  Penalty-PPO learns to
    avoid them via ``invalid_action_penalty``, but at eval we still must NOT
    execute an invalid action.  Fallback order is deterministic: prefer the
    predicted action, else the lowest-index valid non-HOLD action, else HOLD.
    """

    if 0 <= predicted < len(mask) and mask[predicted]:
        return predicted
    for action in range(1, len(mask)):
        if mask[action]:
            return action
    return ACTION_HOLD


def make_trained_policy_fn(model: Any) -> Callable[[PortfolioEnv, Mapping[str, Any]], int]:
    """Wrap a trained SB3 model as a ``portfolio_walk_forward.PolicyFn``.

    The returned closure decodes the *current* env observation, runs the model
    deterministically, and maps the prediction onto the best *valid* action via
    the per-step ``action_mask`` from ``info``.  This is the obs-decode bridge the
    ``_fit_policy`` ``trained_ppo`` seam consumes (NET-NEW).
    """

    def _policy(env: PortfolioEnv, info: Mapping[str, Any]) -> int:
        observation = env._observation()  # noqa: SLF001 - read-only obs snapshot
        predicted = _predict_action(model, observation)
        mask = list(info["action_mask"])
        return _best_valid_action(predicted, mask)

    return _policy


def measure_invalid_action_rate(
    model: Any,
    config: PortfolioSb3TrainConfig,
    *,
    candidates: Optional[pd.DataFrame] = None,
    use_masked_policy: bool = False,
) -> Dict[str, Any]:
    """Run a bounded deterministic eval and measure the invalid-action rate.

    ``use_masked_policy=False`` measures the RAW model (no fallback) so the rate
    reflects how often the *unmasked* policy would have chosen an invalid action
    — the quantity the MaskablePPO trigger keys on.  ``use_masked_policy=True``
    confirms the masked obs-decode ``PolicyFn`` emits zero invalid actions.
    """

    env = make_portfolio_sb3_env(
        candidate_path=config.candidate_path,
        candidates=candidates,
        top_k_candidates=config.top_k_candidates,
        max_positions=config.max_positions,
        initial_cash=config.initial_cash,
        buy_fraction=config.buy_fraction,
        cost_bps=config.cost_bps,
        slippage_bps=config.slippage_bps,
        invalid_action_penalty=config.invalid_action_penalty,
        turnover_penalty_lambda=config.turnover_penalty_lambda,
        seed=config.seed,
    )
    raw_env = env.raw_env
    observation, info = env.reset(seed=config.seed)
    steps = 0
    invalid = 0
    try:
        terminated = False
        truncated = False
        while not (terminated or truncated):
            if steps >= int(config.max_eval_steps):
                break
            mask = list(info["action_mask"])
            predicted = _predict_action(model, observation)
            action = _best_valid_action(predicted, mask) if use_masked_policy else predicted
            if not (0 <= action < len(mask)) or not mask[action]:
                invalid += 1
            observation, _reward, terminated, truncated, info = env.step(int(action))
            steps += 1
    finally:
        env.close()
    rate = float(invalid) / float(steps) if steps else 0.0
    return {
        "steps": steps,
        "invalid_action_count": invalid,
        "invalid_action_rate": rate,
        "engine_invalid_action_count": int(raw_env.invalid_actions and len(raw_env.invalid_actions) or 0),
        "use_masked_policy": bool(use_masked_policy),
        "trigger_threshold": MASKABLE_PPO_INVALID_ACTION_TRIGGER,
        "maskable_ppo_trigger_fired": bool(rate > MASKABLE_PPO_INVALID_ACTION_TRIGGER),
    }


@dataclass(frozen=True)
class DailyPortfolioSb3TrainConfig:
    """Research-only fold-local daily PortfolioEnv SB3 training config."""

    prediction_run_dir: str
    run_id: str = "daily_portfolio_sb3"
    output_dir: str = str(DEFAULT_DAILY_PORTFOLIO_SB3_OUTPUT_DIR)
    algorithm: str = "ppo"
    total_timesteps: int = 5_000
    seed: int = 100
    device: str = "auto"
    n_folds: int = 2
    top_k_candidates: int = 3
    max_positions: int = 2
    initial_cash: float = 1_000_000.0
    buy_fraction: float = 0.25
    primary_cost_bps: float = 23.0
    control_cost_bps: Tuple[float, float] = (0.0, 46.0)
    slippage_bps: float = 0.0
    invalid_action_penalty: float = 0.001
    turnover_penalty_lambda: float = 1.0
    max_eval_steps: int = 512
    rank_score_column: str = "score_supervised_linear_ranker"
    ppo_n_steps: int = 256
    ppo_batch_size: int = 64
    ppo_n_epochs: int = 4
    dqn_learning_starts: int = 64
    dqn_buffer_size: int = 4_096
    dqn_batch_size: int = 64
    write_artifacts: bool = True


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_json(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json_sorted(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _daily_cost_label(cost_bps: float) -> str:
    value = float(cost_bps)
    if value == 23.0:
        return "base_23bp"
    if value == 0.0:
        return "control_0bp"
    if value == 46.0:
        return "control_46bp"
    return f"cost_{value:g}bp"


def _portfolio_train_config(
    daily_config: DailyPortfolioSb3TrainConfig,
    *,
    output_dir: Path,
    cost_bps: float,
    seed: int,
) -> PortfolioSb3TrainConfig:
    return PortfolioSb3TrainConfig(
        candidate_path=None,
        output_dir=str(output_dir),
        algorithm=daily_config.algorithm.lower(),
        total_timesteps=int(daily_config.total_timesteps),
        top_k_candidates=int(daily_config.top_k_candidates),
        max_positions=int(daily_config.max_positions),
        initial_cash=float(daily_config.initial_cash),
        buy_fraction=float(daily_config.buy_fraction),
        cost_bps=float(cost_bps),
        slippage_bps=float(daily_config.slippage_bps),
        invalid_action_penalty=float(daily_config.invalid_action_penalty),
        turnover_penalty_lambda=float(daily_config.turnover_penalty_lambda),
        seed=int(seed),
        device=str(daily_config.device),
        ppo_n_steps=int(daily_config.ppo_n_steps),
        ppo_batch_size=int(daily_config.ppo_batch_size),
        ppo_n_epochs=int(daily_config.ppo_n_epochs),
        dqn_learning_starts=int(daily_config.dqn_learning_starts),
        dqn_buffer_size=int(daily_config.dqn_buffer_size),
        dqn_batch_size=int(daily_config.dqn_batch_size),
        max_eval_steps=int(daily_config.max_eval_steps),
        write_artifacts=False,
        write_training_events=False,
    )


def _max_drawdown_pct(nav_values: Sequence[float]) -> float:
    peak = float("-inf")
    max_dd = 0.0
    for value in nav_values:
        nav = float(value)
        peak = max(peak, nav)
        if peak > 0:
            max_dd = min(max_dd, (nav / peak) - 1.0)
    return max_dd * 100.0


def _evaluate_model_on_candidates(
    model: Any,
    train_config: PortfolioSb3TrainConfig,
    candidates: pd.DataFrame,
    *,
    fold_index: int,
    cost_label: str,
) -> Dict[str, Any]:
    env = make_portfolio_sb3_env(
        candidate_path=None,
        candidates=candidates,
        top_k_candidates=train_config.top_k_candidates,
        max_positions=train_config.max_positions,
        initial_cash=train_config.initial_cash,
        buy_fraction=train_config.buy_fraction,
        cost_bps=train_config.cost_bps,
        slippage_bps=train_config.slippage_bps,
        invalid_action_penalty=train_config.invalid_action_penalty,
        turnover_penalty_lambda=0.0,
        seed=train_config.seed + fold_index,
    )
    observation, info = env.reset(seed=train_config.seed + fold_index)
    terminated = False
    truncated = False
    steps = 0
    raw_invalid = 0
    rewards: List[float] = []
    try:
        while not (terminated or truncated):
            if train_config.max_eval_steps and steps >= int(train_config.max_eval_steps):
                break
            mask = list(info["action_mask"])
            predicted = _predict_action(model, observation)
            if not (0 <= predicted < len(mask)) or not mask[predicted]:
                raw_invalid += 1
            action = _best_valid_action(predicted, mask)
            observation, reward, terminated, truncated, info = env.step(action)
            rewards.append(float(reward))
            steps += 1
        nav_curve = [float(row["nav"]) for row in env.raw_env.nav_log] or [float(train_config.initial_cash)]
        turnover = float(sum(float(fill.get("gross_value", 0.0)) for fill in env.raw_env.trade_log))
        total_cost = float(sum(float(fill.get("cost", 0.0)) for fill in env.raw_env.trade_log))
        final_nav = float(info["nav"])
        return {
            "fold_index": int(fold_index),
            "cost_label": cost_label,
            "cost_bps": float(train_config.cost_bps),
            "steps": int(steps),
            "final_nav": final_nav,
            "return_pct": (final_nav / float(train_config.initial_cash) - 1.0) * 100.0,
            "max_drawdown_pct": _max_drawdown_pct(nav_curve),
            "turnover": turnover,
            "trade_count": int(info["trade_count"]),
            "total_cost": total_cost,
            "total_reward": float(sum(rewards)),
            "raw_invalid_action_count": int(raw_invalid),
            "raw_invalid_action_rate": float(raw_invalid) / float(steps) if steps else 0.0,
            "executed_invalid_action_count": int(info["invalid_action_count"]),
        }
    finally:
        env.close()


def _no_trade_metrics(
    train_config: PortfolioSb3TrainConfig,
    *,
    fold_index: int,
    cost_label: str,
) -> Dict[str, Any]:
    return {
        "fold_index": int(fold_index),
        "cost_label": cost_label,
        "cost_bps": float(train_config.cost_bps),
        "policy": "no_trade_cash",
        "final_nav": float(train_config.initial_cash),
        "return_pct": 0.0,
        "trade_count": 0,
        "total_cost": 0.0,
    }


def _fold_range(frame: pd.DataFrame) -> Tuple[str, str]:
    timestamps = pd.to_datetime(frame["timestamp"], errors="coerce").dropna()
    if timestamps.empty:
        return "", ""
    return timestamps.min().isoformat(), timestamps.max().isoformat()


def _daily_source_hashes() -> Dict[str, str]:
    source_paths = [
        Path(__file__),
        Path(__file__).with_name("portfolio_sb3_adapter.py"),
        Path(__file__).with_name("portfolio_walk_forward.py"),
        Path(__file__).with_name("daily_portfolio_sb3_dataset.py"),
        Path(__file__).with_name("portfolio_env.py"),
        Path(__file__).with_name("accounting.py"),
        Path(__file__).with_name("symbol_norm.py"),
        Path(__file__).with_name("trading_env.py"),
    ]
    return {path.name: _sha256_file(path) for path in source_paths if path.is_file()}
def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _daily_preregistration_lineage(dataset_manifest: Mapping[str, Any]) -> Dict[str, Any]:
    path = dataset_manifest.get("preregistration_path")
    sha256 = dataset_manifest.get("preregistration_sha256")
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Daily Portfolio SB3 dataset manifest missing verified preregistration_path")
    if not isinstance(sha256, str) or len(sha256.strip()) != 64:
        raise ValueError("Daily Portfolio SB3 dataset manifest missing verified preregistration_sha256")
    source_hashes = dataset_manifest.get("source_artifact_hashes")
    if not isinstance(source_hashes, Mapping) or source_hashes.get("preregistration") != sha256:
        raise ValueError("Daily Portfolio SB3 preregistration hash is not bound to source_artifact_hashes")
    return {
        "path": path.strip(),
        "sha256": sha256.strip(),
        "source": "verified_daily_portfolio_sb3_dataset_manifest",
    }


def _daily_metric_event_info(
    *,
    fold_index: Optional[int],
    cost_label: str,
    config: DailyPortfolioSb3TrainConfig,
    training_device_used: str,
    eval_device: str,
    dataset_manifest: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "fold": fold_index,
        "cost_scenario": cost_label,
        "reward_kind": "raw_reward",
        "reward_unit": "score",
        "equity_kind": "krw_nav",
        "equity_unit": "krw",
        "action_recorded": False,
        "device": {
            "requested": str(config.device),
            "used": training_device_used,
            "eval": eval_device,
        },
        "source_lineage": {
            "source_prediction_run_id": dataset_manifest.get("source_prediction_run_id"),
            "source_prediction_manifest_sha256": dataset_manifest.get("source_prediction_manifest_sha256"),
            "d2_dataset_manifest_sha256": dataset_manifest.get("d2_dataset_manifest_sha256"),
            "d2_daily_db_sha256": dataset_manifest.get("d2_daily_db_sha256"),
        },
    }


def _write_daily_sb3_live_event(
    writer: RlLiveEventWriter,
    *,
    run_id: str,
    algorithm: str,
    phase: str,
    global_step: int,
    reward: Optional[float],
    equity: Optional[float],
    info: Mapping[str, Any],
) -> None:
    writer.write_step(
        algorithm=f"portfolio_{algorithm}",
        phase=phase,
        global_step=global_step,
        action=None,
        reward=reward,
        equity=equity,
        source="daily_portfolio_sb3",
        info=dict(info),
    )


def _daily_source_hash_manifest(
    *,
    source_hashes: Mapping[str, str],
    config_hash: str,
    dataset_artifacts: Mapping[str, Any],
    dataset_manifest: Mapping[str, Any],
    fold_summaries: Sequence[Mapping[str, Any]],
    preregistration: Mapping[str, Any],
) -> Dict[str, Any]:
    model_hashes = {
        f"fold_{int(fold['fold_index']):02d}": fold.get("model_sha256")
        for fold in fold_summaries
    }
    return {
        "schema_version": "daily_portfolio_sb3_source_hashes.v1",
        "generated_at": _utc_now(),
        "source_hashes": dict(source_hashes),
        "config_sha256": config_hash,
        "model_hashes": model_hashes,
        "adapter_artifact_hashes": dict(dataset_artifacts.get("output_hashes", {})),
        "lineage_hashes": {
            "prereg_sha256": preregistration.get("sha256"),
            "d3_prediction_manifest_sha256": dataset_manifest.get("source_prediction_manifest_sha256"),
            "d3_artifacts": dict(dataset_manifest.get("source_artifact_hashes", {})),
            "d2_dataset_manifest_sha256": dataset_manifest.get("d2_dataset_manifest_sha256"),
            "d2_daily_db_sha256": dataset_manifest.get("d2_daily_db_sha256"),
        },
    }


def _daily_training_manifest(
    *,
    config: DailyPortfolioSb3TrainConfig,
    summary: Mapping[str, Any],
    preregistration: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "schema_version": "daily_portfolio_sb3_training_manifest.v1",
        "generated_at": _utc_now(),
        "stage": "G016_SLICE3_DAILY_PORTFOLIO_SB3_RESEARCH",
        "status": "COMPLETED_RESEARCH_ONLY",
        "authority": "D3_D2_DB_LINEAGE_APPROVED_RESEARCH_ONLY",
        "run_id": config.run_id,
        "algorithm": summary.get("algorithm"),
        "seed": summary.get("seed"),
        "device_requested": summary.get("device_requested"),
        "device_used": summary.get("device_used"),
        "device_used_by_fold": summary.get("device_used_by_fold", []),
        "primary_cost_label": summary.get("primary_cost_label"),
        "primary_cost_bps": summary.get("primary_cost_bps"),
        "control_cost_bps": summary.get("control_cost_bps"),
        "controls_retrained": False,
        "oos_rows_used_for_fit": 0,
        "folds": summary.get("folds", []),
        "preregistration": dict(preregistration),
        "dataset": dict(summary.get("dataset", {})),
        "source_hashes": dict(summary.get("source_hashes", {})),
        "config_sha256": summary.get("config_sha256"),
        "false_locks": dict(summary.get("false_locks", {})),
    }


def _daily_rl_manifest(
    *,
    config: DailyPortfolioSb3TrainConfig,
    summary: Mapping[str, Any],
    source_hash_manifest: Mapping[str, Any],
    live_summary: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "schema_version": "daily_portfolio_sb3_rl_manifest.v1",
        "generated_at": _utc_now(),
        "artifact_type": "sb3_smoke",
        "mode": summary.get("mode"),
        "stage": "G016_SLICE3_DAILY_PORTFOLIO_SB3_RESEARCH",
        "status": "COMPLETED_RESEARCH_ONLY",
        "authority": "D3_D2_DB_LINEAGE_APPROVED_RESEARCH_ONLY",
        "run_id": config.run_id,
        "algorithm": summary.get("algorithm"),
        "seed": summary.get("seed"),
        "primary_cost_label": summary.get("primary_cost_label"),
        "primary_cost_bps": summary.get("primary_cost_bps"),
        "control_cost_bps": summary.get("control_cost_bps"),
        "controls": {"control_0bp": 0.0, "control_46bp": 46.0},
        "oos_rows_used_for_fit": 0,
        "fold_count": summary.get("fold_count"),
        "model_hashes": dict(source_hash_manifest.get("model_hashes", {})),
        "lineage_hashes": dict(source_hash_manifest.get("lineage_hashes", {})),
        "live_events": dict(live_summary),
        "false_locks": dict(summary.get("false_locks", {})),
    }


def _daily_sb3_smoke_signature(
    *,
    summary: Mapping[str, Any],
    live_summary: Mapping[str, Any],
) -> Dict[str, Any]:
    folds = list(summary.get("folds", []))
    models = []
    best_model = None
    best_return = float("-inf")
    for fold in folds:
        metrics = fold.get("validation_primary_metrics", {})
        model_name = f"fold_{int(fold['fold_index']):02d}_{summary.get('algorithm')}"
        return_pct = float(metrics.get("return_pct", 0.0) or 0.0)
        if best_model is None or return_pct > best_return:
            best_model = model_name
            best_return = return_pct
        models.append(
            {
                "algorithm": summary.get("algorithm"),
                "model": model_name,
                "policy": f"stable_baselines3_{summary.get('algorithm')}",
                "model_path": fold.get("model_path"),
                "model_sha256": fold.get("model_sha256"),
                "training_timesteps": summary.get("total_timesteps"),
                "avg_episode_net_return_pct": return_pct,
                "trade_count": metrics.get("trade_count"),
                "cost_bps": metrics.get("cost_bps"),
                "slippage_bps": summary.get("slippage_bps"),
                "passes_cost_gate": False,
                "is_smoke": False,
                "research_only": True,
            }
        )
    return {
        "mode": "stom_rl_sb3_smoke",
        "schema_version": "daily_portfolio_sb3_as_sb3_smoke.v1",
        "summary": {
            "algorithm_count": 1,
            "best_model": best_model,
            "best_algorithm_by_avg_episode_net": summary.get("algorithm"),
            "feature_columns": summary.get("feature_columns", []),
            "live_event_count": live_summary.get("event_count"),
            "live_event_phases": live_summary.get("phases"),
            "primary_cost_label": summary.get("primary_cost_label"),
            "primary_cost_bps": summary.get("primary_cost_bps"),
            "oos_rows_used_for_fit": 0,
            "research_only": True,
            "model_build_allowed": False,
            "paper_forward_allowed": False,
            "live_broker_order_allowed": False,
            "profit_claim_allowed": False,
        },
        "models": models,
        "live_events": dict(live_summary),
    }


def run_daily_portfolio_sb3(config: DailyPortfolioSb3TrainConfig) -> Dict[str, Any]:
    """Train fold-local PPO/DQN models from approved D3/D2 daily candidates only."""

    algorithm = config.algorithm.lower()
    if algorithm not in {"ppo", "dqn"}:
        raise ValueError("DailyPortfolioSb3TrainConfig.algorithm must be 'ppo' or 'dqn'.")
    dataset = build_daily_portfolio_sb3_dataset(
        DailyPortfolioSb3DatasetConfig(
            prediction_run_dir=config.prediction_run_dir,
            rank_score_column=config.rank_score_column,
            expected_cost_bps=float(config.primary_cost_bps),
        )
    )
    output_root = Path(config.output_dir)
    dataset_artifacts = write_daily_portfolio_sb3_dataset(dataset, output_dir=output_root, run_id=config.run_id)
    run_dir = Path(dataset_artifacts["artifact_dir"])
    candidates = dataset.candidates.copy()
    if candidates.empty:
        raise ValueError("Daily Portfolio SB3 candidates are empty.")
    candidates["timestamp"] = pd.to_datetime(candidates["timestamp"], errors="coerce")
    if candidates["timestamp"].isna().any():
        raise ValueError("Daily Portfolio SB3 candidate timestamps must be parseable.")

    split_counts = {str(split): int(count) for split, count in candidates["split"].astype(str).value_counts().sort_index().items()}
    official_oos_frame = candidates[candidates["split"].astype(str) == "test"].copy()
    train_validation_candidates = candidates[candidates["split"].astype(str).isin({"train", "val"})].copy()
    if official_oos_frame.empty:
        raise ValueError("Daily Portfolio SB3 candidates contain no official split==test OOS rows.")
    if train_validation_candidates.empty:
        raise ValueError("Daily Portfolio SB3 train/validation candidates are empty.")

    from .portfolio_walk_forward import build_expanding_window_folds

    folds = build_expanding_window_folds(train_validation_candidates, config.n_folds)
    fold_summaries: List[Dict[str, Any]] = []
    source_hashes = _daily_source_hashes()
    config_hash = _sha256_json(asdict(config))
    live_events_path = run_dir / "rl_live_events.jsonl"
    live_writer = RlLiveEventWriter(live_events_path, run_id=config.run_id, enabled=bool(config.write_artifacts))
    live_writer.reset()
    live_step = 0
    preregistration = _daily_preregistration_lineage(dataset.manifest)

    for fold in folds:
        if fold.train_frame.empty:
            raise ValueError(f"Fold {fold.fold_index} has no train rows.")
        if fold.test_frame.empty:
            raise ValueError(f"Fold {fold.fold_index} has no test rows.")
        if "split" in fold.train_frame.columns and (fold.train_frame["split"].astype(str) == "test").any():
            raise AssertionError(f"Fold {fold.fold_index}: official test rows entered training")
        if "split" in fold.test_frame.columns and (fold.test_frame["split"].astype(str) == "test").any():
            raise AssertionError(f"Fold {fold.fold_index}: official test rows entered validation fold construction")
        train_ts = set(pd.Timestamp(ts) for ts in fold.train_frame["timestamp"].unique())
        validation_ts = set(pd.Timestamp(ts) for ts in fold.test_frame["timestamp"].unique())
        if train_ts & validation_ts:
            raise AssertionError(f"Fold {fold.fold_index}: train/validation timestamps overlap")
        if min(validation_ts) <= max(train_ts):
            raise AssertionError(f"Fold {fold.fold_index}: validation timestamps are not strictly after train")

        fold_dir = run_dir / "models" / f"fold_{fold.fold_index:02d}"
        model_path = fold_dir / f"portfolio_{algorithm}_model.zip"
        train_config = _portfolio_train_config(
            config,
            output_dir=fold_dir,
            cost_bps=float(config.primary_cost_bps),
            seed=int(config.seed) + int(fold.fold_index),
        )
        model, runtime = train_portfolio_model(train_config, candidates=fold.train_frame)
        training_device_used = str(getattr(model, "device", config.device))
        fold_dir.mkdir(parents=True, exist_ok=True)
        model.save(str(model_path))
        model_hash = _sha256_file(model_path)
        eval_model = load_trained_model(str(model_path), algorithm=algorithm)
        eval_device = str(getattr(eval_model, "device", "cpu"))

        primary_label = _daily_cost_label(float(config.primary_cost_bps))
        primary_metrics = _evaluate_model_on_candidates(
            eval_model,
            train_config,
            fold.test_frame,
            fold_index=fold.fold_index,
            cost_label=primary_label,
        )
        oos_primary_metrics = _evaluate_model_on_candidates(
            eval_model,
            train_config,
            official_oos_frame,
            fold_index=fold.fold_index,
            cost_label=primary_label,
        )
        raw_invalid = float(primary_metrics["raw_invalid_action_rate"])
        control_metrics: List[Dict[str, Any]] = []
        oos_control_metrics: List[Dict[str, Any]] = []
        for control_cost in [float(value) for value in config.control_cost_bps]:
            control_config = _portfolio_train_config(
                config,
                output_dir=fold_dir,
                cost_bps=control_cost,
                seed=int(config.seed) + int(fold.fold_index),
            )
            control_metrics.append(
                _evaluate_model_on_candidates(
                    eval_model,
                    control_config,
                    fold.test_frame,
                    fold_index=fold.fold_index,
                    cost_label=_daily_cost_label(control_cost),
                )
            )
            oos_control_metrics.append(
                _evaluate_model_on_candidates(
                    eval_model,
                    control_config,
                    official_oos_frame,
                    fold_index=fold.fold_index,
                    cost_label=_daily_cost_label(control_cost),
                )
            )

        train_start, train_end = _fold_range(fold.train_frame)
        test_start, test_end = _fold_range(fold.test_frame)
        fold_manifest = {
            "schema_version": "daily_portfolio_sb3_train_fold.v1",
            "mode": "research_only_fold_local_daily_portfolio_sb3",
            "stage": "G016_SLICE3_DAILY_PORTFOLIO_SB3_RESEARCH",
            "status": "COMPLETED_RESEARCH_ONLY",
            "authority": "D3_D2_DB_LINEAGE_APPROVED_RESEARCH_ONLY",
            "algorithm": algorithm,
            "seed": int(train_config.seed),
            "device_requested": str(config.device),
            "device_used": training_device_used,
            "training_device_used": training_device_used,
            "eval_device": eval_device,
            "fold_index": int(fold.fold_index),
            "train_range": {"start": train_start, "end": train_end, "row_count": int(len(fold.train_frame))},
            "validation_range": {"start": test_start, "end": test_end, "row_count": int(len(fold.test_frame))},
            "test_range": {"start": test_start, "end": test_end, "row_count": int(len(fold.test_frame))},
            "official_split_row_counts": split_counts,
            "oos_rows_used_for_fit": 0,
            "official_test_oos_range": {
                "start": _fold_range(official_oos_frame)[0],
                "end": _fold_range(official_oos_frame)[1],
                "row_count": int(len(official_oos_frame)),
            },
            "train_test_boundary": "PASS_official_test_excluded_from_fold_construction_and_learning",
            "model_path": str(model_path),
            "model_sha256": model_hash,
            "runtime": runtime,
            "source_hashes": source_hashes,
            "config_sha256": config_hash,
            "dataset_hashes": dataset_artifacts.get("output_hashes", {}),
            "source_artifact_hashes": dict(dataset.manifest.get("source_artifact_hashes", {})),
            "cost_labels": {
                primary_label: float(config.primary_cost_bps),
                **{_daily_cost_label(float(value)): float(value) for value in config.control_cost_bps},
            },
            "headline": primary_label,
            "baseline_metrics": {
                primary_label: _no_trade_metrics(train_config, fold_index=fold.fold_index, cost_label=primary_label),
            },
            "primary_metrics": primary_metrics,
            "validation_primary_metrics": primary_metrics,
            "untouched_test_oos_primary_metrics": oos_primary_metrics,
            "control_metrics": control_metrics,
            "untouched_test_oos_control_metrics": oos_control_metrics,
            "controls_retrained": False,
            "invalid_action_rate": raw_invalid,
            "maskable_ppo_trigger": {
                "threshold": MASKABLE_PPO_INVALID_ACTION_TRIGGER,
                "raw_rate": raw_invalid,
                "fired_on_rate": bool(raw_invalid > MASKABLE_PPO_INVALID_ACTION_TRIGGER),
                "recommendation_only": True,
                "recommendation": (
                    "record MaskablePPO recommendation only; do not auto-install sb3-contrib"
                    if raw_invalid > MASKABLE_PPO_INVALID_ACTION_TRIGGER
                    else "no MaskablePPO recommendation"
                ),
            },
            "false_locks": {
                "model_build_allowed": False,
                "paper_forward_allowed": False,
                "live_broker_order_allowed": False,
                "profit_claim_allowed": False,
            },
        }
        _write_json_sorted(fold_dir / "daily_portfolio_sb3_fold_manifest.json", fold_manifest)
        fold_summaries.append(fold_manifest)
        live_step += 1
        _write_daily_sb3_live_event(
            live_writer,
            run_id=config.run_id,
            algorithm=algorithm,
            phase="fold_completed",
            global_step=live_step,
            reward=float(primary_metrics.get("total_reward", 0.0) or 0.0),
            equity=float(primary_metrics.get("final_nav", train_config.initial_cash) or train_config.initial_cash),
            info=_daily_metric_event_info(
                fold_index=int(fold.fold_index),
                cost_label=primary_label,
                config=config,
                training_device_used=training_device_used,
                eval_device=eval_device,
                dataset_manifest=dataset.manifest,
            ),
        )

    summary = {
        "schema_version": "daily_portfolio_sb3_train.v1",
        "mode": "research_only_daily_portfolio_sb3_fold_local_train",
        "stage": "G016_SLICE3_DAILY_PORTFOLIO_SB3_RESEARCH",
        "status": "COMPLETED_RESEARCH_ONLY",
        "authority": "D3_D2_DB_LINEAGE_APPROVED_RESEARCH_ONLY",
        "run_id": config.run_id,
        "algorithm": algorithm,
        "seed": int(config.seed),
        "device_requested": str(config.device),
        "device_used": fold_summaries[0]["training_device_used"] if fold_summaries else str(config.device),
        "device_used_by_fold": [
            {
                "fold_index": int(fold["fold_index"]),
                "training_device_used": fold["training_device_used"],
                "eval_device": fold["eval_device"],
            }
            for fold in fold_summaries
        ],
        "primary_cost_label": "base_23bp",
        "primary_cost_bps": float(config.primary_cost_bps),
        "control_cost_bps": [float(value) for value in config.control_cost_bps],
        "total_timesteps": int(config.total_timesteps),
        "slippage_bps": float(config.slippage_bps),
        "feature_columns": sorted(col for col in candidates.columns if col.startswith("feature_")),
        "preregistration": preregistration,
        "dataset": {
            "manifest": dataset_artifacts.get("daily_portfolio_sb3_dataset_manifest_path"),
            "candidates": dataset_artifacts.get("daily_portfolio_sb3_candidates_path"),
            "hashes": dataset_artifacts.get("output_hashes", {}),
            "source_prediction_run_id": dataset.manifest.get("source_prediction_run_id"),
            "d2_daily_db_sha256": dataset.manifest.get("d2_daily_db_sha256"),
            "d2_dataset_manifest_sha256": dataset.manifest.get("d2_dataset_manifest_sha256"),
            "source_prediction_manifest_sha256": dataset.manifest.get("source_prediction_manifest_sha256"),
            "source_artifact_hashes": dict(dataset.manifest.get("source_artifact_hashes", {})),
        },
        "source_hashes": source_hashes,
        "config_sha256": config_hash,
        "fold_count": len(fold_summaries),
        "official_split_row_counts": split_counts,
        "oos_rows_used_for_fit": 0,
        "folds": fold_summaries,
        "artifacts": {
            "output_dir": str(run_dir),
            "summary_json": str(run_dir / "daily_portfolio_sb3_train_summary.json"),
            "models_dir": str(run_dir / "models"),
            "rl_manifest": str(run_dir / "rl_manifest.json"),
            "training_manifest": str(run_dir / "training_manifest.json"),
            "source_hashes_json": str(run_dir / "source_hashes.json"),
            "live_events": str(run_dir / "rl_live_events.jsonl"),
            "live_summary": str(run_dir / "rl_live_summary.json"),
            "sb3_smoke_summary": str(run_dir / "sb3_smoke_summary.json"),
        },
        "false_locks": {
            "model_build_allowed": False,
            "paper_forward_allowed": False,
            "live_broker_order_allowed": False,
            "profit_claim_allowed": False,
        },
    }
    if fold_summaries:
        live_step += 1
        last_fold = fold_summaries[-1]
        last_metrics = last_fold.get("validation_primary_metrics", {})
        _write_daily_sb3_live_event(
            live_writer,
            run_id=config.run_id,
            algorithm=algorithm,
            phase="completed",
            global_step=live_step,
            reward=float(last_metrics.get("total_reward", 0.0) or 0.0),
            equity=float(last_metrics.get("final_nav", config.initial_cash) or config.initial_cash),
            info=_daily_metric_event_info(
                fold_index=None,
                cost_label=str(summary["primary_cost_label"]),
                config=config,
                training_device_used=str(summary["device_used"]),
                eval_device=str(summary["device_used_by_fold"][-1]["eval_device"]),
                dataset_manifest=dataset.manifest,
            ),
        )

    live_summary = summarize_live_event_file(live_events_path)
    source_hash_manifest = _daily_source_hash_manifest(
        source_hashes=source_hashes,
        config_hash=config_hash,
        dataset_artifacts=dataset_artifacts,
        dataset_manifest=dataset.manifest,
        fold_summaries=fold_summaries,
        preregistration=preregistration,
    )
    training_manifest = _daily_training_manifest(
        config=config,
        summary=summary,
        preregistration=preregistration,
    )
    rl_manifest = _daily_rl_manifest(
        config=config,
        summary=summary,
        source_hash_manifest=source_hash_manifest,
        live_summary=live_summary,
    )
    sb3_signature = _daily_sb3_smoke_signature(summary=summary, live_summary=live_summary)
    summary["live_events"] = live_summary
    summary["source_hash_manifest"] = source_hash_manifest
    if config.write_artifacts:
        _write_json_sorted(run_dir / "daily_portfolio_sb3_train_summary.json", summary)
        _write_json_sorted(run_dir / "source_hashes.json", source_hash_manifest)
        _write_json_sorted(run_dir / "training_manifest.json", training_manifest)
        _write_json_sorted(run_dir / "rl_manifest.json", rl_manifest)
        _write_json_sorted(run_dir / "rl_live_summary.json", live_summary)
        _write_json_sorted(run_dir / "sb3_smoke_summary.json", sb3_signature)
    return summary

def train_and_save(config: PortfolioSb3TrainConfig) -> Dict[str, Any]:
    """Train, save the model, measure invalid-action rate; return a summary.

    Story A: when ``write_artifacts`` AND ``write_training_events`` are on, the
    train run dir gains an ``rl_live_events.jsonl`` (the per-rollout telemetry
    stream), an ``rl_live_summary.json`` rollup, and an ``sb3_smoke_summary.json``
    signature so the existing dashboard recognises the directory as a run and
    serves the live events through ``/table/events`` (follow/replay).
    """

    check_result = check_train_env(config)

    output_dir = Path(config.output_dir)
    emit_events = bool(config.write_artifacts and config.write_training_events)
    live_events_path = output_dir / "rl_live_events.jsonl"
    if emit_events:
        output_dir.mkdir(parents=True, exist_ok=True)

    model, runtime = train_portfolio_model(
        config, live_events_path=live_events_path if emit_events else None
    )
    raw_rate = measure_invalid_action_rate(model, config, use_masked_policy=False)
    masked_rate = measure_invalid_action_rate(model, config, use_masked_policy=True)

    model_path: Optional[str] = None
    if config.write_artifacts:
        output_dir.mkdir(parents=True, exist_ok=True)
        model_path = str(output_dir / f"portfolio_{config.algorithm}_model.zip")
        model.save(model_path)

    live_summary: Optional[Dict[str, Any]] = None
    if emit_events and live_events_path.is_file():
        live_summary = summarize_live_event_file(live_events_path)

    summary: Dict[str, Any] = {
        "mode": "stom_rl_portfolio_sb3_train",
        "config": asdict(config),
        "runtime": runtime,
        "check_env": check_result,
        "raw_invalid_action": raw_rate,
        "masked_invalid_action": masked_rate,
        "maskable_ppo_trigger": {
            "threshold": MASKABLE_PPO_INVALID_ACTION_TRIGGER,
            "raw_rate": raw_rate["invalid_action_rate"],
            "fired_on_rate": bool(raw_rate["maskable_ppo_trigger_fired"]),
            "recommendation": (
                "ESCALATE: record sb3-contrib MaskablePPO recommendation "
                "(NOT installed in Stage B)"
                if raw_rate["maskable_ppo_trigger_fired"]
                else "no escalation: penalty-PPO invalid-action rate within budget"
            ),
        },
        "model_path": model_path,
    }
    if live_summary is not None:
        summary["live_events"] = live_summary
    if config.write_artifacts:
        (output_dir / "portfolio_sb3_train_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8-sig"
        )
    if live_summary is not None:
        _write_train_run_signature(output_dir, config=config, live_summary=live_summary)
        (output_dir / "rl_live_summary.json").write_text(
            json.dumps(live_summary, ensure_ascii=False, indent=2), encoding="utf-8-sig"
        )
    return summary


def _write_train_run_signature(
    output_dir: Path,
    *,
    config: PortfolioSb3TrainConfig,
    live_summary: Mapping[str, Any],
) -> None:
    """Write the dashboard signature so the train run is follow/replay-visible.

    The dashboard's ``_detect_artifact_type`` recognises a run by a signature
    file; ``sb3_smoke_summary.json`` is one of them and its ``live_events`` block
    is read by ``load_rl_run``.  Writing it here makes the SB3 *training* stream
    appear in the same realtime view the deterministic smoke run uses — without a
    separate publish step or any new ``/api/*`` route.
    """

    live_algorithm = PORTFOLIO_TRAIN_LIVE_ALGORITHM.get(
        config.algorithm.lower(), f"portfolio_{config.algorithm.lower()}"
    )
    signature = {
        "mode": "stom_rl_portfolio_sb3_train",
        "run_name": output_dir.name,
        "config": asdict(config),
        "summary": {
            "algorithm": config.algorithm,
            "best_model": live_algorithm,
            "total_timesteps": int(config.total_timesteps),
            "live_event_count": int(live_summary.get("event_count", 0)),
            "feature_columns": [],
        },
        "models": [
            {
                "model": live_algorithm,
                "algorithm": config.algorithm,
                "total_timesteps": int(config.total_timesteps),
            }
        ],
        "live_events": dict(live_summary),
    }
    (output_dir / SB3_SMOKE_SIGNATURE_FILE).write_text(
        json.dumps(signature, ensure_ascii=False, indent=2), encoding="utf-8-sig"
    )


def load_trained_model(model_path: str, *, algorithm: str = "ppo") -> Any:
    """Load a saved SB3 model from ``model_path`` (PPO or DQN)."""

    DQN, PPO, _ = _sb3_imports()
    cls = DQN if algorithm.lower() == "dqn" else PPO
    return cls.load(model_path, device="cpu")


def trained_eval_metrics(model: Any, candidate_path: Optional[str], *, n_folds: int = 2) -> List[Dict[str, Any]]:
    """Run the trained policy through the walk-forward holdout and return folds.

    Helper used by the determinism reproducibility assertion: two trains with the
    same seed must agree within ``atol=1e-6, rtol=1e-5`` on per-fold metrics.
    """

    from . import portfolio_walk_forward as pwf

    factory_key = "__determinism_probe__"
    pwf.register_trained_policy_factory(factory_key, lambda **_: make_trained_policy_fn(model))
    try:
        cfg = pwf.PortfolioWalkForwardConfig(
            candidate_path=candidate_path,
            n_folds=n_folds,
            baselines=(factory_key,),
            write_artifacts=False,
        )
        payload = pwf.run_portfolio_walk_forward(cfg)
        return [
            {
                "fold_index": row["fold_index"],
                "return_pct": float(row["return_pct"]),
                "max_drawdown_pct": float(row["max_drawdown_pct"]),
                "turnover": float(row["turnover"]),
            }
            for row in payload["folds"]
        ]
    finally:
        pwf.unregister_trained_policy_factory(factory_key)


def assert_reproducible(
    config: PortfolioSb3TrainConfig,
    *,
    atol: float = 1e-6,
    rtol: float = 1e-5,
) -> Dict[str, Any]:
    """Train twice with the same seed/data and assert eval metrics agree.

    Determinism gate (V4): without the pins in :func:`apply_determinism` this is
    untestable, so the pins are applied at every train.  Compares per-fold
    ``return_pct``/``max_drawdown_pct``/``turnover`` within the explicit tolerance.
    """

    model_a, _ = train_portfolio_model(config)
    folds_a = trained_eval_metrics(model_a, config.candidate_path, n_folds=2)
    model_b, _ = train_portfolio_model(config)
    folds_b = trained_eval_metrics(model_b, config.candidate_path, n_folds=2)

    assert len(folds_a) == len(folds_b), "fold count diverged across reruns"
    for fa, fb in zip(folds_a, folds_b):
        for key in ("return_pct", "max_drawdown_pct", "turnover"):
            np.testing.assert_allclose(
                fa[key], fb[key], atol=atol, rtol=rtol,
                err_msg=f"determinism: fold {fa['fold_index']} {key} diverged",
            )
    return {"reproducible": True, "atol": atol, "rtol": rtol, "folds_compared": len(folds_a)}


def run_stage_b_smoke(config: PortfolioSb3TrainConfig, *, n_folds: int = 2) -> Dict[str, Any]:
    """Bounded Stage-B smoke: pre-register, train, then advisory holdout compare.

    Honesty contract: on the 3-symbol universe ``n_folds`` can only be 2, so per
    the plan's P0-1 power floor this is ADVISORY-ONLY — NO alpha may be claimed.
    The summary records the pre-registered primary config and ``M`` (configs
    tried) BEFORE the holdout comparison, and labels the whole result advisory.
    """

    from . import portfolio_walk_forward as pwf

    # --- Pre-registration (P0-1): written BEFORE any test-fold metric. ---
    pre_registration = {
        "primary_config": {
            "algorithm": config.algorithm,
            "turnover_penalty_lambda": config.turnover_penalty_lambda,
            "top_k_candidates": config.top_k_candidates,
            "seed_set": [config.seed],
            "cost_bps": config.cost_bps,
        },
        "candidate_config_set": [
            {"algorithm": config.algorithm, "lambda": config.turnover_penalty_lambda,
             "top_k": config.top_k_candidates, "seed": config.seed},
        ],
        "M_configs_tried": 1,
        "n_folds": n_folds,
        "advisory_only": True,
        "advisory_reason": (
            f"n_folds={n_folds} < 5 power floor (P0-1); 3-symbol universe. "
            "NO alpha claim. Real alpha verdict deferred to Stage E (n_folds>=5)."
        ),
    }

    train_summary = train_and_save(config)
    model = load_trained_model(train_summary["model_path"], algorithm=config.algorithm) \
        if train_summary["model_path"] else train_portfolio_model(config)[0]

    pwf.register_trained_policy_factory(
        "trained_ppo", lambda **_: make_trained_policy_fn(model)
    )
    try:
        wf_cfg = pwf.PortfolioWalkForwardConfig(
            candidate_path=config.candidate_path,
            output_dir=str(Path(config.output_dir) / "walk_forward"),
            n_folds=n_folds,
            baselines=("no_trade", "equal_weight_candidate", "supervised_ranker", "trained_ppo"),
            top_k_candidates=config.top_k_candidates,
            max_positions=config.max_positions,
            cost_bps=config.cost_bps,
            slippage_bps=config.slippage_bps,
            write_artifacts=config.write_artifacts,
        )
        wf_payload = pwf.run_portfolio_walk_forward(wf_cfg)
    finally:
        pwf.unregister_trained_policy_factory("trained_ppo")

    # Advisory comparison: trained_ppo vs no_trade / equal_weight / supervised_ranker.
    by_policy: Dict[str, List[float]] = {}
    for row in wf_payload["folds"]:
        by_policy.setdefault(row["policy"], []).append(float(row["return_pct"]))
    mean_ret = {p: (sum(v) / len(v) if v else 0.0) for p, v in by_policy.items()}
    trained = mean_ret.get("trained_ppo", 0.0)
    ranker = mean_ret.get("supervised_ranker", 0.0)
    advisory = {
        "mean_return_pct_by_policy": mean_ret,
        "cost_bps": config.cost_bps,
        "rl_vs_ranker": "RL_<=_ranker" if trained <= ranker else "RL_>_ranker",
        "ranker_floor_verdict": (
            "RECOMMEND ABANDONING RL (trained_ppo <= supervised_ranker on holdout)"
            if trained <= ranker
            else "RL clears the ranker floor (advisory, n_folds<5)"
        ),
        "alpha_claim": "FORBIDDEN (advisory-only, n_folds<5 per P0-1)",
    }

    summary = {
        "mode": "stom_rl_portfolio_sb3_stage_b_smoke",
        "pre_registration": pre_registration,
        "train": train_summary,
        "walk_forward_folds": wf_payload["folds"],
        "advisory_comparison": advisory,
    }
    if config.write_artifacts:
        out = Path(config.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "stage_b_smoke_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8-sig"
        )
    return summary


def _parse_args(argv: Optional[Sequence[str]] = None) -> Tuple[PortfolioSb3TrainConfig, int]:
    import argparse

    parser = argparse.ArgumentParser(description="Stage-B deterministic SB3 portfolio train + advisory holdout.")
    parser.add_argument("--candidate-csv", default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_DEEP_RL_TRAIN_OUTPUT_DIR))
    parser.add_argument("--algorithm", default="ppo", choices=("ppo", "dqn"))
    parser.add_argument("--total-timesteps", type=int, default=5_000)
    parser.add_argument("--top-k-candidates", type=int, default=3)
    parser.add_argument("--max-positions", type=int, default=2)
    parser.add_argument("--cost-bps", type=float, default=25.0)
    parser.add_argument("--turnover-penalty-lambda", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument("--n-folds", type=int, default=2)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument(
        "--no-training-events",
        action="store_true",
        help="Disable the live training-event stream (rl_live_events.jsonl).",
    )
    args = parser.parse_args(argv)
    config = PortfolioSb3TrainConfig(
        candidate_path=args.candidate_csv,
        output_dir=args.output_dir,
        algorithm=args.algorithm,
        total_timesteps=args.total_timesteps,
        top_k_candidates=args.top_k_candidates,
        max_positions=args.max_positions,
        cost_bps=args.cost_bps,
        turnover_penalty_lambda=args.turnover_penalty_lambda,
        seed=args.seed,
        write_artifacts=not args.no_write,
        write_training_events=not args.no_training_events,
    )
    return config, args.n_folds


def main(argv: Optional[Sequence[str]] = None) -> int:
    config, n_folds = _parse_args(argv)
    summary = run_stage_b_smoke(config, n_folds=n_folds)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


__all__ = [
    "PortfolioSb3TrainConfig",
    "DailyPortfolioSb3TrainConfig",
    "MASKABLE_PPO_INVALID_ACTION_TRIGGER",
    "PORTFOLIO_TRAIN_LIVE_ALGORITHM",
    "PORTFOLIO_TRAIN_LIVE_PHASE",
    "SB3_SMOKE_SIGNATURE_FILE",
    "apply_determinism",
    "check_train_env",
    "train_portfolio_model",
    "make_trained_policy_fn",
    "measure_invalid_action_rate",
    "train_and_save",
    "load_trained_model",
    "trained_eval_metrics",
    "assert_reproducible",
    "run_stage_b_smoke",
    "run_daily_portfolio_sb3",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
