
"""Filesystem-backed live monitor helpers for STOM Kronos training runs."""

from __future__ import annotations

import json
import subprocess
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOTS: List[Path] = [PROJECT_ROOT / "finetune" / "outputs"]
MAX_LOG_LINES = 1000


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        return {"status": "unreadable", "error": str(exc), "path": str(path)}


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _safe_run_name(run_name: str) -> str:
    if not run_name or run_name in {".", ".."}:
        raise ValueError("run name is required")
    if any(separator in run_name for separator in ("/", "\\")):
        raise ValueError("run name must be a direct finetune output directory name")
    return run_name


def _file_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _latest_mtime(paths: Iterable[Path]) -> float:
    latest = 0.0
    for path in paths:
        latest = max(latest, _file_mtime(path))
    return latest


def _iter_run_dirs() -> Iterable[Path]:
    for root in OUTPUT_ROOTS:
        if not root.exists():
            continue
        for candidate in root.iterdir():
            if candidate.is_dir() and _is_relative_to(candidate, root):
                yield candidate


def _run_artifacts(run_dir: Path) -> Dict[str, List[Path]]:
    logs_dir = run_dir / "logs"
    progress_files = sorted(logs_dir.glob("*.progress.json")) if logs_dir.exists() else []
    manifest_files = sorted(run_dir.glob("*run_manifest.json"))
    log_files = sorted(logs_dir.glob("*.stdout.log")) if logs_dir.exists() else []
    return {"progress": progress_files, "manifest": manifest_files, "log": log_files}


def _summarize_stage(payload: Dict[str, Any], source_path: Path) -> Dict[str, Any]:
    stage = payload.get("stage") if isinstance(payload.get("stage"), dict) else {}
    progress = payload.get("progress") if isinstance(payload.get("progress"), dict) else {}
    timing = payload.get("timing") if isinstance(payload.get("timing"), dict) else {}
    paths = payload.get("paths") if isinstance(payload.get("paths"), dict) else {}
    return {
        "source_path": str(source_path),
        "updated_at": payload.get("updated_at") or payload.get("completed_at") or payload.get("created_at"),
        "status": payload.get("status", "unknown"),
        "run_name": payload.get("run_name"),
        "train_stage": payload.get("train_stage") or stage.get("name"),
        "horizon": payload.get("horizon"),
        "mode": payload.get("mode"),
        "stage_index": stage.get("index"),
        "stage_count": stage.get("count"),
        "stage_percent": stage.get("percent"),
        "overall_percent": stage.get("overall_percent"),
        "epoch": progress.get("epoch"),
        "epochs": progress.get("epochs"),
        "step": progress.get("step"),
        "total_steps": progress.get("total_steps"),
        "last_loss": (payload.get("metrics") or {}).get("last_loss") if isinstance(payload.get("metrics"), dict) else None,
        "last_validation_loss": (payload.get("metrics") or {}).get("last_validation_loss") if isinstance(payload.get("metrics"), dict) else None,
        "best_val_loss": (payload.get("metrics") or {}).get("best_val_loss") if isinstance(payload.get("metrics"), dict) else None,
        "elapsed_seconds": timing.get("elapsed_seconds"),
        "eta_seconds": timing.get("eta_seconds"),
        "samples_per_second": timing.get("samples_per_second"),
        "stdout_log": paths.get("stdout_log") or payload.get("stdout_log"),
        "last_line": payload.get("last_line"),
    }


def _manifest_as_stage(payload: Dict[str, Any], source_path: Path) -> Dict[str, Any]:
    return {
        "source_path": str(source_path),
        "updated_at": payload.get("completed_at") or payload.get("created_at"),
        "status": payload.get("status", "unknown"),
        "run_name": payload.get("run_name"),
        "train_stage": payload.get("train_stage"),
        "horizon": payload.get("horizon"),
        "mode": payload.get("mode"),
        "stage_index": payload.get("stage_index"),
        "stage_count": payload.get("stage_count"),
        "stage_percent": 100.0 if payload.get("status") == "ok" else 0.0,
        "overall_percent": 100.0 if payload.get("status") == "ok" else 0.0,
        "epoch": None,
        "epochs": None,
        "step": None,
        "total_steps": None,
        "last_loss": None,
        "last_validation_loss": None,
        "best_val_loss": None,
        "elapsed_seconds": payload.get("duration_seconds"),
        "eta_seconds": None,
        "samples_per_second": None,
        "stdout_log": payload.get("stdout_log"),
        "last_line": (payload.get("stdout_tail") or payload.get("stderr_tail") or "")[-500:],
    }


