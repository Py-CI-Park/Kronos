"""MaskablePPO train-only synthetic wiring for Type 1 daily-close research.

This module has no OOS loader or selection path.  It trains and evaluates only the
frozen Type1ClosingEnv, its native action masks, decoder, and Decimal settlement
ledger; synthetic evidence is not a profitability or live-readiness result.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import random
from typing import Any, Mapping, Sequence

import numpy as np
import torch
from torch import nn
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor

from stom_rl.daily_type1_contract import (
    EXECUTION_PROXY, FEATURES, FRESH_OOS_ACCESS_ALLOWED, MISSING_ENTRY_POLICY,
    OFFICIAL_CLOSE, PARTITION_LABEL, PROXY_TIME, PROXY_TIMEZONE,
    RESEARCH_SPLIT_LABEL, Type1Contract, canonical_json_bytes, sha256_canonical,
)
from stom_rl.daily_type1_env import ACTION_COUNT, EXTRACTOR_WIDTH, STOP, STABLE_SLOTS, Type1ClosingEnv

SYNTHETIC_TIMESTEPS = 104_000
ORACLE_CALIBRATION_EPOCHS = 200
SCHEMA_VERSION = 1
SUCCESS_LABEL = "TRAIN_ONLY_SYNTHETIC_WIRING"
OVERFIT_EXACT_BASKET_THRESHOLD = 61
OVERFIT_FINAL_FOUR_MEAN_THRESHOLD = 0.95
OVERFIT_REWARD_RATIO_THRESHOLD = 0.95
POLICY_NET_ARCH = {"pi": [256, 128], "vf": [256, 128]}


@dataclass(frozen=True)
class TrainingConfig:
    """Approved fixed CPU MaskablePPO hyperparameters for G001."""

    seed: int = 0
    synthetic_timesteps: int = SYNTHETIC_TIMESTEPS
    gamma: float = 1.0
    gae_lambda: float = 0.95
    learning_rate: float = 3e-4
    n_steps: int = 1000
    batch_size: int = 250
    clip_range: float = 0.2
    ent_coef: float = 0.01
    n_epochs: int = 10
    normalize_advantage: bool = True
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    oracle_calibration_epochs: int = ORACLE_CALIBRATION_EPOCHS


class Type1SB3FeaturesExtractor(BaseFeaturesExtractor):
    """Torch implementation of the frozen 8514-wide Type 1 concatenation order."""

    def __init__(self, observation_space: Any) -> None:
        super().__init__(observation_space, EXTRACTOR_WIDTH)

    def forward(self, observations: Mapping[str, torch.Tensor]) -> torch.Tensor:
        keys = (
            "candidate_values", "candidate_missing", "availability_mask",
            "current_selection_mask", "prior_selection_mask", "portfolio_state",
        )
        if set(observations) != set(keys):
            raise ValueError("observation keys must match the frozen Type 1 schema")
        parts = [observations[key].float().flatten(start_dim=1) for key in keys]
        result = torch.cat(parts, dim=1)
        if result.shape[1] != EXTRACTOR_WIDTH:
            raise ValueError("observation does not have the frozen 8514-wide Type 1 shape")
        return result


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _set_cpu_seed(seed: int) -> None:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)

def _source_input_hashes(fixture: Path) -> dict[str, str]:
    """Hash every source/runtime input that defines a reproducible Type 1 attempt."""
    root = Path(__file__).resolve().parents[1]
    paths = {
        "trainer": Path(__file__),
        "env": root / "stom_rl" / "daily_type1_env.py",
        "contract": root / "stom_rl" / "daily_type1_contract.py",
        "accounting": root / "stom_rl" / "daily_type1_accounting.py",
        "requirements_type1_lock": root / "requirements-type1.lock",
        "runtime_type1_json": root / "runtime-type1.json",
        "fixture": fixture,
    }
    try:
        hashes = {name: _sha256_file(path) for name, path in paths.items()}
    except OSError as exc:
        raise ValueError("a required Type 1 source/runtime input is missing") from exc
    hashes["type1_contract"] = sha256_canonical(Type1Contract().to_dict())
    return hashes


def _training_trace_is_valid(training: Any, config: Mapping[str, Any], *, accepted: bool) -> None:
    if (
        not isinstance(training, Mapping)
        or training.get("requested_timesteps") != training.get("actual_sb3_timesteps")
    ):
        raise ValueError("training trace does not prove requested and actual SB3 timesteps match")
    calibration = training.get("train_only_oracle_calibration")
    if calibration is not None:
        try:
            epochs = config["oracle_calibration_epochs"]
        except KeyError as exc:
            raise ValueError("training configuration omits oracle calibration epochs") from exc
        _calibration_trace_is_valid(calibration, epochs=epochs)
    elif accepted:
        raise ValueError("accepted artifact requires disclosed synthetic calibration evidence")
    if accepted and (
        training["requested_timesteps"] != SYNTHETIC_TIMESTEPS
        or training["actual_sb3_timesteps"] != SYNTHETIC_TIMESTEPS
        or config != asdict(TrainingConfig())
    ):
        raise ValueError("accepted artifact requires the frozen 104000-step training configuration")
def _calibration_trace_is_valid(trace: Any, *, epochs: int) -> None:
    if not isinstance(trace, Mapping) or set(trace) != {
        "kind", "epochs_per_pass", "pass_order", "passes", "warm_start_final_loss",
        "post_ppo_final_loss", "environment", "decoder", "reward", "interpretation",
    }:
        raise ValueError("synthetic calibration trace schema is invalid")
    if trace["epochs_per_pass"] != epochs or trace["pass_order"] != ["pre_ppo", "post_ppo"]:
        raise ValueError("synthetic calibration pass order or epochs are invalid")
    passes = trace["passes"]
    if not isinstance(passes, Mapping) or set(passes) != {"pre_ppo", "post_ppo"}:
        raise ValueError("synthetic calibration passes are invalid")
    expected = {
        "observation_count": 128,
        "call_index_counts": {"call0": 64, "call1": 64},
        "label_counts": {"slot": 48, "STOP": 80},
    }
    for value in passes.values():
        if not isinstance(value, Mapping) or any(value.get(key) != expected_value for key, expected_value in expected.items()):
            raise ValueError("synthetic calibration composition is invalid")
        masks = value.get("native_masks")
        if (
            not isinstance(masks, Mapping)
            or masks.get("shape") != [128, ACTION_COUNT]
            or masks.get("all_labels_valid") is not True
            or not isinstance(masks.get("sha256"), str)
            or len(masks["sha256"]) != 64
            or value.get("epochs") != epochs
        ):
            raise ValueError("synthetic calibration native-mask trace is invalid")




def _canonical_pair_snapshot(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return {
            "dtype": str(value.dtype),
            "shape": list(value.shape),
            "values": value.tolist(),
        }
    if isinstance(value, Mapping):
        return {str(key): _canonical_pair_snapshot(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_canonical_pair_snapshot(item) for item in value]
    if isinstance(value, list):
        return [_canonical_pair_snapshot(item) for item in value]
    return value


def _synthetic_pair_snapshot_sha256(pairs: Sequence[Mapping[str, Any]]) -> str:
    return sha256_canonical(_canonical_pair_snapshot(tuple(pairs)))


class _SyntheticFixturePairs(tuple[dict[str, Any], ...]):
    """Immutable sequence minted only by the strict synthetic fixture loader."""

    def __new__(
        cls,
        pairs: Sequence[dict[str, Any]],
        fixture_path: Path,
        fixture_sha256: str,
        snapshot_sha256: str,
    ):
        value = super().__new__(cls, pairs)
        value.fixture_path = fixture_path.resolve()
        value.fixture_sha256 = fixture_sha256
        value.snapshot_sha256 = snapshot_sha256
        return value


def _require_loaded_synthetic_fixture(pairs: Sequence[Mapping[str, Any]]) -> _SyntheticFixturePairs:
    if not isinstance(pairs, _SyntheticFixturePairs):
        raise ValueError("oracle calibration requires pairs loaded from the strict synthetic fixture")
    if (
        not pairs.fixture_path.is_file()
        or _sha256_file(pairs.fixture_path) != pairs.fixture_sha256
        or _synthetic_pair_snapshot_sha256(pairs) != pairs.snapshot_sha256
    ):
        raise ValueError("oracle calibration fixture provenance no longer matches the loaded fixture snapshot")
    return pairs


def load_synthetic_fixture(path: str | Path) -> tuple[dict[str, Any], ...]:
    """Expand the compact, train-only fixture into immutable 500-slot input pairs."""
    fixture_path = Path(path)
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    expected_keys = {"schema_version", "label", "partition", "pair_count", "symbols", "pairs"}
    if (
        not isinstance(raw, Mapping)
        or set(raw) != expected_keys
        or type(raw.get("schema_version")) is not int
        or raw["schema_version"] != SCHEMA_VERSION
    ):
        raise ValueError("synthetic fixture schema is unsupported")
    if raw["label"] != SUCCESS_LABEL or raw["partition"] != "TRAIN_ONLY":
        raise ValueError("synthetic fixture must be explicitly TRAIN_ONLY_SYNTHETIC_WIRING")
    pair_count, symbols, pairs = raw["pair_count"], raw["symbols"], raw["pairs"]
    if type(pair_count) is not int or pair_count != 64:
        raise ValueError("synthetic fixture must contain exactly 64 pairs")
    if not isinstance(symbols, list) or len(symbols) != 8 or any(not isinstance(s, str) or len(s) != 6 or not s.isdigit() for s in symbols):
        raise ValueError("synthetic fixture must contain eight six-digit symbols")
    if len(set(symbols)) != len(symbols) or not isinstance(pairs, list) or len(pairs) != pair_count:
        raise ValueError("synthetic fixture pairs are malformed")
    stable_symbols = [f"{slot:06d}" for slot in range(1, STABLE_SLOTS + 1)]
    stable_symbols[:len(symbols)] = symbols
    expanded: list[dict[str, Any]] = []
    for index, item in enumerate(pairs):
        if not isinstance(item, Mapping) or set(item) != {"signal_slot"}:
            raise ValueError(f"synthetic fixture pair {index} must contain exactly signal_slot")
        signal_slot = item["signal_slot"]
        no_trade = index % 4 == 0
        if (signal_slot is None) != no_trade:
            raise ValueError("synthetic fixture must use the frozen ordinal-mod-4 no-trade layout")
        if signal_slot is not None and (type(signal_slot) is not int or not 0 <= signal_slot < len(symbols)):
            raise ValueError(f"synthetic fixture pair {index} has invalid signal_slot")
        decision_date = date(2020, 1, 3) + timedelta(days=index * 4)
        values = np.zeros((STABLE_SLOTS, len(FEATURES)), dtype=np.float32)
        missing = np.zeros_like(values, dtype=np.int8)
        availability = np.zeros(STABLE_SLOTS, dtype=np.int8)
        entry_available = np.zeros(STABLE_SLOTS, dtype=np.int8)
        post_decision_fill_available = np.ones(STABLE_SLOTS, dtype=np.int8)
        gross_returns: list[str | None] = [None] * STABLE_SLOTS
        for slot in range(len(symbols)):
            availability[slot] = entry_available[slot] = 1
            values[slot, 0] = 10.0 if slot == signal_slot else -10.0
            gross_returns[slot] = "0.0200" if slot == signal_slot else "-0.0100"
        expanded.append({
            "candidate_values": values, "candidate_missing": missing,
            "availability_mask": availability, "symbols": stable_symbols,
            "gross_returns": gross_returns, "entry_available": entry_available,
            "post_decision_fill_available": post_decision_fill_available,
            "decision_date": decision_date.isoformat(), "settlement_date": (decision_date + timedelta(days=1)).isoformat(),
            "observation_cutoff_d1": (decision_date - timedelta(days=1)).isoformat(),
            "observation_cutoff_d2": (decision_date - timedelta(days=2)).isoformat(),
            "split_label": RESEARCH_SPLIT_LABEL, "partition_label": PARTITION_LABEL,
            "fresh_oos_access_allowed": FRESH_OOS_ACCESS_ALLOWED, "execution_proxy": EXECUTION_PROXY,
            "proxy_time": PROXY_TIME, "proxy_timezone": PROXY_TIMEZONE, "official_close": OFFICIAL_CLOSE,
            "missing_entry_policy": MISSING_ENTRY_POLICY,
        })
    targets = sum(item["signal_slot"] is not None for item in pairs)
    if targets != 48 or pair_count - targets != 16:
        raise ValueError("synthetic fixture must contain exactly 48 target and 16 no-trade pairs")
    return _SyntheticFixturePairs(
        expanded,
        fixture_path,
        _sha256_file(fixture_path),
        _synthetic_pair_snapshot_sha256(expanded),
    )




def _oracle_action(observation: Mapping[str, np.ndarray]) -> int:
    values = np.asarray(observation["candidate_values"], dtype=np.float32)
    availability = np.asarray(observation["availability_mask"], dtype=np.int8)
    signals = np.flatnonzero((values[:, 0] > 0.0) & (availability == 1))
    if len(signals) > 1:
        raise ValueError("synthetic oracle requires at most one visible positive signal")
    return STOP if not len(signals) else int(signals[0]) + 1


def _policy_kwargs() -> dict[str, Any]:
    return {
        "features_extractor_class": Type1SB3FeaturesExtractor,
        "net_arch": POLICY_NET_ARCH,
        "activation_fn": nn.Tanh,
        "ortho_init": True,
        "optimizer_class": torch.optim.Adam,
        "optimizer_kwargs": {"eps": 1e-5},
    }
def _ppo_contract(config: TrainingConfig) -> dict[str, Any]:
    return {
        "gamma": config.gamma,
        "gae_lambda": config.gae_lambda,
        "learning_rate": config.learning_rate,
        "n_steps": config.n_steps,
        "batch_size": config.batch_size,
        "clip_range": config.clip_range,
        "ent_coef": config.ent_coef,
        "n_epochs": config.n_epochs,
        "normalize_advantage": config.normalize_advantage,
        "vf_coef": config.vf_coef,
        "max_grad_norm": config.max_grad_norm,
    }




def _assert_model_contract(model: Any, config: TrainingConfig) -> None:
    policy = model.policy
    extractor = policy.features_extractor
    if extractor.__class__.__name__ != "Type1SB3FeaturesExtractor" or extractor.features_dim != EXTRACTOR_WIDTH:
        raise ValueError("loaded model does not use the frozen Type 1 features extractor")
    if (
        model.seed != config.seed
        or str(model.device) != "cpu"
        or model.action_space.n != ACTION_COUNT
        or model.gamma != config.gamma
        or model.gae_lambda != config.gae_lambda
        or model.learning_rate != config.learning_rate
        or model.lr_schedule(1.0) != config.learning_rate
        or model.n_steps != config.n_steps
        or model.batch_size != config.batch_size
        or model.clip_range(1.0) != config.clip_range
        or model.ent_coef != config.ent_coef
        or model.n_epochs != config.n_epochs
        or model.normalize_advantage is not config.normalize_advantage
        or model.vf_coef != config.vf_coef
        or model.max_grad_norm != config.max_grad_norm
    ):
        raise ValueError("loaded model PPO settings do not match the frozen configuration")
    if not isinstance(policy.activation_fn(), nn.Tanh) or policy.ortho_init is not True:
        raise ValueError("loaded model policy network settings do not match the frozen configuration")
    if policy.optimizer_class is not torch.optim.Adam or policy.optimizer_kwargs != {"eps": 1e-5}:
        raise ValueError("loaded model optimizer settings do not match the frozen configuration")
    expected = [256, 128]
    if [layer.out_features for layer in policy.mlp_extractor.policy_net if isinstance(layer, nn.Linear)] != expected or [layer.out_features for layer in policy.mlp_extractor.value_net if isinstance(layer, nn.Linear)] != expected:
        raise ValueError("loaded model pi/vf network widths do not match the frozen configuration")


def create_model(pairs: Sequence[Mapping[str, Any]], config: TrainingConfig = TrainingConfig()):
    """Create the approved CPU MaskablePPO model around the unmodified Type1ClosingEnv."""
    _set_cpu_seed(config.seed)
    try:
        from sb3_contrib import MaskablePPO
        from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
    except ImportError as exc:
        raise RuntimeError("MaskablePPO requires sb3-contrib==2.8.0") from exc
    vec_env = DummyVecEnv([lambda: Type1ClosingEnv(pairs)])
    # This persisted no-op normalizer is part of the approved downstream model-loading contract.
    normalizer = VecNormalize(vec_env, norm_obs=False, norm_reward=False)
    model = MaskablePPO("MultiInputPolicy", normalizer, seed=config.seed, device="cpu", gamma=config.gamma,
        gae_lambda=config.gae_lambda, learning_rate=config.learning_rate, n_steps=config.n_steps,
        batch_size=config.batch_size, clip_range=config.clip_range, ent_coef=config.ent_coef,
        n_epochs=config.n_epochs, normalize_advantage=config.normalize_advantage, vf_coef=config.vf_coef,
        max_grad_norm=config.max_grad_norm, policy_kwargs=_policy_kwargs(), verbose=0)
    _assert_model_contract(model, config)
    return model, normalizer


def _oracle_calibration(model: Any, pairs: Sequence[Mapping[str, Any]], *, epochs: int) -> float:
    """Apply the disclosed synthetic-only oracle calibration to loaded fixture pairs."""
    _require_loaded_synthetic_fixture(pairs)
    observations: list[Mapping[str, np.ndarray]] = []
    masks: list[np.ndarray] = []
    actions: list[int] = []
    call_indices: list[int] = []
    if type(epochs) is not int or epochs <= 0:
        raise ValueError("oracle calibration epochs must be a positive integer")
    env = Type1ClosingEnv(pairs)
    observation, _ = env.reset(seed=0)
    while True:
        call_index = env._call_index
        action = _oracle_action(observation) if call_index == 0 else STOP
        if call_index <= 1:
            observations.append(observation)
            masks.append(env.action_masks())
            actions.append(action)
            call_indices.append(call_index)
        observation, _, terminated, truncated, _ = env.step(action)
        if terminated or truncated:
            break
    action_masks = np.stack(masks)
    if (
        len(observations) != 128
        or call_indices.count(0) != 64
        or call_indices.count(1) != 64
        or sum(action != STOP for action in actions) != 48
        or sum(action == STOP for action in actions) != 80
        or not np.all(action_masks[np.arange(len(actions)), actions])
    ):
        raise ValueError("synthetic oracle calibration composition does not match amendment A1")
    stacked = {
        key: np.stack([np.asarray(item[key]) for item in observations])
        for key in observations[0]
    }
    observation_tensor, _ = model.policy.obs_to_tensor(stacked)
    action_tensor = torch.as_tensor(actions, dtype=torch.long, device=model.device)
    model.policy.set_training_mode(True)
    loss_value = 0.0
    for _ in range(epochs):
        distribution = model.policy.get_distribution(observation_tensor, action_masks=action_masks)
        loss = -distribution.log_prob(action_tensor).mean()
        model.policy.optimizer.zero_grad()
        loss.backward()
        model.policy.optimizer.step()
        loss_value = float(loss.detach().cpu())
    model._type1_last_calibration_trace = {
        "observation_count": len(observations),
        "call_index_counts": {"call0": call_indices.count(0), "call1": call_indices.count(1)},
        "label_counts": {"slot": sum(action != STOP for action in actions), "STOP": sum(action == STOP for action in actions)},
        "native_masks": {
            "shape": list(action_masks.shape),
            "all_labels_valid": True,
            "sha256": hashlib.sha256(action_masks.tobytes()).hexdigest(),
        },
        "epochs": epochs,
    }
    return loss_value


def calibrate_synthetic_oracle(model: Any, pairs: Sequence[Mapping[str, Any]], *, epochs: int) -> float:
    """Public discovery-lab boundary for disclosed synthetic-only oracle BC."""

    return _oracle_calibration(model, pairs, epochs=epochs)


def train_model(pairs: Sequence[Mapping[str, Any]], config: TrainingConfig = TrainingConfig(), *, timesteps: int | None = None):
    """Train generic Type 1 pairs with PPO only; this path never invokes oracle calibration."""
    total_timesteps = config.synthetic_timesteps if timesteps is None else timesteps
    if type(total_timesteps) is not int or total_timesteps <= 0:
        raise ValueError("timesteps must be a positive integer")
    model, normalizer = create_model(pairs, config)
    model.learn(total_timesteps=total_timesteps, progress_bar=False)
    model._type1_training_trace = {
        "requested_timesteps": total_timesteps,
        "actual_sb3_timesteps": model.num_timesteps,
        "train_only_oracle_calibration": None,
    }
    return model, normalizer


def train_synthetic_calibrated_model(
    pairs: Sequence[Mapping[str, Any]], config: TrainingConfig = TrainingConfig(), *, timesteps: int | None = None,
):
    """Train strict loaded synthetic fixture pairs with disclosed pre/post oracle calibration."""
    _require_loaded_synthetic_fixture(pairs)
    total_timesteps = config.synthetic_timesteps if timesteps is None else timesteps
    if type(total_timesteps) is not int or total_timesteps <= 0:
        raise ValueError("timesteps must be a positive integer")
    model, normalizer = create_model(pairs, config)
    warm_start_loss = _oracle_calibration(model, pairs, epochs=config.oracle_calibration_epochs)
    warm_start_trace = dict(model._type1_last_calibration_trace)
    model.learn(total_timesteps=total_timesteps, progress_bar=False)
    final_calibration_loss = _oracle_calibration(model, pairs, epochs=config.oracle_calibration_epochs)
    final_trace = dict(model._type1_last_calibration_trace)
    model._type1_training_trace = {
        "requested_timesteps": total_timesteps,
        "actual_sb3_timesteps": model.num_timesteps,
        "train_only_oracle_calibration": {
            "kind": "disclosed synthetic oracle behavior cloning before and after PPO",
            "epochs_per_pass": config.oracle_calibration_epochs,
            "pass_order": ["pre_ppo", "post_ppo"],
            "passes": {"pre_ppo": warm_start_trace, "post_ppo": final_trace},
            "warm_start_final_loss": format(warm_start_loss, ".12f"),
            "post_ppo_final_loss": format(final_calibration_loss, ".12f"),
            "environment": "Type1ClosingEnv",
            "decoder": "native oracle action through the frozen action contract",
            "reward": "native economic reward during the fixed PPO learn budget",
            "interpretation": "plumbing-only overfit calibration; not market learning or profitability evidence",
        },
    }
    return model, normalizer


def _oracle_trace(pairs: Sequence[Mapping[str, Any]], *, seed: int) -> tuple[list[int], float, list[float]]:
    env = Type1ClosingEnv(pairs)
    observation, _ = env.reset(seed=seed)
    actions: list[int] = []
    rewards: list[float] = []
    while True:
        action = _oracle_action(observation) if env._call_index == 0 else STOP
        observation, reward, terminated, truncated, _ = env.step(action)
        actions.append(action)
        if env._call_index == 0 or terminated:
            rewards.append(float(reward))
        if terminated or truncated:
            return actions, sum(rewards), rewards


def evaluate_model(model: Any, pairs: Sequence[Mapping[str, Any]], *, seed: int = 0) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Replay the model through the same native environment path used for settlement."""
    env = Type1ClosingEnv(pairs)
    observation, _ = env.reset(seed=seed)
    events: list[dict[str, Any]] = []
    invalid_actions = 0
    while True:
        mask = env.action_masks()
        pair_index, call_index = env._pair_index, env._call_index
        oracle_action = _oracle_action(observation) if call_index == 0 else STOP
        action, _ = model.predict(observation, deterministic=True, action_masks=mask)
        action_value = int(np.asarray(action).item())
        if not mask[action_value]:
            invalid_actions += 1
            raise RuntimeError("MaskablePPO predicted an invalid action despite supplied environment mask")
        observation, _, terminated, truncated, info = env.step(action_value)
        settlement = info.get("settlement")
        no_fill_slots = 0 if settlement is None else int(settlement.no_fill_slots)
        events.append({"pair_index": pair_index, "call_index": call_index, "action": action_value,
            "oracle_action": oracle_action, "action_kind": "STOP" if action_value == STOP else "SLOT",
            "mask_valid": True, "status": info["status"], "event_reward": info["event_reward"],
            "economic_reward": info.get("economic_reward"), "no_fill_slots": no_fill_slots})
        if terminated or truncated:
            break
    oracle_actions, oracle_reward, oracle_pair_rewards = _oracle_trace(pairs, seed=seed)
    baskets = [events[index:index + 10] for index in range(0, len(events), 10)]
    oracle_baskets = [oracle_actions[index:index + 10] for index in range(0, len(oracle_actions), 10)]
    exact_baskets = sum([event["action"] for event in basket] == oracle for basket, oracle in zip(baskets, oracle_baskets))
    final_four_exact_mean = sum([event["action"] for event in basket] == oracle for basket, oracle in zip(baskets[-4:], oracle_baskets[-4:])) / 4
    achieved_pair_rewards = [float(basket[-1]["event_reward"]) for basket in baskets]
    achieved_reward = sum(achieved_pair_rewards)
    if oracle_reward <= 0:
        raise ValueError("oracle total reward must be positive for reward-ratio evaluation")
    reward_ratio = achieved_reward / oracle_reward
    final_four_oracle = sum(oracle_pair_rewards[-4:])
    if final_four_oracle <= 0:
        raise ValueError("final-four oracle reward must be positive for reward-ratio evaluation")
    final_four_reward_ratio = sum(achieved_pair_rewards[-4:]) / final_four_oracle
    oracle_decisions = oracle_actions[::10]
    forbidden_statuses = sum(event["status"] == "BLOCK" for event in events)
    no_fill_count = sum(event["no_fill_slots"] for event in events)
    overfit_pass = (exact_baskets >= OVERFIT_EXACT_BASKET_THRESHOLD and final_four_exact_mean >= OVERFIT_FINAL_FOUR_MEAN_THRESHOLD
        and reward_ratio >= OVERFIT_REWARD_RATIO_THRESHOLD and final_four_reward_ratio >= OVERFIT_REWARD_RATIO_THRESHOLD
        and invalid_actions == 0 and forbidden_statuses == 0 and no_fill_count == 0)
    metrics = {"label": SUCCESS_LABEL, "partition": "TRAIN_ONLY", "event_count": len(events),
        "invalid_action_count": invalid_actions, "block_count": forbidden_statuses, "no_fill_count": no_fill_count,
        "terminal_status": events[-1]["status"], "total_event_reward": format(achieved_reward, ".12f"),
        "oracle_selection_count": sum(action != STOP for action in oracle_decisions),
        "oracle_no_trade_count": sum(action == STOP for action in oracle_decisions),
        "exact_basket_count": exact_baskets, "exact_basket_accuracy": format(exact_baskets / len(baskets), ".12f"),
        "final_four_exact_mean": format(final_four_exact_mean, ".12f"), "oracle_total_reward": format(oracle_reward, ".12f"),
        "achieved_reward_ratio": format(reward_ratio, ".12f"), "final_four_reward_ratio": format(final_four_reward_ratio, ".12f"),
        "overfit_threshold": {"exact_basket_count": OVERFIT_EXACT_BASKET_THRESHOLD,
            "final_four_exact_mean": OVERFIT_FINAL_FOUR_MEAN_THRESHOLD, "achieved_reward_ratio": OVERFIT_REWARD_RATIO_THRESHOLD,
            "final_four_reward_ratio": OVERFIT_REWARD_RATIO_THRESHOLD, "zero_invalid_block_no_fill": True},
        "overfit_pass": overfit_pass, "interpretation": "Synthetic train-only overfit evidence only; not profitability or live readiness."}
    return events, metrics


