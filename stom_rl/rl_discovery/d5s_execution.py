"""D5S stability matrix training, evaluation, and success evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d3_contract import D3PolicyArmId
from stom_rl.rl_discovery.d3_env import D3Representation
from stom_rl.rl_discovery.d3_training import (
    D3Metrics,
    evaluate_d3_model,
    shuffled_d3_episodes,
)
from stom_rl.rl_discovery.d4_training import D4PlainPolicy
from stom_rl.rl_discovery.d5_approval import primary_custody_signature
from stom_rl.rl_discovery.d5s_approval import approve_d5s_smoke
from stom_rl.rl_discovery.d5s_gate import (
    D5SCheckpointOutcome,
    D5SStabilityGate,
    evaluate_d5s_stability_gate,
)
from stom_rl.rl_discovery.d5s_source import D5SSourceBundle, load_d5s_source
from stom_rl.rl_discovery.d5s_training import advance_d5s_lineage, start_d5s_lineage
from stom_rl.rl_discovery.storage import RunDirectoryGuard, artifact_manifest_sha256


class D5SProfile(StrEnum):
    SMOKE = "SMOKE"
    PRIMARY = "PRIMARY"


D5SRewardArm = Literal["NATIVE", "SHUFFLED"]


@dataclass(frozen=True, slots=True)
class D5SCheckpointRow:
    reward_arm: D5SRewardArm
    seed: int
    total_steps: int
    fit_23bp: D3Metrics
    native_23bp: D3Metrics
    native_0bp: D3Metrics


def execute_d5s(
    repo_root: Path,
    *,
    guard: RunDirectoryGuard,
    profile: D5SProfile,
    approved_smoke: Path | None,
    approval_key: bytes | None,
) -> Path:
    source = load_d5s_source(repo_root)
    approved_name = (
        approve_d5s_smoke(
            approved_smoke,
            run_root=guard.run_root,
            approval_key=approval_key,
            prereg_sha=source.prereg_sha256,
            episode_sha=source.prereg.source_run.episode_snapshot_sha256,
        )
        if profile is D5SProfile.PRIMARY
        else None
    )
    _ = guard.publish_bytes(source.prereg_bytes, "inputs", "prereg.json")
    arms, seeds, checkpoints = registered_d5s_schedule(profile)
    representation = D3Representation.for_arm(D3PolicyArmId.TOP5_CONTEXT_4X)
    rows: list[D5SCheckpointRow] = []
    outcomes: list[D5SCheckpointOutcome] = []
    for reward_arm in arms:
        for seed in seeds:
            fit_episodes = (
                source.episodes
                if reward_arm == "NATIVE"
                else shuffled_d3_episodes(source.episodes, seed=seed)
            )
            lineage = start_d5s_lineage(
                fit_episodes,
                representation=representation,
                seed=seed,
                cost_bp=23,
            )
            for checkpoint in checkpoints:
                lineage = advance_d5s_lineage(lineage, target_steps=checkpoint)
                policy = D4PlainPolicy(lineage.model)
                fit_metrics, fit_events = evaluate_d3_model(
                    policy, fit_episodes, representation=representation, seed=seed, cost_bp=23
                )
                native_metrics, native_events = evaluate_d3_model(
                    policy, source.episodes, representation=representation, seed=seed, cost_bp=23
                )
                zero_metrics, zero_events = evaluate_d3_model(
                    policy, source.episodes, representation=representation, seed=seed, cost_bp=0
                )
                row = D5SCheckpointRow(
                    reward_arm, seed, checkpoint, fit_metrics, native_metrics, zero_metrics
                )
                rows.append(row)
                outcomes.append(D5SCheckpointOutcome(reward_arm, seed, checkpoint, native_metrics))
                with guard.locked_parent(
                    "models", reward_arm, f"seed-{seed}", f"steps-{checkpoint}", exclusive_leaf=True
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
    gate = (
        evaluate_d5s_stability_gate(tuple(outcomes), source.baselines)
        if profile is D5SProfile.PRIMARY
        else None
    )
    return _finish_d5s(guard, source, profile, tuple(rows), gate, approved_name, approval_key)


def registered_d5s_schedule(
    profile: D5SProfile,
) -> tuple[tuple[D5SRewardArm, ...], tuple[int, ...], tuple[int, ...]]:
    match profile:
        case D5SProfile.SMOKE:
            return ("NATIVE", "SHUFFLED"), (0,), (4096,)
        case D5SProfile.PRIMARY:
            return (
                ("NATIVE", "SHUFFLED"),
                (0, 1, 2),
                (50_000, 100_000, 150_000, 200_000, 300_000, 400_000),
            )


def _finish_d5s(
    guard: RunDirectoryGuard,
    source: D5SSourceBundle,
    profile: D5SProfile,
    rows: tuple[D5SCheckpointRow, ...],
    gate: D5SStabilityGate | None,
    approved_smoke: str | None,
    approval_key: bytes | None,
) -> Path:
    verdict = "D5S_SMOKE_COMPLETE" if gate is None else gate.verdict
    summary = {
        "schema_version": "kronos.rl-discovery.d5s.stability.v1",
        "profile": profile.value,
        "status": "COMPLETE",
        "verdict": verdict,
        "gate": None if gate is None else asdict(gate),
        "models": [asdict(row) for row in rows],
        "source_run": source.prereg.source_run.run_name,
        "approved_smoke": approved_smoke,
        "d5_verdict_unchanged": "D5_FULL_TRAIN_COST_NOT_CONFIRMED",
        "d5r_verdict_unchanged": "D5R_CAPACITY_NOT_CONFIRMED",
        "reused_validation": "NOT_RUN_NO_READ",
        "fresh_oos": "NOT_RUN_NO_READ",
        "promotion_allowed": False,
        "profitability_claim_allowed": False,
        "live_broker_order_allowed": False,
    }
    _ = guard.publish_bytes(canonical_json_bytes(summary), "summary.json")
    with guard.locked() as locked_dir:
        digest = artifact_manifest_sha256(
            locked_dir, excluded_relative_paths=frozenset({"terminal_receipt.json"})
        )
    receipt = {
        "schema_version": "kronos.rl-discovery.d5s.receipt.v1",
        "profile": profile.value,
        "status": "COMPLETE",
        "verdict": verdict,
        "artifact_manifest_sha256": digest,
        "fresh_oos": "NOT_RUN_NO_READ",
        "live_broker_order_allowed": False,
    }
    if profile is D5SProfile.PRIMARY and approved_smoke is not None and approval_key is not None:
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
