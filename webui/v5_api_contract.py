"""Semantic boundary for the canonical V5 RL API wire contract."""
from __future__ import annotations

import base64
import hashlib
import hmac
import importlib.util
import json
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Final, Mapping

import rfc8785

from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_PATH: Final = Path(__file__).resolve().parents[1] / "docs" / "schemas" / "kronos_rl_api_v2.schema.json"
SOURCE_IDENTITY_SCHEMA_PATH: Final = SCHEMA_PATH.with_name("kronos_v5_source_identity.v1.schema.json")
SCHEMA_ID: Final = "https://kronos.local/schemas/kronos_rl_api_v2.schema.json"
SOURCE_IDENTITY_SCHEMA_ID: Final = "https://kronos.local/schemas/kronos_v5_source_identity.v1.schema.json"
SIX_LOCKS: Final = {"promotion_allowed": False, "model_build_allowed": False, "paper_forward_allowed": False, "live_broker_order_allowed": False, "profitability_claim_allowed": False, "go_summary_allowed": False}
MATRIX_SEEDS: Final = tuple(f"seed-{number:02d}" for number in range(1, 6))
MATRIX_FOLDS: Final = ("fold-01", "fold-02")
MATRIX_VARIANTS: Final = ("baseline", "cost-00bp", "cost-23bp", "cost-46bp", "no-trade")
MATRIX_COLUMNS: Final = tuple(f"{fold}:{variant}" for fold in MATRIX_FOLDS for variant in MATRIX_VARIANTS)
MATRIX_ORDER: Final = tuple((seed, column) for seed in MATRIX_SEEDS for column in MATRIX_COLUMNS)
CURSOR_MIN_LENGTH: Final = 16
CURSOR_MAX_LENGTH: Final = 2048
SAFE_INTEGER_MAX: Final = 9007199254740991
_WINDOWS_RESERVED_BASENAMES: Final = frozenset({"con", "prn", "aux", "nul", *(f"com{number}" for number in range(1, 10)), *(f"lpt{number}" for number in range(1, 10))})


class V5ApiContractError(ValueError):
    """A payload or request context violates the canonical V5 contract."""


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


_SCHEMA: Final = _load(SCHEMA_PATH)
_SOURCE_SCHEMA: Final = _load(SOURCE_IDENTITY_SCHEMA_PATH)
Draft202012Validator.check_schema(_SCHEMA)
Draft202012Validator.check_schema(_SOURCE_SCHEMA)
_FORMAT_CHECKER: Final = FormatChecker()
_VALIDATOR: Final = Draft202012Validator(_SCHEMA, format_checker=_FORMAT_CHECKER)
_SOURCE_VALIDATOR: Final = Draft202012Validator(_SOURCE_SCHEMA, format_checker=_FORMAT_CHECKER)
SEMANTIC_RULES: Final = _SCHEMA["$defs"]["semantic_rules"]["const"]


def _route_descriptors() -> dict[str, dict[str, Any]]:
    return {
        route: {
            "method": value["method"], "path": value["path"], "root": value["root"],
            "path_bindings": tuple(value["path_bindings"]), "allowed_errors": tuple(value["allowed_errors"]),
            "order": tuple(value.get("cursor", {}).get("order", ())),
            "tie_breaker": value.get("cursor", {}).get("tie_breaker"),
            "page_limit": value.get("cursor", {}).get("page_limit", 0),
        }
        for route, value in _SCHEMA["$defs"]["routeDescriptors"]["const"].items()
    }


ROUTE_DESCRIPTORS: Final = _route_descriptors()
V5_ROUTE_IDS: Final = tuple(ROUTE_DESCRIPTORS)
ROUTE_EXPORTS: Final = {route: descriptor["root"] for route, descriptor in ROUTE_DESCRIPTORS.items()}
_ARTIFACT_MEDIA: Final = dict(_SCHEMA["$defs"]["artifact"]["x-kronos-extension-media-map"])
_DOWNLOAD_URL_RE: Final = re.compile(r"^/api/v5/rl/artifacts/([A-Za-z0-9][A-Za-z0-9_-]{0,127})/download(?:\?run_id=([A-Za-z0-9][A-Za-z0-9._%~-]{0,383})&(revision|run_revision)=([1-9][0-9]{0,15}))?$")


