"""Authenticated held-snapshot approval for D4 Smoke evidence."""

from __future__ import annotations

import hmac
import json
from pathlib import Path

from stom_rl.rl_discovery.d2_custody import assert_plain_path
from stom_rl.rl_discovery.d3_approval import smoke_approval_signature
from stom_rl.rl_discovery.d4_contract import D4AlgorithmArmId, D4RewardArmId
from stom_rl.rl_discovery.evidence_snapshot import read_evidence_snapshot


def approve_d4_smoke(
    path: Path | None,
    *,
    run_root: Path,
    prereg_sha: str,
    episode_sha: str,
    approval_key: bytes | None,
) -> str:
    """Approve only the authenticated exact eight-unit D4 Smoke matrix."""

    if path is None:
        raise PermissionError("D4 Primary requires an approved Smoke")
    if approval_key is None or len(approval_key) < 32:
        raise PermissionError("D4 Primary requires a 32-byte operator approval key")
    configured_root = run_root.absolute()
    root = path.absolute()
    if root.parent != configured_root:
        raise PermissionError("approved D4 Smoke must be a direct run-root child")
    assert_plain_path(root, anchor=configured_root, require_file=False)
    expected = {
        (algorithm.value, reward.value, 0)
        for algorithm in D4AlgorithmArmId
        for reward in D4RewardArmId
    }
    outcome_paths = frozenset(
        f"outcomes/{algorithm}/{reward}/seed-0.json"
        for algorithm, reward, _seed in expected
    )
    try:
        snapshot = read_evidence_snapshot(
            root,
            capture_paths=frozenset({"summary.json", "terminal_receipt.json"}) | outcome_paths,
            excluded_manifest_paths=frozenset({"terminal_receipt.json"}),
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise PermissionError("approved D4 Smoke snapshot is incomplete or unsafe") from exc
    summary = json.loads(snapshot.captured["summary.json"])
    receipt = json.loads(snapshot.captured["terminal_receipt.json"])
    required_receipt = {
        "profile": "SMOKE",
        "status": "COMPLETE",
        "verdict": "SMOKE_COMPLETE",
        "prereg_sha256": prereg_sha,
        "episode_snapshot_sha256": episode_sha,
        "artifact_manifest_sha256": snapshot.manifest_sha256,
        "fresh_oos": "NOT_RUN_NO_READ",
    }
    if any(receipt.get(key) != value for key, value in required_receipt.items()):
        raise PermissionError("approved D4 Smoke receipt is missing or mismatched")
    signature = smoke_approval_signature(
        approval_key,
        run_name=root.name,
        prereg_sha=prereg_sha,
        episode_sha=episode_sha,
        manifest_sha=snapshot.manifest_sha256,
    )
    if not hmac.compare_digest(str(receipt.get("approval_hmac_sha256", "")), signature):
        raise PermissionError("approved D4 Smoke lacks operator authentication")
    models = summary.get("models")
    observed = {
        (item.get("algorithm_arm"), item.get("reward_arm"), item.get("seed"))
        for item in models
        if isinstance(item, dict)
    } if isinstance(models, list) else set()
    if (
        summary.get("schema_version") != "kronos.rl-discovery.d4.result.v1"
        or summary.get("profile") != "SMOKE"
        or summary.get("status") != "COMPLETE"
        or summary.get("verdict") != "SMOKE_COMPLETE"
        or len(models) != 8
        or observed != expected
    ):
        raise PermissionError("approved D4 Smoke does not match the exact eight-unit matrix")
    required_artifacts = outcome_paths | frozenset(
        f"models/{algorithm}__{reward}/seed-0/model.zip"
        for algorithm, reward, _seed in expected
    )
    if not required_artifacts <= snapshot.relative_paths:
        raise PermissionError("approved D4 Smoke is missing model or outcome artifacts")
    outcome_units = {
        (
            json.loads(snapshot.captured[path]).get("algorithm_arm"),
            json.loads(snapshot.captured[path]).get("reward_arm"),
            json.loads(snapshot.captured[path]).get("seed"),
        )
        for path in outcome_paths
    }
    if outcome_units != expected:
        raise PermissionError("approved D4 Smoke outcome identities are mismatched")
    return root.name
