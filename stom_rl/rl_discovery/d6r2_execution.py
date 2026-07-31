"""Smoke and primary execution matrix for D6R2."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d3_contract import D3PolicyArmId
from stom_rl.rl_discovery.d3_env import D3Representation
from stom_rl.rl_discovery.d3_training import evaluate_d3_model, shuffled_d3_episodes
from stom_rl.rl_discovery.d6_evaluation import maximum_cumulative_reward_drawdown, parse_d6_events
from stom_rl.rl_discovery.d6r_folds import registered_d6r_folds
from stom_rl.rl_discovery.d6r2_data import FoldEpisodes, build_fold_episodes
from stom_rl.rl_discovery.d6r2_gate import (
    D6R2Algorithm,
    D6R2GateThresholds,
    D6R2RewardArm,
    D6R2UnitOutcome,
    evaluate_d6r2_gate,
)
from stom_rl.rl_discovery.d6r2_source import D6R2SourceBundle, load_d6r2_source
from stom_rl.rl_discovery.d6r2_training import D6R2DqnPolicy, RidgeRewardPolicy, train_dqn_policy, train_ridge_reward_policy
from stom_rl.rl_discovery.d6r2_unit import D6R2UnitRow
from stom_rl.rl_discovery.storage import RunDirectoryGuard


class D6R2RunProfile(StrEnum):
    SMOKE = "SMOKE"
    PRIMARY = "PRIMARY"


class D6R2ExecutionError(RuntimeError):
    """A D6R2 execution violated the frozen schedule or stop rule."""


@dataclass(frozen=True, slots=True)
class D6R2UnitExecution:
    row: D6R2UnitRow
    policy: D6R2DqnPolicy | RidgeRewardPolicy
    events_23bp: tuple[dict[str, str | int | float | None], ...]
    events_0bp: tuple[dict[str, str | int | float | None], ...]


def execute_d6r2(
    repo_root: Path,
    *,
    guard: RunDirectoryGuard,
    profile: D6R2RunProfile,
    approved_smoke: Path | None = None,
) -> Path:
    source = load_d6r2_source(repo_root)
    approved_name = _approve_primary(source, profile, guard, approved_smoke)
    _ = guard.publish_bytes(source.prereg_bytes, "inputs", "prereg.json")
    algorithms, arms, fold_ids, steps = registered_d6r2_schedule(profile)
    representation = D3Representation.for_arm(D3PolicyArmId.TOP5_CONTEXT_4X)
    folds = {fold.fold_id: build_fold_episodes(source.raw.sessions, fold) for fold in registered_d6r_folds() if fold.fold_id in fold_ids}
    _ = guard.publish_bytes(
        canonical_json_bytes([{"fold_id": fold_id, "sha256": folds[fold_id].normalizer_sha256, "scales": folds[fold_id].scales} for fold_id in fold_ids]),
        "inputs", "fold_normalizers.json",
    )
    rows: list[D6R2UnitRow] = []
    outcomes: list[D6R2UnitOutcome] = []
    for algorithm in algorithms:
        seeds = (0,) if algorithm == "RIDGE_REWARD_CEILING" else (0, 1, 2) if profile is D6R2RunProfile.PRIMARY else (0,)
        for arm in arms:
            for seed in seeds:
                for fold_id in fold_ids:
                    unit = _execute_unit(folds[fold_id], algorithm, arm, seed, fold_id, steps, representation)
                    if unit.row.evaluation_23bp.invalid_action_count or unit.row.normalizer_evaluation_row_count:
                        raise D6R2ExecutionError("D6R2 stopped on invalid action or normalization leakage")
                    rows.append(unit.row)
                    outcomes.append(D6R2UnitOutcome(algorithm, arm, seed, fold_id, unit.row.evaluation_23bp, unit.row.maximum_drawdown_23bp, 0))
                    with guard.locked_parent("models", algorithm, arm, f"fold-{fold_id}", f"seed-{seed}", exclusive_leaf=True) as model_dir:
                        unit.policy.save(model_dir / "model")
                    _ = guard.publish_bytes(
                        canonical_json_bytes({**asdict(unit.row), "events": {"evaluation_23bp": unit.events_23bp, "evaluation_0bp": unit.events_0bp}}),
                        "outcomes", algorithm, arm, f"fold-{fold_id}", f"seed-{seed}.json",
                    )
    gate = evaluate_d6r2_gate(tuple(outcomes), thresholds=D6R2GateThresholds.registered()) if profile is D6R2RunProfile.PRIMARY else None
    from stom_rl.rl_discovery.d6r2_evidence import finish_d6r2

    return finish_d6r2(guard, source, profile=profile.value, rows=tuple(rows), gate=gate, approved_smoke=approved_name)


def registered_d6r2_schedule(profile: D6R2RunProfile) -> tuple[tuple[D6R2Algorithm, ...], tuple[D6R2RewardArm, ...], tuple[int, ...], int]:
    algorithms: tuple[D6R2Algorithm, ...] = ("DQN_GAMMA_0_CONTEXTUAL", "DQN_GAMMA_1_SEQUENCE_CONTROL", "RIDGE_REWARD_CEILING")
    arms: tuple[D6R2RewardArm, ...] = ("NATIVE", "SHUFFLED")
    schedules = {
        D6R2RunProfile.SMOKE: (algorithms, arms, (0,), 4_096),
        D6R2RunProfile.PRIMARY: (algorithms, arms, (0, 1, 2, 3, 4), 50_000),
    }
    return schedules[profile]


def _execute_unit(fold: FoldEpisodes, algorithm: D6R2Algorithm, arm: D6R2RewardArm, seed: int, fold_id: int, steps: int, representation: D3Representation) -> D6R2UnitExecution:
    training = fold.training if arm == "NATIVE" else shuffled_d3_episodes(fold.training, seed=seed)
    if algorithm == "RIDGE_REWARD_CEILING":
        policy: D6R2DqnPolicy | RidgeRewardPolicy = train_ridge_reward_policy(training, representation=representation, cost_bp=23, alpha=1.0)
        training_steps = 0
        classification = "NON_RL_SUPERVISED_SIGNAL_FLOOR"
    else:
        gamma = 0.0 if algorithm == "DQN_GAMMA_0_CONTEXTUAL" else 1.0
        policy = train_dqn_policy(training, representation=representation, seed=seed, gamma=gamma, training_steps=steps, cost_bp=23)
        training_steps = steps
        classification = "RL_ALGORITHM_CONTEXTUAL_DIAGNOSTIC" if gamma == 0 else "RL_ALGORITHM_MISSPECIFICATION_CONTROL"
    metrics_23, raw_23 = evaluate_d3_model(policy, fold.evaluation, representation=representation, seed=seed, cost_bp=23)
    metrics_0, raw_0 = evaluate_d3_model(policy, fold.evaluation, representation=representation, seed=seed, cost_bp=0)
    events_23 = tuple(raw_23)
    events_0 = tuple(raw_0)
    drawdown = maximum_cumulative_reward_drawdown(tuple(event.reward for event in parse_d6_events(events_23)))
    row = D6R2UnitRow(algorithm, classification, arm, seed, fold_id, training_steps, len(training), len(fold.evaluation), fold.normalizer_sha256, fold.normalizer_fit_session_count, fold.normalizer_fit_row_count, 0, metrics_23, metrics_0, drawdown)
    return D6R2UnitExecution(row, policy, events_23, events_0)


def _approve_primary(source: D6R2SourceBundle, profile: D6R2RunProfile, guard: RunDirectoryGuard, smoke: Path | None) -> str | None:
    if profile is D6R2RunProfile.SMOKE:
        return None
    if smoke is None:
        raise D6R2ExecutionError("D6R2 Primary requires approved Smoke")
    from stom_rl.rl_discovery.d6r2_evidence import approve_d6r2_smoke

    return approve_d6r2_smoke(smoke, run_root=guard.run_root, prereg_sha256=source.prereg_sha256)
