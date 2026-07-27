"""Dashboard and receipt serialization for discovery lifecycle state."""

from __future__ import annotations

from pathlib import Path

from stom_rl.rl_discovery.gates import ArmOutcome, GateResult
from stom_rl.rl_discovery.lifecycle_schema import LifecycleState, outcome_payload
from stom_rl.rl_discovery.storage import JsonValue, atomic_write_json, contained_path


def write_dashboard(
    run_dir: Path,
    state: LifecycleState,
    outcomes: tuple[ArmOutcome, ...],
    gate: GateResult | None,
) -> None:
    """Write dashboard-compatible aggregate evidence before the commit marker."""

    summary: dict[str, JsonValue] = {
        "research_lane": "rl_discovery",
        "experiment_id": state.experiment_id,
        "profile": state.profile.value,
        "status": state.status.value,
        "verdict": gate.verdict if gate else "RUNNING_NOT_EVALUATED",
        "reasons": list(gate.reasons) if gate else ["run is incomplete"],
        "fresh_oos": gate.fresh_oos if gate else "NOT_RUN_NO_READ",
        "type1_outcome": "COMPLETE_NO_GO",
        "promotion_allowed": gate.promotion_allowed if gate else False,
        "profitability_claim_allowed": gate.profitability_claim_allowed if gate else False,
        "prereg_sha256": state.prereg_sha256,
        "fixture_sha256": state.fixture_sha256,
        "completed_run_count": len(state.completed_runs),
        "expected_run_count": len(state.expected_runs),
        "arm_count": len({outcome.arm for outcome in outcomes}),
        "seed_count": len({outcome.seed for outcome in outcomes}),
    }
    models: list[JsonValue] = [outcome_payload(outcome) for outcome in outcomes]
    atomic_write_json(
        contained_path(run_dir, "sb3_smoke_summary.json"),
        {"summary": summary, "models": models},
    )
    atomic_write_json(contained_path(run_dir, "outcomes.json"), models)


def state_payload(state: LifecycleState) -> dict[str, JsonValue]:
    """Serialize lifecycle state with explicit trusted fields."""

    return {
        "schema_version": state.schema_version,
        "experiment_id": state.experiment_id,
        "profile": state.profile.value,
        "prereg_sha256": state.prereg_sha256,
        "fixture_sha256": state.fixture_sha256,
        "status": state.status.value,
        "expected_runs": list(state.expected_runs),
        "completed_runs": list(state.completed_runs),
        "unit_manifests": [item.model_dump(mode="json") for item in state.unit_manifests],
    }


def receipt_payload(state: LifecycleState, gate: GateResult) -> dict[str, JsonValue]:
    """Serialize the append-only terminal commit marker."""

    return {
        "experiment_id": state.experiment_id,
        "profile": state.profile.value,
        "status": gate.status,
        "verdict": gate.verdict,
        "promotion_allowed": gate.promotion_allowed,
        "profitability_claim_allowed": gate.profitability_claim_allowed,
        "fresh_oos": gate.fresh_oos,
        "prereg_sha256": state.prereg_sha256,
        "fixture_sha256": state.fixture_sha256,
    }
