"""Fail-closed verification for the canonical Kronos v2 authority wire format."""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import io
import posixpath
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from threading import Lock
from pathlib import Path
from typing import Any, Callable, Final, Protocol, TypeAlias

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


LIFECYCLE_DOMAIN: Final = b"KRONOS-AUTHORITY-LIFECYCLE-V2\x00"
ATTESTATION_DOMAIN: Final = b"KRONOS-ATTESTATION-V2\x00"
ZERO_SHA256: Final = "0" * 64
SAFE_INT_MAX: Final = 9007199254740991
ROLES: Final = frozenset({"ORCHESTRATOR", "USABILITY_OPERATOR", "TASK_SCORE_REVIEWER", "ARCHITECT_REVIEWER", "CRITIC_REVIEWER", "EXECUTOR_QA_REVIEWER", "TERMINAL_CLOSURE_AUTHORITY", "D0_ISSUER", "D0_REVIEWER", "D1_ISSUER", "D1_REVIEWER", "OOS_CUSTODIAN", "OOS_EVALUATOR"})
SCOPES: Final = frozenset({"AUTHORITY_LIFECYCLE", "OPERATOR_A", "OPERATOR_B", "TASK_SCORE", "ARCHITECT_REVIEW", "CRITIC_REVIEW", "EXECUTOR_QA", "TERMINAL_CLOSURE", "D0_EVIDENCE", "D1_EVIDENCE", "OOS_CUSTODY", "OOS_CAPABILITY", "OOS_RELEASE", "OOS_EVALUATION"})
GJC_ROLES: Final = frozenset({"ORCHESTRATOR", "USABILITY_OPERATOR", "TASK_SCORE_REVIEWER", "ARCHITECT_REVIEWER", "CRITIC_REVIEWER", "EXECUTOR_QA_REVIEWER", "TERMINAL_CLOSURE_AUTHORITY"})
NonceKey: TypeAlias = tuple[str, str, str, bytes]


class AuthorityVerificationError(ValueError):
    """Raised when canonical authority verification fails."""


class NonceReplayStore(Protocol):
    """Durable replay store; consumption must be atomic across all consumers."""

    def consume_if_absent(self, key: NonceKey) -> bool:
        """Atomically record ``key`` and return false when it was already present."""


class InMemoryNonceReplayStore:
    """Thread-safe replay store suitable only for one-process verification tests."""

    def __init__(self) -> None:
        self._keys: set[NonceKey] = set()
        self._lock = Lock()

    def consume_if_absent(self, key: NonceKey) -> bool:
        with self._lock:
            if key in self._keys:
                return False
            self._keys.add(key)
            return True


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    """Return RFC 8785 bytes without applying any input normalization."""
    try:
        return rfc8785.dumps(value)
    except Exception as exc:
        raise AuthorityVerificationError("value is not RFC 8785 canonicalizable") from exc


