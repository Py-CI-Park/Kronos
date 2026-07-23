
from flask import Flask

import webui.v6_platform_api as api
from stom_rl.daily_v1_type1_report import (
    IDENTITY, LOCKS, POLICY, commit_report_tip, insert_report_revision,
    materialize_report_revision, report_source_sha256,
)


def _revision(run):
    return {
        "schema_version": "kronos_type1_report_revision.v1", "revision_id": "type1-r0001", "revision_ordinal": 1,
        "identity": IDENTITY, "policy": POLICY,
        "result": {"run_state": "FAILED", "training_state": "FAILED", "reused_validation_state": "FAILED", "verdict": "NO_GO", "fresh_oos_state": "NOT_RUN", "fresh_oos_read_performed": False, "failures": ["EXPECTED_FAILURE"]},
        "source_sha256": report_source_sha256(run),
        "false_research_locks": LOCKS, "claims": {"symbol": "000660"},
    }


def _client(monkeypatch, tmp_path):
    root = tmp_path / "runs"; run = root / "type1-close-20260803-001" / "train_type1-public-001"
    run.mkdir(parents=True)
    (run.parent / "dataset_manifest.json").write_bytes(b"dataset")
    (run.parent / "public_rows.json").write_bytes(b"rows")
    (run / "run_manifest.json").write_bytes(b"run")
    (run / "receipt.json").write_bytes(b"receipt")
    for kind in ("primary", "shuffled_reward"):
        for seed in range(5):
            member = run / kind / f"seed_{seed}"
            member.mkdir(parents=True)
            (member / "final_model.zip").write_bytes(f"{kind}-{seed}-model".encode())
            (member / "normalizer.pkl").write_bytes(f"{kind}-{seed}-normalizer".encode())
    inserted = insert_report_revision(run, _revision(run))
    materialized = materialize_report_revision(run, inserted["event_sha256"])
    commit_report_tip(run, materialized["event_sha256"])
    monkeypatch.setattr(api, "RUNS_ROOT", root)
    app = Flask(__name__); app.register_blueprint(api.create_v6_platform_blueprint())
    return app.test_client(), run


def test_type1_reports_are_native_committed_and_html_is_immutable(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    reports = client.get("/api/v6/reports").get_json()["reports"]
    entry = next(item for item in reports if item.get("report_family") == "TYPE1")
    assert entry["availability"] == "COMMITTED" and entry["result"]["verdict"] == "NO_GO"
    response = client.get("/api/v6/report-html?dataset=type1-close-20260803-001&train=train_type1-public-001")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "immutable" in response.headers["Cache-Control"]
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert b"NOT_RUN" in response.data and b"profitability evidence" in response.data
    detail = client.get("/api/v6/run-detail?dataset=type1-close-20260803-001&train=train_type1-public-001").get_json()
    assert detail["identity"]["report_family"] == "TYPE1" and detail["result"]["fresh_oos_state"] == "NOT_RUN"


def test_report_html_rejects_bad_queries_legacy_and_non_get(monkeypatch, tmp_path):
    client, run = _client(monkeypatch, tmp_path)
    for query in ("?dataset=x&train=y&bad=1", "?dataset=x&dataset=y&train=z", "?dataset=..%2Fx&train=z"):
        assert client.get("/api/v6/report-html" + query).status_code == 400
    assert client.post("/api/v6/report-html?dataset=type1-close-20260803-001&train=train_type1-public-001").status_code == 405
    legacy = run.parent / "legacy"; legacy.mkdir(); (legacy / "report.html").write_text("legacy"); (legacy / "report_manifest.json").write_text("{}")
    assert client.get("/api/v6/report-html?dataset=type1-close-20260803-001&train=legacy").status_code == 409
