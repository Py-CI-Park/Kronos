"""Run listing and detail loading for STOM RL dashboard artifacts."""

# This module is the public orchestrator for intentionally private file helpers.
# pyright: reportPrivateUsage=false, reportPrivateLocalImportUsage=false

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import cast

from stom_rl.rl_discovery.storage import JsonValue

if __package__:
    from . import rl_dashboard_files as _files
    from . import rl_dashboard_identity as _identity
    from . import rl_dashboard_json as _json
    from . import rl_dashboard_opening as _opening
    from . import rl_dashboard_run_state as _state
    from . import rl_dashboard_summary as _summary
    from . import rl_strategy_context as _strategy
else:  # pragma: no cover - supports direct script-style imports
    from webui import rl_dashboard_files as _files
    from webui import rl_dashboard_identity as _identity
    from webui import rl_dashboard_json as _json
    from webui import rl_dashboard_opening as _opening
    from webui import rl_dashboard_run_state as _state
    from webui import rl_dashboard_summary as _summary
    from webui import rl_strategy_context as _strategy

RUN_IDENTITY_PROTOCOL = _identity.RUN_IDENTITY_PROTOCOL
DEFAULT_POLL_INTERVAL_SECONDS = _state.DEFAULT_POLL_INTERVAL_SECONDS
require_discovery_terminal_receipt = _state.require_discovery_terminal_receipt
_baseline_policies = _state.baseline_policies
_find_discovery_evidence = _summary.find_discovery_evidence
_run_lifecycle = _state.run_lifecycle


def _detect_artifact_type(run_dir: Path) -> str:
    discovery_path = run_dir / "summary.json"
    if _files._is_run_file(run_dir, discovery_path):
        payload = _json.read_run_json(run_dir, discovery_path)
        schema = payload.get("schema_version")
        if schema == "kronos.rl-discovery.d2.result.v1":
            return "rl_discovery_d2"
        if schema == "kronos.rl-discovery.d3.result.v1":
            return "rl_discovery_d3"
        if schema == "kronos.rl-discovery.d4.result.v1":
            return "rl_discovery_d4"
        if schema == "kronos.rl-discovery.d5.result.v1":
            return "rl_discovery_d5"
        if schema == "kronos.rl-discovery.d5r.capacity.v1":
            return "rl_discovery_d5r"
        if schema == "kronos.rl-discovery.d5s.stability.v1":
            return "rl_discovery_d5s"
        if schema == "kronos.rl-discovery.d6.validation.v1":
            return "rl_discovery_d6"
        if schema == "kronos.rl-discovery.d6r.falsification.v1":
            return "rl_discovery_d6r"
    for artifact_type, file_name in _files.ARTIFACT_SIGNATURES:
        if _files._is_run_file(run_dir, run_dir / file_name):
            return artifact_type
    return "unknown"


def _run_record(
    run_dir: Path,
    *,
    verified_summary: dict[str, JsonValue] | None = None,
) -> dict[str, object]:
    artifact_type = _detect_artifact_type(run_dir)
    summary = (
        verified_summary
        if verified_summary is not None
        else _summary.find_json_summary(run_dir, artifact_type)
    )
    identity = _identity.run_identity_fields(run_dir)
    return {
        "name": run_dir.name,
        **identity,
        "artifact_type": artifact_type,
        "modified_at": _files._utc_mtime(run_dir),
        "summary": summary,
        "strategy_context": _strategy.build_strategy_context(artifact_type, summary),
        "policies": _state.baseline_policies(run_dir) if artifact_type == "baseline" else [],
        "lifecycle": _state.run_lifecycle(run_dir),
    }


def iter_run_dirs() -> Iterable[Path]:
    seen: set[str] = set()
    for root in _files.RL_RUN_ROOTS:
        root = Path(root)
        if not root.is_dir():
            continue
        for child in _candidate_run_dirs(root):
            if not _files._is_relative_to_root(child, root):
                continue
            key = _identity.canonical_path_id(child)
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


def _nested_run_dirs(parent: Path) -> list[Path]:
    return [
        grandchild
        for grandchild in parent.iterdir()
        if grandchild.is_dir() and _detect_artifact_type(grandchild) != "unknown"
    ]


def list_rl_runs(limit: int = 50) -> list[dict[str, object]]:
    """List available independent RL runtime artifact directories."""

    runs = sorted(iter_run_dirs(), key=lambda path: path.stat().st_mtime, reverse=True)
    return [_run_record(path) for path in runs[: max(0, int(limit))]]


def resolve_run_dir(run_name: str) -> Path:
    safe_name = _files._safe_direct_child_name(run_name, label="run")
    for root in _files.RL_RUN_ROOTS:
        root_path = Path(root)
        candidate = root_path / safe_name
        if candidate.is_dir() and not _nested_run_dirs(candidate):
            if not _files._is_relative_to_root(candidate, root_path):
                raise _files.RlDashboardPathError(
                    f"Invalid run: resolved path escapes RL root: {run_name!r}"
                )
            return candidate
        children: Iterable[Path] = root_path.iterdir() if root_path.is_dir() else ()
        for child in children:
            nested = child / safe_name
            if nested.is_dir() and _files._is_relative_to_root(nested, root_path):
                return nested
    raise FileNotFoundError(f"RL run not found: {run_name}")


