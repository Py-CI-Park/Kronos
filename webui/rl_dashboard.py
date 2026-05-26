"""Read-only dashboard helpers for independent STOM RL artifacts.

The RL lab writes runtime artifacts under ``webui/rl_runs``.  This module gives
the Flask app a small, path-safe API surface for listing runs and reading JSON
or CSV artifacts without coupling the web layer to training code.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
WEBUI_ROOT = Path(__file__).resolve().parent
RL_RUN_ROOTS = [WEBUI_ROOT / "rl_runs"]
MAX_TABLE_LIMIT = 5000


ARTIFACT_SIGNATURES = (
    ("portfolio_paper", "portfolio_paper_summary.json"),
    ("performance_leaderboard", "performance_leaderboard.json"),
    ("sb3_smoke", "sb3_smoke_summary.json"),
    ("contextual_bandit", "eval_summary.json"),
    ("cost_gate", "cost_gate_report.json"),
    ("baseline", "baseline_summary.json"),
    ("episode_manifest", "episode_manifest.json"),
)

TABLE_ALIASES = {
    "action": "actions",
    "actions": "actions",
    "trade": "trades",
    "trades": "trades",
    "equity": "equity",
    "equity_curve": "equity",
    "episodes": "episodes",
    "episode": "episodes",
    "summary": "summary",
    "manifest": "manifest",
    "scenario": "scenario",
    "scenarios": "scenario",
    "rolling": "rolling",
    "folds": "rolling",
    "gate": "gate",
    "cost_gate": "gate",
    "leaderboard": "leaderboard",
    "performance": "leaderboard",
    "performance_leaderboard": "leaderboard",
    "nav": "nav",
    "nav_curve": "nav",
    "decision": "decisions",
    "decisions": "decisions",
    "position": "decisions",
    "positions": "decisions",
    "candidate": "candidates",
    "candidates": "candidates",
    "portfolio_fold": "portfolio_folds",
    "portfolio_folds": "portfolio_folds",
    "event": "events",
    "events": "events",
    "live": "events",
    "live_events": "events",
}

ROOT_TABLE_CANDIDATES = {
    "actions": ("actions.csv",),
    "trades": ("trades.csv",),
    "equity": ("equity_curve.csv", "equity.csv"),
    "episodes": ("episodes.csv",),
    "summary": ("sb3_smoke_summary.csv", "baseline_summary.csv", "gate_summary.csv"),
    "manifest": ("episode_manifest.csv",),
    "scenario": ("scenario_summary.csv",),
    "rolling": ("rolling_folds.csv",),
    "gate": ("gate_summary.csv",),
    "leaderboard": ("performance_leaderboard.csv", "leaderboard.csv"),
    "nav": ("nav.csv",),
    "decisions": ("decisions.csv",),
    "candidates": ("candidates.csv",),
    "portfolio_folds": ("portfolio_walk_forward_folds.csv",),
}

LIVE_EVENT_FILE_NAMES = ("rl_live_events.jsonl", "live_events.jsonl", "events.jsonl")
LIVE_SUMMARY_FILE_NAMES = ("rl_live_summary.json", "live_summary.json")


def _safe_direct_child_name(name: str, *, label: str) -> str:
    value = str(name or "").strip()
    if not value:
        raise ValueError(f"{label} is required")
    path = Path(value)
    if path.is_absolute() or value in {".", ".."} or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Invalid {label}: {name!r}")
    if "/" in value or "\\" in value:
        raise ValueError(f"{label} must be a direct child name: {name!r}")
    return value


def _utc_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def _coerce_scalar(value: str) -> Any:
    if value == "":
        return None
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    # Preserve zero-padded codes (e.g. Korean stock symbol ``000250``) as strings:
    # coercing to int would strip the leading zeros and display ``250``.
    if len(value) > 1 and value[0] == "0" and value.isdigit():
        return value
    try:
        if any(ch in value for ch in (".", "e", "E")):
            return float(value)
        return int(value)
    except ValueError:
        return value


def _float_or_zero(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int_or_zero(value: Any) -> int:
    return int(_float_or_zero(value))


def _read_csv_rows(path: Path, *, limit: int) -> Tuple[List[Dict[str, Any]], bool]:
    limit = max(0, min(int(limit), MAX_TABLE_LIMIT))
    rows: List[Dict[str, Any]] = []
    truncated = False
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            if idx >= limit:
                truncated = True
                break
            rows.append({key: _coerce_scalar(value) for key, value in row.items()})
    return rows, truncated


def _detect_artifact_type(run_dir: Path) -> str:
    for artifact_type, file_name in ARTIFACT_SIGNATURES:
        if (run_dir / file_name).is_file():
            return artifact_type
    return "unknown"


def _find_json_summary(run_dir: Path, artifact_type: str) -> Dict[str, Any]:
    if artifact_type == "portfolio_paper":
        payload = _read_json(run_dir / "portfolio_paper_summary.json")
        summary = dict(payload.get("summary", {}))
        config = payload.get("config", {})
        if isinstance(config, dict):
            summary.setdefault("cost_bps", config.get("cost_bps"))
            summary.setdefault("max_positions", config.get("max_positions"))
            summary.setdefault("top_k_candidates", config.get("top_k_candidates"))
        return summary
    if artifact_type == "performance_leaderboard":
        payload = _read_json(run_dir / "performance_leaderboard.json")
        return dict(payload.get("summary", {}))
    if artifact_type == "sb3_smoke":
        payload = _read_json(run_dir / "sb3_smoke_summary.json")
        summary = dict(payload.get("summary", {}))
        live_summary = payload.get("live_events")
        if isinstance(live_summary, dict):
            summary.setdefault("live_event_count", live_summary.get("event_count"))
            summary.setdefault("live_event_phases", live_summary.get("phases"))
        else:
            for file_name in LIVE_SUMMARY_FILE_NAMES:
                summary_path = run_dir / file_name
                if summary_path.is_file():
                    file_summary = _read_json(summary_path)
                    summary.setdefault("live_event_count", file_summary.get("event_count"))
                    summary.setdefault("live_event_phases", file_summary.get("phases"))
                    break
        models = payload.get("models", [])
        best_model = summary.get("best_model")
        selected_model = next((row for row in models if row.get("model") == best_model), models[0] if models else {})
        summary.setdefault(
            "max_training_timesteps",
            max((_int_or_zero(row.get("training_timesteps")) for row in models), default=0),
        )
        for key in (
            "avg_episode_net_return_pct",
            "trade_count",
            "cost_bps",
            "slippage_bps",
            "passes_cost_gate",
        ):
            if key in selected_model:
                summary.setdefault(key, selected_model[key])
        return summary
    if artifact_type == "contextual_bandit":
        payload = _read_json(run_dir / "eval_summary.json")
        return dict(payload.get("eval_summary", payload.get("summary", {})))
    if artifact_type == "cost_gate":
        payload = _read_json(run_dir / "cost_gate_report.json")
        return dict(payload.get("summary", {}))
    if artifact_type == "baseline":
        payload = _read_json(run_dir / "baseline_summary.json")
        return dict(payload.get("summary", {}))
    if artifact_type == "episode_manifest":
        summary_path = run_dir / "episode_summary.json"
        payload = _read_json(summary_path if summary_path.is_file() else run_dir / "episode_manifest.json")
        return dict(payload.get("summary", payload))
    return {}


def _artifact_files(run_dir: Path) -> List[Dict[str, Any]]:
    files = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(run_dir).as_posix()
            files.append(
                {
                    "name": rel,
                    "suffix": path.suffix.lower(),
                    "size_bytes": path.stat().st_size,
                    "modified_at": _utc_mtime(path),
                }
            )
    return files


def _baseline_policies(run_dir: Path) -> List[str]:
    policies = []
    for child in sorted(run_dir.iterdir()):
        if child.is_dir() and any((child / file_name).is_file() for file_name in ("actions.csv", "trades.csv", "equity.csv", "episodes.csv")):
            policies.append(child.name)
    return policies


def _run_record(run_dir: Path) -> Dict[str, Any]:
    artifact_type = _detect_artifact_type(run_dir)
    summary = _find_json_summary(run_dir, artifact_type)
    return {
        "name": run_dir.name,
        "artifact_type": artifact_type,
        "modified_at": _utc_mtime(run_dir),
        "summary": summary,
        "policies": _baseline_policies(run_dir) if artifact_type == "baseline" else [],
    }


def iter_run_dirs() -> Iterable[Path]:
    seen = set()
    for root in RL_RUN_ROOTS:
        root = Path(root)
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if child.is_dir() and child.name not in seen:
                seen.add(child.name)
                yield child


def list_rl_runs(limit: int = 50) -> List[Dict[str, Any]]:
    """List available independent RL runtime artifact directories."""

    runs = sorted(iter_run_dirs(), key=lambda path: path.stat().st_mtime, reverse=True)
    return [_run_record(path) for path in runs[: max(0, int(limit))]]


def resolve_run_dir(run_name: str) -> Path:
    safe_name = _safe_direct_child_name(run_name, label="run")
    for root in RL_RUN_ROOTS:
        candidate = Path(root) / safe_name
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(f"RL run not found: {run_name}")


def load_rl_run(run_name: str) -> Dict[str, Any]:
    """Load a run detail payload without reading large CSV tables."""

    run_dir = resolve_run_dir(run_name)
    artifact_type = _detect_artifact_type(run_dir)
    payload: Dict[str, Any] = {
        **_run_record(run_dir),
        "artifacts": _artifact_files(run_dir),
    }
    if artifact_type == "portfolio_paper":
        signature = _read_json(run_dir / "portfolio_paper_summary.json")
        wf_report_path = run_dir / "portfolio_walk_forward_report.json"
        walk_forward = _read_json(wf_report_path) if wf_report_path.is_file() else {}
        risk_path = run_dir / "risk_triggers.json"
        risk_payload = _read_json(risk_path) if risk_path.is_file() else {}
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
        payload["detail"] = _read_json(run_dir / "performance_leaderboard.json")
    elif artifact_type == "sb3_smoke":
        payload["detail"] = _read_json(run_dir / "sb3_smoke_summary.json")
        live_summary = payload["detail"].get("live_events")
        if not isinstance(live_summary, dict):
            for file_name in LIVE_SUMMARY_FILE_NAMES:
                summary_path = run_dir / file_name
                if summary_path.is_file():
                    live_summary = _read_json(summary_path)
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
    elif artifact_type == "contextual_bandit":
        payload["detail"] = _read_json(run_dir / "eval_summary.json")
        model_path = run_dir / "model.json"
        if model_path.is_file():
            model_payload = _read_json(model_path)
            model = model_payload.get("model", {})
            payload["model"] = {
                "model_type": model.get("model_type"),
                "feature_columns": model.get("feature_columns", []),
                "train_summary": model.get("train_summary", {}),
            }
    elif artifact_type == "cost_gate":
        payload["detail"] = _read_json(run_dir / "cost_gate_report.json")
    elif artifact_type == "baseline":
        payload["detail"] = _read_json(run_dir / "baseline_summary.json")
    elif artifact_type == "episode_manifest":
        manifest = _read_json(run_dir / "episode_manifest.json")
        payload["detail"] = {"summary": manifest.get("summary", {}), "episode_sample": manifest.get("episodes", [])[:10]}
    return payload


def _live_events_path(run_dir: Path) -> Optional[Path]:
    for file_name in LIVE_EVENT_FILE_NAMES:
        path = run_dir / file_name
        if path.is_file():
            return path
    return None


def _read_jsonl_rows(path: Path, *, limit: int) -> Tuple[List[Dict[str, Any]], bool]:
    limit = max(0, min(int(limit), MAX_TABLE_LIMIT))
    if limit == 0:
        return [], False
    lines = path.read_text(encoding="utf-8").splitlines()
    truncated = len(lines) > limit
    rows: List[Dict[str, Any]] = []
    for line in reversed(lines):
        if len(rows) >= limit:
            break
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    rows.reverse()
    return rows, truncated


def _normalize_table(table_name: str) -> str:
    table = str(table_name or "").strip().lower().replace("-", "_")
    if table not in TABLE_ALIASES:
        raise ValueError(f"Unknown RL table: {table_name}")
    return TABLE_ALIASES[table]


def _read_policy_table(run_dir: Path, table: str, policy: Optional[str], limit: int) -> Dict[str, Any]:
    file_name = "equity.csv" if table == "equity" else f"{table}.csv"
    policies = [policy] if policy else _baseline_policies(run_dir)
    rows: List[Dict[str, Any]] = []
    truncated = False
    for policy_name in policies:
        safe_policy = _safe_direct_child_name(policy_name, label="policy")
        path = run_dir / safe_policy / file_name
        if not path.is_file():
            if policy:
                raise FileNotFoundError(f"Baseline table not found: {safe_policy}/{file_name}")
            continue
        remaining = max(0, min(int(limit), MAX_TABLE_LIMIT) - len(rows))
        table_rows, table_truncated = _read_csv_rows(path, limit=remaining)
        rows.extend(table_rows)
        truncated = truncated or table_truncated
        if len(rows) >= min(int(limit), MAX_TABLE_LIMIT):
            truncated = truncated or table_truncated
            break
    return {"rows": rows, "row_count": len(rows), "truncated": truncated, "policies": policies}


def load_rl_table(run_name: str, table_name: str, *, policy: Optional[str] = None, limit: int = 500) -> Dict[str, Any]:
    """Load a CSV table for a run with path-safe table/policy handling."""

    run_dir = resolve_run_dir(run_name)
    artifact_type = _detect_artifact_type(run_dir)
    table = _normalize_table(table_name)
    limit = max(0, min(int(limit), MAX_TABLE_LIMIT))

    if table == "events":
        path = _live_events_path(run_dir)
        if path is None:
            return {
                "run": run_name,
                "artifact_type": artifact_type,
                "table": table,
                "policy": policy,
                "source_file": None,
                "rows": [],
                "row_count": 0,
                "truncated": False,
                "message": "live event log is not available for this run",
            }
        rows, truncated = _read_jsonl_rows(path, limit=limit)
        return {
            "run": run_name,
            "artifact_type": artifact_type,
            "table": table,
            "policy": policy,
            "source_file": path.name,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
        }

    if artifact_type == "baseline" and table in {"actions", "trades", "equity", "episodes"}:
        payload = _read_policy_table(run_dir, table, policy, limit)
        payload.update({"run": run_name, "artifact_type": artifact_type, "table": table, "policy": policy})
        return payload

    for file_name in ROOT_TABLE_CANDIDATES.get(table, ()):
        path = run_dir / file_name
        if path.is_file():
            rows, truncated = _read_csv_rows(path, limit=limit)
            return {
                "run": run_name,
                "artifact_type": artifact_type,
                "table": table,
                "policy": policy,
                "source_file": file_name,
                "rows": rows,
                "row_count": len(rows),
                "truncated": truncated,
            }
    raise FileNotFoundError(f"RL table not found for run={run_name!r}, table={table!r}")


def load_rl_cost_gate(run_name: str, *, limit: int = 500) -> Dict[str, Any]:
    """Load cost-gate summary and compact CSV tables for a cost-gate run."""

    run_dir = resolve_run_dir(run_name)
    report_path = run_dir / "cost_gate_report.json"
    if not report_path.is_file():
        raise FileNotFoundError(f"cost_gate_report.json not found for run: {run_name}")
    report = _read_json(report_path)
    return {
        "run": run_name,
        "artifact_type": _detect_artifact_type(run_dir),
        "summary": report.get("summary", {}),
        "gate": load_rl_table(run_name, "gate", limit=limit),
        "scenario": load_rl_table(run_name, "scenario", limit=limit),
        "rolling": load_rl_table(run_name, "rolling", limit=limit),
    }


def load_rl_events(run_name: str, *, limit: int = 500) -> Dict[str, Any]:
    """Load realtime RL JSONL event tail for a run."""

    return load_rl_table(run_name, "events", limit=limit)


def _criteria_progress(criteria: Sequence[Tuple[str, bool, str]]) -> Tuple[int, List[Dict[str, Any]]]:
    rows = [{"label": label, "passed": bool(passed), "evidence": evidence} for label, passed, evidence in criteria]
    if not rows:
        return 0, rows
    passed_count = sum(1 for row in rows if row["passed"])
    return int(round((passed_count / len(rows)) * 100)), rows


def _latest_sb3_details() -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    details: List[Dict[str, Any]] = []
    for run in list_rl_runs(limit=200):
        if run.get("artifact_type") != "sb3_smoke":
            continue
        try:
            detail = load_rl_run(str(run["name"]))
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            continue
        models = detail.get("detail", {}).get("models", [])
        max_timesteps = max((_int_or_zero(row.get("training_timesteps")) for row in models), default=0)
        detail["max_training_timesteps"] = max_timesteps
        details.append(detail)
    details.sort(key=lambda row: int(row.get("max_training_timesteps") or 0), reverse=True)
    return details, details[0] if details else None


def _has_model_file(detail: Optional[Mapping[str, Any]], algorithm: str) -> bool:
    if not detail:
        return False
    model_files = detail.get("detail", {}).get("artifacts", {}).get("model_files", {})
    path = model_files.get(algorithm) if isinstance(model_files, dict) else None
    return bool(path and _repo_path(str(path)).is_file())


def load_rl_progress() -> Dict[str, Any]:
    """Return page-level STOM RL completion progress for the dashboard."""

    runs = list_rl_runs(limit=200)
    run_types = {str(run.get("artifact_type")) for run in runs}
    run_names = {str(run.get("name")) for run in runs}
    sb3_details, latest_sb3 = _latest_sb3_details()
    latest_sb3_summary = latest_sb3.get("summary", {}) if latest_sb3 else {}
    latest_models = latest_sb3.get("detail", {}).get("models", []) if latest_sb3 else []
    latest_algorithms = {str(row.get("algorithm")) for row in latest_models}
    max_timesteps = _int_or_zero(latest_sb3.get("max_training_timesteps")) if latest_sb3 else 0

    leaderboard_detail = next((run for run in runs if run.get("artifact_type") == "performance_leaderboard"), None)
    leaderboard_payload: Dict[str, Any] = {}
    leaderboard_rows: List[Dict[str, Any]] = []
    if leaderboard_detail:
        try:
            leaderboard_payload = load_rl_run(str(leaderboard_detail["name"]))
            leaderboard_rows = list(leaderboard_payload.get("detail", {}).get("leaderboard", []))
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            leaderboard_payload = {}
            leaderboard_rows = []
    leaderboard_models = {str(row.get("model")) for row in leaderboard_rows}

    docs_ready = _repo_path("docs/stom_rl_realtime_learning_dashboard_implementation_2026-05-23.md").is_file()
    completion_doc_ready = _repo_path("docs/stom_rl_page100_completion_report_2026-05-24.md").is_file()

    page_specs = [
        (
            "RL Lab 개요",
            [
                ("run 목록 조회", bool(runs), f"{len(runs)} runs"),
                ("baseline/contextual/cost/SB3/leaderboard 유형", {"baseline", "contextual_bandit", "cost_gate", "sb3_smoke", "performance_leaderboard"}.issubset(run_types), ",".join(sorted(run_types))),
                ("상세 artifact 조회", bool(leaderboard_payload or latest_sb3), "load_rl_run available"),
            ],
        ),
        (
            "실시간 RL",
            [
                ("live event log", int(latest_sb3_summary.get("live_event_count") or 0) > 0, str(latest_sb3_summary.get("live_event_count") or 0)),
                ("DQN/PPO event", {"dqn", "ppo"}.issubset(latest_algorithms), ",".join(sorted(latest_algorithms))),
                ("50k short run", max_timesteps >= 50_000, str(max_timesteps)),
            ],
        ),
        (
            "실제 딥러닝 학습",
            [
                ("check_env 통과", bool(latest_sb3_summary.get("check_env_passed")), str(latest_sb3_summary.get("check_env_passed"))),
                ("CUDA 학습 확인", bool(latest_sb3_summary.get("cuda_available")), str(latest_sb3_summary.get("cuda_available"))),
                ("DQN/PPO 모델 파일", _has_model_file(latest_sb3, "dqn") and _has_model_file(latest_sb3, "ppo"), latest_sb3.get("name", "-") if latest_sb3 else "-"),
            ],
        ),
        (
            "Performance Leaderboard",
            [
                ("leaderboard artifact", "performance_leaderboard" in run_types, leaderboard_detail.get("name", "-") if leaderboard_detail else "-"),
                ("DQN/PPO short 모델 반영", {"dqn_50k", "ppo_50k"}.issubset(leaderboard_models), ",".join(sorted(leaderboard_models))),
                ("row count", int(leaderboard_payload.get("summary", {}).get("row_count") or len(leaderboard_rows)) >= 10, str(len(leaderboard_rows))),
            ],
        ),
        (
            "Artifacts / Models",
            [
                ("summary/csv/jsonl", bool(latest_sb3 and {"sb3_smoke_summary.json", "sb3_smoke_summary.csv", "rl_live_events.jsonl"}.issubset({Path(row.get("name", "")).name for row in latest_sb3.get("artifacts", [])})), latest_sb3.get("name", "-") if latest_sb3 else "-"),
                ("DQN zip", _has_model_file(latest_sb3, "dqn"), "dqn_model.zip"),
                ("PPO zip", _has_model_file(latest_sb3, "ppo"), "ppo_model.zip"),
            ],
        ),
        (
            "Docs / 운영 경계",
            [
                ("구현 문서", docs_ready, "implementation doc"),
                ("완료 보고 문서", completion_doc_ready, "page100 report"),
                ("실주문 분리", True, "read-only historical replay / smoke-short training"),
            ],
        ),
    ]

    pages: List[Dict[str, Any]] = []
    for page, criteria in page_specs:
        progress_pct, criteria_rows = _criteria_progress(criteria)
        pages.append(
            {
                "page": page,
                "progress_pct": progress_pct,
                "status": "complete" if progress_pct == 100 else "in_progress",
                "criteria": criteria_rows,
            }
        )

    overall_progress = int(round(sum(int(page["progress_pct"]) for page in pages) / len(pages))) if pages else 0
    return {
        "mode": "stom_rl_page_progress",
        "overall_progress_pct": overall_progress,
        "status": "complete" if overall_progress == 100 else "in_progress",
        "pages": pages,
        "evidence": {
            "run_count": len(runs),
            "run_names": sorted(run_names),
            "latest_sb3_run": latest_sb3.get("name") if latest_sb3 else None,
            "max_sb3_training_timesteps": max_timesteps,
            "leaderboard_models": sorted(leaderboard_models),
        },
    }
