"""Fail-closed discovery evidence verification for the RL dashboard."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import cast

from stom_rl.rl_discovery.d4_approval import primary_custody_signature
from stom_rl.rl_discovery.d4_contract import D4AlgorithmArmId, D4RewardArmId
from stom_rl.rl_discovery.evidence_snapshot import read_evidence_snapshot
from stom_rl.rl_discovery.storage import JsonValue

if __package__:
    from .rl_dashboard_d5 import valid_d5_primary
    from .rl_dashboard_d5r import valid_d5r_primary
    from .rl_dashboard_d5s import valid_d5s_primary
else:  # pragma: no cover - supports direct script-style imports
    from webui.rl_dashboard_d5 import valid_d5_primary
    from webui.rl_dashboard_d5r import valid_d5r_primary
    from webui.rl_dashboard_d5s import valid_d5s_primary


def find_discovery_evidence(
    run_dir: Path,
    artifact_type: str,
) -> tuple[dict[str, JsonValue], dict[str, JsonValue]]:
    """Return compact and detailed discovery data from one verified snapshot."""

    blocked: dict[str, JsonValue] = {
        "research_lane": "rl_discovery",
        "status": "BLOCK",
        "verdict": "NO_GO",
    }
    capture_paths = frozenset({"summary.json", "terminal_receipt.json"})
    if artifact_type == "rl_discovery_d5":
        capture_paths |= frozenset({"inputs/prereg.json"}) | frozenset(
            f"outcomes/{reward.value}/seed-{seed}.json"
            for reward in D4RewardArmId
            for seed in range(5)
        )
    if artifact_type == "rl_discovery_d5r":
        capture_paths |= frozenset({"inputs/prereg.json", "inputs/amendment.json"}) | frozenset(
            f"outcomes/{reward}/seed-{seed}/steps-{steps}.json"
            for reward in ("NATIVE", "SHUFFLED")
            for seed in range(3)
            for steps in (400_000, 800_000)
        )
    if artifact_type == "rl_discovery_d5s":
        capture_paths |= frozenset({"inputs/prereg.json"}) | frozenset(
            f"outcomes/{reward}/seed-{seed}/steps-{steps}.json"
            for reward in ("NATIVE", "SHUFFLED")
            for seed in range(3)
            for steps in (50_000, 100_000, 150_000, 200_000, 300_000, 400_000)
        )
    try:
        snapshot = read_evidence_snapshot(
            run_dir,
            capture_paths=capture_paths,
            excluded_manifest_paths=frozenset({"terminal_receipt.json"}),
        )
        payload_value = cast(
            JsonValue,
            json.loads(snapshot.captured["summary.json"]),
        )
        receipt_value = cast(
            JsonValue,
            json.loads(snapshot.captured["terminal_receipt.json"]),
        )
    except (OSError, ValueError):
        return blocked, {}
    if not isinstance(payload_value, dict) or not isinstance(receipt_value, dict):
        return blocked, {}
    payload = payload_value
    receipt = receipt_value
    expected_schema = {
        "rl_discovery_d2": "kronos.rl-discovery.d2.result.v1",
        "rl_discovery_d3": "kronos.rl-discovery.d3.result.v1",
        "rl_discovery_d4": "kronos.rl-discovery.d4.result.v1",
        "rl_discovery_d5": "kronos.rl-discovery.d5.result.v1",
        "rl_discovery_d5r": "kronos.rl-discovery.d5r.capacity.v1",
        "rl_discovery_d5s": "kronos.rl-discovery.d5s.stability.v1",
    }.get(artifact_type)
    digest = snapshot.manifest_sha256
    source_identity_in_receipt = artifact_type not in {"rl_discovery_d5r", "rl_discovery_d5s"}
    if (
        payload.get("schema_version") != expected_schema
        or payload.get("status") != "COMPLETE"
        or payload.get("profile") != "PRIMARY"
        or receipt.get("status") != "COMPLETE"
        or receipt.get("profile") != "PRIMARY"
        or receipt.get("verdict") != payload.get("verdict")
        or (source_identity_in_receipt and receipt.get("prereg_sha256") != payload.get("prereg_sha256"))
        or (source_identity_in_receipt and receipt.get("episode_snapshot_sha256") != payload.get("episode_snapshot_sha256"))
        or receipt.get("fresh_oos") != "NOT_RUN_NO_READ"
        or receipt.get("artifact_manifest_sha256") != digest
    ):
        return blocked, {}
    if artifact_type == "rl_discovery_d4" and not _valid_d4_primary(run_dir, payload, receipt, digest):
        return blocked, {}
    if artifact_type == "rl_discovery_d5" and not valid_d5_primary(
        run_dir, payload, receipt, digest, snapshot.relative_paths, snapshot.captured,
    ):
        return blocked, {}
    if artifact_type == "rl_discovery_d5r" and not valid_d5r_primary(
        run_dir, payload, receipt, digest, snapshot.relative_paths, snapshot.captured,
    ):
        return blocked, {}
    if artifact_type == "rl_discovery_d5s" and not valid_d5s_primary(
        run_dir, payload, receipt, digest, snapshot.relative_paths, snapshot.captured,
    ):
        return blocked, {}
    is_d5 = artifact_type == "rl_discovery_d5"
    is_d5r = artifact_type == "rl_discovery_d5r"
    is_d5s = artifact_type == "rl_discovery_d5s"
    is_train_cost = is_d5 or is_d5r or is_d5s
    prereg_value = payload.get("prereg_sha256")
    if is_d5r or is_d5s:
        prereg_sha: JsonValue = hashlib.sha256(
            snapshot.captured["inputs/prereg.json"]
        ).hexdigest()
    else:
        prereg_sha = prereg_value if isinstance(prereg_value, str) else None
    type1_outcome = {
        "rl_discovery_d4": "D4_TRAIN_ONLY_CONFIRMED",
        "rl_discovery_d5": "D5_TRAIN_ONLY_EVALUATED",
        "rl_discovery_d5r": "D5R_CAPACITY_EVALUATED",
        "rl_discovery_d5s": "D5S_STABILITY_EVALUATED",
    }.get(artifact_type, "COMPLETE_NO_GO")
    compact: dict[str, JsonValue] = {
        "research_lane": "rl_discovery",
        "status": payload.get("status"),
        "verdict": payload.get("verdict"),
        "profile": payload.get("profile"),
        "fresh_oos": payload.get("fresh_oos"),
        "type1_outcome": type1_outcome,
        "primary_round_trip_cost_bp": 23 if is_train_cost else 0,
        "diagnostic_round_trip_cost_bp": 0 if is_train_cost else 23,
        "prereg_sha256": prereg_sha,
        "promotion_allowed": False,
        "profitability_claim_allowed": False,
        "live_broker_order_allowed": False,
        "artifact_manifest_sha256": digest,
    }
    if is_train_cost:
        payload = {**payload, "live_broker_order_allowed": False}
    return compact, payload


def _valid_d4_primary(
    run_dir: Path,
    payload: dict[str, JsonValue],
    receipt: dict[str, JsonValue],
    digest: str,
) -> bool:
    expected = {
        (algorithm.value, reward.value, seed)
        for algorithm in D4AlgorithmArmId
        for reward in D4RewardArmId
        for seed in (0, 1, 2)
    }
    models = payload.get("models")
    if not isinstance(models, list) or len(models) != 24:
        return False
    observed: set[tuple[str, str, int]] = set()
    for row in models:
        if not isinstance(row, dict):
            return False
        if not all(isinstance(row.get(metric), dict) for metric in ("fit", "native", "cost_23bp")):
            return False
        algorithm = row.get("algorithm_arm")
        reward = row.get("reward_arm")
        seed = row.get("seed")
        if not isinstance(algorithm, str) or not isinstance(reward, str) or not isinstance(seed, int):
            return False
        observed.add((algorithm, reward, seed))
    gate = payload.get("gate")
    approved_smoke = payload.get("approved_smoke")
    try:
        key = bytes.fromhex(os.environ.get("KRONOS_D4_APPROVAL_KEY_HEX", ""))
    except ValueError:
        return False
    if (
        observed != expected
        or not isinstance(gate, dict)
        or gate.get("best_rl_arm") != "C_DQN_DISCRETE"
        or gate.get("confirmed_rl_arms") != ["C_DQN_DISCRETE"]
        or gate.get("supervised_ceiling_confirmed") is not True
        or payload.get("promotion_allowed") is not False
        or payload.get("profitability_claim_allowed") is not False
        or not isinstance(approved_smoke, str)
    ):
        return False
    if len(key) >= 32:
        expected_signature = primary_custody_signature(
            key,
            run_name=run_dir.name,
            prereg_sha=str(payload.get("prereg_sha256", "")),
            episode_sha=str(payload.get("episode_snapshot_sha256", "")),
            manifest_sha=digest,
            approved_smoke=approved_smoke,
        )
        if hmac.compare_digest(str(receipt.get("primary_custody_hmac_sha256", "")), expected_signature):
            return True
    return _matches_committed_d4_custody(run_dir, digest)


def _matches_committed_d4_custody(run_dir: Path, digest: str) -> bool:
    custody_path = Path(__file__).resolve().parents[1] / "docs" / "evidence" / f"{run_dir.name}.custody.json"
    try:
        value = cast(JsonValue, json.loads(custody_path.read_bytes()))
        summary_sha = hashlib.sha256((run_dir / "summary.json").read_bytes()).hexdigest()
        receipt_sha = hashlib.sha256((run_dir / "terminal_receipt.json").read_bytes()).hexdigest()
    except (OSError, ValueError):
        return False
    return (
        isinstance(value, dict)
        and value.get("schema_version") == "kronos.rl-discovery.d4.custody.v1"
        and value.get("run_name") == run_dir.name
        and value.get("artifact_manifest_sha256") == digest
        and value.get("summary_sha256") == summary_sha
        and value.get("terminal_receipt_sha256") == receipt_sha
        and value.get("model_count") == 24
        and value.get("outcome_count") == 24
    )
