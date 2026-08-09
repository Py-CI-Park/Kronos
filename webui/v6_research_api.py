"""Read-only, lightweight research catalog API for the unified V6 dashboard."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Callable, Final, Mapping, TypedDict

from flask import Blueprint, Response, request
from werkzeug.datastructures import MultiDict

from .v6_research_catalog import ResearchQuery, ResearchRun, discover_runs, filter_runs, resolve_run_directory
from .v6_research_outcomes import observe_outcome

DEFAULT_RUNS_ROOT: Final = Path(__file__).resolve().parent / "rl_runs"
ALLOWED_QUERY_KEYS: Final = frozenset({"search", "lane", "status", "page", "page_size"})
MAX_ARTIFACTS: Final = 100
PROGRAM_SCORES: Final = {
    "maturity_score": 70,
    "implementation_score": 94,
    "economic_model_score": 20,
    "live_readiness_score": 0,
}


class ArtifactPayload(TypedDict):
    name: str
    relative_path: str
    size_bytes: int
    modified_at: str


@dataclass(frozen=True, slots=True)
class ResearchQueryError(Exception):
    field: str

    def __str__(self) -> str:
        return f"invalid research query field: {self.field}"


def _response(payload: Mapping, status_code: int = 200) -> Response:
    return Response(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        status=status_code,
        mimetype="application/json",
    )


def _error(status_code: int, code: str) -> Response:
    return _response({"status": "ERROR", "error": {"code": code}}, status_code)


def _method_not_allowed() -> Response:
    response = _error(405, "METHOD_NOT_ALLOWED")
    response.headers["Allow"] = "GET"
    return response


def _single(args: MultiDict[str, str], key: str, default: str = "") -> str:
    values = args.getlist(key)
    if len(values) > 1:
        raise ResearchQueryError(field=key)
    return values[0] if values else default


def _positive_int(args: MultiDict[str, str], key: str, default: int, maximum: int) -> int:
    raw = _single(args, key, str(default))
    if not raw.isascii() or not raw.isdecimal():
        raise ResearchQueryError(field=key)
    value = int(raw)
    if not 1 <= value <= maximum:
        raise ResearchQueryError(field=key)
    return value


def parse_research_query(args: MultiDict[str, str]) -> ResearchQuery:
    """Parse the HTTP query boundary once into a typed immutable query."""
    unexpected = set(args) - ALLOWED_QUERY_KEYS
    if unexpected:
        raise ResearchQueryError(field=sorted(unexpected)[0])
    return ResearchQuery(
        search=_single(args, "search").strip(),
        lane=_single(args, "lane").strip(),
        status=_single(args, "status").strip(),
        page=_positive_int(args, "page", 1, 10_000),
        page_size=_positive_int(args, "page_size", 40, 200),
    )


def _artifact_payloads(root: Path, directory: Path) -> tuple[ArtifactPayload, ...]:
    try:
        files = sorted(
            (path for path in directory.iterdir() if path.is_file() and not path.is_symlink()),
            key=lambda path: path.name,
        )[:MAX_ARTIFACTS]
    except OSError:
        return ()
    payloads: list[ArtifactPayload] = []
    for path in files:
        try:
            stat_result = path.stat()
        except OSError:
            continue
        modified = datetime.fromtimestamp(stat_result.st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        payloads.append(
            {
                "name": path.name,
                "relative_path": path.relative_to(root).as_posix(),
                "size_bytes": stat_result.st_size,
                "modified_at": modified,
            }
        )
    return tuple(payloads)


def _run_by_id(rows: tuple[ResearchRun, ...], run_id: str) -> ResearchRun | None:
    return next((row for row in rows if row.run_id == run_id), None)


def create_v6_research_blueprint(
    *,
    runs_root: Path = DEFAULT_RUNS_ROOT,
    name: str = "v6_research",
    url_prefix: str = "/api/v6",
    catalog_ttl_seconds: float = 60.0,
    clock: Callable[[], float] = monotonic,
) -> Blueprint:
    """Create the GET-only research catalog blueprint."""
    blueprint = Blueprint(name, __name__, url_prefix=url_prefix)
    cache_lock = Lock()
    cached_rows = discover_runs(runs_root)
    cache_expires_at = clock() + max(0.0, catalog_ttl_seconds)

    def catalog_snapshot() -> tuple[ResearchRun, ...]:
        """Share one bounded snapshot across summary, catalog, and detail calls."""
        nonlocal cached_rows, cache_expires_at
        now = clock()
        if now < cache_expires_at:
            return cached_rows
        with cache_lock:
            now = clock()
            if now < cache_expires_at:
                return cached_rows
            cached_rows = discover_runs(runs_root)
            cache_expires_at = now + max(0.0, catalog_ttl_seconds)
            return cached_rows

    def summary_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        if request.args:
            return _error(400, "BAD_REQUEST")
        rows = catalog_snapshot()
        by_status = dict(sorted(Counter(row.status for row in rows).items()))
        latest = rows[0].to_payload() if rows else None
        return _response(
            {
                "schema_version": "kronos_v6_research_summary.v1",
                "status": "OK",
                "generated_at": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
                "program": PROGRAM_SCORES,
                "catalog": {"total": len(rows), "by_status": by_status, "latest_run": latest},
                "claims": {"profitability": False, "live_ready": False, "fresh_oos_opened": False},
            }
        )

    def catalog_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        try:
            query = parse_research_query(request.args)
        except ResearchQueryError:
            return _error(400, "BAD_REQUEST")
        page = filter_runs(catalog_snapshot(), query)
        return _response(
            {
                "schema_version": "kronos_v6_research_runs.v1",
                "status": "OK",
                "items": [row.to_payload() for row in page.items],
                "total": page.total,
                "page": page.page,
                "page_size": page.page_size,
            }
        )

    def detail_handler(run_id: str) -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        if request.args:
            return _error(400, "BAD_REQUEST")
        directory = resolve_run_directory(runs_root, run_id)
        if directory is None:
            invalid = ".." in run_id or any(not segment for segment in run_id.split("/"))
            return _error(400 if invalid else 404, "BAD_REQUEST" if invalid else "RUN_NOT_FOUND")
        rows = catalog_snapshot()
        run = _run_by_id(rows, run_id)
        if run is None:
            return _error(404, "RUN_NOT_FOUND")
        return _response(
            {
                "schema_version": "kronos_v6_research_run_detail.v1",
                "status": "OK",
                "run": run.to_payload(),
                "artifacts": list(_artifact_payloads(runs_root, directory)),
                "evidence_scope": "DIRECT_DIRECTORY_METADATA_ONLY",
                "observed_outcome": observe_outcome(directory, run.source_file),
            }
        )

    blueprint.add_url_rule("/summary", endpoint="summary", view_func=summary_handler, methods=["GET", "POST"], provide_automatic_options=False)
    blueprint.add_url_rule("/research-runs", endpoint="runs", view_func=catalog_handler, methods=["GET", "POST"], provide_automatic_options=False)
    blueprint.add_url_rule("/research-runs/<path:run_id>", endpoint="run_detail", view_func=detail_handler, methods=["GET", "POST"], provide_automatic_options=False)
    return blueprint


__all__ = ["create_v6_research_blueprint", "parse_research_query"]
