"""Deterministic control-plane tests; fixtures contain hashes and signed metadata only."""
from __future__ import annotations

import ast
import base64
import hashlib
import inspect
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl import daily_type1_fresh_custody as custody

DATASET="type1-close-20260803-002"; CUSTODY="type1-fresh-oos-20260803-002"; PREREG="a"*64; PROTOCOL="b"*64
PRINCIPAL="agent://type1-krx-authority-20260723-001"; KEY_ID="22222222-2222-4222-8222-222222222222"


def _calendar():
    first=date(2026,8,3); result=[(first+timedelta(days=n*3),first+timedelta(days=n*3+1)) for n in range(119)]
    result.append((date(2027,7,29),date(2027,7,30)))
    return tuple((a.isoformat(),b.isoformat()) for a,b in result)


class Authority:
    def __init__(self,key,calendar): self.key,self.calendar,self.responses,self.access=key,calendar,{}, {"state":"UNUSED"}; self.disable_calls=self.consume_calls=self.deny_calls=0
    @staticmethod
    def _receipt(label):
        raw=canonical_json_bytes({"receipt_type":label,"schema_version":"kronos_type1_authority_receipt.v1"})
        return {"receipt_sha256":hashlib.sha256(raw).hexdigest(),"receipt":raw}
    def commitment(self,ordinal):
        value=self.responses.get(ordinal)
        if isinstance(value,Exception): raise value
        return value
    def key_enable(self,access_ledger_id,*_):
        key_raw=self.key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        enabled=self._receipt("KEY_ENABLED"); stamp=self._receipt("RFC3161")
        return {"access_ledger_id":access_ledger_id,"key_id":KEY_ID,"authority_public_key_sha256":hashlib.sha256(key_raw).hexdigest(),"key_enable_receipt_sha256":enabled["receipt_sha256"],"access_ledger_genesis_sha256":"d"*64,"rfc3161_receipt_sha256":stamp["receipt_sha256"],"key_enable_receipt":enabled["receipt"],"rfc3161_receipt":stamp["receipt"]}
    def key_disable(self,*_): self.disable_calls+=1; return self._receipt("KEY_DISABLED")
    def access_snapshot(self,*_): return self.access
    def consume_observed(self,*_): self.consume_calls+=1; result=self._receipt("CONSUMED"); self.access={"state":"CONSUMED","receipt_sha256":result["receipt_sha256"]}; return result
    def issue_deny(self,*_): self.deny_calls+=1; return self._receipt("DENIED")


def _envelope(key,ordinal,calendar,prior):
    statement={"schema_version":custody.COMMITMENT_ENVELOPE_SCHEMA,"dataset_id":DATASET,"custody_uid":CUSTODY,"prereg_sha256":PREREG,"ordinal":ordinal,"decision_session":calendar[ordinal-1][0],"settlement_session":calendar[ordinal-1][1],"ciphertext_sha256":hashlib.sha256(str(ordinal).encode()).hexdigest(),"ciphertext_byte_length":ordinal,"previous_commitment_sha256":prior,"authority_principal_uri":PRINCIPAL,"authority_key_id":KEY_ID}
    signature=key.sign(custody.COMMITMENT_DOMAIN+canonical_json_bytes(statement))
    return canonical_json_bytes({"schema_version":custody.COMMITMENT_ENVELOPE_SCHEMA,"statement":statement,"signature":base64.urlsafe_b64encode(signature).decode().rstrip("=")})


def _ledger(tmp_path):
    key=Ed25519PrivateKey.from_private_bytes(bytes(range(32))); calendar=_calendar(); authority=Authority(key,calendar)
    return custody.Type1FreshCustodyLedger(tmp_path/"custody.sqlite",dataset_id=DATASET,custody_uid=CUSTODY,prereg_sha256=PREREG,calendar=calendar,authority_principal_uri=PRINCIPAL,authority_key_id=KEY_ID,authority_public_key=key.public_key(),protocol_sha256=PROTOCOL),authority,key,calendar


def _fill(ledger,authority,key,calendar):
    prior=custody.GENESIS_COMMITMENT_SHA256
    for ordinal in range(1,len(calendar)+1):
        raw=_envelope(key,ordinal,calendar,prior); authority.responses[ordinal]=raw; ledger.reconcile_ordinal(authority,ordinal); prior=custody.commitment_digest(json.loads(raw)["statement"])


def test_hash_registry_literal_kats():
    fixture=json.loads((Path(__file__).parent/"fixtures/type1_hash_domains_v1.json").read_text(encoding="utf-8"))
    assert fixture["genesis_commitment_sha256"]==custody.GENESIS_COMMITMENT_SHA256
    for case in fixture["cases"]: assert custody._domain_digest(case["domain"],*(bytes.fromhex(x) for x in case["parts_hex"]))==case["sha256"]


def test_absence_is_accumulating_and_signed_calendar_is_exact(tmp_path):
    ledger,authority,key,calendar=_ledger(tmp_path)
    assert ledger.reconcile_ordinal(authority,1) is None
    assert ledger.status()["public_status"]=="ACCUMULATING_NOT_RUN"
    authority.responses[1]=_envelope(key,1,calendar,custody.GENESIS_COMMITMENT_SHA256)
    assert ledger.reconcile_ordinal(authority,1)
    forged=json.loads(authority.responses[1]); forged["statement"]["decision_session"]="2026-08-04"; authority.responses[1]=canonical_json_bytes(forged)
    with pytest.raises(custody.CustodyBlocked): ledger.reconcile_ordinal(authority,1)