def canonical_json(value: Any) -> bytes:
    """Pinned RFC 8785/JCS bytes used by cursor signatures and event hashes."""
    try:
        return rfc8785.dumps(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise V5ApiContractError("value is outside the pinned RFC 8785/JCS profile") from exc


def event_payload_projection(event: Mapping[str, Any]) -> dict[str, Any]:
    """Closed event payload excluding transport envelope and its digest."""
    kind = event["event_type"]
    fields = {
        "PROGRESS": {"progress"},
        "MESSAGE": {"level", "message"},
        "ARTIFACT": {"artifact_id"},
        "STATE": {"state"},
    }.get(kind)
    if fields is None or set(event) != {"event_type", "event_id", "occurred_at", "payload_sha256", *fields}:
        raise V5ApiContractError("event must be exactly one closed variant")
    return {"event_type": kind, **{field: event[field] for field in fields}}


def event_payload_sha256(event: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(event_payload_projection(event))).hexdigest()


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    if not isinstance(value, str) or not CURSOR_MIN_LENGTH <= len(value) <= CURSOR_MAX_LENGTH or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for char in value):
        raise V5ApiContractError("cursor encoding is invalid")
    try: return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except Exception as exc: raise V5ApiContractError("cursor encoding is invalid") from exc


def _require_cursor_key(key: bytes) -> bytes:
    if not isinstance(key, bytes) or not key:
        raise V5ApiContractError("cursor key must be an explicit non-empty server secret")
    return key


def encode_cursor(route_id: str, source_sha256: str, last_key: Mapping[str, Any], *, key: bytes, run_id: str | None = None, page_limit: int | None = None) -> str:
    key = _require_cursor_key(key)
    descriptor = ROUTE_DESCRIPTORS.get(route_id)
    if descriptor is None or not descriptor["page_limit"]: raise V5ApiContractError("route does not support cursors")
    if route_id == "EVENTS" and not run_id: raise V5ApiContractError("events cursor requires run_id")
    limit = descriptor["page_limit"] if page_limit is None else page_limit
    if limit != descriptor["page_limit"]: raise V5ApiContractError("cursor page limit does not match descriptor")
    if not isinstance(last_key, Mapping) or set(last_key) != {term.split(":", 1)[0] for term in descriptor["order"]}: raise V5ApiContractError("cursor final key does not match descriptor order")
    envelope = {"v": 1, "route_id": route_id, "source_sha256": source_sha256, "run_id": run_id, "order": list(descriptor["order"]), "tie_breaker": descriptor["tie_breaker"], "page_limit": limit, "last_key": dict(last_key)}
    body = canonical_json(envelope)
    return _b64encode(body + hmac.new(key, body, hashlib.sha256).digest())


def decode_cursor(token: str, route_id: str, source_sha256: str, *, key: bytes, run_id: str | None = None) -> dict[str, Any]:
    key = _require_cursor_key(key)
    descriptor = ROUTE_DESCRIPTORS.get(route_id)
    if descriptor is None or not descriptor["page_limit"]: raise V5ApiContractError("route does not support cursors")
    raw = _b64decode(token)
    if _b64encode(raw) != token: raise V5ApiContractError("cursor encoding is invalid")
    if len(raw) <= hashlib.sha256().digest_size: raise V5ApiContractError("cursor token is invalid")
    body, signature = raw[:-32], raw[-32:]
    if not hmac.compare_digest(signature, hmac.new(key, body, hashlib.sha256).digest()): raise V5ApiContractError("cursor signature is invalid")
    try: envelope = json.loads(body)
    except (TypeError, ValueError) as exc: raise V5ApiContractError("cursor body is invalid") from exc
    expected = {"v": 1, "route_id": route_id, "source_sha256": source_sha256, "run_id": run_id, "order": list(descriptor["order"]), "tie_breaker": descriptor["tie_breaker"], "page_limit": descriptor["page_limit"]}
    if not isinstance(envelope, dict) or set(envelope) != {*expected, "last_key"} or any(envelope[name] != value for name, value in expected.items()) or not isinstance(envelope["last_key"], dict) or set(envelope["last_key"]) != {term.split(":", 1)[0] for term in descriptor["order"]}:
        raise V5ApiContractError("cursor is stale or belongs to another route")
    return envelope["last_key"]


