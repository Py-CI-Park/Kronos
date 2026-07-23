"""Synthetic control-plane coverage for Type1 fresh custody; no fresh fixture exists here."""
from __future__ import annotations

import ast
import base64
import hashlib
import inspect
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from stom_rl.daily_type1_contract import canonical_json_bytes, sha256_canonical
from stom_rl import daily_type1_fresh_custody as custody


DATASET = "type1-close-20260803-001"
CUSTODY = "11111111-1111-4111-8111-111111111111"
PREREG = "a" * 64
PRINCIPAL = "agent://type1-custody-authority"
KEY_ID = "22222222-2222-4222-8222-222222222222"
PROTOCOL = "b" * 64


def _calendar() -> tuple[tuple[str, str], ...]:
    first = date(2026, 8, 3)
    pairs = [(first + timedelta(days=index * 3), first + timedelta(days=index * 3 + 1)) for index in range(119)]
    pairs.append((date(2027, 7, 29), date(2027, 7, 30)))
    return tuple((decision.isoformat(), settlement.isoformat()) for decision, settlement in pairs)


class FakeAuthority:
    def __init__(self, signing_key: Ed25519PrivateKey, calendar: tuple[tuple[str, str], ...]) -> None:
        self.signing_key = signing_key
        self.calendar = calendar
        self.responses: dict[int, bytes | None | Exception] = {}
        self.disable_calls = 0
        self.deny_calls = 0
        self.enable_calls = 0
        self.consume_calls = 0
        self.access = {"state": "UNUSED"}

    def commitment(self, ordinal: int) -> bytes | None:
        response = self.responses.get(ordinal)
        if isinstance(response, Exception):
            raise response
        return response

    def key_enable(self, custody_uid: str, seal_sha256: str):
        self.enable_calls += 1
        return {"key_id": KEY_ID, "key_enable_receipt_sha256": "c" * 64,
                "access_ledger_genesis_sha256": "d" * 64, "rfc3161_receipt_sha256": "e" * 64}

    def key_disable(self, custody_uid: str, reason: str):
        self.disable_calls += 1
        return {"receipt_sha256": "f" * 64}

    def access_snapshot(self, custody_uid: str, seal_sha256: str):
        return self.access

    def consume_observed(self, custody_uid: str, seal_sha256: str, reason: str):
        self.consume_calls += 1
        self.access = {"state": "CONSUMED"}
        return {"receipt_sha256": "1" * 64}

    def issue_deny(self, custody_uid: str, block_event_sha256: str):
        self.deny_calls += 1
        return {"receipt_sha256": "2" * 64}


def _envelope(key: Ed25519PrivateKey, ordinal: int, calendar, predecessor: str) -> bytes:
    statement = {
        "schema_version": custody.COMMITMENT_ENVELOPE_SCHEMA, "dataset_id": DATASET, "custody_uid": CUSTODY,
        "prereg_sha256": PREREG, "ordinal": ordinal, "decision_session": calendar[ordinal - 1][0],
        "settlement_session": calendar[ordinal - 1][1], "ciphertext_sha256": hashlib.sha256(f"metadata-{ordinal}".encode()).hexdigest(),
        "ciphertext_byte_length": ordinal, "previous_commitment_sha256": predecessor,
        "authority_principal_uri": PRINCIPAL, "authority_key_id": KEY_ID,
    }
    signature = key.sign(custody.COMMITMENT_DOMAIN + canonical_json_bytes(statement))
    return canonical_json_bytes({"schema_version": custody.COMMITMENT_ENVELOPE_SCHEMA, "statement": statement,
                                 "signature": base64.urlsafe_b64encode(signature).decode().rstrip("=")})


def _ledger(tmp_path: Path):
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    calendar = _calendar()
    authority = FakeAuthority(key, calendar)
    ledger = custody.Type1FreshCustodyLedger(
        tmp_path / "custody.sqlite", dataset_id=DATASET, custody_uid=CUSTODY, prereg_sha256=PREREG,
        calendar=calendar, authority_principal_uri=PRINCIPAL, authority_key_id=KEY_ID,
        authority_public_key=key.public_key(), protocol_sha256=PROTOCOL,
    )
    return ledger, authority, key, calendar


def _populate(ledger, authority, key, calendar) -> None:
    predecessor = custody.GENESIS_COMMITMENT_SHA256
    for ordinal in range(1, len(calendar) + 1):
        raw = _envelope(key, ordinal, calendar, predecessor)
        authority.responses[ordinal] = raw
        assert ledger.reconcile_ordinal(authority, ordinal) is not None
        predecessor = sha256_canonical(__import__("json").loads(raw)["statement"])


