import json

from flask import Flask

import webui.v6_platform_api as api
from stom_rl.daily_v1_type1_report import (
    IDENTITY, LOCKS, POLICY, commit_report_tip, insert_report_revision,
    materialize_report_revision, report_source_sha256,
)


def _revision(run, revision_id="type1-r0001", revision_ordinal=1, failure="EXPECTED_FAILURE"):
    sources = report_source_sha256(run)
    evidence = {label: sources[label] for label in (
        "type1_identity", "public_run_seal", "deployment_lock", "attempt_parent",
        "amendment", "protocol", "preregistration", "authority", "builder_source",
    )}
    return {
        "schema_version": "kronos_type1_report_revision.v2",
        "revision_id": revision_id,
        "revision_ordinal": revision_ordinal,
        "identity": IDENTITY,
        "policy": POLICY,
        "result": {
            "run_state": "FAILED",
            "training_state": "FAILED",
            "reused_validation_state": "FAILED",
            "verdict": "NO_GO",
            "fresh_oos_state": "NOT_RUN",
            "fresh_oos_read_performed": False,
            "failures": [failure],
        },
        "source_sha256": sources,
        "evidence": evidence,
        "false_research_locks": LOCKS,
        "claims": {"symbol": "000660"},
    }

def _write_report_sources(run):
    (run.parent / "dataset_manifest.json").write_bytes(b"dataset")
    (run.parent / "public_rows.json").write_bytes(b"rows")
    (run / "run_manifest.json").write_bytes(b"run")
    (run / "receipt.json").write_bytes(b"receipt")
    (run / "type1_identity.json").write_text(json.dumps({
        "identity": IDENTITY,
    }, sort_keys=True, separators=(",", ":")))
    (run / "p6_public_run_seal.json").write_text(json.dumps({
        "identity": IDENTITY,
        "fresh_oos": {"state": "NOT_RUN", "payload_read": False},
    }, sort_keys=True, separators=(",", ":")))
    (run / "deployment_lock.json").write_text(json.dumps({
        "identity": IDENTITY,
        "false_research_locks": LOCKS,
    }, sort_keys=True, separators=(",", ":")))
    (run / "attempt_parent.json").write_text(json.dumps({
        "identity": IDENTITY,
        "parent_identity": {
            "dataset_id": "type1-close-20260803-001",
            "train_id": "type1-public-001",
            "train_run_id": "train_type1-public-001",
        },
    }, sort_keys=True, separators=(",", ":")))
    (run / "authority.json").write_text(json.dumps({
        "identity": IDENTITY,
        "authority_id": IDENTITY["authority_id"],
    }, sort_keys=True, separators=(",", ":")))
    for kind in ("primary", "shuffled_reward"):
        for seed in range(5):
            member = run / kind / f"seed_{seed}"
            member.mkdir(parents=True)
            (member / "final_model.zip").write_bytes(f"{kind}-{seed}-model".encode())
            (member / "normalizer.pkl").write_bytes(f"{kind}-{seed}-normalizer".encode())


def _client(monkeypatch, tmp_path):
    root = tmp_path / "runs"
    old_run = root / "type1-close-20260803-001" / "train_type1-public-001"
    old_run.parent.mkdir(parents=True)
    run = root / IDENTITY["dataset_id"] / IDENTITY["train_run_id"]
    run.mkdir(parents=True)
    _write_report_sources(run)
    first = insert_report_revision(run, _revision(run))
    first_materialization = materialize_report_revision(run, first["event_sha256"])
    second = insert_report_revision(run, _revision(run, "type1-r0002", 2, "SECOND_EXPECTED_FAILURE"))
    second_materialization = materialize_report_revision(run, second["event_sha256"])
    commit_report_tip(run, second_materialization["event_sha256"])
    monkeypatch.setattr(api, "RUNS_ROOT", root)
    app = Flask(__name__); app.register_blueprint(api.create_v6_platform_blueprint())
    return app.test_client(), run, old_run, first_materialization


