"""Canonical append-only event stream for the frozen daily Portfolio SB3 protocol.

The stream is synthetic-verification-only metadata.  It records progress,
heartbeats, checkpoints, resumes, stops, and artifact references without opening
OOS data, importing SB3, training, or embedding raw/model payloads.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import re
from typing import Any, Final

from stom_rl import daily_portfolio_sb3_protocol as protocol_authority
from stom_rl.daily_portfolio_sb3_state import derive_attempt_uid


EVENT_STREAM_SCHEMA: Final = "kronos_daily_sb3_event_stream.v1"
EVENT_RECORD_SCHEMA: Final = "kronos_daily_sb3_event_record.v1"
EVENT_SCHEMA: Final = "kronos_daily_sb3_event.v1"
STATE_SCHEMA: Final = "kronos_daily_sb3_runner_state.v1"
SCHEMA_ID: Final = "https://kronos.local/schemas/kronos_daily_sb3_events.v1.schema.json"
ZERO_SHA256: Final = "0" * 64
MAX_ARTIFACT_REF_BYTES: Final = 8192

LIFECYCLE_STATES: Final = (
    "ADVANCING",
    "STALLED",
    "RESUMED",
    "RESTARTED_NON_EXACT",
    "STOPPED",
    "FAILED",
    "COMPLETED",
    "CONFLICT_BLOCKED",
    "NOT_RUN",
)
PHASES: Final = (
    "NOT_RUN",
    "PREREGISTERED",
    "QUEUED",
    "PREPARING",
    "SYNTHETIC_TRAIN",
    "SYNTHETIC_EVAL",
    "CHECKPOINT",
    "RESUME",
    "STOP",
    "TERMINAL",
)
EVENT_KINDS: Final = (
    "RUN_CREATED",
    "PROGRESS",
    "HEARTBEAT",
    "CHECKPOINT",
    "RESUME",
    "STOP",
)
TERMINAL_LIFECYCLE_STATES: Final = ("STOPPED", "FAILED", "COMPLETED", "CONFLICT_BLOCKED")
RESUME_CHECKPOINT_SOURCE_PHASES: Final = ("SYNTHETIC_TRAIN", "SYNTHETIC_EVAL")
RESUME_CHECKPOINT_SOURCE_LIFECYCLES: Final = ("ADVANCING", "STALLED")
LIVENESS_BASES: Final = (
    "NO_PROGRESS",
    "STEP_INCREASED",
    "HEARTBEAT_ONLY",
    "CHECKPOINT_ONLY",
    "RESUME_ONLY",
    "TERMINAL",
)
ARTIFACT_KINDS: Final = (
    "synthetic_runner_log",
    "synthetic_progress_summary",
    "synthetic_checkpoint",
    "synthetic_stop_report",
)
STOP_REASON_CODES: Final = (
    "USER_REQUESTED_STOP",
    "SYNTHETIC_COMPLETE",
    "SYNTHETIC_FAILURE",
    "CONFLICT_BLOCKED",
)
STOP_REASON_BY_LIFECYCLE: Final = {
    "STOPPED": "USER_REQUESTED_STOP",
    "FAILED": "SYNTHETIC_FAILURE",
    "COMPLETED": "SYNTHETIC_COMPLETE",
    "CONFLICT_BLOCKED": "CONFLICT_BLOCKED",
}
FALSE_LOCK_FIELDS: Final = (
    "promotion_allowed",
    "model_build_allowed",
    "paper_forward_allowed",
    "live_broker_order_allowed",
    "profitability_claim_allowed",
    "go_summary_allowed",
)
FALSE_LOCKS: Final = {field: False for field in FALSE_LOCK_FIELDS}

_SHA_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_UTC_RE: Final = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_RUN_UID_RE: Final = re.compile(r"kdp1-run-[0-9a-f]{32}\Z")
_ATTEMPT_UID_RE: Final = re.compile(r"kdp1-attempt-[0-9a-f]{32}\Z")
_URI_RE: Final = re.compile(r"(?:agent://[^\\\s\0]+|kronos-run://[A-Za-z0-9_-]{43}/[^\\\s\0]+)\Z")
_BANNED_ARTIFACT_TOKENS: Final = ("oos", "model", "payload")


class DailySb3EventsError(ValueError):
    """Raised when a daily SB3 event stream violates its append-only contract."""


def canonical_bytes(value: Any) -> bytes:
    """Return RFC 8785/JCS bytes using the protocol module's canonical encoder."""
    try:
        return protocol_authority.canonical_bytes(value)
    except protocol_authority.DailySb3ProtocolError as exc:
        raise DailySb3EventsError("value is not RFC 8785 canonicalizable") from exc


def sha256_hex(value: bytes | Any) -> str:
    raw = value if isinstance(value, bytes) else canonical_bytes(value)
    return hashlib.sha256(raw).hexdigest()


def event_sha256(event: Mapping[str, Any]) -> str:
    """Hash the canonical event body; the record envelope stores this digest."""
    return sha256_hex(dict(event))


def state_sha256(state: Mapping[str, Any]) -> str:
    """Hash a replayed state snapshot without adding a self-referential field."""
    return sha256_hex(dict(state))


