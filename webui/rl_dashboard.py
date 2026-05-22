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
from typing import Any, Dict, Iterable, List, Optional, Tuple


RL_RUN_ROOTS = [Path(__file__).resolve().parent / "rl_runs"]
MAX_TABLE_LIMIT = 5000


ARTIFACT_SIGNATURES = (
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
}

ROOT_TABLE_CANDIDATES = {
    "actions": ("actions.csv",),
    "trades": ("trades.csv",),
    "equity": ("equity_curve.csv", "equity.csv"),
    "episodes": ("episodes.csv",),
    "summary": ("baseline_summary.csv", "gate_summary.csv"),
    "manifest": ("episode_manifest.csv",),
    "scenario": ("scenario_summary.csv",),
    "rolling": ("rolling_folds.csv",),
    "gate": ("gate_summary.csv",),
}


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


def _coerce_scalar(value: str) -> Any:
    if value == "":
        return None
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        if any(ch in value for ch in (".", "e", "E")):
            return float(value)
        return int(value)
    except ValueError:
        return value


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
    if artifact_type == "contextual_bandit":
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