def _write_artifacts(out_root: Path, model: Any, normalizer: Any, config: TrainingConfig, fixture_path: Path, events: list[dict[str, Any]], metrics: dict[str, Any]) -> dict[str, Any]:
    paths = {name: out_root / name for name in ("type1_maskable_ppo.zip", "type1_normalizer.pkl", "type1_contract.json", "events.json", "metrics.json", "model_manifest.json")}
    if any(path.exists() for path in paths.values()):
        raise FileExistsError("artifact root already contains Type 1 artifacts")
    contract = Type1Contract().to_dict()
    paths["type1_contract.json"].write_bytes(canonical_json_bytes(contract))
    model.save(str(paths["type1_maskable_ppo.zip"]))
    normalizer.save(str(paths["type1_normalizer.pkl"]))
    paths["events.json"].write_bytes(canonical_json_bytes(events))
    full_metrics = dict(metrics)
    full_metrics["training"] = model._type1_training_trace
    paths["metrics.json"].write_bytes(canonical_json_bytes(full_metrics))
    manifest = {"schema_version": SCHEMA_VERSION, "label": SUCCESS_LABEL, "policy": "MultiInputPolicy", "action_count": ACTION_COUNT,
        "extractor": {"class": "Type1SB3FeaturesExtractor", "width": EXTRACTOR_WIDTH, "concatenation_order": ["candidate_values", "candidate_missing", "availability_mask", "current_selection_mask", "prior_selection_mask", "portfolio_state"]},
        "policy_kwargs": {"net_arch": POLICY_NET_ARCH, "activation_fn": "Tanh", "ortho_init": True, "optimizer_class": "Adam", "optimizer_eps": 1e-5},
        "ppo": _ppo_contract(config),
        "config": asdict(config), "training": model._type1_training_trace, "source_inputs": _source_input_hashes(fixture_path),
        "fixture_sha256": _sha256_file(fixture_path), "contract_sha256": sha256_canonical(contract),
        "model_sha256": _sha256_file(paths["type1_maskable_ppo.zip"]),
        "normalizer_sha256": _sha256_file(paths["type1_normalizer.pkl"]), "events_sha256": _sha256_file(paths["events.json"]), "metrics_sha256": _sha256_file(paths["metrics.json"])}
    paths["model_manifest.json"].write_bytes(canonical_json_bytes(manifest))
    return manifest


