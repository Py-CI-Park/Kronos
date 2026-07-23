import json

import pytest

from stom_rl.daily_v1_type1_report import (
    IDENTITY, LOCKS, POLICY, REPLACEMENT_OUTER_IDENTITY, Type1ReportError, commit_report_tip,
    insert_report_revision, materialize_report_revision, report_source_sha256,
    verify_report_catalog,
)


def _sources(run):
    run.mkdir(parents=True, exist_ok=True)
    (run.parent / "dataset_manifest.json").write_bytes(b"dataset")
    (run.parent / "public_rows.json").write_bytes(b"rows")
    (run / "run_manifest.json").write_bytes(b"run")
    (run / "receipt.json").write_bytes(b"receipt")
    outer = {"identity": IDENTITY}
    (run / "type1_identity.json").write_text(json.dumps(outer, sort_keys=True, separators=(",", ":")))
    (run / "p6_public_run_seal.json").write_text(json.dumps({**outer, "fresh_oos": {"state": "NOT_RUN", "payload_read": False}}, sort_keys=True, separators=(",", ":")))
    (run / "deployment_lock.json").write_text(json.dumps({**outer, "locks": LOCKS}, sort_keys=True, separators=(",", ":")))
    (run / "attempt_parent.json").write_text(json.dumps({**outer, "parent_identity": {"dataset_id": "type1-close-20260803-002", "train_id": "type1-public-002", "train_run_id": "train_type1-public-002"}}, sort_keys=True, separators=(",", ":")))
    (run / "authority.json").write_text(json.dumps({**outer, "authority_id": REPLACEMENT_OUTER_IDENTITY["authority_id"]}, sort_keys=True, separators=(",", ":")))
    for kind in ("primary", "shuffled_reward"):
        for seed in range(5):
            member = run / kind / f"seed_{seed}"
            member.mkdir(parents=True, exist_ok=True)
            (member / "final_model.zip").write_bytes(f"{kind}-{seed}-model".encode())
            (member / "normalizer.pkl").write_bytes(f"{kind}-{seed}-normalizer".encode())
    return report_source_sha256(run)


def _revision(run, number=1, *, failed=False):
    sources = _sources(run)
    evidence = {label: sources[label] for label in (
        "type1_identity", "public_run_seal", "deployment_lock", "attempt_parent",
        "amendment", "protocol", "preregistration", "authority", "builder_source",
    )}
    return {
        "schema_version": "kronos_type1_report_revision.v2",
        "revision_id": f"type1-r{number:04d}", "revision_ordinal": number,
        "identity": IDENTITY, "policy": POLICY,
        "result": {"run_state": "FAILED" if failed else "COMPLETE", "training_state": "FAILED" if failed else "COMPLETE", "reused_validation_state": "FAILED" if failed else "COMPLETE", "verdict": "NO_GO", "fresh_oos_state": "NOT_RUN", "fresh_oos_read_performed": False, "failures": ["CONTROL_GATE_FAILED"] if failed else []},
        "source_sha256": sources, "evidence": evidence, "false_research_locks": LOCKS,
        "claims": {"symbols": ["000660"], "synthetic": "TRAIN_ONLY_SYNTHETIC_WIRING"},
    }


def test_catalog_is_alternating_immutable_and_failure_visible(tmp_path):
    first = insert_report_revision(tmp_path, _revision(tmp_path))
    first_materialized = materialize_report_revision(tmp_path, first["event_sha256"])
    second = insert_report_revision(tmp_path, _revision(tmp_path, 2, failed=True))
    second_materialized = materialize_report_revision(tmp_path, second["event_sha256"])
    tip = commit_report_tip(tmp_path, second_materialized["event_sha256"])
    snapshot = verify_report_catalog(tmp_path)
    assert snapshot["state"] == "COMMITTED"
    assert snapshot["event_count"] == 4
    assert tip["latest_revision_event_sha256"] == second["event_sha256"]
    assert snapshot["revision"]["result"]["verdict"] == "NO_GO"
    report = (tmp_path / "type1_reports" / "objects" / f"type1-r0002-{second_materialized['html_sha256']}.html").read_text(encoding="utf-8")
    assert "NOT_RUN" in report and "000660" in json.dumps(snapshot["revision"])
    for label in ("Overview", "Type1 identity", "Protocol and accounting", "Training plan and observed completion", "Reused-validation", "Fresh OOS", "Failures and integrity"):
        assert label in report
    with pytest.raises(Type1ReportError):
        insert_report_revision(tmp_path, _revision(tmp_path, 3))
    with pytest.raises(Type1ReportError):
        materialize_report_revision(tmp_path, first["event_sha256"])


def test_catalog_fails_closed_for_tamper_gap_identity_and_orphan(tmp_path):
    inserted = insert_report_revision(tmp_path, _revision(tmp_path))
    event = next((tmp_path / "type1_reports" / "events").iterdir())
    event.write_bytes(event.read_bytes() + b" ")
    with pytest.raises(Type1ReportError):
        verify_report_catalog(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    bad = _revision(other); bad["identity"] = dict(IDENTITY, dataset_id="near-match")
    with pytest.raises(Type1ReportError):
        insert_report_revision(other, bad)
    assert inserted["revision_id"] == "type1-r0001"

def test_catalog_rehashes_fixed_source_paths(tmp_path):
    inserted = insert_report_revision(tmp_path, _revision(tmp_path))
    materialized = materialize_report_revision(tmp_path, inserted["event_sha256"])
    commit_report_tip(tmp_path, materialized["event_sha256"])
    (tmp_path / "run_manifest.json").write_bytes(b"tampered")
    with pytest.raises(Type1ReportError, match="source hashes"):
        verify_report_catalog(tmp_path)
def test_catalog_rejects_semantic_outer_identity_tamper(tmp_path):
    _sources(tmp_path)
    source = tmp_path / "authority.json"
    value = json.loads(source.read_text())
    value["identity"]["custody_uid"] = "copied-under-wrong-path"
    source.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")))
    with pytest.raises(Type1ReportError, match="outer identity"):
        report_source_sha256(tmp_path)
    assert REPLACEMENT_OUTER_IDENTITY == {
        "authority_id": "type1-krx-authority-20260723-002",
        "dataset_id": "type1-close-20260803-003",
        "train_id": "type1-public-003",
        "train_run_id": "train_type1-public-003",
        "custody_uid": "type1-fresh-oos-20260803-003",
        "report_family": "kronos.type1.report.v1",
    }


def test_report_uses_seven_ordinary_anchor_linked_sections(tmp_path):
    revision = insert_report_revision(tmp_path, _revision(tmp_path))
    object_event = materialize_report_revision(tmp_path, revision["event_sha256"])
    report = (tmp_path / "type1_reports" / "objects" / f"type1-r0001-{object_event['html_sha256']}.html").read_text(encoding="utf-8")
    assert report.count("<section ") == 7
    assert 'role="tab"' not in report and 'role="tabpanel"' not in report
    for section in ("overview", "identity", "protocol", "training", "validation", "custody", "integrity"):
        assert f'href="#{section}"' in report
        assert f'id="{section}"' in report
    assert "LINUCB_CONTEXTUAL_BANDIT_NO_GO_FIVE_SEEDS_23BP_FRESH_OOS_NOT_RUN_UNCHANGED" in report
