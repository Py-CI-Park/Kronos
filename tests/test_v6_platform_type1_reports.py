import json

from flask import Flask

import webui.v6_platform_api as api
from stom_rl.daily_v1_type1_report import (
    IDENTITY, LOCKS, POLICY, commit_report_tip, insert_report_revision,
    materialize_report_revision, report_source_sha256,
)


def _revision(run):
    sources = report_source_sha256(run)
    evidence = {label: sources[label] for label in (
        "type1_identity", "public_run_seal", "deployment_lock", "attempt_parent",
        "amendment", "protocol", "preregistration", "authority", "builder_source",
    )}
    return {
        "schema_version": "kronos_type1_report_revision.v2", "revision_id": "type1-r0001", "revision_ordinal": 1,
        "identity": IDENTITY, "policy": POLICY,
        "result": {"run_state": "FAILED", "training_state": "FAILED", "reused_validation_state": "FAILED", "verdict": "NO_GO", "fresh_oos_state": "NOT_RUN", "fresh_oos_read_performed": False, "failures": ["EXPECTED_FAILURE"]},
        "source_sha256": sources, "evidence": evidence,
        "false_research_locks": LOCKS, "claims": {"symbol": "000660"},
    }

def _write_report_sources(run):
    (run.parent / "dataset_manifest.json").write_bytes(b"dataset")
    (run.parent / "public_rows.json").write_bytes(b"rows")
    (run / "run_manifest.json").write_bytes(b"run")
    (run / "receipt.json").write_bytes(b"receipt")
    for name in ("type1_identity.json", "p6_public_run_seal.json", "attempt_parent.json", "authority.json"):
        (run / name).write_text(json.dumps({"identity": IDENTITY}, sort_keys=True, separators=(",", ":")))
    (run / "deployment_lock.json").write_text(json.dumps({"locks": LOCKS}, sort_keys=True, separators=(",", ":")))
    for kind in ("primary", "shuffled_reward"):
        for seed in range(5):
            member = run / kind / f"seed_{seed}"
            member.mkdir(parents=True)
            (member / "final_model.zip").write_bytes(f"{kind}-{seed}-model".encode())
            (member / "normalizer.pkl").write_bytes(f"{kind}-{seed}-normalizer".encode())


def _client(monkeypatch, tmp_path):
    root = tmp_path / "runs"
    old_run = root / "type1-close-20260803-001" / "train_type1-public-001"
    (old_run / "type1_reports").mkdir(parents=True)
    run = root / IDENTITY["dataset_id"] / IDENTITY["train_run_id"]
    run.mkdir(parents=True)
    _write_report_sources(run)
    inserted = insert_report_revision(run, _revision(run))
    materialized = materialize_report_revision(run, inserted["event_sha256"])
    commit_report_tip(run, materialized["event_sha256"])
    monkeypatch.setattr(api, "RUNS_ROOT", root)
    app = Flask(__name__); app.register_blueprint(api.create_v6_platform_blueprint())
    return app.test_client(), run, old_run


def test_replacement_type1_catalog_requires_explicit_sha_and_old_marker_is_blocked(monkeypatch, tmp_path):
    client, run, old_run = _client(monkeypatch, tmp_path)
    reports = client.get(f"/api/v6/reports?dataset={IDENTITY['dataset_id']}&train={IDENTITY['train_run_id']}").get_json()["reports"]
    assert len(reports) == 1
    entry = reports[0]
    assert entry["availability"] == "COMMITTED" and entry["result"]["verdict"] == "NO_GO"
    report = entry["reports"][0]
    response = client.get(report["report_url"])
    assert response.status_code == 200
    assert response.headers["ETag"] == f'"{report["report_sha256"]}"'
    assert b"NOT_RUN" in response.data and b"Replacement Type1" in response.data
    assert client.get(f"/api/v6/report-html?dataset={IDENTITY['dataset_id']}&train={IDENTITY['train_run_id']}").status_code == 400
    assert client.get(f"/api/v6/report-html?dataset={IDENTITY['dataset_id']}&train={IDENTITY['train_run_id']}&report_sha256={'0' * 64}").status_code == 404
    old = client.get("/api/v6/reports?dataset=type1-close-20260803-001&train=train_type1-public-001").get_json()["reports"][0]
    assert old["availability"] == "BLOCKED"
    assert client.get("/api/v6/report-html?dataset=type1-close-20260803-001&train=train_type1-public-001&report_sha256=" + "0" * 64).status_code == 409
    assert old_run.name == "train_type1-public-001" and run.name == IDENTITY["train_run_id"]


def test_report_html_rejects_bad_queries_legacy_and_non_get(monkeypatch, tmp_path):
    client, run, _ = _client(monkeypatch, tmp_path)
    for query in ("?dataset=x&train=y&bad=1", "?dataset=x&dataset=y&train=z", "?dataset=..%2Fx&train=z"):
        assert client.get("/api/v6/report-html" + query).status_code == 400
    assert client.post(f"/api/v6/report-html?dataset={IDENTITY['dataset_id']}&train={IDENTITY['train_run_id']}").status_code == 405
    assert client.get(f"/api/v6/report-html?dataset={IDENTITY['dataset_id']}&train={IDENTITY['train_run_id']}&report_sha256=" + "A" * 64).status_code == 400
    assert client.get(f"/api/v6/reports?dataset={IDENTITY['dataset_id']}&train={IDENTITY['train_run_id']}&report_sha256=" + "0" * 64).status_code == 400
    legacy = run.parent / "legacy"; legacy.mkdir(); (legacy / "report.html").write_text("legacy"); (legacy / "report_manifest.json").write_text("{}")
    assert client.get(f"/api/v6/report-html?dataset={IDENTITY['dataset_id']}&train=legacy").status_code == 409
