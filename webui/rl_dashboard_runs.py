"""Run listing and detail loading for STOM RL dashboard artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

if __package__:
    from .rl_strategy_context import build_strategy_context
    from . import rl_dashboard_files as _files
    from .rl_dashboard_opening import load_opening_workflow_detail
    from .rl_dashboard_files import ARTIFACT_SIGNATURES, LIVE_SUMMARY_FILE_NAMES, RlDashboardPathError, _is_relative_to_root, _is_run_file, _read_run_json, _safe_direct_child_name, _utc_mtime
    from .rl_dashboard_identity import (
        RUN_IDENTITY_PROTOCOL as _IDENTITY_PROTOCOL,
        canonical_path_id,
        run_identity_fields as _run_identity_fields,
    )
    from .rl_dashboard_run_state import (
        DEFAULT_POLL_INTERVAL_SECONDS as _DEFAULT_POLL_INTERVAL_SECONDS,
        artifact_files as _artifact_files,
        baseline_policies as _baseline_policies,
        require_discovery_terminal_receipt as _require_discovery_terminal_receipt,
        run_lifecycle as _run_lifecycle,
    )
    from .rl_dashboard_summary import find_discovery_evidence as _find_discovery_evidence
    from .rl_dashboard_summary import find_json_summary as _find_json_summary
else:  # pragma: no cover - supports direct script-style imports
    from webui.rl_strategy_context import build_strategy_context
    from webui import rl_dashboard_files as _files
    from webui.rl_dashboard_opening import load_opening_workflow_detail
    from webui.rl_dashboard_files import ARTIFACT_SIGNATURES, LIVE_SUMMARY_FILE_NAMES, RlDashboardPathError, _is_relative_to_root, _is_run_file, _read_run_json, _safe_direct_child_name, _utc_mtime
    from webui.rl_dashboard_identity import (
        RUN_IDENTITY_PROTOCOL as _IDENTITY_PROTOCOL,
        canonical_path_id,
        run_identity_fields as _run_identity_fields,
    )
    from webui.rl_dashboard_run_state import (
        DEFAULT_POLL_INTERVAL_SECONDS as _DEFAULT_POLL_INTERVAL_SECONDS,
        artifact_files as _artifact_files,
        baseline_policies as _baseline_policies,
        require_discovery_terminal_receipt as _require_discovery_terminal_receipt,
        run_lifecycle as _run_lifecycle,
    )
    from webui.rl_dashboard_summary import find_discovery_evidence as _find_discovery_evidence
    from webui.rl_dashboard_summary import find_json_summary as _find_json_summary

RUN_IDENTITY_PROTOCOL = _IDENTITY_PROTOCOL
DEFAULT_POLL_INTERVAL_SECONDS = _DEFAULT_POLL_INTERVAL_SECONDS
require_discovery_terminal_receipt = _require_discovery_terminal_receipt


def _detect_artifact_type(run_dir: Path) -> str:
    discovery_path = run_dir / "summary.json"
    if _is_run_file(run_dir, discovery_path):
        payload = _read_run_json(run_dir, discovery_path)
        schema = payload.get("schema_version")
        if schema == "kronos.rl-discovery.d2.result.v1":
            return "rl_discovery_d2"
        if schema == "kronos.rl-discovery.d3.result.v1":
            return "rl_discovery_d3"
        if schema == "kronos.rl-discovery.d4.result.v1":
            return "rl_discovery_d4"
    for artifact_type, file_name in ARTIFACT_SIGNATURES:
        if _is_run_file(run_dir, run_dir / file_name):
            return artifact_type
    return "unknown"


def _run_record(run_dir: Path, *, verified_summary: Dict[str, Any] | None = None) -> Dict[str, Any]:
    artifact_type = _detect_artifact_type(run_dir)
    summary = verified_summary if verified_summary is not None else _find_json_summary(run_dir, artifact_type)
    identity = _run_identity_fields(run_dir)
    return {
        "name": run_dir.name,
        **identity,
        "artifact_type": artifact_type,
        "modified_at": _utc_mtime(run_dir),
        "summary": summary,
        "strategy_context": build_strategy_context(artifact_type, summary),
        "policies": _baseline_policies(run_dir) if artifact_type == "baseline" else [],
        "lifecycle": _run_lifecycle(run_dir),
    }


def iter_run_dirs() -> Iterable[Path]:
    seen = set()
    for root in _files.RL_RUN_ROOTS:
        root = Path(root)
        if not root.is_dir():
            continue
        for child in _candidate_run_dirs(root):
            if not _is_relative_to_root(child, root):
                continue
            key = canonical_path_id(child)
            if key in seen:
                continue
            seen.add(key)
            yield child


def _candidate_run_dirs(root: Path) -> Iterable[Path]:
    for child in root.iterdir():
        if not child.is_dir():
            continue
        nested_runs = _nested_run_dirs(child)
        if nested_runs:
            yield from nested_runs
        elif _detect_artifact_type(child) != "unknown":
            yield child


def _nested_run_dirs(parent: Path) -> List[Path]:
    return [
        grandchild
        for grandchild in parent.iterdir()
        if grandchild.is_dir() and _detect_artifact_type(grandchild) != "unknown"
    ]


def list_rl_runs(limit: int = 50) -> List[Dict[str, Any]]:
    """List available independent RL runtime artifact directories."""

    runs = sorted(iter_run_dirs(), key=lambda path: path.stat().st_mtime, reverse=True)
    return [_run_record(path) for path in runs[: max(0, int(limit))]]


def resolve_run_dir(run_name: str) -> Path:
    safe_name = _safe_direct_child_name(run_name, label="run")
    for root in _files.RL_RUN_ROOTS:
        root_path = Path(root)
        candidate = root_path / safe_name
        if candidate.is_dir() and not _nested_run_dirs(candidate):
            if not _is_relative_to_root(candidate, root_path):
                raise RlDashboardPathError(f"Invalid run: resolved path escapes RL root: {run_name!r}")
            return candidate
        for child in root_path.iterdir() if root_path.is_dir() else []:
            nested = child / safe_name
            if nested.is_dir() and _is_relative_to_root(nested, root_path):
                return nested
    raise FileNotFoundError(f"RL run not found: {run_name}")


def load_rl_run(run_name: str) -> Dict[str, Any]:
    """Load a run detail payload without reading large CSV tables."""

    run_dir = resolve_run_dir(run_name)
    artifact_type = _detect_artifact_type(run_dir)
    verified_detail: Dict[str, Any] | None = None
    verified_summary: Dict[str, Any] | None = None
    if artifact_type in {"rl_discovery_d2", "rl_discovery_d3", "rl_discovery_d4"}:
        verified_summary, verified_detail = _find_discovery_evidence(run_dir, artifact_type)
    payload: Dict[str, Any] = {
        **_run_record(run_dir, verified_summary=verified_summary),
        "artifacts": _artifact_files(run_dir),
    }
    if artifact_type == "orderbook_rl_readiness":
        payload["detail"] = _read_run_json(run_dir, run_dir / "orderbook_rl_readiness_summary.json")
        payload["model"] = {
            "model_type": "marketable_only_orderbook_rl_environment",
            "feature_columns": payload["detail"].get("observation_features", []),
            "train_summary": payload.get("summary", {}),
        }
    elif artifact_type == "portfolio_paper":
        signature = _read_run_json(run_dir, run_dir / "portfolio_paper_summary.json")
        wf_report_path = run_dir / "portfolio_walk_forward_report.json"
        walk_forward = _read_run_json(run_dir, wf_report_path) if _is_run_file(run_dir, wf_report_path) else {}
        risk_path = run_dir / "risk_triggers.json"
        risk_payload = _read_run_json(run_dir, risk_path) if _is_run_file(run_dir, risk_path) else {}
        risk_triggers = risk_payload.get("risk_triggers", []) if isinstance(risk_payload, dict) else []
        risk_reasons: Dict[str, int] = {}
        for trigger in risk_triggers if isinstance(risk_triggers, list) else []:
            reason = str(trigger.get("reason", "unknown")) if isinstance(trigger, Mapping) else "unknown"
            risk_reasons[reason] = risk_reasons.get(reason, 0) + 1
        payload["detail"] = {
            "summary": signature.get("summary", {}),
            "config": signature.get("config", {}),
            "walk_forward_summary": walk_forward.get("summary", signature.get("walk_forward_summary", {})),
            "risk_trigger_reasons": risk_reasons,
            "risk_trigger_sample": risk_triggers[:20] if isinstance(risk_triggers, list) else [],
        }
    elif artifact_type == "performance_leaderboard":
        payload["detail"] = _read_run_json(run_dir, run_dir / "performance_leaderboard.json")
    elif artifact_type == "sb3_smoke":
        payload["detail"] = _read_run_json(run_dir, run_dir / "sb3_smoke_summary.json")
        live_summary = payload["detail"].get("live_events")
        if not isinstance(live_summary, dict):
            for file_name in LIVE_SUMMARY_FILE_NAMES:
                summary_path = run_dir / file_name
                if _is_run_file(run_dir, summary_path):
                    live_summary = _read_run_json(run_dir, summary_path)
                    break
        if isinstance(live_summary, dict):
            payload["live_events"] = live_summary
        models = payload["detail"].get("models", [])
        best_model = payload["summary"].get("best_model")
        selected_model = next((row for row in models if row.get("model") == best_model), models[0] if models else {})
        payload["model"] = {
            "model_type": f"stable_baselines3_{selected_model.get('algorithm', 'sb3')}",
            "feature_columns": payload["summary"].get("feature_columns", []),
            "train_summary": selected_model,
        }
    elif artifact_type in {"rl_discovery_d2", "rl_discovery_d3", "rl_discovery_d4"}:
        payload["detail"] = verified_detail or {}
    elif artifact_type == "contextual_bandit":
        payload["detail"] = _read_run_json(run_dir, run_dir / "eval_summary.json")
        model_path = run_dir / "model.json"
        if _is_run_file(run_dir, model_path):
            model_payload = _read_run_json(run_dir, model_path)
            model = model_payload.get("model", {})
            payload["model"] = {
                "model_type": model.get("model_type"),
                "feature_columns": model.get("feature_columns", []),
                "train_summary": model.get("train_summary", {}),
            }
    elif artifact_type == "cost_gate":
        payload["detail"] = _read_run_json(run_dir, run_dir / "cost_gate_report.json")
    elif artifact_type == "baseline":
        payload["detail"] = _read_run_json(run_dir, run_dir / "baseline_summary.json")
    elif artifact_type == "episode_manifest":
        manifest = _read_run_json(run_dir, run_dir / "episode_manifest.json")
        payload["detail"] = {"summary": manifest.get("summary", {}), "episode_sample": manifest.get("episodes", [])[:10]}
    elif artifact_type == "opening_30m_rule_filter":
        payload["detail"] = _read_run_json(run_dir, run_dir / "opening_rule_filter_summary.json")
    elif artifact_type == "opening_30m_rl_workflow":
        payload["detail"] = load_opening_workflow_detail(run_dir)
    return payload
