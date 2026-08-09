"""GET-only V6 telemetry API for recorded reinforcement-learning runs."""
from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from flask import Blueprint, Response, request

from .v6_research_api import DEFAULT_RUNS_ROOT
from .v6_research_catalog import resolve_run_directory
from .v6_run_telemetry import EVENT_FILE, discover_telemetry_runs, read_telemetry

MIN_POINTS: Final = 20
MAX_POINTS: Final = 500


def _response(payload: Mapping[str, object], status_code: int = 200) -> Response:
    return Response(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), status=status_code, mimetype="application/json")


def _error(status_code: int, code: str) -> Response:
    return _response({"status": "ERROR", "error": {"code": code}}, status_code)


def _method_not_allowed() -> Response:
    response = _error(405, "METHOD_NOT_ALLOWED")
    response.headers["Allow"] = "GET"
    return response


def _limit() -> int | None:
    if set(request.args) - {"limit"} or len(request.args.getlist("limit")) > 1:
        return None
    raw = request.args.get("limit", "240")
    if not raw.isascii() or not raw.isdecimal():
        return None
    value = int(raw)
    return value if MIN_POINTS <= value <= MAX_POINTS else None


def create_v6_telemetry_blueprint(
    *,
    runs_root: Path = DEFAULT_RUNS_ROOT,
    name: str = "v6_telemetry",
    url_prefix: str = "/api/v6",
) -> Blueprint:
    blueprint = Blueprint(name, __name__, url_prefix=url_prefix)

    def runs_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        if request.args:
            return _error(400, "BAD_REQUEST")
        rows = discover_telemetry_runs(runs_root)
        return _response(
            {
                "schema_version": "kronos_v6_telemetry_runs.v1",
                "status": "OK",
                "items": [
                    {
                        "run_id": row.run_id,
                        "name": row.name,
                        "lane": row.lane,
                        "status": row.status,
                        "algorithm": row.algorithm,
                        "event_bytes": row.event_bytes,
                        "updated_at": row.updated_at,
                    }
                    for row in rows
                ],
                "total": len(rows),
            }
        )

    def telemetry_handler(run_id: str) -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        limit = _limit()
        if limit is None:
            return _error(400, "BAD_REQUEST")
        directory = resolve_run_directory(runs_root, run_id)
        if directory is None:
            invalid = ".." in run_id or any(not segment for segment in run_id.split("/"))
            return _error(400 if invalid else 404, "BAD_REQUEST" if invalid else "RUN_NOT_FOUND")
        event_path = directory / EVENT_FILE
        if not event_path.is_file() or event_path.is_symlink():
            return _error(404, "TELEMETRY_NOT_FOUND")
        try:
            snapshot = read_telemetry(directory, limit=limit)
        except (OSError, UnicodeDecodeError):
            return _error(422, "TELEMETRY_UNREADABLE")
        return _response(
            {
                "schema_version": "kronos_v6_run_telemetry.v1",
                "status": "OK",
                "run_id": run_id,
                "follow_mode": snapshot.follow_mode,
                "sampling": snapshot.sampling,
                "event_bytes": snapshot.event_bytes,
                "invalid_lines": snapshot.invalid_lines,
                "updated_at": snapshot.updated_at,
                "points": [point.to_payload() for point in snapshot.points],
                "claims": {"live_stream": snapshot.follow_mode == "FOLLOWING_FILE", "profitability": False},
            }
        )

    blueprint.add_url_rule("/telemetry-runs", endpoint="runs", view_func=runs_handler, methods=["GET", "POST"], provide_automatic_options=False)
    blueprint.add_url_rule("/research-runs/<path:run_id>/telemetry", endpoint="run", view_func=telemetry_handler, methods=["GET", "POST"], provide_automatic_options=False)
    return blueprint


__all__ = ["create_v6_telemetry_blueprint"]
