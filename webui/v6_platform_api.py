"""Read-only V6 platform readiness API."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from flask import Blueprint, Response, request

WEBUI_ROOT: Final = Path(__file__).resolve().parent
REPO_ROOT: Final = WEBUI_ROOT.parent
MANIFEST_PATH: Final = REPO_ROOT / "docs" / "kronos_v6_universe_manifest_2026-07-19.json"
PREREG_PATH: Final = REPO_ROOT / "docs" / "kronos_v6_prereg_h1_2026-07-19.json"
RUNS_ROOT: Final = WEBUI_ROOT / "rl_runs" / "v6_daily_h1"
AUDIT_PATH: Final = WEBUI_ROOT / "rl_runs" / "daily_ohlcv_db_summary" / "v6_universe_audit.json"
DAILY_DB_PATH: Final = REPO_ROOT / "_database" / "Stock_Database_ohlcv_1day.db"
FIVEMIN_DB_PATH: Final = REPO_ROOT / "_database" / "Stock_Database_ohlcv_5min.db"
INDEX_ARTIFACT_DIR: Final = REPO_ROOT / "artifacts" / "korean_index"
INDEX_BLOCKER: Final = "BLOCKED_INDEX_SERIES_SOURCE"
INDEX_BLOCKER_REASON: Final = "KRX credentials required for pykrx collection"
INDEX_MARKETS: Final = ("KOSDAQ", "KOSPI")
INDEX_NORMALIZED_GLOB: Final = "korean-index-*-normalized-*.json"
_INDEX_OVERLAY_CACHE: dict[str, tuple[tuple[int, int], dict[str, Any]]] = {}
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
    train = request.args["train"]
    if (
        ".." in dataset_run_id
        or ".." in train
        or RUN_ID_PATTERN.fullmatch(dataset_run_id) is None
        or RUN_ID_PATTERN.fullmatch(train) is None
    ):
        raise ValueError
    train_run_id = train if train.startswith("train_") else f"train_{train}"
    return dataset_run_id, train_run_id


def _events_tail(path: Path) -> list[Any]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    events: list[Any] = []
    for line in lines:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events[-50:]


def _report_entries() -> list[dict[str, Any]]:
    """List validated report manifests under RUNS_ROOT with integrity states."""
    entries: list[dict[str, Any]] = []
    try:
        manifest_paths = sorted(RUNS_ROOT.glob("*/*/report_manifest.json"))
    except OSError:
        return entries
    for manifest_path in manifest_paths:
        run_dir = manifest_path.parent
        dataset_run_id = run_dir.parent.name
        train_run_id = run_dir.name
        if RUN_ID_PATTERN.fullmatch(dataset_run_id) is None or RUN_ID_PATTERN.fullmatch(train_run_id) is None:
            continue
        manifest = _read_json(manifest_path)
        if manifest is None:
            continue
        report_path = run_dir / "report.html"
        try:
            report_bytes = report_path.read_bytes()
        except OSError:
            continue
        actual_sha = hashlib.sha256(report_bytes).hexdigest()
        recorded_sha = manifest.get("report_sha256")
        entries.append({
            "dataset_run_id": dataset_run_id,
            "train_run_id": train_run_id,
            "verdict": manifest.get("verdict", "MISSING"),
            "test_state": manifest.get("test_state", "MISSING"),
            "index_overlay_state": manifest.get("index_overlay_state", "MISSING"),
            "generated_utc": manifest.get("generated_utc", "MISSING"),
            "builder_version": manifest.get("builder_version", "MISSING"),
            "report_sha256": recorded_sha,
            "size_bytes": len(report_bytes),
            "integrity": "OK" if recorded_sha == actual_sha else "SHA_MISMATCH",
        })
    entries.sort(key=lambda e: str(e.get("generated_utc")), reverse=True)
    return entries


def _report_query() -> tuple[str, str, bool]:
    allowed = {"dataset", "train", "download"}
    if not {"dataset", "train"} <= set(request.args) or set(request.args) - allowed:
        raise ValueError("invalid report query")
    if any(len(request.args.getlist(name)) > 1 for name in allowed):
        raise ValueError("duplicated report query values")
    dataset_run_id = request.args["dataset"]
    train_run_id = request.args["train"]
    download = request.args.get("download", "")
    if download not in {"", "1"}:
        raise ValueError("invalid download flag")
    if RUN_ID_PATTERN.fullmatch(dataset_run_id) is None or RUN_ID_PATTERN.fullmatch(train_run_id) is None:
        raise ValueError("invalid report run ids")
    return dataset_run_id, train_run_id, download == "1"


def _run_detail_payload(dataset_run_id: str, train_run_id: str) -> dict[str, Any]:
    manifest_path = RUNS_ROOT / dataset_run_id / train_run_id / "run_manifest.json"
    try:
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"status": "BLOCKED", "reason": "RUN_MANIFEST_MISSING"}
    return {
        "schema_version": "kronos_v6_run_detail.v1",
        "status": "OK",
        "dataset_run_id": dataset_run_id,
        "train_run_id": train_run_id,
        "manifest": manifest,
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "events_tail": _events_tail(manifest_path.with_name("events.jsonl")),
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
            "run_id": value.get("run_id", path.parent.name),
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
        dataset_run_id = value.get("dataset_run_id", path.parent.parent.name)
        runs.append({
            "run_id": value.get("run_id", path.parent.name),
            "dataset_run_id": dataset_run_id,
            "path": _artifact_path(path),
            "state": value.get("state"),
            "seeds": list(seeds) if isinstance(seeds, list) else [],
            "generated_utc": value.get("generated_utc"),
            "verdict_candidate": value.get("verdict_candidate"),
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


def _run_state() -> str:
    return _runs_payload()["training_state"]


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
        paths = sorted(path for path in INDEX_ARTIFACT_DIR.glob(INDEX_NORMALIZED_GLOB) if path.is_file())
    except OSError:
        return {}
    overlays: dict[str, dict[str, Any]] = {}
    for path in paths:
        try:
            stat = path.stat()
            key = path.as_posix()
            signature = (stat.st_mtime_ns, stat.st_size)
            cached = _INDEX_OVERLAY_CACHE.get(key)
            if cached is not None and cached[0] == signature:
                overlay = cached[1]
            else:
                overlay = validate_korean_index_artifact(path)
                _INDEX_OVERLAY_CACHE[key] = (signature, overlay)
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
    run_state = _run_state()
    return {
        "schema_version": "kronos_v6_platform_status.v1",
        "status": "OK",
        "journey": {
            "data": _journey_data(),
            "experiment": {"state": _experiment_state()},
            "training": {"state": run_state},
            "evaluation": {"state": run_state},
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
        if request.args:
            return _error(400, "BAD_REQUEST")
        return _response({
            "schema_version": "kronos_v6_reports.v1",
            "status": "OK",
            "reports": _report_entries(),
        })

    def report_html_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        try:
            dataset_run_id, train_run_id, download = _report_query()
        except ValueError:
            return _error(400, "BAD_REQUEST")
        run_dir = RUNS_ROOT / dataset_run_id / train_run_id
        manifest = _read_json(run_dir / "report_manifest.json")
        report_path = run_dir / "report.html"
        try:
            report_bytes = report_path.read_bytes()
        except OSError:
            return _response({"status": "BLOCKED", "reason": "REPORT_NOT_FOUND"}, 404)
        if manifest is None:
            return _response({"status": "BLOCKED", "reason": "REPORT_MANIFEST_MISSING"}, 404)
        if manifest.get("report_sha256") != hashlib.sha256(report_bytes).hexdigest():
            return _response({"status": "BLOCKED", "reason": "REPORT_SHA_MISMATCH"}, 409)
        response = Response(report_bytes, status=200, mimetype="text/html")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
        if download:
            response.headers["Content-Disposition"] = f'attachment; filename="kronos-report-{dataset_run_id}-{train_run_id}.html"'
        return response

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
    ):
        blueprint.add_url_rule(rule, endpoint=endpoint, view_func=handler, methods=list(ALL_ROUTE_METHODS), provide_automatic_options=False)
    return blueprint


create_blueprint = create_v6_platform_blueprint

__all__ = ["create_blueprint", "create_v6_platform_blueprint"]
