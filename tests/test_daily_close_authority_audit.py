from __future__ import annotations

import json
from pathlib import Path

import pytest

from stom_rl.daily_close_research.authority import (
    AuthorityAuditError,
    audit_local_authority,
    classify_registered_codes,
    write_authority_audit,
)


def test_classification_separates_anchor_stable_eligible_and_excluded_codes() -> None:
    authority = {
        "authority_id": "authority-test",
        "anchor_date": "2017-12-29",
        "stable_symbols": ("005930",),
        "candidate_exclusions": (
            {"symbol": "068270", "reason": "not_effective_at_anchor"},
        ),
        "ranking": {"rows": ({"symbol": "000660"},)},
        "fresh_oos": {"status": "NOT_RUN", "no_read": True},
    }

    findings = classify_registered_codes(authority, ("005930", "000660", "068270", "999999"))

    assert tuple(item.disposition for item in findings) == (
        "STABLE_AT_ANCHOR",
        "ELIGIBLE_OUTSIDE_STABLE_TOP_500",
        "EXCLUDED_AT_ANCHOR",
        "NOT_CLASSIFIED",
    )
    assert findings[2].reason == "not_effective_at_anchor"


def test_audit_matches_daily_source_but_keeps_all_external_gates_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority_path = tmp_path / "authority.json"
    identity_path = tmp_path / "identity.json"
    authority_path.write_text("{}", encoding="utf-8")
    identity_path.write_text(
        json.dumps({"daily": {"sha256": "a" * 64, "size_bytes": 10, "mtime_ns": 1}}),
        encoding="utf-8",
    )
    authority = {
        "authority_id": "authority-test",
        "anchor_date": "2017-12-29",
        "stable_symbols": ("005930",),
        "candidate_exclusions": (),
        "ranking": {"rows": ({"symbol": "000660"},)},
        "fresh_oos": {"status": "NOT_RUN", "no_read": True},
    }
    monkeypatch.setattr(
        "stom_rl.daily_close_research.authority.load_type1_authority",
        lambda _path: authority,
    )

    receipt = audit_local_authority(
        authority_path,
        identity_path,
        database_sha256="a" * 64,
        codes=("005930", "000660"),
    )

    assert receipt.source_identity_matched is True
    assert receipt.registered_code_count == 2
    assert receipt.stable_at_anchor_count == 1
    assert receipt.eligible_outside_stable_count == 1
    assert receipt.external_attestation is False
    assert receipt.point_in_time_universe_proven is False
    assert receipt.available_at_proven is False
    assert receipt.official_price_identity_proven is False
    assert receipt.corporate_action_contract_proven is False
    assert receipt.fresh_oos_state == "NOT_RUN_NO_READ"
    assert receipt.verdict == "AUDITED_LOCAL_ANCHOR_NO_GO_EXTERNAL_AUTHORITY"


def test_source_identity_mismatch_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    authority_path = tmp_path / "authority.json"
    identity_path = tmp_path / "identity.json"
    authority_path.write_text("{}", encoding="utf-8")
    identity_path.write_text(
        json.dumps({"daily": {"sha256": "b" * 64, "size_bytes": 10, "mtime_ns": 1}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "stom_rl.daily_close_research.authority.load_type1_authority",
        lambda _path: {
            "authority_id": "authority-test",
            "anchor_date": "2017-12-29",
            "stable_symbols": (),
            "candidate_exclusions": (),
            "ranking": {"rows": ()},
            "fresh_oos": {"status": "NOT_RUN", "no_read": True},
        },
    )

    with pytest.raises(AuthorityAuditError, match="does not match"):
        audit_local_authority(
            authority_path,
            identity_path,
            database_sha256="a" * 64,
            codes=("005930",),
        )


def test_writer_preserves_code_identity_and_external_blockers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority_path = tmp_path / "authority.json"
    identity_path = tmp_path / "identity.json"
    authority_path.write_text("{}", encoding="utf-8")
    identity_path.write_text(
        json.dumps({"daily": {"sha256": "a" * 64}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "stom_rl.daily_close_research.authority.load_type1_authority",
        lambda _path: {
            "authority_id": "authority-test",
            "anchor_date": "2017-12-29",
            "stable_symbols": ("005930",),
            "candidate_exclusions": (),
            "ranking": {"rows": ()},
            "fresh_oos": {"status": "NOT_RUN", "no_read": True},
        },
    )
    receipt = audit_local_authority(
        authority_path,
        identity_path,
        database_sha256="a" * 64,
        codes=("005930",),
    )
    output = tmp_path / "authority_audit.json"

    write_authority_audit(receipt, output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["code_findings"][0]["code"] == "005930"
    assert payload["blockers"] == [
        "POINT_IN_TIME_UNIVERSE",
        "AVAILABLE_AT_PROVEN",
        "OFFICIAL_PRICE_IDENTITY",
        "CORPORATE_ACTION_CONTRACT",
    ]