def progress_percent(step: int, total_steps: int) -> Decimal:
    if not isinstance(step, int) or isinstance(step, bool) or not 0 <= step <= SAFE_INTEGER_MAX: raise V5ApiContractError("progress step must be a safe integer")
    if not isinstance(total_steps, int) or isinstance(total_steps, bool) or not 1 <= total_steps <= SAFE_INTEGER_MAX or step > total_steps: raise V5ApiContractError("invalid progress total_steps")
    return (Decimal(step) * 100 / Decimal(total_steps)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _schema_error(validator: Draft202012Validator, value: Any) -> None:
    error = next(iter(sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))), None)
    if error: raise V5ApiContractError(f"schema violation at {'/'.join(map(str, error.absolute_path)) or '$'}: {error.message}")


def _utc(value: str, label: str) -> datetime:
    try: return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc: raise V5ApiContractError(f"{label} must be a real RFC3339 UTC timestamp") from exc


def _validate_progress(value: Mapping[str, Any]) -> None:
    if Decimal(str(value["percent"])) != progress_percent(value["step"], value["total_steps"]): raise V5ApiContractError("progress percent must equal the six-decimal half-up equation")


def _validate_state(state: Mapping[str, Any]) -> None:
    _validate_progress(state["progress"]); updated, started, finished = _utc(state["updated_at"], "updated_at"), state["started_at"], state["finished_at"]
    status = state["status"]
    if status == "QUEUED" and (started is not None or finished is not None or state["progress"]["step"] != 0): raise V5ApiContractError("queued state requires null timestamps and zero progress")
    if status == "RUNNING" and (started is None or finished is not None): raise V5ApiContractError("running state requires started_at and null finished_at")
    if status in {"SUCCEEDED", "FAILED", "CANCELLED"} and (started is None or finished is None): raise V5ApiContractError("terminal state requires both timestamps")
    if status == "SUCCEEDED" and state["progress"]["step"] != state["progress"]["total_steps"]: raise V5ApiContractError("succeeded state requires complete progress")
    if started is not None and _utc(started, "started_at") > updated: raise V5ApiContractError("started_at must not follow updated_at")
    if finished is not None and (_utc(finished, "finished_at") > updated or (started is not None and _utc(finished, "finished_at") < _utc(started, "started_at"))): raise V5ApiContractError("state timestamps are not ordered")


def _validate_matrix(payload: Mapping[str, Any]) -> None:
    cells = payload["cells"]
    if tuple((cell["row_id"], cell["column_id"]) for cell in cells) != MATRIX_ORDER: raise V5ApiContractError("matrix cells must be canonical Cartesian order")
    counts = {state: sum(cell["state"] == state for cell in cells) for state in ("PASS", "FAIL", "BLOCKED", "PENDING")}
    if payload["summary"] != {"total_cells": 50, **{f"{state.lower()}_count": count for state, count in counts.items()}}: raise V5ApiContractError("matrix summary must conserve cells")


def _validate_source_equal(root_hash: str, *values: str) -> None:
    if any(value != root_hash for value in values): raise V5ApiContractError("nested source_sha256 differs from root source")


