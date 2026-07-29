"""Typed summary readers for RL dashboard run artifacts."""

# JSON artifact readers intentionally expose legacy dynamic payloads.
# pyright: reportPrivateUsage=false, reportExplicitAny=false, reportAny=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false

from __future__ import annotations

import json
import hmac
import hashlib
import os
from pathlib import Path
from typing import Any

from stom_rl.rl_discovery.evidence_snapshot import read_evidence_snapshot
from stom_rl.rl_discovery.d4_approval import primary_custody_signature
from stom_rl.rl_discovery.d4_contract import D4AlgorithmArmId, D4RewardArmId

if __package__:
    from .rl_dashboard_files import LIVE_SUMMARY_FILE_NAMES, _int_or_zero, _is_run_file, _read_run_json
    from .rl_dashboard_opening import opening_workflow_summary
    from .rl_dashboard_run_state import require_discovery_terminal_receipt
    from .rl_dashboard_d5 import valid_d5_primary
else:  # pragma: no cover - supports direct script-style imports
    from webui.rl_dashboard_files import LIVE_SUMMARY_FILE_NAMES, _int_or_zero, _is_run_file, _read_run_json
    from webui.rl_dashboard_opening import opening_workflow_summary
    from webui.rl_dashboard_run_state import require_discovery_terminal_receipt
    from webui.rl_dashboard_d5 import valid_d5_primary


def find_json_summary(run_dir: Path, artifact_type: str) -> dict[str, Any]:
    """Read the compact summary associated with one recognized artifact type."""

    if artifact_type == "opening_30m_rule_filter":
        payload = _read_run_json(run_dir, run_dir / "opening_rule_filter_summary.json")
        summary = dict(payload)
        summary.pop("rule_filter_lifecycle", None)
        return summary
    if artifact_type == "opening_30m_rl_workflow":
        return opening_workflow_summary(run_dir)
    if artifact_type == "orderbook_rl_readiness":
        payload = _read_run_json(run_dir, run_dir / "orderbook_rl_readiness_summary.json")
        return dict(payload.get("summary", {}))
    if artifact_type == "portfolio_paper":
        payload = _read_run_json(run_dir, run_dir / "portfolio_paper_summary.json")
        summary = dict(payload.get("summary", {}))
        config = payload.get("config", {})
        if isinstance(config, dict):
            summary.setdefault("cost_bps", config.get("cost_bps"))
            summary.setdefault("max_positions", config.get("max_positions"))
            summary.setdefault("top_k_candidates", config.get("top_k_candidates"))
        return summary
    if artifact_type == "performance_leaderboard":
        payload = _read_run_json(run_dir, run_dir / "performance_leaderboard.json")
        return dict(payload.get("summary", {}))
    if artifact_type == "sb3_smoke":
        return _sb3_summary(run_dir)
    if artifact_type in {"rl_discovery_d2", "rl_discovery_d3", "rl_discovery_d4", "rl_discovery_d5"}:
        return find_discovery_evidence(run_dir, artifact_type)[0]
    if artifact_type == "contextual_bandit":
        payload = _read_run_json(run_dir, run_dir / "eval_summary.json")
        return dict(payload.get("eval_summary", payload.get("summary", {})))
    if artifact_type == "cost_gate":
        payload = _read_run_json(run_dir, run_dir / "cost_gate_report.json")
        return dict(payload.get("summary", {}))
    if artifact_type == "baseline":
        payload = _read_run_json(run_dir, run_dir / "baseline_summary.json")
        return dict(payload.get("summary", {}))
    if artifact_type == "episode_manifest":
        summary_path = run_dir / "episode_summary.json"
        source = summary_path if _is_run_file(run_dir, summary_path) else run_dir / "episode_manifest.json"
        payload = _read_run_json(run_dir, source)
        return dict(payload.get("summary", payload))
    return {}


