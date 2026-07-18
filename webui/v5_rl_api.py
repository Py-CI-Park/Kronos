"""Read-only Flask Blueprint for the canonical Kronos V5 RL API."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
from datetime import datetime, timezone
from decimal import Decimal
from functools import cmp_to_key, wraps
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from flask import Blueprint, Response, current_app, request

from stom_rl import v5_authority
from webui import v5_downloads
from webui.v5_api_contract import (
    ROUTE_DESCRIPTORS,
    MATRIX_ORDER,
    SIX_LOCKS,
    V5ApiContractError,
    decode_cursor,
    encode_cursor,
    event_payload_sha256,
    progress_percent,
    validate_payload,
)
from webui.v5_downloads import ALLOWED_DOWNLOAD_MEDIA_TYPES, DownloadError, MAX_DOWNLOAD_BYTES

WEBUI_ROOT = Path(__file__).resolve().parent
REPO_ROOT = WEBUI_ROOT.parent
DEFAULT_REGISTRY_PATH = WEBUI_ROOT / "rl_runs" / "kronos_v5_registry.sqlite"
DEFAULT_ARTIFACT_ROOT = WEBUI_ROOT / "rl_runs" / "kronos_v5_artifacts"
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_PAGE_LIMIT = 100
DEFAULT_PAGE_LIMIT = 100
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
ARTIFACT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
EVENT_GLOBAL_SEQ_ID_RE = re.compile(r"^global-seq-([0-9]{16})$")
EVENT_GLOBAL_SEQ_ID_WIDTH = 16
ALL_ROUTE_METHODS = ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
MEDIA_BY_SUFFIX = {suffix.removeprefix("."): media_type for suffix, media_type in ALLOWED_DOWNLOAD_MEDIA_TYPES.items()}
validate_payload.__globals__["_ARTIFACT_MEDIA"] = dict(MEDIA_BY_SUFFIX)
STATUS_MAP = {
    "QUEUED": "QUEUED",
    "PENDING": "QUEUED",
    "MATRIX_READY": "QUEUED",
    "RUNNING": "RUNNING",
    "CELL_RUNNING": "RUNNING",
    "IN_PROGRESS": "RUNNING",
    "DONE": "SUCCEEDED",
    "SUCCESS": "SUCCEEDED",
    "SUCCEEDED": "SUCCEEDED",
    "COMPLETED": "SUCCEEDED",
    "FAILED": "FAILED",
    "ERROR": "FAILED",
    "CANCELLED": "CANCELLED",
    "CANCELED": "CANCELLED",
    "STOPPED": "CANCELLED",
}
MATRIX_STATUS_MAP = {
    "PASS": "PASS",
    "SUCCEEDED": "PASS",
    "SUCCESS": "PASS",
    "COMPLETED": "PASS",
    "DONE": "PASS",
    "FAIL": "FAIL",
    "FAILED": "FAIL",
    "ERROR": "FAIL",
    "BLOCKED": "BLOCKED",
    "PENDING": "PENDING",
    "QUEUED": "PENDING",
    "RUNNING": "PENDING",
}


class ApiHttpError(Exception):
    """HTTP error with a canonical JSON API error code."""

    def __init__(self, status_code: int, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _clone(value: Any) -> Any:
    return json.loads(json.dumps(value, separators=(",", ":"), ensure_ascii=False))


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _utc(value: Any, *, fallback: str | None = None) -> str:
    if value in (None, ""):
        if fallback is None:
            raise ApiHttpError(422, "missing timestamp", code="VALIDATION_ERROR")
        return fallback
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z").replace(".000000Z", "Z")
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            parseable = text[:-1] + "+00:00"
        else:
            parseable = text
        try:
            parsed = datetime.fromisoformat(parseable)
        except ValueError as exc:
            raise ApiHttpError(422, "timestamp is not valid UTC", code="VALIDATION_ERROR") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z").replace(".000000Z", "Z")
    raise ApiHttpError(422, "timestamp has invalid type", code="VALIDATION_ERROR")


def _utc_sort_key(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _valid_sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _cursor_query_scope(run_id: str, revision: int) -> str:
    return _sha256_json({"revision": revision, "run_id": run_id})


def _coerce_cursor_key(cursor_key: bytes | str | None) -> bytes:
    if cursor_key is None:
        hex_key = os.environ.get("KRONOS_V5_RL_API_CURSOR_KEY_HEX")
        text_key = os.environ.get("KRONOS_V5_RL_API_CURSOR_KEY")
        cursor_key = hex_key or text_key
    if isinstance(cursor_key, bytes) and cursor_key:
        return cursor_key
    if isinstance(cursor_key, str) and cursor_key:
        stripped = cursor_key.strip()
        if re.fullmatch(r"[0-9a-fA-F]+", stripped) and len(stripped) % 2 == 0:
            return bytes.fromhex(stripped)
        return stripped.encode("utf-8")
    raise ValueError("cursor_key must be an explicit non-empty server secret")


def _resolve_repo_path(path: Path | str) -> Path:
    value = Path(path)
    if value.is_absolute():
        return value.resolve()
    return (REPO_ROOT / value).resolve()


def _error_code_for(status_code: int, message: str, preferred: str | None = None) -> str:
    if preferred in {"BAD_REQUEST", "NOT_FOUND", "INVALID_CURSOR", "VALIDATION_ERROR", "INTERNAL_ERROR"}:
        return preferred
    lower = message.lower()
    if "cursor" in lower:
        return "INVALID_CURSOR"
    if status_code == 404:
        return "NOT_FOUND"
    if status_code in {409, 413, 422}:
        return "VALIDATION_ERROR"
    if status_code == 400:
        return "BAD_REQUEST"
    return "INTERNAL_ERROR"


def _route_allowed_error_code(route_id: str, code: str, status_code: int, message: str) -> str:
    allowed = set(ROUTE_DESCRIPTORS.get(route_id, {}).get("allowed_errors", ()))
    if not allowed or code in allowed:
        return code
    if code == "VALIDATION_ERROR" and "INTERNAL_ERROR" in allowed:
        return "INTERNAL_ERROR"
    lower = message.lower()
    for candidate in (
        "INVALID_CURSOR" if code == "INVALID_CURSOR" or (status_code in {400, 410} and "cursor" in lower) else "",
        "BAD_REQUEST" if status_code == 400 else "",
        "NOT_FOUND" if status_code == 404 else "",
        "INTERNAL_ERROR",
    ):
        if candidate in allowed:
            return candidate
    return next(iter(sorted(allowed)), "INTERNAL_ERROR")


def _error_payload(route_id: str, status_code: int, message: str, preferred: str | None = None) -> dict[str, Any]:
    code = _route_allowed_error_code(route_id, _error_code_for(status_code, message, preferred), status_code, message)
    return {"route_id": route_id, "error": {"code": code, "message": message or "request failed"}}


def _json_response(payload: Mapping[str, Any], status_code: int = 200, *, enforce_cap: bool = True) -> Response:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if enforce_cap and len(raw) > MAX_JSON_BYTES:
        raise ApiHttpError(413, "JSON response exceeds 2MiB cap", code="VALIDATION_ERROR")
    return current_app.response_class(raw, status=status_code, mimetype="application/json")


def _registry_http_error(exc: Exception) -> ApiHttpError:
    name = exc.__class__.__name__
    raw_status = getattr(exc, "status_code", None)
    status = raw_status if isinstance(raw_status, int) else None
    known = status is not None
    if status is None:
        if "BadRequest" in name:
            status = 400
            known = True
        elif "NotFound" in name:
            status = 404
            known = True
        elif "Gone" in name:
            status = 410
            known = True
        elif "Conflict" in name:
            status = 409
            known = True
        elif "TooLarge" in name:
            status = 413
            known = True
        elif "Corrupt" in name or "Unavailable" in name:
            status = 503
            known = True
        else:
            status = 503
    preferred = getattr(exc, "code", None)
    message = str(getattr(exc, "message", None) or exc or name) if known else "internal server error"
    return ApiHttpError(status, message, code=preferred if isinstance(preferred, str) else None)


def _call_registry(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - registry publishes its own exception classes.
        raise _registry_http_error(exc) from exc


def _require_get(route_id: str) -> Response | None:
    if request.method == "GET":
        return None
    response = _json_response(_error_payload(route_id, 405, "method not allowed", "BAD_REQUEST"), 405, enforce_cap=False)
    response.headers["Allow"] = "GET"
    return response


def _validate_scoped_cursor_success(payload: Mapping[str, Any], *, cursor_key: bytes, cursor: str | None, cursor_scope: str) -> None:
    route_id = str(payload["route_id"])
    root_hash = str(payload["source"]["source_sha256"])
    items = payload["list"]["items"]
    previous_key = decode_cursor(cursor, route_id, root_hash, key=cursor_key, run_id=cursor_scope) if cursor is not None else None
    if previous_key is not None and (not items or _compare_page_keys(route_id, previous_key, _page_key(route_id, items[0])) >= 0):
        raise V5ApiContractError("page does not begin strictly after request cursor")
    next_cursor = payload["list"]["next_cursor"]
    if next_cursor is not None:
        next_key = decode_cursor(next_cursor, route_id, root_hash, key=cursor_key, run_id=cursor_scope)
        if not items or next_key != _page_key(route_id, items[-1]):
            raise V5ApiContractError("next_cursor must bind the final emitted page item")


def _validate_success(payload: Mapping[str, Any], *, cursor_key: bytes, cursor: str | None, cursor_scope: str | None = None) -> None:
    try:
        if cursor_scope is None:
            validate_payload(payload, cursor_key=cursor_key, cursor=cursor)
        else:
            validation_payload = _clone(payload)
            validation_payload["list"]["next_cursor"] = None
            validate_payload(validation_payload, cursor_key=cursor_key, cursor=None)
            _validate_scoped_cursor_success(payload, cursor_key=cursor_key, cursor=cursor, cursor_scope=cursor_scope)
    except V5ApiContractError as exc:
        raise ApiHttpError(422, str(exc), code="VALIDATION_ERROR") from exc


def _route(bp: Blueprint, rule: str, route_id: str, endpoint: str) -> Callable[[Callable[..., Mapping[str, Any] | Response]], Callable[..., Response]]:
    def decorator(fn: Callable[..., Mapping[str, Any] | Response]) -> Callable[..., Response]:
        @bp.route(rule, endpoint=endpoint, methods=list(ALL_ROUTE_METHODS), provide_automatic_options=False)
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Response:
            method_error = _require_get(route_id)
            if method_error is not None:
                return method_error
            try:
                result = fn(*args, **kwargs)
                if isinstance(result, Response):
                    return result
                return _json_response(result)
            except ApiHttpError as exc:
                return _json_response(_error_payload(route_id, exc.status_code, exc.message, exc.code), exc.status_code, enforce_cap=False)
            except Exception:  # noqa: BLE001 - fail closed with a JSON envelope.
                return _json_response(_error_payload(route_id, 503, "internal server error", "INTERNAL_ERROR"), 503, enforce_cap=False)
        return wrapper
    return decorator


def _registry_factory(registry_path: Path | str | None, cursor_key: bytes) -> Any:
    from stom_rl.v5_registry import KronosV5Registry  # Imported lazily so tests can inject fakes before registry exists.

    return KronosV5Registry(registry_path or DEFAULT_REGISTRY_PATH, cursor_keys={"api": cursor_key})


def _identity(registry: Any) -> Mapping[str, Any]:
    identity = _call_registry(registry.identity)
    if not isinstance(identity, Mapping):
        return {
            "source_sha256": v5_authority.ZERO_SHA256,
            "generated_at": _utc_now(),
        }
    source_sha = identity.get("source_sha256") or identity.get("genesis_hash") or identity.get("registry_sha256") or v5_authority.ZERO_SHA256
    if not _valid_sha(source_sha):
        source_sha = v5_authority.ZERO_SHA256
    return {"source_sha256": source_sha, "generated_at": _utc(identity.get("created_utc") or identity.get("generated_at"), fallback=_utc_now())}


def _source_from_snapshot(snapshot: Mapping[str, Any], fallback: Mapping[str, Any] | None = None) -> dict[str, Any]:
    nested_source = snapshot.get("source") if isinstance(snapshot.get("source"), Mapping) else {}
    source_sha = (
        snapshot.get("source_sha256")
        or snapshot.get("protocol_sha256")
        or nested_source.get("source_sha256")
        or (fallback or {}).get("source_sha256")
        or _sha256_json(snapshot)
    )
    if not _valid_sha(source_sha):
        source_sha = _sha256_json(snapshot)
    generated_at = snapshot.get("updated_at") or snapshot.get("updated_utc") or nested_source.get("generated_at") or (fallback or {}).get("generated_at") or _utc_now()
    return {"source_sha256": source_sha, "generated_at": _utc(generated_at, fallback=_utc_now())}


def _snapshot_from_read(read: Any) -> Mapping[str, Any]:
    snapshot = _get(read, "snapshot", read)
    if not isinstance(snapshot, Mapping):
        raise ApiHttpError(422, "registry snapshot is not an object", code="VALIDATION_ERROR")
    return snapshot


def _snapshot_run_uid(snapshot: Mapping[str, Any]) -> str | None:
    value = snapshot.get("run_uid") or snapshot.get("run_id") or snapshot.get("uid") or snapshot.get("uuid")
    return str(value) if isinstance(value, str) else None


def _snapshot_revision(snapshot: Mapping[str, Any], read: Any | None = None) -> int | None:
    for value in (
        _get(read, "run_revision", None) if read is not None else None,
        snapshot.get("run_revision"),
        snapshot.get("revision"),
        snapshot.get("snapshot_revision"),
    ):
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _require_revision_value(value: int | None, label: str = "run_revision") -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 9007199254740991:
        raise ApiHttpError(422, f"{label} is outside the safe integer range", code="VALIDATION_ERROR")
    return value


def _require_run_id(value: str, label: str = "run_id") -> str:
    if not RUN_ID_RE.fullmatch(value or ""):
        raise ApiHttpError(400, f"{label} is not portable", code="BAD_REQUEST")
    return value

def _event_global_seq(value: Mapping[str, Any]) -> int | None:
    raw = value.get("global_seq")
    if isinstance(raw, int) and not isinstance(raw, bool) and 1 <= raw <= 9007199254740991:
        return raw
    return None


def _require_event_global_seq(value: Mapping[str, Any]) -> int:
    global_seq = _event_global_seq(value)
    if global_seq is None:
        raise ApiHttpError(422, "registry event global_seq is required", code="VALIDATION_ERROR")
    return global_seq


def _event_id_from_global_seq(global_seq: int) -> str:
    return f"global-seq-{global_seq:0{EVENT_GLOBAL_SEQ_ID_WIDTH}d}"


def _event_after_global_seq(cursor_page_key: Mapping[str, Any] | None) -> int:
    if cursor_page_key is None:
        return 0
    event_id = cursor_page_key.get("event_id")
    if not isinstance(event_id, str):
        raise ApiHttpError(400, "events cursor event_id is not a registry global sequence", code="INVALID_CURSOR")
    match = EVENT_GLOBAL_SEQ_ID_RE.fullmatch(event_id)
    if match is None:
        raise ApiHttpError(400, "events cursor event_id is not a registry global sequence", code="INVALID_CURSOR")
    return int(match.group(1))



def _require_artifact_id(value: str) -> str:
    if not ARTIFACT_ID_RE.fullmatch(value or ""):
        raise ApiHttpError(400, "artifact_id is invalid", code="BAD_REQUEST")
    return value


def _single_query_arg(name: str, *, required: bool = False) -> str | None:
    values = request.args.getlist(name)
    if not values:
        if required:
            raise ApiHttpError(400, f"missing required query parameter: {name}", code="BAD_REQUEST")
        return None
    if len(values) != 1 or values[0] == "":
        raise ApiHttpError(400, f"query parameter {name} must appear exactly once", code="BAD_REQUEST")
    return values[0]


def _revision_arg() -> int:
    raw = _single_query_arg("revision", required=True)
    assert raw is not None
    if not re.fullmatch(r"[1-9][0-9]{0,15}", raw):
        raise ApiHttpError(400, "revision must be a positive integer", code="BAD_REQUEST")
    revision = int(raw)
    if revision > 9007199254740991:
        raise ApiHttpError(400, "revision exceeds the safe integer range", code="BAD_REQUEST")
    return revision


def _run_query_args() -> tuple[str, int]:
    raw = _single_query_arg("run_id", required=True)
    assert raw is not None
    return _require_run_id(raw), _revision_arg()


def _limit_arg(default: int = DEFAULT_PAGE_LIMIT) -> int:
    raw = _single_query_arg("limit")
    if raw is None:
        return default
    if not re.fullmatch(r"[1-9][0-9]{0,8}", raw):
        raise ApiHttpError(400, "limit must be a positive integer", code="BAD_REQUEST")
    limit = int(raw)
    if limit > MAX_PAGE_LIMIT:
        raise ApiHttpError(413, "limit exceeds the frozen page size of 100", code="VALIDATION_ERROR")
    return limit


def _cursor_arg(route_id: str, source_sha256: str, cursor_key: bytes, *, run_id: str | None = None) -> tuple[str | None, dict[str, Any] | None]:
    cursor = _single_query_arg("cursor")
    if cursor is None:
        return None, None
    try:
        return cursor, decode_cursor(cursor, route_id, source_sha256, key=cursor_key, run_id=run_id)
    except V5ApiContractError as exc:
        raise ApiHttpError(400, str(exc), code="INVALID_CURSOR") from exc


def _progress(raw: Any, *, status: str, fallback_step: Any = None, fallback_total: Any = None) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        step = raw.get("step", fallback_step)
        total = raw.get("total_steps", raw.get("total", fallback_total))
    else:
        step = fallback_step
        total = fallback_total
    if not isinstance(total, int) or isinstance(total, bool) or total < 1:
        total = 1
    if not isinstance(step, int) or isinstance(step, bool) or step < 0:
        step = 0
    step = min(step, total)
    if status == "QUEUED":
        step = 0
    if status == "SUCCEEDED":
        step = total
    percent = progress_percent(step, total)
    return {"step": step, "total_steps": total, "percent": float(percent)}


def _state(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    state = snapshot.get("state") if isinstance(snapshot.get("state"), Mapping) else snapshot
    terminal_status = snapshot.get("terminal") if isinstance(snapshot.get("terminal"), str) else None
    raw_status = str(terminal_status or state.get("status") or snapshot.get("phase") or snapshot.get("lifecycle_state") or "RUNNING").upper()
    status = STATUS_MAP.get(raw_status, STATUS_MAP.get(str(snapshot.get("status") or "").upper(), "RUNNING"))
    updated_at = _utc(state.get("updated_at") or state.get("updated_utc") or snapshot.get("updated_at") or snapshot.get("updated_utc") or snapshot.get("occurred_at"), fallback=_utc_now())
    created_at = _utc(snapshot.get("created_at") or snapshot.get("created_utc") or updated_at, fallback=updated_at)
    started_raw = state.get("started_at") or state.get("started_utc") or snapshot.get("started_at") or snapshot.get("started_utc")
    finished_raw = state.get("finished_at") or state.get("finished_utc") or snapshot.get("finished_at") or snapshot.get("finished_utc") or snapshot.get("completed_at") or snapshot.get("completed_utc")
    if status == "QUEUED":
        started_at = None
        finished_at = None
    elif status == "RUNNING":
        started_at = _utc(started_raw, fallback=created_at)
        finished_at = None
    else:
        started_at = _utc(started_raw, fallback=created_at)
        finished_at = _utc(finished_raw, fallback=updated_at)
    progress = _progress(state.get("progress"), status=status, fallback_step=state.get("step") or snapshot.get("step"), fallback_total=state.get("total_steps") or snapshot.get("total_steps") or snapshot.get("steps_per_cell"))
    return {"status": status, "progress": progress, "updated_at": updated_at, "started_at": started_at, "finished_at": finished_at}


def _run(snapshot: Mapping[str, Any], source: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = dict(source or _source_from_snapshot(snapshot))
    run_uid = _snapshot_run_uid(snapshot)
    if not run_uid:
        raise ApiHttpError(422, "snapshot has no run UID", code="VALIDATION_ERROR")
    run_id = str(snapshot.get("run_id") or run_uid)
    _require_run_id(run_id)
    _require_run_id(run_uid, "run_uid")
    run_revision = _require_revision_value(_snapshot_revision(snapshot))
    created_at = _utc(snapshot.get("created_at") or snapshot.get("created_utc") or snapshot.get("started_at") or snapshot.get("updated_at"), fallback=source["generated_at"])
    return {"run_id": run_id, "run_uid": run_uid, "run_revision": run_revision, "state": _state(snapshot), "source_sha256": source["source_sha256"], "created_at": created_at}


def _read_run(registry: Any, run_id: str, revision: int) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    read = _call_registry(registry.get_run, run_id, revision=revision)
    snapshot = _snapshot_from_read(read)
    observed_uid = _snapshot_run_uid(snapshot)
    observed_revision = _snapshot_revision(snapshot, read)
    if observed_uid != run_id or observed_revision != revision:
        raise ApiHttpError(409, "registry run UID or revision conflicts with the request", code="VALIDATION_ERROR")
    source = _source_from_snapshot(snapshot, _identity(registry))
    return snapshot, source


def _page_key(route_id: str, item: Mapping[str, Any]) -> dict[str, Any]:
    source = item.get("artifact", item)
    return {term.split(":", 1)[0]: source[term.split(":", 1)[0]] for term in ROUTE_DESCRIPTORS[route_id]["order"]}


def _compare_page_keys(route_id: str, left: Mapping[str, Any], right: Mapping[str, Any]) -> int:
    for term in ROUTE_DESCRIPTORS[route_id]["order"]:
        field, direction = term.split(":", 1)
        left_value, right_value = left[field], right[field]
        if field.endswith("_at"):
            left_value, right_value = _utc_sort_key(str(left_value)), _utc_sort_key(str(right_value))
        if left_value == right_value:
            continue
        comparison = -1 if left_value < right_value else 1
        return -comparison if direction == "desc" else comparison
    return 0


def _sort_items(route_id: str, items: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(items, key=cmp_to_key(lambda left, right: _compare_page_keys(route_id, _page_key(route_id, left), _page_key(route_id, right))))


def _paginate(
    route_id: str,
    items: list[Mapping[str, Any]],
    *,
    source_sha256: str,
    cursor_key: bytes,
    request_cursor_key: Mapping[str, Any] | None,
    limit: int,
    cursor_scope: str | None = None,
    registry_has_more: bool = False,
) -> tuple[list[Mapping[str, Any]], str | None]:
    ordered = _sort_items(route_id, items)
    if request_cursor_key is not None:
        ordered = [item for item in ordered if _compare_page_keys(route_id, request_cursor_key, _page_key(route_id, item)) < 0]
    has_more = registry_has_more or len(ordered) > limit
    page = ordered[:limit]
    next_cursor = None
    if has_more and page:
        next_cursor = encode_cursor(route_id, source_sha256, _page_key(route_id, page[-1]), key=cursor_key, run_id=cursor_scope)
    return page, next_cursor


def _page_parts(page: Any) -> tuple[list[Any], bool]:
    if isinstance(page, list):
        return list(page), False
    items = _get(page, "items", [])
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
        raise ApiHttpError(422, "registry page items are invalid", code="VALIDATION_ERROR")
    next_value = _get(page, "next_cursor", None) or _get(page, "next_after_global_seq", None)
    return list(items), next_value is not None


def _event_progress(value: Mapping[str, Any]) -> dict[str, Any]:
    progress = value.get("progress") if isinstance(value.get("progress"), Mapping) else {}
    return _progress(progress, status="RUNNING", fallback_step=value.get("step"), fallback_total=value.get("total_steps"))


def _event(raw: Mapping[str, Any], run_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    event_type = str(raw.get("event_type") or raw.get("event_kind") or "MESSAGE").upper()
    event_snapshot = raw.get("snapshot") if isinstance(raw.get("snapshot"), Mapping) else run_snapshot
    global_seq = _require_event_global_seq(raw)
    event_id = _event_id_from_global_seq(global_seq)
    if raw.get("created_utc") in (None, ""):
        raise ApiHttpError(422, "registry event created_utc is required", code="VALIDATION_ERROR")
    occurred_at = _utc(raw.get("created_utc"))
    if event_type == "PROGRESS":
        progress_source = raw if isinstance(raw.get("progress"), Mapping) else event_snapshot
        event = {"event_type": "PROGRESS", "event_id": event_id, "occurred_at": occurred_at, "progress": _event_progress(progress_source)}
    elif event_type == "STATE":
        event = {"event_type": "STATE", "event_id": event_id, "occurred_at": occurred_at, "state": _state(raw.get("state") if isinstance(raw.get("state"), Mapping) else event_snapshot)}
    elif event_type in {"ARTIFACT", "CHECKPOINT"} and (raw.get("artifact_id") or raw.get("artifact_refs") or raw.get("checkpoint_ref")):
        artifact_id = raw.get("artifact_id")
        if artifact_id is None and isinstance(raw.get("checkpoint_ref"), Mapping):
            artifact_id = str(raw["checkpoint_ref"].get("uri", "checkpoint")).rsplit("/", 1)[-1]
        if artifact_id is None and isinstance(raw.get("artifact_refs"), Sequence) and raw.get("artifact_refs"):
            first = raw["artifact_refs"][0]
            artifact_id = str(first.get("uri", "artifact") if isinstance(first, Mapping) else first).rsplit("/", 1)[-1]
        event = {"event_type": "ARTIFACT", "event_id": event_id, "occurred_at": occurred_at, "artifact_id": str(artifact_id or "artifact")[:128]}
    else:
        level = str(raw.get("level") or "INFO").upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            level = "INFO"
        event = {"event_type": "MESSAGE", "event_id": event_id, "occurred_at": occurred_at, "level": level, "message": str(raw.get("message") or raw.get("phase") or event_type)}
    event["payload_sha256"] = v5_authority.ZERO_SHA256
    event["payload_sha256"] = event_payload_sha256(event)
    return event


def _paginate_events_by_registry_order(
    raw_items: Sequence[Any],
    run_snapshot: Mapping[str, Any],
    *,
    source_sha256: str,
    cursor_key: bytes,
    request_cursor_key: Mapping[str, Any] | None,
    cursor_scope: str,
    limit: int,
    after_global_seq: int,
    registry_has_more: bool,
) -> tuple[list[Mapping[str, Any]], str | None]:
    events: list[Mapping[str, Any]] = []
    previous_seq = after_global_seq
    previous_key = request_cursor_key
    previous_occurred_at = None
    if previous_key is not None:
        try:
            previous_occurred_at = _utc_sort_key(str(previous_key["occurred_at"]))
        except (KeyError, ValueError) as exc:
            raise ApiHttpError(400, "events cursor occurred_at is invalid", code="INVALID_CURSOR") from exc
    for raw in raw_items:
        if not isinstance(raw, Mapping):
            raise ApiHttpError(422, "registry event page items are invalid", code="VALIDATION_ERROR")
        global_seq = _require_event_global_seq(raw)
        if global_seq <= previous_seq:
            raise ApiHttpError(422, "registry event global_seq is not strictly increasing", code="VALIDATION_ERROR")
        event = _event(raw, run_snapshot)
        event_key = _page_key("EVENTS", event)
        event_occurred_at = _utc_sort_key(str(event["occurred_at"]))
        if previous_occurred_at is not None and event_occurred_at <= previous_occurred_at:
            raise ApiHttpError(422, "registry event created_utc is not strictly increasing", code="VALIDATION_ERROR")
        if previous_key is not None and _compare_page_keys("EVENTS", previous_key, event_key) >= 0:
            raise ApiHttpError(422, "registry event order diverges from global sequence", code="VALIDATION_ERROR")
        events.append(event)
        previous_seq = global_seq
        previous_key = event_key
        previous_occurred_at = event_occurred_at
    page_items = events[:limit]
    has_more = registry_has_more or len(events) > limit
    next_cursor = None
    if has_more and page_items:
        next_cursor = encode_cursor("EVENTS", source_sha256, _page_key("EVENTS", page_items[-1]), key=cursor_key, run_id=cursor_scope)
    return page_items, next_cursor




def _matrix_cell_state(value: Any) -> str:
    return MATRIX_STATUS_MAP.get(str(value or "PENDING").upper(), "BLOCKED")


def _matrix_cells(matrix_read: Any, snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_cells = _get(matrix_read, "cells", None)
    if raw_cells is None:
        raw_cells = snapshot.get("cells", [])
    lookup: dict[tuple[str, str], str] = {}
    if isinstance(raw_cells, Sequence) and not isinstance(raw_cells, (str, bytes, bytearray)):
        for raw in raw_cells:
            if not isinstance(raw, Mapping):
                continue
            row_id = raw.get("row_id") or raw.get("seed_id")
            column_id = raw.get("column_id")
            if column_id is None and raw.get("fold_id") and raw.get("variant_id"):
                column_id = f"{raw['fold_id']}:{raw['variant_id']}"
            if isinstance(row_id, str) and isinstance(column_id, str):
                lookup[(row_id, column_id)] = _matrix_cell_state(raw.get("state") or raw.get("status"))
    cells = [{"row_id": row, "column_id": column, "state": lookup.get((row, column), "BLOCKED")} for row, column in MATRIX_ORDER]
    return cells


def _matrix_summary(cells: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "total_cells": 50,
        "pass_count": sum(cell["state"] == "PASS" for cell in cells),
        "fail_count": sum(cell["state"] == "FAIL" for cell in cells),
        "blocked_count": sum(cell["state"] == "BLOCKED" for cell in cells),
        "pending_count": sum(cell["state"] == "PENDING" for cell in cells),
    }


def _ledger_entries(snapshot: Mapping[str, Any], source: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_entries = snapshot.get("ledger_entries") or snapshot.get("ledger") or []
    if isinstance(raw_entries, Mapping):
        raw_entries = raw_entries.get("items", [])
    if not isinstance(raw_entries, Sequence) or isinstance(raw_entries, (str, bytes, bytearray)):
        raise ApiHttpError(422, "ledger entries are invalid", code="VALIDATION_ERROR")
    entries: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_entries, 1):
        if not isinstance(raw, Mapping):
            continue
        kind = str(raw.get("kind") or "ADJUSTMENT").upper()
        if kind not in {"DEBIT", "CREDIT", "ADJUSTMENT"}:
            kind = "ADJUSTMENT"
        amount = raw.get("amount", 0)
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            amount = 0
        entries.append({
            "entry_id": str(raw.get("entry_id") or raw.get("id") or f"entry-{index}"),
            "occurred_at": _utc(raw.get("occurred_at") or raw.get("created_at") or snapshot.get("updated_at"), fallback=source["generated_at"]),
            "kind": kind,
            "amount": amount,
            "currency": "KRONOS_CREDIT",
            "source_sha256": source["source_sha256"],
        })
    return entries


def _artifact(raw: Mapping[str, Any], source: Mapping[str, Any], *, requested_run_id: str | None = None, requested_revision: int | None = None) -> dict[str, Any]:
    nested = raw.get("artifact") if isinstance(raw.get("artifact"), Mapping) else raw
    artifact_id = str(nested.get("artifact_id") or nested.get("id") or "")
    _require_artifact_id(artifact_id)
    observed_run_id = nested.get("run_id") or nested.get("run_uid") or raw.get("run_id") or raw.get("run_uid")
    observed_revisions = [
        value
        for value in (nested.get("revision"), nested.get("run_revision"), raw.get("revision"), raw.get("run_revision"))
        if isinstance(value, int) and not isinstance(value, bool)
    ]
    if requested_run_id is not None and observed_run_id is not None and observed_run_id != requested_run_id:
        raise ApiHttpError(409, "artifact run UID conflicts with the request", code="VALIDATION_ERROR")
    if requested_revision is not None and any(value != requested_revision for value in observed_revisions):
        raise ApiHttpError(409, "artifact revision conflicts with the request", code="VALIDATION_ERROR")
    filename = str(nested.get("filename") or f"{artifact_id}.json")
    suffix = filename.rsplit(".", 1)[-1].casefold() if "." in filename else "json"
    if suffix not in MEDIA_BY_SUFFIX:
        raise ApiHttpError(422, "artifact extension is not downloadable", code="VALIDATION_ERROR")
    media_type = str(nested.get("media_type") or MEDIA_BY_SUFFIX[suffix])
    if media_type != MEDIA_BY_SUFFIX[suffix]:
        raise ApiHttpError(422, "artifact media_type does not match extension", code="VALIDATION_ERROR")
    byte_length = nested.get("byte_length", nested.get("size_bytes", 0))
    if not isinstance(byte_length, int) or isinstance(byte_length, bool) or byte_length < 0:
        raise ApiHttpError(422, "artifact byte_length is invalid", code="VALIDATION_ERROR")
    if byte_length > MAX_DOWNLOAD_BYTES:
        raise ApiHttpError(413, "artifact exceeds the 25MiB boundary", code="VALIDATION_ERROR")
    sha256 = nested.get("sha256") or nested.get("content_sha256") or source["source_sha256"]
    if not _valid_sha(sha256):
        raise ApiHttpError(422, "artifact sha256 is invalid", code="VALIDATION_ERROR")
    return {"artifact_id": artifact_id, "filename": filename, "media_type": media_type, "byte_length": byte_length, "sha256": sha256, "created_at": _utc(nested.get("created_at") or nested.get("created_utc"), fallback=source["generated_at"])}


def _download(raw: Mapping[str, Any], source: Mapping[str, Any], *, requested_run_id: str | None = None, requested_revision: int | None = None) -> dict[str, Any]:
    artifact = _artifact(raw, source, requested_run_id=requested_run_id, requested_revision=requested_revision)
    run_id = requested_run_id or str(raw.get("run_id") or raw.get("run_uid") or "")
    if not run_id:
        raise ApiHttpError(422, "download run_id is missing", code="VALIDATION_ERROR")
    _require_run_id(run_id)
    run_revision = _require_revision_value(requested_revision if requested_revision is not None else _snapshot_revision(raw))
    return {"artifact": artifact, "download_url": f"/api/v5/rl/artifacts/{artifact['artifact_id']}/download", "portable_filename": artifact["filename"], "run_id": run_id, "run_revision": run_revision}


def _download_registry_snapshot(raw: Mapping[str, Any]) -> dict[str, Any]:
    nested = raw.get("artifact") if isinstance(raw.get("artifact"), Mapping) else raw
    record = dict(nested)
    for key in ("path", "relative_path", "storage_path", "absolute_path", "artifact_path"):
        value = nested.get(key) or raw.get(key)
        if isinstance(value, str) and value:
            record["path"] = value
            break
    return {"schema": "kronos_rl_run_state.v2", "artifacts": [record]}


def _download_http_error(exc: DownloadError) -> ApiHttpError:
    if exc.status_code == 400:
        code = "BAD_REQUEST"
    elif exc.status_code == 404:
        code = "NOT_FOUND"
    elif exc.status_code in {410, 413, 422}:
        code = "VALIDATION_ERROR"
    else:
        code = "INTERNAL_ERROR"
    return ApiHttpError(exc.status_code, exc.message, code=code)


def _source_from_evidence_result(result: Mapping[str, Any], *, fallback_time: str | None = None) -> dict[str, Any]:
    source_sha = result.get("evidence_sha256") if _valid_sha(result.get("evidence_sha256")) else v5_authority.ZERO_SHA256
    return {"source_sha256": source_sha, "generated_at": _utc(fallback_time, fallback=_utc_now())}


def _read_bytes(path: Path | str | None) -> bytes | None:
    if path is None:
        return None
    return _resolve_repo_path(path).read_bytes()


def _d0_payload(evidence_path: Path | str | None) -> dict[str, Any]:
    raw = _read_bytes(evidence_path)
    if raw is None:
        result = v5_authority.read_d0_price_basis_evidence()
        evidence: Mapping[str, Any] = {}
    else:
        evidence = json.loads(raw.decode("utf-8"))
        result = v5_authority.evaluate_d0_price_basis_evidence(raw)
    statement = evidence.get("statement") if isinstance(evidence.get("statement"), Mapping) else {}
    updated_at = statement.get("issued_at") or _utc_now()
    source = _source_from_evidence_result(result, fallback_time=updated_at)
    verified = result.get("status") == "VERIFIED"
    basis = statement.get("price_basis", {}).get("basis") if isinstance(statement.get("price_basis"), Mapping) else None
    if basis not in {"RAW", "ADJUSTED"} or not verified:
        basis = "UNKNOWN"
    return {"route_id": "D0", "source": source, "d0": {"status": "PASS" if verified else "BLOCKED", "price_basis": basis, "source_sha256": source["source_sha256"], "updated_at": _utc(updated_at, fallback=source["generated_at"])}, "locks": dict(SIX_LOCKS)}


def _d1_payload(evidence_path: Path | str | None) -> dict[str, Any]:
    raw = _read_bytes(evidence_path)
    if raw is None:
        result = v5_authority.read_d1_universe_evidence()
        evidence: Mapping[str, Any] = {}
    else:
        evidence = json.loads(raw.decode("utf-8"))
        result = v5_authority.evaluate_d1_universe_evidence(raw)
    statement = evidence.get("statement") if isinstance(evidence.get("statement"), Mapping) else {}
    updated_at = statement.get("issued_at") or _utc_now()
    source = _source_from_evidence_result(result, fallback_time=updated_at)
    verified = result.get("status") == "VERIFIED"
    universe = "OFFICIAL" if verified else "UNKNOWN"
    return {"route_id": "D1", "source": source, "d1": {"status": "PASS" if verified else "BLOCKED", "universe": universe, "source_sha256": source["source_sha256"], "updated_at": _utc(updated_at, fallback=source["generated_at"])}, "locks": dict(SIX_LOCKS)}


def _is_loopback() -> bool:
    remote = request.remote_addr or ""
    try:
        return ipaddress.ip_address(remote).is_loopback
    except ValueError:
        return remote in {"localhost"}


def _fixture_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("route_id") == "FIXTURE":
        return _clone(value)
    fixture = value.get("fixture") if isinstance(value.get("fixture"), Mapping) else value
    if not isinstance(fixture, Mapping):
        raise ApiHttpError(503, "fixture health payload is unavailable", code="INTERNAL_ERROR")
    run = fixture.get("run") if isinstance(fixture.get("run"), Mapping) else None
    if run is None:
        raise ApiHttpError(503, "fixture health payload has no run", code="INTERNAL_ERROR")
    source = {"source_sha256": fixture.get("source_sha256") or run.get("source_sha256") or v5_authority.ZERO_SHA256, "generated_at": _utc(fixture.get("created_at") or run.get("created_at"), fallback=_utc_now())}
    return {"route_id": "FIXTURE", "source": source, "fixture": _clone(fixture), "locks": dict(SIX_LOCKS)}


def create_v5_rl_api_blueprint(
    *,
    registry: Any | None = None,
    registry_path: Path | str | None = None,
    registry_provider: Callable[[], Any] | None = None,
    cursor_key: bytes | str | None = None,
    artifact_root: Path | str | None = None,
    d0_evidence_path: Path | str | None = None,
    d1_evidence_path: Path | str | None = None,
    fixture_provider: Callable[[], Mapping[str, Any]] | None = None,
    fixture_payload: Mapping[str, Any] | None = None,
    unavailable_reason: str | None = None,
    name: str = "kronos_v5_rl_api",
    url_prefix: str = "/api/v5/rl",
) -> Blueprint:
    """Create the read-only V5 RL API Blueprint.

    The factory is intentionally injection-friendly: tests and app integration can
    supply a registry object, while production can pass a registry path for the
    public ``stom_rl.v5_registry.KronosV5Registry`` API.
    """

    disabled_reason = str(unavailable_reason).strip() if unavailable_reason else None
    key = b"kronos-v5-disabled-local-initialization-key" if disabled_reason and cursor_key is None else _coerce_cursor_key(cursor_key)
    root = _resolve_repo_path(artifact_root or DEFAULT_ARTIFACT_ROOT)
    bp = Blueprint(name, __name__, url_prefix=url_prefix)


    def fail_if_unavailable() -> None:
        if disabled_reason is not None:
            raise ApiHttpError(503, disabled_reason, code="INTERNAL_ERROR")

    def get_registry() -> Any:
        fail_if_unavailable()
        if registry_provider is not None:
            return registry_provider()
        if registry is not None:
            return registry
        return _registry_factory(registry_path, key)

    def success(route_id: str, payload: Mapping[str, Any], *, cursor: str | None = None, cursor_scope: str | None = None) -> Mapping[str, Any]:
        fail_if_unavailable()
        _validate_success(payload, cursor_key=key, cursor=cursor, cursor_scope=cursor_scope)
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if len(raw) > MAX_JSON_BYTES:
            raise ApiHttpError(413, "JSON response exceeds 2MiB cap", code="VALIDATION_ERROR")
        return payload

    @_route(bp, "/runs", "RUNS", "runs")
    def runs() -> Mapping[str, Any]:
        active = get_registry()
        identity = _identity(active)
        cursor, cursor_page_key = _cursor_arg("RUNS", identity["source_sha256"], key)
        limit = _limit_arg()
        page = _call_registry(active.list_runs, limit=limit, cursor=cursor, filters=None, sort="latest_desc")
        snapshots, registry_has_more = _page_parts(page)
        items = [_run(_snapshot_from_read(snapshot), identity) for snapshot in snapshots]
        page_items, next_cursor = _paginate("RUNS", items, source_sha256=identity["source_sha256"], cursor_key=key, request_cursor_key=cursor_page_key, limit=limit, registry_has_more=registry_has_more)
        return success("RUNS", {"route_id": "RUNS", "source": dict(identity), "list": {"items": page_items, "next_cursor": next_cursor}, "locks": dict(SIX_LOCKS)}, cursor=cursor)

    @_route(bp, "/runs/<run_id>", "RUN_DETAIL", "run_detail")
    def run_detail(run_id: str) -> Mapping[str, Any]:
        uid = _require_run_id(run_id)
        revision = _revision_arg()
        snapshot, source = _read_run(get_registry(), uid, revision)
        return success("RUN_DETAIL", {"route_id": "RUN_DETAIL", "source": dict(source), "run": _run(snapshot, source), "locks": dict(SIX_LOCKS)})

    @_route(bp, "/runs/<run_id>/events", "EVENTS", "events")
    def events(run_id: str) -> Mapping[str, Any]:
        uid = _require_run_id(run_id)
        revision = _revision_arg()
        active = get_registry()
        snapshot, source = _read_run(active, uid, revision)
        cursor_scope = _cursor_query_scope(uid, revision)
        cursor, cursor_page_key = _cursor_arg("EVENTS", source["source_sha256"], key, run_id=cursor_scope)
        limit = _limit_arg()
        after_global_seq = _event_after_global_seq(cursor_page_key)
        page = _call_registry(active.list_events, uid, revision=revision, after_global_seq=after_global_seq, limit=limit + 1)
        raw_items, registry_has_more = _page_parts(page)
        page_items, next_cursor = _paginate_events_by_registry_order(
            raw_items,
            snapshot,
            source_sha256=source["source_sha256"],
            cursor_key=key,
            request_cursor_key=cursor_page_key,
            cursor_scope=cursor_scope,
            limit=limit,
            after_global_seq=after_global_seq,
            registry_has_more=registry_has_more,
        )
        return success("EVENTS", {"route_id": "EVENTS", "source": dict(source), "list": {"items": page_items, "next_cursor": next_cursor}, "locks": dict(SIX_LOCKS), "run_id": uid}, cursor=cursor, cursor_scope=cursor_scope)

    @_route(bp, "/matrix", "MATRIX", "matrix")
    def matrix() -> Mapping[str, Any]:
        uid, revision = _run_query_args()
        active = get_registry()
        snapshot, source = _read_run(active, uid, revision)
        matrix_read = _call_registry(active.get_matrix, uid, revision=revision)
        cells = _matrix_cells(matrix_read, snapshot)
        return success("MATRIX", {"route_id": "MATRIX", "source": dict(source), "cells": cells, "summary": _matrix_summary(cells), "locks": dict(SIX_LOCKS)})

    @_route(bp, "/ledger", "LEDGER", "ledger")
    def ledger() -> Mapping[str, Any]:
        uid, revision = _run_query_args()
        active = get_registry()
        snapshot, source = _read_run(active, uid, revision)
        cursor_scope = _cursor_query_scope(uid, revision)
        cursor, cursor_page_key = _cursor_arg("LEDGER", source["source_sha256"], key, run_id=cursor_scope)
        limit = _limit_arg()
        items = _ledger_entries(snapshot, source)
        page_items, next_cursor = _paginate("LEDGER", items, source_sha256=source["source_sha256"], cursor_key=key, request_cursor_key=cursor_page_key, cursor_scope=cursor_scope, limit=limit)
        return success("LEDGER", {"route_id": "LEDGER", "source": dict(source), "list": {"items": page_items, "next_cursor": next_cursor}, "locks": dict(SIX_LOCKS)}, cursor=cursor, cursor_scope=cursor_scope)

    @_route(bp, "/artifacts", "ARTIFACTS", "artifacts")
    def artifacts() -> Mapping[str, Any]:
        uid, revision = _run_query_args()
        active = get_registry()
        snapshot, source = _read_run(active, uid, revision)
        cursor_scope = _cursor_query_scope(uid, revision)
        cursor, cursor_page_key = _cursor_arg("ARTIFACTS", source["source_sha256"], key, run_id=cursor_scope)
        limit = _limit_arg()
        raw_items = _call_registry(active.list_artifacts, uid, revision=revision)
        if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes, bytearray)):
            raise ApiHttpError(422, "registry artifacts are invalid", code="VALIDATION_ERROR")
        items = [_download(item, source, requested_run_id=uid, requested_revision=revision) for item in raw_items if isinstance(item, Mapping)]
        page_items, next_cursor = _paginate("ARTIFACTS", items, source_sha256=source["source_sha256"], cursor_key=key, request_cursor_key=cursor_page_key, cursor_scope=cursor_scope, limit=limit)
        return success("ARTIFACTS", {"route_id": "ARTIFACTS", "source": dict(source), "list": {"items": page_items, "next_cursor": next_cursor}, "locks": dict(SIX_LOCKS)}, cursor=cursor, cursor_scope=cursor_scope)

    @_route(bp, "/d0", "D0", "d0")
    def d0() -> Mapping[str, Any]:
        return success("D0", _d0_payload(d0_evidence_path))

    @_route(bp, "/d1", "D1", "d1")
    def d1() -> Mapping[str, Any]:
        return success("D1", _d1_payload(d1_evidence_path))

    @_route(bp, "/fixture", "FIXTURE", "fixture")
    def fixture() -> Mapping[str, Any]:
        if not _is_loopback():
            raise ApiHttpError(404, "fixture health is loopback-only", code="NOT_FOUND")
        payload = fixture_provider() if fixture_provider is not None else fixture_payload
        if payload is None:
            raise ApiHttpError(503, "fixture health payload is unavailable", code="INTERNAL_ERROR")
        return success("FIXTURE", _fixture_payload(payload))

    @_route(bp, "/artifacts/<artifact_id>/download", "ARTIFACTS", "artifact_download")
    def artifact_download(artifact_id: str) -> Response:
        aid = _require_artifact_id(artifact_id)
        run_id_raw = _single_query_arg("run_id", required=True)
        assert run_id_raw is not None
        uid = _require_run_id(run_id_raw)
        revision = _revision_arg()
        active = get_registry()
        metadata = _call_registry(active.get_artifact, uid, aid, revision=revision)
        if not isinstance(metadata, Mapping):
            raise ApiHttpError(422, "registry artifact metadata is invalid", code="VALIDATION_ERROR")
        _snapshot, source = _read_run(active, uid, revision)
        download = _download(metadata, source, requested_run_id=uid, requested_revision=revision)
        _validate_success({"route_id": "ARTIFACTS", "source": dict(source), "list": {"items": [download], "next_cursor": None}, "locks": dict(SIX_LOCKS)}, cursor_key=key, cursor=None)
        artifact = download["artifact"]
        if artifact["artifact_id"] != aid:
            raise ApiHttpError(409, "artifact id conflicts with the request", code="VALIDATION_ERROR")
        try:
            result = v5_downloads.download_artifact(aid, registry_root=_download_registry_snapshot(metadata), fixture_root=root)
        except DownloadError as exc:
            raise _download_http_error(exc) from exc
        return current_app.response_class(result.body, status=200, headers=result.headers)

    return bp


create_blueprint = create_v5_rl_api_blueprint

__all__ = ["MAX_JSON_BYTES", "create_blueprint", "create_v5_rl_api_blueprint"]