def test_replacement_type1_catalog_is_revision_complete_and_preserves_old_attempts(monkeypatch, tmp_path):
    client, run, old_run, first_materialization = _client(monkeypatch, tmp_path)
    payload = client.get(f"/api/v6/reports?dataset={IDENTITY['dataset_id']}&train={IDENTITY['train_run_id']}").get_json()
    assert payload["schema_version"] == "kronos_v6_reports.v2"
    entry = payload["reports"][0]
    assert entry["record_type"] == "TYPE1_CUSTODY"
    assert entry["availability"] == "COMMITTED"
    assert not {"verdict", "test_state", "report_sha256", "report_url", "result", "reports", "catalog"} & set(entry)
    assert [row["revision_ordinal"] for row in entry["revisions"]] == [1, 2]
    first, second = entry["revisions"]
    assert first["record_type"] == second["record_type"] == "TYPE1_REVISION"
    assert first["result"]["failures"] == ["EXPECTED_FAILURE"]
    assert second["failures"] == ["SECOND_EXPECTED_FAILURE"]
    assert first["parent_event_sha256"] is None
    assert second["parent_revision_event_sha256"] == first["revision_event_sha256"]
    assert first["materialization"]["event_sha256"] == first_materialization["event_sha256"]
    response = client.get(first["report_url"])
    assert response.status_code == 200
    assert response.headers["ETag"] == f'"{first["report_sha256"]}"'
    assert b"NOT_RUN" in response.data and b"Replacement Type1" in response.data
    assert client.get(f"/api/v6/report-html?dataset={IDENTITY['dataset_id']}&train={IDENTITY['train_run_id']}").status_code == 400
    assert client.get(f"/api/v6/report-html?dataset={IDENTITY['dataset_id']}&train={IDENTITY['train_run_id']}&report_sha256={'0' * 64}").status_code == 404
    old = client.get("/api/v6/reports?dataset=type1-close-20260803-001&train=train_type1-public-001").get_json()["reports"][0]
    assert old["record_type"] == "TYPE1_PRESERVED_INELIGIBLE_CUSTODY"
    assert old["availability"] == "BLOCKED" and len(old["attempts"]) == 2
    assert [attempt["attempt_id"] for attempt in old["attempts"]] == [
        "train_type1-public-001-aborted-preflight-v1",
        "train_type1-public-001-aborted-universe-v2",
    ]
    assert all(attempt["availability"] == "MISSING" for attempt in old["attempts"])
    blocked = client.get("/api/v6/report-html?dataset=type1-close-20260803-001&train=train_type1-public-001&report_sha256=" + "0" * 64)
    assert blocked.status_code == 409
    assert blocked.get_json()["reason"] == "PRESERVED_INELIGIBLE_REPORT_NOT_SERVABLE"
    assert not old_run.exists() and run.name == IDENTITY["train_run_id"]


def test_report_html_rejects_bad_queries_legacy_non_get_and_wrong_outer_identity(monkeypatch, tmp_path):
    client, run, _, _ = _client(monkeypatch, tmp_path)
    for query in ("?dataset=x&train=y&bad=1", "?dataset=x&dataset=y&train=z", "?dataset=..%2Fx&train=z"):
        assert client.get("/api/v6/report-html" + query).status_code == 400
    assert client.post(f"/api/v6/report-html?dataset={IDENTITY['dataset_id']}&train={IDENTITY['train_run_id']}").status_code == 405
    assert client.get(f"/api/v6/report-html?dataset={IDENTITY['dataset_id']}&train={IDENTITY['train_run_id']}&report_sha256=" + "A" * 64).status_code == 400
    assert client.get(f"/api/v6/reports?dataset={IDENTITY['dataset_id']}&train={IDENTITY['train_run_id']}&report_sha256=" + "0" * 64).status_code == 400
    copied = run.parents[1] / "copied-dataset" / "copied-train"
    import shutil
    shutil.copytree(run, copied)
    revision = client.get(f"/api/v6/reports?dataset={IDENTITY['dataset_id']}&train={IDENTITY['train_run_id']}").get_json()["reports"][0]["revisions"][0]
    wrong = client.get(f"/api/v6/report-html?dataset=copied-dataset&train=copied-train&report_sha256={revision['report_sha256']}")
    assert wrong.status_code == 409
    assert wrong.get_json()["reason"] == "TYPE1_REPLACEMENT_IDENTITY_MISMATCH"
    legacy = run.parent / "legacy"; legacy.mkdir(); (legacy / "report.html").write_text("legacy"); (legacy / "report_manifest.json").write_text("{}")
    assert client.get(f"/api/v6/report-html?dataset={IDENTITY['dataset_id']}&train=legacy").status_code == 409