def _validate_download(download: Mapping[str, Any]) -> None:
    artifact = download["artifact"]; stem, dot, extension = artifact["filename"].rpartition(".")
    has_run_id, has_run_revision = "run_id" in download, "run_revision" in download
    url = _DOWNLOAD_URL_RE.fullmatch(download["download_url"])
    if not stem or not dot or "." in stem or stem.casefold() in _WINDOWS_RESERVED_BASENAMES or extension not in _ARTIFACT_MEDIA: raise V5ApiContractError("artifact filename must have one portable non-reserved suffix")
    if artifact["media_type"] != _ARTIFACT_MEDIA[extension] or download["portable_filename"] != artifact["filename"] or url is None or url.group(1) != artifact["artifact_id"] or has_run_id != has_run_revision: raise V5ApiContractError("download metadata is not bound")
    if url.group(2) is not None and (not has_run_id or download["run_id"] != url.group(2) or str(download["run_revision"]) != url.group(4)): raise V5ApiContractError("download metadata is not bound")

def _validate_governance_semantics(status: str, value: str, *, pass_values: set[str], label: str) -> None:
    if status == "PASS" and value not in pass_values:
        raise V5ApiContractError(f"{label} PASS cannot use UNKNOWN or unverified semantics")
    if value == "UNKNOWN" and status not in {"BLOCKED", "PENDING"}:
        raise V5ApiContractError(f"{label} UNKNOWN is only allowed for BLOCKED or PENDING")


def _page_key(descriptor: Mapping[str, Any], item: Mapping[str, Any]) -> dict[str, Any]:
    source = item.get("artifact", item)
    return {term.split(":", 1)[0]: source[term.split(":", 1)[0]] for term in descriptor["order"]}


def _compare_page_keys(descriptor: Mapping[str, Any], left: Mapping[str, Any], right: Mapping[str, Any]) -> int:
    for term in descriptor["order"]:
        field, direction = term.split(":", 1)
        left_value, right_value = left[field], right[field]
        if field.endswith("_at"):
            left_value, right_value = _utc(left_value, f"page key {field}"), _utc(right_value, f"page key {field}")
        if left_value == right_value:
            continue
        comparison = -1 if left_value < right_value else 1
        return -comparison if direction == "desc" else comparison
    return 0


def _validate_page_order(route: str, items: list[Mapping[str, Any]]) -> None:
    descriptor = ROUTE_DESCRIPTORS[route]
    for before, after in zip(items, items[1:]):
        if _compare_page_keys(descriptor, _page_key(descriptor, before), _page_key(descriptor, after)) >= 0:
            raise V5ApiContractError("page items are not in strict canonical order")


def validate_source_identity(identity: Mapping[str, Any]) -> None:
    _schema_error(_SOURCE_VALIDATOR, identity)
    try:
        spec = importlib.util.spec_from_file_location("kronos_v5_source_scorer", SCHEMA_PATH.parents[2] / "scripts" / "score_kronos_dashboard_v5.py")
        if spec is None or spec.loader is None: raise ImportError("authoritative C2 scorer is unavailable")
        scorer = importlib.util.module_from_spec(spec); spec.loader.exec_module(scorer); scorer.source_identity_sha256(identity)
    except Exception as exc: raise V5ApiContractError(f"invalid authoritative C2 source identity: {exc}") from exc