def _shape(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise DailySb3EventsError(f"{label} has an invalid wire shape")
    return value


def _bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise DailySb3EventsError(f"{label} must be a boolean")
    return value


def _int(value: Any, label: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum or (maximum is not None and value > maximum):
        raise DailySb3EventsError(f"{label} must be an integer in range")
    return value


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
        raise DailySb3EventsError(f"{label} is not a canonical lower-case SHA-256 digest")
    return value


def _utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not _UTC_RE.fullmatch(value):
        raise DailySb3EventsError(f"{label} is not an exact UTC timestamp")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise DailySb3EventsError(f"{label} is not a valid UTC timestamp") from exc


def _run_uid(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _RUN_UID_RE.fullmatch(value):
        raise DailySb3EventsError(f"{label} is not a canonical run UID")
    return value


def _attempt_uid(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _ATTEMPT_UID_RE.fullmatch(value):
        raise DailySb3EventsError(f"{label} is not a canonical attempt UID")
    return value


def _uri(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _URI_RE.fullmatch(value):
        raise DailySb3EventsError(f"{label} URI is invalid")
    return value


def _percent(step: int, total_steps: int) -> str:
    if total_steps == 0:
        return "0.000000"
    return f"{(step * 100.0) / total_steps:.6f}"


def _protocol(protocol: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    value = protocol_authority.build_protocol() if protocol is None else protocol
    protocol_authority.validate_protocol(value)
    return value


def _protocol_cells(protocol: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    cells = protocol["matrix"]["cells"]
    return {str(cell["cell_uid"]): cell for cell in cells}


def _attempt_uid_for_cell(protocol: Mapping[str, Any], cell_uid: str, attempt_number: int) -> str:
    cells = _protocol_cells(protocol)
    if cell_uid not in cells:
        raise DailySb3EventsError("cell_uid is not in the frozen protocol matrix")
    if attempt_number == 1:
        return str(cells[cell_uid]["attempt_uid"])
    return derive_attempt_uid(protocol["identity"]["protocol_sha256"], cell_uid, attempt_number)


def _source_ref(value: Any, label: str = "source_ref") -> dict[str, Any]:
    ref = _shape(value, {"uri", "sha256", "byte_length", "schema"}, label)
    uri = _uri(ref["uri"], f"{label} uri")
    digest = _sha(ref["sha256"], f"{label} sha256")
    length = _int(ref["byte_length"], f"{label} byte_length", minimum=1)
    if ref["schema"] != "kronos_source_identity.v1":
        raise DailySb3EventsError(f"{label} must bind a kronos_source_identity.v1 object")
    return {"uri": uri, "sha256": digest, "byte_length": length, "schema": "kronos_source_identity.v1"}


def _artifact_ref(value: Any, label: str = "artifact_ref") -> dict[str, Any]:
    ref = _shape(value, {"uri", "sha256", "byte_length", "schema", "artifact_kind"}, label)
    uri = _uri(ref["uri"], f"{label} uri")
    digest = _sha(ref["sha256"], f"{label} sha256")
    length = _int(ref["byte_length"], f"{label} byte_length", minimum=0, maximum=MAX_ARTIFACT_REF_BYTES)
    schema = ref["schema"]
    kind = ref["artifact_kind"]
    if not isinstance(schema, str) or not schema or not isinstance(kind, str) or kind not in ARTIFACT_KINDS:
        raise DailySb3EventsError(f"{label} schema or kind is invalid")
    haystack = f"{uri} {schema} {kind}".lower()
    if any(token in haystack for token in _BANNED_ARTIFACT_TOKENS):
        raise DailySb3EventsError(f"{label} may not reference raw OOS, model, or payload artifacts")
    return {"uri": uri, "sha256": digest, "byte_length": length, "schema": schema, "artifact_kind": kind}


def _artifact_refs(value: Any, label: str = "artifact_refs") -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise DailySb3EventsError(f"{label} must be a list")
    refs = [_artifact_ref(item, f"{label}[{index}]") for index, item in enumerate(value)]
    encoded = [canonical_bytes(ref) for ref in refs]
    if len(encoded) != len(set(encoded)):
        raise DailySb3EventsError(f"{label} contains duplicate artifact refs")
    return refs


def _locks(value: Any, label: str = "locks") -> dict[str, bool]:
    locks = _shape(value, set(FALSE_LOCK_FIELDS), label)
    if any(locks[field] is not False for field in FALSE_LOCK_FIELDS):
        raise DailySb3EventsError("all six runner locks must remain false")
    return dict(FALSE_LOCKS)


def _cell_identity(value: Any, protocol: Mapping[str, Any]) -> dict[str, Any]:
    cell = _shape(value, {"cell_uid", "attempt_uid", "attempt_number", "cell_ordinal", "seed_id", "fold_id", "variant_id"}, "cell identity")
    uid = cell["cell_uid"]
    cells_by_uid = _protocol_cells(protocol)
    if not isinstance(uid, str) or uid not in cells_by_uid:
        raise DailySb3EventsError("event cell_uid is not in the frozen 50-cell protocol matrix")
    attempt_number = _int(cell["attempt_number"], "cell attempt_number", minimum=1)
    expected_cell = cells_by_uid[uid]
    expected = {
        "cell_uid": expected_cell["cell_uid"],
        "attempt_uid": _attempt_uid_for_cell(protocol, str(expected_cell["cell_uid"]), attempt_number),
        "attempt_number": attempt_number,
        "cell_ordinal": expected_cell["ordinal"],
        "seed_id": expected_cell["seed_id"],
        "fold_id": expected_cell["fold_id"],
        "variant_id": expected_cell["variant_id"],
    }
    if dict(cell) != expected:
        raise DailySb3EventsError("event cell identity does not match the protocol authority and attempt transition")
    return expected


def _progress(value: Any) -> dict[str, Any]:
    progress = _shape(value, {"step", "total_steps", "percent_complete"}, "progress")
    step = _int(progress["step"], "progress step")
    total_steps = _int(progress["total_steps"], "progress total_steps")
    if step > total_steps:
        raise DailySb3EventsError("progress step may not exceed total_steps")
    expected_percent = _percent(step, total_steps)
    if progress["percent_complete"] != expected_percent:
        raise DailySb3EventsError("progress percent_complete is not deterministic")
    return {"step": step, "total_steps": total_steps, "percent_complete": expected_percent}


def _heartbeat(value: Any) -> dict[str, Any]:
    heartbeat = _shape(value, {"observed", "heartbeat_sequence"}, "heartbeat")
    return {
        "observed": _bool(heartbeat["observed"], "heartbeat observed"),
        "heartbeat_sequence": _int(heartbeat["heartbeat_sequence"], "heartbeat sequence"),
    }


def _liveness(value: Any) -> dict[str, Any]:
    liveness = _shape(value, {"live", "basis"}, "liveness")
    basis = liveness["basis"]
    if not isinstance(basis, str) or basis not in LIVENESS_BASES:
        raise DailySb3EventsError("liveness basis is invalid")
    return {"live": _bool(liveness["live"], "liveness live"), "basis": basis}


def _resume(value: Any) -> dict[str, Any]:
    resume = _shape(value, {"requested", "from_checkpoint_ref", "exact"}, "resume")
    requested = _bool(resume["requested"], "resume requested")
    exact = _bool(resume["exact"], "resume exact")
    ref = None if resume["from_checkpoint_ref"] is None else _artifact_ref(resume["from_checkpoint_ref"], "resume from_checkpoint_ref")
    if requested:
        if ref is None or ref["artifact_kind"] != "synthetic_checkpoint":
            raise DailySb3EventsError("resume events must reference a synthetic checkpoint")
    elif ref is not None or exact is not False:
        raise DailySb3EventsError("non-resume events must not carry resume metadata")
    return {"requested": requested, "from_checkpoint_ref": ref, "exact": exact}


def _stop(value: Any) -> dict[str, Any]:
    stop = _shape(value, {"requested", "terminal", "reason_code"}, "stop")
    requested = _bool(stop["requested"], "stop requested")
    terminal = _bool(stop["terminal"], "stop terminal")
    reason_code = stop["reason_code"]
    if requested:
        if terminal is not True or not isinstance(reason_code, str) or reason_code not in STOP_REASON_CODES:
            raise DailySb3EventsError("stop events must be terminal and carry a valid reason code")
    elif terminal is not False or reason_code is not None:
        raise DailySb3EventsError("non-stop events must not carry stop metadata")
    return {"requested": requested, "terminal": terminal, "reason_code": reason_code}


def _event_body(value: Any, *, protocol: Mapping[str, Any], source_ref: Mapping[str, Any]) -> Mapping[str, Any]:
    event = _shape(
        value,
        {
            "schema",
            "global_sequence",
            "run_sequence",
            "cell_sequence",
            "previous_event_sha256",
            "occurred_at",
            "run_uid",
            "attempt_uid",
            "attempt_number",
            "event_kind",
            "phase",
            "lifecycle_state",
            "protocol_uid",
            "protocol_sha256",
            "source_ref",
            "cell",
            "progress",
            "heartbeat",
            "liveness",
            "artifact_refs",
            "checkpoint_ref",
            "resume",
            "stop",
            "locks",
        },
        "event",
    )
    identity = protocol["identity"]
    if event["schema"] != EVENT_SCHEMA:
        raise DailySb3EventsError("event schema mismatch")
    _int(event["global_sequence"], "global_sequence", minimum=1)
    _int(event["run_sequence"], "run_sequence", minimum=1)
    _int(event["cell_sequence"], "cell_sequence", minimum=1)
    _sha(event["previous_event_sha256"], "previous_event_sha256")
    _utc(event["occurred_at"], "occurred_at")
    _run_uid(event["run_uid"], "run_uid")
    _attempt_uid(event["attempt_uid"], "attempt_uid")
    _int(event["attempt_number"], "attempt_number", minimum=1)
    if event["event_kind"] not in EVENT_KINDS or event["phase"] not in PHASES or event["lifecycle_state"] not in LIFECYCLE_STATES:
        raise DailySb3EventsError("event kind, phase, or lifecycle state is invalid")
    if event["protocol_uid"] != identity["protocol_uid"] or event["protocol_sha256"] != identity["protocol_sha256"]:
        raise DailySb3EventsError("event protocol identity does not match the frozen authority")
    if _source_ref(event["source_ref"], "event source_ref") != dict(source_ref):
        raise DailySb3EventsError("event source identity does not match the stream source")
    cell_identity = _cell_identity(event["cell"], protocol)
    if event["attempt_uid"] != cell_identity["attempt_uid"] or event["attempt_number"] != cell_identity["attempt_number"]:
        raise DailySb3EventsError("event attempt transition fields do not match cell identity")
    refs = _artifact_refs(event["artifact_refs"])
    checkpoint_ref = None if event["checkpoint_ref"] is None else _artifact_ref(event["checkpoint_ref"], "checkpoint_ref")
    if checkpoint_ref is not None and checkpoint_ref["artifact_kind"] != "synthetic_checkpoint":
        raise DailySb3EventsError("checkpoint_ref must be a synthetic checkpoint")
    if checkpoint_ref is not None and canonical_bytes(checkpoint_ref) not in {canonical_bytes(ref) for ref in refs}:
        raise DailySb3EventsError("checkpoint_ref must also appear in artifact_refs")
    _progress(event["progress"])
    _heartbeat(event["heartbeat"])
    _liveness(event["liveness"])
    _resume(event["resume"])
    _stop(event["stop"])
    _locks(event["locks"])
    return event


def _record(value: Any, *, protocol: Mapping[str, Any], source_ref: Mapping[str, Any]) -> Mapping[str, Any]:
    record = _shape(value, {"schema", "event_sha256", "event"}, "event record")
    if record["schema"] != EVENT_RECORD_SCHEMA:
        raise DailySb3EventsError("event record schema mismatch")
    digest = _sha(record["event_sha256"], "event_sha256")
    event = _event_body(record["event"], protocol=protocol, source_ref=source_ref)
    if event_sha256(event) != digest:
        raise DailySb3EventsError("event record hash does not match canonical event bytes")
    return record


def _expected_liveness_basis(event_kind: str, *, step_increased: bool, heartbeat_observed: bool, terminal: bool) -> str:
    if step_increased:
        return "STEP_INCREASED"
    if terminal:
        return "TERMINAL"
    if heartbeat_observed:
        return "HEARTBEAT_ONLY"
    if event_kind == "CHECKPOINT":
        return "CHECKPOINT_ONLY"
    if event_kind == "RESUME":
        return "RESUME_ONLY"
    return "NO_PROGRESS"


def _checkpoint_source_is_resume_eligible(phase: str | None, lifecycle_state: str | None) -> bool:
    return phase in RESUME_CHECKPOINT_SOURCE_PHASES and lifecycle_state in RESUME_CHECKPOINT_SOURCE_LIFECYCLES


def _validate_kind_semantics(event: Mapping[str, Any], *, step_increased: bool) -> None:
    kind = event["event_kind"]
    phase = event["phase"]
    lifecycle = event["lifecycle_state"]
    progress = event["progress"]
    heartbeat = event["heartbeat"]
    checkpoint_ref = event["checkpoint_ref"]
    resume = event["resume"]
    stop = event["stop"]

    if kind == "RUN_CREATED":
        if phase != "PREREGISTERED" or lifecycle != "NOT_RUN" or progress["step"] != 0 or heartbeat["observed"] or checkpoint_ref is not None or resume["requested"] or stop["requested"]:
            raise DailySb3EventsError("RUN_CREATED event metadata is inconsistent")
    elif kind == "PROGRESS":
        if phase not in {"SYNTHETIC_TRAIN", "SYNTHETIC_EVAL"} or lifecycle != "ADVANCING" or not step_increased or heartbeat["observed"] or checkpoint_ref is not None or resume["requested"] or stop["requested"]:
            raise DailySb3EventsError("PROGRESS events must be the only ADVANCING events and must increase step")
    elif kind == "HEARTBEAT":
        if phase not in {"SYNTHETIC_TRAIN", "SYNTHETIC_EVAL"} or lifecycle != "STALLED" or not heartbeat["observed"] or step_increased or checkpoint_ref is not None or resume["requested"] or stop["requested"]:
            raise DailySb3EventsError("HEARTBEAT events are heartbeat-only and not live progress")
    elif kind == "CHECKPOINT":
        if phase != "CHECKPOINT" or lifecycle != "STALLED" or step_increased or heartbeat["observed"] or checkpoint_ref is None or resume["requested"] or stop["requested"]:
            raise DailySb3EventsError("CHECKPOINT events must only reference a checkpoint artifact")
    elif kind == "RESUME":
        expected_lifecycle = "RESUMED" if resume["exact"] else "RESTARTED_NON_EXACT"
        if phase != "RESUME" or lifecycle != expected_lifecycle or step_increased or heartbeat["observed"] or checkpoint_ref is not None or not resume["requested"] or stop["requested"]:
            raise DailySb3EventsError("RESUME events must encode exact vs non-exact resume semantics")
    elif kind == "STOP":
        expected_reason = STOP_REASON_BY_LIFECYCLE.get(lifecycle)
        if phase not in {"STOP", "TERMINAL"} or lifecycle not in TERMINAL_LIFECYCLE_STATES or step_increased or heartbeat["observed"] or checkpoint_ref is not None or resume["requested"] or not stop["requested"] or stop["reason_code"] != expected_reason:
            raise DailySb3EventsError("STOP events must be terminal and match their reason code")
        if not event["artifact_refs"]:
            raise DailySb3EventsError("STOP events must carry a small stop artifact reference")
    else:  # pragma: no cover - guarded by enum validation.
        raise DailySb3EventsError("unknown event kind")


def _empty_cell_state(cell: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "kronos_daily_sb3_cell_state.v1",
        "cell_uid": cell["cell_uid"],
        "attempt_uid": cell["attempt_uid"],
        "attempt_number": 1,
        "cell_ordinal": cell["ordinal"],
        "seed_id": cell["seed_id"],
        "fold_id": cell["fold_id"],
        "variant_id": cell["variant_id"],
        "run_uid": None,
        "phase": "NOT_RUN",
        "lifecycle_state": "NOT_RUN",
        "last_step": 0,
        "total_steps": 0,
        "percent_complete": "0.000000",
        "heartbeat_count": 0,
        "last_heartbeat_at": None,
        "last_progress_at": None,
        "last_live_at": None,
        "last_event_at": None,
        "last_event_sha256": None,
        "liveness": {"live": False, "basis": "NO_PROGRESS"},
        "checkpoint_ref": None,
        "resume_count": 0,
        "stop": {"requested": False, "terminal": False, "reason_code": None},
        "artifact_refs": [],
    }


def _empty_run_state(run_uid: str, occurred_at: str) -> dict[str, Any]:
    return {
        "schema": "kronos_daily_sb3_run_state.v1",
        "run_uid": run_uid,
        "phase": "NOT_RUN",
        "lifecycle_state": "NOT_RUN",
        "event_count": 0,
        "last_run_sequence": 0,
        "last_global_sequence": 0,
        "last_event_sha256": None,
        "started_at": occurred_at,
        "updated_at": occurred_at,
        "terminal_at": None,
        "cell_uids": [],
        "max_step": 0,
        "total_steps": 0,
        "heartbeat_count": 0,
        "last_heartbeat_at": None,
        "last_live_at": None,
        "liveness": {"live": False, "basis": "NO_PROGRESS"},
        "checkpoint_refs": [],
        "artifact_refs": [],
        "stop": {"requested": False, "terminal": False, "reason_code": None},
    }


def _append_unique(target: list[dict[str, Any]], refs: Sequence[Mapping[str, Any]]) -> None:
    seen = {canonical_bytes(item) for item in target}
    for ref in refs:
        item = dict(ref)
        encoded = canonical_bytes(item)
        if encoded not in seen:
            target.append(item)
            seen.add(encoded)


def _stream_shape(stream: Any) -> Mapping[str, Any]:
    return _shape(stream, {"schema", "protocol_uid", "protocol_sha256", "source_ref", "created_at", "event_count", "final_event_sha256", "events"}, "event stream")


def _validate_and_replay(stream: Mapping[str, Any], *, protocol: Mapping[str, Any] | None = None) -> dict[str, Any]:
    authority = _protocol(protocol)
    identity = authority["identity"]
    stream = _stream_shape(stream)
    if stream["schema"] != EVENT_STREAM_SCHEMA:
        raise DailySb3EventsError("event stream schema mismatch")
    if stream["protocol_uid"] != identity["protocol_uid"] or stream["protocol_sha256"] != identity["protocol_sha256"]:
        raise DailySb3EventsError("event stream protocol identity does not match the frozen authority")
    source_ref = _source_ref(stream["source_ref"])
    created_at = _utc(stream["created_at"], "stream created_at")
    events = stream["events"]
    if not isinstance(events, list):
        raise DailySb3EventsError("event stream events must be a list")
    if _int(stream["event_count"], "stream event_count") != len(events):
        raise DailySb3EventsError("event stream event_count does not match events")
    _sha(stream["final_event_sha256"], "stream final_event_sha256")

    protocol_cells = list(authority["matrix"]["cells"])
    cells = {str(cell["cell_uid"]): _empty_cell_state(cell) for cell in protocol_cells}
    cell_attempt_number = {str(cell["cell_uid"]): 1 for cell in protocol_cells}
    runs: dict[str, dict[str, Any]] = {}
    run_next_sequence: dict[str, int] = {}
    run_last_at: dict[str, datetime] = {}
    cell_next_sequence: dict[str, int] = {}
    cell_last_at: dict[str, datetime] = {}
    cell_last_step: dict[tuple[str, str, int], int] = {}
    cell_total_steps: dict[tuple[str, str, int], int] = {}
    cell_heartbeat_count: dict[tuple[str, str, int], int] = {}
    cell_last_phase: dict[tuple[str, str, int], str] = {}
    cell_last_lifecycle_state: dict[tuple[str, str, int], str] = {}
    eligible_resume_checkpoint_refs: dict[tuple[str, str, int], set[bytes]] = {}
    terminal_runs: set[str] = set()

    previous_hash = ZERO_SHA256
    seen_hashes: set[str] = set()
    global_last_at = created_at
    first_event_at: str | None = None
    last_event_at: str | None = None

    for index, raw_record in enumerate(events, start=1):
        record = _record(raw_record, protocol=authority, source_ref=source_ref)
        event = record["event"]
        digest = record["event_sha256"]
        if digest in seen_hashes:
            raise DailySb3EventsError("event stream contains a forked duplicate event hash")
        seen_hashes.add(digest)
        if event["previous_event_sha256"] != previous_hash:
            raise DailySb3EventsError("event stream previous hash is not append-only contiguous")
        if event["global_sequence"] != index:
            raise DailySb3EventsError("event stream global_sequence has a gap or fork")

        occurred_dt = _utc(event["occurred_at"], "event occurred_at")
        if occurred_dt < global_last_at:
            raise DailySb3EventsError("event chronology is not monotonic")
        run_uid = event["run_uid"]
        cell_uid = event["cell"]["cell_uid"]
        if run_uid in terminal_runs:
            raise DailySb3EventsError("terminal run event stream is immutable")
        attempt_uid = event["attempt_uid"]
        attempt_number = event["attempt_number"]
        run_expected = run_next_sequence.get(run_uid, 1)
        if event["run_sequence"] != run_expected:
            raise DailySb3EventsError("run_sequence has a gap or fork")
        cell_expected = cell_next_sequence.get(cell_uid, 1)
        if event["cell_sequence"] != cell_expected:
            raise DailySb3EventsError("cell_sequence has a gap or fork")
        if occurred_dt < run_last_at.get(run_uid, created_at) or occurred_dt < cell_last_at.get(cell_uid, created_at):
            raise DailySb3EventsError("run/cell chronology is not monotonic")

        progress = _progress(event["progress"])
        heartbeat = _heartbeat(event["heartbeat"])
        liveness = _liveness(event["liveness"])
        resume = _resume(event["resume"])
        stop = _stop(event["stop"])
        refs = _artifact_refs(event["artifact_refs"])
        current_attempt_number = cell_attempt_number[cell_uid]
        expected_attempt_number = current_attempt_number + 1 if event["event_kind"] == "RESUME" and resume["requested"] and not resume["exact"] else current_attempt_number
        if attempt_number != expected_attempt_number:
            raise DailySb3EventsError("event attempt_number is not a contiguous exact/non-exact transition")
        expected_attempt_uid = _attempt_uid_for_cell(authority, cell_uid, attempt_number)
        if attempt_uid != expected_attempt_uid:
            raise DailySb3EventsError("event attempt_uid is not derived from the protocol, cell, and attempt_number")
        run_cell_key = (run_uid, cell_uid, attempt_number)
        prior_step = cell_last_step.get(run_cell_key, 0)
        prior_total_steps = cell_total_steps.get(run_cell_key, 0)
        prior_heartbeat_count = cell_heartbeat_count.get(run_cell_key, 0)
        prior_phase = cell_last_phase.get(run_cell_key)
        prior_lifecycle_state = cell_last_lifecycle_state.get(run_cell_key)
        if progress["step"] < prior_step:
            raise DailySb3EventsError("progress step is not monotonic for the run/cell")
        if prior_total_steps != 0 and progress["total_steps"] != prior_total_steps:
            raise DailySb3EventsError("progress total_steps drifted within a run/cell")
        step_increased = progress["step"] > prior_step
        if event["lifecycle_state"] == "ADVANCING" and not step_increased:
            raise DailySb3EventsError("ADVANCING is allowed only on a step increase")
        if step_increased and event["lifecycle_state"] != "ADVANCING":
            raise DailySb3EventsError("step increases must be recorded as ADVANCING")
        expected_heartbeat_sequence = prior_heartbeat_count + (1 if heartbeat["observed"] else 0)
        if heartbeat["heartbeat_sequence"] != expected_heartbeat_sequence:
            raise DailySb3EventsError("heartbeat sequence is not contiguous for the run/cell")
        if heartbeat["observed"] and step_increased:
            raise DailySb3EventsError("heartbeat observations must not be used as live progress")
        expected_basis = _expected_liveness_basis(
            event["event_kind"],
            step_increased=step_increased,
            heartbeat_observed=heartbeat["observed"],
            terminal=stop["terminal"],
        )
        if liveness["basis"] != expected_basis or liveness["live"] is not step_increased:
            raise DailySb3EventsError("liveness must be true only when a step increases")
        _validate_kind_semantics(event, step_increased=step_increased)
        if event["event_kind"] == "RESUME" and resume["requested"]:
            resume_ref = resume["from_checkpoint_ref"]
            source_key = (run_uid, cell_uid, current_attempt_number)
            if resume_ref is None or canonical_bytes(resume_ref) not in eligible_resume_checkpoint_refs.get(source_key, set()):
                raise DailySb3EventsError("RESUME requires a prior matching eligible CHECKPOINT for the same run/cell attempt")
        if event["event_kind"] == "CHECKPOINT" and event["checkpoint_ref"] is not None and _checkpoint_source_is_resume_eligible(prior_phase, prior_lifecycle_state):
            checkpoint = _artifact_ref(event["checkpoint_ref"], "checkpoint_ref")
            eligible_resume_checkpoint_refs.setdefault(run_cell_key, set()).add(canonical_bytes(checkpoint))
        if event["lifecycle_state"] in TERMINAL_LIFECYCLE_STATES or stop["terminal"]:
            terminal_runs.add(run_uid)

        cell = cells[cell_uid]
        cell.update(
            {
                "run_uid": run_uid,
                "phase": event["phase"],
                "lifecycle_state": event["lifecycle_state"],
                "last_step": progress["step"],
                "total_steps": progress["total_steps"],
                "percent_complete": progress["percent_complete"],
                "heartbeat_count": heartbeat["heartbeat_sequence"],
                "last_event_at": event["occurred_at"],
                "last_event_sha256": digest,
                "liveness": dict(liveness),
                "attempt_uid": attempt_uid,
                "attempt_number": attempt_number,
            }
        )
        if event["event_kind"] == "RESUME" and resume["requested"] and not resume["exact"]:
            cell["last_heartbeat_at"] = None
            cell["last_progress_at"] = None
            cell["last_live_at"] = None
            cell["checkpoint_ref"] = None
        if heartbeat["observed"]:
            cell["last_heartbeat_at"] = event["occurred_at"]
        if step_increased:
            cell["last_progress_at"] = event["occurred_at"]
            cell["last_live_at"] = event["occurred_at"]
        if event["checkpoint_ref"] is not None:
            cell["checkpoint_ref"] = dict(_artifact_ref(event["checkpoint_ref"], "checkpoint_ref"))
        if resume["requested"]:
            cell["resume_count"] += 1
        if stop["requested"]:
            cell["stop"] = dict(stop)
        _append_unique(cell["artifact_refs"], refs)

        run = runs.setdefault(run_uid, _empty_run_state(run_uid, event["occurred_at"]))
        run["phase"] = event["phase"]
        run["lifecycle_state"] = event["lifecycle_state"]
        run["event_count"] += 1
        run["last_run_sequence"] = event["run_sequence"]
        run["last_global_sequence"] = event["global_sequence"]
        run["last_event_sha256"] = digest
        run["updated_at"] = event["occurred_at"]
        if stop["terminal"]:
            run["terminal_at"] = event["occurred_at"]
        if cell_uid not in run["cell_uids"]:
            run["cell_uids"].append(cell_uid)
            run["cell_uids"].sort(key=lambda uid: cells[uid]["cell_ordinal"])
        run["max_step"] = max(run["max_step"], progress["step"])
        run["total_steps"] = max(run["total_steps"], progress["total_steps"])
        run["heartbeat_count"] += 1 if heartbeat["observed"] else 0
        if heartbeat["observed"]:
            run["last_heartbeat_at"] = event["occurred_at"]
        if step_increased:
            run["last_live_at"] = event["occurred_at"]
        run["liveness"] = dict(liveness)
        if event["checkpoint_ref"] is not None:
            _append_unique(run["checkpoint_refs"], [dict(_artifact_ref(event["checkpoint_ref"], "checkpoint_ref"))])
        _append_unique(run["artifact_refs"], refs)
        if stop["requested"]:
            run["stop"] = dict(stop)

        run_next_sequence[run_uid] = run_expected + 1
        cell_next_sequence[cell_uid] = cell_expected + 1
        run_last_at[run_uid] = occurred_dt
        cell_last_at[cell_uid] = occurred_dt
        cell_last_step[run_cell_key] = progress["step"]
        cell_total_steps[run_cell_key] = progress["total_steps"]
        cell_heartbeat_count[run_cell_key] = heartbeat["heartbeat_sequence"]
        cell_last_phase[run_cell_key] = event["phase"]
        cell_last_lifecycle_state[run_cell_key] = event["lifecycle_state"]
        cell_attempt_number[cell_uid] = attempt_number
        global_last_at = occurred_dt
        first_event_at = first_event_at or event["occurred_at"]
        last_event_at = event["occurred_at"]
        previous_hash = digest

    if previous_hash != stream["final_event_sha256"]:
        raise DailySb3EventsError("event stream final_event_sha256 does not match the terminal event")
    if not events and stream["final_event_sha256"] != ZERO_SHA256:
        raise DailySb3EventsError("empty event streams must carry the zero final hash")

    return {
        "schema": STATE_SCHEMA,
        "protocol": {
            "protocol_uid": identity["protocol_uid"],
            "protocol_sha256": identity["protocol_sha256"],
            "cell_count": authority["matrix"]["cell_count"],
        },
        "source_ref": source_ref,
        "locks": dict(FALSE_LOCKS),
        "stream": {
            "event_count": len(events),
            "final_event_sha256": previous_hash,
            "first_event_at": first_event_at,
            "last_event_at": last_event_at,
        },
        "runs": [runs[uid] for uid in sorted(runs)],
        "cells": [cells[str(cell["cell_uid"])] for cell in protocol_cells],
    }


def validate_event_stream(stream: Mapping[str, Any], *, protocol: Mapping[str, Any] | None = None) -> None:
    """Fail closed unless the stream is append-only, canonical, and protocol-bound."""
    _validate_and_replay(stream, protocol=protocol)


def replay_event_stream(stream: Mapping[str, Any], *, protocol: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Validate and deterministically reconstruct the full 50-cell state snapshot."""
    return _validate_and_replay(stream, protocol=protocol)


def synthetic_source_ref() -> dict[str, Any]:
    """Return the deterministic tiny source identity reference used by fixtures."""
    raw = canonical_bytes(
        {
            "schema": "kronos_source_identity.v1",
            "kind": "synthetic_events_fixture_source",
            "revision": "2026-07-15.g008.events.v1",
        }
    )
    return {
        "uri": "agent://kronos-v5/source-identity/events-fixture",
        "sha256": sha256_hex(raw),
        "byte_length": len(raw),
        "schema": "kronos_source_identity.v1",
    }


def artifact_ref(uri: str, schema: str, artifact_kind: str, body: Mapping[str, Any]) -> dict[str, Any]:
    """Create a small artifact reference from deterministic synthetic metadata."""
    raw = canonical_bytes(dict(body))
    ref = {
        "uri": uri,
        "sha256": sha256_hex(raw),
        "byte_length": len(raw),
        "schema": schema,
        "artifact_kind": artifact_kind,
    }
    return _artifact_ref(ref)


def start_event_stream(
    *,
    source_ref: Mapping[str, Any] | None = None,
    created_at: str = "2026-07-15T00:00:00Z",
    protocol: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an empty stream header bound to the immutable protocol authority."""
    authority = _protocol(protocol)
    identity = authority["identity"]
    source = synthetic_source_ref() if source_ref is None else _source_ref(source_ref)
    _utc(created_at, "created_at")
    return {
        "schema": EVENT_STREAM_SCHEMA,
        "protocol_uid": identity["protocol_uid"],
        "protocol_sha256": identity["protocol_sha256"],
        "source_ref": source,
        "created_at": created_at,
        "event_count": 0,
        "final_event_sha256": ZERO_SHA256,
        "events": [],
    }


def _cell_identity_from_uid(cell_uid: str, *, protocol: Mapping[str, Any], attempt_number: int = 1) -> dict[str, Any]:
    cells = _protocol_cells(protocol)
    if cell_uid not in cells:
        raise DailySb3EventsError("cell_uid is not in the frozen protocol matrix")
    attempt_number = _int(attempt_number, "attempt_number", minimum=1)
    cell = cells[cell_uid]
    return {
        "cell_uid": cell["cell_uid"],
        "attempt_uid": _attempt_uid_for_cell(protocol, cell_uid, attempt_number),
        "attempt_number": attempt_number,
        "cell_ordinal": cell["ordinal"],
        "seed_id": cell["seed_id"],
        "fold_id": cell["fold_id"],
        "variant_id": cell["variant_id"],
    }


def _last_run_cell_sequences(stream: Mapping[str, Any], run_uid: str, cell_uid: str) -> tuple[int, int, int]:
    run_sequence = 0
    cell_sequence = 0
    current_attempt_number = 1
    for record in stream["events"]:
        event = record["event"]
        if event["cell"]["cell_uid"] == cell_uid:
            cell_sequence = max(cell_sequence, int(event["cell_sequence"]))
        if event["run_uid"] == run_uid:
            run_sequence = max(run_sequence, int(event["run_sequence"]))
            if event["cell"]["cell_uid"] == cell_uid:
                current_attempt_number = int(event["attempt_number"])
    return run_sequence, cell_sequence, current_attempt_number


def _last_run_cell_attempt_counters(stream: Mapping[str, Any], run_uid: str, cell_uid: str, attempt_number: int) -> tuple[int, int, int]:
    step = 0
    total_steps = 0
    heartbeat_sequence = 0
    for record in stream["events"]:
        event = record["event"]
        if event["run_uid"] == run_uid and event["cell"]["cell_uid"] == cell_uid and int(event["attempt_number"]) == attempt_number:
            step = int(event["progress"]["step"])
            total_steps = int(event["progress"]["total_steps"])
            heartbeat_sequence = int(event["heartbeat"]["heartbeat_sequence"])
    return step, total_steps, heartbeat_sequence


def append_event(
    stream: Mapping[str, Any],
    *,
    run_uid: str,
    cell_uid: str,
    occurred_at: str,
    event_kind: str,
    phase: str,
    lifecycle_state: str,
    step: int,
    total_steps: int,
    heartbeat_observed: bool = False,
    artifact_refs: Sequence[Mapping[str, Any]] = (),
    checkpoint_ref: Mapping[str, Any] | None = None,
    resume_from_checkpoint_ref: Mapping[str, Any] | None = None,
    resume_exact: bool = False,
    attempt_number: int | None = None,
    stop_reason_code: str | None = None,
    protocol: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a new stream with one appended event; the input stream is untouched."""
    authority = _protocol(protocol)
    validate_event_stream(stream, protocol=authority)
    target = deepcopy(dict(stream))
    _run_uid(run_uid, "run_uid")
    _utc(occurred_at, "occurred_at")
    if event_kind not in EVENT_KINDS or phase not in PHASES or lifecycle_state not in LIFECYCLE_STATES:
        raise DailySb3EventsError("event kind, phase, or lifecycle state is invalid")
    step = _int(step, "step")
    total_steps = _int(total_steps, "total_steps")
    if step > total_steps:
        raise DailySb3EventsError("step may not exceed total_steps")
    refs = _artifact_refs(list(artifact_refs))
    checkpoint = None if checkpoint_ref is None else _artifact_ref(checkpoint_ref, "checkpoint_ref")
    resume_ref = None if resume_from_checkpoint_ref is None else _artifact_ref(resume_from_checkpoint_ref, "resume_from_checkpoint_ref")
    if checkpoint is not None and canonical_bytes(checkpoint) not in {canonical_bytes(ref) for ref in refs}:
        refs.append(checkpoint)
    run_sequence, cell_sequence, current_attempt_number = _last_run_cell_sequences(target, run_uid, cell_uid)
    next_attempt_number = current_attempt_number + 1 if resume_ref is not None and resume_exact is False else current_attempt_number
    event_attempt_number = next_attempt_number if attempt_number is None else _int(attempt_number, "attempt_number", minimum=1)
    previous_step, previous_total_steps, previous_heartbeat_sequence = _last_run_cell_attempt_counters(target, run_uid, cell_uid, event_attempt_number)
    if previous_total_steps != 0 and total_steps != previous_total_steps:
        raise DailySb3EventsError("total_steps drifted within a run/cell attempt")
    step_increased = step > previous_step
    heartbeat_sequence = previous_heartbeat_sequence + (1 if heartbeat_observed else 0)
    stop_requested = stop_reason_code is not None
    liveness_basis = _expected_liveness_basis(
        event_kind,
        step_increased=step_increased,
        heartbeat_observed=heartbeat_observed,
        terminal=stop_requested,
    )
    event = {
        "schema": EVENT_SCHEMA,
        "global_sequence": target["event_count"] + 1,
        "run_sequence": run_sequence + 1,
        "cell_sequence": cell_sequence + 1,
        "previous_event_sha256": target["final_event_sha256"],
        "occurred_at": occurred_at,
        "run_uid": run_uid,
        "attempt_uid": _attempt_uid_for_cell(authority, cell_uid, event_attempt_number),
        "attempt_number": event_attempt_number,
        "event_kind": event_kind,
        "phase": phase,
        "lifecycle_state": lifecycle_state,
        "protocol_uid": authority["identity"]["protocol_uid"],
        "protocol_sha256": authority["identity"]["protocol_sha256"],
        "source_ref": dict(target["source_ref"]),
        "cell": _cell_identity_from_uid(cell_uid, protocol=authority, attempt_number=event_attempt_number),
        "progress": {"step": step, "total_steps": total_steps, "percent_complete": _percent(step, total_steps)},
        "heartbeat": {"observed": heartbeat_observed, "heartbeat_sequence": heartbeat_sequence},
        "liveness": {"live": step_increased, "basis": liveness_basis},
        "artifact_refs": refs,
        "checkpoint_ref": checkpoint,
        "resume": {"requested": resume_ref is not None, "from_checkpoint_ref": resume_ref, "exact": resume_exact if resume_ref is not None else False},
        "stop": {"requested": stop_requested, "terminal": stop_requested, "reason_code": stop_reason_code},
        "locks": dict(FALSE_LOCKS),
    }
    digest = event_sha256(event)
    target["events"].append({"schema": EVENT_RECORD_SCHEMA, "event_sha256": digest, "event": event})
    target["event_count"] += 1
    target["final_event_sha256"] = digest
    validate_event_stream(target, protocol=authority)
    return target


def build_fixture_stream() -> dict[str, Any]:
    """Build a tiny deterministic stream that exercises progress, heartbeat, checkpoint, resume, and stop."""
    authority = _protocol()
    cell = authority["matrix"]["cells"][0]
    source = synthetic_source_ref()
    run_uid = f"kdp1-run-{sha256_hex({'schema': 'kronos_daily_sb3_event_fixture_run_basis.v1', 'protocol_sha256': authority['identity']['protocol_sha256'], 'source_sha256': source['sha256'], 'cell_uid': cell['cell_uid']})[:32]}"
    checkpoint = artifact_ref(
        f"agent://kronos-v5/checkpoints/{run_uid}/step-1",
        "kronos_daily_sb3_checkpoint_ref.v1",
        "synthetic_checkpoint",
        {"schema": "kronos_daily_sb3_checkpoint_ref.v1", "run_uid": run_uid, "cell_uid": cell["cell_uid"], "step": 1},
    )
    checkpoint_restart = artifact_ref(
        f"agent://kronos-v5/checkpoints/{run_uid}/step-2",
        "kronos_daily_sb3_checkpoint_ref.v1",
        "synthetic_checkpoint",
        {"schema": "kronos_daily_sb3_checkpoint_ref.v1", "run_uid": run_uid, "cell_uid": cell["cell_uid"], "step": 2},
    )
    stop_report = artifact_ref(
        f"agent://kronos-v5/stop-reports/{run_uid}",
        "kronos_daily_sb3_stop_report.v1",
        "synthetic_stop_report",
        {"schema": "kronos_daily_sb3_stop_report.v1", "run_uid": run_uid, "reason_code": "USER_REQUESTED_STOP", "step": 1, "attempt_number": 2},
    )
    stream = start_event_stream(source_ref=source, created_at="2026-07-15T00:00:00Z", protocol=authority)
    stream = append_event(stream, run_uid=run_uid, cell_uid=cell["cell_uid"], occurred_at="2026-07-15T00:00:00Z", event_kind="RUN_CREATED", phase="PREREGISTERED", lifecycle_state="NOT_RUN", step=0, total_steps=3, protocol=authority)
    stream = append_event(stream, run_uid=run_uid, cell_uid=cell["cell_uid"], occurred_at="2026-07-15T00:00:01Z", event_kind="PROGRESS", phase="SYNTHETIC_TRAIN", lifecycle_state="ADVANCING", step=1, total_steps=3, protocol=authority)
    stream = append_event(stream, run_uid=run_uid, cell_uid=cell["cell_uid"], occurred_at="2026-07-15T00:00:02Z", event_kind="HEARTBEAT", phase="SYNTHETIC_TRAIN", lifecycle_state="STALLED", step=1, total_steps=3, heartbeat_observed=True, protocol=authority)
    stream = append_event(stream, run_uid=run_uid, cell_uid=cell["cell_uid"], occurred_at="2026-07-15T00:00:03Z", event_kind="CHECKPOINT", phase="CHECKPOINT", lifecycle_state="STALLED", step=1, total_steps=3, artifact_refs=[checkpoint], checkpoint_ref=checkpoint, protocol=authority)
    stream = append_event(stream, run_uid=run_uid, cell_uid=cell["cell_uid"], occurred_at="2026-07-15T00:00:04Z", event_kind="RESUME", phase="RESUME", lifecycle_state="RESUMED", step=1, total_steps=3, resume_from_checkpoint_ref=checkpoint, resume_exact=True, protocol=authority)
    stream = append_event(stream, run_uid=run_uid, cell_uid=cell["cell_uid"], occurred_at="2026-07-15T00:00:05Z", event_kind="PROGRESS", phase="SYNTHETIC_TRAIN", lifecycle_state="ADVANCING", step=2, total_steps=3, protocol=authority)
    stream = append_event(stream, run_uid=run_uid, cell_uid=cell["cell_uid"], occurred_at="2026-07-15T00:00:06Z", event_kind="CHECKPOINT", phase="CHECKPOINT", lifecycle_state="STALLED", step=2, total_steps=3, artifact_refs=[checkpoint_restart], checkpoint_ref=checkpoint_restart, protocol=authority)
    stream = append_event(stream, run_uid=run_uid, cell_uid=cell["cell_uid"], occurred_at="2026-07-15T00:00:07Z", event_kind="RESUME", phase="RESUME", lifecycle_state="RESTARTED_NON_EXACT", step=0, total_steps=3, resume_from_checkpoint_ref=checkpoint_restart, resume_exact=False, protocol=authority)
    stream = append_event(stream, run_uid=run_uid, cell_uid=cell["cell_uid"], occurred_at="2026-07-15T00:00:08Z", event_kind="PROGRESS", phase="SYNTHETIC_TRAIN", lifecycle_state="ADVANCING", step=1, total_steps=3, protocol=authority)
    return append_event(stream, run_uid=run_uid, cell_uid=cell["cell_uid"], occurred_at="2026-07-15T00:00:09Z", event_kind="STOP", phase="STOP", lifecycle_state="STOPPED", step=1, total_steps=3, artifact_refs=[stop_report], stop_reason_code="USER_REQUESTED_STOP", protocol=authority)


def fixture_summary(stream: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return the compact golden summary used by the deterministic fixture."""
    value = build_fixture_stream() if stream is None else stream
    state = replay_event_stream(value)
    active_cells = [cell for cell in state["cells"] if cell["run_uid"] is not None]
    first_active = active_cells[0] if active_cells else None
    return {
        "schema": "kronos_daily_sb3_events_fixture_summary.v1",
        "protocol_sha256": state["protocol"]["protocol_sha256"],
        "event_count": state["stream"]["event_count"],
        "final_event_sha256": state["stream"]["final_event_sha256"],
        "state_sha256": state_sha256(state),
        "run_count": len(state["runs"]),
        "cell_count": len(state["cells"]),
        "active_cell_count": len(active_cells),
        "lifecycle_states": list(LIFECYCLE_STATES),
        "locks": dict(FALSE_LOCKS),
        "first_active_cell": None
        if first_active is None
        else {
            "cell_uid": first_active["cell_uid"],
            "attempt_uid": first_active["attempt_uid"],
            "attempt_number": first_active["attempt_number"],
            "lifecycle_state": first_active["lifecycle_state"],
            "phase": first_active["phase"],
            "last_step": first_active["last_step"],
            "total_steps": first_active["total_steps"],
            "heartbeat_count": first_active["heartbeat_count"],
            "resume_count": first_active["resume_count"],
            "liveness": first_active["liveness"],
            "stop": first_active["stop"],
        },
    }


__all__ = [
    "ARTIFACT_KINDS",
    "DailySb3EventsError",
    "EVENT_KINDS",
    "EVENT_RECORD_SCHEMA",
    "EVENT_SCHEMA",
    "EVENT_STREAM_SCHEMA",
    "FALSE_LOCK_FIELDS",
    "FALSE_LOCKS",
    "LIFECYCLE_STATES",
    "PHASES",
    "SCHEMA_ID",
    "STATE_SCHEMA",
    "ZERO_SHA256",
    "append_event",
    "artifact_ref",
    "build_fixture_stream",
    "canonical_bytes",
    "event_sha256",
    "fixture_summary",
    "replay_event_stream",
    "sha256_hex",
    "start_event_stream",
    "state_sha256",
    "synthetic_source_ref",
    "validate_event_stream",
]
