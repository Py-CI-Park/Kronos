"""Detached HMAC approval for exact D5R Smoke evidence."""

from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d3_approval import smoke_approval_signature
from stom_rl.rl_discovery.d5_approval import primary_custody_signature
from stom_rl.rl_discovery.d5r_contract import load_d5r_prereg_bytes
from stom_rl.rl_discovery.storage import RunDirectoryGuard, artifact_manifest_sha256


class _FrozenBoundary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore", strict=True)


class _SmokeModel(_FrozenBoundary):
    reward_arm: Literal["NATIVE", "SHUFFLED"]
    seed: Literal[0]
    total_steps: Literal[2048]


class _SmokeSummary(_FrozenBoundary):
    schema_version: Literal["kronos.rl-discovery.d5r.capacity.v1"]
    profile: Literal["SMOKE"]
    status: Literal["COMPLETE"]
    verdict: Literal["D5R_SMOKE_COMPLETE"]
    models: tuple[_SmokeModel, ...]


class _SmokeReceipt(_FrozenBoundary):
    profile: Literal["SMOKE"]
    status: Literal["COMPLETE"]
    verdict: Literal["D5R_SMOKE_COMPLETE"]
    artifact_manifest_sha256: str


class _OperatorApproval(_FrozenBoundary):
    kind: Literal["D5R_SMOKE_OPERATOR_APPROVAL_V1"]
    run_name: str
    prereg_sha256: str
    episode_snapshot_sha256: str
    artifact_manifest_sha256: str
    approval_hmac_sha256: str


class D5RApprovalError(PermissionError):
    """D5R Smoke is incomplete, mismatched, or unauthenticated."""


def create_d5r_smoke_approval(path: Path, *, run_root: Path, approval_key: bytes) -> Path:
    if len(approval_key) < 32:
        raise D5RApprovalError("D5R Smoke approval requires a 32-byte key")
    guard = RunDirectoryGuard.capture(run_root, path)
    prereg_sha, episode_sha, manifest_sha = _verified_smoke(guard)
    approval = {
        "kind": "D5R_SMOKE_OPERATOR_APPROVAL_V1",
        "run_name": path.name,
        "prereg_sha256": prereg_sha,
        "episode_snapshot_sha256": episode_sha,
        "artifact_manifest_sha256": manifest_sha,
        "approval_hmac_sha256": smoke_approval_signature(
            approval_key,
            run_name=path.name,
            prereg_sha=prereg_sha,
            episode_sha=episode_sha,
            manifest_sha=manifest_sha,
        ),
    }
    return guard.publish_bytes(canonical_json_bytes(approval), "operator_approval.json")


def approve_d5r_smoke(
    path: Path | None,
    *,
    run_root: Path,
    approval_key: bytes | None,
    prereg_sha: str,
    episode_sha: str,
) -> str:
    if path is None or approval_key is None or len(approval_key) < 32:
        raise D5RApprovalError("D5R Primary requires detached Smoke approval")
    guard = RunDirectoryGuard.capture(run_root, path)
    observed_prereg, observed_episode, manifest_sha = _verified_smoke(guard)
    approval = _OperatorApproval.model_validate_json((path / "operator_approval.json").read_bytes())
    expected = smoke_approval_signature(
        approval_key,
        run_name=path.name,
        prereg_sha=prereg_sha,
        episode_sha=episode_sha,
        manifest_sha=manifest_sha,
    )
    if (
        observed_prereg != prereg_sha
        or observed_episode != episode_sha
        or approval.run_name != path.name
        or approval.prereg_sha256 != prereg_sha
        or approval.episode_snapshot_sha256 != episode_sha
        or approval.artifact_manifest_sha256 != manifest_sha
        or not hmac.compare_digest(approval.approval_hmac_sha256, expected)
    ):
        raise D5RApprovalError("D5R Smoke approval identity is mismatched")
    return path.name


def _verified_smoke(guard: RunDirectoryGuard) -> tuple[str, str, str]:
    root = guard.verify()
    summary = _SmokeSummary.model_validate_json((root / "summary.json").read_bytes())
    receipt = _SmokeReceipt.model_validate_json((root / "terminal_receipt.json").read_bytes())
    if {(row.reward_arm, row.seed, row.total_steps) for row in summary.models} != {
        ("NATIVE", 0, 2048),
        ("SHUFFLED", 0, 2048),
    }:
        raise D5RApprovalError("D5R Smoke requires the exact two-unit matrix")
    expected_files = {
        root / "models" / arm / "seed-0" / "steps-2048" / "model.zip"
        for arm in ("NATIVE", "SHUFFLED")
    } | {
        root / "outcomes" / arm / "seed-0" / "steps-2048.json"
        for arm in ("NATIVE", "SHUFFLED")
    }
    if not all(path.is_file() for path in expected_files):
        raise D5RApprovalError("D5R Smoke model or outcome artifacts are incomplete")
    manifest_sha = artifact_manifest_sha256(
        root,
        excluded_relative_paths=frozenset({"terminal_receipt.json", "operator_approval.json"}),
    )
    if receipt.artifact_manifest_sha256 != manifest_sha:
        raise D5RApprovalError("D5R Smoke artifact manifest is mismatched")
    prereg_bytes = (root / "inputs" / "prereg.json").read_bytes()
    prereg = load_d5r_prereg_bytes(prereg_bytes)
    return hashlib.sha256(prereg_bytes).hexdigest(), prereg.source_run.episode_snapshot_sha256, manifest_sha


__all__ = [
    "approve_d5r_smoke",
    "create_d5r_smoke_approval",
    "primary_custody_signature",
]
