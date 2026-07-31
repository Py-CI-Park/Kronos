"""Smoke evidence approval boundary for D6R Primary."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from stom_rl.rl_discovery.d2_custody import held_bytes
from stom_rl.rl_discovery.storage import (
    artifact_manifest_sha256,
    validate_run_directory,
)


class D6RApprovalError(ValueError):
    """The supplied D6R Smoke cannot authorize Primary execution."""


class _FrozenEvidence(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore", strict=True)


class _SmokeCommon(_FrozenEvidence):
    profile: Literal["SMOKE"]
    status: Literal["COMPLETE"]
    verdict: Literal["D6R_SMOKE_COMPLETE"]
    prereg_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    unit_count: Literal[4]
    invalid_action_count: Literal[0]
    fresh_oos: Literal["NOT_RUN_NO_READ"]


class _SmokeSummary(_SmokeCommon):
    schema_version: Literal["kronos.rl-discovery.d6r.falsification.v1"]


class _SmokeReceipt(_SmokeCommon):
    schema_version: Literal["kronos.rl-discovery.d6r.receipt.v1"]
    artifact_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def approve_d6r_smoke(
    smoke_run: Path,
    *,
    run_root: Path,
    prereg_sha256: str,
) -> str:
    candidate = validate_run_directory(run_root, smoke_run)
    try:
        summary = _SmokeSummary.model_validate_json(
            held_bytes(candidate / "summary.json", anchor=run_root)
        )
        receipt = _SmokeReceipt.model_validate_json(
            held_bytes(candidate / "terminal_receipt.json", anchor=run_root)
        )
    except ValidationError as exc:
        raise D6RApprovalError("D6R Smoke evidence schema is invalid") from exc
    manifest = artifact_manifest_sha256(
        candidate,
        excluded_relative_paths=frozenset({"terminal_receipt.json"}),
    )
    if (
        summary.prereg_sha256 != prereg_sha256
        or receipt.prereg_sha256 != prereg_sha256
        or receipt.artifact_manifest_sha256 != manifest
    ):
        raise D6RApprovalError("D6R Smoke custody is mismatched")
    return candidate.name