def load_rl_run(run_name: str) -> dict[str, object]:
    """Load a run detail payload without reading large CSV tables."""

    run_dir = resolve_run_dir(run_name)
    artifact_type = _detect_artifact_type(run_dir)
    verified_detail: dict[str, JsonValue] | None = None
    verified_summary: dict[str, JsonValue] | None = None
    if artifact_type in _json.DISCOVERY_ARTIFACT_TYPES:
        verified_summary, verified_detail = _find_discovery_evidence(
            run_dir,
            artifact_type,
        )
    payload: dict[str, object] = {
        **_run_record(run_dir, verified_summary=verified_summary),
        "artifacts": _state.artifact_files(run_dir),
    }
    if artifact_type == "orderbook_rl_readiness":
        detail = _json.read_run_json(
            run_dir,
            run_dir / "orderbook_rl_readiness_summary.json",
        )
        payload["detail"] = detail
        payload["model"] = {
            "model_type": "marketable_only_orderbook_rl_environment",
            "feature_columns": detail.get("observation_features", []),
            "train_summary": payload.get("summary", {}),
        }
    elif artifact_type == "portfolio_paper":
        signature = _json.read_run_json(run_dir, run_dir / "portfolio_paper_summary.json")
        wf_report_path = run_dir / "portfolio_walk_forward_report.json"
        walk_forward = (
            _json.read_run_json(run_dir, wf_report_path)
            if _files._is_run_file(run_dir, wf_report_path)
            else {}
        )
        risk_path = run_dir / "risk_triggers.json"
        risk_payload = (
            _json.read_run_json(run_dir, risk_path)
            if _files._is_run_file(run_dir, risk_path)
            else {}
        )
        risk_value = risk_payload.get("risk_triggers")
        risk_triggers = cast(list[JsonValue], risk_value) if isinstance(risk_value, list) else []
        risk_reasons: dict[str, int] = {}
        for trigger in risk_triggers:
            trigger_map = _json.json_object(trigger)
            reason = str(trigger_map.get("reason", "unknown")) if trigger_map else "unknown"
            risk_reasons[reason] = risk_reasons.get(reason, 0) + 1
        payload["detail"] = {
            "summary": signature.get("summary", {}),
            "config": signature.get("config", {}),
            "walk_forward_summary": walk_forward.get("summary", signature.get("walk_forward_summary", {})),
            "risk_trigger_reasons": risk_reasons,
            "risk_trigger_sample": risk_triggers[:20],
        }
    elif artifact_type == "performance_leaderboard":
        payload["detail"] = _json.read_run_json(
            run_dir,
            run_dir / "performance_leaderboard.json",
        )
    elif artifact_type == "sb3_smoke":
        detail = _json.read_run_json(run_dir, run_dir / "sb3_smoke_summary.json")
        payload["detail"] = detail
        live_value = detail.get("live_events")
        live_summary = (
            cast(dict[str, JsonValue], live_value)
            if isinstance(live_value, dict)
            else None
        )
        if live_summary is None:
            for file_name in _files.LIVE_SUMMARY_FILE_NAMES:
                summary_path = run_dir / file_name
                if _files._is_run_file(run_dir, summary_path):
                    live_summary = _json.read_run_json(run_dir, summary_path)
                    break
        if live_summary is not None:
            payload["live_events"] = live_summary
        models = _json.json_objects(detail.get("models"))
        summary = _json.json_object(payload.get("summary"))
        best_model = summary.get("best_model")
        selected_model = next((row for row in models if row.get("model") == best_model), models[0] if models else {})
        payload["model"] = {
            "model_type": f"stable_baselines3_{selected_model.get('algorithm', 'sb3')}",
            "feature_columns": summary.get("feature_columns", []),
            "train_summary": selected_model,
        }
    elif artifact_type in _json.DISCOVERY_ARTIFACT_TYPES:
        payload["detail"] = verified_detail or {}
    elif artifact_type == "contextual_bandit":
        payload["detail"] = _json.read_run_json(run_dir, run_dir / "eval_summary.json")
        model_path = run_dir / "model.json"
        if _files._is_run_file(run_dir, model_path):
            model_payload = _json.read_run_json(run_dir, model_path)
            model = _json.json_object(model_payload.get("model"))
            payload["model"] = {
                "model_type": model.get("model_type"),
                "feature_columns": model.get("feature_columns", []),
                "train_summary": model.get("train_summary", {}),
            }
    elif artifact_type == "cost_gate":
        payload["detail"] = _json.read_run_json(run_dir, run_dir / "cost_gate_report.json")
    elif artifact_type == "baseline":
        payload["detail"] = _json.read_run_json(run_dir, run_dir / "baseline_summary.json")
    elif artifact_type == "episode_manifest":
        manifest = _json.read_run_json(run_dir, run_dir / "episode_manifest.json")
        episodes_value = manifest.get("episodes")
        episodes = (
            cast(list[JsonValue], episodes_value)
            if isinstance(episodes_value, list)
            else []
        )
        payload["detail"] = {
            "summary": manifest.get("summary", {}),
            "episode_sample": episodes[:10],
        }
    elif artifact_type == "opening_30m_rule_filter":
        payload["detail"] = _json.read_run_json(
            run_dir,
            run_dir / "opening_rule_filter_summary.json",
        )
    elif artifact_type == "opening_30m_rl_workflow":
        payload["detail"] = _opening.load_opening_workflow_detail(run_dir)
    return payload
