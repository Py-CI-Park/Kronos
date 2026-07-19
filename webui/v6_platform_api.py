"""Read-only V6 platform readiness API."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from flask import Blueprint, Response, request

WEBUI_ROOT: Final = Path(__file__).resolve().parent
REPO_ROOT: Final = WEBUI_ROOT.parent
MANIFEST_PATH: Final = REPO_ROOT / "docs" / "kronos_v6_universe_manifest_2026-07-19.json"
PREREG_PATH: Final = REPO_ROOT / "docs" / "kronos_v6_prereg_h1_2026-07-19.json"
RUN_DIR: Final = WEBUI_ROOT / "rl_runs" / "v6_daily_h1"
AUDIT_PATH: Final = WEBUI_ROOT / "rl_runs" / "daily_ohlcv_db_summary" / "v6_universe_audit.json"
DAILY_DB_PATH: Final = REPO_ROOT / "_database" / "Stock_Database_ohlcv_1day.db"
FIVEMIN_DB_PATH: Final = REPO_ROOT / "_database" / "Stock_Database_ohlcv_5min.db"
INDEX_ARTIFACT_DIR: Final = REPO_ROOT / "artifacts" / "korean_index"
INDEX_BLOCKER: Final = "BLOCKED_INDEX_SERIES_SOURCE"
INDEX_BLOCKER_REASON: Final = "KRX credentials required for pykrx collection"
SIX_FALSE_LOCKS: Final = {
    "promotion_allowed": False,
    "model_build_allowed": False,
    "paper_forward_allowed": False,
    "live_broker_order_allowed": False,
    "profitability_claim_allowed": False,
    "go_summary_allowed": False,
}
ALL_ROUTE_METHODS: Final = ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")


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


def _run_manifest_present() -> bool:
    try:
        candidates = tuple(RUN_DIR.glob("*manifest*.json"))
    except OSError:
        return False
    return any(_read_json(candidate) is not None for candidate in candidates if candidate.is_file())


def _journey_data() -> dict[str, Any]:
    manifest, _ = _manifest()
    if manifest is None:
        return {"state": "MISSING"}
    universe = manifest["universe"]
    return {
        "state": "PARTIAL",
        "universe_manifest": "docs/kronos_v6_universe_manifest_2026-07-19.json",
        "universe_size": len(universe),
        "index_overlay": INDEX_BLOCKER,
        "index_blocker_reason": INDEX_BLOCKER_REASON,
    }


def _experiment_state() -> str:
    return "FROZEN" if _read_json(PREREG_PATH) is not None else "NOT_FROZEN"


def _run_state() -> str:
    return "PRESENT" if _run_manifest_present() else "NOT_RUN"


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
    try:
        artifacts = [path for path in INDEX_ARTIFACT_DIR.glob("*.json") if path.is_file()]
    except OSError:
        artifacts = []
    if not artifacts:
        return {"state": INDEX_BLOCKER, "reason": INDEX_BLOCKER_REASON}
    valid_artifacts = [path for path in artifacts if _read_json(path) is not None]
    if not valid_artifacts:
        return {"state": "MISSING"}
    return {"state": "PRESENT", "artifact_count": len(valid_artifacts)}


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
            "report": {"state": "NOT_RUN"},
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

    for rule, endpoint, handler in (
        ("/status", "status", status_handler),
        ("/universe", "universe", universe_handler),
        ("/data-readiness", "data_readiness", readiness_handler),
    ):
        blueprint.add_url_rule(rule, endpoint=endpoint, view_func=handler, methods=list(ALL_ROUTE_METHODS), provide_automatic_options=False)
    return blueprint


create_blueprint = create_v6_platform_blueprint

__all__ = ["create_blueprint", "create_v6_platform_blueprint"]
