"""Fail-closed smoke approval and terminal evidence for D6R2."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d2_custody import held_bytes
from stom_rl.rl_discovery.d6r2_gate import D6R2GateResult
from stom_rl.rl_discovery.d6r2_source import D6R2SourceBundle
from stom_rl.rl_discovery.d6r2_unit import D6R2UnitRow
from stom_rl.rl_discovery.storage import RunDirectoryGuard, artifact_manifest_sha256, validate_run_directory


class D6R2ApprovalError(ValueError):
    """A smoke run cannot authorize D6R2 Primary."""


class _SmokeEvidence(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore", strict=True)

    profile: Literal["SMOKE"]
    status: Literal["COMPLETE"]
    verdict: Literal["D6R2_SMOKE_COMPLETE"]
    prereg_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    unit_count: Literal[6]
    invalid_action_count: Literal[0]
    normalizer_evaluation_row_count: Literal[0]
    fresh_oos: Literal["NOT_RUN_NO_READ"]


class _SmokeReceipt(_SmokeEvidence):
    artifact_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def approve_d6r2_smoke(smoke_run: Path, *, run_root: Path, prereg_sha256: str) -> str:
    candidate = validate_run_directory(run_root, smoke_run)
    try:
        summary = _SmokeEvidence.model_validate_json(held_bytes(candidate / "summary.json", anchor=run_root))
        receipt = _SmokeReceipt.model_validate_json(held_bytes(candidate / "terminal_receipt.json", anchor=run_root))
    except ValidationError as exc:
        raise D6R2ApprovalError("D6R2 Smoke evidence schema is invalid") from exc
    digest = artifact_manifest_sha256(candidate, excluded_relative_paths=frozenset({"terminal_receipt.json"}))
    if summary.prereg_sha256 != prereg_sha256 or receipt.prereg_sha256 != prereg_sha256 or receipt.artifact_manifest_sha256 != digest:
        raise D6R2ApprovalError("D6R2 Smoke custody is mismatched")
    return candidate.name


def finish_d6r2(
    guard: RunDirectoryGuard,
    source: D6R2SourceBundle,
    *,
    profile: str,
    rows: tuple[D6R2UnitRow, ...],
    gate: D6R2GateResult | None,
    approved_smoke: str | None,
) -> Path:
    verdict = "D6R2_SMOKE_COMPLETE" if gate is None else gate.verdict
    invalid = sum(row.evaluation_23bp.invalid_action_count for row in rows)
    eval_normalizer_rows = sum(row.normalizer_evaluation_row_count for row in rows)
    summary = {
        "schema_version": "kronos.rl-discovery.d6r2.falsification.v1",
        "profile": profile,
        "status": "COMPLETE",
        "verdict": verdict,
        "prereg_sha256": source.prereg_sha256,
        "source_episode_sha256": source.raw.episode_identity_sha256,
        "source_episode_count": len(source.raw.sessions),
        "input_hashes": dict(source.raw.input_hashes),
        "unit_count": len(rows),
        "invalid_action_count": invalid,
        "normalizer_evaluation_row_count": eval_normalizer_rows,
        "gate": None if gate is None else asdict(gate),
        "evaluations": [asdict(row) for row in rows],
        "approved_smoke": approved_smoke,
        "training_partition": "TRAIN_ONLY",
        "normalizer": "FOLD_LOCAL_TRAIN_ONLY_TYPE7_MEDIAN_IQR",
        "reused_validation": "NO_READ_ALREADY_CONSUMED_DIAGNOSTIC_ONLY",
        "fresh_oos": "NOT_RUN_NO_READ",
        "d7": "LOCKED",
        "gamma0_is_not_sequential_portfolio_control": True,
        "ridge_is_not_reinforcement_learning": True,
        "candidate_is_not_confirmation": True,
        "promotion_allowed": False,
        "profitability_claim_allowed": False,
        "paper_forward_allowed": False,
        "live_broker_order_allowed": False,
    }
    _ = guard.publish_bytes(canonical_json_bytes(summary), "summary.json")
    with guard.locked() as locked_dir:
        digest = artifact_manifest_sha256(locked_dir, excluded_relative_paths=frozenset({"terminal_receipt.json"}))
    receipt = {
        "schema_version": "kronos.rl-discovery.d6r2.receipt.v1",
        "profile": profile,
        "status": "COMPLETE",
        "verdict": verdict,
        "artifact_manifest_sha256": digest,
        "prereg_sha256": source.prereg_sha256,
        "source_episode_sha256": source.raw.episode_identity_sha256,
        "unit_count": len(rows),
        "invalid_action_count": invalid,
        "normalizer_evaluation_row_count": eval_normalizer_rows,
        "approved_smoke": approved_smoke,
        "fresh_oos": "NOT_RUN_NO_READ",
        "d7": "LOCKED",
        "live_broker_order_allowed": False,
    }
    _ = guard.publish_bytes(canonical_json_bytes(receipt), "terminal_receipt.json")
    return guard.verify()