def find_discovery_evidence(run_dir: Path, artifact_type: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return compact and detailed discovery data from one verified snapshot."""

    blocked = {"research_lane": "rl_discovery", "status": "BLOCK", "verdict": "NO_GO"}
    try:
        snapshot = read_evidence_snapshot(
            run_dir,
            capture_paths=frozenset({"summary.json", "terminal_receipt.json"}),
            excluded_manifest_paths=frozenset({"terminal_receipt.json"}),
        )
        payload_value: object = json.loads(snapshot.captured["summary.json"])
        receipt_value: object = json.loads(snapshot.captured["terminal_receipt.json"])
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
    }.get(artifact_type)
    digest = snapshot.manifest_sha256
    if (
        payload.get("schema_version") != expected_schema
        or payload.get("status") != "COMPLETE"
        or payload.get("profile") != "PRIMARY"
        or receipt.get("status") != "COMPLETE"
        or receipt.get("profile") != "PRIMARY"
        or receipt.get("verdict") != payload.get("verdict")
        or receipt.get("prereg_sha256") != payload.get("prereg_sha256")
        or receipt.get("episode_snapshot_sha256") != payload.get("episode_snapshot_sha256")
        or receipt.get("fresh_oos") != "NOT_RUN_NO_READ"
        or receipt.get("artifact_manifest_sha256") != digest
    ):
        return blocked, {}
    if artifact_type == "rl_discovery_d4" and not _valid_d4_primary(run_dir, payload, receipt, digest):
        return blocked, {}
    if artifact_type == "rl_discovery_d5" and not valid_d5_primary(run_dir, payload, receipt, digest):
        return blocked, {}
    is_d5 = artifact_type == "rl_discovery_d5"
    compact = {
        "research_lane": "rl_discovery",
        "status": payload.get("status"),
        "verdict": payload.get("verdict"),
        "profile": payload.get("profile"),
        "fresh_oos": payload.get("fresh_oos"),
        "type1_outcome": "D5_TRAIN_ONLY_EVALUATED" if is_d5 else ("COMPLETE_NO_GO" if artifact_type != "rl_discovery_d4" else "D4_TRAIN_ONLY_CONFIRMED"),
        "primary_round_trip_cost_bp": 23 if is_d5 else 0,
        "diagnostic_round_trip_cost_bp": 0 if is_d5 else 23,
        "prereg_sha256": payload.get("prereg_sha256"),
        "promotion_allowed": False,
        "profitability_claim_allowed": False,
        "artifact_manifest_sha256": digest,
    }
    return compact, payload


def _valid_d4_primary(run_dir: Path, payload: dict[object, object], receipt: dict[object, object], digest: str) -> bool:
    expected = {
        (algorithm.value, reward.value, seed)
        for algorithm in D4AlgorithmArmId for reward in D4RewardArmId for seed in (0, 1, 2)
    }
    models = payload.get("models")
    if not isinstance(models, list) or len(models) != 24:
        return False
    observed: set[tuple[object, object, object]] = set()
    for row in models:
        if not isinstance(row, dict):
            return False
        if not all(isinstance(row.get(metric), dict) for metric in ("fit", "native", "cost_23bp")):
            return False
        observed.add((row.get("algorithm_arm"), row.get("reward_arm"), row.get("seed")))
    gate = payload.get("gate")
    approved_smoke = payload.get("approved_smoke")
    raw_key = os.environ.get("KRONOS_D4_APPROVAL_KEY_HEX", "")
    try:
        key = bytes.fromhex(raw_key)
    except ValueError:
        return False
    if (
        observed != expected or not isinstance(gate, dict)
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
            key, run_name=run_dir.name, prereg_sha=str(payload.get("prereg_sha256", "")),
            episode_sha=str(payload.get("episode_snapshot_sha256", "")), manifest_sha=digest,
            approved_smoke=approved_smoke,
        )
        if hmac.compare_digest(str(receipt.get("primary_custody_hmac_sha256", "")), expected_signature):
            return True
    return _matches_committed_d4_custody(run_dir, digest)


def _matches_committed_d4_custody(run_dir: Path, digest: str) -> bool:
    custody_path = Path(__file__).resolve().parents[1] / "docs" / "evidence" / f"{run_dir.name}.custody.json"
    try:
        value: object = json.loads(custody_path.read_bytes())
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


def _sb3_summary(run_dir: Path) -> dict[str, Any]:
    payload = _read_run_json(run_dir, run_dir / "sb3_smoke_summary.json")
    summary = require_discovery_terminal_receipt(run_dir, dict(payload.get("summary", {})))
    live_summary = payload.get("live_events")
    if isinstance(live_summary, dict):
        summary.setdefault("live_event_count", live_summary.get("event_count"))
        summary.setdefault("live_event_phases", live_summary.get("phases"))
    else:
        for file_name in LIVE_SUMMARY_FILE_NAMES:
            summary_path = run_dir / file_name
            if _is_run_file(run_dir, summary_path):
                file_summary = _read_run_json(run_dir, summary_path)
                summary.setdefault("live_event_count", file_summary.get("event_count"))
                summary.setdefault("live_event_phases", file_summary.get("phases"))
                break
    models = payload.get("models", [])
    best_model = summary.get("best_model")
    selected = next((row for row in models if row.get("model") == best_model), models[0] if models else {})
    summary.setdefault(
        "max_training_timesteps",
        max((_int_or_zero(row.get("training_timesteps")) for row in models), default=0),
    )
    for key in ("avg_episode_net_return_pct", "trade_count", "cost_bps", "slippage_bps", "passes_cost_gate"):
        if key in selected:
            summary.setdefault(key, selected[key])
    return summary
