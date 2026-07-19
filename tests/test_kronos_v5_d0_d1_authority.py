from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from stom_rl.v5_authority import (
    AuthorityVerificationError,
    D0_PRICE_BASIS_BLOCKER,
    D0_PRICE_BASIS_RECORD_COUNT_EQUATION,
    D0_PRICE_BASIS_VERIFIED_COLLAPSE_EQUATION,
    D1_UNIVERSE_BLOCKER,
    D1_UNIVERSE_CSV_COLUMNS,
    D1_UNIVERSE_ROW_COUNT_EQUATION,
    D1_UNIVERSE_VERIFIED_ZERO_EQUATION,
    canonical_bytes,
    evaluate_d0_price_basis_evidence,
    evaluate_d1_universe_evidence,
    read_d0_price_basis_evidence,
    read_d1_universe_evidence,
    verify_d0_price_basis_evidence,
    verify_d1_universe_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "docs" / "schemas"
DATA = ROOT / "tests" / "data"
D0_FIXTURE = DATA / "kronos_d0_price_basis_evidence_synthetic.v1.json"
D1_FIXTURE = DATA / "kronos_d1_universe_evidence_synthetic.v1.json"
D1_CSV = b"code,market,issuer_name,security_type,listing_status,disposition,reason,review_decision\n005930,KOSPI,Samsung Electronics,COMMON,LISTED,INCLUDE,synthetic parser row,APPROVED\n000660,KOSPI,SK hynix,COMMON,LISTED,EXCLUDE,synthetic parser exclusion,APPROVED\n"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema(name: str) -> Draft202012Validator:
    schema = _load(SCHEMAS / name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _bind_attestations(evidence: dict[str, Any]) -> dict[str, Any]:
    digest = hashlib.sha256(canonical_bytes(evidence["statement"])).hexdigest()
    for attestation in evidence["attestations"].values():
        attestation["payload_sha256"] = digest
    return evidence


def _trusted(_: dict[str, Any], __: bytes) -> bool:
    return True


def _real_d0() -> dict[str, Any]:
    evidence = copy.deepcopy(_load(D0_FIXTURE))
    evidence["statement"]["evidence_kind"] = "REAL"
    evidence["status"] = "VERIFIED"
    evidence["blocking_codes"] = []
    return _bind_attestations(evidence)


def _real_d1() -> dict[str, Any]:
    evidence = copy.deepcopy(_load(D1_FIXTURE))
    evidence["statement"]["evidence_kind"] = "REAL"
    evidence["status"] = "VERIFIED"
    evidence["blocking_codes"] = []
    return _bind_attestations(evidence)


def test_d0_d1_schemas_accept_synthetic_parser_fixtures_and_reject_status_mismatch() -> None:
    d0_validator = _schema("kronos_d0_price_basis_evidence.v1.schema.json")
    d1_validator = _schema("kronos_d1_universe_evidence.v1.schema.json")
    d0 = _load(D0_FIXTURE)
    d1 = _load(D1_FIXTURE)
    d0_validator.validate(d0)
    d1_validator.validate(d1)
    bad = copy.deepcopy(d0)
    bad["status"] = "VERIFIED"
    assert list(d0_validator.iter_errors(bad))
    bad = copy.deepcopy(d1)
    bad["blocking_codes"] = []
    assert list(d1_validator.iter_errors(bad))


def test_synthetic_fixture_signatures_parse_but_never_verify() -> None:
    d0 = evaluate_d0_price_basis_evidence(_load(D0_FIXTURE), signature_verifier=_trusted)
    d1 = evaluate_d1_universe_evidence(_load(D1_FIXTURE), csv_bytes=D1_CSV, signature_verifier=_trusted)
    assert d0["status"] == "BLOCKED" and d0["blocking_codes"] == [D0_PRICE_BASIS_BLOCKER]
    assert d1["status"] == "BLOCKED" and d1["blocking_codes"] == [D1_UNIVERSE_BLOCKER]


def test_absent_or_untrusted_real_evidence_paths_fail_closed_without_aliasing() -> None:
    for result in (
        read_d0_price_basis_evidence(),
        read_d1_universe_evidence(),
        read_d0_price_basis_evidence("tests/data/kronos_d0_price_basis_evidence_synthetic.v1.json"),
        read_d1_universe_evidence("_database/evidence/universe/../price_basis/latest.json"),
    ):
        assert result["status"] == "BLOCKED"
    assert read_d0_price_basis_evidence()["blocking_codes"] == [D0_PRICE_BASIS_BLOCKER]
    assert read_d1_universe_evidence()["blocking_codes"] == [D1_UNIVERSE_BLOCKER]


def test_d0_verifies_only_exact_dataset_range_hash_ohlc_actions_review_and_independent_attestations() -> None:
    evidence = _real_d0()
    result = verify_d0_price_basis_evidence(evidence, signature_verifier=_trusted)
    assert result["status"] == "VERIFIED" and result["blocking_codes"] == []
    assert evidence["statement"]["equations"] == {
        "record_count": D0_PRICE_BASIS_RECORD_COUNT_EQUATION,
        "verified_collapse": D0_PRICE_BASIS_VERIFIED_COLLAPSE_EQUATION,
    }
    assert evaluate_d0_price_basis_evidence(evidence)["status"] == "BLOCKED"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda e: e["statement"]["dataset"].__setitem__("artifact_path", "tests/data/alias.json"),
        lambda e: e["statement"]["dataset"].__setitem__("source_database_sha256", "g" * 64),
        lambda e: e["statement"]["price_basis"]["ohlc_semantics"].__setitem__("close", "ADJUSTED_CLOSE"),
        lambda e: e["statement"]["equations"].__setitem__("record_count", "record_count >= matched_count"),
        lambda e: e["statement"]["corporate_actions"]["splits"].__setitem__("record_count", 1),
        lambda e: e["statement"]["corporate_actions"]["splits"].__setitem__("missing_count", 1),
        lambda e: e["statement"].__setitem__("conflicts", ["issuer/reviewer mismatch"]),
        lambda e: e["attestations"]["reviewer"].__setitem__("principal_uri", e["attestations"]["issuer"]["principal_uri"]),
        lambda e: e.__setitem__("blocking_codes", [D0_PRICE_BASIS_BLOCKER]),
    ],
)
def test_d0_adversarial_predicates_remain_blocked(mutate) -> None:
    evidence = _real_d0()
    mutate(evidence)
    _bind_attestations(evidence)
    result = evaluate_d0_price_basis_evidence(evidence, signature_verifier=_trusted)
    assert result["status"] == "BLOCKED" and result["blocking_codes"] == [D0_PRICE_BASIS_BLOCKER]
    with pytest.raises(AuthorityVerificationError, match=D0_PRICE_BASIS_BLOCKER):
        verify_d0_price_basis_evidence(evidence, signature_verifier=_trusted)


