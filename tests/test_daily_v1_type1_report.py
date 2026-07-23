import hashlib
import json

import pytest

from stom_rl.daily_v1_type1_report import (
    IDENTITY, LOCKS, POLICY, Type1ReportError, commit_report_tip,
    insert_report_revision, materialize_report_revision, verify_report_catalog,
)


def _revision(number=1, *, failed=False):
    digest = hashlib.sha256(b"public-only-source").hexdigest()
    return {
        "schema_version": "kronos_type1_report_revision.v1",
        "revision_id": f"type1-r{number:04d}", "revision_ordinal": number,
        "identity": IDENTITY, "policy": POLICY,
        "result": {"run_state": "FAILED" if failed else "COMPLETE", "training_state": "FAILED" if failed else "COMPLETE", "reused_validation_state": "FAILED" if failed else "COMPLETE", "verdict": "NO_GO", "fresh_oos_state": "NOT_RUN", "fresh_oos_read_performed": False, "failures": ["CONTROL_GATE_FAILED"] if failed else []},
        "source_sha256": {"public_run_seal": digest}, "false_research_locks": LOCKS,
        "claims": {"symbols": ["000660"], "synthetic": "TRAIN_ONLY_SYNTHETIC_WIRING"},
    }


def test_catalog_is_alternating_immutable_and_failure_visible(tmp_path):
    first = insert_report_revision(tmp_path, _revision())
    first_materialized = materialize_report_revision(tmp_path, first["event_sha256"])
    second = insert_report_revision(tmp_path, _revision(2, failed=True))
    second_materialized = materialize_report_revision(tmp_path, second["event_sha256"])
    tip = commit_report_tip(tmp_path, second_materialized["event_sha256"])
    snapshot = verify_report_catalog(tmp_path)
    assert snapshot["state"] == "COMMITTED"
    assert snapshot["event_count"] == 4
    assert tip["latest_revision_event_sha256"] == second["event_sha256"]
    assert snapshot["revision"]["result"]["verdict"] == "NO_GO"
    report = (tmp_path / "type1_reports" / "objects" / f"type1-r0002-{second_materialized['html_sha256']}.html").read_text()
    assert "NOT_RUN" in report and "000660" in json.dumps(snapshot["revision"])
    for label in ("Overview", "Type1 identity", "Protocol and accounting", "Five-seed", "Reused-validation", "Fresh OOS", "Failures and integrity"):
        assert label in report
    with pytest.raises(Type1ReportError):
        insert_report_revision(tmp_path, _revision(3))
    with pytest.raises(Type1ReportError):
        materialize_report_revision(tmp_path, first["event_sha256"])


def test_catalog_fails_closed_for_tamper_gap_identity_and_orphan(tmp_path):
    inserted = insert_report_revision(tmp_path, _revision())
    event = next((tmp_path / "type1_reports" / "events").iterdir())
    event.write_bytes(event.read_bytes() + b" ")
    with pytest.raises(Type1ReportError):
        verify_report_catalog(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    bad = _revision(); bad["identity"] = dict(IDENTITY, dataset_id="near-match")
    with pytest.raises(Type1ReportError):
        insert_report_revision(other, bad)
    assert inserted["revision_id"] == "type1-r0001"
