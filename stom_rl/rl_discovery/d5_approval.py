"""Authenticated held-snapshot approval for D5 Smoke evidence."""

from __future__ import annotations

import hmac
from collections.abc import Mapping
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d2_custody import assert_plain_path
from stom_rl.rl_discovery.d3_approval import smoke_approval_signature
from stom_rl.rl_discovery.d4_contract import D4RewardArmId
from stom_rl.rl_discovery.evidence_snapshot import (
    EvidenceSnapshot,
    read_evidence_snapshot,
)
from stom_rl.rl_discovery.storage import RunDirectoryGuard, contained_path


class _EvidenceModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")


class _ModelIdentity(_EvidenceModel):
    algorithm_arm: Literal["C_DQN_DISCRETE"]
    reward_arm: D4RewardArmId
    seed: Literal[0]


class _SmokeSummary(_EvidenceModel):
    schema_version: Literal["kronos.rl-discovery.d5.result.v1"]
    profile: Literal["SMOKE"]
    status: Literal["COMPLETE"]
    verdict: Literal["SMOKE_COMPLETE"]
    prereg_sha256: str
    episode_snapshot_sha256: str
    models: tuple[_ModelIdentity, ...]


class _TerminalReceipt(_EvidenceModel):
    profile: Literal["SMOKE"]
    status: Literal["COMPLETE"]
    verdict: Literal["SMOKE_COMPLETE"]
    prereg_sha256: str
    episode_snapshot_sha256: str
    artifact_manifest_sha256: str
    fresh_oos: Literal["NOT_RUN_NO_READ"]


class _OperatorApproval(_EvidenceModel):
    kind: Literal["D5_SMOKE_OPERATOR_APPROVAL_V1"]
    run_name: str
    prereg_sha256: str
    episode_snapshot_sha256: str
    artifact_manifest_sha256: str
    approval_hmac_sha256: str


def create_d5_smoke_approval(
    path: Path, *, run_root: Path, approval_key: bytes
) -> Path:
    """Sign a complete exact D5 Smoke in a separate operator action."""

    if len(approval_key) < 32:
        raise PermissionError("D5 Smoke approval requires a 32-byte operator key")
    guard = _direct_run_guard(path, run_root)
    root = guard.verify()
    snapshot = _smoke_snapshot(root)
    summary = _SmokeSummary.model_validate_json(snapshot.captured["summary.json"])
    receipt = _TerminalReceipt.model_validate_json(
        snapshot.captured["terminal_receipt.json"]
    )
    _verify_summary_and_receipt(summary, receipt, snapshot.manifest_sha256)
    approval = {
        "kind": "D5_SMOKE_OPERATOR_APPROVAL_V1",
        "run_name": root.name,
        "prereg_sha256": summary.prereg_sha256,
        "episode_snapshot_sha256": summary.episode_snapshot_sha256,
        "artifact_manifest_sha256": snapshot.manifest_sha256,
        "approval_hmac_sha256": smoke_approval_signature(
            approval_key,
            run_name=root.name,
            prereg_sha=summary.prereg_sha256,
            episode_sha=summary.episode_snapshot_sha256,
            manifest_sha=snapshot.manifest_sha256,
        ),
    }
    return guard.publish_bytes(canonical_json_bytes(approval), "operator_approval.json")