def test_d1_verifies_only_exact_csv_columns_equations_counts_hashes_and_independent_attestations() -> None:
    evidence = _real_d1()
    result = verify_d1_universe_evidence(evidence, csv_bytes=D1_CSV, signature_verifier=_trusted)
    assert result["status"] == "VERIFIED" and result["blocking_codes"] == []
    assert tuple(evidence["statement"]["csv"]["columns"]) == D1_UNIVERSE_CSV_COLUMNS
    assert evidence["statement"]["equations"] == {
        "row_count": D1_UNIVERSE_ROW_COUNT_EQUATION,
        "verified_zero_blockers": D1_UNIVERSE_VERIFIED_ZERO_EQUATION,
    }
    assert next(csv.DictReader(io.StringIO(D1_CSV.decode("utf-8"))))["code"] == "005930"
    assert evaluate_d1_universe_evidence(evidence, csv_bytes=D1_CSV)["status"] == "BLOCKED"


def _replace_csv(evidence: dict[str, Any], csv_bytes: bytes, counts: dict[str, int] | None = None) -> None:
    evidence["statement"]["csv"]["sha256"] = hashlib.sha256(csv_bytes).hexdigest()
    evidence["statement"]["csv"]["byte_length"] = len(csv_bytes)
    if counts is not None:
        evidence["statement"]["counts"].update(counts)
    _bind_attestations(evidence)


@pytest.mark.parametrize(
    "mutate,csv_bytes",
    [
        (lambda e: e["statement"]["csv"].__setitem__("columns", list(reversed(D1_UNIVERSE_CSV_COLUMNS))), D1_CSV),
        (lambda e: e["statement"]["equations"].__setitem__("row_count", "row_count == included_count + excluded_count"), D1_CSV),
        (lambda e: e["statement"]["counts"].__setitem__("conflict_count", 1), D1_CSV),
        (lambda e: e["statement"].__setitem__("conflicts", ["duplicate issuer"]), D1_CSV),
        (lambda e: e["attestations"]["reviewer"].__setitem__("signature", e["attestations"]["issuer"]["signature"]), D1_CSV),
        (lambda e: _replace_csv(e, D1_CSV.replace(b"005930", b"A05930")), D1_CSV.replace(b"005930", b"A05930")),
        (lambda e: _replace_csv(e, D1_CSV.replace(b"000660", b"005930")), D1_CSV.replace(b"000660", b"005930")),
        (lambda e: _replace_csv(e, D1_CSV.replace(b"EXCLUDE", b"QUARANTINE"), {"included_count": 1, "excluded_count": 0, "quarantine_count": 1}), D1_CSV.replace(b"EXCLUDE", b"QUARANTINE")),
    ],
)
def test_d1_adversarial_predicates_remain_blocked(mutate, csv_bytes: bytes) -> None:
    evidence = _real_d1()
    mutate(evidence)
    _bind_attestations(evidence)
    result = evaluate_d1_universe_evidence(evidence, csv_bytes=csv_bytes, signature_verifier=_trusted)
    assert result["status"] == "BLOCKED" and result["blocking_codes"] == [D1_UNIVERSE_BLOCKER]
    with pytest.raises(AuthorityVerificationError, match=D1_UNIVERSE_BLOCKER):
        verify_d1_universe_evidence(evidence, csv_bytes=csv_bytes, signature_verifier=_trusted)