def validate_payload(payload: Mapping[str, Any], *, cursor_key: bytes, cursor: str | None = None) -> None:
    cursor_key = _require_cursor_key(cursor_key)
    _schema_error(_VALIDATOR, payload)
    route = payload["route_id"]
    if "error" in payload: return
    root_hash = payload["source"]["source_sha256"]; _utc(payload["source"]["generated_at"], "source.generated_at")
    if payload["locks"] != SIX_LOCKS: raise V5ApiContractError("success payload locks must be the canonical false lock set")
    if route == "RUN_DETAIL": _validate_state(payload["run"]["state"]); _validate_source_equal(root_hash, payload["run"]["source_sha256"])
    elif route == "RUNS":
        for item in payload["list"]["items"]: _validate_state(item["state"]); _validate_source_equal(root_hash, item["source_sha256"])
    elif route == "EVENTS":
        for item in payload["list"]["items"]:
            if item["event_type"] == "PROGRESS": _validate_progress(item["progress"])
            if item["event_type"] == "STATE": _validate_state(item["state"])
            _utc(item["occurred_at"], "event.occurred_at")
            if item["payload_sha256"] != event_payload_sha256(item): raise V5ApiContractError("event payload_sha256 does not match canonical payload projection")
    elif route == "MATRIX": _validate_matrix(payload)
    elif route == "LEDGER":
        for item in payload["list"]["items"]: _validate_source_equal(root_hash, item["source_sha256"])
    elif route == "ARTIFACTS":
        for item in payload["list"]["items"]: _validate_download(item)
    elif route == "D0":
        d0 = payload["d0"]; _validate_source_equal(root_hash, d0["source_sha256"]); _validate_governance_semantics(d0["status"], d0["price_basis"], pass_values={"RAW", "ADJUSTED"}, label="D0")
    elif route == "D1":
        d1 = payload["d1"]; _validate_source_equal(root_hash, d1["source_sha256"]); _validate_governance_semantics(d1["status"], d1["universe"], pass_values={"OFFICIAL", "MANUAL_REVIEWED"}, label="D1")
    elif route == "FIXTURE":
        fixture = payload["fixture"]; _validate_state(fixture["run"]["state"]); _validate_source_equal(root_hash, fixture["source_sha256"], fixture["run"]["source_sha256"])
    if route in {"RUNS", "EVENTS", "LEDGER", "ARTIFACTS"}:
        descriptor = ROUTE_DESCRIPTORS[route]
        items = payload["list"]["items"]; _validate_page_order(route, items)
        previous_key = decode_cursor(cursor, route, root_hash, key=cursor_key, run_id=payload.get("run_id")) if cursor is not None else None
        if previous_key is not None and (not items or _compare_page_keys(descriptor, previous_key, _page_key(descriptor, items[0])) >= 0):
            raise V5ApiContractError("page does not begin strictly after request cursor")
        next_cursor = payload["list"]["next_cursor"]
        if next_cursor is not None:
            next_key = decode_cursor(next_cursor, route, root_hash, key=cursor_key, run_id=payload.get("run_id"))
            if not items or next_key != _page_key(descriptor, items[-1]):
                raise V5ApiContractError("next_cursor must bind the final emitted page item")


def validate_route_payload(route_id: str, payload: Mapping[str, Any], *, cursor_key: bytes, cursor: str | None = None, method: str = "GET", path: str | None = None, path_params: Mapping[str, str] | None = None) -> None:
    descriptor = ROUTE_DESCRIPTORS.get(route_id)
    if descriptor is None: raise V5ApiContractError(f"unknown V5 route: {route_id}")
    if method != descriptor["method"]: raise V5ApiContractError("request method does not match route descriptor")
    if path is not None:
        expected = descriptor["path"]
        for name in descriptor["path_bindings"]:
            value = (path_params or {}).get(name)
            if not value: raise V5ApiContractError(f"missing path binding {name}")
            expected = expected.replace("{" + name + "}", value)
        if path != expected: raise V5ApiContractError("request path does not match route descriptor")
    validate_payload(payload, cursor_key=cursor_key, cursor=cursor)
    if payload["route_id"] != route_id: raise V5ApiContractError("payload route_id does not match request")
    if "error" in payload and payload["error"]["code"] not in descriptor["allowed_errors"]: raise V5ApiContractError("error code is not allowed for this route")
    if "error" not in payload and "run_id" in descriptor["path_bindings"] and path_params is not None:
        bound = path_params.get("run_id"); actual = payload["run"]["run_id"] if route_id == "RUN_DETAIL" else payload["run_id"]
        if actual != bound: raise V5ApiContractError("run_id path binding does not match payload")