def list_training_runs(limit: int = 50) -> List[Dict[str, Any]]:
    """List known finetune output runs without reading arbitrary paths."""
    runs: List[Dict[str, Any]] = []
    for run_dir in _iter_run_dirs():
        artifacts = _run_artifacts(run_dir)
        if not artifacts["progress"] and not artifacts["manifest"] and not artifacts["log"]:
            continue
        latest = _latest_mtime(artifacts["progress"] + artifacts["manifest"] + artifacts["log"] + [run_dir])
        status = "unknown"
        overall_percent = None
        stages: List[Dict[str, Any]] = []
        for progress_file in artifacts["progress"]:
            stage = _summarize_stage(_load_json(progress_file), progress_file)
            stages.append(stage)
        if not stages:
            for manifest_file in artifacts["manifest"]:
                stages.append(_manifest_as_stage(_load_json(manifest_file), manifest_file))
        if stages:
            statuses = {str(stage.get("status")) for stage in stages}
            if "running" in statuses:
                status = "running"
            elif "failed" in statuses:
                status = "failed"
            elif statuses and statuses <= {"ok", "dry_run"}:
                status = "ok" if "ok" in statuses else "dry_run"
            elif statuses:
                status = sorted(statuses)[0]
            percents = [stage.get("overall_percent") for stage in stages if isinstance(stage.get("overall_percent"), (int, float))]
            overall_percent = max(percents) if percents else None
        runs.append(
            {
                "name": run_dir.name,
                "path": str(run_dir),
                "status": status,
                "overall_percent": overall_percent,
                "updated_at_epoch": latest,
                "updated_at": datetime.fromtimestamp(latest, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if latest else None,
                "stage_count": len(stages),
            }
        )
    runs.sort(key=lambda item: item.get("updated_at_epoch") or 0, reverse=True)
    return runs[: max(1, min(int(limit), 200))]


def resolve_run_dir(run_name: Optional[str] = None) -> Path:
    if run_name:
        safe_name = _safe_run_name(run_name)
        for root in OUTPUT_ROOTS:
            candidate = root / safe_name
            if candidate.exists() and candidate.is_dir() and _is_relative_to(candidate, root):
                return candidate
        raise FileNotFoundError(f"training run not found: {safe_name}")

    runs = list_training_runs(limit=1)
    if not runs:
        raise FileNotFoundError("no training runs found under finetune/outputs")
    return Path(str(runs[0]["path"]))


def load_training_status(run_name: Optional[str] = None) -> Dict[str, Any]:
    run_dir = resolve_run_dir(run_name)
    artifacts = _run_artifacts(run_dir)
    stages: List[Dict[str, Any]] = []
    stage_names_with_progress = set()
    for progress_file in artifacts["progress"]:
        payload = _load_json(progress_file)
        stage = _summarize_stage(payload, progress_file)
        stages.append(stage)
        if stage.get("train_stage"):
            stage_names_with_progress.add(str(stage["train_stage"]))

    for manifest_file in artifacts["manifest"]:
        payload = _load_json(manifest_file)
        stage_name = str(payload.get("train_stage") or "")
        if stage_name and stage_name in stage_names_with_progress:
            continue
        stages.append(_manifest_as_stage(payload, manifest_file))

    stages.sort(key=lambda stage: (stage.get("stage_index") is None, stage.get("stage_index") or 99, stage.get("train_stage") or ""))
    statuses = {str(stage.get("status")) for stage in stages}
    if "running" in statuses:
        status = "running"
    elif "failed" in statuses:
        status = "failed"
    elif statuses and statuses <= {"ok", "dry_run"}:
        status = "ok" if "ok" in statuses else "dry_run"
    elif statuses:
        status = sorted(statuses)[0]
    else:
        status = "unknown"
    percents = [stage.get("overall_percent") for stage in stages if isinstance(stage.get("overall_percent"), (int, float))]
    overall_percent = max(percents) if percents else 0.0
    latest_stage = max(stages, key=lambda stage: stage.get("updated_at") or "") if stages else None
    return {
        "run_name": run_dir.name,
        "run_path": str(run_dir),
        "status": status,
        "overall_percent": overall_percent,
        "stage_count": len(stages),
        "stages": stages,
        "latest_stage": latest_stage,
        "updated_at": (latest_stage or {}).get("updated_at"),
        "generated_at": _utc_now(),
    }


def _tail_lines(path: Path, line_count: int) -> List[str]:
    tail: deque[str] = deque(maxlen=max(1, min(line_count, MAX_LOG_LINES)))
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            tail.append(line.rstrip("\r\n"))
    return list(tail)


def tail_training_log(run_name: Optional[str] = None, stage: Optional[str] = None, lines: int = 200) -> Dict[str, Any]:
    run_dir = resolve_run_dir(run_name)
    line_count = max(1, min(int(lines), MAX_LOG_LINES))
    status = load_training_status(run_dir.name)
    stages: Sequence[Dict[str, Any]] = status.get("stages", [])
    selected_stage: Optional[Dict[str, Any]] = None
    if stage:
        selected_stage = next((item for item in stages if item.get("train_stage") == stage), None)
    if selected_stage is None:
        selected_stage = status.get("latest_stage") if isinstance(status.get("latest_stage"), dict) else None
    log_path: Optional[Path] = None
    if selected_stage and selected_stage.get("stdout_log"):
        candidate = Path(str(selected_stage["stdout_log"]))
        if candidate.exists() and _is_relative_to(candidate, run_dir):
            log_path = candidate
    if log_path is None:
        logs = sorted((run_dir / "logs").glob("*.stdout.log"), key=_file_mtime, reverse=True)
        log_path = logs[0] if logs else None
    if log_path is None or not log_path.exists() or not _is_relative_to(log_path, run_dir):
        return {
            "run_name": run_dir.name,
            "stage": stage,
            "log_path": None,
            "lines": [],
            "text": "",
            "error": "no stdout log found for this run",
        }
    lines_payload = _tail_lines(log_path, line_count)
    return {
        "run_name": run_dir.name,
        "stage": (selected_stage or {}).get("train_stage") or stage,
        "log_path": str(log_path),
        "lines": lines_payload,
        "text": "\n".join(lines_payload),
    }


def _number_or_none(value: str) -> Optional[float]:
    value = value.strip()
    if not value or value.upper() in {"N/A", "[NOT SUPPORTED]", "NOT SUPPORTED"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def query_gpu_status(timeout_seconds: int = 5) -> Dict[str, Any]:
    """Return current NVIDIA GPU utilization/power when nvidia-smi is available."""
    fields = [
        "index",
        "name",
        "utilization.gpu",
        "memory.used",
        "memory.total",
        "power.draw",
        "power.limit",
        "temperature.gpu",
    ]
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                f"--query-gpu={','.join(fields)}",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
    except Exception as exc:
        return {"available": False, "error": str(exc), "gpus": [], "generated_at": _utc_now()}

    if completed.returncode != 0:
        return {
            "available": False,
            "error": completed.stderr.strip() or completed.stdout.strip(),
            "gpus": [],
            "generated_at": _utc_now(),
        }

    gpus: List[Dict[str, Any]] = []
    for row in completed.stdout.splitlines():
        parts = [part.strip() for part in row.split(",")]
        if len(parts) < len(fields):
            continue
        gpu = {
            "index": int(_number_or_none(parts[0]) or 0),
            "name": parts[1],
            "utilization_gpu_percent": _number_or_none(parts[2]),
            "memory_used_mib": _number_or_none(parts[3]),
            "memory_total_mib": _number_or_none(parts[4]),
            "power_draw_watts": _number_or_none(parts[5]),
            "power_limit_watts": _number_or_none(parts[6]),
            "temperature_c": _number_or_none(parts[7]),
        }
        if gpu["memory_used_mib"] is not None and gpu["memory_total_mib"]:
            gpu["memory_used_percent"] = round(gpu["memory_used_mib"] / gpu["memory_total_mib"] * 100.0, 2)
        else:
            gpu["memory_used_percent"] = None
        gpus.append(gpu)

    power_values = [gpu["power_draw_watts"] for gpu in gpus if gpu["power_draw_watts"] is not None]
    total_power = sum(power_values) if power_values else None
    return {
        "available": bool(gpus),
        "gpus": gpus,
        "total_power_draw_watts": total_power,
        "generated_at": _utc_now(),
    }