def test_recovery_intent_precedes_effects_and_is_idempotent(tmp_path):
    ledger,authority,key,calendar=_ledger(tmp_path); _fill(ledger,authority,key,calendar); seal=ledger.seal(authority)
    authority.access={"state":"RESERVED","receipt_sha256":"4"*64}
    receipt=ledger.recover(authority)
    assert json.loads(receipt)["retry_allowed"] is False
    assert ledger.recover(authority)==receipt and authority.consume_calls==1
    assert ledger.status()["public_status"]=="CONSUMED_NOT_RUN"
    assert hashlib.sha256(seal).hexdigest()==json.loads(receipt)["seal_sha256"]


def test_gate_must_be_canonical_signed_and_identity_bound(tmp_path):
    ledger,authority,key,calendar=_ledger(tmp_path); _fill(ledger,authority,key,calendar); seal=ledger.seal(authority)
    statement={"schema_version":custody.GATE_RECEIPT_SCHEMA,"dataset_id":DATASET,"custody_uid":CUSTODY,"prereg_sha256":PREREG,"seal_sha256":hashlib.sha256(seal).hexdigest(),"commitment_sha256":"3"*64,"authority_principal_uri":PRINCIPAL,"authority_key_id":KEY_ID}
    raw=canonical_json_bytes({"schema_version":custody.GATE_RECEIPT_SCHEMA,"statement":statement,"signature":base64.urlsafe_b64encode(key.sign(custody.HASH_DOMAINS["gate"]+canonical_json_bytes(statement))).decode().rstrip("=")})
    assert ledger.record_gate_receipt(raw)==raw
    with pytest.raises(custody.Type1FreshCustodyError): ledger.record_gate_receipt(raw[:-1]+b" ")


def test_tamper_profile_and_concurrent_replay_fail_closed_or_read_only(tmp_path):
    ledger,authority,key,calendar=_ledger(tmp_path); raw=_envelope(key,1,calendar,custody.GENESIS_COMMITMENT_SHA256); authority.responses[1]=raw
    with ThreadPoolExecutor(max_workers=2) as pool: outcomes=list(pool.map(lambda _: ledger.reconcile_ordinal(authority,1),range(2)))
    assert outcomes[0]==outcomes[1]
    assert ledger._commitment_count()==1
    db=sqlite3.connect(ledger.database)
    assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0]==2
    db.close()
    db=sqlite3.connect(ledger.database)
    with pytest.raises(sqlite3.IntegrityError,match="append only"):
        db.execute("UPDATE events SET digest=? WHERE sequence=2",("0"*64,))
    db.execute("DROP TRIGGER events_no_update")
    db.execute("UPDATE events SET digest=? WHERE sequence=2",("0"*64,))
    db.commit()
    db.close()
    with pytest.raises(custody.Type1FreshCustodyError,match="tampered"): ledger.status()


def test_reopen_after_recovery_fault_keeps_durable_intent(tmp_path):
    ledger,authority,key,calendar=_ledger(tmp_path); _fill(ledger,authority,key,calendar); ledger.seal(authority)
    authority.access={"state":"RESERVED","receipt_sha256":"4"*64}
    original=authority.key_disable
    authority.key_disable=lambda *_: (_ for _ in ()).throw(custody.AuthorityUnavailable("fault"))
    with pytest.raises(custody.Type1FreshCustodyError,match="key disable recovery pending"): ledger.recover(authority)
    reopened=custody.Type1FreshCustodyLedger(ledger.database,dataset_id=DATASET,custody_uid=CUSTODY,prereg_sha256=PREREG,calendar=calendar,authority_principal_uri=PRINCIPAL,authority_key_id=KEY_ID,authority_public_key=key.public_key(),protocol_sha256=PROTOCOL)
    assert reopened.status()["recovery_state"]=="PENDING"
    authority.key_disable=original
    assert reopened.recover(authority) is not None
def test_recovery_consume_fault_is_reported_as_pending(tmp_path):
    ledger,authority,key,calendar=_ledger(tmp_path); _fill(ledger,authority,key,calendar); ledger.seal(authority)
    authority.access={"state":"RESERVED","receipt_sha256":"4"*64}
    original=authority.consume_observed
    authority.consume_observed=lambda *_: (_ for _ in ()).throw(custody.AuthorityUnavailable("fault"))
    with pytest.raises(custody.Type1FreshCustodyError,match="consume recovery pending"): ledger.recover(authority)
    assert ledger.status()["recovery_state"]=="PENDING"
    authority.consume_observed=original
    assert ledger.recover(authority) is not None

def test_base64url_is_canonical():
    signature=bytes(range(64)); encoded=base64.urlsafe_b64encode(signature).decode().rstrip("=")
    assert custody._b64(encoded)==signature
    with pytest.raises(custody.Type1FreshCustodyError): custody._b64(encoded+"=")

def test_forbidden_capability_surface_is_absent():
    tree=ast.parse(inspect.getsource(custody)); names={node.name for node in ast.walk(tree) if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))}
    assert not names & {"open","read","read_payload","decrypt","encrypt","reserve","lease","materialize","metric","evaluate"}
    assert "fresh_oos_metrics" not in inspect.getsource(custody)
