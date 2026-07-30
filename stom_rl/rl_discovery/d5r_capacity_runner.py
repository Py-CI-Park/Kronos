"""Smoke and Primary D5R capacity execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from statistics import median

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d2_custody import held_bytes
from stom_rl.rl_discovery.d3_contract import D3PolicyArmId
from stom_rl.rl_discovery.d3_env import D3Representation
from stom_rl.rl_discovery.d3_training import D3Metrics, evaluate_d3_model, shuffled_d3_episodes
from stom_rl.rl_discovery.d4_training import D4PlainPolicy
from stom_rl.rl_discovery.d5_approval import primary_custody_signature
from stom_rl.rl_discovery.d5r_approval import approve_d5r_smoke
from stom_rl.rl_discovery.d5r_diagnostic import diagnose_d5r_unit
from stom_rl.rl_discovery.d5r_gate import (
    D5RBaseline,
    D5RCapacityGate,
    D5RCapacityOutcome,
    evaluate_d5r_capacity_gate,
)
from stom_rl.rl_discovery.d5r_source import D5RSourceBundle, load_d5r_source
from stom_rl.rl_discovery.d5r_training import advance_d5r_lineage, start_d5r_lineage
from stom_rl.rl_discovery.storage import (
    RunDirectoryGuard,
    artifact_manifest_sha256,
    create_run_directory,
)


class D5RCapacityProfile(StrEnum):
    SMOKE = "SMOKE"
    PRIMARY = "PRIMARY"


@dataclass(frozen=True, slots=True)
class D5RCheckpointRow:
    reward_arm: str
    seed: int
    total_steps: int
    fit_23bp: D3Metrics
    native_23bp: D3Metrics
    native_0bp: D3Metrics


def run_d5r_capacity(
    repo_root: Path,
    *,
    run_root: Path,
    run_id: str,
    profile: D5RCapacityProfile,
    approved_smoke: Path | None = None,
    approval_key: bytes | None = None,
) -> Path:
    source = load_d5r_source(repo_root)
    _require_capacity_study(source)
    approved_name = (
        approve_d5r_smoke(
            approved_smoke,
            run_root=run_root,
            approval_key=approval_key,
            prereg_sha=source.prereg_sha256,
            episode_sha=source.prereg.source_run.episode_snapshot_sha256,
        )
        if profile is D5RCapacityProfile.PRIMARY
        else None
    )
    run_dir = create_run_directory(run_root, run_id)
    guard = RunDirectoryGuard.capture(run_root, run_dir)
    amendment = held_bytes(
        repo_root / "docs/kronos_rl_discovery_type2_d5r_amendment_2026-07-30.json",
        anchor=repo_root,
    )
    _ = guard.publish_bytes(source.prereg_bytes, "inputs", "prereg.json")
    _ = guard.publish_bytes(amendment, "inputs", "amendment.json")
    arms, seeds, checkpoints = _registered_schedule(profile)
    representation = D3Representation.for_arm(D3PolicyArmId.TOP5_CONTEXT_4X)
    rows: list[D5RCheckpointRow] = []
    outcomes: list[D5RCapacityOutcome] = []
    for reward_arm in arms:
        for seed in seeds:
            fit_episodes = (
                source.episodes
                if reward_arm == "NATIVE"
                else shuffled_d3_episodes(source.episodes, seed=seed)
            )
            lineage = start_d5r_lineage(
                fit_episodes,
                representation=representation,
                seed=seed,
                cost_bp=23,
            )
            for checkpoint in checkpoints:
                lineage = advance_d5r_lineage(lineage, target_steps=checkpoint)
                policy = D4PlainPolicy(lineage.model)
                fit_metrics, fit_events = evaluate_d3_model(
                    policy,
                    fit_episodes,
                    representation=representation,
                    seed=seed,
                    cost_bp=23,
                )
                native_metrics, native_events = evaluate_d3_model(
                    policy,
                    source.episodes,
                    representation=representation,
                    seed=seed,
                    cost_bp=23,
                )
                zero_metrics, zero_events = evaluate_d3_model(
                    policy,
                    source.episodes,
                    representation=representation,
                    seed=seed,
                    cost_bp=0,
                )
                row = D5RCheckpointRow(
                    reward_arm,
                    seed,
                    checkpoint,
                    fit_metrics,
                    native_metrics,
                    zero_metrics,
                )
                rows.append(row)
                outcomes.append(D5RCapacityOutcome(reward_arm, seed, checkpoint, native_metrics))
                with guard.locked_parent(
                    "models",
                    reward_arm,
                    f"seed-{seed}",
                    f"steps-{checkpoint}",
                    exclusive_leaf=True,
                ) as model_dir:
                    lineage.model.save(model_dir / "model")
                _ = guard.publish_bytes(
                    canonical_json_bytes(
                        {
                            **asdict(row),
                            "events": {
                                "fit_23bp": fit_events,
                                "native_23bp": native_events,
                                "native_0bp": zero_events,
                            },
                        }
                    ),
                    "outcomes",
                    reward_arm,
                    f"seed-{seed}",
                    f"steps-{checkpoint}.json",
                )
    gate = _capacity_gate(source, tuple(outcomes)) if profile is D5RCapacityProfile.PRIMARY else None
    return _finish_capacity_run(
        guard,
        source,
        profile,
        tuple(rows),
        gate,
        approved_name,
        approval_key,
    )


def _registered_schedule(
    profile: D5RCapacityProfile,
) -> tuple[tuple[str, ...], tuple[int, ...], tuple[int, ...]]:
    match profile:
        case D5RCapacityProfile.SMOKE:
            return ("NATIVE", "SHUFFLED"), (0,), (2048,)
        case D5RCapacityProfile.PRIMARY:
            return ("NATIVE", "SHUFFLED"), (0, 1, 2), (400_000, 800_000)


def _require_capacity_study(source: D5RSourceBundle) -> None:
    native = tuple(
        diagnose_d5r_unit(source.episodes, unit.events, cost_bp=23)
        for unit in source.units
        if unit.reward_arm == "NATIVE"
    )
    if median(row.near_optimal_25bp for row in native) >= 0.85 and median(
        row.median_regret_bp for row in native
    ) <= 25:
        raise ValueError("D5R preregistration does not permit capacity execution")


def _capacity_gate(
    source: D5RSourceBundle,
    outcomes: tuple[D5RCapacityOutcome, ...],
) -> D5RCapacityGate:
    baselines = tuple(
        D5RBaseline(unit.seed, unit.baseline_accuracy, unit.baseline_reward_ratio)
        for unit in source.units
        if unit.reward_arm == "NATIVE" and unit.seed in {0, 1, 2}
    )
    return evaluate_d5r_capacity_gate(outcomes, baselines)


def _finish_capacity_run(
    guard: RunDirectoryGuard,
    source: D5RSourceBundle,
    profile: D5RCapacityProfile,
    rows: tuple[D5RCheckpointRow, ...],
    gate: D5RCapacityGate | None,
    approved_smoke: str | None,
    approval_key: bytes | None,
) -> Path:
    verdict = "D5R_SMOKE_COMPLETE" if gate is None else gate.verdict
    summary = {
        "schema_version": "kronos.rl-discovery.d5r.capacity.v1",
        "profile": profile.value,
        "status": "COMPLETE",
        "verdict": verdict,
        "gate": None if gate is None else asdict(gate),
        "models": [asdict(row) for row in rows],
        "source_run": source.prereg.source_run.run_name,
        "approved_smoke": approved_smoke,
        "d5_verdict_unchanged": "D5_FULL_TRAIN_COST_NOT_CONFIRMED",
        "reused_validation": "NOT_RUN_NO_READ",
        "fresh_oos": "NOT_RUN_NO_READ",
        "promotion_allowed": False,
        "profitability_claim_allowed": False,
        "live_broker_order_allowed": False,
    }
    _ = guard.publish_bytes(canonical_json_bytes(summary), "summary.json")
    with guard.locked() as locked_dir:
        digest = artifact_manifest_sha256(
            locked_dir,
            excluded_relative_paths=frozenset({"terminal_receipt.json"}),
        )
    receipt = {
        "schema_version": "kronos.rl-discovery.d5r.receipt.v1",
        "profile": profile.value,
        "status": "COMPLETE",
        "verdict": verdict,
        "artifact_manifest_sha256": digest,
        "fresh_oos": "NOT_RUN_NO_READ",
        "live_broker_order_allowed": False,
    }
    if profile is D5RCapacityProfile.PRIMARY and approved_smoke is not None and approval_key is not None:
        receipt["primary_custody_hmac_sha256"] = primary_custody_signature(
            approval_key,
            run_name=guard.run_dir.name,
            prereg_sha=source.prereg_sha256,
            episode_sha=source.prereg.source_run.episode_snapshot_sha256,
            manifest_sha=digest,
            approved_smoke=approved_smoke,
        )
    _ = guard.publish_bytes(canonical_json_bytes(receipt), "terminal_receipt.json")
    return guard.verify()
