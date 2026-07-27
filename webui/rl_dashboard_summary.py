"""Typed summary readers for RL dashboard run artifacts."""

# JSON artifact readers intentionally expose legacy dynamic payloads.
# pyright: reportPrivateUsage=false, reportExplicitAny=false, reportAny=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false

from __future__ import annotations

from pathlib import Path
from typing import Any

if __package__:
    from .rl_dashboard_files import LIVE_SUMMARY_FILE_NAMES, _int_or_zero, _is_run_file, _read_run_json
    from .rl_dashboard_opening import opening_workflow_summary
    from .rl_dashboard_run_state import require_discovery_terminal_receipt
else:  # pragma: no cover - supports direct script-style imports
    from webui.rl_dashboard_files import LIVE_SUMMARY_FILE_NAMES, _int_or_zero, _is_run_file, _read_run_json
    from webui.rl_dashboard_opening import opening_workflow_summary
    from webui.rl_dashboard_run_state import require_discovery_terminal_receipt


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
