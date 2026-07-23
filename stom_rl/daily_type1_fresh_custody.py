"""Durable metadata-only custody ledger for the Type1 frozen window.

This module intentionally has no content transport capability.  Its inputs and
outputs are signed authority statements, hashes, calendar pairs, and receipts.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping, Protocol, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from stom_rl.daily_type1_contract import FRESH_OOS_END_DATE, FRESH_OOS_START_DATE, canonical_json_bytes

COMMITMENT_ENVELOPE_SCHEMA = "kronos_type1_fresh_commitment_envelope.v1"
EVENT_SCHEMA = "kronos_type1_fresh_custody_event.v1"
SEAL_SCHEMA = "kronos_type1_fresh_custody_seal.v1"
STATUS_SCHEMA = "kronos_type1_fresh_custody_status.v1"
FAILURE_RECEIPT_SCHEMA = "kronos_type1_fresh_custody_failure_receipt.v1"
GATE_RECEIPT_SCHEMA = "kronos_type1_fresh_gate_receipt.v1"
# Frozen, non-zero protocol anchor.  It is an identity, not an all-zero sentinel.
GENESIS_COMMITMENT_SHA256 = "4127aeb0" + ("0" * 52) + "2301"
HASH_DOMAINS = {
    "commitment": b"KRONOS-TYPE1-COMMITMENT-V1\x00",
    "merkle_leaf": b"KRONOS-TYPE1-MERKLE-LEAF-V1\x00",
    "merkle_node": b"KRONOS-TYPE1-MERKLE-NODE-V1\x00",
    "event": b"KRONOS-TYPE1-EVENT-V1\x00",
    "seal": b"KRONOS-TYPE1-SEAL-V1\x00",
    "block": b"KRONOS-TYPE1-BLOCK-V1\x00",
    "gate": b"KRONOS-TYPE1-GATE-V1\x00",
}
COMMITMENT_DOMAIN = HASH_DOMAINS["commitment"]


class Type1FreshCustodyError(RuntimeError): pass
class AuthorityUnavailable(Type1FreshCustodyError): pass
class CustodyBlocked(Type1FreshCustodyError): pass


class MetadataAuthority(Protocol):
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


def _domain_digest(domain: str, *parts: bytes) -> str:
    try: prefix = HASH_DOMAINS[domain]
    except KeyError as exc: raise Type1FreshCustodyError("unknown hash domain") from exc
    h = hashlib.sha256(prefix)
    for part in parts:
        h.update(len(part).to_bytes(8, "big")); h.update(part)
    return h.hexdigest()


def _hex_bytes(value: str, label: str) -> bytes:
    _hash(value, label)
    return bytes.fromhex(value)


def commitment_digest(statement: Mapping[str, Any]) -> str:
    """Domain-separated statement identity using raw canonical bytes."""
    ordinal = statement.get("ordinal")
    _positive_int(ordinal, "ordinal")
    return _domain_digest("commitment", ordinal.to_bytes(8, "big"), canonical_json_bytes(statement))


def parse_and_verify_commitment_envelope(raw: bytes, *, expected_dataset_id: str, expected_custody_uid: str,
    expected_prereg_sha256: str, expected_principal_uri: str, expected_key_id: str,
    public_key: bytes | Ed25519PublicKey) -> Commitment:
    value = _canonical_object(raw, "commitment envelope")
    _keys(value, {"schema_version", "statement", "signature"}, "commitment envelope")
    if value["schema_version"] != COMMITMENT_ENVELOPE_SCHEMA or not isinstance(value["statement"], dict):
        raise Type1FreshCustodyError("invalid commitment envelope")
    statement = value["statement"]
    _keys(statement, {"schema_version", "dataset_id", "custody_uid", "prereg_sha256", "ordinal", "decision_session",
        "settlement_session", "ciphertext_sha256", "ciphertext_byte_length", "previous_commitment_sha256",
        "authority_principal_uri", "authority_key_id"}, "commitment statement")
    if statement["schema_version"] != COMMITMENT_ENVELOPE_SCHEMA or (statement["dataset_id"], statement["custody_uid"], statement["prereg_sha256"]) != (expected_dataset_id, expected_custody_uid, expected_prereg_sha256):
        raise Type1FreshCustodyError("commitment identity does not match custody")
    if (statement["authority_principal_uri"], statement["authority_key_id"]) != (expected_principal_uri, expected_key_id):
        raise Type1FreshCustodyError("commitment authority identity does not match trust input")
    _positive_int(statement["ordinal"], "ordinal"); _iso_date(statement["decision_session"], "decision_session"); _iso_date(statement["settlement_session"], "settlement_session")
    for name in ("prereg_sha256", "ciphertext_sha256", "previous_commitment_sha256"): _hash(statement[name], name)
    if type(statement["ciphertext_byte_length"]) is not int or statement["ciphertext_byte_length"] < 0: raise Type1FreshCustodyError("invalid ciphertext length")
    try: _public_key(public_key).verify(_b64(value["signature"]), COMMITMENT_DOMAIN + canonical_json_bytes(statement))
    except (InvalidSignature, ValueError, TypeError) as exc: raise Type1FreshCustodyError("commitment signature verification failed") from exc
    return Commitment(raw, statement, commitment_digest(statement))


class Type1FreshCustodyLedger:
    """SQLite WAL/FULL, append-only, identity-bound local custody metadata."""
    def __init__(self, database: str | Path, *, dataset_id: str, custody_uid: str, prereg_sha256: str,
        calendar: Sequence[tuple[str, str]], authority_principal_uri: str, authority_key_id: str,
        authority_public_key: bytes | Ed25519PublicKey, protocol_sha256: str) -> None:
        for value, label in ((prereg_sha256, "prereg_sha256"), (protocol_sha256, "protocol_sha256")): _hash(value, label)
        if not all(isinstance(x, str) and x for x in (dataset_id, custody_uid, authority_principal_uri, authority_key_id)): raise ValueError("empty custody identity")
        self.database, self.dataset_id, self.custody_uid, self.prereg_sha256 = str(database), dataset_id, custody_uid, prereg_sha256
        self.calendar, self.authority_principal_uri, self.authority_key_id = tuple(calendar), authority_principal_uri, authority_key_id
        self.authority_public_key, self.protocol_sha256 = authority_public_key, protocol_sha256
        self._validate_calendar(); self._initialize(); self._verify_storage()

    def reconcile_ordinal(self, authority: MetadataAuthority, ordinal: int) -> bytes | None:
        self._assert_healthy(); _positive_int(ordinal, "ordinal")
        try: raw = authority.commitment(ordinal)
        except AuthorityUnavailable: return None
        if raw is None: return None
        try:
            commitment = parse_and_verify_commitment_envelope(raw, expected_dataset_id=self.dataset_id, expected_custody_uid=self.custody_uid, expected_prereg_sha256=self.prereg_sha256, expected_principal_uri=self.authority_principal_uri, expected_key_id=self.authority_key_id, public_key=self.authority_public_key)
            if commitment.statement["ordinal"] != ordinal or tuple(commitment.statement[x] for x in ("decision_session", "settlement_session")) != self.calendar[ordinal - 1]: raise Type1FreshCustodyError("calendar proof differs from signed authority input")
            prior = self._commitment_digest(ordinal - 1) if ordinal > 1 else GENESIS_COMMITMENT_SHA256
            if commitment.statement["previous_commitment_sha256"] != prior: raise Type1FreshCustodyError("commitment predecessor differs")
            old = self._commitment(ordinal)
            if old:
                if old[0] != commitment.digest or old[1] != raw: raise Type1FreshCustodyError("conflicting ordinal")
                return old[2]
            if ordinal != self._commitment_count() + 1: raise Type1FreshCustodyError("commitments must be contiguous")
            receipt = canonical_json_bytes({"schema_version": EVENT_SCHEMA, "ordinal": ordinal, "commitment_sha256": commitment.digest})
            with self._transaction() as db:
                db.execute("INSERT INTO commitments(ordinal,digest,envelope,receipt) VALUES(?,?,?,?)", (ordinal, commitment.digest, raw, receipt)); self._append_event(db, "COMMITMENT_RECORDED", ordinal, commitment.digest, commitment.digest, "AUTHENTICATED")
            return receipt
        except (Type1FreshCustodyError, IndexError): self._block(authority, "COMMITMENT_CONFLICT_OR_INVALID")

    def seal(self, authority: MetadataAuthority) -> bytes:
        self._assert_healthy()
        if self._sealed(): return self._seal_bytes()
        if self._commitment_count() != len(self.calendar) or len(self.calendar) < 120: raise Type1FreshCustodyError("complete calendar required")
        tip = self._commitment_digest(len(self.calendar))
        try:
            facts = authority.key_enable(self.custody_uid, tip); _keys(facts, {"key_id","key_enable_receipt_sha256","access_ledger_genesis_sha256","rfc3161_receipt_sha256"}, "seal facts")
            if not isinstance(facts["key_id"], str) or not facts["key_id"]: raise Type1FreshCustodyError("invalid key identity")
            for item in ("key_enable_receipt_sha256","access_ledger_genesis_sha256","rfc3161_receipt_sha256"): _hash(facts[item], item)
            if authority.access_snapshot(self.custody_uid, tip) != {"state":"UNUSED"}: raise Type1FreshCustodyError("access state invalid")
        except AuthorityUnavailable: raise
        except (Type1FreshCustodyError, KeyError, TypeError): self._block(authority, "SEAL_PREREQUISITE_INVALID")
        seal = {"schema_version":SEAL_SCHEMA,"dataset_id":self.dataset_id,"custody_uid":self.custody_uid,"prereg_sha256":self.prereg_sha256,"freeze_start":FRESH_OOS_START_DATE,"decision_end":self.calendar[-1][0],"freeze_end":FRESH_OOS_END_DATE,"pair_count":len(self.calendar),"first_ordinal":1,"last_ordinal":len(self.calendar),"commitment_tip_sha256":tip,"commitment_merkle_root_sha256":self._merkle_root(),"ledger_tip_sha256":self._tip(),"key_id":facts["key_id"],"key_enable_receipt_sha256":facts["key_enable_receipt_sha256"],"access_ledger_genesis_sha256":facts["access_ledger_genesis_sha256"],"key_state":"ENABLED","access_state":"UNUSED","deny_state":"ABSENT","fresh_oos_status":"NOT_RUN"}
        raw = canonical_json_bytes(seal); digest = _domain_digest("seal", raw)
        # The sidecar is create-new and fsynced: an existing nonmatching final record is fatal.
        sidecar = self.database + ".seal"
        try:
            fd = os.open(sidecar, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as out: out.write(raw); out.flush(); os.fsync(out.fileno())
        except FileExistsError:
            self._block(authority, "FINAL_SEAL_CONFLICT")
        with self._transaction() as db:
            db.execute("INSERT INTO seals(singleton,seal,digest) VALUES(1,?,?)", (raw,digest)); self._append_event(db,"SEALED",None,tip,digest,"HEALTHY_SEAL")
        return raw

    def record_gate_receipt(self, raw: bytes) -> bytes:
        """Accept only an authority-signed, seal/evidence-bound gate receipt."""
        self._assert_healthy()
        value = _canonical_object(raw, "gate receipt"); _keys(value, {"schema_version","statement","signature"}, "gate receipt")
        statement = value["statement"]
        if value["schema_version"] != GATE_RECEIPT_SCHEMA or not isinstance(statement, dict): raise Type1FreshCustodyError("invalid gate receipt")
        _keys(statement, {"schema_version","dataset_id","custody_uid","prereg_sha256","seal_sha256","commitment_sha256","authority_principal_uri","authority_key_id"}, "gate statement")
        if (statement["schema_version"],statement["dataset_id"],statement["custody_uid"],statement["prereg_sha256"],statement["authority_principal_uri"],statement["authority_key_id"]) != (GATE_RECEIPT_SCHEMA,self.dataset_id,self.custody_uid,self.prereg_sha256,self.authority_principal_uri,self.authority_key_id): raise Type1FreshCustodyError("gate identity mismatch")
        for item in ("seal_sha256","commitment_sha256"): _hash(statement[item], item)
        if statement["seal_sha256"] != hashlib.sha256(self._seal_bytes()).hexdigest(): raise Type1FreshCustodyError("gate seal mismatch")
        try: _public_key(self.authority_public_key).verify(_b64(value["signature"]), HASH_DOMAINS["gate"] + canonical_json_bytes(statement))
        except (InvalidSignature, ValueError, TypeError) as exc: raise Type1FreshCustodyError("gate signature invalid") from exc
        digest = _domain_digest("gate", canonical_json_bytes(statement)); old = self._setting("gate_receipt_sha256")
        if old:
            if old != digest: raise Type1FreshCustodyError("gate replacement forbidden")
            return raw
        with self._transaction() as db: db.execute("INSERT INTO settings(name,value) VALUES('gate_receipt_sha256',?)",(digest,)); self._append_event(db,"GATE_RECORDED",None,statement["commitment_sha256"],digest,"SIGNED_GATE")
        return raw

    def recover(self, authority: MetadataAuthority) -> bytes | None:
        self._assert_integrity()
        if not self._sealed() or self._blocked(): return None
        prior = self._failure_receipt()
        if prior: return prior
        seal_sha = hashlib.sha256(self._seal_bytes()).hexdigest()
        try: snapshot = authority.access_snapshot(self.custody_uid, seal_sha)
        except AuthorityUnavailable: return None
        if snapshot == {"state":"UNUSED"}: return None
        if not isinstance(snapshot, Mapping) or snapshot.get("state") not in {"RESERVED","CONSUMED"}: self._block(authority,"ACCESS_AUTHORITY_INVALID")
        receipt_sha = snapshot.get("receipt_sha256")
        if snapshot.get("state") == "RESERVED": _hash(receipt_sha,"reservation receipt")
        with self._transaction() as db:
            if not self._setting("recovery_intent"):
                db.execute("INSERT INTO settings(name,value) VALUES('recovery_intent',?)",(seal_sha,)); self._append_event(db,"RECOVERY_INTENT",None,None,receipt_sha if isinstance(receipt_sha,str) else None,"POST_RESERVED_RECOVERY")
        # Intent is now durable before either external effect.  Calls are required idempotent authority operations.
        try:
            disabled = authority.key_disable(self.custody_uid,"POST_RESERVED_RECOVERY"); _hash(disabled["receipt_sha256"],"disable receipt")
            with self._transaction() as db:
                if not self._setting("disable_receipt_sha256"): db.execute("INSERT INTO settings(name,value) VALUES('disable_receipt_sha256',?)",(disabled["receipt_sha256"],)); self._append_event(db,"KEY_DISABLED",None,None,disabled["receipt_sha256"],"POST_RESERVED_RECOVERY")
            consumed = authority.consume_observed(self.custody_uid,seal_sha,"POST_RESERVED_RECOVERY"); _hash(consumed["receipt_sha256"],"consumed receipt")
        except (AuthorityUnavailable, KeyError, TypeError, Type1FreshCustodyError) as exc: raise Type1FreshCustodyError("recovery remains pending") from exc
        failure={"schema_version":FAILURE_RECEIPT_SCHEMA,"custody_uid":self.custody_uid,"seal_sha256":seal_sha,"reservation_receipt_sha256":receipt_sha,"consumed_receipt_sha256":consumed["receipt_sha256"],"key_disable_receipt_sha256":disabled["receipt_sha256"],"reason":"POST_RESERVED_RECOVERY","retry_allowed":False}
        raw=canonical_json_bytes(failure)
        with self._transaction() as db: db.execute("INSERT INTO failures(singleton,receipt) VALUES(1,?)",(raw,)); self._append_event(db,"CONSUMED_RECOVERY",None,None,consumed["receipt_sha256"],"POST_RESERVED_RECOVERY")
        return raw

    def status(self) -> Mapping[str, Any]:
        self._assert_integrity(); blocked=self._blocked(); blocking=self._blocking(); failure=self._failure_receipt() is not None; sealed=self._sealed(); pending=self._setting("recovery_intent") is not None and not failure
        if blocked: state, public, key, access, deny="BLOCKED","BLOCKED_NOT_RUN","DISABLED","UNUSED","ISSUED"
        elif blocking: state, public, key, access, deny="BLOCK_RECOVERY","RECOVERY_REQUIRED_NOT_RUN","DISABLED","UNKNOWN","PENDING"
        elif pending: state, public, key, access, deny="RECOVERY_PENDING","RECOVERY_REQUIRED_NOT_RUN","DISABLED","UNKNOWN","ABSENT"
        elif failure: state, public, key, access, deny="SEALED","CONSUMED_NOT_RUN","DISABLED","CONSUMED","ABSENT"
        elif sealed: state, public, key, access, deny="SEALED","SEALED_NOT_RUN","ENABLED","UNUSED","ABSENT"
        else: state, public, key, access, deny="ACCUMULATING","ACCUMULATING_NOT_RUN","UNAVAILABLE","UNUSED","ABSENT"
        return {"schema_version":STATUS_SCHEMA,"dataset_id":self.dataset_id,"custody_uid":self.custody_uid,"prereg_sha256":self.prereg_sha256,"expected_pair_count":len(self.calendar),"committed_pair_count":self._commitment_count(),"custody_state":state,"authority_state":"AVAILABLE" if sealed else "ABSENT","key_state":key,"gate_receipt_state":"ISSUED" if self._setting("gate_receipt_sha256") else "ABSENT","access_state":access,"deny_state":deny,"fresh_oos_status":"NOT_RUN","public_status":public,"recovery_state":"COMPLETE" if failure else ("PENDING" if pending or blocking else "NONE"),"reason_code":self._setting("reason_code") or "NONE"}

    def verify_chain(self) -> None:
        db=self._connection()
        try: rows=db.execute("SELECT sequence,event,digest,previous_digest FROM events ORDER BY sequence").fetchall()
        finally: db.close()
        previous=GENESIS_COMMITMENT_SHA256
        for sequence, raw, digest, stored_previous in rows:
            if stored_previous != previous or digest != _domain_digest("event", raw): raise Type1FreshCustodyError("event hash chain is tampered")
            event=_canonical_object(raw,"ledger event")
            if event.get("sequence") != sequence or event.get("previous_event_sha256") != previous or (event.get("dataset_id"),event.get("custody_uid"),event.get("prereg_sha256")) != (self.dataset_id,self.custody_uid,self.prereg_sha256): raise Type1FreshCustodyError("event identity is tampered")
            previous=digest

    def _block(self, authority: MetadataAuthority, reason: str) -> None:
        if self._blocked(): raise CustodyBlocked("custody is terminally blocked")
        if not self._setting("block_intent"):
            with self._transaction() as db: db.execute("INSERT INTO settings(name,value) VALUES('block_intent',?)",(reason,)); db.execute("INSERT INTO settings(name,value) VALUES('reason_code',?)",(reason,)); self._append_event(db,"BLOCK_INTENT",None,None,None,reason)
        try: disabled=authority.key_disable(self.custody_uid,reason); _hash(disabled["receipt_sha256"],"disable receipt")
        except (AuthorityUnavailable, KeyError, TypeError, Type1FreshCustodyError) as exc: raise CustodyBlocked("block disable pending") from exc
        with self._transaction() as db:
            if not self._setting("block_disable_receipt"):
                db.execute("INSERT INTO settings(name,value) VALUES('block_disable_receipt',?)",(disabled["receipt_sha256"],)); self._append_event(db,"KEY_DISABLED",None,None,disabled["receipt_sha256"],reason); self._append_event(db,"BLOCKED",None,None,disabled["receipt_sha256"],reason)
        try: deny=authority.issue_deny(self.custody_uid,_domain_digest("block", self._tip().encode())); _hash(deny["receipt_sha256"],"deny receipt")
        except (AuthorityUnavailable, KeyError, TypeError, Type1FreshCustodyError) as exc: raise CustodyBlocked("deny receipt pending") from exc
        with self._transaction() as db:
            if not self._setting("deny_receipt"):
                db.execute("INSERT INTO settings(name,value) VALUES('deny_receipt',?)",(deny["receipt_sha256"],)); self._append_event(db,"DENY_RECORDED",None,None,deny["receipt_sha256"],reason)
        raise CustodyBlocked(reason)

    def _initialize(self) -> None:
        db=self._connection(); db.executescript("""CREATE TABLE IF NOT EXISTS events(sequence INTEGER PRIMARY KEY,event BLOB NOT NULL,digest TEXT NOT NULL UNIQUE,previous_digest TEXT NOT NULL);CREATE TABLE IF NOT EXISTS commitments(ordinal INTEGER PRIMARY KEY,digest TEXT NOT NULL UNIQUE,envelope BLOB NOT NULL UNIQUE,receipt BLOB NOT NULL);CREATE TABLE IF NOT EXISTS seals(singleton INTEGER PRIMARY KEY CHECK(singleton=1),seal BLOB NOT NULL,digest TEXT NOT NULL);CREATE TABLE IF NOT EXISTS failures(singleton INTEGER PRIMARY KEY CHECK(singleton=1),receipt BLOB NOT NULL);CREATE TABLE IF NOT EXISTS settings(name TEXT PRIMARY KEY,value TEXT NOT NULL);CREATE TABLE IF NOT EXISTS writer_locks(custody_uid TEXT PRIMARY KEY);""")
        for table in ("events","commitments","seals","failures","settings"):
            db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_update BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT,'append only'); END")
            db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT,'append only'); END")
        identity={"identity_dataset_id":self.dataset_id,"identity_custody_uid":self.custody_uid,"identity_prereg_sha256":self.prereg_sha256,"identity_protocol_sha256":self.protocol_sha256,"identity_principal_uri":self.authority_principal_uri,"identity_key_id":self.authority_key_id,"identity_calendar_sha256":hashlib.sha256(canonical_json_bytes(self.calendar)).hexdigest()}
        empty=db.execute("SELECT COUNT(*) FROM events").fetchone()[0]==0
        if not empty:
            stored=dict(db.execute("SELECT name,value FROM settings WHERE name LIKE 'identity_%'"))
            db.close()
            if stored != identity: raise Type1FreshCustodyError("stored custody identity or calendar differs")
            self.verify_chain()
            return
        db.close()
        with self._transaction() as tx:
            for name,value in identity.items(): tx.execute("INSERT INTO settings(name,value) VALUES(?,?)",(name,value))
            self._append_event(tx,"GENESIS",None,None,self.protocol_sha256,"INITIALIZED")

    def _connection(self) -> sqlite3.Connection:
        db=sqlite3.connect(self.database, timeout=30, isolation_level=None); db.execute("PRAGMA journal_mode=WAL"); db.execute("PRAGMA synchronous=FULL"); db.execute("PRAGMA foreign_keys=ON"); return db
    @contextmanager
    def _transaction(self):
        db=self._connection(); db.execute("BEGIN EXCLUSIVE")
        try:
            db.execute("INSERT INTO writer_locks(custody_uid) VALUES(?)",(self.custody_uid,)); yield db; db.execute("DELETE FROM writer_locks WHERE custody_uid=?",(self.custody_uid,)); db.commit()
        except BaseException: db.rollback(); raise
        finally: db.close()
    def _append_event(self,db:sqlite3.Connection,event_type:str,ordinal:int|None,commitment:str|None,receipt:str|None,reason:str)->None:
        prior=self._tip(db); seq=db.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM events").fetchone()[0]; event={"schema_version":EVENT_SCHEMA,"sequence":seq,"event_type":event_type,"dataset_id":self.dataset_id,"custody_uid":self.custody_uid,"prereg_sha256":self.prereg_sha256,"ordinal":ordinal,"commitment_sha256":commitment,"authority_receipt_sha256":receipt,"reason_code":reason,"previous_event_sha256":prior}; raw=canonical_json_bytes(event); db.execute("INSERT INTO events VALUES(?,?,?,?)",(seq,raw,_domain_digest("event",raw),prior))
    def _tip(self,db:sqlite3.Connection|None=None)->str:
        own=db is None; db=db or self._connection(); row=db.execute("SELECT digest FROM events ORDER BY sequence DESC LIMIT 1").fetchone();
        if own: db.close()
        return row[0] if row else GENESIS_COMMITMENT_SHA256
    def _commitment(self,ordinal:int):
        db=self._connection(); row=db.execute("SELECT digest,envelope,receipt FROM commitments WHERE ordinal=?",(ordinal,)).fetchone(); db.close(); return row
    def _commitment_digest(self,ordinal:int)->str:
        row=self._commitment(ordinal)
        if not row: raise Type1FreshCustodyError("missing commitment")
        return row[0]
    def _commitment_count(self)->int:
        db=self._connection(); n=db.execute("SELECT COUNT(*) FROM commitments").fetchone()[0]; db.close(); return n
    def _sealed(self)->bool:
        db=self._connection(); ok=db.execute("SELECT 1 FROM seals WHERE singleton=1").fetchone() is not None; db.close(); return ok
    def _seal_bytes(self)->bytes:
        db=self._connection(); row=db.execute("SELECT seal FROM seals WHERE singleton=1").fetchone(); db.close()
        if not row: raise Type1FreshCustodyError("seal is absent")
        return row[0]
    def _failure_receipt(self)->bytes|None:
        db=self._connection(); row=db.execute("SELECT receipt FROM failures WHERE singleton=1").fetchone(); db.close(); return row[0] if row else None
    def _setting(self,name:str)->str|None:
        db=self._connection(); row=db.execute("SELECT value FROM settings WHERE name=?",(name,)).fetchone(); db.close(); return row[0] if row else None
    def _blocked(self)->bool: return self._setting("deny_receipt") is not None
    def _blocking(self)->bool: return self._setting("block_intent") is not None and not self._blocked()
    def _assert_integrity(self)->None: self._verify_storage(); self.verify_chain()
    def _assert_healthy(self)->None:
        self._assert_integrity()
        if self._blocking() or self._blocked() or self._failure_receipt() is not None: raise CustodyBlocked("custody is terminally unavailable")
    def _verify_storage(self)->None:
        db=self._connection(); quick=db.execute("PRAGMA quick_check").fetchone()[0]; integrity=db.execute("PRAGMA integrity_check").fetchone()[0]; journal=db.execute("PRAGMA journal_mode").fetchone()[0]; sync=db.execute("PRAGMA synchronous").fetchone()[0]; db.close()
        if quick!="ok" or integrity!="ok" or journal.lower()!="wal" or sync != 2: raise Type1FreshCustodyError("SQLite custody profile invalid")
    def _merkle_root(self)->str:
        db=self._connection(); rows=db.execute("SELECT ordinal,digest FROM commitments ORDER BY ordinal").fetchall(); db.close(); leaves=[_domain_digest("merkle_leaf",int(o).to_bytes(8,"big"),_hex_bytes(d,"commitment digest")) for o,d in rows]
        if not leaves: raise Type1FreshCustodyError("empty commitment tree")
        while len(leaves)>1:
            if len(leaves)%2: leaves.append(leaves[-1])
            leaves=[_domain_digest("merkle_node",_hex_bytes(a,"merkle left"),_hex_bytes(b,"merkle right")) for a,b in zip(leaves[::2],leaves[1::2])]
        return leaves[0]
    def _validate_calendar(self)->None:
        if len(self.calendar)<120 or self.calendar[0][0]!=FRESH_OOS_START_DATE or self.calendar[-1][1]!=FRESH_OOS_END_DATE: raise ValueError("calendar must cover frozen window")
        last=None
        for decision,settlement in self.calendar:
            d,s=_iso_date(decision,"decision"),_iso_date(settlement,"settlement")
            if d>=s or (last and d<=last): raise ValueError("calendar must be ordered pairs")
            last=s


def _canonical_object(raw:bytes,label:str)->dict[str,Any]:
    if not isinstance(raw,bytes): raise Type1FreshCustodyError(f"{label} must be bytes")
    try: value=json.loads(raw)
    except (UnicodeDecodeError,json.JSONDecodeError) as exc: raise Type1FreshCustodyError(f"{label} is not JSON") from exc
    if not isinstance(value,dict) or canonical_json_bytes(value)!=raw: raise Type1FreshCustodyError(f"{label} is not canonical JSON")
    return value
def _keys(value:Mapping[str,Any],expected:set[str],label:str)->None:
    if set(value)!=expected: raise Type1FreshCustodyError(f"{label} has missing or unknown fields")
def _hash(value:Any,label:str)->None:
    if not isinstance(value,str) or len(value)!=64 or any(c not in "0123456789abcdef" for c in value): raise Type1FreshCustodyError(f"{label} must be lower-case SHA-256")
def _positive_int(value:Any,label:str)->None:
    if type(value) is not int or value<1: raise Type1FreshCustodyError(f"{label} must be positive")
def _iso_date(value:Any,label:str)->date:
    if not isinstance(value,str): raise Type1FreshCustodyError(f"{label} must be ISO date")
    try: return date.fromisoformat(value)
    except ValueError as exc: raise Type1FreshCustodyError(f"{label} must be ISO date") from exc
def _b64(value:str)->bytes:
    if not isinstance(value,str) or "=" in value: raise Type1FreshCustodyError("signature is not canonical base64url")
    try: decoded=base64.urlsafe_b64decode(value+"="*(-len(value)%4))
    except (ValueError,UnicodeEncodeError) as exc: raise Type1FreshCustodyError("signature is not base64url") from exc
    if len(decoded)!=64 or base64.urlsafe_b64encode(decoded).decode().rstrip("=")!=value: raise Type1FreshCustodyError("signature is not canonical base64url")
    return decoded
def _public_key(value:bytes|Ed25519PublicKey)->Ed25519PublicKey:
    if isinstance(value,Ed25519PublicKey): return value
    if isinstance(value,bytes) and len(value)==32: return Ed25519PublicKey.from_public_bytes(value)
    raise Type1FreshCustodyError("authority public key must be 32 bytes")
