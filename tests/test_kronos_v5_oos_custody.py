"""Synthetic-only tests for V5 fresh-OOS custody denial/status mechanics."""
from __future__ import annotations

import base64
import builtins
import json

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from stom_rl import v5_oos_custody as custody

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "schemas" / "kronos_v5_oos_custody.v1.schema.json"
FIXTURE = json.loads((ROOT / "tests" / "data" / "kronos_v5_oos_custody_fixture.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 1, 2, 0, 10, tzinfo=timezone.utc)
UUIDS = {
    "calendar": "10000000-0000-4000-8000-000000000001",
    "custody": "10000000-0000-4000-8000-000000000002",
    "event0": "10000000-0000-4000-8000-000000000003",
    "event1": "10000000-0000-4000-8000-000000000004",
    "event2": "10000000-0000-4000-8000-000000000010",
    "event3": "10000000-0000-4000-8000-000000000011",
    "event4": "10000000-0000-4000-8000-000000000012",
    "capability": "10000000-0000-4000-8000-000000000005",
    "receipt": "10000000-0000-4000-8000-000000000006",
    "custody_key": "10000000-0000-4000-8000-000000000007",
    "capability_key": "10000000-0000-4000-8000-000000000008",
    "evaluator_key": "10000000-0000-4000-8000-000000000009",
}


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _key(start: int) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(bytes(range(start, start + 32)))


def _pub(key: Ed25519PrivateKey) -> str:
    return _b64u(key.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw))


def _signed(schema: str, statement: dict[str, Any], domain: bytes, key: Ed25519PrivateKey) -> bytes:
    signature = key.sign(domain + custody.canonical_bytes(statement))
    return custody.canonical_bytes({"schema": schema, "statement": statement, "signature": _b64u(signature)})


def _obj(raw: bytes) -> dict[str, Any]:
    return json.loads(raw)


def _validator():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def _sessions(count: int = 65) -> list[dict[str, Any]]:
    start = date(2026, 1, 2)
    rows = []
    for offset in range(count):
        session_date = (start + timedelta(days=offset)).isoformat()
        rows.append({
            "session_date": session_date,
            "market": "KRX",
            "is_open": True,
            "open_time": f"{session_date}T09:00:00+09:00",
            "close_time": f"{session_date}T15:30:00+09:00",
            "timezone": "Asia/Seoul",
        })
    return rows


def _calendar_raw(key: Ed25519PrivateKey, sessions: list[dict[str, Any]] | None = None) -> bytes:
    statement = {
        "schema": custody.CALENDAR_STATEMENT_SCHEMA,
        "calendar_uid": UUIDS["calendar"],
        "issued_at": "2026-01-01T00:00:00Z",
        "timezone": FIXTURE["calendar_timezone"],
        "columns": FIXTURE["calendar_columns"],
        "sessions": sessions or _sessions(),
    }
    return _signed(custody.CALENDAR_SCHEMA, statement, custody.CALENDAR_DOMAIN, key)


def _manifest_raw(calendar: custody.CalendarWindow, *, include_acl: bool = True, state: str = "SEALED") -> bytes:
    manifest = {
        "schema": custody.CUSTODY_MANIFEST_SCHEMA,
        "custody_uid": UUIDS["custody"],
        "custody_state": state,
        "preregistered_at": FIXTURE["preregistered_at"],
        "calendar_manifest_sha256": calendar.manifest_sha256,
        "first_open_sessions": list(calendar.first_open_sessions),
        "sealed_archive": {
            "content_kind": "SEALED_ARCHIVE_COMMITMENT",
            "archive_sha256": "a" * 64,
            "archive_byte_length": 4096,
            "archive_media_type": "application/octet-stream+sealed-oos",
            "locator_commitment_sha256": "b" * 64,
        },
        "acl": {
            "custodian_principal_uri": "agent://oos-custodian",
            "evaluator_principal_uri": "agent://oos-evaluator",
            "evaluator_action": custody.EVALUATOR_ACTION,
            "capability_ttl_seconds": 3600,
        },
        "created_at": "2026-01-01T00:00:00Z",
    }
    if not include_acl:
        manifest.pop("acl")
    return custody.canonical_bytes(manifest)


def _grant(principal: str, role: str, scope: str, purpose: str, key_id: str, key: Ed25519PrivateKey) -> dict[str, Any]:
    return {
        "schema": custody.AUTHORITY_GRANT_SCHEMA,
        "principal_uri": principal,
        "role": role,
        "scope": scope,
        "purpose": purpose,
        "key_id": key_id,
        "public_key": _pub(key),
    }


def _event_statement(world: dict[str, Any], *, sequence: int = 0, event_type: str = "GENESIS_SEALED", previous: str = custody.ZERO_SHA256, genesis: str = custody.ZERO_SHA256, archive_sha: str | None = None, capability_sha: str | None = None, release_receipt_sha: str | None = None) -> dict[str, Any]:
    role, action, state = {
        "GENESIS_SEALED": ("OOS_CUSTODIAN", "OOS_CUSTODY_SEAL_STATUS_ONLY", "SEALED"),
        "CAPABILITY_ISSUED": ("OOS_CUSTODIAN", "OOS_CAPABILITY_ISSUE_STATUS_ONLY", "CAPABILITY_ISSUED"),
        "CAPABILITY_CONSUMED": ("OOS_CUSTODIAN", "OOS_CAPABILITY_CONSUME_STATUS_ONLY", "CAPABILITY_CONSUMED"),
        "DENIED": ("OOS_CUSTODIAN", "OOS_CUSTODY_DENY_STATUS_ONLY", custody.STATUS_FRESH_OOS_NOT_AVAILABLE),
        "CONTAMINATED": ("OOS_CUSTODIAN", "OOS_CUSTODY_CONTAMINATE_STATUS_ONLY", custody.STATUS_CONTAMINATED),
        "RELEASE_RECEIVED": ("OOS_EVALUATOR", custody.EVALUATOR_ACTION, "RELEASE_RECEIVED"),
    }[event_type]
    return {
        "schema": custody.ACCESS_EVENT_STATEMENT_SCHEMA,
        "event_uid": UUIDS[f"event{sequence}"],
        "custody_uid": UUIDS["custody"],
        "sequence": sequence,
        "event_type": event_type,
        "actor_principal_uri": "agent://oos-custodian" if role == "OOS_CUSTODIAN" else "agent://oos-evaluator",
        "actor_role": role,
        "key_id": UUIDS["custody_key"] if role == "OOS_CUSTODIAN" else UUIDS["evaluator_key"],
        "scope": "OOS_CUSTODY" if role == "OOS_CUSTODIAN" else "OOS_EVALUATION",
        "purpose": "OOS_CUSTODY" if role == "OOS_CUSTODIAN" else "OOS_EVALUATION",
        "action": action,
        "custody_manifest_sha256": custody.sha256_hex(world["manifest_raw"]),
        "calendar_manifest_sha256": world["calendar"].manifest_sha256,
        "sealed_archive_sha256": archive_sha or "a" * 64,
        "capability_sha256": capability_sha or custody.ZERO_SHA256,
        "release_receipt_sha256": release_receipt_sha or custody.ZERO_SHA256,
        "previous_event_sha256": previous,
        "genesis_event_sha256": genesis,
        "occurred_at": f"2026-01-02T00:00:{sequence + 1:02d}Z",
        "next_custody_state": state,
    }


def _event_raw(world: dict[str, Any], **kwargs: Any) -> bytes:
    statement = _event_statement(world, **kwargs)
    key = world["keys"]["custody"] if statement["actor_role"] == "OOS_CUSTODIAN" else world["keys"]["evaluator"]
    return _signed(custody.ACCESS_EVENT_SCHEMA, statement, custody.ACCESS_EVENT_DOMAIN, key)


def _capability_raw(world: dict[str, Any], **overrides: Any) -> bytes:
    statement = {
        "schema": custody.CAPABILITY_STATEMENT_SCHEMA,
        "capability_uid": UUIDS["capability"],
        "custody_uid": UUIDS["custody"],
        "custodian_principal_uri": "agent://oos-custodian",
        "role": "OOS_CUSTODIAN",
        "key_id": UUIDS["capability_key"],
        "scope": "OOS_CAPABILITY",
        "purpose": "OOS_CAPABILITY",
        "evaluator_principal_uri": "agent://oos-evaluator",
        "evaluator_action": custody.EVALUATOR_ACTION,
        "calendar_manifest_sha256": world["calendar"].manifest_sha256,
        "custody_manifest_sha256": custody.sha256_hex(world["manifest_raw"]),
        "access_chain_head_sha256": world.get("issued_chain", world["chain"]).head_event_sha256,
        "sealed_archive_sha256": "a" * 64,
        "issued_at": "2026-01-02T00:00:00Z",
        "expires_at": "2026-01-02T00:59:00Z",
        "nonce": _b64u(bytes(range(32))),
        "max_uses": 1,
    }
    statement.update(overrides)
    return _signed(custody.CAPABILITY_SCHEMA, statement, custody.CAPABILITY_DOMAIN, world["keys"]["capability"])


def _release_raw(world: dict[str, Any], capability_sha: str, **overrides: Any) -> bytes:
    statement = {
        "schema": custody.RELEASE_RECEIPT_STATEMENT_SCHEMA,
        "receipt_uid": UUIDS["receipt"],
        "custody_uid": UUIDS["custody"],
        "capability_sha256": capability_sha,
        "calendar_manifest_sha256": world["calendar"].manifest_sha256,
        "custody_manifest_sha256": custody.sha256_hex(world["manifest_raw"]),
        "access_chain_head_sha256": world.get("consumed_chain", world["chain"]).head_event_sha256,
        "sealed_archive_sha256": "a" * 64,
        "evaluator_principal_uri": "agent://oos-evaluator",
        "role": "OOS_EVALUATOR",
        "key_id": UUIDS["evaluator_key"],
        "scope": "OOS_EVALUATION",
        "purpose": "OOS_EVALUATION",
        "evaluator_action": custody.EVALUATOR_ACTION,
        "issued_at": "2026-01-02T00:10:00Z",
        "status": custody.STATUS_RELEASE_RECEIVED,
        "result": custody.RESULT_NOT_RUN,
        "reason_codes": [custody.STATUS_ONLY_REASON],
        "fresh_oos_consumed": False,
        "raw_data_read": False,
        "archive_opened": False,
        "decrypt_attempted": False,
        "six_locks_false": dict(custody.SIX_LOCKS_FALSE),
    }
    statement.update(overrides)
    return _signed(custody.RELEASE_RECEIPT_SCHEMA, statement, custody.RELEASE_RECEIPT_DOMAIN, world["keys"]["evaluator"])


def _world() -> dict[str, Any]:
    keys = {"calendar": _key(0), "custody": _key(32), "capability": _key(64), "evaluator": _key(96)}
    calendar_raw = _calendar_raw(keys["calendar"])
    calendar = custody.verify_krx_calendar_manifest(calendar_raw, public_key=_pub(keys["calendar"]), preregistered_at=FIXTURE["preregistered_at"])
    manifest_raw = _manifest_raw(calendar)
    manifest = custody.verify_custody_manifest(manifest_raw, calendar=calendar)
    grants = [
        _grant("agent://oos-custodian", "OOS_CUSTODIAN", "OOS_CUSTODY", "OOS_CUSTODY", UUIDS["custody_key"], keys["custody"]),
        _grant("agent://oos-custodian", "OOS_CUSTODIAN", "OOS_CAPABILITY", "OOS_CAPABILITY", UUIDS["capability_key"], keys["capability"]),
        _grant("agent://oos-evaluator", "OOS_EVALUATOR", "OOS_EVALUATION", "OOS_EVALUATION", UUIDS["evaluator_key"], keys["evaluator"]),
    ]
    world: dict[str, Any] = {"keys": keys, "calendar_raw": calendar_raw, "calendar": calendar, "manifest_raw": manifest_raw, "manifest": manifest, "grants": grants}
    event0_raw = _event_raw(world)
    genesis_chain = custody.verify_access_chain((event0_raw,), custody_manifest_raw=manifest_raw, custody_manifest=manifest, authority_grants=grants)
    world.update(event0_raw=event0_raw, genesis_chain=genesis_chain, chain=genesis_chain)

    event1_raw = _event_raw(world, sequence=1, event_type="CAPABILITY_ISSUED", previous=genesis_chain.head_event_sha256, genesis=genesis_chain.genesis_event_sha256)
    issued_chain = custody.verify_access_chain((event0_raw, event1_raw), custody_manifest_raw=manifest_raw, custody_manifest=manifest, authority_grants=grants)
    world.update(event1_raw=event1_raw, issued_chain=issued_chain, chain=issued_chain)

    capability_raw = _capability_raw(world)
    capability = custody.verify_capability(capability_raw, custody_manifest_raw=manifest_raw, custody_manifest=manifest, chain=issued_chain, authority_grants=grants, now=NOW)
    event2_raw = _event_raw(world, sequence=2, event_type="CAPABILITY_CONSUMED", previous=issued_chain.head_event_sha256, genesis=issued_chain.genesis_event_sha256, capability_sha=capability.envelope_sha256)
    consumed_chain = custody.verify_access_chain((event0_raw, event1_raw, event2_raw), custody_manifest_raw=manifest_raw, custody_manifest=manifest, authority_grants=grants)
    world.update(event2_raw=event2_raw, consumed_chain=consumed_chain, capability_raw=capability_raw, capability=capability, chain=consumed_chain)

    release_raw = _release_raw(world, capability.envelope_sha256)
    release_sha = custody.sha256_hex(release_raw)
    event3_raw = _event_raw(world, sequence=3, event_type="RELEASE_RECEIVED", previous=consumed_chain.head_event_sha256, genesis=consumed_chain.genesis_event_sha256, capability_sha=capability.envelope_sha256, release_receipt_sha=release_sha)
    chain = custody.verify_access_chain((event0_raw, event1_raw, event2_raw, event3_raw), custody_manifest_raw=manifest_raw, custody_manifest=manifest, authority_grants=grants)
    world.update(event3_raw=event3_raw, access_event_raws=(event0_raw, event1_raw, event2_raw, event3_raw), chain=chain, release_raw=release_raw)
    return world


def _evaluate(world: dict[str, Any], store: custody.CapabilityConsumptionStore) -> custody.OosDecision:
    return custody.evaluate_status_release(
        calendar_manifest_raw=world["calendar_raw"],
        calendar_public_key=_pub(world["keys"]["calendar"]),
        custody_manifest_raw=world["manifest_raw"],
        authority_grants=world["grants"],
        access_event_raws=world["access_event_raws"],
        capability_raw=world["capability_raw"],
        release_receipt_raw=world["release_raw"],
        consumption_store=store,
        now=NOW,
    )


def test_schema_validates_closed_synthetic_status_only_wires_and_rejects_raw_fields() -> None:
    validator = _validator()
    schema_table = validator.schema["$defs"]["accessTransitionTable"]["const"]
    assert [(row["from"], row["event_type"], row["to"]) for row in schema_table] == [tuple(row) for row in FIXTURE["allowed_access_transitions"]]
    world = _world()
    for value in [_obj(world["calendar_raw"]), world["manifest"], *world["grants"], *[_obj(raw) for raw in world["access_event_raws"]], _obj(world["capability_raw"]), _obj(world["release_raw"]), custody.denial_receipt(custody.STATUS_FRESH_OOS_NOT_AVAILABLE, [custody.STATUS_FRESH_OOS_NOT_AVAILABLE])]:
        validator.validate(value)
    bad = _obj(world["release_raw"])
    bad["statement"]["raw"] = "forbidden"
    with pytest.raises(Exception):
        validator.validate(bad)


def test_signed_krx_calendar_enforces_exact_columns_timezone_unique_ascending_and_first_60() -> None:
    key = _key(0)
    raw = _calendar_raw(key)
    window = custody.verify_krx_calendar_manifest(raw, public_key=_pub(key), preregistered_at=FIXTURE["preregistered_at"])
    assert window.first_open_sessions == tuple(row["session_date"] for row in _sessions()[:60])
    assert len(window.first_open_sessions) == FIXTURE["first_open_session_count"]

    columns_bad = _obj(raw)
    columns_bad["statement"]["columns"] = list(reversed(columns_bad["statement"]["columns"]))
    with pytest.raises(custody.OosContaminationError):
        custody.verify_krx_calendar_manifest(_signed(custody.CALENDAR_SCHEMA, columns_bad["statement"], custody.CALENDAR_DOMAIN, key), public_key=_pub(key), preregistered_at=FIXTURE["preregistered_at"])

    duplicate = _sessions()
    duplicate[1]["session_date"] = duplicate[0]["session_date"]
    with pytest.raises(custody.OosContaminationError):
        custody.verify_krx_calendar_manifest(_calendar_raw(key, duplicate), public_key=_pub(key), preregistered_at=FIXTURE["preregistered_at"])

    with pytest.raises(custody.OosUnavailableError):
        custody.verify_krx_calendar_manifest(_calendar_raw(key, _sessions(59)), public_key=_pub(key), preregistered_at=FIXTURE["preregistered_at"])

    sig_bad = _obj(raw)
    sig_bad["signature"] = ("A" if sig_bad["signature"][-1] != "A" else "B") + sig_bad["signature"][1:]
    with pytest.raises(custody.OosContaminationError):
        custody.verify_krx_calendar_manifest(custody.canonical_bytes(sig_bad), public_key=_pub(key), preregistered_at=FIXTURE["preregistered_at"])


def test_missing_key_calendar_acl_or_authority_denies_not_run_without_consuming_capability() -> None:
    world = _world()
    missing_acl_raw = _manifest_raw(world["calendar"], include_acl=False)
    cases = [
        {"calendar_manifest_raw": None},
        {"calendar_public_key": None},
        {"custody_manifest_raw": missing_acl_raw},
        {"authority_grants": None},
        {"authority_grants": []},
    ]
    for override in cases:
        store = custody.InMemoryCapabilityConsumptionStore()
        args = {
            "calendar_manifest_raw": world["calendar_raw"],
            "calendar_public_key": _pub(world["keys"]["calendar"]),
            "custody_manifest_raw": world["manifest_raw"],
            "authority_grants": world["grants"],
            "access_event_raws": world["access_event_raws"],
            "capability_raw": world["capability_raw"],
            "release_receipt_raw": world["release_raw"],
            "consumption_store": store,
            "now": NOW,
        }
        args.update(override)
        decision = custody.evaluate_status_release(**args)
        assert decision.status == FIXTURE["denial_status"]
        assert decision.result == FIXTURE["result"]
        assert decision.capability_consumed is False
        assert decision.receipt["fresh_oos_consumed"] is False
        assert store.attempts == 0

    shared_key_world = _world()
    shared_key_world["grants"][2] = _grant("agent://oos-evaluator", "OOS_EVALUATOR", "OOS_EVALUATION", "OOS_EVALUATION", UUIDS["evaluator_key"], shared_key_world["keys"]["custody"])
    store = custody.InMemoryCapabilityConsumptionStore()
    assert _evaluate(shared_key_world, store).status == custody.STATUS_FRESH_OOS_NOT_AVAILABLE
    assert store.attempts == 0


def test_valid_status_release_consumes_once_replay_contaminates_and_no_real_oos_io(monkeypatch: pytest.MonkeyPatch) -> None:
    world = _world()

    def forbidden_io(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("real OOS archive/database/key IO attempted")

    monkeypatch.setattr(Path, "read_bytes", forbidden_io)
    monkeypatch.setattr(builtins, "open", forbidden_io)
    store = custody.InMemoryCapabilityConsumptionStore()
    decision = _evaluate(world, store)
    assert decision.status == custody.STATUS_RELEASE_RECEIVED
    assert decision.result == custody.RESULT_NOT_RUN
    assert decision.capability_consumed is True
    assert decision.receipt["statement"]["fresh_oos_consumed"] is False
    assert decision.receipt["statement"]["raw_data_read"] is False
    assert decision.receipt["statement"]["archive_opened"] is False
    assert decision.receipt["statement"]["decrypt_attempted"] is False
    assert store.attempts == 1

    replay = _evaluate(world, store)
    assert replay.status == custody.STATUS_CONTAMINATED
    assert replay.result == custody.RESULT_NOT_RUN
    assert replay.capability_consumed is False
    assert replay.receipt["fresh_oos_consumed"] is False
    assert store.attempts == 2


def test_access_hash_chain_fork_gap_signature_archive_and_hash_mismatch_contaminate() -> None:
    world = _world()
    event1 = world["event1_raw"]
    ok = custody.verify_access_chain((world["event0_raw"], event1), custody_manifest_raw=world["manifest_raw"], custody_manifest=world["manifest"], authority_grants=world["grants"])
    assert ok.head_event_sha256 == custody.sha256_hex(event1)
    assert ok.head_state == "CAPABILITY_ISSUED"
    assert world["chain"].head_state == custody.STATUS_RELEASE_RECEIVED
    assert world["chain"].capability_sha256 == world["capability"].envelope_sha256
    assert world["chain"].release_receipt_sha256 == custody.sha256_hex(world["release_raw"])

    genesis = world["genesis_chain"]
    gap = _event_raw(world, sequence=2, event_type="CAPABILITY_CONSUMED", previous=genesis.head_event_sha256, genesis=genesis.genesis_event_sha256, capability_sha=world["capability"].envelope_sha256)
    bad_previous = _event_raw(world, sequence=1, event_type="CAPABILITY_ISSUED", previous="f" * 64, genesis=genesis.genesis_event_sha256)
    bad_genesis = _event_raw(world, sequence=1, event_type="CAPABILITY_ISSUED", previous=genesis.head_event_sha256, genesis="f" * 64)
    bad_archive = _event_raw(world, sequence=1, event_type="CAPABILITY_ISSUED", previous=genesis.head_event_sha256, genesis=genesis.genesis_event_sha256, archive_sha="f" * 64)
    bad_signature = _obj(world["event0_raw"])
    bad_signature["signature"] = ("A" if bad_signature["signature"][-1] != "A" else "B") + bad_signature["signature"][1:]
    for raw_events in [
        (world["event0_raw"], gap),
        (world["event0_raw"], bad_previous),
        (world["event0_raw"], bad_genesis),
        (world["event0_raw"], bad_archive),
        (custody.canonical_bytes(bad_signature),),
        (world["event0_raw"], event1, event1),
    ]:
        with pytest.raises(custody.OosContaminationError):
            custody.verify_access_chain(raw_events, custody_manifest_raw=world["manifest_raw"], custody_manifest=world["manifest"], authority_grants=world["grants"])

def test_access_transition_table_rejects_skips_and_terminal_state_escape() -> None:
    world = _world()
    runtime_transitions = sorted(
        (from_state or "START", event_type, custody._ACCESS_EVENT_ACTIONS[event_type][2])
        for from_state, event_types in custody._ALLOWED_ACCESS_TRANSITIONS.items()
        for event_type in event_types
    )
    assert runtime_transitions == sorted(tuple(row) for row in FIXTURE["allowed_access_transitions"])
    assert sorted(custody._TERMINAL_CUSTODY_STATES) == sorted(FIXTURE["terminal_states"])
    genesis = world["genesis_chain"]
    skipped_release = _event_raw(
        world,
        sequence=1,
        event_type="RELEASE_RECEIVED",
        previous=genesis.head_event_sha256,
        genesis=genesis.genesis_event_sha256,
        capability_sha=world["capability"].envelope_sha256,
        release_receipt_sha=custody.sha256_hex(world["release_raw"]),
    )
    with pytest.raises(custody.OosContaminationError):
        custody.verify_access_chain((world["event0_raw"], skipped_release), custody_manifest_raw=world["manifest_raw"], custody_manifest=world["manifest"], authority_grants=world["grants"])

    denied = _event_raw(world, sequence=1, event_type="DENIED", previous=genesis.head_event_sha256, genesis=genesis.genesis_event_sha256)
    denied_chain = custody.verify_access_chain((world["event0_raw"], denied), custody_manifest_raw=world["manifest_raw"], custody_manifest=world["manifest"], authority_grants=world["grants"])
    assert denied_chain.head_state == custody.STATUS_FRESH_OOS_NOT_AVAILABLE
    denied_escape = _event_raw(world, sequence=2, event_type="CAPABILITY_ISSUED", previous=custody.sha256_hex(denied), genesis=genesis.genesis_event_sha256)
    with pytest.raises(custody.OosContaminationError, match="terminal"):
        custody.verify_access_chain((world["event0_raw"], denied, denied_escape), custody_manifest_raw=world["manifest_raw"], custody_manifest=world["manifest"], authority_grants=world["grants"])

    contaminated = _event_raw(world, sequence=1, event_type="CONTAMINATED", previous=genesis.head_event_sha256, genesis=genesis.genesis_event_sha256)
    contaminated_escape = _event_raw(world, sequence=2, event_type="CAPABILITY_ISSUED", previous=custody.sha256_hex(contaminated), genesis=genesis.genesis_event_sha256)
    with pytest.raises(custody.OosContaminationError, match="terminal"):
        custody.verify_access_chain((world["event0_raw"], contaminated, contaminated_escape), custody_manifest_raw=world["manifest_raw"], custody_manifest=world["manifest"], authority_grants=world["grants"])


def test_capability_ttl_nonce_evaluator_action_and_crash_store_fail_closed_before_read() -> None:
    world = _world()
    with pytest.raises(custody.OosContaminationError):
        custody.verify_capability(_capability_raw(world, expires_at="2026-01-02T01:01:00Z"), custody_manifest_raw=world["manifest_raw"], custody_manifest=world["manifest"], chain=world["issued_chain"], authority_grants=world["grants"], now=NOW)
    with pytest.raises(custody.OosContaminationError):
        custody.verify_capability(_capability_raw(world, nonce=_b64u(b"\x00" * 32)), custody_manifest_raw=world["manifest_raw"], custody_manifest=world["manifest"], chain=world["issued_chain"], authority_grants=world["grants"], now=NOW)
    with pytest.raises(custody.OosContaminationError):
        custody.verify_capability(world["capability_raw"], custody_manifest_raw=world["manifest_raw"], custody_manifest=world["manifest"], chain=world["genesis_chain"], authority_grants=world["grants"], now=NOW)
    with pytest.raises(custody.OosContaminationError):
        custody.verify_release_receipt(world["release_raw"], capability=world["capability"], custody_manifest_raw=world["manifest_raw"], custody_manifest=world["manifest"], chain=world["consumed_chain"], authority_grants=world["grants"])

    for field, value in (
        ("evaluator_action", "OOS_EVALUATION_READ_RAW"),
        ("evaluator_principal_uri", "agent://wrong-evaluator"),
    ):
        bad_capability = dict(world)
        bad_capability["capability_raw"] = _capability_raw(world, **{field: value})
        store = custody.InMemoryCapabilityConsumptionStore()
        decision = _evaluate(bad_capability, store)
        assert decision.status == custody.STATUS_CONTAMINATED
        assert decision.result == custody.RESULT_NOT_RUN
        assert store.attempts == 0

    class CrashStore:
        def __init__(self) -> None:
            self.attempts = 0

        def consume_if_absent(self, capability_sha256: str, nonce_sha256: str) -> bool:
            self.attempts += 1
            raise RuntimeError("simulated durable store crash")

    crash_store = CrashStore()
    crash_decision = _evaluate(world, crash_store)
    assert crash_decision.status == custody.STATUS_CONTAMINATED
    assert crash_decision.result == custody.RESULT_NOT_RUN
    assert crash_decision.capability_consumed is False
    assert crash_decision.receipt["raw_data_read"] is False
    assert crash_store.attempts == 1
