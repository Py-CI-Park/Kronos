"""Read-only V6 platform readiness API."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from flask import Blueprint, Response, g, has_request_context, request

WEBUI_ROOT: Final = Path(__file__).resolve().parent
REPO_ROOT: Final = WEBUI_ROOT.parent
MANIFEST_PATH: Final = REPO_ROOT / "docs" / "kronos_v6_universe_manifest_2026-07-19.json"
PREREG_PATH: Final = REPO_ROOT / "docs" / "kronos_v6_prereg_h1_2026-07-19.json"
RUNS_ROOT: Final = WEBUI_ROOT / "rl_runs" / "v6_daily_h1"
M3E_CUSTODY_ROOT: Final = WEBUI_ROOT / "rl_runs" / "v8_daily_m3e_custody"
AUDIT_PATH: Final = WEBUI_ROOT / "rl_runs" / "daily_ohlcv_db_summary" / "v6_universe_audit.json"
DAILY_DB_PATH: Final = REPO_ROOT / "_database" / "Stock_Database_ohlcv_1day.db"
FIVEMIN_DB_PATH: Final = REPO_ROOT / "_database" / "Stock_Database_ohlcv_5min.db"
INDEX_ARTIFACT_DIR: Final = REPO_ROOT / "artifacts" / "korean_index"
INDEX_BLOCKER: Final = "BLOCKED_INDEX_SERIES_SOURCE"
INDEX_BLOCKER_REASON: Final = "KRX credentials required for pykrx collection"
DOCS_ROOT: Final = REPO_ROOT / "docs"
PREREG_GLOBS: Final = ("kronos_v*_prereg_*.json", "kronos_v6_prereg_*.json")
RESEARCH_DOC_RE: Final = re.compile(r"^kronos_v[0-9][0-9a-z_\-]*\.(md|json)$")
DOC_NAME_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,120}$")
INDEX_MARKETS: Final = ("KOSDAQ", "KOSPI")
INDEX_NORMALIZED_GLOB: Final = "korean-index-*-normalized-*.json"
_INDEX_OVERLAY_CACHE: dict[str, tuple[str, dict[str, Any]]] = {}
_INDEX_OVERLAY_CACHE_LIMIT: Final = 64
_EVENT_TAIL_CHUNK_BYTES: Final = 64 * 1024
_EVENT_TAIL_MAX_BYTES: Final = 1024 * 1024
_EVENT_TAIL_MAX_EVENTS: Final = 50
SIX_FALSE_LOCKS: Final = {
    "promotion_allowed": False,
    "model_build_allowed": False,
    "paper_forward_allowed": False,
    "live_broker_order_allowed": False,
    "profitability_claim_allowed": False,
    "go_summary_allowed": False,
}
ALL_ROUTE_METHODS: Final = ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
RUN_ID_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,80}$")
PROJECT_ID_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,80}$")
PROJECT_REPORT_SCHEMA: Final = "kronos_v7_project_report.v2"
KNOWN_V7_REPORT_SCHEMA: Final = "kronos_v7_report.v1"
TYPE1_REPLACEMENT_IDENTITY: Final = {
    "authority_id": "type1-krx-authority-20260724-004",
    "dataset_id": "type1-close-20260803-005",
    "train_id": "type1-public-005",
    "train_run_id": "train_type1-public-005",
    "custody_uid": "type1-fresh-oos-20260803-005",
}
TYPE1_MAX_OBJECT_BYTES: Final = 8 * 1024 * 1024
TYPE1_MAX_CATALOG_EVENTS: Final = 256
TYPE1_PRESERVED_ATTEMPTS: Final = (
    ("type1-close-20260803-001", "type1-public-001", "train_type1-public-001", "INELIGIBLE_BLOCKED"),
    ("type1-close-20260803-002", "type1-public-002", "train_type1-public-002", "INELIGIBLE_BLOCKED"),
    ("type1-close-20260803-003", "type1-public-003", "train_type1-public-003", "NON_MATERIALIZED_INELIGIBLE"),
    ("type1-close-20260803-004", "type1-public-004", "train_type1-public-004", "MATERIALIZED_NOT_TRAINED_QUARANTINED"),
)


def _response(payload: Mapping[str, Any], status_code: int = 200) -> Response:
    return Response(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), status=status_code, mimetype="application/json")


def _error(status_code: int, code: str) -> Response:
    return _response({"status": "ERROR", "error": {"code": code}}, status_code)


def _method_not_allowed() -> Response:
    response = _error(405, "METHOD_NOT_ALLOWED")
    response.headers["Allow"] = "GET"
    return response


def _read_json(path: Path) -> Mapping[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return dict(value) if isinstance(value, Mapping) else None


def _manifest() -> tuple[Mapping[str, Any] | None, bytes | None]:
    try:
        raw = MANIFEST_PATH.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, None
    if not isinstance(value, Mapping) or not isinstance(value.get("universe"), list):
        return None, None
    return dict(value), raw


def _query_limit() -> int:
    if set(request.args) - {"limit"} or len(request.args.getlist("limit")) > 1:
        raise ValueError
    raw = request.args.get("limit", "50")
    if not raw.isascii() or not raw.isdecimal():
        raise ValueError
    value = int(raw)
    if not 1 <= value <= 500:
        raise ValueError
    return value

def _run_detail_query() -> tuple[str, str]:
    if set(request.args) != {"dataset", "train"}:
        raise ValueError
    if any(len(request.args.getlist(key)) != 1 for key in ("dataset", "train")):
        raise ValueError
    dataset_run_id = request.args["dataset"]
    train_run_id = request.args["train"]
    if (
        ".." in dataset_run_id
        or ".." in train_run_id
        or RUN_ID_PATTERN.fullmatch(dataset_run_id) is None
        or RUN_ID_PATTERN.fullmatch(train_run_id) is None
    ):
        raise ValueError
    return dataset_run_id, train_run_id


def _events_tail(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read the newest JSON object events from a bounded, stable file snapshot."""
    diagnostics: dict[str, Any] = {
        "state": "MISSING",
        "invalid_line_count": 0,
        "bytes_scanned": 0,
        "truncated": False,
    }
    try:
        with path.open("rb") as event_file:
            snapshot_size = event_file.seek(0, 2)
            if snapshot_size == 0:
                diagnostics["state"] = "EMPTY"
                return [], diagnostics
            start = max(0, snapshot_size - _EVENT_TAIL_MAX_BYTES)
            diagnostics["truncated"] = start > 0
            event_file.seek(start)
            chunks: list[bytes] = []
            remaining = snapshot_size - start
            while remaining:
                chunk = event_file.read(min(_EVENT_TAIL_CHUNK_BYTES, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
    except OSError:
        return [], diagnostics

    snapshot = b"".join(chunks)
    diagnostics["bytes_scanned"] = len(snapshot)
    if start:
        newline = snapshot.find(b"\n")
        snapshot = snapshot[newline + 1:] if newline >= 0 else b""
    events: list[dict[str, Any]] = []
    for line in snapshot.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            diagnostics["invalid_line_count"] += 1
            continue
        if not isinstance(event, Mapping):
            diagnostics["invalid_line_count"] += 1
            continue
        events.append(dict(event))

    events = events[-_EVENT_TAIL_MAX_EVENTS:]
    if events and diagnostics["invalid_line_count"] == 0 and not diagnostics["truncated"]:
        diagnostics["state"] = "PRESENT"
    elif events:
        diagnostics["state"] = "PARTIAL"
    else:
        diagnostics["state"] = "CORRUPT"
    return events, diagnostics


def _sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None
def _request_snapshot(key: str, factory: Any) -> Any:
    """Cache deterministic artifact indexes for the lifetime of one request."""
    if not has_request_context():
        return factory()
    snapshots = getattr(g, "_v6_artifact_snapshots", None)
    if snapshots is None:
        snapshots = {}
        g._v6_artifact_snapshots = snapshots
    if key not in snapshots:
        snapshots[key] = factory()
    return snapshots[key]



def _run_states(manifest: Mapping[str, Any]) -> dict[str, str]:
    test = manifest.get("test")
    test_state = str(test.get("state", "MISSING")) if isinstance(test, Mapping) else "MISSING"
    if manifest.get("schema_version") == "kronos_v8_m3e_validation_run.v1":
        has_members = isinstance(manifest.get("members"), list) and len(manifest["members"]) == 5
        has_validation = isinstance(manifest.get("ensemble"), Mapping) and isinstance(manifest.get("jackknives"), Mapping)
        training_state = "COMPLETE" if has_members else "MISSING"
        validation_state = "REUSED_VALIDATION_COMPLETE" if has_validation else "NOT_RECORDED"
    else:
        per_seed = manifest.get("per_seed")
        training_state = str(manifest.get("state", "MISSING"))
        validation_state = "PRESENT" if isinstance(per_seed, (list, Mapping)) and per_seed else "NOT_RECORDED"
    return {
        "training_state": training_state,
        "validation_state": validation_state,
        "test_state": test_state,
        "evaluation_state": "TEST_NOT_RUN" if test_state == "NOT_RUN" else f"TEST_{test_state}",
    }


def _prereg_path(prereg_ref: Mapping[str, Any]) -> Path | None:
    prereg_id = prereg_ref.get("id")
    prereg_sha = prereg_ref.get("sha256")
    if not isinstance(prereg_id, str) or not isinstance(prereg_sha, str):
        return None
    try:
        paths = sorted({path for pattern in PREREG_GLOBS for path in DOCS_ROOT.glob(pattern) if path.is_file()})
    except OSError:
        return None
    for path in paths:
        prereg = _read_json(path)
        if prereg and prereg.get("prereg_id") == prereg_id and _sha256_file(path) == prereg_sha:
            return path
    return None


def _m3e_report_chain(run_dir: Path, report_manifest: Mapping[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    run_manifest_path = run_dir / "run_manifest.json"
    run_manifest = _read_json(run_manifest_path)
    if report_manifest.get("schema_version") != "kronos_v8_m3e_report.v1":
        reasons.append("REPORT_SCHEMA_MISMATCH")
    if report_manifest.get("test_state") != "NOT_RUN":
        reasons.append("REPORT_TEST_STATE_MISMATCH")
    if report_manifest.get("verdict") != "NO_GO":
        reasons.append("REPORT_VERDICT_MISMATCH")
    if run_manifest is None:
        reasons.append("RUN_MANIFEST_MISSING")
        return "CHAIN_INVALID", reasons
    if report_manifest.get("run_manifest_sha256") != _sha256_file(run_manifest_path):
        reasons.append("RUN_MANIFEST_SHA_MISMATCH")
    if run_manifest.get("schema_version") != "kronos_v8_m3e_validation_run.v1":
        reasons.append("RUN_MANIFEST_SCHEMA_MISMATCH")
    run_test = run_manifest.get("test")
    run_test_state = run_test.get("state") if isinstance(run_test, Mapping) else None
    if not isinstance(run_test, Mapping) or dict(run_test) != {"state": "NOT_RUN"}:
        reasons.append("RUN_TEST_STATE_MISMATCH")
    if report_manifest.get("test_state") != run_test_state:
        reasons.append("REPORT_RUN_TEST_STATE_CONTRADICTION")
    if run_manifest.get("false_research_locks") != SIX_FALSE_LOCKS:
        reasons.append("FALSE_RESEARCH_LOCKS_MISMATCH")
    prereg_ref = run_manifest.get("prereg")
    prereg_path = _prereg_path(prereg_ref) if isinstance(prereg_ref, Mapping) else None
    if prereg_path is None:
        reasons.append("PREREG_NOT_FOUND_OR_SHA_MISMATCH")
    elif report_manifest.get("prereg_sha256") != _sha256_file(prereg_path):
        reasons.append("PREREG_SHA_MISMATCH")
    if run_manifest.get("trainer_version") != "kronos_v8_m3e_contextual_bandit.v1":
        reasons.append("M3E_ALGORITHM_MISMATCH")
    members = run_manifest.get("members")
    if (
        run_manifest.get("seeds") != [0, 1, 2, 3, 4]
        or not isinstance(members, list)
        or len(members) != 5
        or [member.get("seed") if isinstance(member, Mapping) else None for member in members] != [0, 1, 2, 3, 4]
    ):
        reasons.append("M3E_FIVE_SEEDS_MISMATCH")
    run_verdict = run_manifest.get("verdict")
    run_verdict_value = run_verdict.get("value") if isinstance(run_verdict, Mapping) else None
    if not isinstance(run_verdict, Mapping) or run_verdict_value != "NO_GO":
        reasons.append("M3E_VERDICT_MISMATCH")
    if report_manifest.get("verdict") != run_verdict_value:
        reasons.append("REPORT_RUN_VERDICT_CONTRADICTION")
    policy = run_manifest.get("policy")
    if not isinstance(policy, Mapping) or policy.get("primary_cost_rate") != 0.0023:
        reasons.append("M3E_23BP_POLICY_MISMATCH")
    custody_uid = run_manifest.get("custody_uid")
    if not isinstance(custody_uid, str) or not custody_uid or Path(custody_uid).name != custody_uid:
        reasons.append("CUSTODY_UID_INVALID")
    else:
        custody_path = _safe_contained_file(M3E_CUSTODY_ROOT, custody_uid, "public", "train_validation_manifest.json")
        if custody_path is None:
            reasons.append("PUBLIC_CUSTODY_MANIFEST_INVALID")
        else:
            custody = _read_json(custody_path)
            if custody is None:
                reasons.append("PUBLIC_CUSTODY_MANIFEST_MISSING")
            else:
                if report_manifest.get("public_custody_manifest_sha256") != _sha256_file(custody_path):
                    reasons.append("PUBLIC_CUSTODY_MANIFEST_SHA_MISMATCH")
                public = custody.get("public_artifact")
                if not isinstance(public, Mapping) or report_manifest.get("public_custody_sha256") != public.get("sha256"):
                    reasons.append("PUBLIC_CUSTODY_SHA_MISMATCH")
                if custody.get("custody_uid") != custody_uid:
                    reasons.append("PUBLIC_CUSTODY_UID_MISMATCH")
    return ("CHAIN_OK", []) if not reasons else ("CHAIN_INVALID", reasons)


def _report_chain(run_dir: Path, report_manifest: Mapping[str, Any]) -> tuple[str, list[str]]:
    """Verify source custody while classifying source-less legacy reports."""
    if report_manifest.get("schema_version") == "kronos_v8_m3e_report.v1":
        return _m3e_report_chain(run_dir, report_manifest)
    source_hashes = report_manifest.get("source_sha256")
    locks = report_manifest.get("false_research_locks")
    if source_hashes is None and locks is None:
        return "LEGACY_UNVERIFIED", ["LEGACY_SOURCE_CUSTODY_NOT_RECORDED"]
    reasons: list[str] = []
    if not isinstance(report_manifest.get("schema_version"), str):
        reasons.append("REPORT_SCHEMA_MISSING")
    if not isinstance(source_hashes, Mapping):
        reasons.append("REPORT_SOURCE_HASHES_MISSING")
        source_hashes = {}
    run_manifest_path = run_dir / "run_manifest.json"
    run_manifest = _read_json(run_manifest_path)
    if run_manifest is None:
        reasons.append("RUN_MANIFEST_MISSING")
    else:
        if not isinstance(run_manifest.get("schema_version"), str):
            reasons.append("RUN_MANIFEST_SCHEMA_MISSING")
        if source_hashes.get("run_manifest") != _sha256_file(run_manifest_path):
            reasons.append("RUN_MANIFEST_SHA_MISMATCH")
        dataset_manifest_path = run_dir.parent / "dataset_manifest.json"
        dataset_manifest = _read_json(dataset_manifest_path)
        if dataset_manifest is None:
            reasons.append("DATASET_MANIFEST_MISSING")
        else:
            if not isinstance(dataset_manifest.get("schema_version"), str):
                reasons.append("DATASET_MANIFEST_SCHEMA_MISSING")
            if source_hashes.get("dataset_manifest") != _sha256_file(dataset_manifest_path):
                reasons.append("DATASET_MANIFEST_SHA_MISMATCH")
        prereg_ref = run_manifest.get("prereg")
        if not isinstance(prereg_ref, Mapping):
            reasons.append("PREREG_REFERENCE_MISSING")
        else:
            prereg_path = _prereg_path(prereg_ref)
            if prereg_path is None:
                reasons.append("PREREG_NOT_FOUND_OR_SHA_MISMATCH")
            elif source_hashes.get("prereg") != _sha256_file(prereg_path):
                reasons.append("PREREG_SHA_MISMATCH")
            elif not isinstance((_read_json(prereg_path) or {}).get("schema_version"), str):
                reasons.append("PREREG_SCHEMA_MISSING")
    if not isinstance(locks, Mapping) or dict(locks) != SIX_FALSE_LOCKS:
        reasons.append("FALSE_RESEARCH_LOCKS_MISMATCH")
    return ("CHAIN_OK", []) if not reasons else ("CHAIN_INVALID", reasons)
def _project_source_path(path_value: object) -> Path | None:
    """Resolve a project source only when it is a regular, non-symlinked custody file."""
    if not isinstance(path_value, str) or not path_value:
        return None
    try:
        raw_path = Path(path_value)
        candidate = raw_path if raw_path.is_absolute() else REPO_ROOT / raw_path
        resolved = candidate.resolve(strict=True)
    except (OSError, ValueError):
        return None
    for root in (DOCS_ROOT, RUNS_ROOT):
        try:
            root_resolved = root.resolve(strict=True)
            relative = candidate.relative_to(root)
            resolved.relative_to(root_resolved)
        except (OSError, ValueError):
            continue
        current = root
        try:
            for part in relative.parts:
                current = current / part
                if current.is_symlink():
                    return None
        except OSError:
            return None
        return resolved if resolved.is_file() else None
    return None


def _project_report_chain(project_id: str, project_dir: Path, manifest: Mapping[str, Any], report_bytes: bytes | None) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if manifest.get("schema_version") != PROJECT_REPORT_SCHEMA:
        reasons.append("PROJECT_REPORT_SCHEMA_MISMATCH")
    if manifest.get("project_id") != project_id:
        reasons.append("PROJECT_ID_MISMATCH")
    if not isinstance(report_bytes, bytes):
        reasons.append("PROJECT_REPORT_MISSING")
    elif manifest.get("report_sha256") != hashlib.sha256(report_bytes).hexdigest():
        reasons.append("REPORT_SHA_MISMATCH")
    if not isinstance(manifest.get("false_research_locks"), Mapping) or dict(manifest["false_research_locks"]) != SIX_FALSE_LOCKS:
        reasons.append("FALSE_RESEARCH_LOCKS_MISMATCH")
    source_hashes = manifest.get("source_sha256")
    if not isinstance(source_hashes, list) or not source_hashes:
        reasons.append("SOURCE_SHA256_MISSING")
    else:
        for source in source_hashes:
            if not isinstance(source, Mapping):
                reasons.append("SOURCE_SHA256_INVALID")
                continue
            path = _project_source_path(source.get("path"))
            recorded_sha = source.get("sha256")
            if not isinstance(source.get("label"), str) or not isinstance(recorded_sha, str) or re.fullmatch(r"[0-9a-f]{64}", recorded_sha) is None:
                reasons.append("SOURCE_SHA256_INVALID")
                continue
            if path is None:
                reasons.append("SOURCE_PATH_INVALID")
            elif _sha256_file(path) != recorded_sha:
                reasons.append("SOURCE_SHA256_MISMATCH")
    return ("CHAIN_OK", []) if not reasons else ("CHAIN_INVALID", reasons)


def _project_report_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    projects_root = RUNS_ROOT / "_projects"
    try:
        project_dirs = sorted(path for path in projects_root.iterdir() if path.is_dir() and not path.is_symlink())
    except OSError:
        return entries
    for project_dir in project_dirs:
        project_id = project_dir.name
        if PROJECT_ID_PATTERN.fullmatch(project_id) is None:
            continue
        manifest_path = project_dir / "project_report_manifest.json"
        report_path = project_dir / "project_report.html"
        if manifest_path.is_symlink() or report_path.is_symlink():
            continue
        manifest = _read_json(manifest_path)
        if manifest is None:
            continue
        try:
            report_bytes = report_path.read_bytes()
        except OSError:
            report_bytes = None
        integrity, integrity_reasons = _project_report_chain(project_id, project_dir, manifest, report_bytes)
        entries.append({
            "project_id": project_id,
            "title": manifest.get("title", "MISSING"),
            "generated_utc": manifest.get("generated_utc", "MISSING"),
            "builder_version": manifest.get("builder_version", "MISSING"),
            "report_sha256": manifest.get("report_sha256"),
            "size_bytes": len(report_bytes) if report_bytes is not None else 0,
            "cycle_count": manifest.get("cycle_count", "MISSING"),
            "run_count": manifest.get("run_count", "MISSING"),
            "verdicts": manifest.get("verdicts", []),
            "test_states": manifest.get("test_states", []),
            "cycles": manifest.get("cycles", []),
            "integrity": integrity,
            "integrity_reasons": integrity_reasons,
        })
    entries.sort(key=lambda entry: str(entry["generated_utc"]), reverse=True)
    return entries


def _project_report_query() -> tuple[str, bool]:
    allowed = {"project", "download"}
    if "project" not in request.args or set(request.args) - allowed:
        raise ValueError("invalid project report query")
    if any(len(request.args.getlist(name)) != 1 for name in allowed if name in request.args):
        raise ValueError("duplicated project report query values")
    project_id = request.args["project"]
    download = request.args.get("download", "")
    if PROJECT_ID_PATTERN.fullmatch(project_id) is None or download not in {"", "1"}:
        raise ValueError("invalid project report query")
    return project_id, download == "1"


def _project_report_dir(project_id: str) -> Path | None:
    projects_root = RUNS_ROOT / "_projects"
    project_dir = projects_root / project_id
    try:
        root_resolved = projects_root.resolve(strict=True)
        resolved = project_dir.resolve(strict=True)
        resolved.relative_to(root_resolved)
    except (OSError, ValueError):
        return None
    if project_dir.is_symlink() or not resolved.is_dir():
        return None
    return resolved
def _has_reparse_point(path: Path) -> bool:
    try:
        return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)
    except OSError:
        return True


def _safe_contained_path(root: Path, *parts: str, directory: bool) -> Path | None:
    """Resolve a fixed-root path only after rejecting every link/reparse component."""
    if not parts or any(not isinstance(part, str) or not part or part in {".", ".."} or "/" in part or "\\" in part for part in parts):
        return None
    try:
        root_resolved = root.resolve(strict=True)
        if _has_reparse_point(root) or not root_resolved.is_dir():
            return None
        current = root
        for part in parts:
            current = current / part
            if _has_reparse_point(current):
                return None
        resolved = current.resolve(strict=True)
        resolved.relative_to(root_resolved)
        return resolved if (resolved.is_dir() if directory else stat.S_ISREG(resolved.stat().st_mode)) else None
    except (OSError, ValueError):
        return None


def _safe_contained_file(root: Path, *parts: str) -> Path | None:
    return _safe_contained_path(root, *parts, directory=False)


def _safe_contained_dir(root: Path, *parts: str) -> Path | None:
    return _safe_contained_path(root, *parts, directory=True)


def _guarded_read(root: Path, *parts: str, maximum_bytes: int) -> tuple[bytes | None, str | None]:
    """Read one stable regular file under a fixed root without link/reparse traversal."""
    path = _safe_contained_file(root, *parts)
    if path is None:
        return None, "MISSING"
    try:
        before = path.stat()
        if before.st_size > maximum_bytes:
            return None, "TOO_LARGE"
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as handle:
            raw = handle.read(maximum_bytes + 1)
        if _safe_contained_file(root, *parts) != path:
            return None, "READ_FAILED"
        after = path.stat()
    except OSError:
        return None, "READ_FAILED"
    if len(raw) > maximum_bytes:
        return None, "TOO_LARGE"
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        return None, "READ_FAILED"
    return raw, None


def _type1_report_dir(dataset_run_id: str, train_run_id: str) -> Path | None:
    if (
        dataset_run_id != TYPE1_REPLACEMENT_IDENTITY["dataset_id"]
        or train_run_id != TYPE1_REPLACEMENT_IDENTITY["train_run_id"]
    ):
        return None
    run_dir = _safe_contained_dir(RUNS_ROOT, dataset_run_id, train_run_id)
    return run_dir if run_dir is not None and _safe_contained_dir(run_dir, "type1_reports") is not None else None


def _type1_catalog_snapshot(run_dir: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        from stom_rl.daily_v1_type1_report import Type1ReportError, verify_report_catalog
        snapshot = verify_report_catalog(run_dir)
    except (ImportError, Type1ReportError, OSError, ValueError):
        return None, ["TYPE1_CATALOG_INVALID"]
    return (snapshot, []) if snapshot.get("state") == "COMMITTED" else (None, ["TYPE1_COMMITTED_TIP_MISSING"])


def _type1_materializations(run_dir: Path) -> tuple[list[dict[str, Any]] | None, list[str]]:
    snapshot, reasons = _type1_catalog_snapshot(run_dir)
    events = snapshot.get("events") if snapshot is not None else None
    if not isinstance(events, list) or not events or len(events) > TYPE1_MAX_CATALOG_EVENTS or len(events) % 2:
        return None, reasons or ["TYPE1_CATALOG_INVALID"]
    rows: list[dict[str, Any]] = []
    for index in range(0, len(events), 2):
        revision, revision_event_sha = events[index]
        materialization, materialization_event_sha = events[index + 1]
        if not isinstance(revision, Mapping) or not isinstance(materialization, Mapping) or not isinstance(revision_event_sha, str) or not isinstance(materialization_event_sha, str):
            return None, ["TYPE1_CATALOG_INVALID"]
        identity = revision.get("identity")
        if not isinstance(identity, Mapping) or any(identity.get(key) != value for key, value in TYPE1_REPLACEMENT_IDENTITY.items()) or materialization.get("revision_event_sha256") != revision_event_sha:
            return None, ["TYPE1_REPLACEMENT_IDENTITY_MISMATCH"]
        rows.append({"revision": dict(revision), "revision_event_sha256": revision_event_sha, "materialization": dict(materialization), "materialization_event_sha256": materialization_event_sha})
    return rows, []


def _type1_revision_record(
    dataset_run_id: str, train_run_id: str, row: Mapping[str, Any],
) -> dict[str, Any]:
    revision = row["revision"]
    materialization = row["materialization"]
    result = revision["result"]
    report_sha256 = materialization["html_sha256"]
    return {
        "record_type": "TYPE1_REVISION",
        "revision_id": revision["revision_id"],
        "revision_ordinal": revision["revision_ordinal"],
        "revision_event_sha256": row["revision_event_sha256"],
        "parent_event_sha256": revision["previous_event_sha256"],
        "parent_revision_event_sha256": revision["previous_revision_event_sha256"],
        "materialization": {
            "event_sha256": row["materialization_event_sha256"],
            "catalog_ordinal": materialization["catalog_ordinal"],
            "object_id": materialization["object_id"],
            "builder_version": materialization["builder_version"],
        },
        "report_sha256": report_sha256,
        "size_bytes": materialization["byte_size"],
        "result": dict(result),
        "failures": list(result["failures"]),
        "integrity": "OK",
        "integrity_reasons": [],
        "report_url": (
            f"/api/v6/report-html?dataset={dataset_run_id}&train={train_run_id}"
            f"&report_sha256={report_sha256}"
        ),
    }


def _type1_report_entry(run_dir: Path) -> dict[str, Any]:
    dataset_run_id, train_run_id = run_dir.parent.name, run_dir.name
    rows, reasons = _type1_materializations(run_dir)
    custody = {
        "identity": dict(TYPE1_REPLACEMENT_IDENTITY),
        "catalog_state": "COMMITTED" if rows is not None else "INVALID",
        "event_count": len(rows) * 2 if rows is not None else 0,
    }
    if rows is None:
        return {
            "record_type": "TYPE1_CUSTODY",
            "dataset_run_id": dataset_run_id,
            "train_run_id": train_run_id,
            "report_family": "TYPE1",
            "availability": "BLOCKED",
            "integrity": "BLOCKED",
            "integrity_reasons": reasons,
            "chain_integrity": "CHAIN_INVALID",
            "chain_reasons": reasons,
            "custody": custody,
            "revisions": [],
        }
    return {
        "record_type": "TYPE1_CUSTODY",
        "dataset_run_id": dataset_run_id,
        "train_run_id": train_run_id,
        "report_family": "TYPE1",
        "availability": "COMMITTED",
        "integrity": "OK",
        "integrity_reasons": [],
        "chain_integrity": "CHAIN_OK",
        "chain_reasons": [],
        "custody": custody,
        "revisions": [
            _type1_revision_record(dataset_run_id, train_run_id, row) for row in rows
        ],
    }


def _type1_preserved_attempt_entries() -> list[dict[str, Any]]:
    amendment = _read_json(DOCS_ROOT / "kronos_type1_g002_recovery_amendment_v4_2026-07-24.json")
    preserved = amendment.get("preserved_aborted_evidence") if amendment is not None else None
    invalid_reason: str | None = None
    if amendment is None:
        invalid_reason = "AMENDMENT_MISSING_OR_MALFORMED"
    elif (
        not isinstance(preserved, list)
        or amendment.get("schema_version") != "kronos.type1.g002-recovery-amendment.v4"
        or amendment.get("amendment_id") != "KRONOS-TYPE1-G002-RECOVERY-2026-07-24-004"
        or amendment.get("replacement_identity") != TYPE1_REPLACEMENT_IDENTITY
        or len(preserved) != len(TYPE1_PRESERVED_ATTEMPTS)
        or amendment.get("quarantined_authorities") != [
            {
                "authority_id": "type1-krx-authority-20260723-002",
                "authority_sha256": "7d0ea6d76e3181da6caef232ce0c152645c290a290021e906d700667f8a059a2",
                "status": "QUARANTINED",
                "models_created": 0,
                "fresh_oos": {"status": "NOT_RUN", "no_read": True},
            },
            {
                "authority_id": "type1-krx-authority-20260724-003",
                "authority_sha256": "30e34b05fe65e31b2cbb826a48628946fa3f03dc7fc7f868ebd41ff36fcef1fe",
                "rows_sha256": "0af2be6cba26827f48ea00bf0caf700b1ce40e6fc1c2cfdebf1710ae39dfbd11",
                "status": "QUARANTINED_MATERIALIZED_NOT_TRAINED",
                "models_created": 0,
                "fresh_oos": {"status": "NOT_RUN", "no_read": True},
            },
        ]
        or not isinstance(amendment.get("authority_contract"), Mapping)
        or (
            amendment["authority_contract"].get("authority_metadata_cutoff"),
            amendment["authority_contract"].get("authority_metadata_scope"),
        ) != (
            "2026-07-24",
            "MDCSTAT23801 instrument-master metadata only; price, calendar, ranking, public-row, and fresh-OOS access end at 2025-06-30.",
        )
    ):
        invalid_reason = "AMENDMENT_INTEGRITY_MISMATCH"
    elif any(
        not isinstance(evidence, Mapping)
        or (
            evidence.get("dataset_id"),
            evidence.get("train_id"),
            evidence.get("train_run_id"),
            evidence.get("status"),
            evidence.get("models_created"),
        ) != expected
        or (
            expected[0] in {"type1-close-20260803-003", "type1-close-20260803-004"}
            and evidence.get("fresh_oos") != {"status": "NOT_RUN", "no_read": True}
        )
        for evidence, expected in zip(preserved, TYPE1_PRESERVED_ATTEMPTS)
    ):
        invalid_reason = "AMENDMENT_PRESERVED_EVIDENCE_MISMATCH"

    entries: list[dict[str, Any]] = []
    for dataset_id, train_id, train_run_id, status in TYPE1_PRESERVED_ATTEMPTS:
        custody = {
            "amendment_id": amendment.get("amendment_id", "MISSING") if amendment is not None else "MISSING",
            "scientific_eligibility": status,
            "model_files_created": 0,
            "fresh_oos_state": "NOT_RUN",
            "fresh_oos_read": False,
            "immutable_history": True,
            "html_serving": "BLOCKED",
        }
        if dataset_id == "type1-close-20260803-003":
            custody.update({
                "authority_id": "type1-krx-authority-20260723-002",
                "authority_sha256": "7d0ea6d76e3181da6caef232ce0c152645c290a290021e906d700667f8a059a2",
                "authority_status": "QUARANTINED",
                "materializations_created": 0,
            })
        elif dataset_id == "type1-close-20260803-004":
            custody.update({
                "authority_id": "type1-krx-authority-20260724-003",
                "authority_sha256": "30e34b05fe65e31b2cbb826a48628946fa3f03dc7fc7f868ebd41ff36fcef1fe",
                "authority_status": "QUARANTINED_MATERIALIZED_NOT_TRAINED",
                "materializations_created": 1,
            })
        entries.append({
            "record_type": "TYPE1_PRESERVED_INELIGIBLE_CUSTODY",
            "dataset_run_id": dataset_id,
            "train_run_id": train_run_id,
            "report_family": "TYPE1",
            "availability": "BLOCKED",
            "integrity": "INVALID" if invalid_reason is not None else "OK",
            "integrity_reasons": [invalid_reason] if invalid_reason is not None else [],
            "chain_integrity": "CHAIN_INVALID" if invalid_reason is not None else "CHAIN_OK",
            "chain_reasons": [invalid_reason] if invalid_reason is not None else [],
            "custody": custody,
            "attempts": [],
        })
    return entries


def _report_family(run_dir: Path, manifest: Mapping[str, Any] | None) -> str:
    if _safe_contained_dir(run_dir, "type1_reports") is not None:
        return "TYPE1"
    if manifest is not None and manifest.get("schema_version") == "kronos_v8_m3e_report.v1":
        return "M3E"
    if manifest is not None and manifest.get("schema_version") == KNOWN_V7_REPORT_SCHEMA:
        source_hashes = manifest.get("source_sha256")
        locks = manifest.get("false_research_locks")
        return "V7" if isinstance(source_hashes, Mapping) and isinstance(locks, Mapping) else "LEGACY"
    return "LEGACY" if manifest is not None and manifest.get("source_sha256") is None and manifest.get("false_research_locks") is None else "UNKNOWN"


def _type1_report_response(run_dir: Path, report_sha256: str | None, download: bool) -> Response:
    if (
        run_dir.parent.name != TYPE1_REPLACEMENT_IDENTITY["dataset_id"]
        or run_dir.name != TYPE1_REPLACEMENT_IDENTITY["train_run_id"]
    ):
        return _response({"status": "BLOCKED", "reason": "TYPE1_REPLACEMENT_IDENTITY_MISMATCH"}, 409)
    if report_sha256 is None:
        return _error(400, "BAD_REQUEST")
    rows, reasons = _type1_materializations(run_dir)
    if rows is None:
        return _response({"status": "BLOCKED", "reason": reasons[0], "reasons": reasons}, 409)
    row = next((candidate for candidate in rows if candidate["materialization"]["html_sha256"] == report_sha256), None)
    if row is None:
        return _response({"status": "BLOCKED", "reason": "TYPE1_REPORT_NOT_FOUND"}, 404)
    materialization = row["materialization"]
    report_bytes, error = _guarded_read(run_dir / "type1_reports", "objects", f"{materialization['object_id']}-{report_sha256}.html", maximum_bytes=TYPE1_MAX_OBJECT_BYTES)
    if error == "TOO_LARGE":
        return _response({"status": "BLOCKED", "reason": "TYPE1_OBJECT_TOO_LARGE"}, 413)
    if error is not None or report_bytes is None:
        return _response({"status": "ERROR", "error": {"code": "REPORT_READ_FAILED"}}, 500)
    if len(report_bytes) != materialization["byte_size"] or hashlib.sha256(report_bytes).hexdigest() != report_sha256:
        return _response({"status": "BLOCKED", "reason": "TYPE1_OBJECT_INTEGRITY_MISMATCH"}, 409)
    response = Response(report_bytes, status=200, mimetype="text/html")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"
    response.headers["ETag"] = f'"{report_sha256}"'
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    if download:
        response.headers["Content-Disposition"] = f'attachment; filename="kronos-type1-report-{run_dir.parent.name}-{run_dir.name}-{report_sha256}.html"'
    return response


def _report_entries() -> list[dict[str, Any]]:
    return _request_snapshot("report_entries", _build_report_entries)


def _build_report_entries() -> list[dict[str, Any]]:
    """List report artifacts, retaining invalid custody states for review."""
    entries: list[dict[str, Any]] = []
    try:
        run_dirs = {
            path.parent
            for pattern in ("*/*/report_manifest.json", "*/*/report.html")
            for path in RUNS_ROOT.glob(pattern)
        }
    except OSError:
        return entries
    try:
        type1_dirs = sorted({
            path.parent for path in RUNS_ROOT.glob("*/*/type1_reports")
            if path.is_dir() and not path.is_symlink()
        })
    except OSError:
        type1_dirs = []
    for run_dir in type1_dirs:
        dataset_run_id, train_run_id = run_dir.parent.name, run_dir.name
        if _type1_report_dir(dataset_run_id, train_run_id) is not None:
            entries.append(_type1_report_entry(run_dir))
    entries.extend(_type1_preserved_attempt_entries())
    for run_dir in sorted(run_dirs):
        dataset_run_id = run_dir.parent.name
        train_run_id = run_dir.name
        if RUN_ID_PATTERN.fullmatch(dataset_run_id) is None or RUN_ID_PATTERN.fullmatch(train_run_id) is None:
            continue
        if _report_family(run_dir, None) == "TYPE1":
            continue
        manifest_path = run_dir / "report_manifest.json"
        report_path = run_dir / "report.html"
        manifest = None if manifest_path.is_symlink() else _read_json(manifest_path)
        report_bytes: bytes | None = None
        if not report_path.is_symlink():
            try:
                report_bytes = report_path.read_bytes()
            except OSError:
                pass
        reasons: list[str] = []
        if manifest is None:
            reasons.append("REPORT_MANIFEST_INVALID")
        if report_bytes is None:
            reasons.append("REPORT_NOT_FOUND")
        actual_sha = hashlib.sha256(report_bytes).hexdigest() if report_bytes is not None else None
        recorded_sha = manifest.get("report_sha256") if manifest is not None else None
        if report_bytes is not None and manifest is not None and recorded_sha != actual_sha:
            reasons.append("REPORT_SHA_MISMATCH")
        chain_integrity, chain_reasons = (
            _report_chain(run_dir, manifest) if manifest is not None and report_bytes is not None else ("CHAIN_INVALID", reasons)
        )
        run_manifest = _read_json(run_dir / "run_manifest.json")
        states = _run_states(run_manifest) if run_manifest is not None else None
        family = _report_family(run_dir, manifest)
        entries.append({
            "dataset_run_id": dataset_run_id,
            "train_run_id": train_run_id,
            "report_family": family,
            "compatibility_state": "NATIVE" if family == "M3E" else "KNOWN_V7" if family == "V7" else "LEGACY_UNVERIFIED" if family == "LEGACY" else "UNKNOWN_SCHEMA",
            "availability": "COMMITTED" if family in {"M3E", "V7"} and not reasons and chain_integrity == "CHAIN_OK" else "BLOCKED",
            "verdict": manifest.get("verdict", "MISSING") if manifest is not None else "MISSING",
            "test_state": states["test_state"] if states is not None else manifest.get("test_state", "MISSING") if manifest is not None else "MISSING",
            "index_overlay_state": manifest.get("index_overlay_state", "MISSING") if manifest is not None else "MISSING",
            "generated_utc": manifest.get("generated_utc", "MISSING") if manifest is not None else "MISSING",
            "builder_version": manifest.get("builder_version", "MISSING") if manifest is not None else "MISSING",
            "report_sha256": recorded_sha,
            "size_bytes": len(report_bytes) if report_bytes is not None else 0,
            "integrity": "OK" if not reasons else "INVALID" if actual_sha is None or manifest is None else "SHA_MISMATCH",
            "integrity_reasons": reasons,
            "chain_integrity": chain_integrity,
            "chain_reasons": chain_reasons,
            "report_state": "PRESENT" if report_bytes is not None else "MISSING",
            "training_state": states["training_state"] if states is not None else "MISSING",
            "validation_state": states["validation_state"] if states is not None else "NOT_RECORDED",
            "evaluation_state": states["evaluation_state"] if states is not None else "TEST_MISSING",
        })
    entries.sort(key=lambda entry: str(entry.get("generated_utc")), reverse=True)
    return entries



def _prereg_registry() -> list[dict[str, Any]]:
    return _request_snapshot("prereg_registry", _build_prereg_registry)


def _build_prereg_registry() -> list[dict[str, Any]]:
    """Registry of preregistrations linked to the runs and reports that cite them."""
    runs_by_prereg: dict[str, list[dict[str, Any]]] = {}
    report_index = {(entry["dataset_run_id"], entry["train_run_id"]): entry for entry in _report_entries()}
    try:
        run_manifests = sorted(RUNS_ROOT.glob("*/*/run_manifest.json"))
    except OSError:
        run_manifests = []
    for manifest_path in run_manifests:
        manifest = _read_json(manifest_path)
        if manifest is None:
            continue
        prereg = manifest.get("prereg")
        prereg_id = prereg.get("id") if isinstance(prereg, Mapping) else None
        if not isinstance(prereg_id, str):
            continue
        run_dir = manifest_path.parent
        dataset_run_id, train_run_id = run_dir.parent.name, run_dir.name
        verdict = manifest.get("verdict_candidate")
        record = {
            "dataset_run_id": dataset_run_id,
            "train_run_id": train_run_id,
            "trainer_version": manifest.get("trainer_version", "MISSING"),
            "verdict": verdict.get("value") if isinstance(verdict, Mapping) else "MISSING",
            "test_state": manifest.get("test", {}).get("state") if isinstance(manifest.get("test"), Mapping) else "MISSING",
            "generated_utc": manifest.get("generated_utc", "MISSING"),
            "has_report": (dataset_run_id, train_run_id) in report_index,
        }
        runs_by_prereg.setdefault(prereg_id, []).append(record)

    seen: set[Path] = set()
    prereg_paths: list[Path] = []
    for pattern in PREREG_GLOBS:
        try:
            for path in DOCS_ROOT.glob(pattern):
                if path.is_file() and path not in seen:
                    seen.add(path)
                    prereg_paths.append(path)
        except OSError:
            continue
    registry: list[dict[str, Any]] = []
    for path in sorted(prereg_paths):
        prereg = _read_json(path)
        if prereg is None:
            registry.append({
                "prereg_id": "MISSING",
                "doc": path.name,
                "status": "INVALID",
                "frozen_utc": "MISSING",
                "supersedes": None,
                "family": None,
                "sha256": _sha256_file(path),
                "runs": [],
                "run_count": 0,
                "verdicts": [],
                "integrity_reasons": ["PREREG_PARSE_FAILED"],
            })
            continue
        prereg_id = str(prereg.get("prereg_id", "MISSING"))
        runs = sorted(runs_by_prereg.get(prereg_id, []), key=lambda r: str(r["generated_utc"]), reverse=True)
        registry.append({
            "prereg_id": prereg_id,
            "doc": path.name,
            "status": prereg.get("status", "MISSING"),
            "frozen_utc": prereg.get("frozen_utc", "MISSING"),
            "supersedes": prereg.get("supersedes"),
            "family": prereg.get("algorithm", {}).get("family") if isinstance(prereg.get("algorithm"), Mapping) else None,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "runs": runs,
            "run_count": len(runs),
            "verdicts": sorted({str(run["verdict"]) for run in runs}),
            "integrity_reasons": [],
        })
    registry.sort(key=lambda item: str(item["frozen_utc"]), reverse=True)
    return registry


def _result_docs() -> list[dict[str, Any]]:
    """Allowlisted V6/V7 research markdown documents available for read-only viewing."""
    docs: list[dict[str, Any]] = []
    try:
        candidates = sorted(DOCS_ROOT.glob("kronos_v*_*.md"))
    except OSError:
        return docs
    for path in candidates:
        if RESEARCH_DOC_RE.fullmatch(path.name) is None:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        docs.append({
            "doc": path.name,
            "size_bytes": stat.st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    docs.sort(key=lambda item: item["doc"], reverse=True)
    return docs

def _report_query() -> tuple[str, str, str | None, bool]:
    allowed = {"dataset", "train", "report_sha256", "download"}
    if not {"dataset", "train"} <= set(request.args) or set(request.args) - allowed:
        raise ValueError("invalid report query")
    if any(len(request.args.getlist(name)) != 1 for name in allowed if name in request.args):
        raise ValueError("duplicated report query values")
    dataset_run_id = request.args["dataset"]
    train_run_id = request.args["train"]
    report_sha256 = request.args.get("report_sha256")
    download = request.args.get("download", "")
    if not dataset_run_id or not train_run_id or download not in {"", "1"} or RUN_ID_PATTERN.fullmatch(dataset_run_id) is None or RUN_ID_PATTERN.fullmatch(train_run_id) is None or (report_sha256 is not None and re.fullmatch(r"[0-9a-f]{64}", report_sha256) is None):
        raise ValueError("invalid report query")
    return dataset_run_id, train_run_id, report_sha256, download == "1"


def _run_detail_payload(dataset_run_id: str, train_run_id: str) -> dict[str, Any]:
    type1_dir = _type1_report_dir(dataset_run_id, train_run_id)
    if type1_dir is not None:
        entry = _type1_report_entry(type1_dir)
        return {
            "schema_version": "kronos_v6_run_detail.v1",
            "status": "OK" if entry["availability"] == "COMMITTED" else "BLOCKED",
            "dataset_run_id": dataset_run_id,
            "train_run_id": train_run_id,
            "identity": {
                "report_family": "TYPE1",
                "dataset_id": dataset_run_id,
                "train_id": train_run_id,
                "train_run_id": train_run_id,
                "domain": "kronos.type1",
                "algorithm_family": "MASKABLE_PPO",
            },
            "report_custody": entry,
            "manifest": {},
            "events_tail": [],
            "events_tail_diagnostics": {"state": "TYPE1_IMMUTABLE_CATALOG"},
            "states": {},
        }
    manifest_path = RUNS_ROOT / dataset_run_id / train_run_id / "run_manifest.json"
    raw, manifest_error = _guarded_read(RUNS_ROOT, dataset_run_id, train_run_id, "run_manifest.json", maximum_bytes=TYPE1_MAX_OBJECT_BYTES)
    if manifest_error is not None or raw is None:
        return {"status": "BLOCKED", "reason": "RUN_MANIFEST_MISSING"}
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"status": "BLOCKED", "reason": "RUN_MANIFEST_MISSING"}
    events_tail, events_tail_diagnostics = _events_tail(manifest_path.with_name("events.jsonl"))
    return {
        "schema_version": "kronos_v6_run_detail.v1",
        "status": "OK",
        "dataset_run_id": dataset_run_id,
        "train_run_id": train_run_id,
        "manifest": manifest,
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "events_tail": events_tail,
        "events_tail_diagnostics": events_tail_diagnostics,
        "states": _run_states(manifest) if isinstance(manifest, Mapping) else {},
    }


def _preregistration() -> dict[str, Any]:
    prereg: dict[str, Any] = {
        "state": "NOT_FROZEN",
        "path": "docs/kronos_v6_prereg_h1_2026-07-19.json",
        "sha256": None,
    }
    try:
        raw = PREREG_PATH.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except FileNotFoundError:
        return prereg
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        prereg["error"] = "PREREG_PARSE_FAILED"
        return prereg
    if not isinstance(value, Mapping):
        prereg["error"] = "PREREG_PARSE_FAILED"
        return prereg
    prereg["state"] = "FROZEN"
    prereg["sha256"] = hashlib.sha256(raw).hexdigest()
    prereg.update({key: value[key] for key in ("hypothesis", "frozen_utc") if key in value})
    return prereg


def _manifest_candidates(filename: str) -> list[Path]:
    try:
        candidates = [path for path in RUNS_ROOT.glob(f"*/{filename}") if path.is_file()]
        return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)
    except OSError:
        return []


def _artifact_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()

def _run_manifest_candidates() -> list[Path]:
    try:
        candidates = [
            path
            for pattern in ("*/run_manifest.json", "*/*/run_manifest.json")
            for path in RUNS_ROOT.glob(pattern)
            if path.is_file()
        ]
        return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)
    except OSError:
        return []


def _runs_payload() -> dict[str, Any]:
    datasets: list[dict[str, Any]] = []
    for path in _manifest_candidates("dataset_manifest.json"):
        if len(datasets) == 50:
            break
        try:
            raw = path.read_bytes()
            value = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(value, Mapping):
            continue
        split_row_counts = value.get("split_row_counts")
        datasets.append({
            "run_id": path.parent.name,
            "path": _artifact_path(path),
            "generated_utc": value.get("generated_utc"),
            "split_row_counts": dict(split_row_counts) if isinstance(split_row_counts, Mapping) else {},
            "sha256": hashlib.sha256(raw).hexdigest(),
        })

    runs: list[dict[str, Any]] = []
    for path in _run_manifest_candidates():
        if len(runs) == 50:
            break
        value = _read_json(path)
        if value is None:
            continue
        seeds = value.get("seeds")
        dataset_run_id = path.parent.parent.name
        states = _run_states(value)
        runs.append({
            "run_id": path.parent.name,
            "dataset_run_id": dataset_run_id,
            "path": _artifact_path(path),
            "state": value.get("state"),
            "seeds": list(seeds) if isinstance(seeds, list) else [],
            "generated_utc": value.get("generated_utc"),
            "verdict_candidate": value.get("verdict_candidate"),
            **states,
        })

    return {
        "schema_version": "kronos_v6_runs.v1",
        "status": "OK",
        "datasets": datasets,
        "runs": runs,
        "training_state": "HAS_RUNS" if runs else "NOT_RUN",
    }


def _experiment_state() -> str:
    return _preregistration()["state"]



def _index_overlays() -> dict[str, dict[str, Any]]:
    """Return per-market overlay-safe validated normalized index artifacts.

    Validation is fully offline (no pykrx import, no network).  Invalid or
    unreadable artifacts are skipped so the endpoint fails closed to the
    blocker state instead of serving unverified index values.
    """
    try:
        from stom_rl.korean_index_source import KoreanIndexArtifactError, validate_korean_index_artifact
    except ImportError:
        return {}
    try:
        paths = sorted(
            path for path in INDEX_ARTIFACT_DIR.glob(INDEX_NORMALIZED_GLOB)
            if not path.is_symlink() and path.is_file()
        )
    except OSError:
        return {}
    current_keys = {path.as_posix() for path in paths}
    for key in tuple(_INDEX_OVERLAY_CACHE):
        if key not in current_keys:
            del _INDEX_OVERLAY_CACHE[key]

    overlays: dict[str, dict[str, Any]] = {}
    for path in paths:
        try:
            key = path.as_posix()
            content_sha = _sha256_file(path)
            if content_sha is None:
                continue
            cached = _INDEX_OVERLAY_CACHE.get(key)
            if cached is not None and cached[0] == content_sha:
                overlay = cached[1]
            else:
                overlay = validate_korean_index_artifact(path)
                _INDEX_OVERLAY_CACHE[key] = (content_sha, overlay)
                while len(_INDEX_OVERLAY_CACHE) > _INDEX_OVERLAY_CACHE_LIMIT:
                    del _INDEX_OVERLAY_CACHE[next(iter(_INDEX_OVERLAY_CACHE))]
        except (OSError, KoreanIndexArtifactError, ValueError):
            continue
        market = str(overlay["market"])
        current = overlays.get(market)
        if current is None or str(overlay["actual_end_date"]) > str(current["actual_end_date"]):
            overlays[market] = overlay
    return overlays


def index_overlay_states() -> dict[str, dict[str, Any]]:
    """Public per-market summary of validated offline index artifacts."""
    overlays = _index_overlays()
    return {
        market: {
            "index_code": overlay["index_code"],
            "index_name": overlay["index_name"],
            "actual_start_date": overlay["actual_start_date"],
            "actual_end_date": overlay["actual_end_date"],
            "row_count": overlay["row_count"],
            "normalized_sha256": overlay["normalized_sha256"],
        }
        for market, overlay in sorted(overlays.items())
    }

def index_overlay_series() -> dict[str, list[dict[str, Any]]]:
    """Public per-market validated close series rows (date/close only)."""
    return {market: [dict(row) for row in overlay["series"]] for market, overlay in sorted(_index_overlays().items())}


def _index_overlay_state() -> str:
    overlays = _index_overlays()
    return "PRESENT" if all(market in overlays for market in INDEX_MARKETS) else INDEX_BLOCKER


def _journey_data() -> dict[str, Any]:
    manifest, _ = _manifest()
    if manifest is None:
        return {"state": "MISSING"}
    universe = manifest["universe"]
    payload = {
        "state": "PARTIAL",
        "universe_manifest": "docs/kronos_v6_universe_manifest_2026-07-19.json",
        "universe_size": len(universe),
        "index_overlay": _index_overlay_state(),
    }
    if payload["index_overlay"] == INDEX_BLOCKER:
        payload["index_blocker_reason"] = INDEX_BLOCKER_REASON
    return payload


def _experiment_payload() -> dict[str, Any]:
    return {
        "schema_version": "kronos_v6_experiment_state.v1",
        "status": "OK",
        "prereg": _preregistration(),
        "planned": {
            "strategy": "daily_close_10slot",
            "horizons": {"primary": "H1", "validation": ["H3", "H5"]},
            "execution": {"price_basis": "15:20_bar_close_proxy", "official_close": False},
            "capital": {
                "initial_krw": 60000000,
                "slots": 10,
                "slot_budget_krw": 5000000,
                "reserve_krw": 10000000,
            },
            "costs": {"primary": "0.23%", "zero_control": "0.00%", "stress": "0.46%"},
            "universe": {"manifest": "docs/kronos_v6_universe_manifest_2026-07-19.json", "size": 500},
            "dataset_contract": "kronos_v6_joined_dataset.v1",
            "seeds": [0, 1, 2],
            "constraints": {"shorting": False, "leverage": False, "duplicate_slots": False},
        },
        "locks": dict(SIX_FALSE_LOCKS),
    }




def _file_details(path: Path, *, include_tables: bool = False) -> dict[str, Any]:
    try:
        stat = path.stat()
    except OSError:
        return {"state": "MISSING"}
    details: dict[str, Any] = {
        "state": "PRESENT",
        "size_bytes": stat.st_size,
        "mtime_epoch": int(stat.st_mtime),
    }
    if include_tables:
        try:
            with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as connection:
                row = connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()
            details["table_count"] = int(row[0]) if row is not None else 0
        except (OSError, sqlite3.Error, ValueError):
            details["table_count"] = None
            details["table_count_state"] = "MISSING"
    return details


def _audit_summary() -> tuple[dict[str, Any], dict[str, Any]]:
    audit = _read_json(AUDIT_PATH)
    if audit is None:
        return {"state": "MISSING"}, {"state": "MISSING"}
    disclaimers = {
        key: audit[key]
        for key in ("flow_columns_disclaimer", "liquidity_proxy_disclaimer", "instrument_type")
        if key in audit
    }
    summary: dict[str, Any] = {"state": "PRESENT"}
    for key in ("population", "filters"):
        value = audit.get(key)
        summary[key] = value if isinstance(value, Mapping) else {"state": "MISSING"}
    summary["disclaimers"] = disclaimers if disclaimers else {"state": "MISSING"}
    price_basis = audit.get("price_basis")
    return summary, dict(price_basis) if isinstance(price_basis, Mapping) else {"state": "MISSING"}


def _index_status() -> dict[str, Any]:
    markets = index_overlay_states()
    if not all(market in markets for market in INDEX_MARKETS):
        return {"state": INDEX_BLOCKER, "reason": INDEX_BLOCKER_REASON}
    return {"state": "PRESENT", "markets": markets}


def _status_payload() -> dict[str, Any]:
    runs_payload = _runs_payload()
    runs = runs_payload["runs"]
    evaluation_state = runs[0]["evaluation_state"] if runs else "NOT_RUN"
    return {
        "schema_version": "kronos_v6_platform_status.v1",
        "status": "OK",
        "journey": {
            "data": _journey_data(),
            "experiment": {"state": _experiment_state()},
            "training": {"state": runs_payload["training_state"]},
            "evaluation": {"state": evaluation_state},
            "report": {"state": "HAS_REPORTS" if _report_entries() else "NOT_RUN"},
        },
        "locks": dict(SIX_FALSE_LOCKS),
    }


def create_v6_platform_blueprint(*, name: str = "v6_platform", url_prefix: str = "/api/v6") -> Blueprint:
    """Create the V6 GET-only platform API blueprint."""
    blueprint = Blueprint(name, __name__, url_prefix=url_prefix)

    def status_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        if request.args:
            return _error(400, "BAD_REQUEST")
        return _response(_status_payload())

    def experiment_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        if request.args:
            return _error(400, "BAD_REQUEST")
        return _response(_experiment_payload())

    def runs_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        if request.args:
            return _error(400, "BAD_REQUEST")
        return _response(_runs_payload())

    def run_detail_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        try:
            dataset_run_id, train_run_id = _run_detail_query()
        except ValueError:
            return _error(400, "BAD_REQUEST")
        return _response(_run_detail_payload(dataset_run_id, train_run_id))


    def universe_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        try:
            limit = _query_limit()
        except ValueError:
            return _error(400, "BAD_REQUEST")
        manifest, raw = _manifest()
        if manifest is None or raw is None:
            return _response({"status": "BLOCKED", "reason": "UNIVERSE_MANIFEST_MISSING"}, 404)
        universe = manifest["universe"]
        payload = dict(manifest)
        payload["sha256"] = hashlib.sha256(raw).hexdigest()
        payload["total"] = len(universe)
        payload["universe"] = universe[:limit]
        return _response(payload)

    def readiness_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        if request.args:
            return _error(400, "BAD_REQUEST")
        audit, price_basis = _audit_summary()
        return _response({
            "schema_version": "kronos_v6_data_readiness.v1",
            "status": "OK",
            "daily_db": _file_details(DAILY_DB_PATH, include_tables=True),
            "fivemin_db": _file_details(FIVEMIN_DB_PATH),
            "audit": audit,
            "index": _index_status(),
            "price_basis": price_basis,
        })

    def index_series_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        if set(request.args) != {"market"} or len(request.args.getlist("market")) != 1:
            return _error(400, "BAD_REQUEST")
        market = request.args["market"]
        if market not in INDEX_MARKETS:
            return _error(400, "BAD_REQUEST")
        overlay = _index_overlays().get(market)
        if overlay is None:
            return _response({"status": "BLOCKED", "reason": INDEX_BLOCKER}, 404)
        return _response({
            "schema_version": "kronos_v6_index_series.v1",
            "status": "OK",
            "market": overlay["market"],
            "index_code": overlay["index_code"],
            "index_name": overlay["index_name"],
            "actual_start_date": overlay["actual_start_date"],
            "actual_end_date": overlay["actual_end_date"],
            "row_count": overlay["row_count"],
            "series": overlay["series"],
            "provider_package": overlay["provider_package"],
            "normalization_method": overlay["parser"]["normalization_method"],
            "point_in_time": overlay["point_in_time"],
            "false_locks": overlay["false_locks"],
            "claims": overlay["claims"],
            "hashes": overlay["hashes"],
        })

    def reports_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        if not request.args:
            reports = _report_entries()
        else:
            try:
                dataset_run_id, train_run_id, report_sha256, download = _report_query()
            except ValueError:
                return _error(400, "BAD_REQUEST")
            if report_sha256 is not None or download:
                return _error(400, "BAD_REQUEST")
            run_dir = _type1_report_dir(dataset_run_id, train_run_id)
            preserved_entries = _type1_preserved_attempt_entries()
            if run_dir is not None:
                reports = [_type1_report_entry(run_dir)]
            else:
                reports = [
                    entry for entry in preserved_entries
                    if dataset_run_id == entry["dataset_run_id"]
                    and train_run_id == entry["train_run_id"]
                ]
        return _response({
            "schema_version": "kronos_v6_reports.v2",
            "status": "OK",
            "reports": reports,
        })
    def project_reports_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        if request.args:
            return _error(400, "BAD_REQUEST")
        return _response({
            "schema_version": "kronos_v7_project_reports.v2",
            "status": "OK",
            "projects": _project_report_entries(),
        })

    def project_report_html_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        try:
            project_id, download = _project_report_query()
        except ValueError:
            return _error(400, "BAD_REQUEST")
        project_dir = _project_report_dir(project_id)
        if project_dir is None:
            return _response({"status": "BLOCKED", "reason": "PROJECT_REPORT_NOT_FOUND"}, 404)
        manifest_path = project_dir / "project_report_manifest.json"
        report_path = project_dir / "project_report.html"
        if manifest_path.is_symlink() or report_path.is_symlink():
            return _response({"status": "BLOCKED", "reason": "PROJECT_REPORT_NOT_FOUND"}, 404)
        manifest = _read_json(manifest_path)
        try:
            report_bytes = report_path.read_bytes()
        except OSError:
            return _response({"status": "BLOCKED", "reason": "PROJECT_REPORT_NOT_FOUND"}, 404)
        if manifest is None:
            return _response({"status": "BLOCKED", "reason": "PROJECT_REPORT_MANIFEST_MISSING"}, 404)
        integrity, reasons = _project_report_chain(project_id, project_dir, manifest, report_bytes)
        if integrity != "CHAIN_OK":
            return _response({"status": "BLOCKED", "reason": reasons[0], "reasons": reasons}, 409)
        response = Response(report_bytes, status=200, mimetype="text/html")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
        if download:
            response.headers["Content-Disposition"] = f'attachment; filename="kronos-project-report-{project_id}.html"'
        return response


    def report_html_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        try:
            dataset_run_id, train_run_id, report_sha256, download = _report_query()
        except ValueError:
            return _error(400, "BAD_REQUEST")
        preserved_entries = _type1_preserved_attempt_entries()
        if any(
            dataset_run_id == entry["dataset_run_id"]
            and train_run_id == entry["train_run_id"]
            for entry in preserved_entries
        ):
            return _response({"status": "BLOCKED", "reason": "PRESERVED_INELIGIBLE_REPORT_NOT_SERVABLE"}, 409)
        run_dir = _safe_contained_dir(RUNS_ROOT, dataset_run_id, train_run_id)
        if run_dir is None:
            return _response({"status": "BLOCKED", "reason": "REPORT_NOT_FOUND"}, 404)
        manifest_path = _safe_contained_file(run_dir, "report_manifest.json")
        manifest = _read_json(manifest_path) if manifest_path is not None else None
        family = _report_family(run_dir, manifest)
        if family == "TYPE1":
            return _type1_report_response(run_dir, report_sha256, download)
        if report_sha256 is not None:
            return _error(400, "BAD_REQUEST")
        report_path = _safe_contained_file(run_dir, "report.html")
        if manifest_path is None or report_path is None:
            return _response({"status": "BLOCKED", "reason": "REPORT_NOT_FOUND"}, 404)
        try:
            report_bytes = report_path.read_bytes()
        except OSError:
            return _response({"status": "BLOCKED", "reason": "REPORT_NOT_FOUND"}, 404)
        if manifest is None:
            return _response({"status": "BLOCKED", "reason": "REPORT_MANIFEST_MISSING"}, 404)
        if manifest.get("report_sha256") != hashlib.sha256(report_bytes).hexdigest():
            return _response({"status": "BLOCKED", "reason": "REPORT_SHA_MISMATCH"}, 409)
        if family not in {"M3E", "V7"}:
            return _response({"status": "BLOCKED", "reason": "UNKNOWN_OR_LEGACY_REPORT_FAMILY"}, 409)
        chain_integrity, chain_reasons = (
            _m3e_report_chain(run_dir, manifest)
            if family == "M3E"
            else _report_chain(run_dir, manifest)
        )
        if chain_integrity != "CHAIN_OK":
            return _response({"status": "BLOCKED", "reason": chain_reasons[0], "reasons": chain_reasons}, 409)
        response = Response(report_bytes, status=200, mimetype="text/html")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
        if download:
            response.headers["Content-Disposition"] = f'attachment; filename="kronos-report-{dataset_run_id}-{train_run_id}.html"'
        return response

    def research_registry_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        if request.args:
            return _error(400, "BAD_REQUEST")
        return _response({
            "schema_version": "kronos_v6_research_registry.v1",
            "status": "OK",
            "preregistrations": _prereg_registry(),
            "result_docs": _result_docs(),
        })

    def research_doc_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        if set(request.args) != {"doc"} or len(request.args.getlist("doc")) != 1:
            return _error(400, "BAD_REQUEST")
        name = request.args["doc"]
        if DOC_NAME_RE.fullmatch(name) is None or RESEARCH_DOC_RE.fullmatch(name) is None:
            return _error(400, "BAD_REQUEST")
        path = DOCS_ROOT / name
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            return _response({"status": "BLOCKED", "reason": "DOC_NOT_FOUND"}, 404)
        if resolved.parent != DOCS_ROOT.resolve() or not resolved.is_file():
            return _response({"status": "BLOCKED", "reason": "DOC_NOT_FOUND"}, 404)
        try:
            text = resolved.read_text(encoding="utf-8")
        except OSError:
            return _response({"status": "BLOCKED", "reason": "DOC_NOT_FOUND"}, 404)
        return _response({
            "schema_version": "kronos_v6_research_doc.v1",
            "status": "OK",
            "doc": name,
            "format": "markdown" if name.endswith(".md") else "json",
            "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
            "content": text,
        })

    for rule, endpoint, handler in (
        ("/status", "status", status_handler),
        ("/experiment", "experiment", experiment_handler),
        ("/runs", "runs", runs_handler),
        ("/run-detail", "run_detail", run_detail_handler),
        ("/universe", "universe", universe_handler),
        ("/data-readiness", "data_readiness", readiness_handler),
        ("/index-series", "index_series", index_series_handler),
        ("/reports", "reports", reports_handler),
        ("/report-html", "report_html", report_html_handler),
        ("/project-reports", "project_reports", project_reports_handler),
        ("/project-report-html", "project_report_html", project_report_html_handler),
        ("/research-registry", "research_registry", research_registry_handler),
        ("/research-doc", "research_doc", research_doc_handler),
    ):
        blueprint.add_url_rule(rule, endpoint=endpoint, view_func=handler, methods=list(ALL_ROUTE_METHODS), provide_automatic_options=False)
    return blueprint


create_blueprint = create_v6_platform_blueprint

__all__ = ["create_blueprint", "create_v6_platform_blueprint"]