def approve_d5_smoke(
    path: Path | None,
    *,
    run_root: Path,
    prereg_sha: str,
    episode_sha: str,
    approval_key: bytes | None,
) -> str:
    """Approve only an authenticated exact two-unit D5 Smoke matrix."""

    if path is None:
        raise PermissionError("D5 Primary requires an approved Smoke")
    if approval_key is None or len(approval_key) < 32:
        raise PermissionError("D5 Primary requires a 32-byte operator approval key")
    guard = _direct_run_guard(path, run_root)
    root = guard.verify()
    try:
        snapshot = _smoke_snapshot(root)
        summary = _SmokeSummary.model_validate_json(snapshot.captured["summary.json"])
        receipt = _TerminalReceipt.model_validate_json(
            snapshot.captured["terminal_receipt.json"]
        )
        approval = _OperatorApproval.model_validate_json(
            contained_path(root, "operator_approval.json").read_bytes()
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise PermissionError(
            "approved D5 Smoke lacks detached operator approval"
        ) from exc
    _verify_summary_and_receipt(summary, receipt, snapshot.manifest_sha256)
    _ = guard.verify()
    if (
        summary.prereg_sha256 != prereg_sha
        or summary.episode_snapshot_sha256 != episode_sha
    ):
        raise PermissionError("approved D5 Smoke input identity is mismatched")
    expected_signature = smoke_approval_signature(
        approval_key,
        run_name=root.name,
        prereg_sha=prereg_sha,
        episode_sha=episode_sha,
        manifest_sha=snapshot.manifest_sha256,
    )
    if (
        approval.run_name != root.name
        or approval.prereg_sha256 != prereg_sha
        or approval.episode_snapshot_sha256 != episode_sha
        or approval.artifact_manifest_sha256 != snapshot.manifest_sha256
        or not hmac.compare_digest(approval.approval_hmac_sha256, expected_signature)
    ):
        raise PermissionError("approved D5 Smoke lacks operator authentication")
    _verify_artifacts(snapshot.relative_paths, summary.models, snapshot.captured)
    return root.name


def primary_custody_signature(
    key: bytes,
    *,
    run_name: str,
    prereg_sha: str,
    episode_sha: str,
    manifest_sha: str,
    approved_smoke: str,
) -> str:
    """Return a domain-separated D5 Primary custody signature."""

    payload = "\0".join(
        (
            "D5_PRIMARY_CUSTODY_V1",
            run_name,
            prereg_sha,
            episode_sha,
            manifest_sha,
            approved_smoke,
        )
    )
    return hmac.new(key, payload.encode(), "sha256").hexdigest()


def _direct_run_guard(path: Path, run_root: Path) -> RunDirectoryGuard:
    root = path.absolute()
    configured = run_root.absolute()
    if root.parent != configured:
        raise PermissionError("D5 Smoke must be a direct run-root child")
    _ = assert_plain_path(root, anchor=configured, require_file=False)
    return RunDirectoryGuard.capture(configured, root)


def _smoke_snapshot(root: Path) -> EvidenceSnapshot:
    outcomes = frozenset(
        f"outcomes/{reward.value}/seed-0.json" for reward in D4RewardArmId
    )
    return read_evidence_snapshot(
        root,
        capture_paths=frozenset({"summary.json", "terminal_receipt.json"}) | outcomes,
        excluded_manifest_paths=frozenset(
            {"terminal_receipt.json", "operator_approval.json"}
        ),
    )


def _verify_summary_and_receipt(
    summary: _SmokeSummary,
    receipt: _TerminalReceipt,
    manifest_sha256: str,
) -> None:
    expected = {(reward, 0) for reward in D4RewardArmId}
    observed = {(model.reward_arm, model.seed) for model in summary.models}
    if len(summary.models) != 2 or observed != expected:
        raise PermissionError(
            "approved D5 Smoke does not match the exact two-unit matrix"
        )
    if (
        receipt.prereg_sha256 != summary.prereg_sha256
        or receipt.episode_snapshot_sha256 != summary.episode_snapshot_sha256
        or receipt.artifact_manifest_sha256 != manifest_sha256
    ):
        raise PermissionError("approved D5 Smoke receipt is mismatched")


def _verify_artifacts(
    relative_paths: frozenset[str],
    models: tuple[_ModelIdentity, ...],
    captured: Mapping[str, bytes],
) -> None:
    required = frozenset(
        f"models/C_DQN_DISCRETE__{reward.value}/seed-0/model.zip"
        for reward in D4RewardArmId
    )
    if not required <= relative_paths:
        raise PermissionError("approved D5 Smoke is missing model artifacts")
    for model in models:
        relative = f"outcomes/{model.reward_arm.value}/seed-0.json"
        outcome = _ModelIdentity.model_validate_json(captured[relative])
        if outcome != model:
            raise PermissionError("approved D5 Smoke outcome identity is mismatched")
