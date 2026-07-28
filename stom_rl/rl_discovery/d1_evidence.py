"""Terminal and per-unit evidence publication for Type2-D1."""

from __future__ import annotations

from pathlib import Path

from stom_rl.rl_discovery.d1_contract import D1Preregistration
from stom_rl.rl_discovery.d1_gates import D1GateResult, D1Outcome
from stom_rl.rl_discovery.gates import RunProfile
from stom_rl.rl_discovery.storage import (
    JsonValue,
    artifact_manifest_sha256,
    atomic_write_json,
    contained_path,
)


def write_d1_unit(
    run_dir: Path,
    *,
    outcome: D1Outcome,
    events: tuple[dict[str, JsonValue], ...],
) -> None:
    """Persist one evaluated arm/seed unit before terminal publication."""

    arm = outcome.arm.value
    seed = outcome.seed
    atomic_write_json(
        contained_path(run_dir, "outcomes", arm, f"seed-{seed}.json"),
        outcome_payload(outcome),
    )
    atomic_write_json(
        contained_path(run_dir, "events", arm, f"seed-{seed}.json"),
        list(events),
    )


def outcome_payload(outcome: D1Outcome) -> dict[str, JsonValue]:
    """Return the canonical D1 outcome payload."""

    return {
        "arm": outcome.arm.value,
        "seed": outcome.seed,
        "training_timesteps": outcome.training_timesteps,
        "economic_reward_ratio": outcome.economic_reward_ratio,
        "initial_decision_accuracy": outcome.initial_decision_accuracy,
        "invalid_action_count": outcome.invalid_action_count,
        "block_count": outcome.block_count,
        "no_fill_count": outcome.no_fill_count,
        "dominant_initial_action_rate": outcome.dominant_initial_action_rate,
    }


def write_d1_terminal(
    run_dir: Path,
    *,
    prereg: D1Preregistration,
    profile: RunProfile,
    outcomes: tuple[D1Outcome, ...],
    gate: D1GateResult,
    prereg_sha: str,
    fixture_sha: str,
    smoke_reference: str | None,
) -> None:
    """Publish dashboard summary followed by the terminal commit receipt."""

    models: list[JsonValue] = [
        {
            "model": f"{outcome.arm.value}/seed-{outcome.seed}",
            "algorithm": outcome.arm.value,
            "seed": outcome.seed,
            "training_timesteps": outcome.training_timesteps,
            "oracle_reward_ratio": outcome.economic_reward_ratio,
            "exact_basket_accuracy": outcome.initial_decision_accuracy,
            "invalid_action_count": outcome.invalid_action_count,
            "block_count": outcome.block_count,
            "no_fill_count": outcome.no_fill_count,
            "dominant_action_rate": outcome.dominant_initial_action_rate,
            "shuffled_reward": outcome.arm.value.endswith("SHUFFLED"),
        }
        for outcome in outcomes
    ]
    summary: dict[str, JsonValue] = {
        "research_lane": "rl_discovery",
        "experiment_id": prereg.experiment_id,
        "profile": profile.value,
        "status": gate.status,
        "verdict": gate.verdict,
        "reasons": list(gate.reasons),
        "d1_smoke_pass": gate.smoke_pass,
        "fresh_oos": gate.fresh_oos,
        "type1_outcome": "COMPLETE_NO_GO",
        "primary_round_trip_cost_bp": prereg.primary_round_trip_cost_bp,
        "promotion_allowed": gate.promotion_allowed,
        "profitability_claim_allowed": gate.profitability_claim_allowed,
        "prereg_sha256": prereg_sha,
        "fixture_sha256": fixture_sha,
        "approved_smoke_run": smoke_reference,
        "arm_count": len({outcome.arm for outcome in outcomes}),
        "seed_count": len({outcome.seed for outcome in outcomes}),
    }
    atomic_write_json(
        contained_path(run_dir, "sb3_smoke_summary.json"),
        {"summary": summary, "models": models},
    )
    atomic_write_json(contained_path(run_dir, "outcomes.json"), models)
    approval_digest = artifact_manifest_sha256(
        run_dir,
        excluded_relative_paths=frozenset({"terminal_receipt.json"}),
    )
    atomic_write_json(
        contained_path(run_dir, "terminal_receipt.json"),
        {
            "experiment_id": prereg.experiment_id,
            "profile": profile.value,
            "status": gate.status,
            "verdict": gate.verdict,
            "d1_smoke_pass": gate.smoke_pass,
            "promotion_allowed": gate.promotion_allowed,
            "profitability_claim_allowed": gate.profitability_claim_allowed,
            "fresh_oos": gate.fresh_oos,
            "prereg_sha256": prereg_sha,
            "fixture_sha256": fixture_sha,
            "primary_round_trip_cost_bp": prereg.primary_round_trip_cost_bp,
            "artifact_manifest_sha256": approval_digest,
        },
    )
