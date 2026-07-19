"""Fail-closed fresh-OOS custody status mechanics for Kronos v5.

This module never opens archives, decrypts bytes, reads databases, or resolves file
paths.  It verifies signed status-only custody metadata and can only return a
NOT_RUN status/denial receipt for fresh OOS data.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Final, Protocol

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


CALENDAR_DOMAIN: Final = b"KRONOS-KRX-CALENDAR-MANIFEST-V1\x00"
ACCESS_EVENT_DOMAIN: Final = b"KRONOS-OOS-ACCESS-EVENT-V1\x00"
CAPABILITY_DOMAIN: Final = b"KRONOS-OOS-CAPABILITY-V1\x00"
RELEASE_RECEIPT_DOMAIN: Final = b"KRONOS-OOS-RELEASE-RECEIPT-V1\x00"

CALENDAR_SCHEMA: Final = "kronos_krx_calendar_manifest.v1"
CALENDAR_STATEMENT_SCHEMA: Final = "kronos_krx_calendar_manifest_statement.v1"
CUSTODY_MANIFEST_SCHEMA: Final = "kronos_oos_custody_manifest.v1"
ACCESS_EVENT_SCHEMA: Final = "kronos_oos_access_event.v1"
ACCESS_EVENT_STATEMENT_SCHEMA: Final = "kronos_oos_access_event_statement.v1"
CAPABILITY_SCHEMA: Final = "kronos_oos_capability.v1"
CAPABILITY_STATEMENT_SCHEMA: Final = "kronos_oos_capability_statement.v1"
RELEASE_RECEIPT_SCHEMA: Final = "kronos_oos_release_receipt.v1"
RELEASE_RECEIPT_STATEMENT_SCHEMA: Final = "kronos_oos_release_receipt_statement.v1"
DENIAL_RECEIPT_SCHEMA: Final = "kronos_oos_denial_receipt.v1"
AUTHORITY_GRANT_SCHEMA: Final = "kronos_oos_authority_grant.v1"

KRX_TIMEZONE: Final = "Asia/Seoul"
KRX_MARKET: Final = "KRX"
CALENDAR_COLUMNS: Final = ("session_date", "market", "is_open", "open_time", "close_time", "timezone")
EVALUATOR_ACTION: Final = "OOS_EVALUATION_NOT_RUN_STATUS_ONLY"
ZERO_SHA256: Final = "0" * 64
FIRST_OPEN_SESSION_COUNT: Final = 60
MAX_CAPABILITY_TTL: Final = timedelta(hours=1)

STATUS_FRESH_OOS_NOT_AVAILABLE: Final = "FRESH_OOS_NOT_AVAILABLE"
STATUS_CONTAMINATED: Final = "CONTAMINATED"
STATUS_RELEASE_RECEIVED: Final = "RELEASE_RECEIVED"
RESULT_NOT_RUN: Final = "NOT_RUN"
STATUS_ONLY_REASON: Final = "STATUS_ONLY_RELEASE_NO_OOS_READ"

SIX_LOCKS_FALSE: Final = {
    "promotion_allowed": False,
    "model_build_allowed": False,
    "paper_forward_allowed": False,
    "live_broker_order_allowed": False,
    "profitability_claim_allowed": False,
    "go_summary_allowed": False,
}

_SHA_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_UUID_RE: Final = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")
_PRINCIPAL_RE: Final = re.compile(r"agent://[^/\s]+\Z")
_B64U_RE: Final = re.compile(r"[A-Za-z0-9_-]+\Z")
_UTC_RE: Final = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_DATE_RE: Final = re.compile(r"\d{4}-\d{2}-\d{2}\Z")

_FORBIDDEN_PAYLOAD_KEYS: Final = frozenset({
    "raw",
    "raw_bytes",
    "plaintext",
    "ciphertext",
    "decrypt_key",
    "private_key",
    "repo_path",
    "repository_path",
    "evidence_path",
    "api_path",
    "archive_path",
    "archive_uri",
    "oos_path",
    "database_path",
})

_ACCESS_EVENT_ACTIONS: Final = {
    "GENESIS_SEALED": ("OOS_CUSTODIAN", "OOS_CUSTODY_SEAL_STATUS_ONLY", "SEALED"),
    "CAPABILITY_ISSUED": ("OOS_CUSTODIAN", "OOS_CAPABILITY_ISSUE_STATUS_ONLY", "CAPABILITY_ISSUED"),
    "CAPABILITY_CONSUMED": ("OOS_CUSTODIAN", "OOS_CAPABILITY_CONSUME_STATUS_ONLY", "CAPABILITY_CONSUMED"),
    "DENIED": ("OOS_CUSTODIAN", "OOS_CUSTODY_DENY_STATUS_ONLY", STATUS_FRESH_OOS_NOT_AVAILABLE),
    "CONTAMINATED": ("OOS_CUSTODIAN", "OOS_CUSTODY_CONTAMINATE_STATUS_ONLY", STATUS_CONTAMINATED),
    "RELEASE_RECEIVED": ("OOS_EVALUATOR", EVALUATOR_ACTION, STATUS_RELEASE_RECEIVED),
}

_TERMINAL_CUSTODY_STATES: Final = frozenset({STATUS_FRESH_OOS_NOT_AVAILABLE, STATUS_CONTAMINATED})
_ALLOWED_ACCESS_TRANSITIONS: Final = {
    None: frozenset({"GENESIS_SEALED"}),
    "SEALED": frozenset({"CAPABILITY_ISSUED", "DENIED", "CONTAMINATED"}),
    "CAPABILITY_ISSUED": frozenset({"CAPABILITY_CONSUMED", "DENIED", "CONTAMINATED"}),
    "CAPABILITY_CONSUMED": frozenset({"RELEASE_RECEIVED", "CONTAMINATED"}),
    STATUS_RELEASE_RECEIVED: frozenset(),
    STATUS_FRESH_OOS_NOT_AVAILABLE: frozenset(),
    STATUS_CONTAMINATED: frozenset(),
}


class OosCustodyError(ValueError):
    """Base class for fail-closed fresh-OOS custody failures."""


class OosUnavailableError(OosCustodyError):
    """A prerequisite is absent, so fresh OOS must remain unavailable and NOT_RUN."""


class OosContaminationError(OosCustodyError):
    """Signed metadata is present but forked, replayed, malformed, or tampered."""


class CapabilityConsumptionStore(Protocol):
    """Durable one-use store.  Implementations must atomically consume first."""

    def consume_if_absent(self, capability_sha256: str, nonce_sha256: str) -> bool:
        """Return true only when this exact capability/nonce was newly consumed."""


class InMemoryCapabilityConsumptionStore:
    """Thread-safe process-local store for tests; production callers need durable IO."""

    def __init__(self) -> None:
        self._seen: set[tuple[str, str]] = set()
        self._attempts = 0
        self._lock = threading.Lock()

    @property
    def attempts(self) -> int:
        return self._attempts

    def consume_if_absent(self, capability_sha256: str, nonce_sha256: str) -> bool:
        with self._lock:
            self._attempts += 1
            key = (capability_sha256, nonce_sha256)
            if key in self._seen:
                return False
            self._seen.add(key)
            return True


@dataclass(frozen=True)
class CalendarWindow:
    manifest_sha256: str
    calendar_uid: str
    preregistered_at: datetime
    first_open_sessions: tuple[str, ...]


@dataclass(frozen=True)
class AuthorityGrant:
    principal_uri: str
    role: str
    scope: str
    purpose: str
    key_id: str
    public_key: str


@dataclass(frozen=True)
class AuthorityPair:
    custodian_custody: AuthorityGrant
    custodian_capability: AuthorityGrant
    evaluator: AuthorityGrant


@dataclass(frozen=True)
class ChainHead:
    custody_uid: str
    genesis_event_sha256: str
    head_event_sha256: str
    sealed_archive_sha256: str
    events: tuple[Mapping[str, Any], ...]
    event_sha256: tuple[str, ...]
    head_state: str
    capability_issued_event_sha256: str | None
    capability_consumed_event_sha256: str | None
    release_received_event_sha256: str | None
    capability_sha256: str | None
    release_receipt_sha256: str | None


@dataclass(frozen=True)
class CapabilityRecord:
    envelope_sha256: str
    custody_uid: str
    evaluator_principal_uri: str
    evaluator_action: str
    sealed_archive_sha256: str
    nonce_sha256: str
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class OosDecision:
    status: str
    result: str
    reason_codes: tuple[str, ...]
    capability_consumed: bool
    receipt: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "result": self.result,
            "reason_codes": list(self.reason_codes),
            "capability_consumed": self.capability_consumed,
            "receipt": dict(self.receipt),
        }


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    """Return RFC 8785/JCS bytes without normalizing the supplied value."""
    try:
        return rfc8785.dumps(value)
    except Exception as exc:  # pragma: no cover - defensive wrapper around dependency
        raise OosContaminationError("value is not RFC 8785 canonicalizable") from exc


def parse_canonical_json(raw: bytes, label: str = "object") -> dict[str, Any]:
    """Parse only strict UTF-8 JSON objects already encoded as RFC 8785/JCS bytes."""
    if not isinstance(raw, bytes) or raw.startswith(b"\xef\xbb\xbf"):
        raise OosContaminationError(f"{label} must be UTF-8 bytes without a BOM")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise OosContaminationError(f"{label} contains a duplicate member")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
        )
    except OosContaminationError:
        raise
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise OosContaminationError(f"{label} is not strict JSON") from exc
    if not isinstance(value, dict) or canonical_bytes(value) != raw:
        raise OosContaminationError(f"{label} is not raw RFC 8785/JCS bytes")
    return value


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def denial_receipt(status: str, reason_codes: Sequence[str], *, capability_consumed: bool = False) -> dict[str, Any]:
    if status not in {STATUS_FRESH_OOS_NOT_AVAILABLE, STATUS_CONTAMINATED}:
        raise OosContaminationError("denial status is invalid")
    if not reason_codes or any(not isinstance(code, str) or not code for code in reason_codes):
        raise OosContaminationError("denial reason codes are invalid")
    return {
        "schema": DENIAL_RECEIPT_SCHEMA,
        "status": status,
        "result": RESULT_NOT_RUN,
        "reason_codes": list(reason_codes),
        "fresh_oos_consumed": False,
        "capability_consumed": bool(capability_consumed),
        "raw_data_read": False,
        "archive_opened": False,
        "decrypt_attempted": False,
        "six_locks_false": dict(SIX_LOCKS_FALSE),
    }


def verify_krx_calendar_manifest(raw_manifest: bytes | None, *, public_key: bytes | str | None, preregistered_at: datetime | str) -> CalendarWindow:
    if raw_manifest is None or public_key is None:
        raise OosUnavailableError("calendar manifest or calendar key is missing")
    prereg = _coerce_utc(preregistered_at, "preregistered_at")
    _, statement, digest = _verify_envelope(raw_manifest, CALENDAR_SCHEMA, CALENDAR_STATEMENT_SCHEMA, CALENDAR_DOMAIN, public_key, "calendar manifest")
    _shape(statement, {"schema", "calendar_uid", "issued_at", "timezone", "columns", "sessions"}, "calendar statement")
    _uuid(statement["calendar_uid"], "calendar_uid")
    _utc(statement["issued_at"], "calendar issued_at")
    if statement["timezone"] != KRX_TIMEZONE or statement["columns"] != list(CALENDAR_COLUMNS):
        raise OosContaminationError("calendar timezone or columns are not the closed KRX contract")
    sessions = _calendar_sessions(statement["sessions"])
    first_open: list[str] = []
    for session in sessions:
        if session["is_open"] and _krx_timestamp(session["open_time"], session["session_date"], "09:00:00") > prereg:
            first_open.append(session["session_date"])
        if len(first_open) == FIRST_OPEN_SESSION_COUNT:
            break
    if len(first_open) != FIRST_OPEN_SESSION_COUNT:
        raise OosUnavailableError("calendar does not contain the first 60 open sessions after preregistration")
    return CalendarWindow(digest, statement["calendar_uid"], prereg, tuple(first_open))


def verify_custody_manifest(raw_manifest: bytes | None, *, calendar: CalendarWindow) -> Mapping[str, Any]:
    if raw_manifest is None:
        raise OosUnavailableError("custody manifest is missing")
    manifest = parse_canonical_json(raw_manifest, "custody manifest")
    if "acl" not in manifest:
        raise OosUnavailableError("custody ACL is missing")
    _shape(manifest, {"schema", "custody_uid", "custody_state", "preregistered_at", "calendar_manifest_sha256", "first_open_sessions", "sealed_archive", "acl", "created_at"}, "custody manifest")
    _reject_forbidden_payload(manifest)
    if manifest["schema"] != CUSTODY_MANIFEST_SCHEMA:
        raise OosContaminationError("custody manifest schema is invalid")
    _uuid(manifest["custody_uid"], "custody_uid")
    if manifest["custody_state"] == STATUS_FRESH_OOS_NOT_AVAILABLE:
        raise OosUnavailableError("custody manifest states fresh OOS is unavailable")
    if manifest["custody_state"] == STATUS_CONTAMINATED:
        raise OosContaminationError("custody manifest is already contaminated")
    if manifest["custody_state"] not in {"SEALED", "CAPABILITY_ISSUED", "CAPABILITY_CONSUMED", STATUS_RELEASE_RECEIVED}:
        raise OosContaminationError("custody state is invalid")
    if _utc(manifest["preregistered_at"], "manifest preregistered_at") != calendar.preregistered_at:
        raise OosContaminationError("custody preregistration timestamp mismatches calendar window")
    if manifest["calendar_manifest_sha256"] != calendar.manifest_sha256 or manifest["first_open_sessions"] != list(calendar.first_open_sessions):
        raise OosContaminationError("custody manifest does not bind the verified KRX calendar window")
    _utc(manifest["created_at"], "custody created_at")
    _sealed_archive(manifest["sealed_archive"])
    _acl(manifest["acl"])
    return manifest


def verify_access_chain(raw_events: Sequence[bytes] | None, *, custody_manifest_raw: bytes, custody_manifest: Mapping[str, Any], authority_grants: Sequence[Mapping[str, Any]] | None) -> ChainHead:
    if raw_events is None or not raw_events:
        raise OosUnavailableError("access event chain is missing")
    manifest_sha = sha256_hex(custody_manifest_raw)
    archive_sha = custody_manifest["sealed_archive"]["archive_sha256"]
    authority = _authority_pair(authority_grants, custody_manifest["acl"])
    statements: list[Mapping[str, Any]] = []
    event_hashes: list[str] = []
    previous_hash = ZERO_SHA256
    genesis_hash = ZERO_SHA256
    previous_time: datetime | None = None
    current_state: str | None = None
    capability_issued_event_sha: str | None = None
    capability_consumed_event_sha: str | None = None
    release_received_event_sha: str | None = None
    capability_sha: str | None = None
    release_receipt_sha: str | None = None
    for index, raw_event in enumerate(raw_events):
        envelope, statement, event_hash = _parse_signed_envelope(raw_event, ACCESS_EVENT_SCHEMA, ACCESS_EVENT_STATEMENT_SCHEMA, "access event")
        _shape(statement, {"schema", "event_uid", "custody_uid", "sequence", "event_type", "actor_principal_uri", "actor_role", "key_id", "scope", "purpose", "action", "custody_manifest_sha256", "calendar_manifest_sha256", "sealed_archive_sha256", "capability_sha256", "release_receipt_sha256", "previous_event_sha256", "genesis_event_sha256", "occurred_at", "next_custody_state"}, "access event statement")
        _verify_access_event_signature(envelope, statement, authority)
        _uuid(statement["event_uid"], "event_uid")
        if statement["custody_uid"] != custody_manifest["custody_uid"]:
            raise OosContaminationError("access event custody UID mismatches manifest")
        if not isinstance(statement["sequence"], int) or isinstance(statement["sequence"], bool) or statement["sequence"] != index:
            raise OosContaminationError("access event sequence has a gap or fork")
        expected_role, expected_action, expected_state = _ACCESS_EVENT_ACTIONS.get(statement["event_type"], (None, None, None))
        if statement["actor_role"] != expected_role or statement["action"] != expected_action or statement["next_custody_state"] != expected_state:
            raise OosContaminationError("access event role, action, or state is invalid")
        if statement["event_type"] not in _ALLOWED_ACCESS_TRANSITIONS.get(current_state, frozenset()):
            if current_state in _TERMINAL_CUSTODY_STATES:
                raise OosContaminationError("terminal OOS custody state cannot be escaped")
            raise OosContaminationError("access event custody transition is not allowed")
        if statement["custody_manifest_sha256"] != manifest_sha or statement["calendar_manifest_sha256"] != custody_manifest["calendar_manifest_sha256"] or statement["sealed_archive_sha256"] != archive_sha:
            raise OosContaminationError("access event hash binding mismatches manifest or archive")
        _sha(statement["capability_sha256"], "access event capability_sha256")
        _sha(statement["release_receipt_sha256"], "access event release_receipt_sha256")
        event_type = statement["event_type"]
        event_capability_sha = statement["capability_sha256"]
        event_release_sha = statement["release_receipt_sha256"]
        if event_type in {"GENESIS_SEALED", "CAPABILITY_ISSUED", "DENIED", "CONTAMINATED"}:
            if event_capability_sha != ZERO_SHA256 or event_release_sha != ZERO_SHA256:
                raise OosContaminationError("access event hash slots do not match the custody transition")
        elif event_type == "CAPABILITY_CONSUMED":
            if event_capability_sha == ZERO_SHA256 or event_release_sha != ZERO_SHA256:
                raise OosContaminationError("capability consumption event must bind exactly one capability")
            capability_sha = event_capability_sha
        elif event_type == "RELEASE_RECEIVED":
            if event_capability_sha == ZERO_SHA256 or event_release_sha == ZERO_SHA256:
                raise OosContaminationError("release event must bind capability and release receipt")
            if capability_sha is not None and event_capability_sha != capability_sha:
                raise OosContaminationError("release event capability hash mismatches consumed capability")
            capability_sha = event_capability_sha
            release_receipt_sha = event_release_sha
        if statement["previous_event_sha256"] != previous_hash:
            raise OosContaminationError("access event previous hash does not continue the chain")
        if index == 0:
            if statement["event_type"] != "GENESIS_SEALED" or statement["genesis_event_sha256"] != ZERO_SHA256:
                raise OosContaminationError("access chain genesis event is invalid")
            genesis_hash = event_hash
        elif statement["genesis_event_sha256"] != genesis_hash:
            raise OosContaminationError("access event genesis hash mismatches the chain root")
        occurred_at = _utc(statement["occurred_at"], "access event occurred_at")
        if previous_time is not None and occurred_at <= previous_time:
            raise OosContaminationError("access event timestamps are not strictly increasing")
        previous_time = occurred_at
        if event_type == "CAPABILITY_ISSUED":
            capability_issued_event_sha = event_hash
        elif event_type == "CAPABILITY_CONSUMED":
            capability_consumed_event_sha = event_hash
        elif event_type == "RELEASE_RECEIVED":
            release_received_event_sha = event_hash
        current_state = statement["next_custody_state"]
        statements.append(statement)
        event_hashes.append(event_hash)
        previous_hash = event_hash
    assert current_state is not None
    return ChainHead(custody_manifest["custody_uid"], genesis_hash, event_hashes[-1], archive_sha, tuple(statements), tuple(event_hashes), current_state, capability_issued_event_sha, capability_consumed_event_sha, release_received_event_sha, capability_sha, release_receipt_sha)


def verify_capability(raw_capability: bytes | None, *, custody_manifest_raw: bytes, custody_manifest: Mapping[str, Any], chain: ChainHead, authority_grants: Sequence[Mapping[str, Any]] | None, now: datetime) -> CapabilityRecord:
    if raw_capability is None:
        raise OosUnavailableError("capability is missing")
    authority = _authority_pair(authority_grants, custody_manifest["acl"])
    envelope, statement, capability_sha = _verify_envelope(raw_capability, CAPABILITY_SCHEMA, CAPABILITY_STATEMENT_SCHEMA, CAPABILITY_DOMAIN, authority.custodian_capability.public_key, "capability")
    _shape(statement, {"schema", "capability_uid", "custody_uid", "custodian_principal_uri", "role", "key_id", "scope", "purpose", "evaluator_principal_uri", "evaluator_action", "calendar_manifest_sha256", "custody_manifest_sha256", "access_chain_head_sha256", "sealed_archive_sha256", "issued_at", "expires_at", "nonce", "max_uses"}, "capability statement")
    _uuid(statement["capability_uid"], "capability_uid")
    if statement["custodian_principal_uri"] != authority.custodian_capability.principal_uri or statement["role"] != "OOS_CUSTODIAN" or statement["key_id"] != authority.custodian_capability.key_id or statement["scope"] != "OOS_CAPABILITY" or statement["purpose"] != "OOS_CAPABILITY":
        raise OosContaminationError("capability custodian authority tuple is invalid")
    acl = custody_manifest["acl"]
    if statement["custody_uid"] != custody_manifest["custody_uid"] or statement["evaluator_principal_uri"] != acl["evaluator_principal_uri"] or statement["evaluator_action"] != EVALUATOR_ACTION:
        raise OosContaminationError("capability evaluator binding is invalid")
    if chain.head_state in _TERMINAL_CUSTODY_STATES or chain.capability_issued_event_sha256 is None:
        raise OosContaminationError("capability is not bound to an allowed issued custody head")
    if chain.capability_sha256 is not None and chain.capability_sha256 != capability_sha:
        raise OosContaminationError("access chain consumed a different capability")
    if statement["calendar_manifest_sha256"] != custody_manifest["calendar_manifest_sha256"] or statement["custody_manifest_sha256"] != sha256_hex(custody_manifest_raw) or statement["access_chain_head_sha256"] != chain.capability_issued_event_sha256 or statement["sealed_archive_sha256"] != chain.sealed_archive_sha256:
        raise OosContaminationError("capability hash binding mismatches custody state")
    issued_at, expires_at = _utc(statement["issued_at"], "capability issued_at"), _utc(statement["expires_at"], "capability expires_at")
    ttl = expires_at - issued_at
    if ttl <= timedelta(0) or ttl > MAX_CAPABILITY_TTL or ttl.total_seconds() > acl["capability_ttl_seconds"]:
        raise OosContaminationError("capability TTL is not one-use <=1h")
    at = _aware_utc(now, "now")
    if not (issued_at <= at < expires_at):
        raise OosUnavailableError("capability is not valid at verification time")
    if statement["max_uses"] != 1:
        raise OosContaminationError("capability max_uses is not one")
    nonce = _nonce(statement["nonce"], "capability nonce")
    return CapabilityRecord(capability_sha, statement["custody_uid"], statement["evaluator_principal_uri"], statement["evaluator_action"], statement["sealed_archive_sha256"], sha256_hex(nonce), issued_at, expires_at)


def verify_release_receipt(raw_receipt: bytes | None, *, capability: CapabilityRecord, custody_manifest_raw: bytes, custody_manifest: Mapping[str, Any], chain: ChainHead, authority_grants: Sequence[Mapping[str, Any]] | None) -> Mapping[str, Any]:
    if raw_receipt is None:
        raise OosUnavailableError("release receipt is missing")
    authority = _authority_pair(authority_grants, custody_manifest["acl"])
    envelope, statement, receipt_sha = _verify_envelope(raw_receipt, RELEASE_RECEIPT_SCHEMA, RELEASE_RECEIPT_STATEMENT_SCHEMA, RELEASE_RECEIPT_DOMAIN, authority.evaluator.public_key, "release receipt")
    _shape(statement, {"schema", "receipt_uid", "custody_uid", "capability_sha256", "calendar_manifest_sha256", "custody_manifest_sha256", "access_chain_head_sha256", "sealed_archive_sha256", "evaluator_principal_uri", "role", "key_id", "scope", "purpose", "evaluator_action", "issued_at", "status", "result", "reason_codes", "fresh_oos_consumed", "raw_data_read", "archive_opened", "decrypt_attempted", "six_locks_false"}, "release receipt statement")
    _uuid(statement["receipt_uid"], "receipt_uid")
    if statement["custody_uid"] != custody_manifest["custody_uid"] or statement["capability_sha256"] != capability.envelope_sha256:
        raise OosContaminationError("release receipt capability binding is invalid")
    if chain.head_state != STATUS_RELEASE_RECEIVED or chain.capability_consumed_event_sha256 is None or chain.release_received_event_sha256 != chain.head_event_sha256:
        raise OosContaminationError("release receipt is not bound to the consumed/released custody sequence")
    if chain.capability_sha256 != capability.envelope_sha256 or chain.release_receipt_sha256 != receipt_sha:
        raise OosContaminationError("release event hash binding mismatches capability or receipt")
    if statement["calendar_manifest_sha256"] != custody_manifest["calendar_manifest_sha256"] or statement["custody_manifest_sha256"] != sha256_hex(custody_manifest_raw) or statement["access_chain_head_sha256"] != chain.capability_consumed_event_sha256 or statement["sealed_archive_sha256"] != chain.sealed_archive_sha256:
        raise OosContaminationError("release receipt hash binding mismatches custody state")
    if statement["evaluator_principal_uri"] != authority.evaluator.principal_uri or statement["role"] != "OOS_EVALUATOR" or statement["key_id"] != authority.evaluator.key_id or statement["scope"] != "OOS_EVALUATION" or statement["purpose"] != "OOS_EVALUATION" or statement["evaluator_action"] != EVALUATOR_ACTION:
        raise OosContaminationError("release receipt evaluator authority tuple is invalid")
    issued_at = _utc(statement["issued_at"], "release receipt issued_at")
    if not (capability.issued_at <= issued_at < capability.expires_at):
        raise OosContaminationError("release receipt was not issued inside capability validity")
    if statement["status"] != STATUS_RELEASE_RECEIVED or statement["result"] != RESULT_NOT_RUN or statement["reason_codes"] != [STATUS_ONLY_REASON]:
        raise OosContaminationError("release receipt is not the closed status-only NOT_RUN contract")
    if statement["fresh_oos_consumed"] is not False or statement["raw_data_read"] is not False or statement["archive_opened"] is not False or statement["decrypt_attempted"] is not False:
        raise OosContaminationError("release receipt claims raw OOS access")
    if statement["six_locks_false"] != SIX_LOCKS_FALSE:
        raise OosContaminationError("release receipt does not preserve false locks")
    _reject_forbidden_payload(statement)
    return envelope


def evaluate_status_release(
    *,
    calendar_manifest_raw: bytes | None,
    calendar_public_key: bytes | str | None,
    custody_manifest_raw: bytes | None,
    authority_grants: Sequence[Mapping[str, Any]] | None,
    access_event_raws: Sequence[bytes] | None,
    capability_raw: bytes | None,
    release_receipt_raw: bytes | None,
    consumption_store: CapabilityConsumptionStore | None,
    now: datetime,
) -> OosDecision:
    """Validate status-only release metadata and consume the one-use capability.

    Missing prerequisites return FRESH_OOS_NOT_AVAILABLE/NOT_RUN without touching
    the consumption store.  Tamper, fork, gap, archive mismatch, bad signature,
    replay, or store crash returns CONTAMINATED/NOT_RUN.  No file/archive IO is
    possible because the API accepts only already-supplied signed metadata bytes.
    """
    consumed = False
    try:
        preregistered_at = _peek_preregistered_at(custody_manifest_raw)
        calendar = verify_krx_calendar_manifest(calendar_manifest_raw, public_key=calendar_public_key, preregistered_at=preregistered_at)
        custody_manifest = verify_custody_manifest(custody_manifest_raw, calendar=calendar)
        chain = verify_access_chain(access_event_raws, custody_manifest_raw=custody_manifest_raw, custody_manifest=custody_manifest, authority_grants=authority_grants)
        capability = verify_capability(capability_raw, custody_manifest_raw=custody_manifest_raw, custody_manifest=custody_manifest, chain=chain, authority_grants=authority_grants, now=now)
        receipt = verify_release_receipt(release_receipt_raw, capability=capability, custody_manifest_raw=custody_manifest_raw, custody_manifest=custody_manifest, chain=chain, authority_grants=authority_grants)
        if consumption_store is None:
            raise OosUnavailableError("capability consumption store is missing")
        try:
            consumed = consumption_store.consume_if_absent(capability.envelope_sha256, capability.nonce_sha256)
        except Exception as exc:
            raise OosContaminationError("capability consume-before-read store failed") from exc
        if consumed is not True:
            consumed = False
            raise OosContaminationError("capability replay detected")
        return OosDecision(STATUS_RELEASE_RECEIVED, RESULT_NOT_RUN, (STATUS_ONLY_REASON,), True, receipt)
    except OosUnavailableError as exc:
        receipt = denial_receipt(STATUS_FRESH_OOS_NOT_AVAILABLE, (STATUS_FRESH_OOS_NOT_AVAILABLE, str(exc)), capability_consumed=False)
        return OosDecision(STATUS_FRESH_OOS_NOT_AVAILABLE, RESULT_NOT_RUN, tuple(receipt["reason_codes"]), False, receipt)
    except OosContaminationError as exc:
        receipt = denial_receipt(STATUS_CONTAMINATED, (STATUS_CONTAMINATED, str(exc)), capability_consumed=consumed)
        return OosDecision(STATUS_CONTAMINATED, RESULT_NOT_RUN, tuple(receipt["reason_codes"]), consumed, receipt)


def _peek_preregistered_at(raw_manifest: bytes | None) -> datetime:
    if raw_manifest is None:
        raise OosUnavailableError("custody manifest is missing")
    manifest = parse_canonical_json(raw_manifest, "custody manifest")
    if "preregistered_at" not in manifest:
        raise OosUnavailableError("custody preregistration timestamp is missing")
    if "acl" not in manifest:
        raise OosUnavailableError("custody ACL is missing")
    return _utc(manifest["preregistered_at"], "manifest preregistered_at")


def _shape(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise OosContaminationError(f"{label} has an invalid wire shape")
    return value


def _reject_forbidden_payload(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str) and key in _FORBIDDEN_PAYLOAD_KEYS:
                raise OosContaminationError("raw/ciphertext/path payload fields are forbidden")
            _reject_forbidden_payload(child)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden_payload(child)


def _verify_envelope(raw: bytes, envelope_schema: str, statement_schema: str, domain: bytes, public_key: bytes | str, label: str) -> tuple[Mapping[str, Any], Mapping[str, Any], str]:
    envelope, statement, digest = _parse_signed_envelope(raw, envelope_schema, statement_schema, label)
    _verify_signature(public_key, envelope["signature"], domain, statement, label)
    return envelope, statement, digest


def _parse_signed_envelope(raw: bytes, envelope_schema: str, statement_schema: str, label: str) -> tuple[Mapping[str, Any], Mapping[str, Any], str]:
    envelope = parse_canonical_json(raw, label)
    _shape(envelope, {"schema", "statement", "signature"}, label)
    if envelope["schema"] != envelope_schema:
        raise OosContaminationError(f"{label} schema is invalid")
    statement = envelope["statement"]
    if not isinstance(statement, Mapping):
        raise OosContaminationError(f"{label} statement has an invalid wire shape")
    if statement.get("schema") != statement_schema:
        raise OosContaminationError(f"{label} statement schema is invalid")
    _decode_b64u(envelope["signature"], 64, f"{label} signature")
    return envelope, statement, sha256_hex(raw)


def _verify_signature(public_key: bytes | str, signature: Any, domain: bytes, statement: Mapping[str, Any], label: str) -> None:
    key_bytes = _public_key(public_key, f"{label} public key")
    sig_bytes = _decode_b64u(signature, 64, f"{label} signature")
    try:
        Ed25519PublicKey.from_public_bytes(key_bytes).verify(sig_bytes, domain + canonical_bytes(statement))
    except InvalidSignature as exc:
        raise OosContaminationError(f"{label} signature verification failed") from exc


def _calendar_sessions(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or not value:
        raise OosContaminationError("calendar sessions are invalid")
    sessions: list[Mapping[str, Any]] = []
    dates: list[str] = []
    for row in value:
        row = _shape(row, set(CALENDAR_COLUMNS), "calendar session")
        if row["market"] != KRX_MARKET or row["timezone"] != KRX_TIMEZONE:
            raise OosContaminationError("calendar row market or timezone is invalid")
        session_date = row["session_date"]
        if not isinstance(session_date, str) or not _DATE_RE.fullmatch(session_date):
            raise OosContaminationError("calendar session_date is invalid")
        if not isinstance(row["is_open"], bool):
            raise OosContaminationError("calendar is_open is not boolean")
        if row["is_open"]:
            open_at = _krx_timestamp(row["open_time"], session_date, "09:00:00")
            close_at = _krx_timestamp(row["close_time"], session_date, "15:30:00")
            if close_at <= open_at:
                raise OosContaminationError("calendar open session close_time is not after open_time")
        elif row["open_time"] is not None or row["close_time"] is not None:
            raise OosContaminationError("closed calendar session must not carry open/close times")
        dates.append(session_date)
        sessions.append(row)
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise OosContaminationError("calendar sessions are not unique ascending")
    return sessions


def _sealed_archive(value: Any) -> None:
    value = _shape(value, {"content_kind", "archive_sha256", "archive_byte_length", "archive_media_type", "locator_commitment_sha256"}, "sealed archive commitment")
    if value["content_kind"] != "SEALED_ARCHIVE_COMMITMENT" or value["archive_media_type"] != "application/octet-stream+sealed-oos":
        raise OosContaminationError("sealed archive commitment kind is invalid")
    _sha(value["archive_sha256"], "archive_sha256")
    _sha(value["locator_commitment_sha256"], "locator_commitment_sha256")
    if not isinstance(value["archive_byte_length"], int) or isinstance(value["archive_byte_length"], bool) or value["archive_byte_length"] <= 0:
        raise OosContaminationError("sealed archive byte length is invalid")


def _acl(value: Any) -> None:
    value = _shape(value, {"custodian_principal_uri", "evaluator_principal_uri", "evaluator_action", "capability_ttl_seconds"}, "custody ACL")
    _principal(value["custodian_principal_uri"], "ACL custodian principal")
    _principal(value["evaluator_principal_uri"], "ACL evaluator principal")
    if value["custodian_principal_uri"] == value["evaluator_principal_uri"] or value["evaluator_action"] != EVALUATOR_ACTION:
        raise OosUnavailableError("custodian and evaluator ACL lanes are not distinct")
    if not isinstance(value["capability_ttl_seconds"], int) or isinstance(value["capability_ttl_seconds"], bool) or not 0 < value["capability_ttl_seconds"] <= int(MAX_CAPABILITY_TTL.total_seconds()):
        raise OosContaminationError("ACL capability TTL is invalid")


def _authority_pair(values: Sequence[Mapping[str, Any]] | None, acl: Mapping[str, Any]) -> AuthorityPair:
    if values is None:
        raise OosUnavailableError("authority grants are missing")
    grants = [_authority_grant(value) for value in values]
    if not grants:
        raise OosUnavailableError("authority grants are missing")

    def find(principal: str, role: str, scope: str, purpose: str) -> AuthorityGrant:
        matches = [grant for grant in grants if grant.principal_uri == principal and grant.role == role and grant.scope == scope and grant.purpose == purpose]
        if len(matches) != 1:
            raise OosUnavailableError("required authority grant is missing or ambiguous")
        return matches[0]

    custodian_custody = find(acl["custodian_principal_uri"], "OOS_CUSTODIAN", "OOS_CUSTODY", "OOS_CUSTODY")
    custodian_capability = find(acl["custodian_principal_uri"], "OOS_CUSTODIAN", "OOS_CAPABILITY", "OOS_CAPABILITY")
    evaluator = find(acl["evaluator_principal_uri"], "OOS_EVALUATOR", "OOS_EVALUATION", "OOS_EVALUATION")
    custodian_keys = {_public_key(custodian_custody.public_key, "custodian custody public key"), _public_key(custodian_capability.public_key, "custodian capability public key")}
    evaluator_key = _public_key(evaluator.public_key, "evaluator public key")
    if custodian_custody.principal_uri == evaluator.principal_uri or evaluator_key in custodian_keys:
        raise OosUnavailableError("custodian and evaluator authority lanes are not distinct")
    return AuthorityPair(custodian_custody, custodian_capability, evaluator)


def _authority_grant(value: Mapping[str, Any]) -> AuthorityGrant:
    value = _shape(value, {"schema", "principal_uri", "role", "scope", "purpose", "key_id", "public_key"}, "authority grant")
    if value["schema"] != AUTHORITY_GRANT_SCHEMA:
        raise OosUnavailableError("authority grant schema is invalid")
    _principal(value["principal_uri"], "authority principal")
    _uuid(value["key_id"], "authority key_id")
    _public_key(value["public_key"], "authority public key")
    allowed = {
        ("OOS_CUSTODIAN", "OOS_CUSTODY", "OOS_CUSTODY"),
        ("OOS_CUSTODIAN", "OOS_CAPABILITY", "OOS_CAPABILITY"),
        ("OOS_EVALUATOR", "OOS_EVALUATION", "OOS_EVALUATION"),
    }
    if (value["role"], value["scope"], value["purpose"]) not in allowed:
        raise OosUnavailableError("authority grant tuple is invalid")
    return AuthorityGrant(value["principal_uri"], value["role"], value["scope"], value["purpose"], value["key_id"], value["public_key"])


def _verify_access_event_signature(envelope: Mapping[str, Any], statement: Mapping[str, Any], authority: AuthorityPair) -> None:
    if statement["actor_role"] == "OOS_CUSTODIAN":
        grant = authority.custodian_custody
    elif statement["actor_role"] == "OOS_EVALUATOR":
        grant = authority.evaluator
    else:
        raise OosContaminationError("access event actor role is invalid")
    if statement["actor_principal_uri"] != grant.principal_uri or statement["key_id"] != grant.key_id or statement["scope"] != grant.scope or statement["purpose"] != grant.purpose:
        raise OosContaminationError("access event authority tuple mismatches signer")
    _verify_signature(grant.public_key, envelope["signature"], ACCESS_EVENT_DOMAIN, statement, "access event")


def _public_key(value: bytes | str, label: str) -> bytes:
    if isinstance(value, bytes):
        if len(value) != 32:
            raise OosUnavailableError(f"{label} is not a 32-byte Ed25519 key")
        return value
    try:
        return _decode_b64u(value, 32, label)
    except OosContaminationError as exc:
        raise OosUnavailableError(f"{label} is unavailable") from exc


def _decode_b64u(value: Any, length: int, label: str) -> bytes:
    if not isinstance(value, str) or not _B64U_RE.fullmatch(value):
        raise OosContaminationError(f"{label} is not base64url-no-pad")
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except Exception as exc:
        raise OosContaminationError(f"{label} is not base64url-no-pad") from exc
    if len(decoded) != length:
        raise OosContaminationError(f"{label} has invalid length")
    return decoded


def _nonce(value: Any, label: str) -> bytes:
    decoded = _decode_b64u(value, 32, label)
    if len(set(decoded)) <= 1:
        raise OosContaminationError("capability nonce is not a random 256-bit value")
    return decoded


def _uuid(value: Any, label: str) -> None:
    if not isinstance(value, str) or not _UUID_RE.fullmatch(value):
        raise OosContaminationError(f"{label} is not a canonical UUID")


def _sha(value: Any, label: str) -> None:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
        raise OosContaminationError(f"{label} is not a SHA-256 digest")


def _principal(value: Any, label: str) -> None:
    if not isinstance(value, str) or not _PRINCIPAL_RE.fullmatch(value):
        raise OosContaminationError(f"{label} is not a principal URI")


def _utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not _UTC_RE.fullmatch(value):
        raise OosContaminationError(f"{label} is not a UTC seconds timestamp")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise OosContaminationError(f"{label} is not a valid UTC timestamp") from exc


def _coerce_utc(value: datetime | str, label: str) -> datetime:
    if isinstance(value, str):
        return _utc(value, label)
    return _aware_utc(value, label)


def _aware_utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise OosContaminationError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc).replace(microsecond=0)


def _krx_timestamp(value: Any, session_date: str, hhmmss: str) -> datetime:
    expected = f"{session_date}T{hhmmss}+09:00"
    if value != expected:
        raise OosContaminationError("calendar timestamp is not the exact KRX wall-clock contract")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise OosContaminationError("calendar timestamp is invalid") from exc
    if parsed.utcoffset() != timedelta(hours=9):
        raise OosContaminationError("calendar timestamp timezone offset is invalid")
    return parsed.astimezone(timezone.utc)
