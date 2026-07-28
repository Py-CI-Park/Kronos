"""Fail-closed approval of one digest-bound D1 Smoke run."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from stom_rl.rl_discovery.d1_contract import load_d1_prereg_bytes
from stom_rl.rl_discovery.d1_gates import evaluate_d1_gate
from stom_rl.rl_discovery.d1_lifecycle import D1Lifecycle, D1LifecycleError
from stom_rl.rl_discovery.gates import RunProfile
from stom_rl.rl_discovery.storage import (
    artifact_manifest_sha256,
    contained_path,
    validate_run_directory,
)


class D1SmokeBoundary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")

    experiment_id: Literal["TYPE2-D1-REWARD-ACTION"]
    profile: Literal["SMOKE"]
    status: Literal["SMOKE_COMPLETE"]
    verdict: Literal["SMOKE_INCOMPLETE"]
    d1_smoke_pass: Literal[True]
    promotion_allowed: Literal[False]
    profitability_claim_allowed: Literal[False]
    fresh_oos: Literal["NOT_RUN_NO_READ"]
    prereg_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fixture_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    primary_round_trip_cost_bp: Literal[23]


class D1SmokeApproval(D1SmokeBoundary):
    artifact_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class D1SmokeModelRow(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")

    algorithm: str
    seed: int = Field(ge=0)
    training_timesteps: int = Field(gt=0)
    oracle_reward_ratio: float
    exact_basket_accuracy: float = Field(ge=0, le=1)
    dominant_action_rate: float = Field(ge=0, le=1)
    invalid_action_count: int = Field(ge=0)
    block_count: int = Field(ge=0)
    no_fill_count: int = Field(ge=0)


class D1SmokeEnvelope(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")

    summary: D1SmokeBoundary
    models: tuple[D1SmokeModelRow, ...]


def approved_smoke_reference(
    *,
    profile: RunProfile,
    approved_smoke: Path | None,
    prereg_sha: str,
    fixture_sha: str,
    run_root: Path,
) -> str | None:
    """Return a trusted direct-child Smoke name or reject Primary execution."""

    if profile is RunProfile.SMOKE:
        return None
    if approved_smoke is None:
        raise PermissionError("D1 Primary requires an approved Smoke receipt")
    smoke_dir = validate_run_directory(run_root, approved_smoke)
    approval = D1SmokeApproval.model_validate_json(
        contained_path(smoke_dir, "terminal_receipt.json").read_text(encoding="utf-8")
    )
    if approval.prereg_sha256 != prereg_sha or approval.fixture_sha256 != fixture_sha:
        raise PermissionError("D1 Primary input identity differs from approved Smoke")
    envelope = D1SmokeEnvelope.model_validate_json(
        contained_path(smoke_dir, "sb3_smoke_summary.json").read_text(encoding="utf-8")
    )
    if envelope.summary.model_dump() != approval.model_dump(
        exclude={"artifact_manifest_sha256"}
    ):
        raise PermissionError("D1 Smoke summary differs from its terminal receipt")
    prereg = load_d1_prereg_bytes(
        contained_path(smoke_dir, "inputs", "prereg.json").read_bytes()
    )
    expected_units = {(contract.id.value, 0) for contract in prereg.arms}
    observed_units = {(row.algorithm, row.seed) for row in envelope.models}
    if observed_units != expected_units or len(envelope.models) != len(expected_units):
        raise PermissionError("D1 Smoke unit matrix is incomplete or duplicated")
    try:
        lifecycle = D1Lifecycle.verify_terminal(
            run_root,
            smoke_dir,
            profile=RunProfile.SMOKE,
            prereg_sha256=prereg_sha,
            fixture_sha256=fixture_sha,
            expected_runs=tuple(D1Lifecycle.key(contract.id, 0) for contract in prereg.arms),
        )
    except D1LifecycleError as exc:
        raise PermissionError("D1 Smoke lifecycle or artifact manifest is invalid") from exc
    outcomes = lifecycle.outcomes
    gate = evaluate_d1_gate(outcomes, profile=RunProfile.SMOKE, thresholds=prereg.gate)
    if not gate.smoke_pass or gate.status != approval.status or gate.verdict != approval.verdict:
        raise PermissionError("D1 Smoke gate cannot be reproduced from lifecycle outcomes")
    outcome_rows = {
        (
            outcome.arm.value,
            outcome.seed,
            outcome.training_timesteps,
            outcome.economic_reward_ratio,
            outcome.initial_decision_accuracy,
            outcome.dominant_initial_action_rate,
            outcome.invalid_action_count,
            outcome.block_count,
            outcome.no_fill_count,
        )
        for outcome in outcomes
    }
    dashboard_rows = {
        (
            row.algorithm,
            row.seed,
            row.training_timesteps,
            row.oracle_reward_ratio,
            row.exact_basket_accuracy,
            row.dominant_action_rate,
            row.invalid_action_count,
            row.block_count,
            row.no_fill_count,
        )
        for row in envelope.models
    }
    if dashboard_rows != outcome_rows:
        raise PermissionError("D1 Smoke dashboard metrics differ from lifecycle outcomes")
    for arm, seed in expected_units:
        required = (
            contained_path(smoke_dir, "models", arm, f"seed-{seed}", "model.zip"),
            contained_path(smoke_dir, "models", arm, f"seed-{seed}", "normalizer.pkl"),
            contained_path(smoke_dir, "outcomes", arm, f"seed-{seed}.json"),
        )
        if not all(path.is_file() for path in required):
            raise PermissionError("D1 Smoke artifact bundle is incomplete")
    observed_digest = artifact_manifest_sha256(
        smoke_dir,
        excluded_relative_paths=frozenset({"terminal_receipt.json"}),
    )
    if observed_digest != approval.artifact_manifest_sha256:
        raise PermissionError("D1 Smoke artifact manifest differs from its receipt")
    return smoke_dir.name