def _load_manifest(root: Path, fixture: Path) -> dict[str, Any]:
    try:
        manifest = json.loads((root / "model_manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("model manifest is missing or malformed") from exc
    required = {"schema_version", "label", "policy", "action_count", "extractor", "policy_kwargs", "ppo", "config", "training", "source_inputs", "contract_sha256", "model_sha256", "normalizer_sha256", "events_sha256", "metrics_sha256", "fixture_sha256"}
    allowed_keys = (required, required | {"terminal_receipt_sha256"})
    if (
        not isinstance(manifest, Mapping)
        or set(manifest) not in allowed_keys
        or type(manifest["schema_version"]) is not int
        or manifest["schema_version"] != SCHEMA_VERSION
        or manifest["label"] != SUCCESS_LABEL
    ):
        raise ValueError("model manifest schema is unsupported")
    if manifest["policy"] != "MultiInputPolicy" or manifest["action_count"] != ACTION_COUNT or manifest["extractor"] != {"class": "Type1SB3FeaturesExtractor", "width": EXTRACTOR_WIDTH, "concatenation_order": ["candidate_values", "candidate_missing", "availability_mask", "current_selection_mask", "prior_selection_mask", "portfolio_state"]}:
        raise ValueError("model manifest does not match the frozen Type 1 model schema")
    try:
        config = TrainingConfig(**manifest["config"])
    except (TypeError, ValueError) as exc:
        raise ValueError("model manifest configuration is malformed") from exc
    if (
        manifest["policy_kwargs"] != {"net_arch": POLICY_NET_ARCH, "activation_fn": "Tanh", "ortho_init": True, "optimizer_class": "Adam", "optimizer_eps": 1e-5}
        or manifest["ppo"] != _ppo_contract(config)
    ):
        raise ValueError("model manifest does not match frozen policy settings")
    for filename, key in (("type1_contract.json", "contract_sha256"), ("type1_maskable_ppo.zip", "model_sha256"), ("type1_normalizer.pkl", "normalizer_sha256"), ("events.json", "events_sha256"), ("metrics.json", "metrics_sha256")):
        try:
            actual = _sha256_file(root / filename)
        except OSError as exc:
            raise ValueError(f"{filename} is missing") from exc
        if actual != manifest[key]:
            raise ValueError(f"{filename} hash does not match model manifest")
    contract = json.loads((root / "type1_contract.json").read_text(encoding="utf-8"))
    Type1Contract.from_mapping(contract)
    if sha256_canonical(contract) != manifest["contract_sha256"] or _sha256_file(fixture) != manifest["fixture_sha256"]:
        raise ValueError("contract or fixture hash does not match model manifest")
    if manifest["source_inputs"] != _source_input_hashes(fixture):
        raise ValueError("source/runtime input hash does not match model manifest")
    _training_trace_is_valid(manifest["training"], manifest["config"], accepted=False)
    return dict(manifest)


def _load_terminal_pass_receipt(root: Path, manifest: Mapping[str, Any]) -> None:
    expected_hash = manifest.get("terminal_receipt_sha256")
    if not isinstance(expected_hash, str):
        raise ValueError("terminal PASS receipt is missing")
    receipt_path = root / "terminal_receipt.json"
    try:
        receipt_bytes = receipt_path.read_bytes()
        receipt = json.loads(receipt_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("terminal PASS receipt is missing or malformed") from exc
    if _sha256_file(receipt_path) != expected_hash:
        raise ValueError("terminal receipt hash does not match model manifest")
    if (
        not isinstance(receipt, Mapping)
        or type(receipt.get("schema_version")) is not int
        or receipt["schema_version"] != SCHEMA_VERSION
    ):
        raise ValueError("terminal receipt schema is unsupported")
    core = dict(manifest)
    core.pop("terminal_receipt_sha256", None)
    expected = {
        "schema_version": SCHEMA_VERSION,
        "label": SUCCESS_LABEL,
        "terminal_status": "PASS",
        "detail": "dual independent reload evaluations were byte-identical and the synthetic overfit gate passed",
        "manifest_core_sha256": sha256_canonical(core),
    }
    if receipt != expected:
        raise ValueError("terminal receipt is not an untampered PASS")


def _verify_stored_model(root: Path, fixture: Path, *, require_terminal_pass: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest = _load_manifest(root, fixture)
    if require_terminal_pass:
        _load_terminal_pass_receipt(root, manifest)
        _training_trace_is_valid(manifest["training"], manifest["config"], accepted=True)
    try:
        stored_events = (root / "events.json").read_bytes()
        stored_metrics = (root / "metrics.json").read_bytes()
        stored_metrics_value = json.loads(stored_metrics)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("stored replay records are missing or malformed") from exc
    if not isinstance(stored_metrics_value, Mapping) or stored_metrics_value.get("training") != manifest["training"]:
        raise ValueError("stored training metadata does not match model manifest")
    try:
        from sb3_contrib import MaskablePPO
        from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
    except ImportError as exc:
        raise RuntimeError("MaskablePPO requires sb3-contrib==2.8.0") from exc
    pairs = load_synthetic_fixture(fixture)
    normalizer = VecNormalize.load(str(root / "type1_normalizer.pkl"), DummyVecEnv([lambda: Type1ClosingEnv(pairs)]))
    model = MaskablePPO.load(str(root / "type1_maskable_ppo.zip"), env=normalizer, device="cpu")
    _assert_model_contract(model, TrainingConfig(**manifest["config"]))
    events, metrics = evaluate_model(model, pairs, seed=manifest["config"]["seed"])
    replay_metrics = dict(metrics)
    replay_metrics["training"] = manifest["training"]
    if canonical_json_bytes(events) != stored_events or canonical_json_bytes(replay_metrics) != stored_metrics:
        raise ValueError("replayed behavior does not byte-match stored events and metrics")
    return events, metrics


def verify_model(out_root: str | Path, fixture_path: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Require an untampered terminal PASS, then byte-verify a fresh native replay."""
    return _verify_stored_model(Path(out_root), Path(fixture_path), require_terminal_pass=True)


def _write_receipt(root: Path, status: str, detail: str, manifest: Mapping[str, Any] | None = None) -> None:
    receipt = root / "terminal_receipt.json"
    if receipt.exists():
        raise FileExistsError("terminal receipt already exists")
    value: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "label": SUCCESS_LABEL, "terminal_status": status, "detail": detail}
    if manifest is not None:
        value["manifest_core_sha256"] = sha256_canonical(manifest)
    receipt.write_bytes(canonical_json_bytes(value))


def _finalize_receipt(root: Path, manifest: dict[str, Any], status: str, detail: str) -> None:
    _write_receipt(root, status, detail, manifest)
    manifest["terminal_receipt_sha256"] = _sha256_file(root / "terminal_receipt.json")
    (root / "model_manifest.json").write_bytes(canonical_json_bytes(manifest))


def run_synthetic_overfit(out_root: str | Path, fixture_path: str | Path, config: TrainingConfig = TrainingConfig(), *, timesteps: int | None = None, require_overfit: bool = True) -> dict[str, Any]:
    """Create one immutable artifact attempt and durable PASS/FAIL terminal receipt."""
    if not isinstance(require_overfit, bool):
        raise ValueError("require_overfit must be a boolean")
    root, fixture = Path(out_root), Path(fixture_path)
    if root.exists():
        raise FileExistsError("out_root must be a unique caller-supplied path that does not exist")
    root.mkdir(parents=True)
    manifest: dict[str, Any] | None = None
    try:
        pairs = load_synthetic_fixture(fixture)
        model, normalizer = train_synthetic_calibrated_model(pairs, config, timesteps=timesteps)
        events, metrics = evaluate_model(model, pairs, seed=config.seed)
        manifest = _write_artifacts(root, model, normalizer, config, fixture, events, metrics)
        first_events, first_metrics = _verify_stored_model(root, fixture, require_terminal_pass=False)
        second_events, second_metrics = _verify_stored_model(root, fixture, require_terminal_pass=False)
        if (canonical_json_bytes(events) != canonical_json_bytes(first_events)
                or canonical_json_bytes(metrics) != canonical_json_bytes(first_metrics)
                or canonical_json_bytes(first_events) != canonical_json_bytes(second_events)
                or canonical_json_bytes(first_metrics) != canonical_json_bytes(second_metrics)):
            raise RuntimeError("direct and two independent reload evaluations did not produce byte-identical traces and metrics")
        if not require_overfit:
            _finalize_receipt(root, manifest, "ABORTED", "incomplete smoke attempt; not an accepted 104000-step overfit result")
            return manifest
        if config != TrainingConfig() or (timesteps is not None and timesteps != SYNTHETIC_TIMESTEPS):
            raise ValueError("accepted synthetic overfit requires exact seed 0 and 104000 timesteps")
        if not metrics["overfit_pass"]:
            raise RuntimeError("synthetic overfit threshold was not met")
        _finalize_receipt(root, manifest, "PASS", "dual independent reload evaluations were byte-identical and the synthetic overfit gate passed")
        return manifest
    except Exception as exc:
        if not (root / "terminal_receipt.json").exists():
            _write_receipt(root, "FAIL", f"{type(exc).__name__}: {exc}", manifest)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Type 1 train-only MaskablePPO wiring")
    parser.add_argument("mode", choices=("synthetic-overfit", "verify-model"))
    parser.add_argument("--out-root", required=True, type=Path)
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/type1_synthetic_fixture.json"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--timesteps", type=int, default=None)
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args(argv)
    if args.allow_incomplete and args.timesteps is None:
        parser.error("--allow-incomplete requires an explicit --timesteps smoke bound")
    config = TrainingConfig(seed=args.seed)
    if args.mode == "synthetic-overfit":
        manifest = run_synthetic_overfit(args.out_root, args.fixture, config, timesteps=args.timesteps, require_overfit=not args.allow_incomplete)
        print(json.dumps(manifest, sort_keys=True))
    else:
        _, metrics = verify_model(args.out_root, args.fixture)
        print(json.dumps(metrics, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
