"""Fast governance first-viewport API that defers heavy run linkage."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Callable, Final, Mapping

from flask import Blueprint, Response, request

from .v6_governance_catalog import GovernanceCatalog, build_governance_catalog

DEFAULT_DOCS_ROOT: Final = Path(__file__).resolve().parent.parent / "docs"


def _response(payload: Mapping, status_code: int = 200) -> Response:
    return Response(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), status=status_code, mimetype="application/json")


def _error(status_code: int, code: str) -> Response:
    return _response({"status": "ERROR", "error": {"code": code}}, status_code)


def _method_not_allowed() -> Response:
    response = _error(405, "METHOD_NOT_ALLOWED")
    response.headers["Allow"] = "GET"
    return response


def _payload(catalog: GovernanceCatalog) -> Mapping:
    return {
        "schema_version": "kronos_v6_governance_summary.v1",
        "status": "OK",
        "generated_at": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "preregistrations": [
            {
                "prereg_id": item.prereg_id,
                "doc": item.doc,
                "status": item.status,
                "frozen_utc": item.frozen_utc,
                "family": item.family,
                "sha256": item.sha256,
                "linkage_state": item.linkage_state,
            }
            for item in catalog.preregistrations
        ],
        "result_docs": [
            {"doc": item.doc, "size_bytes": item.size_bytes, "sha256": item.sha256}
            for item in catalog.result_docs
        ],
        "claims": {"fresh_oos_opened": False, "promotion_allowed": False, "human_approval_required": True},
    }


def create_v6_governance_blueprint(
    *,
    docs_root: Path = DEFAULT_DOCS_ROOT,
    name: str = "v6_governance",
    url_prefix: str = "/api/v6",
    cache_ttl_seconds: float = 60.0,
    clock: Callable[[], float] = monotonic,
) -> Blueprint:
    blueprint = Blueprint(name, __name__, url_prefix=url_prefix)
    lock = Lock()
    cached: GovernanceCatalog | None = None
    expires_at = 0.0

    def snapshot() -> GovernanceCatalog:
        nonlocal cached, expires_at
        now = clock()
        if cached is not None and now < expires_at:
            return cached
        with lock:
            now = clock()
            if cached is not None and now < expires_at:
                return cached
            cached = build_governance_catalog(docs_root)
            expires_at = now + max(0.0, cache_ttl_seconds)
            return cached

    def handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        if request.args:
            return _error(400, "BAD_REQUEST")
        return _response(_payload(snapshot()))

    blueprint.add_url_rule("/governance-summary", endpoint="summary", view_func=handler, methods=["GET", "POST"], provide_automatic_options=False)
    return blueprint


__all__ = ["create_v6_governance_blueprint"]
