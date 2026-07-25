import json
import pytest
import stom_rl.daily_v1_type1_report as type1_report

from flask import Flask

import webui.v6_platform_api as api
from stom_rl.daily_v1_type1_report import (
    IDENTITY, LOCKS, POLICY, REPORT_CLAIMS, REPORT_RESULT, commit_report_tip,
    insert_report_revision, materialize_report_revision, report_source_sha256,
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
        "result": REPORT_RESULT,
        "source_sha256": sources,
        "evidence": evidence,
        "false_research_locks": LOCKS,
        "claims": REPORT_CLAIMS,
    }

def _write_report_sources(run):
    (run.parent / "dataset_manifest.json").write_bytes(b"dataset")
    (run.parent / "public_rows.json").write_bytes(b"rows")
    (run.parent / "materializer_complete_receipt.json").write_bytes(type1_report._canonical({
        "schema_version": "kronos.type1.materializer-complete-receipt.v1",
        "role": "materializer_complete_receipt",
        "status": "COMPLETE",
        "dataset_id": IDENTITY["dataset_id"],
        "materializer_manifest_sha256": "0" * 64,
        "rows_sha256": "0" * 64,
        "authority_sha256": "0" * 64,
        "amendment_sha256": "0" * 64,
        "source_hashes": {},
        "materializer_source_sha256": "0" * 64,
        "expected": {},
        "price_basis": "EXACT_15_20_BAR_CLOSE_PROXY",
        "fresh_oos": {"state": "NOT_RUN", "read_performed": False},
    }))
    outer = {"identity": IDENTITY}
    (run / "type1_identity.json").write_bytes(type1_report._canonical(outer))
    (run / "p6_public_run_seal.json").write_bytes(type1_report._canonical({
        **outer, "fresh_oos": {"state": "NOT_RUN", "payload_read": False},
    }))
    (run / "deployment_lock.json").write_bytes(type1_report._canonical({
        **outer, "false_research_locks": LOCKS,
    }))
    (run / "attempt_parent.json").write_bytes(type1_report._canonical({
        **outer,
        "parent_identity": {
            "dataset_id": "type1-close-20260803-004",
            "train_id": "type1-public-004",
            "train_run_id": "train_type1-public-004",
        },
    }))
    (run / "authority.json").write_bytes(type1_report._canonical({
        **outer, "authority_id": IDENTITY["authority_id"],
    }))
    members = {}
    for kind in ("primary", "shuffled_reward"):
        members[kind] = {}
        for seed in range(5):
            member = run / kind / f"seed_{seed}"
            member.mkdir(parents=True)
            model = f"{kind}-{seed}-model".encode()
            normalizer = f"{kind}-{seed}-normalizer".encode()
            (member / "final_model.zip").write_bytes(model)
            (member / "normalizer.pkl").write_bytes(normalizer)
            artifacts = {
                "model_sha256": type1_report._sha(model),
                "normalizer_sha256": type1_report._sha(normalizer),
            }
            members[kind][str(seed)] = {
                "seed": seed,
                "timesteps": 200000,
                "actual_sb3_timesteps": 200000,
                "device": "cpu",
                "artifact": "FINAL_MODEL_ONLY",
                "artifacts": artifacts,
                "reload_receipt": {**artifacts, "deterministic": True},
                "validation": {},
            }
    manifest = {
        "schema_version": "kronos_type1_g002_public_run.v1",
        "identities": IDENTITY,
        "training": {
            "seeds": [0, 1, 2, 3, 4],
            "timesteps_per_seed": 200000,
            "device": "cpu",
            "validation_visible_to_training": False,
            "eval_callback": False,
            "early_stopping": False,
            "best_model_selection": False,
            "checkpoint_selection": False,
            "member_selection": False,
            "saved_artifact": "FINAL_MODEL_ONLY",
            "synthetic_oracle_calibration": False,
        },
        "members": members,
        "controls": {"integrity_ok": True},
        "pretraining_gate": {
            "accounting": {"cost_bps": 23, "slot_notional_krw": 5000000, "max_slots": 10},
            "block_semantics": "BLOCK",
            "validation_noninterference": {
                "train_only_normalizer_digest": "0" * 64,
                "train_pairs_sha256": "1" * 64,
                "mutated_surfaces": ["features", "gross_return", "entry_available"],
                "unchanged": True,
            },
        },
        "fresh_oos": {"state": "NOT_RUN", "metrics": None},
        "false_research_locks": LOCKS,
        "execution_status": "COMPLETE",
        "verdict": "NO_GO",
    }
    (run / "run_manifest.json").write_bytes(type1_report._canonical(manifest))
    (run / "receipt.json").write_bytes(type1_report._canonical({}))
    sources = report_source_sha256(run)
    (run.parent / "materializer_complete_receipt.json").write_bytes(type1_report._canonical({
        "schema_version": "kronos.type1.materializer-complete-receipt.v1",
        "role": "materializer_complete_receipt",
        "status": "COMPLETE",
        "dataset_id": IDENTITY["dataset_id"],
        "materializer_manifest_sha256": sources["dataset_manifest"],
        "rows_sha256": sources["public_rows"],
        "authority_sha256": sources["authority"],
        "amendment_sha256": sources["amendment"],
        "source_hashes": {},
        "materializer_source_sha256": "0" * 64,
        "expected": {},
        "price_basis": "EXACT_15_20_BAR_CLOSE_PROXY",
        "fresh_oos": {"state": "NOT_RUN", "read_performed": False},
    }))
    (run / "receipt.json").write_bytes(type1_report._canonical({
        "manifest_sha256": sources["run_manifest"],
        "execution_status": "COMPLETE",
        "verdict": "NO_GO",
        "fresh_oos": {"state": "NOT_RUN", "metrics": None},
    }))

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
    assert entry["custody"]["identity"] == {
        "authority_id": "type1-krx-authority-20260724-004",
        "dataset_id": "type1-close-20260803-005",
        "train_id": "type1-public-005",
        "train_run_id": "train_type1-public-005",
        "custody_uid": "type1-fresh-oos-20260803-005",
    }
    assert not {"verdict", "test_state", "report_sha256", "report_url", "result", "reports", "catalog"} & set(entry)
    assert "latest_revision_event_sha256" not in entry
    assert [row["revision_ordinal"] for row in entry["revisions"]] == [1, 2]
    first, second = entry["revisions"]
    assert first["record_type"] == second["record_type"] == "TYPE1_REVISION"
    assert first["result"] == REPORT_RESULT
    assert second["failures"] == []
    assert first["parent_event_sha256"] is None
    assert second["parent_revision_event_sha256"] == first["revision_event_sha256"]
    assert first["materialization"]["event_sha256"] == first_materialization["event_sha256"]
    response = client.get(first["report_url"])
    assert response.status_code == 200
    assert response.headers["ETag"] == f'"{first["report_sha256"]}"'
    assert "report_sha256=" + first["report_sha256"] in first["report_url"]
    assert b"NOT_RUN" in response.data
    assert b"Replacement Type1" in response.data
    assert b"LINUCB_CONTEXTUAL_BANDIT_NO_GO_FIVE_SEEDS_23BP_FRESH_OOS_NOT_RUN_UNCHANGED" in response.data
    assert client.get(f"/api/v6/report-html?dataset={IDENTITY['dataset_id']}&train={IDENTITY['train_run_id']}").status_code == 400
    assert client.get(f"/api/v6/report-html?dataset={IDENTITY['dataset_id']}&train={IDENTITY['train_run_id']}&report_sha256={'0' * 64}").status_code == 404
    preserved = [
        client.get(f"/api/v6/reports?dataset=type1-close-20260803-00{ordinal}&train=train_type1-public-00{ordinal}").get_json()["reports"][0]
        for ordinal in (1, 2, 3, 4)
    ]
    assert all(entry["record_type"] == "TYPE1_PRESERVED_INELIGIBLE_CUSTODY" for entry in preserved)
    assert all(entry["availability"] == "BLOCKED" for entry in preserved)
    assert [entry["custody"]["scientific_eligibility"] for entry in preserved] == [
        "INELIGIBLE_BLOCKED",
        "INELIGIBLE_BLOCKED",
        "NON_MATERIALIZED_INELIGIBLE",
        "MATERIALIZED_NOT_TRAINED_QUARANTINED",
    ]
    assert all(entry["custody"]["immutable_history"] is True for entry in preserved)
    assert [entry["custody"]["model_files_created"] for entry in preserved] == [0, 0, 0, 0]
    assert preserved[2]["custody"] == {
        "amendment_id": "KRONOS-TYPE1-G002-RECOVERY-2026-07-24-004",
        "scientific_eligibility": "NON_MATERIALIZED_INELIGIBLE",
        "model_files_created": 0,
        "fresh_oos_state": "NOT_RUN",
        "fresh_oos_read": False,
        "immutable_history": True,
        "html_serving": "BLOCKED",
        "authority_id": "type1-krx-authority-20260723-002",
        "authority_sha256": "7d0ea6d76e3181da6caef232ce0c152645c290a290021e906d700667f8a059a2",
        "authority_status": "QUARANTINED",
        "materializations_created": 0,
    }
    assert preserved[3]["custody"]["authority_id"] == "type1-krx-authority-20260724-003"
    assert preserved[3]["custody"]["materializations_created"] == 1
    assert all(entry["custody"]["fresh_oos_state"] == "NOT_RUN" for entry in preserved)
    assert all(entry["custody"]["fresh_oos_read"] is False for entry in preserved)


    catalog = client.get("/api/v6/reports").get_json()["reports"]
    assert {(entry["dataset_run_id"], entry["train_run_id"]) for entry in catalog if entry["record_type"].startswith("TYPE1_")} == {
        ("type1-close-20260803-001", "train_type1-public-001"),
        ("type1-close-20260803-002", "train_type1-public-002"),
        ("type1-close-20260803-003", "train_type1-public-003"),
        ("type1-close-20260803-004", "train_type1-public-004"),
        (IDENTITY["dataset_id"], IDENTITY["train_run_id"]),
    }
    for ordinal in (1, 2, 3, 4):
        blocked = client.get(f"/api/v6/report-html?dataset=type1-close-20260803-00{ordinal}&train=train_type1-public-00{ordinal}&report_sha256={'0' * 64}")
        assert blocked.status_code == 409
        assert blocked.get_json()["reason"] == "PRESERVED_INELIGIBLE_REPORT_NOT_SERVABLE"
    assert not old_run.exists() and run.name == IDENTITY["train_run_id"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("authority_metadata_cutoff", "2026-07-25"),
        ("authority_metadata_scope", "metadata includes post-cutoff prices"),
    ],
)
def test_reports_omit_preserved_history_for_tampered_authority_metadata(monkeypatch, tmp_path, field, value):
    client, _, _, _ = _client(monkeypatch, tmp_path)
    amendment = json.loads(
        (api.DOCS_ROOT / "kronos_type1_g002_recovery_amendment_v4_2026-07-24.json").read_text(encoding="utf-8")
    )
    amendment["authority_contract"][field] = value
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    (docs_root / "kronos_type1_g002_recovery_amendment_v4_2026-07-24.json").write_text(
        json.dumps(amendment), encoding="utf-8"
    )
    monkeypatch.setattr(api, "DOCS_ROOT", docs_root)

    catalog = client.get("/api/v6/reports").get_json()["reports"]
    preserved = [
        entry for entry in catalog
        if entry["record_type"] == "TYPE1_PRESERVED_INELIGIBLE_CUSTODY"
    ]
    assert len(preserved) == 4
    assert all(entry["integrity"] == "INVALID" for entry in preserved)
    assert all(entry["integrity_reasons"] == ["AMENDMENT_INTEGRITY_MISMATCH"] for entry in preserved)
    queried = client.get(
        "/api/v6/reports?dataset=type1-close-20260803-003&train=train_type1-public-003"
    ).get_json()["reports"]
    assert len(queried) == 1
    assert queried[0]["availability"] == "BLOCKED"


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
