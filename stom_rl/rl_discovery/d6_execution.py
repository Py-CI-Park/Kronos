"""Frozen-model D6 reused-validation execution and evidence publication."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d3_contract import D3PolicyArmId
from stom_rl.rl_discovery.d3_env import D3Representation
from stom_rl.rl_discovery.d3_training import D3Metrics, evaluate_d3_model
from stom_rl.rl_discovery.d6_evaluation import (
    D6RewardEvent,
    maximum_cumulative_reward_drawdown,
    parse_d6_events,
)
from stom_rl.rl_discovery.d6_gate import (
    D6Evaluation,
    D6GateResult,
    D6GateThresholds,
    evaluate_d6_gate,
)
from stom_rl.rl_discovery.d6_policy import load_d6_policy
from stom_rl.rl_discovery.d6_source import D6ModelArtifact, D6SourceBundle, load_d6_source
from stom_rl.rl_discovery.storage import RunDirectoryGuard, artifact_manifest_sha256


@dataclass(frozen=True, slots=True)
class D6EvaluationRow:
    reward_arm: Literal["NATIVE", "SHUFFLED"]
    seed: int
    selected_steps: Literal[100000]
    source_model_sha256: str
    validation_23bp: D3Metrics
    validation_0bp: D3Metrics
    maximum_drawdown_23bp: float


def execute_d6(repo_root: Path, *, guard: RunDirectoryGuard) -> Path:
    source = load_d6_source(repo_root)
    _ = guard.publish_bytes(source.prereg_bytes, "inputs", "prereg.json")
    _ = guard.publish_bytes(source.validation_bytes, "inputs", "validation_episodes.json")
    representation = D3Representation.for_arm(D3PolicyArmId.TOP5_CONTEXT_4X)
    rows: list[D6EvaluationRow] = []
    gate_rows: list[D6Evaluation] = []
    for model in source.models:
        row, events_23bp, events_0bp = _evaluate_model(
            repo_root,
            source,
            model,
            representation,
        )
        rows.append(row)
        gate_rows.append(
            D6Evaluation(
                row.reward_arm,
                row.seed,
                row.validation_23bp,
                row.maximum_drawdown_23bp,
            )
        )
        _ = guard.publish_bytes(
            canonical_json_bytes(
                {
                    **asdict(row),
                    "events": {
                        "validation_23bp": [event.model_dump(mode="json") for event in events_23bp],
                        "validation_0bp": [event.model_dump(mode="json") for event in events_0bp],
                    },
                }
            ),
            "outcomes",
            model.reward_arm,
            f"seed-{model.seed}.json",
        )
    gate = evaluate_d6_gate(
        tuple(gate_rows),
        thresholds=_thresholds(source),
    )
    return _finish_d6(guard, source, tuple(rows), gate)


def _evaluate_model(
    repo_root: Path,
    source: D6SourceBundle,
    model: D6ModelArtifact,
    representation: D3Representation,
) -> tuple[D6EvaluationRow, tuple[D6RewardEvent, ...], tuple[D6RewardEvent, ...]]:
    policy = load_d6_policy(model, repo_root=repo_root)
    metrics_23bp, raw_23bp = evaluate_d3_model(
        policy,
        source.validation_episodes,
        representation=representation,
        seed=model.seed,
        cost_bp=23,
    )
    metrics_0bp, raw_0bp = evaluate_d3_model(
        policy,
        source.validation_episodes,
        representation=representation,
        seed=model.seed,
        cost_bp=0,
    )
    events_23bp = parse_d6_events(raw_23bp)
    events_0bp = parse_d6_events(raw_0bp)
    drawdown = maximum_cumulative_reward_drawdown(tuple(event.reward for event in events_23bp))
    return (
        D6EvaluationRow(
            model.reward_arm,
            model.seed,
            100_000,
            model.sha256,
            metrics_23bp,
            metrics_0bp,
            drawdown,
        ),
        events_23bp,
        events_0bp,
    )


def _thresholds(source: D6SourceBundle) -> D6GateThresholds:
    gate = source.prereg.gate
    return D6GateThresholds(
        gate.minimum_native_median_accuracy,
        gate.minimum_native_median_reward_ratio,
        gate.minimum_native_median_total_reward,
        gate.minimum_native_reward_delta_vs_shuffled,
        gate.minimum_passing_native_seed_fraction,
        gate.maximum_native_median_reward_drawdown,
        gate.zero_invalid_actions,
    )


def _finish_d6(
    guard: RunDirectoryGuard,
    source: D6SourceBundle,
    rows: tuple[D6EvaluationRow, ...],
    gate: D6GateResult,
) -> Path:
    summary = {
        "schema_version": "kronos.rl-discovery.d6.validation.v1",
        "profile": "PRIMARY",
        "status": "COMPLETE",
        "verdict": gate.verdict,
        "gate": asdict(gate),
        "evaluations": [asdict(row) for row in rows],
        "source_run": source.prereg.source_run.run_name,
        "selected_steps": source.prereg.source_run.selected_steps,
        "validation_episode_count": len(source.validation_episodes),
        "validation_episode_sha256": source.validation_sha256,
        "input_hashes": dict(source.input_hashes),
        "reused_validation": "COMPLETE",
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
        "schema_version": "kronos.rl-discovery.d6.receipt.v1",
        "profile": "PRIMARY",
        "status": "COMPLETE",
        "verdict": gate.verdict,
        "artifact_manifest_sha256": digest,
        "validation_episode_sha256": source.validation_sha256,
        "reused_validation": "COMPLETE",
        "fresh_oos": "NOT_RUN_NO_READ",
        "live_broker_order_allowed": False,
    }
    _ = guard.publish_bytes(canonical_json_bytes(receipt), "terminal_receipt.json")
    return guard.verify()
