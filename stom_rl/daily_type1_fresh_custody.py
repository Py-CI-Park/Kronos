"""Type 1 fresh-OOS metadata custody coordinator.

This module deliberately handles authenticated metadata only.  It has no data
transport, no dataset capability, and no operation that can make fresh OOS
content available to a caller.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from stom_rl.daily_type1_contract import (
    FRESH_OOS_END_DATE,
    FRESH_OOS_START_DATE,
    canonical_json_bytes,
    sha256_canonical,
)

COMMITMENT_ENVELOPE_SCHEMA = "kronos_type1_fresh_commitment_envelope.v1"
EVENT_SCHEMA = "kronos_type1_fresh_custody_event.v1"
SEAL_SCHEMA = "kronos_type1_fresh_custody_seal.v1"
STATUS_SCHEMA = "kronos_type1_fresh_custody_status.v1"
FAILURE_RECEIPT_SCHEMA = "kronos_type1_fresh_custody_failure_receipt.v1"
COMMITMENT_DOMAIN = b"KRONOS-TYPE1-FRESH-COMMITMENT-V1\x00"
GENESIS_COMMITMENT_SHA256 = "0" * 64


class Type1FreshCustodyError(RuntimeError):
    """A custody invariant was violated."""


class AuthorityUnavailable(Type1FreshCustodyError):
    """The authority was unavailable before it supplied a response."""


class CustodyBlocked(Type1FreshCustodyError):
    """The custody identity has irreversibly entered terminal block."""


class MetadataAuthority(Protocol):
    """Authority facts used by this coordinator; these contain metadata only."""

    def commitment(self, ordinal: int) -> bytes | None: ...

    def key_enable(self, custody_uid: str, seal_sha256: str) -> Mapping[str, Any]: ...

    def key_disable(self, custody_uid: str, reason: str) -> Mapping[str, Any]: ...

    def access_snapshot(self, custody_uid: str, seal_sha256: str) -> Mapping[str, Any]: ...

    def consume_observed(self, custody_uid: str, seal_sha256: str, reason: str) -> Mapping[str, Any]: ...

    def issue_deny(self, custody_uid: str, block_event_sha256: str) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class Commitment:
    canonical: bytes
    statement: Mapping[str, Any]
    digest: str
@dataclass(frozen=True)
class VerifiedType1Gate:
    """A capability produced only by a separate Type1 gate verifier."""

    dataset_id: str
    custody_uid: str
    prereg_sha256: str
    seal_sha256: str
    commitment_sha256: str



def parse_and_verify_commitment_envelope(
    raw: bytes,
    *,
    expected_dataset_id: str,
    expected_custody_uid: str,
    expected_prereg_sha256: str,
    expected_principal_uri: str,
    expected_key_id: str,
    public_key: bytes | Ed25519PublicKey,
) -> Commitment:
    """Strictly parse and authenticate a canonical Type1 commitment envelope."""
    value = _canonical_object(raw, "commitment envelope")
    _keys(value, {"schema_version", "statement", "signature"}, "commitment envelope")
    if value["schema_version"] != COMMITMENT_ENVELOPE_SCHEMA:
        raise Type1FreshCustodyError("wrong commitment envelope schema")
    statement = value["statement"]
    if not isinstance(statement, dict):
        raise Type1FreshCustodyError("commitment statement must be an object")
    expected = {
        "schema_version", "dataset_id", "custody_uid", "prereg_sha256", "ordinal",
        "decision_session", "settlement_session", "ciphertext_sha256", "ciphertext_byte_length",
        "previous_commitment_sha256", "authority_principal_uri", "authority_key_id",
    }
    _keys(statement, expected, "commitment statement")
    if statement["schema_version"] != COMMITMENT_ENVELOPE_SCHEMA:
        raise Type1FreshCustodyError("wrong commitment statement schema")
    if (statement["dataset_id"], statement["custody_uid"], statement["prereg_sha256"]) != (
        expected_dataset_id, expected_custody_uid, expected_prereg_sha256,
    ):
        raise Type1FreshCustodyError("commitment identity does not match custody")
    if (statement["authority_principal_uri"], statement["authority_key_id"]) != (
        expected_principal_uri, expected_key_id,
    ):
        raise Type1FreshCustodyError("commitment authority identity does not match trust input")
    _positive_int(statement["ordinal"], "ordinal")
    _iso_date(statement["decision_session"], "decision_session")
    _iso_date(statement["settlement_session"], "settlement_session")
    _hash(statement["prereg_sha256"], "prereg_sha256")
    _hash(statement["ciphertext_sha256"], "ciphertext_sha256")
    _hash(statement["previous_commitment_sha256"], "previous_commitment_sha256")
    if type(statement["ciphertext_byte_length"]) is not int or statement["ciphertext_byte_length"] < 0:
        raise Type1FreshCustodyError("ciphertext_byte_length must be a non-negative integer")
    if not isinstance(value["signature"], str):
        raise Type1FreshCustodyError("commitment signature must be base64url text")
    try:
        _public_key(public_key).verify(_b64(value["signature"]), COMMITMENT_DOMAIN + canonical_json_bytes(statement))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise Type1FreshCustodyError("commitment signature verification failed") from exc
    return Commitment(canonical=raw, statement=statement, digest=sha256_canonical(statement))


class Type1FreshCustodyLedger:
    """Append-only local mirror of externally authenticated Type1 custody facts."""

    def __init__(
        self,
        database: str | Path,
        *,
        dataset_id: str,
        custody_uid: str,
        prereg_sha256: str,
        calendar: Sequence[tuple[str, str]],
        authority_principal_uri: str,
        authority_key_id: str,
        authority_public_key: bytes | Ed25519PublicKey,
        protocol_sha256: str,
    ) -> None:
        _hash(prereg_sha256, "prereg_sha256")
        _hash(protocol_sha256, "protocol_sha256")
        if not dataset_id or not custody_uid or not authority_principal_uri or not authority_key_id:
            raise ValueError("custody identity values must be non-empty")
        self.database = str(database)
        self.dataset_id = dataset_id
        self.custody_uid = custody_uid
        self.prereg_sha256 = prereg_sha256
        self.calendar = tuple(calendar)
        self.authority_principal_uri = authority_principal_uri
        self.authority_key_id = authority_key_id
        self.authority_public_key = authority_public_key
        self.protocol_sha256 = protocol_sha256
        self._validate_calendar()
        self._initialize()

    def reconcile_ordinal(self, authority: MetadataAuthority, ordinal: int) -> bytes | None:
        """Mirror exactly the next authenticated commitment, or perform exact replay."""
        if self._blocking():
            return self._block(authority, self._setting("reason_code") or "BLOCK_RECOVERY")
        self._assert_not_terminal()
        _positive_int(ordinal, "ordinal")
        try:
            raw = authority.commitment(ordinal)
        except AuthorityUnavailable:
            return None
        if raw is None:
            return None
        if not isinstance(raw, bytes):
            return self._block(authority, "MALFORMED_AUTHORITY_RESPONSE")
        try:
            commitment = parse_and_verify_commitment_envelope(
                raw, expected_dataset_id=self.dataset_id, expected_custody_uid=self.custody_uid,
                expected_prereg_sha256=self.prereg_sha256, expected_principal_uri=self.authority_principal_uri,
                expected_key_id=self.authority_key_id, public_key=self.authority_public_key,
            )
            if commitment.statement["ordinal"] != ordinal:
                raise Type1FreshCustodyError("authority ordinal differs from requested ordinal")
            expected_pair = self.calendar[ordinal - 1]
            if (commitment.statement["decision_session"], commitment.statement["settlement_session"]) != expected_pair:
                raise Type1FreshCustodyError("commitment session pair differs from frozen calendar")
            previous = self._commitment_digest(ordinal - 1) if ordinal > 1 else GENESIS_COMMITMENT_SHA256
            if commitment.statement["previous_commitment_sha256"] != previous:
                raise Type1FreshCustodyError("commitment predecessor differs from frozen chain")
            existing = self._commitment(ordinal)
            if existing is not None:
                if existing[0] != commitment.digest or existing[1] != raw:
                    raise Type1FreshCustodyError("same ordinal has a conflicting commitment")
                return existing[2]
            if ordinal != self._commitment_count() + 1:
                raise Type1FreshCustodyError("commitments must be contiguous and append-only")
            receipt = canonical_json_bytes({"schema_version": EVENT_SCHEMA, "ordinal": ordinal, "commitment_sha256": commitment.digest})
            with self._transaction() as connection:
                self._append_event(connection, "COMMITMENT_RECORDED", ordinal, commitment.digest, commitment.digest, "AUTHENTICATED")
                connection.execute(
                    "INSERT INTO commitments(ordinal, digest, envelope, receipt) VALUES(?, ?, ?, ?)",
                    (ordinal, commitment.digest, raw, receipt),
                )
            return receipt
        except (Type1FreshCustodyError, IndexError):
            return self._block(authority, "COMMITMENT_CONFLICT_OR_INVALID")

    def seal(self, authority: MetadataAuthority) -> bytes:
        """Record a healthy seal only after a complete authenticated calendar."""
        if self._blocking():
            return self._block(authority, self._setting("reason_code") or "BLOCK_RECOVERY")
        self._assert_not_terminal()
        if self._sealed():
            return self._seal_bytes()
        if self._commitment_count() != len(self.calendar) or len(self.calendar) < 120:
            raise Type1FreshCustodyError("complete calendar commitments are required before seal")
        try:
            facts = authority.key_enable(self.custody_uid, self._commitment_digest(len(self.calendar)))
            _keys(facts, {"key_id", "key_enable_receipt_sha256", "access_ledger_genesis_sha256", "rfc3161_receipt_sha256"}, "seal authority facts")
            for field in ("key_enable_receipt_sha256", "access_ledger_genesis_sha256", "rfc3161_receipt_sha256"):
                _hash(facts[field], field)
            if not isinstance(facts["key_id"], str) or not facts["key_id"]:
                raise Type1FreshCustodyError("seal key ID is invalid")
            snapshot = authority.access_snapshot(self.custody_uid, self._commitment_digest(len(self.calendar)))
            if snapshot != {"state": "UNUSED"}:
                raise Type1FreshCustodyError("access authority is not UNUSED")
        except AuthorityUnavailable:
            raise
        except (Type1FreshCustodyError, KeyError, TypeError):
            return self._block(authority, "SEAL_PREREQUISITE_INVALID")
        seal = {
            "schema_version": SEAL_SCHEMA, "dataset_id": self.dataset_id, "custody_uid": self.custody_uid,
            "prereg_sha256": self.prereg_sha256, "freeze_start": FRESH_OOS_START_DATE,
            "decision_end": self.calendar[-1][0], "freeze_end": FRESH_OOS_END_DATE,
            "pair_count": len(self.calendar), "first_ordinal": 1, "last_ordinal": len(self.calendar),
            "commitment_tip_sha256": self._commitment_digest(len(self.calendar)),
            "commitment_merkle_root_sha256": self._merkle_root(), "ledger_tip_sha256": self._tip(),
            "key_id": facts["key_id"], "key_enable_receipt_sha256": facts["key_enable_receipt_sha256"],
            "access_ledger_genesis_sha256": facts["access_ledger_genesis_sha256"], "key_state": "ENABLED",
            "access_state": "UNUSED", "deny_state": "ABSENT", "fresh_oos_status": "NOT_RUN",
        }
        raw = canonical_json_bytes(seal)
        with self._transaction() as connection:
            connection.execute("INSERT INTO seals(singleton, seal) VALUES(1, ?)", (raw,))
            self._append_event(connection, "SEALED", None, seal["commitment_tip_sha256"], facts["key_enable_receipt_sha256"], "HEALTHY_SEAL")
        return raw

    def record_verified_gate(self, gate: VerifiedType1Gate) -> bytes:
        """Append a separately verified Type1 gate commitment without access mutation."""
        self._assert_not_terminal()
        if not self._sealed():
            raise Type1FreshCustodyError("a gate requires a seal")
        if not isinstance(gate, VerifiedType1Gate):
            raise Type1FreshCustodyError("gate must be a verified Type1 capability")
        if (gate.dataset_id, gate.custody_uid, gate.prereg_sha256) != (
            self.dataset_id, self.custody_uid, self.prereg_sha256,
        ):
            raise Type1FreshCustodyError("gate capability does not bind this custody")
        _hash(gate.commitment_sha256, "gate_commitment_sha256")
        if gate.seal_sha256 != hashlib.sha256(self._seal_bytes()).hexdigest():
            raise Type1FreshCustodyError("gate capability does not bind this seal")
        existing = self._setting("gate_commitment_sha256")
        if existing is not None:
            if existing != gate.commitment_sha256:
                raise Type1FreshCustodyError("different gate commitment cannot replace the recorded gate")
            return canonical_json_bytes({"schema_version": EVENT_SCHEMA, "gate_commitment_sha256": existing})
        with self._transaction() as connection:
            self._append_event(connection, "GATE_RECORDED", None, gate.commitment_sha256, gate.commitment_sha256, "VERIFIED_TYPE1_GATE")
            connection.execute("INSERT INTO settings(name, value) VALUES('gate_commitment_sha256', ?)", (gate.commitment_sha256,))
        return canonical_json_bytes({"schema_version": EVENT_SCHEMA, "gate_commitment_sha256": gate.commitment_sha256})

    def recover(self, authority: MetadataAuthority) -> bytes | None:
        """Fail closed on an externally observed future RESERVED state without evaluation."""
        if self._blocking():
            return self._block(authority, self._setting("reason_code") or "BLOCK_RECOVERY")
        if not self._sealed() or self._blocked():
            return None
        seal_sha256 = hashlib.sha256(self._seal_bytes()).hexdigest()
        try:
            snapshot = authority.access_snapshot(self.custody_uid, seal_sha256)
        except AuthorityUnavailable:
            return None
        if snapshot == {"state": "UNUSED"}:
            return None
        if snapshot.get("state") == "CONSUMED":
            return self._failure_receipt()
        if snapshot.get("state") != "RESERVED":
            return self._block(authority, "ACCESS_AUTHORITY_INVALID")
        try:
            disabled = authority.key_disable(self.custody_uid, "POST_RESERVED_RECOVERY")
            _hash(disabled["receipt_sha256"], "key disable receipt")
            consumed = authority.consume_observed(self.custody_uid, seal_sha256, "POST_RESERVED_RECOVERY")
            _hash(consumed["receipt_sha256"], "consumed receipt")
        except (AuthorityUnavailable, KeyError, TypeError, Type1FreshCustodyError):
            raise Type1FreshCustodyError("post-reservation recovery could not be completed")
        receipt = {
            "schema_version": FAILURE_RECEIPT_SCHEMA, "custody_uid": self.custody_uid,
            "seal_sha256": seal_sha256, "reservation_receipt_sha256": snapshot.get("receipt_sha256"),
            "consumed_receipt_sha256": consumed["receipt_sha256"], "key_disable_receipt_sha256": disabled["receipt_sha256"],
            "reason": "POST_RESERVED_RECOVERY", "decrypt_attempted_by_recovery": False, "retry_allowed": False,
        }
        _hash(receipt["reservation_receipt_sha256"], "reservation receipt")
        raw = canonical_json_bytes(receipt)
        if self._failure_receipt() is not None:
            return self._failure_receipt()
        with self._transaction() as connection:
            self._append_event(connection, "KEY_DISABLED", None, None, disabled["receipt_sha256"], "POST_RESERVED_RECOVERY")
            self._append_event(connection, "CONSUMED_RECOVERY", None, None, consumed["receipt_sha256"], "POST_RESERVED_RECOVERY")
            connection.execute("INSERT INTO failures(singleton, receipt) VALUES(1, ?)", (raw,))
        return raw

    def status(self) -> Mapping[str, Any]:
        """Return the non-sensitive public state; fresh OOS metrics are always null."""
        blocked = self._blocked()
        recovering = self._blocking() and not blocked
        failure = self._failure_receipt() is not None
        sealed = self._sealed()
        if blocked:
            custody, public, key, access, deny = "BLOCKED", "BLOCKED_NOT_RUN", "DISABLED", "UNUSED", "ISSUED"
        elif recovering:
            custody, public, key, access, deny = "BLOCK_RECOVERY", "RECOVERY_REQUIRED_NOT_RUN", "DISABLED", "UNUSED", "PENDING"
        elif failure:
            custody, public, key, access, deny = "SEALED", "CONSUMED_NOT_RUN", "DISABLED", "CONSUMED", "ABSENT"
        elif sealed:
            custody, public, key, access, deny = "SEALED", "SEALED_NOT_RUN", "ENABLED", "UNUSED", "ABSENT"
        else:
            custody, public, key, access, deny = "ACCUMULATING", "ACCUMULATING_NOT_RUN", "UNAVAILABLE", "UNUSED", "ABSENT"
        return {
            "schema_version": STATUS_SCHEMA, "dataset_id": self.dataset_id, "custody_uid": self.custody_uid,
            "prereg_sha256": self.prereg_sha256, "expected_pair_count": len(self.calendar),
            "committed_pair_count": self._commitment_count(), "custody_state": custody,
            "authority_state": "AVAILABLE" if sealed else "ABSENT", "key_state": key,
            "gate_receipt_state": "ISSUED" if self._setting("gate_commitment_sha256") else "ABSENT",
            "access_state": access, "deny_state": deny, "fresh_oos_status": "NOT_RUN",
            "fresh_oos_metrics": None, "public_status": public,
            "recovery_state": "COMPLETE" if failure else "NONE", "reason_code": self._setting("reason_code") or "NONE",
        }

    def verify_chain(self) -> None:
        """Verify the local append-only event hash chain before relying on it."""
        previous = GENESIS_COMMITMENT_SHA256
        for row in self._connection().execute("SELECT sequence, event, digest, previous_digest FROM events ORDER BY sequence"):
            sequence, raw, digest, stored_previous = row
            if stored_previous != previous or hashlib.sha256(raw).hexdigest() != digest:
                raise Type1FreshCustodyError("event hash chain is tampered")
            event = _canonical_object(raw, "ledger event")
            _keys(event, {
                "schema_version", "sequence", "event_type", "dataset_id", "custody_uid",
                "prereg_sha256", "ordinal", "commitment_sha256", "authority_receipt_sha256",
                "reason_code", "previous_event_sha256",
            }, "ledger event")
            if event["schema_version"] != EVENT_SCHEMA or event["sequence"] != sequence:
                raise Type1FreshCustodyError("event schema or sequence is tampered")
            if (event["dataset_id"], event["custody_uid"], event["prereg_sha256"]) != (
                self.dataset_id, self.custody_uid, self.prereg_sha256,
            ):
                raise Type1FreshCustodyError("event identity is tampered")
            if event["previous_event_sha256"] != stored_previous:
                raise Type1FreshCustodyError("event predecessor is tampered")
            previous = digest

    def _block(self, authority: MetadataAuthority, reason: str) -> None:
        if self._blocked():
            raise CustodyBlocked("custody is terminally blocked")
        if not self._blocking():
            with self._transaction() as connection:
                self._append_event(connection, "BLOCK_INTENT", None, None, None, reason)
                connection.execute("INSERT INTO settings(name, value) VALUES('reason_code', ?)", (reason,))
        try:
            disabled = authority.key_disable(self.custody_uid, reason)
            _hash(disabled["receipt_sha256"], "key disable receipt")
        except (AuthorityUnavailable, KeyError, TypeError, Type1FreshCustodyError) as exc:
            raise CustodyBlocked("block recovery requires external key disable") from exc
        with self._transaction() as connection:
            self._append_event(connection, "KEY_DISABLED", None, None, disabled["receipt_sha256"], reason)
            self._append_event(connection, "BLOCKED", None, None, disabled["receipt_sha256"], reason)
        deny = authority.issue_deny(self.custody_uid, self._tip())
        try:
            _hash(deny["receipt_sha256"], "deny receipt")
        except (KeyError, TypeError, Type1FreshCustodyError) as exc:
            raise CustodyBlocked("terminal deny receipt is invalid") from exc
        with self._transaction() as connection:
            self._append_event(connection, "DENY_RECORDED", None, None, deny["receipt_sha256"], reason)
        raise CustodyBlocked(reason)

    def _initialize(self) -> None:
        connection = self._connection()
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS events(sequence INTEGER PRIMARY KEY, event BLOB NOT NULL,
                digest TEXT NOT NULL UNIQUE, previous_digest TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS commitments(ordinal INTEGER PRIMARY KEY, digest TEXT NOT NULL UNIQUE,
                envelope BLOB NOT NULL UNIQUE, receipt BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS seals(singleton INTEGER PRIMARY KEY CHECK(singleton = 1), seal BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS failures(singleton INTEGER PRIMARY KEY CHECK(singleton = 1), receipt BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS settings(name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        if connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0:
            connection.close()
            with self._transaction() as tx:
                self._append_event(tx, "GENESIS", None, None, self.protocol_sha256, "INITIALIZED")
        else:
            connection.close()
            self.verify_chain()

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _transaction(self):
        connection = self._connection()
        connection.execute("BEGIN IMMEDIATE")
        return _Transaction(connection)

    def _append_event(self, connection: sqlite3.Connection, event_type: str, ordinal: int | None, commitment: str | None, receipt: str | None, reason: str) -> None:
        previous = self._tip(connection)
        sequence = connection.execute("SELECT COALESCE(MAX(sequence), 0) + 1 FROM events").fetchone()[0]
        event = {"schema_version": EVENT_SCHEMA, "sequence": sequence, "event_type": event_type,
                 "dataset_id": self.dataset_id, "custody_uid": self.custody_uid, "prereg_sha256": self.prereg_sha256,
                 "ordinal": ordinal, "commitment_sha256": commitment, "authority_receipt_sha256": receipt,
                 "reason_code": reason, "previous_event_sha256": previous}
        raw = canonical_json_bytes(event)
        connection.execute("INSERT INTO events(sequence, event, digest, previous_digest) VALUES(?, ?, ?, ?)",
                           (sequence, raw, hashlib.sha256(raw).hexdigest(), previous))

    def _tip(self, connection: sqlite3.Connection | None = None) -> str:
        close = connection is None
        connection = connection or self._connection()
        row = connection.execute("SELECT digest FROM events ORDER BY sequence DESC LIMIT 1").fetchone()
        if close:
            connection.close()
        return row[0] if row else GENESIS_COMMITMENT_SHA256

    def _commitment(self, ordinal: int) -> tuple[str, bytes, bytes] | None:
        row = self._connection().execute("SELECT digest, envelope, receipt FROM commitments WHERE ordinal = ?", (ordinal,)).fetchone()
        return None if row is None else (row[0], row[1], row[2])

    def _commitment_digest(self, ordinal: int) -> str:
        row = self._connection().execute("SELECT digest FROM commitments WHERE ordinal = ?", (ordinal,)).fetchone()
        if row is None:
            raise Type1FreshCustodyError("missing commitment")
        return row[0]

    def _commitment_count(self) -> int:
        return self._connection().execute("SELECT COUNT(*) FROM commitments").fetchone()[0]

    def _sealed(self) -> bool:
        return self._connection().execute("SELECT 1 FROM seals WHERE singleton = 1").fetchone() is not None

    def _seal_bytes(self) -> bytes:
        row = self._connection().execute("SELECT seal FROM seals WHERE singleton = 1").fetchone()
        if row is None:
            raise Type1FreshCustodyError("seal is absent")
        return row[0]

    def _failure_receipt(self) -> bytes | None:
        row = self._connection().execute("SELECT receipt FROM failures WHERE singleton = 1").fetchone()
        return None if row is None else row[0]

    def _blocking(self) -> bool:
        return self._connection().execute("SELECT 1 FROM events WHERE CAST(event AS TEXT) LIKE ?", ('%"event_type":"BLOCK_INTENT"%',)).fetchone() is not None

    def _blocked(self) -> bool:
        return self._connection().execute("SELECT 1 FROM events WHERE CAST(event AS TEXT) LIKE ?", ('%"event_type":"BLOCKED"%',)).fetchone() is not None

    def _setting(self, name: str) -> str | None:
        row = self._connection().execute("SELECT value FROM settings WHERE name = ?", (name,)).fetchone()
        return None if row is None else row[0]

    def _assert_not_terminal(self) -> None:
        self.verify_chain()
        if self._blocked():
            raise CustodyBlocked("custody is terminally blocked")
        if self._failure_receipt() is not None:
            raise CustodyBlocked("custody was externally consumed")

    def _merkle_root(self) -> str:
        leaves = [row[0] for row in self._connection().execute("SELECT digest FROM commitments ORDER BY ordinal")]
        while len(leaves) > 1:
            if len(leaves) % 2:
                leaves.append(leaves[-1])
            leaves = [hashlib.sha256((left + right).encode("ascii")).hexdigest() for left, right in zip(leaves[::2], leaves[1::2])]
        return leaves[0]

    def _validate_calendar(self) -> None:
        if len(self.calendar) < 120 or self.calendar[0][0] != FRESH_OOS_START_DATE or self.calendar[-1][1] != FRESH_OOS_END_DATE:
            raise ValueError("calendar must cover the frozen complete Type1 OOS window with at least 120 pairs")
        previous = None
        for decision, settlement in self.calendar:
            if _iso_date(decision, "decision session") >= _iso_date(settlement, "settlement session"):
                raise ValueError("calendar pairs must be increasing")
            if previous is not None and _iso_date(decision, "decision session") <= previous:
                raise ValueError("calendar pairs must be non-overlapping and ordered")
            previous = _iso_date(settlement, "settlement session")


class _Transaction:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def __enter__(self) -> sqlite3.Connection:
        return self.connection

    def __exit__(self, kind: Any, value: Any, traceback: Any) -> None:
        try:
            self.connection.commit() if kind is None else self.connection.rollback()
        finally:
            self.connection.close()


def _canonical_object(raw: bytes, label: str) -> dict[str, Any]:
    if not isinstance(raw, bytes):
        raise Type1FreshCustodyError(f"{label} must be bytes")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Type1FreshCustodyError(f"{label} is not JSON") from exc
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        raise Type1FreshCustodyError(f"{label} is not canonical JSON")
    return value


def _keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise Type1FreshCustodyError(f"{label} has missing or unknown fields")


def _hash(value: Any, label: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise Type1FreshCustodyError(f"{label} must be lower-case SHA-256")


def _positive_int(value: Any, label: str) -> None:
    if type(value) is not int or value < 1:
        raise Type1FreshCustodyError(f"{label} must be a positive integer")


def _iso_date(value: Any, label: str) -> date:
    if not isinstance(value, str):
        raise Type1FreshCustodyError(f"{label} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise Type1FreshCustodyError(f"{label} must be an ISO date") from exc


def _b64(value: str) -> bytes:
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, UnicodeEncodeError) as exc:
        raise Type1FreshCustodyError("signature is not base64url") from exc
    if len(decoded) != 64:
        raise Type1FreshCustodyError("signature has wrong length")
    return decoded


def _public_key(value: bytes | Ed25519PublicKey) -> Ed25519PublicKey:
    if isinstance(value, Ed25519PublicKey):
        return value
    if isinstance(value, bytes) and len(value) == 32:
        return Ed25519PublicKey.from_public_bytes(value)
    raise Type1FreshCustodyError("authority public key must be a 32-byte Ed25519 key")
