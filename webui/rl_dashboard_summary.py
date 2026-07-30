"""Typed summary readers for RL dashboard run artifacts."""

# This summary facade intentionally uses the path helper's private containment check.
# pyright: reportPrivateUsage=false

from __future__ import annotations

from pathlib import Path
from typing import cast

from stom_rl.rl_discovery.storage import JsonValue

if __package__:
    from . import rl_dashboard_discovery as _discovery
    from . import rl_dashboard_files as _files
    from . import rl_dashboard_json as _json
    from . import rl_dashboard_opening as _opening
    from . import rl_dashboard_run_state as _state
else:  # pragma: no cover - supports direct script-style imports
    from webui import rl_dashboard_discovery as _discovery
    from webui import rl_dashboard_files as _files
    from webui import rl_dashboard_json as _json
    from webui import rl_dashboard_opening as _opening
    from webui import rl_dashboard_run_state as _state

find_discovery_evidence = _discovery.find_discovery_evidence


def find_json_summary(run_dir: Path, artifact_type: str) -> dict[str, JsonValue]:
    """Read the compact summary associated with one recognized artifact type."""

    if artifact_type == "opening_30m_rule_filter":
        payload = _json.read_run_json(run_dir, run_dir / "opening_rule_filter_summary.json")
        summary = dict(payload)
        _ = summary.pop("rule_filter_lifecycle", None)
        return summary
    if artifact_type == "opening_30m_rl_workflow":
        return cast(dict[str, JsonValue], _opening.opening_workflow_summary(run_dir))
    if artifact_type == "orderbook_rl_readiness":
        payload = _json.read_run_json(run_dir, run_dir / "orderbook_rl_readiness_summary.json")
        return _json.json_object(payload.get("summary"))
    if artifact_type == "portfolio_paper":
        payload = _json.read_run_json(run_dir, run_dir / "portfolio_paper_summary.json")
        summary = _json.json_object(payload.get("summary"))
        config = _json.json_object(payload.get("config"))
        if config:
            _ = summary.setdefault("cost_bps", config.get("cost_bps"))
            _ = summary.setdefault("max_positions", config.get("max_positions"))
            _ = summary.setdefault("top_k_candidates", config.get("top_k_candidates"))
        return summary
    if artifact_type == "performance_leaderboard":
        payload = _json.read_run_json(run_dir, run_dir / "performance_leaderboard.json")
        return _json.json_object(payload.get("summary"))
    if artifact_type == "sb3_smoke":
        return _sb3_summary(run_dir)
    if artifact_type in _json.DISCOVERY_ARTIFACT_TYPES:
        return find_discovery_evidence(run_dir, artifact_type)[0]
    if artifact_type == "contextual_bandit":
        payload = _json.read_run_json(run_dir, run_dir / "eval_summary.json")
        summary = _json.json_object(payload.get("eval_summary"))
        return summary or _json.json_object(payload.get("summary"))
    if artifact_type == "cost_gate":
        payload = _json.read_run_json(run_dir, run_dir / "cost_gate_report.json")
        return _json.json_object(payload.get("summary"))
    if artifact_type == "baseline":
        payload = _json.read_run_json(run_dir, run_dir / "baseline_summary.json")
        return _json.json_object(payload.get("summary"))
    if artifact_type == "episode_manifest":
        summary_path = run_dir / "episode_summary.json"
        source = (
            summary_path
            if _files._is_run_file(run_dir, summary_path)
            else run_dir / "episode_manifest.json"
        )
        payload = _json.read_run_json(run_dir, source)
        return _json.json_object(payload.get("summary")) or payload
    return {}


def _sb3_summary(run_dir: Path) -> dict[str, JsonValue]:
    payload = _json.read_run_json(run_dir, run_dir / "sb3_smoke_summary.json")
    summary = cast(
        dict[str, JsonValue],
        _state.require_discovery_terminal_receipt(
            run_dir,
            cast(dict[str, object], _json.json_object(payload.get("summary"))),
        ),
    )
    live_value = payload.get("live_events")
    live_summary = _json.json_object(live_value)
    if isinstance(live_value, dict):
        _ = summary.setdefault("live_event_count", live_summary.get("event_count"))
        _ = summary.setdefault("live_event_phases", live_summary.get("phases"))
    else:
        for file_name in _files.LIVE_SUMMARY_FILE_NAMES:
            summary_path = run_dir / file_name
            if _files._is_run_file(run_dir, summary_path):
                file_summary = _json.read_run_json(run_dir, summary_path)
                _ = summary.setdefault("live_event_count", file_summary.get("event_count"))
                _ = summary.setdefault("live_event_phases", file_summary.get("phases"))
                break
    models = _json.json_objects(payload.get("models"))
    best_model = summary.get("best_model")
    selected = next((row for row in models if row.get("model") == best_model), models[0] if models else {})
    _ = summary.setdefault(
        "max_training_timesteps",
        max((_int_or_zero(row.get("training_timesteps")) for row in models), default=0),
    )
    for key in ("avg_episode_net_return_pct", "trade_count", "cost_bps", "slippage_bps", "passes_cost_gate"):
        if key in selected:
            _ = summary.setdefault(key, selected[key])
    return summary


def _int_or_zero(value: JsonValue | None) -> int:
    try:
        return int(float(value)) if isinstance(value, (bool, int, float, str)) else 0
    except ValueError:
        return 0
