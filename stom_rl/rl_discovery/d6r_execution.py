"""D6R deterministic training and fold-evaluation execution."""

from __future__ import annotations

from dataclasses import asdict
from enum import StrEnum
from pathlib import Path
from typing import assert_never

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d3_contract import D3PolicyArmId
from stom_rl.rl_discovery.d3_env import D3Representation
from stom_rl.rl_discovery.d6r_approval import approve_d6r_smoke
from stom_rl.rl_discovery.d6r_evidence import finish_d6r
from stom_rl.rl_discovery.d6r_folds import registered_d6r_folds, split_d6r_fold
from stom_rl.rl_discovery.d6r_gate import D6RProfileId, D6RRewardArm
from stom_rl.rl_discovery.d6r_gate import (
    D6RGateResult,
    D6RGateThresholds,
    D6RUnitOutcome,
    evaluate_d6r_gate,
)
from stom_rl.rl_discovery.d6r_source import D6RSourceBundle, load_d6r_source
from stom_rl.rl_discovery.d6r_unit import D6RUnitRow, execute_d6r_unit
from stom_rl.rl_discovery.storage import RunDirectoryGuard


class D6RExecutionError(RuntimeError):
    """A D6R unit violated a preregistered execution stop rule."""


class D6RRunProfile(StrEnum):
    SMOKE = "SMOKE"
    PRIMARY = "PRIMARY"


def registered_d6r_schedule(
    profile: D6RRunProfile,
) -> tuple[
    tuple[D6RProfileId, ...],
    tuple[D6RRewardArm, ...],
    tuple[int, ...],
    tuple[int, ...],
    int,
]:
    profiles: tuple[D6RProfileId, ...] = ("COST_ONLY", "TURNOVER_10BP")
    arms: tuple[D6RRewardArm, ...] = ("NATIVE", "SHUFFLED")
    match profile:
        case D6RRunProfile.SMOKE:
            return profiles, arms, (0,), (0,), 4_096
        case D6RRunProfile.PRIMARY:
            return profiles, arms, (0, 1, 2), (0, 1, 2, 3, 4), 50_000
    assert_never(profile)


def execute_d6r(
    repo_root: Path,
    *,
    guard: RunDirectoryGuard,
    profile: D6RRunProfile,
    approved_smoke: Path | None = None,
) -> Path:
    source = load_d6r_source(repo_root)
    approved_name = _approve_primary(
        profile,
        approved_smoke=approved_smoke,
        guard=guard,
        prereg_sha256=source.prereg_sha256,
    )
    _ = guard.publish_bytes(source.prereg_bytes, "inputs", "prereg.json")
    profiles, arms, seeds, fold_ids, steps = registered_d6r_schedule(profile)
    fold_by_id = {fold.fold_id: fold for fold in registered_d6r_folds()}
    representation = D3Representation.for_arm(D3PolicyArmId.TOP5_CONTEXT_4X)
    rows: list[D6RUnitRow] = []
    outcomes: list[D6RUnitOutcome] = []
    for reward_profile in profiles:
        for reward_arm in arms:
            for seed in seeds:
                for fold_id in fold_ids:
                    training, evaluation = split_d6r_fold(
                        source.episodes,
                        fold_by_id[fold_id],
                    )
                    unit = execute_d6r_unit(
                        training,
                        evaluation,
                        profile=reward_profile,
                        reward_arm=reward_arm,
                        seed=seed,
                        fold_id=fold_id,
                        training_steps=steps,
                        representation=representation,
                    )
                    if unit.row.evaluation_23bp.invalid_action_count != 0:
                        raise D6RExecutionError("D6R stopped on an invalid action")
                    rows.append(unit.row)
                    outcomes.append(
                        D6RUnitOutcome(
                            reward_profile,
                            reward_arm,
                            seed,
                            fold_id,
                            unit.row.evaluation_23bp,
                            unit.row.evaluation_0bp,
                            unit.row.maximum_drawdown_23bp,
                        )
                    )
                    with guard.locked_parent(
                        "models",
                        reward_profile,
                        reward_arm,
                        f"fold-{fold_id}",
                        f"seed-{seed}",
                        exclusive_leaf=True,
                    ) as model_dir:
                        unit.model.save(model_dir / "model")
                    _ = guard.publish_bytes(
                        canonical_json_bytes(
                            {
                                **asdict(unit.row),
                                "events": {
                                    "evaluation_23bp": [
                                        event.model_dump(mode="json")
                                        for event in unit.events_23bp
                                    ],
                                    "evaluation_0bp": [
                                        event.model_dump(mode="json")
                                        for event in unit.events_0bp
                                    ],
                                },
                            }
                        ),
                        "outcomes",
                        reward_profile,
                        reward_arm,
                        f"fold-{fold_id}",
                        f"seed-{seed}.json",
                    )
    gate = _evaluate_primary(profile, source, tuple(outcomes))
    return finish_d6r(
        guard,
        source,
        profile=profile.value,
        rows=tuple(rows),
        gate=gate,
        approved_smoke=approved_name,
    )


def _approve_primary(
    profile: D6RRunProfile,
    *,
    approved_smoke: Path | None,
    guard: RunDirectoryGuard,
    prereg_sha256: str,
) -> str | None:
    match profile:
        case D6RRunProfile.SMOKE:
            return None
        case D6RRunProfile.PRIMARY:
            if approved_smoke is None:
                raise D6RExecutionError("D6R Primary requires an approved Smoke")
            return approve_d6r_smoke(
                approved_smoke,
                run_root=guard.run_root,
                prereg_sha256=prereg_sha256,
            )
    assert_never(profile)


def _evaluate_primary(
    profile: D6RRunProfile,
    source: D6RSourceBundle,
    outcomes: tuple[D6RUnitOutcome, ...],
) -> D6RGateResult | None:
    match profile:
        case D6RRunProfile.SMOKE:
            return None
        case D6RRunProfile.PRIMARY:
            gate = source.prereg.gate
            return evaluate_d6r_gate(
                outcomes,
                thresholds=D6RGateThresholds(
                    gate.minimum_native_median_accuracy,
                    gate.minimum_native_median_reward_ratio,
                    gate.minimum_native_median_total_reward,
                    gate.minimum_native_reward_delta_vs_shuffled,
                    gate.minimum_positive_fold_fraction,
                    gate.minimum_positive_seed_fraction,
                    gate.maximum_native_median_trade_rate,
                    gate.minimum_trade_rate_reduction_vs_cost_only,
                    gate.maximum_native_median_reward_drawdown,
                    gate.zero_invalid_actions,
                ),
            )
    assert_never(profile)