def test_append_and_same_ordinal_readback_is_read_only(tmp_path: Path) -> None:
    ledger, authority, key, calendar = _ledger(tmp_path)
    raw = _envelope(key, 1, calendar, custody.GENESIS_COMMITMENT_SHA256)
    authority.responses[1] = raw
    first = ledger.reconcile_ordinal(authority, 1)
    event_tip = ledger._tip()
    replay = ledger.reconcile_ordinal(authority, 1)
    assert replay == first
    assert ledger._tip() == event_tip
    assert ledger.status()["public_status"] == "ACCUMULATING_NOT_RUN"
    assert authority.disable_calls == authority.deny_calls == 0


@pytest.mark.parametrize("ordinal", [2, 1])
def test_gaps_and_conflicts_terminally_block(tmp_path: Path, ordinal: int) -> None:
    ledger, authority, key, calendar = _ledger(tmp_path)
    predecessor = custody.GENESIS_COMMITMENT_SHA256 if ordinal == 1 else "0" * 64
    authority.responses[ordinal] = _envelope(key, ordinal, calendar, predecessor)
    if ordinal == 1:
        assert ledger.reconcile_ordinal(authority, 1)
        altered = bytearray(authority.responses[1])
        altered[-2] = ord("A") if altered[-2] != ord("A") else ord("B")
        authority.responses[1] = bytes(altered)
    with pytest.raises(custody.CustodyBlocked):
        ledger.reconcile_ordinal(authority, ordinal)
    assert ledger.status()["public_status"] == "BLOCKED_NOT_RUN"
    assert authority.disable_calls == authority.deny_calls == 1


def test_chain_tamper_is_fail_closed(tmp_path: Path) -> None:
    ledger, authority, key, calendar = _ledger(tmp_path)
    authority.responses[1] = _envelope(key, 1, calendar, custody.GENESIS_COMMITMENT_SHA256)
    assert ledger.reconcile_ordinal(authority, 1)
    connection = sqlite3.connect(ledger.database)
    connection.execute("UPDATE events SET digest = ? WHERE sequence = 2", ("0" * 64,))
    connection.commit()
    connection.close()
    with pytest.raises(custody.Type1FreshCustodyError, match="tampered"):
        ledger.status() if False else ledger.reconcile_ordinal(authority, 1)


def test_authority_absence_is_accumulating_not_denied(tmp_path: Path) -> None:
    ledger, authority, _, _ = _ledger(tmp_path)
    authority.responses[1] = custody.AuthorityUnavailable("offline")
    assert ledger.reconcile_ordinal(authority, 1) is None
    state = ledger.status()
    assert (state["public_status"], state["key_state"], state["access_state"], state["deny_state"], state["fresh_oos_metrics"]) == (
        "ACCUMULATING_NOT_RUN", "UNAVAILABLE", "UNUSED", "ABSENT", None)
    assert authority.disable_calls == authority.deny_calls == 0


def test_healthy_seal_gate_is_non_reserving_and_reserved_recovery_never_decrypts(tmp_path: Path) -> None:
    ledger, authority, key, calendar = _ledger(tmp_path)
    _populate(ledger, authority, key, calendar)
    seal = ledger.seal(authority)
    assert __import__("json").loads(seal)["fresh_oos_status"] == "NOT_RUN"
    before = dict(authority.access)
    ledger.record_verified_gate(custody.VerifiedType1Gate(
        dataset_id=DATASET, custody_uid=CUSTODY, prereg_sha256=PREREG,
        seal_sha256=hashlib.sha256(seal).hexdigest(), commitment_sha256="3" * 64,
    ))
    assert authority.access == before
    authority.access = {"state": "RESERVED", "receipt_sha256": "4" * 64}
    receipt = ledger.recover(authority)
    assert receipt is not None
    assert __import__("json").loads(receipt)["decrypt_attempted_by_recovery"] is False
    assert ledger.status()["public_status"] == "CONSUMED_NOT_RUN"
    assert authority.consume_calls == 1 and authority.deny_calls == 0
    assert ledger.recover(authority) == receipt


def test_prepared_or_malformed_authority_response_blocks(tmp_path: Path) -> None:
    ledger, authority, _, _ = _ledger(tmp_path)
    authority.responses[1] = canonical_json_bytes({"state": "PREPARED"})
    with pytest.raises(custody.CustodyBlocked):
        ledger.reconcile_ordinal(authority, 1)
    assert ledger.status()["deny_state"] == "ISSUED"


def test_public_surface_has_no_fresh_content_capability() -> None:
    tree = ast.parse(inspect.getsource(custody))
    names = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    forbidden = {"open", "read", "read_payload", "decrypt", "encrypt", "reserve", "vault", "lease"}
    assert names.isdisjoint(forbidden)
    source = inspect.getsource(custody)
    assert "daily_v8_custody" not in source and "daily_v8_gate_receipt" not in source
