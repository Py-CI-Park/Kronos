"""Authenticated held-snapshot approval for D4 Smoke evidence."""

from __future__ import annotations

import hmac
from pathlib import Path
from pydantic import TypeAdapter

from stom_rl.rl_discovery.d2_custody import assert_plain_path
from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d3_approval import smoke_approval_signature
from stom_rl.rl_discovery.d4_contract import D4AlgorithmArmId, D4RewardArmId
from stom_rl.rl_discovery.evidence_snapshot import read_evidence_snapshot
from stom_rl.rl_discovery.storage import atomic_write_bytes, contained_path

_JSON_OBJECT = TypeAdapter(dict[str, object])
_JSON_ROWS = TypeAdapter(list[dict[str, object]])


def create_d4_smoke_approval(path: Path, *, run_root: Path, approval_key: bytes) -> Path:
    """Sign a completed Smoke in a separate operator action."""

    if len(approval_key) < 32:
        raise PermissionError("D4 Smoke approval requires a 32-byte operator key")
    root = path.absolute()
    configured_root = run_root.absolute()
    if root.parent != configured_root:
        raise PermissionError("D4 Smoke must be a direct run-root child")
    snapshot = read_evidence_snapshot(
        root,
        capture_paths=frozenset({"summary.json", "terminal_receipt.json"}),
        excluded_manifest_paths=frozenset({"terminal_receipt.json", "operator_approval.json"}),
    )
    summary = _json_object(snapshot.captured["summary.json"])
    receipt = _json_object(snapshot.captured["terminal_receipt.json"])
    if summary.get("verdict") != "SMOKE_COMPLETE" or receipt.get("status") != "COMPLETE":
        raise PermissionError("only a completed D4 Smoke can be approved")
    approval = {
        "kind": "D4_SMOKE_OPERATOR_APPROVAL_V1",
        "run_name": root.name,
        "prereg_sha256": summary.get("prereg_sha256"),
        "episode_snapshot_sha256": summary.get("episode_snapshot_sha256"),
        "artifact_manifest_sha256": snapshot.manifest_sha256,
    }
    approval["approval_hmac_sha256"] = smoke_approval_signature(
        approval_key,
        run_name=root.name,
        prereg_sha=str(approval["prereg_sha256"]),
        episode_sha=str(approval["episode_snapshot_sha256"]),
        manifest_sha=snapshot.manifest_sha256,
    )
    target = contained_path(root, "operator_approval.json")
    atomic_write_bytes(target, canonical_json_bytes(approval))
    return target


def primary_custody_signature(
    key: bytes, *, run_name: str, prereg_sha: str, episode_sha: str,
    manifest_sha: str, approved_smoke: str,
) -> str:
    """Return a domain-separated Primary custody signature."""

    payload = "\0".join(("D4_PRIMARY_CUSTODY_V1", run_name, prereg_sha, episode_sha, manifest_sha, approved_smoke))
    return hmac.new(key, payload.encode("utf-8"), "sha256").hexdigest()


def _json_object(raw: bytes) -> dict[str, object]:
    return _JSON_OBJECT.validate_json(raw)


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
    _ = assert_plain_path(root, anchor=configured_root, require_file=False)
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
            excluded_manifest_paths=frozenset({"terminal_receipt.json", "operator_approval.json"}),
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise PermissionError("approved D4 Smoke snapshot is incomplete or unsafe") from exc
    summary = _json_object(snapshot.captured["summary.json"])
    receipt = _json_object(snapshot.captured["terminal_receipt.json"])
    approval_path = contained_path(root, "operator_approval.json")
    try:
        approval = _json_object(approval_path.read_bytes())
    except (OSError, ValueError) as exc:
        raise PermissionError("approved D4 Smoke lacks detached operator approval") from exc
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
    if (
        approval.get("kind") != "D4_SMOKE_OPERATOR_APPROVAL_V1"
        or approval.get("run_name") != root.name
        or approval.get("artifact_manifest_sha256") != snapshot.manifest_sha256
        or not hmac.compare_digest(str(approval.get("approval_hmac_sha256", "")), signature)
    ):
        raise PermissionError("approved D4 Smoke lacks operator authentication")
    try:
        models = _JSON_ROWS.validate_python(summary.get("models"))
    except ValueError:
        raise PermissionError("approved D4 Smoke models must be a list")

    observed = {
        (item.get("algorithm_arm"), item.get("reward_arm"), item.get("seed"))
        for item in models
    }
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
            _json_object(snapshot.captured[path]).get("algorithm_arm"),
            _json_object(snapshot.captured[path]).get("reward_arm"),
            _json_object(snapshot.captured[path]).get("seed"),
        )
        for path in outcome_paths
    }
    if outcome_units != expected:
        raise PermissionError("approved D4 Smoke outcome identities are mismatched")
    return root.name
