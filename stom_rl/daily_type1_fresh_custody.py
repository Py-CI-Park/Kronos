"""Metadata-only, crash-resumable custody ledger for the frozen Type1 window."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from stom_rl.daily_type1_contract import FRESH_OOS_END_DATE, FRESH_OOS_START_DATE, canonical_json_bytes

COMMITMENT_ENVELOPE_SCHEMA="kronos_type1_fresh_commitment_envelope.v1"
EVENT_SCHEMA="kronos_type1_fresh_custody_event.v1"
SEAL_SCHEMA="kronos_type1_fresh_custody_seal.v1"
STATUS_SCHEMA="kronos_type1_fresh_custody_status.v1"
FAILURE_RECEIPT_SCHEMA="kronos_type1_fresh_custody_failure_receipt.v1"
GATE_RECEIPT_SCHEMA="kronos_type1_fresh_gate_receipt.v1"
GENESIS_COMMITMENT_SHA256="4127aeb0"+("0"*52)+"2301"
HASH_DOMAINS={"commitment":b"KRONOS-TYPE1-COMMITMENT-V1\x00","merkle_leaf":b"KRONOS-TYPE1-MERKLE-LEAF-V1\x00","merkle_node":b"KRONOS-TYPE1-MERKLE-NODE-V1\x00","event":b"KRONOS-TYPE1-EVENT-V1\x00","seal":b"KRONOS-TYPE1-SEAL-V1\x00","block":b"KRONOS-TYPE1-BLOCK-V1\x00","gate":b"KRONOS-TYPE1-GATE-V1\x00","access_ledger":b"KRONOS-TYPE1-ACCESS-LEDGER-V1\x00"}
COMMITMENT_DOMAIN=HASH_DOMAINS["commitment"]

class Type1FreshCustodyError(RuntimeError): pass
class AuthorityUnavailable(Type1FreshCustodyError): pass
class CustodyBlocked(Type1FreshCustodyError): pass

class MetadataAuthority(Protocol):
    def commitment(self, ordinal:int)->bytes|None: ...
    def key_enable(self, access_ledger_id:str, seal_sha256:str)->Mapping[str,Any]: ...
    def key_disable(self, access_ledger_id:str, reason:str)->Mapping[str,Any]: ...
    def access_snapshot(self, access_ledger_id:str, seal_sha256:str)->Mapping[str,Any]: ...
    def consume_observed(self, access_ledger_id:str, seal_sha256:str, reason:str)->Mapping[str,Any]: ...
    def issue_deny(self, access_ledger_id:str, block_event_sha256:str)->Mapping[str,Any]: ...

@dataclass(frozen=True)
class Commitment:
    canonical:bytes
    statement:Mapping[str,Any]
    digest:str

def _domain_digest(domain:str,*parts:bytes)->str:
    if domain not in HASH_DOMAINS: raise Type1FreshCustodyError("unknown hash domain")
    h=hashlib.sha256(HASH_DOMAINS[domain])
    for part in parts: h.update(len(part).to_bytes(8,"big")); h.update(part)
    return h.hexdigest()
def _hash(value:Any,label:str)->None:
    if not isinstance(value,str) or len(value)!=64 or any(c not in "0123456789abcdef" for c in value): raise Type1FreshCustodyError(f"{label} must be lower-case SHA-256")
def _hex_bytes(value:str,label:str)->bytes: _hash(value,label); return bytes.fromhex(value)
def _positive_int(value:Any,label:str)->None:
    if type(value) is not int or value<1: raise Type1FreshCustodyError(f"{label} must be positive")
def _iso_date(value:Any,label:str)->date:
    if not isinstance(value,str): raise Type1FreshCustodyError(f"{label} must be ISO date")
    try: return date.fromisoformat(value)
    except ValueError as exc: raise Type1FreshCustodyError(f"{label} must be ISO date") from exc
def _canonical_object(raw:bytes,label:str)->dict[str,Any]:
    if not isinstance(raw,bytes): raise Type1FreshCustodyError(f"{label} must be bytes")
    try: value=json.loads(raw)
    except (UnicodeDecodeError,json.JSONDecodeError) as exc: raise Type1FreshCustodyError(f"{label} is not JSON") from exc
    if not isinstance(value,dict) or canonical_json_bytes(value)!=raw: raise Type1FreshCustodyError(f"{label} is not canonical JSON")
    return value
def _keys(value:Mapping[str,Any],expected:set[str],label:str)->None:
    if set(value)!=expected: raise Type1FreshCustodyError(f"{label} has missing or unknown fields")
def _b64(value:str)->bytes:
    if not isinstance(value,str) or "=" in value: raise Type1FreshCustodyError("signature is not canonical base64url")
    try: result=base64.urlsafe_b64decode(value+"="*(-len(value)%4))
    except (ValueError,UnicodeEncodeError) as exc: raise Type1FreshCustodyError("signature is not base64url") from exc
    if len(result)!=64 or base64.urlsafe_b64encode(result).decode().rstrip("=")!=value: raise Type1FreshCustodyError("signature is not canonical base64url")
    return result
def _public_key(value:bytes|Ed25519PublicKey)->Ed25519PublicKey:
    if isinstance(value,Ed25519PublicKey): return value
    if isinstance(value,bytes) and len(value)==32: return Ed25519PublicKey.from_public_bytes(value)
    raise Type1FreshCustodyError("authority public key must be 32 bytes")
def commitment_digest(statement:Mapping[str,Any])->str:
    _positive_int(statement.get("ordinal"),"ordinal")
    return _domain_digest("commitment",statement["ordinal"].to_bytes(8,"big"),canonical_json_bytes(statement))
def parse_and_verify_commitment_envelope(raw:bytes,*,expected_dataset_id:str,expected_custody_uid:str,expected_prereg_sha256:str,expected_principal_uri:str,expected_key_id:str,public_key:bytes|Ed25519PublicKey)->Commitment:
    value=_canonical_object(raw,"commitment envelope"); _keys(value,{"schema_version","statement","signature"},"commitment envelope")
    statement=value["statement"]
    fields={"schema_version","dataset_id","custody_uid","prereg_sha256","ordinal","decision_session","settlement_session","ciphertext_sha256","ciphertext_byte_length","previous_commitment_sha256","authority_principal_uri","authority_key_id"}
    if value["schema_version"]!=COMMITMENT_ENVELOPE_SCHEMA or not isinstance(statement,dict): raise Type1FreshCustodyError("invalid commitment envelope")
    _keys(statement,fields,"commitment statement")
    if (statement["schema_version"],statement["dataset_id"],statement["custody_uid"],statement["prereg_sha256"],statement["authority_principal_uri"],statement["authority_key_id"]) != (COMMITMENT_ENVELOPE_SCHEMA,expected_dataset_id,expected_custody_uid,expected_prereg_sha256,expected_principal_uri,expected_key_id): raise Type1FreshCustodyError("commitment identity does not match custody")
    _positive_int(statement["ordinal"],"ordinal"); _iso_date(statement["decision_session"],"decision_session"); _iso_date(statement["settlement_session"],"settlement_session")
    for item in ("prereg_sha256","ciphertext_sha256","previous_commitment_sha256"): _hash(statement[item],item)
    if type(statement["ciphertext_byte_length"]) is not int or statement["ciphertext_byte_length"]<0: raise Type1FreshCustodyError("invalid ciphertext length")
    try: _public_key(public_key).verify(_b64(value["signature"]),COMMITMENT_DOMAIN+canonical_json_bytes(statement))
    except (InvalidSignature,ValueError,TypeError) as exc: raise Type1FreshCustodyError("commitment signature verification failed") from exc
    return Commitment(raw,statement,commitment_digest(statement))

class Type1FreshCustodyLedger:
    """Append-only SQLite state machine. Authority calls are idempotency-keyed."""
    _settings={"identity_dataset_id","identity_custody_uid","identity_prereg_sha256","identity_protocol_sha256","identity_principal_uri","identity_key_id","identity_public_key_sha256","identity_calendar_sha256","seal_intent","key_enabled","sidecar_published","recovery_intent","key_disabled_recovery","consumed","failure_final","block_intent","key_disabled_block","denied","reason_code","gate_receipt"}
    def __init__(self,database:str|Path,*,dataset_id:str,custody_uid:str,prereg_sha256:str,calendar:Sequence[tuple[str,str]],authority_principal_uri:str,authority_key_id:str,authority_public_key:bytes|Ed25519PublicKey,protocol_sha256:str)->None:
        _hash(prereg_sha256,"prereg_sha256"); _hash(protocol_sha256,"protocol_sha256")
        if not all(isinstance(x,str) and x for x in (dataset_id,custody_uid,authority_principal_uri,authority_key_id)): raise ValueError("empty custody identity")
        self.database=str(database); self.dataset_id=dataset_id; self.custody_uid=custody_uid; self.prereg_sha256=prereg_sha256; self.calendar=tuple(calendar); self.authority_principal_uri=authority_principal_uri; self.authority_key_id=authority_key_id; self.authority_public_key=_public_key(authority_public_key); self.protocol_sha256=protocol_sha256
        self._validate_calendar(); self._initialize(); self._verify_full()
    def reconcile_ordinal(self,authority:MetadataAuthority,ordinal:int)->bytes|None:
        self._resume_block(authority)
        self._assert_healthy(); _positive_int(ordinal,"ordinal")
        try: raw=authority.commitment(ordinal)
        except AuthorityUnavailable: return None
        if raw is None: return None
        try:
            item=parse_and_verify_commitment_envelope(raw,expected_dataset_id=self.dataset_id,expected_custody_uid=self.custody_uid,expected_prereg_sha256=self.prereg_sha256,expected_principal_uri=self.authority_principal_uri,expected_key_id=self.authority_key_id,public_key=self.authority_public_key)
            if item.statement["ordinal"]!=ordinal or tuple(item.statement[x] for x in ("decision_session","settlement_session"))!=self.calendar[ordinal-1]: raise Type1FreshCustodyError("calendar proof differs from signed authority input")
            receipt=canonical_json_bytes({"schema_version":EVENT_SCHEMA,"ordinal":ordinal,"commitment_sha256":item.digest})
            with self._transaction() as db:
                old=db.execute("SELECT digest,envelope,receipt FROM commitments WHERE ordinal=?",(ordinal,)).fetchone()
                if old:
                    if old[0]!=item.digest or old[1]!=raw: raise Type1FreshCustodyError("conflicting ordinal")
                    return old[2]
                count=db.execute("SELECT COUNT(*) FROM commitments").fetchone()[0]
                if ordinal!=count+1: raise Type1FreshCustodyError("commitments must be contiguous")
                prior=GENESIS_COMMITMENT_SHA256 if ordinal==1 else db.execute("SELECT digest FROM commitments WHERE ordinal=?",(ordinal-1,)).fetchone()[0]
                if item.statement["previous_commitment_sha256"]!=prior: raise Type1FreshCustodyError("commitment predecessor differs")
                db.execute("INSERT INTO commitments VALUES(?,?,?,?)",(ordinal,item.digest,raw,receipt)); self._append_event(db,"COMMITMENT_RECORDED",ordinal,item.digest,item.digest,"AUTHENTICATED")
            return receipt
        except (Type1FreshCustodyError,IndexError): self._block(authority,"COMMITMENT_CONFLICT_OR_INVALID")
    def seal(self,authority:MetadataAuthority)->bytes:
        self._resume_block(authority)
        self._assert_healthy()
        if self._phase("sidecar_published") and self._sidecar_matches(): return self._finalize_seal()
        if self._commitment_count()!=len(self.calendar): raise Type1FreshCustodyError("complete calendar required")
        tip=self._commitment_digest(len(self.calendar)); access_id=self._access_ledger_id(tip)
        intent={"access_ledger_id":access_id,"commitment_tip_sha256":tip,"calendar_sha256":self._calendar_sha(),"authority_key_id":self.authority_key_id,"authority_public_key_sha256":self._key_fingerprint()}
        self._set_phase("seal_intent",intent,"SEAL_INTENT",tip,None,"PRESEAL")
        enabled=self._phase_json("key_enabled")
        if enabled is None:
            facts=authority.key_enable(access_id,tip); enabled=self._enable_facts(facts,access_id)
            self._set_phase("key_enabled",enabled,"KEY_ENABLED",tip,enabled["key_enable_receipt_sha256"],"PRESEAL")
        seal=self._seal_record(intent,enabled); raw=canonical_json_bytes(seal); digest=_domain_digest("seal",raw)
        if not self._phase("sidecar_published"):
            self._publish_sidecar(raw,authority)
            self._set_phase("sidecar_published",{"seal_sha256":hashlib.sha256(raw).hexdigest(),"seal_domain_sha256":digest},"SIDECAR_PUBLISHED",tip,digest,"PRESEAL")
        return self._finalize_seal()
    def recover(self,authority:MetadataAuthority)->bytes|None:
        self._resume_block(authority)
        self._assert_integrity()
        if not self._sealed() or self._blocked(): return None
        final=self._failure_receipt()
        if final: return final
        seal_sha=hashlib.sha256(self._seal_bytes()).hexdigest(); access_id=self._sealed_access_id()
        try: snap=authority.access_snapshot(access_id,seal_sha)
        except AuthorityUnavailable: return None
        if not isinstance(snap,Mapping) or snap.get("state") not in {"UNUSED","RESERVED","CONSUMED"}: self._block(authority,"ACCESS_AUTHORITY_INVALID")
        if snap["state"]=="UNUSED" and not self._phase("recovery_intent"): return None
        reservation=snap.get("receipt_sha256")
        if snap["state"]=="RESERVED": _hash(reservation,"reservation receipt")
        self._set_phase("recovery_intent",{"access_ledger_id":access_id,"seal_sha256":seal_sha,"reservation_receipt_sha256":reservation},"RECOVERY_INTENT",None,reservation if isinstance(reservation,str) else None,"POST_RESERVED_RECOVERY")
        disabled=self._phase_json("key_disabled_recovery")
        if disabled is None:
            try: result=authority.key_disable(access_id,"POST_RESERVED_RECOVERY")
            except AuthorityUnavailable as exc: raise Type1FreshCustodyError("key disable recovery pending") from exc
            disabled=self._receipt_result(result,"disable")
            self._set_phase("key_disabled_recovery",disabled,"KEY_DISABLED",None,disabled["receipt_sha256"],"POST_RESERVED_RECOVERY")
        consumed=self._phase_json("consumed")
        if consumed is None:
            if snap["state"]=="CONSUMED":
                if not isinstance(snap.get("receipt_sha256"),str): raise Type1FreshCustodyError("consumed snapshot receipt missing")
                consumed={"receipt_sha256":snap["receipt_sha256"]}
            else:
                try: result=authority.consume_observed(access_id,seal_sha,"POST_RESERVED_RECOVERY")
                except AuthorityUnavailable as exc: raise Type1FreshCustodyError("consume recovery pending") from exc
                consumed=self._receipt_result(result,"consume")
            self._set_phase("consumed",consumed,"CONSUMED",None,consumed["receipt_sha256"],"POST_RESERVED_RECOVERY")
        failure={"schema_version":FAILURE_RECEIPT_SCHEMA,"custody_uid":self.custody_uid,"access_ledger_id":access_id,"seal_sha256":seal_sha,"reservation_receipt_sha256":reservation,"consumed_receipt_sha256":consumed["receipt_sha256"],"key_disable_receipt_sha256":disabled["receipt_sha256"],"reason":"POST_RESERVED_RECOVERY","retry_allowed":False}
        raw=canonical_json_bytes(failure)
        if not self._phase("failure_final"):
            with self._transaction() as db:
                db.execute("INSERT INTO failures VALUES(1,?)",(raw,)); self._put(db,"failure_final",{"failure_sha256":hashlib.sha256(raw).hexdigest()}); self._append_event(db,"FAILURE_FINAL",None,None,consumed["receipt_sha256"],"POST_RESERVED_RECOVERY")
        return self._failure_receipt()
    def record_gate_receipt(self,raw:bytes)->bytes:
        self._assert_healthy(); value=_canonical_object(raw,"gate receipt"); _keys(value,{"schema_version","statement","signature"},"gate receipt"); statement=value["statement"]
        fields={"schema_version","dataset_id","custody_uid","prereg_sha256","seal_sha256","commitment_sha256","authority_principal_uri","authority_key_id"}
        if value["schema_version"]!=GATE_RECEIPT_SCHEMA or not isinstance(statement,dict): raise Type1FreshCustodyError("invalid gate receipt")
        _keys(statement,fields,"gate statement")
        if tuple(statement[x] for x in ("schema_version","dataset_id","custody_uid","prereg_sha256","authority_principal_uri","authority_key_id")) != (GATE_RECEIPT_SCHEMA,self.dataset_id,self.custody_uid,self.prereg_sha256,self.authority_principal_uri,self.authority_key_id): raise Type1FreshCustodyError("gate identity mismatch")
        for x in ("seal_sha256","commitment_sha256"): _hash(statement[x],x)
        if statement["seal_sha256"]!=hashlib.sha256(self._seal_bytes()).hexdigest(): raise Type1FreshCustodyError("gate seal mismatch")
        try: self.authority_public_key.verify(_b64(value["signature"]),HASH_DOMAINS["gate"]+canonical_json_bytes(statement))
        except (InvalidSignature,ValueError,TypeError) as exc: raise Type1FreshCustodyError("gate signature invalid") from exc
        digest=_domain_digest("gate",canonical_json_bytes(statement)); current=self._phase_json("gate_receipt")
        if current:
            if current["digest"]!=digest: raise Type1FreshCustodyError("gate replacement forbidden")
            return raw
        self._set_phase("gate_receipt",{"digest":digest,"raw_b64":base64.b64encode(raw).decode()},"GATE_RECORDED",None,digest,"SIGNED_GATE"); return raw
    def status(self)->Mapping[str,Any]:
        self._assert_integrity(); blocked=self._blocked(); blocking=self._phase("block_intent") and not blocked; pending=self._phase("recovery_intent") and not self._phase("failure_final")
        if blocked: state,public,key,access,deny="BLOCKED","BLOCKED_NOT_RUN","DISABLED","UNKNOWN","ISSUED"
        elif blocking: state,public,key,access,deny="BLOCK_RECOVERY","RECOVERY_REQUIRED_NOT_RUN","UNKNOWN","UNKNOWN","PENDING"
        elif pending: state,public,key,access,deny="RECOVERY_PENDING","RECOVERY_REQUIRED_NOT_RUN","DISABLED" if self._phase("key_disabled_recovery") else "UNKNOWN","UNKNOWN","ABSENT"
        elif self._phase("failure_final"): state,public,key,access,deny="SEALED","CONSUMED_NOT_RUN","DISABLED","CONSUMED","ABSENT"
        elif self._sealed(): state,public,key,access,deny="SEALED","SEALED_NOT_RUN","ENABLED","UNUSED","ABSENT"
        else: state,public,key,access,deny="ACCUMULATING","ACCUMULATING_NOT_RUN","UNAVAILABLE","UNKNOWN","ABSENT"
        return {"schema_version":STATUS_SCHEMA,"dataset_id":self.dataset_id,"custody_uid":self.custody_uid,"prereg_sha256":self.prereg_sha256,"expected_pair_count":len(self.calendar),"committed_pair_count":self._commitment_count(),"custody_state":state,"authority_state":"AVAILABLE" if self._sealed() else "ABSENT","key_state":key,"gate_receipt_state":"ISSUED" if self._phase("gate_receipt") else "ABSENT","access_state":access,"deny_state":deny,"fresh_oos_status":"NOT_RUN","public_status":public,"recovery_state":"COMPLETE" if self._phase("failure_final") else ("PENDING" if pending or blocking else "NONE"),"reason_code":self._setting("reason_code") or "NONE"}
    def _resume_block(self,authority:MetadataAuthority)->None:
        intent=self._phase_json("block_intent")
        if intent is not None:
            if set(intent)!={"reason"} or not isinstance(intent["reason"],str) or not intent["reason"]:
                raise Type1FreshCustodyError("block intent is invalid")
            self._block(authority,intent["reason"])

    def _block(self,authority:MetadataAuthority,reason:str)->None:
        intent=self._phase_json("block_intent")
        if intent is None:
            self._set_phase("block_intent",{"reason":reason},"BLOCK_INTENT",None,None,reason)
        elif intent != {"reason":reason}:
            raise Type1FreshCustodyError("block reason differs")
        access_id=self._sealed_access_id_or_pending()
        disabled=self._phase_json("key_disabled_block")
        if disabled is None:
            disabled=self._receipt_result(authority.key_disable(access_id,reason),"disable")
            self._set_phase("key_disabled_block",disabled,"KEY_DISABLED",None,disabled["receipt_sha256"],reason)
        if not self._phase("denied"):
            denied=self._receipt_result(authority.issue_deny(access_id,_domain_digest("block",self._tip().encode())),"deny")
            self._set_phase("denied",denied,"DENIED",None,denied["receipt_sha256"],reason)
        raise CustodyBlocked(reason)
    def _enable_facts(self,facts:Mapping[str,Any],access_id:str)->dict[str,Any]:
        required={"access_ledger_id","key_id","authority_public_key_sha256","key_enable_receipt_sha256","access_ledger_genesis_sha256","rfc3161_receipt_sha256","key_enable_receipt","rfc3161_receipt"}
        if not isinstance(facts,Mapping) or set(facts)!=required: raise Type1FreshCustodyError("seal facts have missing or unknown fields")
        if facts["access_ledger_id"]!=access_id or facts["key_id"]!=self.authority_key_id or facts["authority_public_key_sha256"]!=self._key_fingerprint(): raise Type1FreshCustodyError("key authority identity mismatch")
        for x in ("key_enable_receipt_sha256","access_ledger_genesis_sha256","rfc3161_receipt_sha256"): _hash(facts[x],x)
        for x in ("key_enable_receipt","rfc3161_receipt"):
            raw=facts[x]
            if not isinstance(raw,bytes) or hashlib.sha256(raw).hexdigest()!=facts[x+"_sha256"]: raise Type1FreshCustodyError("full authority receipt mismatch")
            _canonical_object(raw,x)
        return {x:(base64.b64encode(v).decode() if isinstance(v,bytes) else v) for x,v in facts.items()}
    def _receipt_result(self,value:Mapping[str,Any],label:str)->dict[str,Any]:
        if not isinstance(value,Mapping) or set(value)!={"receipt_sha256","receipt"}: raise Type1FreshCustodyError(f"{label} receipt fields invalid")
        _hash(value["receipt_sha256"],label+" receipt"); raw=value["receipt"]
        if not isinstance(raw,bytes) or hashlib.sha256(raw).hexdigest()!=value["receipt_sha256"]: raise Type1FreshCustodyError(f"{label} full receipt mismatch")
        _canonical_object(raw,label+" receipt"); return {"receipt_sha256":value["receipt_sha256"],"receipt_b64":base64.b64encode(raw).decode()}
    def _seal_record(self,intent:Mapping[str,Any],enabled:Mapping[str,Any])->dict[str,Any]:
        return {"schema_version":SEAL_SCHEMA,"dataset_id":self.dataset_id,"custody_uid":self.custody_uid,"prereg_sha256":self.prereg_sha256,"freeze_start":FRESH_OOS_START_DATE,"decision_end":self.calendar[-1][0],"freeze_end":FRESH_OOS_END_DATE,"pair_count":len(self.calendar),"first_ordinal":1,"last_ordinal":len(self.calendar),"commitment_tip_sha256":intent["commitment_tip_sha256"],"commitment_merkle_root_sha256":self._merkle_root(),"ledger_tip_sha256":self._tip(),"access_ledger_id":intent["access_ledger_id"],"authority_key_id":self.authority_key_id,"authority_public_key_sha256":self._key_fingerprint(),"key_id":enabled["key_id"],"key_enable_receipt_sha256":enabled["key_enable_receipt_sha256"],"access_ledger_genesis_sha256":enabled["access_ledger_genesis_sha256"],"rfc3161_receipt_sha256":enabled["rfc3161_receipt_sha256"],"key_enable_receipt":enabled["key_enable_receipt"],"rfc3161_receipt":enabled["rfc3161_receipt"],"key_state":"ENABLED","access_state":"UNUSED","deny_state":"ABSENT","fresh_oos_status":"NOT_RUN"}
    def _publish_sidecar(self,raw:bytes,authority:MetadataAuthority)->None:
        path=self.database+".seal"
        try:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,"wb") as out: out.write(raw); out.flush(); os.fsync(out.fileno())
            self._sync_parent(path)
        except FileExistsError:
            try:
                with open(path,"rb") as src: existing=src.read()
            except OSError: self._block(authority,"FINAL_SEAL_CONFLICT")
            if existing!=raw: self._block(authority,"FINAL_SEAL_CONFLICT")
    def _finalize_seal(self)->bytes:
        raw=self._sidecar()
        with self._transaction() as db:
            old=db.execute("SELECT seal FROM seals WHERE singleton=1").fetchone()
            if old is None: db.execute("INSERT INTO seals VALUES(1,?,?)",(raw,_domain_digest("seal",raw))); self._append_event(db,"SEALED",None,self._phase_json("seal_intent")["commitment_tip_sha256"],_domain_digest("seal",raw),"HEALTHY_SEAL")
            elif old[0]!=raw: raise Type1FreshCustodyError("sealed record differs from sidecar")
        return raw
    def _initialize(self)->None:
        db=self._connection(); db.executescript("CREATE TABLE IF NOT EXISTS events(sequence INTEGER PRIMARY KEY,event BLOB NOT NULL,digest TEXT NOT NULL UNIQUE,previous_digest TEXT NOT NULL);CREATE TABLE IF NOT EXISTS commitments(ordinal INTEGER PRIMARY KEY,digest TEXT NOT NULL UNIQUE,envelope BLOB NOT NULL UNIQUE,receipt BLOB NOT NULL);CREATE TABLE IF NOT EXISTS seals(singleton INTEGER PRIMARY KEY CHECK(singleton=1),seal BLOB NOT NULL,digest TEXT NOT NULL);CREATE TABLE IF NOT EXISTS failures(singleton INTEGER PRIMARY KEY CHECK(singleton=1),receipt BLOB NOT NULL);CREATE TABLE IF NOT EXISTS settings(name TEXT PRIMARY KEY,value TEXT NOT NULL);CREATE TABLE IF NOT EXISTS writer_locks(custody_uid TEXT PRIMARY KEY);")
        for table in ("events","commitments","seals","failures","settings"):
            db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_update BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT,'append only'); END"); db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT,'append only'); END")
        identity={"identity_dataset_id":self.dataset_id,"identity_custody_uid":self.custody_uid,"identity_prereg_sha256":self.prereg_sha256,"identity_protocol_sha256":self.protocol_sha256,"identity_principal_uri":self.authority_principal_uri,"identity_key_id":self.authority_key_id,"identity_public_key_sha256":self._key_fingerprint(),"identity_calendar_sha256":self._calendar_sha()}
        empty=db.execute("SELECT COUNT(*) FROM events").fetchone()[0]==0; db.close()
        if empty:
            with self._transaction() as tx:
                for k,v in identity.items(): self._put(tx,k,v)
                self._append_event(tx,"GENESIS",None,None,self.protocol_sha256,"INITIALIZED")
        elif self._settings_dict()!=identity | {k:v for k,v in self._settings_dict().items() if not k.startswith("identity_")}:
            stored=self._settings_dict()
            if {k:stored.get(k) for k in identity}!=identity: raise Type1FreshCustodyError("stored custody identity or calendar differs")
    def _connection(self)->sqlite3.Connection:
        db=sqlite3.connect(self.database,timeout=30,isolation_level=None); db.execute("PRAGMA journal_mode=WAL"); db.execute("PRAGMA synchronous=FULL"); db.execute("PRAGMA foreign_keys=ON"); return db
    @contextmanager
    def _transaction(self):
        db=self._connection(); db.execute("BEGIN EXCLUSIVE")
        try: db.execute("INSERT OR IGNORE INTO writer_locks VALUES(?)",(self.custody_uid,)); yield db; db.execute("DELETE FROM writer_locks WHERE custody_uid=?",(self.custody_uid,)); db.commit()
        except BaseException: db.rollback(); raise
        finally: db.close()
    def _put(self,db:sqlite3.Connection,name:str,value:Any)->bool:
        if name not in self._settings: raise Type1FreshCustodyError("settings allowlist violation")
        raw=value if isinstance(value,str) else canonical_json_bytes(value).decode()
        try: db.execute("INSERT INTO settings VALUES(?,?)",(name,raw)); return True
        except sqlite3.IntegrityError:
            row=db.execute("SELECT value FROM settings WHERE name=?",(name,)).fetchone()
            if row is None or row[0]!=raw: raise Type1FreshCustodyError("immutable phase differs")
            return False
    def _set_plain(self,name:str,value:str)->None:
        with self._transaction() as db: self._put(db,name,value)
    def _set_phase(self,name:str,value:Mapping[str,Any],event:str,commitment:str|None,receipt:str|None,reason:str)->None:
        with self._transaction() as db:
            if self._put(db,name,value): self._append_event(db,event,None,commitment,receipt,reason)
    def _append_event(self,db:sqlite3.Connection,event:str,ordinal:int|None,commitment:str|None,receipt:str|None,reason:str)->None:
        prior=self._tip(db); seq=db.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM events").fetchone()[0]; data={"schema_version":EVENT_SCHEMA,"sequence":seq,"event_type":event,"dataset_id":self.dataset_id,"custody_uid":self.custody_uid,"prereg_sha256":self.prereg_sha256,"ordinal":ordinal,"commitment_sha256":commitment,"authority_receipt_sha256":receipt,"reason_code":reason,"previous_event_sha256":prior}; raw=canonical_json_bytes(data); db.execute("INSERT INTO events VALUES(?,?,?,?)",(seq,raw,_domain_digest("event",raw),prior))
    def _tip(self,db:sqlite3.Connection|None=None)->str:
        own=db is None; db=db or self._connection(); row=db.execute("SELECT digest FROM events ORDER BY sequence DESC LIMIT 1").fetchone()
        if own: db.close()
        return row[0] if row else GENESIS_COMMITMENT_SHA256
    def _setting(self,name:str)->str|None:
        db=self._connection(); row=db.execute("SELECT value FROM settings WHERE name=?",(name,)).fetchone(); db.close(); return row[0] if row else None
    def _phase(self,name:str)->bool: return self._setting(name) is not None
    def _phase_json(self,name:str)->dict[str,Any]|None:
        value=self._setting(name); return json.loads(value) if value else None
    def _settings_dict(self)->dict[str,str]:
        db=self._connection(); rows=dict(db.execute("SELECT name,value FROM settings")); db.close(); return rows
    def _commitment_count(self)->int:
        db=self._connection(); n=db.execute("SELECT COUNT(*) FROM commitments").fetchone()[0]; db.close(); return n
    def _commitment_digest(self,ordinal:int)->str:
        db=self._connection(); row=db.execute("SELECT digest FROM commitments WHERE ordinal=?",(ordinal,)).fetchone(); db.close()
        if not row: raise Type1FreshCustodyError("missing commitment")
        return row[0]
    def _sealed(self)->bool:
        db=self._connection(); yes=db.execute("SELECT 1 FROM seals WHERE singleton=1").fetchone() is not None; db.close(); return yes
    def _seal_bytes(self)->bytes:
        db=self._connection(); row=db.execute("SELECT seal FROM seals WHERE singleton=1").fetchone(); db.close()
        if not row: raise Type1FreshCustodyError("seal is absent")
        return row[0]
    def _failure_receipt(self)->bytes|None:
        db=self._connection(); row=db.execute("SELECT receipt FROM failures WHERE singleton=1").fetchone(); db.close(); return row[0] if row else None
    def _blocked(self)->bool: return self._phase("denied")
    def _sidecar(self)->bytes:
        with open(self.database+".seal","rb") as src: return src.read()
    def _sidecar_matches(self)->bool:
        try:
            raw=self._sidecar()
            if self._sealed():
                return raw==self._seal_bytes()
            phase=self._phase_json("sidecar_published")
            return phase is not None and phase=={"seal_sha256":hashlib.sha256(raw).hexdigest(),"seal_domain_sha256":_domain_digest("seal",raw)}
        except (OSError,Type1FreshCustodyError):
            return False
    def _calendar_sha(self)->str: return hashlib.sha256(canonical_json_bytes(self.calendar)).hexdigest()
    def _key_fingerprint(self)->str: return hashlib.sha256(self.authority_public_key.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).hexdigest()
    def _access_ledger_id(self,tip:str)->str: return _domain_digest("access_ledger",canonical_json_bytes({"dataset_id":self.dataset_id,"custody_uid":self.custody_uid,"prereg_sha256":self.prereg_sha256,"calendar_sha256":self._calendar_sha(),"commitment_tip_sha256":tip,"authority_key_id":self.authority_key_id,"authority_public_key_sha256":self._key_fingerprint()}))
    def _sealed_access_id(self)->str: return _canonical_object(self._seal_bytes(),"seal")["access_ledger_id"]
    def _sealed_access_id_or_pending(self)->str: return self._sealed_access_id() if self._sealed() else (self._phase_json("seal_intent") or {"access_ledger_id":self._access_ledger_id(self._tip())})["access_ledger_id"]
    def _merkle_root(self)->str:
        db=self._connection(); rows=db.execute("SELECT ordinal,digest FROM commitments ORDER BY ordinal").fetchall(); db.close(); leaves=[_domain_digest("merkle_leaf",int(o).to_bytes(8,"big"),_hex_bytes(d,"commitment digest")) for o,d in rows]
        if not leaves: raise Type1FreshCustodyError("empty commitment tree")
        while len(leaves)>1:
            if len(leaves)%2: leaves.append(leaves[-1])
            leaves=[_domain_digest("merkle_node",_hex_bytes(a,"merkle left"),_hex_bytes(b,"merkle right")) for a,b in zip(leaves[::2],leaves[1::2])]
        return leaves[0]
    def _sync_parent(self,path:str)->None:
        if os.name=="posix":
            fd=os.open(str(Path(path).parent),os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)
    def _validate_calendar(self)->None:
        if len(self.calendar)<120 or self.calendar[0][0]!=FRESH_OOS_START_DATE or self.calendar[-1][1]!=FRESH_OOS_END_DATE: raise ValueError("calendar must cover frozen window")
        last=None
        for decision,settlement in self.calendar:
            d,s=_iso_date(decision,"decision"),_iso_date(settlement,"settlement")
            if d>=s or (last and d<=last): raise ValueError("calendar must be ordered pairs")
            last=s
    def verify_chain(self)->None:
        db=self._connection(); rows=db.execute("SELECT sequence,event,digest,previous_digest FROM events ORDER BY sequence").fetchall(); db.close(); previous=GENESIS_COMMITMENT_SHA256
        for seq,raw,digest,stored in rows:
            event=_canonical_object(raw,"ledger event")
            if stored!=previous or digest!=_domain_digest("event",raw) or event.get("sequence")!=seq or event.get("previous_event_sha256")!=previous or (event.get("schema_version"),event.get("dataset_id"),event.get("custody_uid"),event.get("prereg_sha256"))!=(EVENT_SCHEMA,self.dataset_id,self.custody_uid,self.prereg_sha256): raise Type1FreshCustodyError("event hash chain is tampered")
            previous=digest
    def _verify_full(self)->None:
        self._verify_storage(); self.verify_chain(); settings=self._settings_dict()
        if set(settings)-self._settings: raise Type1FreshCustodyError("settings allowlist violated")
        for table in ("events","commitments","seals","failures","settings"):
            db=self._connection(); names={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=?",(table,))}; db.close()
            if names!={table+"_no_update",table+"_no_delete"}: raise Type1FreshCustodyError("append-only trigger set differs")
        db=self._connection(); rows=db.execute("SELECT ordinal,digest,envelope,receipt FROM commitments ORDER BY ordinal").fetchall(); events=[_canonical_object(x[0],"ledger event") for x in db.execute("SELECT event FROM events ORDER BY sequence")]; db.close()
        prior=GENESIS_COMMITMENT_SHA256
        for ordinal,digest,envelope,receipt in rows:
            item=parse_and_verify_commitment_envelope(envelope,expected_dataset_id=self.dataset_id,expected_custody_uid=self.custody_uid,expected_prereg_sha256=self.prereg_sha256,expected_principal_uri=self.authority_principal_uri,expected_key_id=self.authority_key_id,public_key=self.authority_public_key)
            if ordinal!=item.statement["ordinal"] or digest!=item.digest or item.statement["previous_commitment_sha256"]!=prior or tuple(item.statement[x] for x in ("decision_session","settlement_session"))!=self.calendar[ordinal-1] or receipt!=canonical_json_bytes({"schema_version":EVENT_SCHEMA,"ordinal":ordinal,"commitment_sha256":digest}): raise Type1FreshCustodyError("commitment projection is tampered")
            prior=digest
        phase_events={"seal_intent":"SEAL_INTENT","key_enabled":"KEY_ENABLED","sidecar_published":"SIDECAR_PUBLISHED","recovery_intent":"RECOVERY_INTENT","key_disabled_recovery":"KEY_DISABLED","consumed":"CONSUMED","failure_final":"FAILURE_FINAL","block_intent":"BLOCK_INTENT","key_disabled_block":"KEY_DISABLED","denied":"DENIED","gate_receipt":"GATE_RECORDED"}
        allowed={"GENESIS","COMMITMENT_RECORDED","SEALED",*phase_events.values()}
        if any(e.get("event_type") not in allowed for e in events):
            raise Type1FreshCustodyError("unknown event state")
        commitment_events=[e for e in events if e["event_type"]=="COMMITMENT_RECORDED"]
        if len([e for e in events if e["event_type"]=="GENESIS"])!=1 or len(commitment_events)!=len(rows) or any((e["ordinal"],e["commitment_sha256"],e["authority_receipt_sha256"],e["reason_code"])!=(o,d,d,"AUTHENTICATED") for e,(o,d,_,_) in zip(commitment_events,rows)):
            raise Type1FreshCustodyError("event projection is tampered")
        for name,event in phase_events.items():
            matches=[e for e in events if e["event_type"]==event]
            if name=="key_disabled_recovery":
                matches=[e for e in matches if e["reason_code"]=="POST_RESERVED_RECOVERY"]
            elif name=="key_disabled_block":
                block_intent=self._phase_json("block_intent")
                matches=[e for e in matches if block_intent is not None and e["reason_code"]==block_intent["reason"]]
            if name in settings:
                if len(matches)!=1: raise Type1FreshCustodyError("phase event projection is tampered")
            elif matches: raise Type1FreshCustodyError("orphan phase event")
        if self._phase("key_enabled") and not self._phase("seal_intent") or self._phase("sidecar_published") and not self._phase("key_enabled") or self._sealed() and not self._phase("sidecar_published") or self._phase("recovery_intent") and not self._sealed() or self._phase("key_disabled_recovery") and not self._phase("recovery_intent") or self._phase("consumed") and not self._phase("key_disabled_recovery") or self._phase("failure_final") and not self._phase("consumed") or self._phase("key_disabled_block") and not self._phase("block_intent") or self._phase("denied") and not self._phase("key_disabled_block"):
            raise Type1FreshCustodyError("phase ordering is invalid")
        for name in ("key_disabled_recovery","key_disabled_block","consumed","denied"):
            phase=self._phase_json(name)
            if phase is not None:
                if set(phase)!={"receipt_sha256","receipt_b64"}: raise Type1FreshCustodyError("receipt phase fields are invalid")
                raw=base64.b64decode(phase["receipt_b64"],validate=True)
                if base64.b64encode(raw).decode()!=phase["receipt_b64"] or hashlib.sha256(raw).hexdigest()!=phase["receipt_sha256"]: raise Type1FreshCustodyError("full receipt projection is tampered")
                _canonical_object(raw,name+" receipt")
        if self._phase("key_enabled"):
            enabled=self._phase_json("key_enabled")
            for name in ("key_enable_receipt","rfc3161_receipt"):
                raw=base64.b64decode(enabled[name],validate=True)
                if base64.b64encode(raw).decode()!=enabled[name] or hashlib.sha256(raw).hexdigest()!=enabled[name+"_sha256"]: raise Type1FreshCustodyError("full seal receipt projection is tampered")
                _canonical_object(raw,name)
        if self._phase("gate_receipt"):
            phase=self._phase_json("gate_receipt"); raw=base64.b64decode(phase["raw_b64"],validate=True); gate=_canonical_object(raw,"gate receipt")
            if base64.b64encode(raw).decode()!=phase["raw_b64"] or phase["digest"]!=_domain_digest("gate",canonical_json_bytes(gate)): raise Type1FreshCustodyError("gate receipt is tampered")
            _keys(gate,{"schema_version","statement","signature"},"gate receipt")
            try: self.authority_public_key.verify(_b64(gate["signature"]),HASH_DOMAINS["gate"]+canonical_json_bytes(gate["statement"]))
            except (InvalidSignature,ValueError,TypeError) as exc: raise Type1FreshCustodyError("gate receipt is tampered") from exc
        if self._phase("failure_final"):
            failure=_canonical_object(self._failure_receipt(),"failure receipt")
            if set(failure)!={"schema_version","custody_uid","access_ledger_id","seal_sha256","reservation_receipt_sha256","consumed_receipt_sha256","key_disable_receipt_sha256","reason","retry_allowed"} or failure["schema_version"]!=FAILURE_RECEIPT_SCHEMA or failure["consumed_receipt_sha256"]!=self._phase_json("consumed")["receipt_sha256"] or failure["key_disable_receipt_sha256"]!=self._phase_json("key_disabled_recovery")["receipt_sha256"]: raise Type1FreshCustodyError("failure receipt is tampered")
        if self._phase("sidecar_published"):
            raw=self._sidecar(); phase=self._phase_json("sidecar_published")
            if phase!={"seal_sha256":hashlib.sha256(raw).hexdigest(),"seal_domain_sha256":_domain_digest("seal",raw)}: raise Type1FreshCustodyError("sidecar projection is tampered")
            side_event=[e for e in events if e["event_type"]=="SIDECAR_PUBLISHED"][0]; intent=self._phase_json("seal_intent"); expected=self._seal_record(intent,self._phase_json("key_enabled")); expected["ledger_tip_sha256"]=side_event["previous_event_sha256"]
            if raw!=canonical_json_bytes(expected) or side_event["commitment_sha256"]!=intent["commitment_tip_sha256"] or side_event["authority_receipt_sha256"]!=_domain_digest("seal",raw): raise Type1FreshCustodyError("seal projection is tampered")
        if self._sealed():
            if self._seal_bytes()!=self._sidecar(): raise Type1FreshCustodyError("sealed sidecar differs")
            sealed=[e for e in events if e["event_type"]=="SEALED"]
            if len(sealed)!=1 or sealed[0]["authority_receipt_sha256"]!=_domain_digest("seal",self._seal_bytes()): raise Type1FreshCustodyError("seal finalization projection is tampered")
    def _verify_storage(self)->None:
        db=self._connection(); quick=db.execute("PRAGMA quick_check").fetchone()[0]; integrity=db.execute("PRAGMA integrity_check").fetchone()[0]; journal=db.execute("PRAGMA journal_mode").fetchone()[0]; sync=db.execute("PRAGMA synchronous").fetchone()[0]; db.close()
        if quick!="ok" or integrity!="ok" or journal.lower()!="wal" or sync!=2: raise Type1FreshCustodyError("SQLite custody profile invalid")
    def _assert_integrity(self)->None: self._verify_full()
    def _assert_healthy(self)->None:
        self._assert_integrity()
        if self._phase("block_intent") or self._phase("failure_final"): raise CustodyBlocked("custody is terminally unavailable")