def sha256_identity(value: Mapping[str, Any]) -> str:
    """Return SHA256(JCS(complete value))."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def parse_canonical_json(raw: bytes, label: str = "JSON") -> Mapping[str, Any]:
    """Parse only raw UTF-8 bytes already equal to their RFC 8785 encoding."""
    if not isinstance(raw, bytes) or raw.startswith(b"\xef\xbb\xbf"):
        raise AuthorityVerificationError(f"{label} must be UTF-8 bytes without a BOM")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AuthorityVerificationError(f"{label} contains a duplicate member")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicates, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise AuthorityVerificationError(f"{label} is not strict JSON") from exc
    if not isinstance(value, dict) or canonical_bytes(value) != raw:
        raise AuthorityVerificationError(f"{label} is not raw canonical JCS bytes")
    return value


def _required(value: Mapping[str, Any], keys: set[str], label: str) -> None:
    if set(value) != keys:
        raise AuthorityVerificationError(f"{label} has an invalid wire shape")


def _uuid(value: Any, label: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", value):
        raise AuthorityVerificationError(f"{label} is not a canonical UUID")


def _sha256(value: Any, label: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise AuthorityVerificationError(f"{label} is not a SHA-256 digest")


def _principal_uri(value: Any, label: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"agent://[^/\s]+", value):
        raise AuthorityVerificationError(f"{label} is not a principal URI")


def _time(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise AuthorityVerificationError(f"{label} is not a canonical UTC timestamp")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except ValueError as exc:
        raise AuthorityVerificationError(f"{label} is not a UTC timestamp") from exc


def _verification_time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise AuthorityVerificationError("verification_time must be timezone-aware")
    return value.astimezone(timezone.utc)


def _decode(value: Any, size: int, label: str) -> bytes:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise AuthorityVerificationError(f"{label} is not strict base64url-no-pad")
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, TypeError) as exc:
        raise AuthorityVerificationError(f"{label} is not base64url") from exc
    if len(decoded) != size or base64.urlsafe_b64encode(decoded).rstrip(b"=").decode() != value:
        raise AuthorityVerificationError(f"{label} has an invalid decoded length")
    return decoded


def _public_key(value: bytes | str, label: str) -> bytes:
    if isinstance(value, bytes):
        if len(value) != 32:
            raise AuthorityVerificationError(f"{label} must be 32 bytes")
        return value
    return _decode(value, 32, label)


def _verify(public_key: bytes, signature: Any, domain: bytes, statement: Mapping[str, Any]) -> None:
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(_decode(signature, 64, "signature"), domain + canonical_bytes(statement))
    except (InvalidSignature, ValueError) as exc:
        raise AuthorityVerificationError("Ed25519 signature verification failed") from exc


def _validate_roster(statement: Mapping[str, Any]) -> None:
    principals = statement["principals"]
    if not isinstance(principals, list) or not principals:
        raise AuthorityVerificationError("lifecycle principals are invalid")
    principal_ids: set[str] = set()
    key_ids: set[str] = set()
    lanes: dict[str, tuple[str, set[str]]] = {}
    for principal in principals:
        if not isinstance(principal, dict):
            raise AuthorityVerificationError("lifecycle principal is invalid")
        _required(principal, {"principal_uri", "roles", "scopes", "status", "keys"}, "principal")
        principal_uri, roles, scopes, keys = principal["principal_uri"], principal["roles"], principal["scopes"], principal["keys"]
        if not isinstance(principal_uri, str) or principal_uri in principal_ids or not isinstance(roles, list) or not roles or not all(isinstance(role, str) and role in ROLES for role in roles) or roles != sorted(set(roles)) or not isinstance(scopes, list) or not scopes or not all(isinstance(scope, str) and scope in SCOPES for scope in scopes) or scopes != sorted(set(scopes)) or not isinstance(keys, list) or not keys or not all(isinstance(key, dict) and isinstance(key.get("key_id"), str) for key in keys) or [key["key_id"] for key in keys] != sorted({key["key_id"] for key in keys}):
            raise AuthorityVerificationError("principal roster ordering or enum membership is invalid")
        _principal_uri(principal_uri, "principal URI")
        principal_ids.add(principal_uri)
        if principal["status"] not in {"ACTIVE", "SUSPENDED", "REVOKED"}:
            raise AuthorityVerificationError("principal status is invalid")
        principal_key_ids: set[str] = set()
        for key in keys:
            if not isinstance(key, dict):
                raise AuthorityVerificationError("lifecycle key is invalid")
            _required(key, {"key_id", "algorithm", "public_key_encoding", "public_key", "status", "not_before", "not_after", "revoked_at", "revocation_reason"}, "key")
            key_id = key["key_id"]
            if not isinstance(key_id, str) or key_id in key_ids or key_id in principal_key_ids or key["algorithm"] != "Ed25519" or key["public_key_encoding"] != "base64url-no-pad" or key["status"] not in {"ACTIVE", "SUSPENDED", "REVOKED"}:
                raise AuthorityVerificationError("key identity or status is invalid")
            _uuid(key_id, "key ID")
            key_ids.add(key_id)
            principal_key_ids.add(key_id)
            _decode(key["public_key"], 32, "public key")
            not_before, not_after = _time(key["not_before"], "key not_before"), _time(key["not_after"], "key not_after")
            if not_after <= not_before:
                raise AuthorityVerificationError("key validity interval is not chronological")
            revoked_at, reason = key["revoked_at"], key["revocation_reason"]
            if key["status"] == "REVOKED":
                if revoked_at is None or reason not in {"COMPROMISE", "ROTATION", "ROLE_REMOVED", "ADMINISTRATIVE"} or not_before >= _time(revoked_at, "key revoked_at") or _time(revoked_at, "key revoked_at") > not_after:
                    raise AuthorityVerificationError("revoked key metadata is invalid")
            elif revoked_at is not None or reason is not None:
                raise AuthorityVerificationError("non-revoked key has revocation metadata")
        if principal["status"] == "REVOKED" and any(key["status"] != "REVOKED" for key in keys):
            raise AuthorityVerificationError("revoked principal has a non-revoked key")
        for role, lane in (("D0_ISSUER", "d0_issuer"), ("D0_REVIEWER", "d0_reviewer"), ("D1_ISSUER", "d1_issuer"), ("D1_REVIEWER", "d1_reviewer"), ("OOS_CUSTODIAN", "oos_custodian"), ("OOS_EVALUATOR", "oos_evaluator")):
            if role in roles:
                lanes[lane] = (principal_uri, principal_key_ids)
    for left, right in (("d0_issuer", "d0_reviewer"), ("d1_issuer", "d1_reviewer"), ("oos_custodian", "oos_evaluator")):
        if left in lanes and right in lanes:
            left_uri, left_keys = lanes[left]
            right_uri, right_keys = lanes[right]
            if left_uri == right_uri or left_keys & right_keys:
                raise AuthorityVerificationError("independent authority lane shares a principal or key")


def _lifecycle_statement(envelope: Mapping[str, Any]) -> Mapping[str, Any]:
    _required(envelope, {"schema", "statement", "signature"}, "lifecycle envelope")
    if envelope.get("schema") != "kronos_authority_lifecycle.v2" or not isinstance(envelope.get("statement"), dict):
        raise AuthorityVerificationError("invalid lifecycle envelope")
    statement = envelope["statement"]
    _required(statement, {"schema", "authority_epoch", "sequence", "previous_authority_envelope_sha256", "roster_version", "principals", "issued_at", "effective_at", "expires_at", "signer_principal_uri", "signer_key_id", "algorithm", "signature_encoding"}, "lifecycle statement")
    if statement["schema"] != "kronos_authority_lifecycle_statement.v2" or statement["algorithm"] != "Ed25519" or statement["signature_encoding"] != "base64url-no-pad" or not isinstance(statement["sequence"], int) or isinstance(statement["sequence"], bool) or not 1 <= statement["sequence"] <= SAFE_INT_MAX or not isinstance(statement["roster_version"], int) or isinstance(statement["roster_version"], bool) or not 1 <= statement["roster_version"] <= SAFE_INT_MAX:
        raise AuthorityVerificationError("invalid lifecycle metadata")
    _uuid(statement["authority_epoch"], "authority epoch")
    _sha256(statement["previous_authority_envelope_sha256"], "lifecycle predecessor")
    _principal_uri(statement["signer_principal_uri"], "lifecycle signer principal")
    _uuid(statement["signer_key_id"], "lifecycle signer key")
    issued, effective, expires = (_time(statement[key], f"lifecycle {key}") for key in ("issued_at", "effective_at", "expires_at"))
    if effective < issued or expires <= effective:
        raise AuthorityVerificationError("lifecycle timestamps are not chronological")
    _validate_roster(statement)
    return statement


def _principal_key(statement: Mapping[str, Any], principal_uri: Any, key_id: Any, at: datetime, role: Any, scope: str | None) -> tuple[bytes, datetime]:
    principals = statement["principals"]
    principal = next((item for item in principals if item["principal_uri"] == principal_uri), None)
    if principal is None or principal["status"] != "ACTIVE" or role not in principal["roles"] or (scope is not None and scope not in principal["scopes"]):
        raise AuthorityVerificationError("principal is not active for the claimed role and scope")
    key = next((item for item in principal["keys"] if item["key_id"] == key_id), None)
    if key is None or key["status"] != "ACTIVE":
        raise AuthorityVerificationError("key is not active")
    not_before, not_after = _time(key["not_before"], "key not_before"), _time(key["not_after"], "key not_after")
    if not (not_before <= at < not_after):
        raise AuthorityVerificationError("key is outside its validity interval")
    return _decode(key["public_key"], 32, "public key"), not_after


def _verified_chain(raw_chain: Sequence[bytes], *, pinned_root_public_key: bytes | str, pinned_root_key_id: str, pinned_genesis_envelope_sha256: str) -> list[Mapping[str, Any]]:
    if not raw_chain:
        raise AuthorityVerificationError("lifecycle chain is empty")
    _sha256(pinned_genesis_envelope_sha256, "pinned genesis envelope SHA-256")
    chain = [parse_canonical_json(raw, "lifecycle envelope") for raw in raw_chain]
    root = _public_key(pinned_root_public_key, "pinned root public key")
    previous: Mapping[str, Any] | None = None
    for envelope in chain:
        statement = _lifecycle_statement(envelope)
        if previous is None:
            if statement["sequence"] != 1 or statement["previous_authority_envelope_sha256"] != ZERO_SHA256 or statement["signer_key_id"] != pinned_root_key_id or sha256_identity(envelope) != pinned_genesis_envelope_sha256:
                raise AuthorityVerificationError("genesis lifecycle is not the A3-pinned root envelope")
            _verify(root, envelope["signature"], LIFECYCLE_DOMAIN, statement)
        else:
            prior_statement = _lifecycle_statement(previous)
            if statement["authority_epoch"] != prior_statement["authority_epoch"] or statement["sequence"] != prior_statement["sequence"] + 1 or statement["roster_version"] <= prior_statement["roster_version"] or statement["previous_authority_envelope_sha256"] != sha256_identity(previous):
                raise AuthorityVerificationError("lifecycle successor identity is not contiguous")
            if _time(statement["issued_at"], "lifecycle issued_at") <= _time(prior_statement["issued_at"], "prior lifecycle issued_at") or _time(statement["effective_at"], "lifecycle effective_at") < _time(prior_statement["expires_at"], "prior lifecycle expires_at"):
                raise AuthorityVerificationError("lifecycle successor chronology overlaps or regresses")
            _validate_terminal_status_transitions(prior_statement, statement)
            signer_key, _ = _principal_key(prior_statement, statement["signer_principal_uri"], statement["signer_key_id"], _time(statement["issued_at"], "lifecycle issued_at"), "ORCHESTRATOR", "AUTHORITY_LIFECYCLE")
            _verify(signer_key, envelope["signature"], LIFECYCLE_DOMAIN, statement)
        previous = envelope
    return chain


def verify_lifecycle(raw_envelope: bytes, *, pinned_root_public_key: bytes | str, pinned_root_key_id: str, pinned_genesis_envelope_sha256: str, prior_lifecycles: Sequence[bytes] = (), verification_time: datetime) -> str:
    """Verify a canonical lifecycle chain ending in ``raw_envelope`` against A3 pins."""
    chain = _verified_chain([*prior_lifecycles, raw_envelope], pinned_root_public_key=pinned_root_public_key, pinned_root_key_id=pinned_root_key_id, pinned_genesis_envelope_sha256=pinned_genesis_envelope_sha256)
    statement = _lifecycle_statement(chain[-1])
    now = _verification_time(verification_time)
    if not (_time(statement["effective_at"], "lifecycle effective_at") <= now < _time(statement["expires_at"], "lifecycle expires_at")):
        raise AuthorityVerificationError("current lifecycle is not effective at verification time")
    return sha256_identity(chain[-1])


_STATUS_RANK: Final = {"ACTIVE": 0, "SUSPENDED": 1, "REVOKED": 2}

_ALLOWED_TUPLES: Final = frozenset({("ORCHESTRATOR", "AUTHORITY_LIFECYCLE", "AUTHORITY_LIFECYCLE"), *( ("ORCHESTRATOR", scope, "GJC_ASSIGNMENT") for scope in ("OPERATOR_A", "OPERATOR_B", "TASK_SCORE", "ARCHITECT_REVIEW", "CRITIC_REVIEW", "EXECUTOR_QA", "TERMINAL_CLOSURE") ), *( ("USABILITY_OPERATOR", scope, "GJC_ROLE_OUTPUT") for scope in ("OPERATOR_A", "OPERATOR_B") ), ("TASK_SCORE_REVIEWER", "TASK_SCORE", "GJC_ROLE_OUTPUT"), ("ARCHITECT_REVIEWER", "ARCHITECT_REVIEW", "GJC_ROLE_OUTPUT"), ("CRITIC_REVIEWER", "CRITIC_REVIEW", "GJC_ROLE_OUTPUT"), ("EXECUTOR_QA_REVIEWER", "EXECUTOR_QA", "GJC_ROLE_OUTPUT"), ("TERMINAL_CLOSURE_AUTHORITY", "TERMINAL_CLOSURE", "GJC_ROLE_OUTPUT"), ("D0_ISSUER", "D0_EVIDENCE", "D0_EVIDENCE"), ("D0_REVIEWER", "D0_EVIDENCE", "D0_EVIDENCE"), ("D1_ISSUER", "D1_EVIDENCE", "D1_EVIDENCE"), ("D1_REVIEWER", "D1_EVIDENCE", "D1_EVIDENCE"), ("OOS_CUSTODIAN", "OOS_CUSTODY", "OOS_CUSTODY"), ("OOS_CUSTODIAN", "OOS_CAPABILITY", "OOS_CAPABILITY"), ("OOS_CUSTODIAN", "OOS_RELEASE", "OOS_RELEASE"), ("OOS_EVALUATOR", "OOS_EVALUATION", "OOS_EVALUATION")})


def _validate_terminal_status_transitions(prior: Mapping[str, Any], successor: Mapping[str, Any]) -> None:
    successor_principals = {principal["principal_uri"]: principal for principal in successor["principals"]}
    for principal in prior["principals"]:
        successor_principal = successor_principals.get(principal["principal_uri"])
        if successor_principal is not None and _STATUS_RANK[successor_principal["status"]] < _STATUS_RANK[principal["status"]]:
            raise AuthorityVerificationError("principal status transition is not monotonic")
        successor_keys = {} if successor_principal is None else {key["key_id"]: key for key in successor_principal["keys"]}
        for key in principal["keys"]:
            successor_key = successor_keys.get(key["key_id"])
            if successor_key is not None and _STATUS_RANK[successor_key["status"]] < _STATUS_RANK[key["status"]]:
                raise AuthorityVerificationError("key status transition is not monotonic")


def _require_no_later_signer_revocation(chain: Sequence[Mapping[str, Any]], reference_index: int, principal_uri: str, key_id: str, role: str, scope: str) -> None:
    for envelope in chain[reference_index + 1:]:
        statement = _lifecycle_statement(envelope)
        try:
            _principal_key(statement, principal_uri, key_id, _time(statement["effective_at"], "later lifecycle effective_at"), role, scope)
        except AuthorityVerificationError as exc:
            raise AuthorityVerificationError("a later lifecycle revoked, suspended, or removed the attestation signer") from exc


def verify_attestation(raw_attestation: bytes, *, payload_bytes: bytes, payload_schema: str, scope: str, referenced_lifecycle: bytes, current_lifecycle: bytes, lifecycle_history: Sequence[bytes], pinned_root_public_key: bytes | str, pinned_root_key_id: str, pinned_genesis_envelope_sha256: str, verification_time: datetime, role_validity_caps: Mapping[str, timedelta], nonce_store: NonceReplayStore) -> None:
    """Verify a canonical attestation at issuance and against latest authority state."""
    attestation = parse_canonical_json(raw_attestation, "attestation")
    _required(attestation, {"schema", "statement", "signature"}, "attestation envelope")
    if attestation.get("schema") != "kronos_attestation.v2" or not isinstance(attestation.get("statement"), dict):
        raise AuthorityVerificationError("invalid attestation envelope")
    statement = attestation["statement"]
    _required(statement, {"schema", "attestation_uid", "payload_schema", "payload_sha256", "payload_byte_length", "signer_principal_uri", "role", "key_id", "algorithm", "signature_encoding", "authority_envelope_sha256", "issued_at", "expires_at", "nonce", "purpose"}, "attestation statement")
    if statement["schema"] != "kronos_attestation_statement.v2" or statement["algorithm"] != "Ed25519" or statement["signature_encoding"] != "base64url-no-pad":
        raise AuthorityVerificationError("invalid attestation algorithm metadata")
    _uuid(statement["attestation_uid"], "attestation UID")
    _sha256(statement["payload_sha256"], "payload SHA-256")
    _sha256(statement["authority_envelope_sha256"], "authority envelope SHA-256")
    _principal_uri(statement["signer_principal_uri"], "attestation signer principal")
    _uuid(statement["key_id"], "attestation key ID")
    if not isinstance(statement["payload_schema"], str) or not statement["payload_schema"] or not isinstance(statement["payload_byte_length"], int) or isinstance(statement["payload_byte_length"], bool) or not 0 <= statement["payload_byte_length"] <= SAFE_INT_MAX or scope not in SCOPES or (statement["role"], scope, statement["purpose"]) not in _ALLOWED_TUPLES:
        raise AuthorityVerificationError("invalid attestation payload or authorization tuple")
    if not isinstance(payload_bytes, bytes) or statement["payload_schema"] != payload_schema or statement["payload_sha256"] != hashlib.sha256(payload_bytes).hexdigest() or statement["payload_byte_length"] != len(payload_bytes):
        raise AuthorityVerificationError("attestation payload binding mismatches")
    now = _verification_time(verification_time)
    chain = _verified_chain([*lifecycle_history, current_lifecycle], pinned_root_public_key=pinned_root_public_key, pinned_root_key_id=pinned_root_key_id, pinned_genesis_envelope_sha256=pinned_genesis_envelope_sha256)
    current = chain[-1]
    if not (_time(current["statement"]["effective_at"], "current lifecycle effective_at") <= now < _time(current["statement"]["expires_at"], "current lifecycle expires_at")):
        raise AuthorityVerificationError("current lifecycle is not effective at verification time")
    referenced = parse_canonical_json(referenced_lifecycle, "referenced lifecycle envelope")
    referenced_hash = sha256_identity(referenced)
    chain_by_hash = {sha256_identity(item): item for item in chain}
    if statement["authority_envelope_sha256"] != referenced_hash or referenced_hash not in chain_by_hash:
        raise AuthorityVerificationError("attestation referenced lifecycle is not in the verified current chain")
    reference_index = next(index for index, envelope in enumerate(chain) if sha256_identity(envelope) == referenced_hash)
    referenced_statement = _lifecycle_statement(chain_by_hash[referenced_hash])
    issued, expires = _time(statement["issued_at"], "attestation issued_at"), _time(statement["expires_at"], "attestation expires_at")
    if expires <= issued or not (issued <= now < expires) or not (_time(referenced_statement["effective_at"], "referenced lifecycle effective_at") <= issued < _time(referenced_statement["expires_at"], "referenced lifecycle expires_at")):
        raise AuthorityVerificationError("attestation validity interval is invalid")
    if statement["role"] not in role_validity_caps or not isinstance(role_validity_caps[statement["role"]], timedelta) or role_validity_caps[statement["role"]] <= timedelta(0) or expires - issued > role_validity_caps[statement["role"]]:
        raise AuthorityVerificationError("attestation exceeds the role validity cap")
    if statement["role"] in GJC_ROLES and expires - issued > timedelta(hours=24):
        raise AuthorityVerificationError("GJC attestation exceeds 24 hours")
    signing_key, key_not_after = _principal_key(referenced_statement, statement["signer_principal_uri"], statement["key_id"], issued, statement["role"], scope)
    if expires > key_not_after:
        raise AuthorityVerificationError("attestation expires after its signing key")
    _require_no_later_signer_revocation(chain, reference_index, statement["signer_principal_uri"], statement["key_id"], statement["role"], scope)
    nonce = _decode(statement["nonce"], 32, "nonce")
    _verify(signing_key, attestation["signature"], ATTESTATION_DOMAIN, statement)
    try:
        consumed = nonce_store.consume_if_absent((statement["signer_principal_uri"], statement["key_id"], statement["purpose"], nonce))
    except Exception as exc:
        raise AuthorityVerificationError("nonce replay store consumption failed") from exc
    if consumed is not True:
        raise AuthorityVerificationError("attestation nonce was already used")


D0_PRICE_BASIS_SCHEMA: Final = "kronos_d0_price_basis_evidence.v1"
D0_PRICE_BASIS_STATEMENT_SCHEMA: Final = "kronos_d0_price_basis_evidence_statement.v1"
D0_PRICE_BASIS_BLOCKER: Final = "D0_PRICE_BASIS_NOT_VERIFIED"
D0_PRICE_BASIS_ROOT: Final = "_database/evidence/price_basis"
D0_PRICE_BASIS_RECORD_COUNT_EQUATION: Final = "record_count == matched_count + missing_count + conflict_count"
D0_PRICE_BASIS_VERIFIED_COLLAPSE_EQUATION: Final = "missing_count == 0 and conflict_count == 0 implies matched_count == record_count"
D1_UNIVERSE_SCHEMA: Final = "kronos_d1_universe_evidence.v1"
D1_UNIVERSE_STATEMENT_SCHEMA: Final = "kronos_d1_universe_evidence_statement.v1"
D1_UNIVERSE_BLOCKER: Final = "D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED"
D1_UNIVERSE_ROOT: Final = "_database/evidence/universe"
D1_UNIVERSE_CSV_COLUMNS: Final = ("code", "market", "issuer_name", "security_type", "listing_status", "disposition", "reason", "review_decision")
D1_UNIVERSE_ROW_COUNT_EQUATION: Final = "row_count == included_count + excluded_count + quarantine_count + unmatched_count"
D1_UNIVERSE_VERIFIED_ZERO_EQUATION: Final = "unmatched_count == 0 and quarantine_count == 0 and conflict_count == 0"
_REPO_ROOT: Final = Path(__file__).resolve().parents[1]
SignatureVerifier: TypeAlias = Callable[[Mapping[str, Any], bytes], bool]


def _evidence_blocked(schema: str, blocker: str, reasons: Sequence[str], evidence_uid: str | None = None, evidence_sha256: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"schema": f"{schema}_verification.v1", "status": "BLOCKED", "blocking_codes": [blocker], "reasons": sorted(set(reasons)) or [blocker]}
    if evidence_uid is not None:
        result["evidence_uid"] = evidence_uid
    if evidence_sha256 is not None:
        result["evidence_sha256"] = evidence_sha256
    return result


def _evidence_verified(schema: str, evidence_uid: str, evidence_sha256: str) -> dict[str, Any]:
    return {"schema": f"{schema}_verification.v1", "status": "VERIFIED", "blocking_codes": [], "reasons": [], "evidence_uid": evidence_uid, "evidence_sha256": evidence_sha256}


def _safe_count(value: Any, label: str, *, positive: bool = False) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < (1 if positive else 0) or value > SAFE_INT_MAX:
        raise AuthorityVerificationError(f"{label} is not a safe count")
    return value


def _date_only(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise AuthorityVerificationError(f"{label} is not a canonical date")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise AuthorityVerificationError(f"{label} is not a valid date") from exc


def _date_range(value: Any, label: str) -> None:
    if not isinstance(value, Mapping):
        raise AuthorityVerificationError(f"{label} is invalid")
    _required(value, {"start", "end"}, label)
    start, end = _date_only(value["start"], f"{label} start"), _date_only(value["end"], f"{label} end")
    if end < start:
        raise AuthorityVerificationError(f"{label} is not chronological")


def _portable_id(value: Any, label: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value):
        raise AuthorityVerificationError(f"{label} is not a portable identifier")


def _trusted_evidence_path(value: Any, relative_root: str, label: str, suffix: str | None = None) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value or "://" in value or value.startswith(("/", ".")):
        raise AuthorityVerificationError(f"{label} is not a trusted evidence path")
    normalized = posixpath.normpath(value)
    if normalized != value or normalized == relative_root or not normalized.startswith(f"{relative_root}/"):
        raise AuthorityVerificationError(f"{label} is outside the trusted evidence root")
    if suffix is not None and not normalized.endswith(suffix):
        raise AuthorityVerificationError(f"{label} has the wrong file type")
    return normalized


def _read_trusted_path(path: str | Path | None, relative_root: str, *, default_name: str, suffix: str) -> bytes:
    if path is None:
        relative = f"{relative_root}/{default_name}"
    else:
        candidate = Path(path)
        if candidate.is_absolute():
            raise AuthorityVerificationError("absolute evidence paths are not trusted")
        relative = candidate.as_posix()
    relative = _trusted_evidence_path(relative, relative_root, "evidence path", suffix)
    root = (_REPO_ROOT / relative_root).resolve(strict=False)
    target = (_REPO_ROOT / relative).resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise AuthorityVerificationError("evidence path escapes the trusted root") from exc
    if not target.is_file():
        raise FileNotFoundError(relative)
    try:
        real_root = root.resolve(strict=True)
        real_target = target.resolve(strict=True)
        real_target.relative_to(real_root)
    except (FileNotFoundError, ValueError) as exc:
        raise AuthorityVerificationError("evidence path resolves outside the trusted root") from exc
    return real_target.read_bytes()


def _parse_evidence_input(evidence: bytes | Mapping[str, Any], label: str) -> tuple[Mapping[str, Any], bytes]:
    if isinstance(evidence, bytes):
        if evidence.startswith(b"\xef\xbb\xbf"):
            raise AuthorityVerificationError(f"{label} must be UTF-8 bytes without a BOM")

        def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise AuthorityVerificationError(f"{label} contains a duplicate member")
                result[key] = value
            return result

        try:
            value = json.loads(evidence.decode("utf-8"), object_pairs_hook=reject_duplicates, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
            raise AuthorityVerificationError(f"{label} is not strict JSON") from exc
        if not isinstance(value, dict):
            raise AuthorityVerificationError(f"{label} is not a JSON object")
        return value, evidence
    if not isinstance(evidence, Mapping):
        raise AuthorityVerificationError(f"{label} is not a JSON object")
    raw = canonical_bytes(evidence)
    return evidence, raw


def _status_predicate(evidence: Mapping[str, Any], blocker: str) -> list[str]:
    status, blockers = evidence["status"], evidence["blocking_codes"]
    if status == "VERIFIED" and blockers == []:
        return []
    if status == "BLOCKED" and blockers == [blocker]:
        return ["evidence declares itself BLOCKED"]
    raise AuthorityVerificationError("evidence status/blocking_codes are inconsistent")


def _attestation_pair(attestations: Any, issuer_role: str, reviewer_role: str, payload: bytes, signature_verifier: SignatureVerifier | None) -> list[str]:
    if not isinstance(attestations, Mapping):
        raise AuthorityVerificationError("attestations are invalid")
    _required(attestations, {"issuer", "reviewer"}, "attestations")
    parsed: list[Mapping[str, Any]] = []
    for label, role in (("issuer", issuer_role), ("reviewer", reviewer_role)):
        attestation = attestations[label]
        if not isinstance(attestation, Mapping):
            raise AuthorityVerificationError(f"{label} attestation is invalid")
        _required(attestation, {"principal_uri", "role", "key_id", "payload_sha256", "algorithm", "signature_encoding", "signature", "signed_at"}, f"{label} attestation")
        _principal_uri(attestation["principal_uri"], f"{label} principal")
        _uuid(attestation["key_id"], f"{label} key_id")
        _sha256(attestation["payload_sha256"], f"{label} payload_sha256")
        _time(attestation["signed_at"], f"{label} signed_at")
        if attestation["role"] != role or attestation["algorithm"] != "Ed25519" or attestation["signature_encoding"] != "base64url-no-pad":
            raise AuthorityVerificationError(f"{label} attestation role or algorithm metadata is invalid")
        if attestation["payload_sha256"] != hashlib.sha256(payload).hexdigest():
            raise AuthorityVerificationError(f"{label} attestation does not bind the evidence statement")
        _decode(attestation["signature"], 64, f"{label} signature")
        parsed.append(attestation)
    issuer, reviewer = parsed
    if issuer["principal_uri"] == reviewer["principal_uri"] or issuer["key_id"] == reviewer["key_id"] or issuer["signature"] == reviewer["signature"]:
        raise AuthorityVerificationError("issuer and reviewer attestations are not independent")
    if signature_verifier is None:
        return ["attestations were parsed but not authority-verified"]
    reasons: list[str] = []
    for attestation in parsed:
        try:
            if signature_verifier(attestation, payload) is not True:
                reasons.append(f"{attestation['role']} signature verifier did not approve")
        except Exception as exc:
            reasons.append(f"{attestation['role']} signature verifier failed: {exc.__class__.__name__}")
    return reasons


def _d0_action_source(value: Any, label: str) -> list[str]:
    if not isinstance(value, Mapping):
        raise AuthorityVerificationError(f"{label} source is invalid")
    _required(value, {"source_path", "source_sha256", "date_range", "record_count", "matched_count", "missing_count", "conflict_count"}, label)
    _trusted_evidence_path(value["source_path"], D0_PRICE_BASIS_ROOT, f"{label} source_path")
    _sha256(value["source_sha256"], f"{label} source_sha256")
    _date_range(value["date_range"], f"{label} date_range")
    record_count = _safe_count(value["record_count"], f"{label} record_count")
    matched_count = _safe_count(value["matched_count"], f"{label} matched_count")
    missing_count = _safe_count(value["missing_count"], f"{label} missing_count")
    conflict_count = _safe_count(value["conflict_count"], f"{label} conflict_count")
    reasons: list[str] = []
    if record_count != matched_count + missing_count + conflict_count:
        reasons.append(f"{label} record_count equation does not balance")
    if matched_count > record_count:
        reasons.append(f"{label} matched_count exceeds record_count")
    if missing_count != 0:
        reasons.append(f"{label} missing_count is non-zero")
    if conflict_count != 0:
        reasons.append(f"{label} conflict_count is non-zero")
    if missing_count == 0 and conflict_count == 0 and matched_count != record_count:
        reasons.append(f"{label} verified zero blockers do not collapse matched_count to record_count")
    return reasons


def _d0_statement_predicates(statement: Mapping[str, Any]) -> list[str]:
    _required(statement, {"schema", "evidence_uid", "evidence_kind", "dataset", "price_basis", "equations", "corporate_actions", "review", "conflicts", "issued_at"}, "D0 statement")
    if statement["schema"] != D0_PRICE_BASIS_STATEMENT_SCHEMA:
        raise AuthorityVerificationError("D0 statement schema is invalid")
    _uuid(statement["evidence_uid"], "D0 evidence_uid")
    _time(statement["issued_at"], "D0 issued_at")
    reasons: list[str] = []
    if statement["evidence_kind"] != "REAL":
        reasons.append("D0 evidence_kind is not REAL")

    dataset = statement["dataset"]
    if not isinstance(dataset, Mapping):
        raise AuthorityVerificationError("D0 dataset is invalid")
    _required(dataset, {"artifact_path", "dataset_id", "source_database_sha256", "source_database_byte_length", "date_range", "code_count", "row_count"}, "D0 dataset")
    _trusted_evidence_path(dataset["artifact_path"], D0_PRICE_BASIS_ROOT, "D0 dataset artifact_path")
    _portable_id(dataset["dataset_id"], "D0 dataset_id")
    _sha256(dataset["source_database_sha256"], "D0 source_database_sha256")
    _safe_count(dataset["source_database_byte_length"], "D0 source_database_byte_length", positive=True)
    _date_range(dataset["date_range"], "D0 dataset date_range")
    _safe_count(dataset["code_count"], "D0 code_count", positive=True)
    _safe_count(dataset["row_count"], "D0 row_count", positive=True)

    price_basis = statement["price_basis"]
    if not isinstance(price_basis, Mapping):
        raise AuthorityVerificationError("D0 price_basis is invalid")
    _required(price_basis, {"basis", "ohlc_semantics"}, "D0 price_basis")
    basis = price_basis["basis"]
    if basis not in {"RAW", "ADJUSTED"}:
        raise AuthorityVerificationError("D0 price_basis must be RAW or ADJUSTED")
    semantics = price_basis["ohlc_semantics"]
    if not isinstance(semantics, Mapping):
        raise AuthorityVerificationError("D0 OHLC semantics are invalid")
    _required(semantics, {"open", "high", "low", "close"}, "D0 OHLC semantics")
    expected_semantics = {field: f"{basis}_{field.upper()}" for field in ("open", "high", "low", "close")}
    if dict(semantics) != expected_semantics:
        reasons.append("D0 OHLC semantics do not match the declared price basis")

    equations = statement["equations"]
    if not isinstance(equations, Mapping):
        raise AuthorityVerificationError("D0 equations are invalid")
    _required(equations, {"record_count", "verified_collapse"}, "D0 equations")
    if equations["record_count"] != D0_PRICE_BASIS_RECORD_COUNT_EQUATION:
        reasons.append("D0 record_count equation is not exact")
    if equations["verified_collapse"] != D0_PRICE_BASIS_VERIFIED_COLLAPSE_EQUATION:
        reasons.append("D0 verified_collapse equation is not exact")

    corporate_actions = statement["corporate_actions"]
    if not isinstance(corporate_actions, Mapping):
        raise AuthorityVerificationError("D0 corporate_actions is invalid")
    _required(corporate_actions, {"splits", "dividends"}, "D0 corporate_actions")
    reasons.extend(_d0_action_source(corporate_actions["splits"], "D0 splits"))
    reasons.extend(_d0_action_source(corporate_actions["dividends"], "D0 dividends"))

    review = statement["review"]
    if not isinstance(review, Mapping):
        raise AuthorityVerificationError("D0 review is invalid")
    _required(review, {"decision", "reviewed_at", "reason"}, "D0 review")
    _time(review["reviewed_at"], "D0 reviewed_at")
    if review["decision"] != "APPROVE" or not isinstance(review["reason"], str) or not review["reason"]:
        reasons.append("D0 review is not an explicit approval")
    if statement["conflicts"] != []:
        reasons.append("D0 conflicts are non-empty")
    return reasons


def evaluate_d0_price_basis_evidence(evidence: bytes | Mapping[str, Any], *, signature_verifier: SignatureVerifier | None = None) -> dict[str, Any]:
    """Parse D0 price-basis evidence and fail closed unless every predicate is exact."""
    evidence_uid: str | None = None
    evidence_sha256: str | None = None
    try:
        value, raw = _parse_evidence_input(evidence, "D0 price-basis evidence")
        evidence_sha256 = hashlib.sha256(raw).hexdigest()
        _required(value, {"schema", "statement", "attestations", "status", "blocking_codes"}, "D0 evidence")
        if value["schema"] != D0_PRICE_BASIS_SCHEMA or not isinstance(value["statement"], Mapping):
            raise AuthorityVerificationError("D0 evidence schema is invalid")
        statement = value["statement"]
        evidence_uid = statement.get("evidence_uid") if isinstance(statement.get("evidence_uid"), str) else None
        reasons = [*_status_predicate(value, D0_PRICE_BASIS_BLOCKER), *_d0_statement_predicates(statement), *_attestation_pair(value["attestations"], "D0_ISSUER", "D0_REVIEWER", canonical_bytes(statement), signature_verifier)]
        if reasons:
            return _evidence_blocked(D0_PRICE_BASIS_SCHEMA, D0_PRICE_BASIS_BLOCKER, reasons, evidence_uid, evidence_sha256)
        return _evidence_verified(D0_PRICE_BASIS_SCHEMA, str(statement["evidence_uid"]), evidence_sha256)
    except (AuthorityVerificationError, TypeError, ValueError) as exc:
        return _evidence_blocked(D0_PRICE_BASIS_SCHEMA, D0_PRICE_BASIS_BLOCKER, [str(exc)], evidence_uid, evidence_sha256)


def verify_d0_price_basis_evidence(evidence: bytes | Mapping[str, Any], *, signature_verifier: SignatureVerifier | None = None) -> dict[str, Any]:
    """Return the D0 verification result or raise the exact D0 blocker."""
    result = evaluate_d0_price_basis_evidence(evidence, signature_verifier=signature_verifier)
    if result["status"] != "VERIFIED":
        raise AuthorityVerificationError(D0_PRICE_BASIS_BLOCKER)
    return result


def read_d0_price_basis_evidence(evidence_path: str | Path | None = None, *, signature_verifier: SignatureVerifier | None = None) -> dict[str, Any]:
    """Read D0 evidence only from _database/evidence/price_basis/ and fail closed."""
    try:
        raw = _read_trusted_path(evidence_path, D0_PRICE_BASIS_ROOT, default_name="latest.json", suffix=".json")
    except (AuthorityVerificationError, OSError) as exc:
        return _evidence_blocked(D0_PRICE_BASIS_SCHEMA, D0_PRICE_BASIS_BLOCKER, [str(exc)])
    return evaluate_d0_price_basis_evidence(raw, signature_verifier=signature_verifier)


def _d1_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise AuthorityVerificationError("D1 counts are invalid")
    _required(value, {"row_count", "included_count", "excluded_count", "quarantine_count", "unmatched_count", "conflict_count"}, "D1 counts")
    return {key: _safe_count(value[key], f"D1 {key}") for key in value}


def _d1_csv_predicates(csv_decl: Mapping[str, Any], counts: Mapping[str, int], csv_bytes: bytes | None) -> list[str]:
    reasons: list[str] = []
    if csv_decl["columns"] != list(D1_UNIVERSE_CSV_COLUMNS):
        reasons.append("D1 CSV columns are not the exact official order")
    if csv_decl["byte_length"] == 0:
        reasons.append("D1 CSV byte_length is zero")
    if csv_bytes is None:
        return [*reasons, "D1 CSV bytes are unavailable from the trusted evidence root"]
    if csv_bytes.startswith(b"\xef\xbb\xbf"):
        raise AuthorityVerificationError("D1 CSV must be UTF-8 without a BOM")
    if len(csv_bytes) != csv_decl["byte_length"] or hashlib.sha256(csv_bytes).hexdigest() != csv_decl["sha256"]:
        reasons.append("D1 CSV hash or byte_length does not match")
    try:
        text = csv_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuthorityVerificationError("D1 CSV is not UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames != list(D1_UNIVERSE_CSV_COLUMNS):
        reasons.append("D1 CSV header is not exact")
        return reasons
    rows = list(reader)
    if not rows:
        reasons.append("D1 CSV has no rows")
    seen_codes: set[str] = set()
    actual_counts = {"row_count": len(rows), "included_count": 0, "excluded_count": 0, "quarantine_count": 0, "unmatched_count": 0, "conflict_count": counts["conflict_count"]}
    for row in rows:
        if row.get(None) is not None or set(row) != set(D1_UNIVERSE_CSV_COLUMNS):
            raise AuthorityVerificationError("D1 CSV row shape is invalid")
        code = row["code"]
        if not re.fullmatch(r"\d{6}", code):
            reasons.append("D1 CSV contains a non-six-digit code")
        if code in seen_codes:
            reasons.append("D1 CSV contains duplicate six-digit codes")
        seen_codes.add(code)
        disposition = row["disposition"]
        if disposition == "INCLUDE":
            actual_counts["included_count"] += 1
        elif disposition == "EXCLUDE":
            actual_counts["excluded_count"] += 1
        elif disposition == "QUARANTINE":
            actual_counts["quarantine_count"] += 1
        elif disposition == "UNMATCHED":
            actual_counts["unmatched_count"] += 1
        else:
            reasons.append("D1 CSV contains an invalid disposition")
        if not row["reason"]:
            reasons.append("D1 CSV contains an empty disposition reason")
        if row["review_decision"] != "APPROVED":
            reasons.append("D1 CSV contains an unapproved review decision")
    for key, actual in actual_counts.items():
        if counts[key] != actual:
            reasons.append(f"D1 {key} equation does not match the CSV")
    return reasons


def _d1_statement_predicates(statement: Mapping[str, Any], csv_bytes: bytes | None) -> list[str]:
    _required(statement, {"schema", "evidence_uid", "evidence_kind", "universe", "csv", "equations", "counts", "review", "conflicts", "issued_at"}, "D1 statement")
    if statement["schema"] != D1_UNIVERSE_STATEMENT_SCHEMA:
        raise AuthorityVerificationError("D1 statement schema is invalid")
    _uuid(statement["evidence_uid"], "D1 evidence_uid")
    _time(statement["issued_at"], "D1 issued_at")
    reasons: list[str] = []
    if statement["evidence_kind"] != "REAL":
        reasons.append("D1 evidence_kind is not REAL")

    universe = statement["universe"]
    if not isinstance(universe, Mapping):
        raise AuthorityVerificationError("D1 universe is invalid")
    _required(universe, {"universe_id", "official_source_path", "official_source_sha256", "source_date_range"}, "D1 universe")
    _portable_id(universe["universe_id"], "D1 universe_id")
    _trusted_evidence_path(universe["official_source_path"], D1_UNIVERSE_ROOT, "D1 official_source_path")
    _sha256(universe["official_source_sha256"], "D1 official_source_sha256")
    _date_range(universe["source_date_range"], "D1 source_date_range")

    csv_decl = statement["csv"]
    if not isinstance(csv_decl, Mapping):
        raise AuthorityVerificationError("D1 csv declaration is invalid")
    _required(csv_decl, {"artifact_path", "sha256", "byte_length", "columns"}, "D1 csv")
    _trusted_evidence_path(csv_decl["artifact_path"], D1_UNIVERSE_ROOT, "D1 csv artifact_path", ".csv")
    _sha256(csv_decl["sha256"], "D1 csv sha256")
    _safe_count(csv_decl["byte_length"], "D1 csv byte_length")
    if not isinstance(csv_decl["columns"], list) or not all(isinstance(column, str) for column in csv_decl["columns"]):
        raise AuthorityVerificationError("D1 csv columns are invalid")

    equations = statement["equations"]
    if not isinstance(equations, Mapping):
        raise AuthorityVerificationError("D1 equations are invalid")
    _required(equations, {"row_count", "verified_zero_blockers"}, "D1 equations")
    if equations["row_count"] != D1_UNIVERSE_ROW_COUNT_EQUATION:
        reasons.append("D1 row_count equation is not exact")
    if equations["verified_zero_blockers"] != D1_UNIVERSE_VERIFIED_ZERO_EQUATION:
        reasons.append("D1 verified_zero_blockers equation is not exact")

    counts = _d1_counts(statement["counts"])
    if counts["row_count"] != counts["included_count"] + counts["excluded_count"] + counts["quarantine_count"] + counts["unmatched_count"]:
        reasons.append("D1 declared row_count equation does not balance")
    if counts["unmatched_count"] != 0:
        reasons.append("D1 unmatched_count is non-zero")
    if counts["quarantine_count"] != 0:
        reasons.append("D1 quarantine_count is non-zero")
    if counts["conflict_count"] != 0:
        reasons.append("D1 conflict_count is non-zero")

    review = statement["review"]
    if not isinstance(review, Mapping):
        raise AuthorityVerificationError("D1 review is invalid")
    _required(review, {"decision", "reviewed_at", "reason"}, "D1 review")
    _time(review["reviewed_at"], "D1 reviewed_at")
    if review["decision"] != "APPROVE" or not isinstance(review["reason"], str) or not review["reason"]:
        reasons.append("D1 review is not an explicit approval")
    if statement["conflicts"] != []:
        reasons.append("D1 conflicts are non-empty")
    reasons.extend(_d1_csv_predicates(csv_decl, counts, csv_bytes))
    return reasons


def evaluate_d1_universe_evidence(evidence: bytes | Mapping[str, Any], *, csv_bytes: bytes | None = None, signature_verifier: SignatureVerifier | None = None) -> dict[str, Any]:
    """Parse D1 universe evidence and fail closed unless every predicate is exact."""
    evidence_uid: str | None = None
    evidence_sha256: str | None = None
    try:
        value, raw = _parse_evidence_input(evidence, "D1 universe evidence")
        evidence_sha256 = hashlib.sha256(raw).hexdigest()
        _required(value, {"schema", "statement", "attestations", "status", "blocking_codes"}, "D1 evidence")
        if value["schema"] != D1_UNIVERSE_SCHEMA or not isinstance(value["statement"], Mapping):
            raise AuthorityVerificationError("D1 evidence schema is invalid")
        statement = value["statement"]
        evidence_uid = statement.get("evidence_uid") if isinstance(statement.get("evidence_uid"), str) else None
        reasons = [*_status_predicate(value, D1_UNIVERSE_BLOCKER), *_d1_statement_predicates(statement, csv_bytes), *_attestation_pair(value["attestations"], "D1_ISSUER", "D1_REVIEWER", canonical_bytes(statement), signature_verifier)]
        if reasons:
            return _evidence_blocked(D1_UNIVERSE_SCHEMA, D1_UNIVERSE_BLOCKER, reasons, evidence_uid, evidence_sha256)
        return _evidence_verified(D1_UNIVERSE_SCHEMA, str(statement["evidence_uid"]), evidence_sha256)
    except (AuthorityVerificationError, TypeError, ValueError) as exc:
        return _evidence_blocked(D1_UNIVERSE_SCHEMA, D1_UNIVERSE_BLOCKER, [str(exc)], evidence_uid, evidence_sha256)


def verify_d1_universe_evidence(evidence: bytes | Mapping[str, Any], *, csv_bytes: bytes | None = None, signature_verifier: SignatureVerifier | None = None) -> dict[str, Any]:
    """Return the D1 verification result or raise the exact D1 blocker."""
    result = evaluate_d1_universe_evidence(evidence, csv_bytes=csv_bytes, signature_verifier=signature_verifier)
    if result["status"] != "VERIFIED":
        raise AuthorityVerificationError(D1_UNIVERSE_BLOCKER)
    return result


def read_d1_universe_evidence(evidence_path: str | Path | None = None, *, signature_verifier: SignatureVerifier | None = None) -> dict[str, Any]:
    """Read D1 evidence only from _database/evidence/universe/ and fail closed."""
    try:
        raw = _read_trusted_path(evidence_path, D1_UNIVERSE_ROOT, default_name="latest.json", suffix=".json")
    except (AuthorityVerificationError, OSError) as exc:
        return _evidence_blocked(D1_UNIVERSE_SCHEMA, D1_UNIVERSE_BLOCKER, [str(exc)])
    csv_bytes: bytes | None = None
    try:
        value, _ = _parse_evidence_input(raw, "D1 universe evidence")
        statement = value.get("statement")
        if isinstance(statement, Mapping):
            csv_decl = statement.get("csv")
            if isinstance(csv_decl, Mapping):
                csv_bytes = _read_trusted_path(str(csv_decl.get("artifact_path", "")), D1_UNIVERSE_ROOT, default_name="latest.csv", suffix=".csv")
    except (AuthorityVerificationError, OSError):
        csv_bytes = None
    return evaluate_d1_universe_evidence(raw, csv_bytes=csv_bytes, signature_verifier=signature_verifier)
