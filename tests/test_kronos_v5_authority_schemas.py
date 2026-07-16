"""Frozen literal vectors for the normative Kronos v2 authority verifier."""

from __future__ import annotations

import base64
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from itertools import product
from pathlib import Path

import nacl.signing
import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from stom_rl.v5_authority import (
    ATTESTATION_DOMAIN, LIFECYCLE_DOMAIN, AuthorityVerificationError,
    InMemoryNonceReplayStore, canonical_bytes, parse_canonical_json,
    sha256_identity, verify_attestation, verify_lifecycle,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "docs" / "schemas"
VECTORS = ROOT / "tests" / "data" / "kronos_attestation_v2_vectors.json"
T0 = datetime(2026, 7, 15, 0, 11, tzinfo=timezone.utc)
T_REVOKED = datetime(2026, 7, 15, 0, 21, tzinfo=timezone.utc)


def _load(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def _validator(name: str) -> Draft202012Validator:
    resources = [_load(n) for n in ("kronos_gjc_authority.v2.schema.json", "kronos_authority_lifecycle.v2.schema.json", "kronos_attestation.v2.schema.json")]
    return Draft202012Validator(_load(name), registry=Registry().with_resources((x["$id"], Resource.from_contents(x)) for x in resources))


@pytest.fixture(scope="module")
def vectors() -> dict:
    return json.loads(VECTORS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def wire(vectors: dict) -> dict[str, bytes]:
    return {name: vectors[f"{name}_raw"].encode() for name in ("genesis", "rotation", "revocation", "attestation")}


def _obj(raw: bytes) -> dict:
    return json.loads(raw)


def _raw(value: dict) -> bytes:
    return canonical_bytes(value)

def _scalar_paths(value: object, prefix: tuple[object, ...] = ()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _scalar_paths(child, (*prefix, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _scalar_paths(child, (*prefix, index))
    else:
        yield prefix


def _replace_leaf(value: dict, path: tuple[object, ...]) -> None:
    target: object = value
    for part in path[:-1]:
        target = target[part]  # type: ignore[index]
    old = target[path[-1]]  # type: ignore[index]
    target[path[-1]] = old + 1 if isinstance(old, int) else ("x" if old != "x" else "y")  # type: ignore[index]
def _resign_lifecycle(envelope: dict, seed: bytes) -> bytes:
    envelope["signature"] = base64.urlsafe_b64encode(
        nacl.signing.SigningKey(seed).sign(
            LIFECYCLE_DOMAIN + canonical_bytes(envelope["statement"])
        ).signature
    ).rstrip(b"=").decode()
    return _raw(envelope)



def _reject(call) -> None:
    with pytest.raises(AuthorityVerificationError):
        call()


def _life(v: dict, w: dict[str, bytes], raw: bytes | None = None, history=(), when=T0):
    return verify_lifecycle(raw or w["rotation"], pinned_root_public_key=v["root_public_key"], pinned_root_key_id=v["root_key_id"], pinned_genesis_envelope_sha256=v["pinned_genesis_envelope_sha256"], prior_lifecycles=history, verification_time=when)


def _att(v: dict, w: dict[str, bytes], raw: bytes | None = None, **extra):
    args = dict(payload_bytes=v["payload_utf8"].encode(), payload_schema=v["payload_schema"], scope="D0_EVIDENCE", referenced_lifecycle=w["rotation"], current_lifecycle=w["rotation"], lifecycle_history=(w["genesis"],), pinned_root_public_key=v["root_public_key"], pinned_root_key_id=v["root_key_id"], pinned_genesis_envelope_sha256=v["pinned_genesis_envelope_sha256"], verification_time=T0, role_validity_caps={"D0_ISSUER": timedelta(minutes=15)}, nonce_store=InMemoryNonceReplayStore())
    args.update(extra)
    return verify_attestation(raw or w["attestation"], **args)


def test_vector_metadata_canonical_literals_and_schema(vectors: dict, wire: dict[str, bytes]) -> None:
    assert vectors["vector_version"] == "kronos_attestation_v2_fixed_seed_2"
    assert vectors["canonicalization"] == "RFC 8785 JCS; signatures are Ed25519(domain || JCS(statement))."
    assert vectors["fixed_seed"] == "root=bytes(0..31); orchestrator=bytes(32..63); d0_issuer=bytes(64..95)"
    assert vectors["domains"] == {
        "lifecycle": LIFECYCLE_DOMAIN.decode("latin1"),
        "attestation": ATTESTATION_DOMAIN.decode("latin1"),
    }
    for name in wire:
        envelope = parse_canonical_json(wire[name])
        assert canonical_bytes(envelope["statement"]) == vectors["statement_raw"][name].encode()
    assert sha256_identity(_obj(wire["genesis"])) == vectors["pinned_genesis_envelope_sha256"]
    lifecycle = _validator("kronos_authority_lifecycle.v2.schema.json")
    for name in ("genesis", "rotation", "revocation"):
        lifecycle.validate(_obj(wire[name]))
    _validator("kronos_attestation.v2.schema.json").validate(_obj(wire["attestation"]))


def test_exact_authority_matrix_and_unknown_enums_fail(vectors: dict, wire: dict[str, bytes]) -> None:
    defs = _load("kronos_gjc_authority.v2.schema.json")["$defs"]
    valid = {tuple(x) for x in vectors["positive_authority"]}
    validator = _validator("kronos_gjc_authority.v2.schema.json")
    for grant in product(defs["role"]["enum"], defs["scope"]["enum"], defs["purpose"]["enum"]):
        assert (not list(validator.iter_errors({"schema": "kronos_gjc_authority.v2", "authority": dict(zip(("role", "scope", "purpose"), grant))}))) is (grant in valid)
    lifecycle = _obj(wire["rotation"])
    lifecycle["statement"]["principals"][1]["roles"] = ["UNKNOWN_ROLE"]
    _reject(lambda: _life(vectors, wire, _raw(lifecycle), history=(wire["genesis"],)))


def test_pinned_contiguous_chain_benign_rotation_and_later_revocation(vectors: dict, wire: dict[str, bytes]) -> None:
    assert _life(vectors, wire, wire["genesis"], when=datetime(2026, 7, 15, 0, 1, tzinfo=timezone.utc)) == vectors["sha256"]["genesis"]
    assert _life(vectors, wire, history=(wire["genesis"],)) == vectors["sha256"]["rotation"]
    assert _life(vectors, wire, wire["revocation"], history=(wire["genesis"], wire["rotation"]), when=T_REVOKED) == vectors["sha256"]["revocation"]
    _att(vectors, wire)
    _reject(lambda: _att(vectors, wire, current_lifecycle=wire["revocation"], lifecycle_history=(wire["genesis"], wire["rotation"]), verification_time=T_REVOKED))
def test_independent_lanes_cannot_share_a_principal_or_key(vectors: dict, wire: dict[str, bytes]) -> None:
    lifecycle = _obj(wire["rotation"])
    issuer = lifecycle["statement"]["principals"][1]
    issuer["roles"] = ["D0_ISSUER", "D0_REVIEWER"]
    _reject(lambda: _life(vectors, wire, _raw(lifecycle), history=(wire["genesis"],)))



@pytest.mark.parametrize("field,value", [("authority_epoch", "66666666-6666-4666-8666-666666666666"), ("roster_version", 1), ("effective_at", "2026-07-15T00:01:59Z"), ("previous_authority_envelope_sha256", "f" * 64)])
def test_epoch_version_window_predecessor_continuity_fail_closed(vectors: dict, wire: dict[str, bytes], field: str, value: object) -> None:
    altered = _obj(wire["rotation"])
    altered["statement"][field] = value
    _reject(lambda: _life(vectors, wire, _raw(altered), history=(wire["genesis"],)))
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("authority_epoch", "66666666-6666-4666-8666-666666666666"),
        ("roster_version", 1),
        ("effective_at", "2026-07-15T00:01:59Z"),
    ],
)
def test_validly_resigned_epoch_version_and_window_negatives(vectors: dict, wire: dict[str, bytes], field: str, value: object) -> None:
    altered = _obj(wire["rotation"])
    altered["statement"][field] = value
    raw = _resign_lifecycle(altered, bytes(range(32, 64)))
    _reject(lambda: _life(vectors, wire, raw, history=(wire["genesis"],)))

def test_validly_resigned_key_ordering_semantic_negative(vectors: dict, wire: dict[str, bytes]) -> None:
    altered = _obj(wire["rotation"])
    issuer_keys = altered["statement"]["principals"][1]["keys"]
    extra = dict(issuer_keys[0])
    extra["key_id"] = "66666666-6666-4666-8666-666666666666"
    extra["public_key"] = base64.urlsafe_b64encode(b"z" * 32).rstrip(b"=").decode()
    issuer_keys.insert(0, extra)
    raw = _resign_lifecycle(altered, bytes(range(32, 64)))
    _reject(lambda: _life(vectors, wire, raw, history=(wire["genesis"],)))


def test_validly_resigned_revoke_then_reactivate_is_terminal(vectors: dict, wire: dict[str, bytes]) -> None:
    revoked = _obj(wire["revocation"])
    revoked["statement"]["principals"][0]["keys"][0]["not_after"] = "2026-07-15T00:40:00Z"
    revoked_raw = _resign_lifecycle(revoked, bytes(range(32, 64)))
    reactivated = _obj(revoked_raw)
    statement = reactivated["statement"]
    statement["sequence"] = 4
    statement["roster_version"] = 4
    statement["previous_authority_envelope_sha256"] = sha256_identity(_obj(revoked_raw))
    statement["issued_at"] = "2026-07-15T00:30:00Z"
    statement["effective_at"] = "2026-07-15T00:30:00Z"
    statement["expires_at"] = "2026-07-15T00:40:00Z"
    key = statement["principals"][1]["keys"][0]
    key.update(status="ACTIVE", revoked_at=None, revocation_reason=None)
    reactivated_raw = _resign_lifecycle(reactivated, bytes(range(32, 64)))
    _reject(lambda: _life(
        vectors,
        wire,
        reactivated_raw,
        history=(wire["genesis"], wire["rotation"], revoked_raw),
        when=datetime(2026, 7, 15, 0, 31, tzinfo=timezone.utc),
    ))



def test_external_root_pin_raw_canonical_and_length_guards(vectors: dict, wire: dict[str, bytes]) -> None:
    _reject(lambda: parse_canonical_json(b" " + wire["genesis"]))
    _reject(lambda: parse_canonical_json(b'{"schema":"x","schema":"x"}'))
    _reject(lambda: verify_lifecycle(wire["genesis"], pinned_root_public_key=b"x" * 32, pinned_root_key_id=vectors["root_key_id"], pinned_genesis_envelope_sha256=vectors["pinned_genesis_envelope_sha256"], verification_time=T0))
    bad = _obj(wire["genesis"]); bad["signature"] = "A" * 85
    _reject(lambda: _life(vectors, wire, _raw(bad), when=datetime(2026, 7, 15, 0, 1, tzinfo=timezone.utc)))
    bad = _obj(wire["genesis"]); bad["statement"]["principals"][0]["keys"][0]["public_key"] = "A" * 42
    _reject(lambda: _life(vectors, wire, _raw(bad), when=datetime(2026, 7, 15, 0, 1, tzinfo=timezone.utc)))


def test_pynacl_and_pinned_noble_independently_verify_signatures(vectors: dict, wire: dict[str, bytes]) -> None:
    entries = [
        ("genesis", vectors["root_public_key"], LIFECYCLE_DOMAIN),
        ("rotation", _obj(wire["genesis"])["statement"]["principals"][0]["keys"][0]["public_key"], LIFECYCLE_DOMAIN),
        ("revocation", _obj(wire["rotation"])["statement"]["principals"][0]["keys"][0]["public_key"], LIFECYCLE_DOMAIN),
        ("attestation", _obj(wire["rotation"])["statement"]["principals"][1]["keys"][0]["public_key"], ATTESTATION_DOMAIN),
    ]
    for name, public_key, domain in entries:
        envelope = _obj(wire[name])
        nacl.signing.VerifyKey(base64.urlsafe_b64decode(public_key + "==")).verify(
            domain + canonical_bytes(envelope["statement"]),
            base64.urlsafe_b64decode(envelope["signature"] + "=="),
        )
    script = """
import { verify, etc } from '@noble/ed25519';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
etc.sha512Sync = (...messages) => new Uint8Array(createHash('sha512').update(Buffer.concat(messages.map(x => Buffer.from(x)))).digest());
const x = JSON.parse(fs.readFileSync(process.argv[1]));
const b = value => Uint8Array.from(Buffer.from(value, 'base64url'));
const utf8 = value => new TextEncoder().encode(value);
const keys = {
  genesis: x.root_public_key,
  rotation: JSON.parse(x.genesis_raw).statement.principals[0].keys[0].public_key,
  revocation: JSON.parse(x.rotation_raw).statement.principals[0].keys[0].public_key,
  attestation: JSON.parse(x.rotation_raw).statement.principals[1].keys[0].public_key,
};
for (const name of ['genesis', 'rotation', 'revocation', 'attestation']) {
  const envelope = JSON.parse(x[`${name}_raw`]);
  const domain = name === 'attestation' ? 'KRONOS-ATTESTATION-V2\\0' : 'KRONOS-AUTHORITY-LIFECYCLE-V2\\0';
  const message = new Uint8Array([...utf8(domain), ...utf8(x.statement_raw[name])]);
  if (!await verify(b(envelope.signature), message, b(keys[name]))) process.exit(1);
}
"""
    subprocess.run(["node", "--input-type=module", "-e", script, str(VECTORS)], cwd=ROOT / "webui" / "v2_src", check=True, timeout=15)


def test_nonce_bytes_non_ascii_atomic_replay_and_public_concurrency(vectors: dict, wire: dict[str, bytes]) -> None:
    store = InMemoryNonceReplayStore()
    _att(vectors, wire, nonce_store=store)
    _reject(lambda: _att(vectors, wire, nonce_store=store))
    key = ("agent://d0-issuer", "33333333-3333-4333-8333-333333333333", "D0_EVIDENCE", bytes(range(128, 160)))
    concurrent_store = InMemoryNonceReplayStore()
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(concurrent_store.consume_if_absent, [key] * 64))
    assert results.count(True) == 1
    assert results.count(False) == 63


@pytest.mark.parametrize("override", [{"payload_bytes": b"wrong"}, {"payload_schema": "wrong"}, {"scope": "D1_EVIDENCE"}, {"role_validity_caps": {}}, {"role_validity_caps": {"D0_ISSUER": timedelta(minutes=14)}}])
def test_payload_scope_and_role_cap_boundaries_fail(vectors: dict, wire: dict[str, bytes], override: dict) -> None:
    _reject(lambda: _att(vectors, wire, **override))
    _att(vectors, wire, role_validity_caps={"D0_ISSUER": timedelta(minutes=15)})


def test_frozen_leaf_status_and_order_mutations_fail(vectors: dict, wire: dict[str, bytes]) -> None:
    lifecycle = _obj(wire["rotation"])
    lifecycle["statement"]["principals"].reverse()
    _reject(lambda: _life(vectors, wire, _raw(lifecycle), history=(wire["genesis"],)))
    for path in (("principals", 1, "status"), ("principals", 1, "keys", 0, "status"), ("principals", 1, "keys", 0, "not_after")):
        altered = _obj(wire["rotation"]); item = altered["statement"]
        for leaf in path[:-1]: item = item[leaf]
        item[path[-1]] = "REVOKED" if path[-1] == "status" else "2026-07-15T00:10:00Z"
        _reject(lambda altered=altered: _att(vectors, wire, current_lifecycle=_raw(altered)))
    for leaf in ("payload_sha256", "payload_byte_length", "nonce", "authority_envelope_sha256", "expires_at"):
        altered = _obj(wire["attestation"])
        altered["statement"][leaf] = 18 if leaf == "payload_byte_length" else ("0" * 64 if leaf in {"payload_sha256", "authority_envelope_sha256"} else ("A" * 43 if leaf == "nonce" else "2026-07-15T00:09:00Z"))
        _reject(lambda altered=altered: _att(vectors, wire, _raw(altered)))
def test_every_frozen_statement_leaf_is_integrity_protected(vectors: dict, wire: dict[str, bytes]) -> None:
    for name, history, when in (
        ("genesis", (), datetime(2026, 7, 15, 0, 1, tzinfo=timezone.utc)),
        ("rotation", (wire["genesis"],), T0),
    ):
        original = _obj(wire[name])
        for path in _scalar_paths(original["statement"]):
            altered = _obj(wire[name])
            _replace_leaf(altered["statement"], path)
            _reject(lambda altered=altered, history=history, when=when: _life(vectors, wire, _raw(altered), history=history, when=when))
    original = _obj(wire["attestation"])
    for path in _scalar_paths(original["statement"]):
        altered = _obj(wire["attestation"])
        _replace_leaf(altered["statement"], path)
        _reject(lambda altered=altered: _att(vectors, wire, _raw(altered)))

