import json
import pytest
import stom_rl.daily_v1_type1_report as type1_report
import stom_rl.daily_type1_publication as publication

from flask import Flask

import webui.v6_platform_api as api
from stom_rl.daily_v1_type1_report import (
    IDENTITY, LOCKS, POLICY, REPORT_RESULT, commit_report_tip,
    insert_report_revision, materialize_report_revision, report_source_sha256,
)
from tests.test_daily_v1_type1_report import _prepare_recovered_runner


_AUTHORITY_SCHEMA = "kronos.type1.krx-public-authority.v2"


def _install_synthetic_authority(monkeypatch):
    import stom_rl.daily_type1_authority as authority_module

    def validate_authority(envelope):
        if (
            not isinstance(envelope, dict)
            or set(envelope) != {"authority", "integrity", "schema"}
            or envelope.get("schema") != _AUTHORITY_SCHEMA
            or envelope.get("authority", {}).get("authority_id") != IDENTITY["authority_id"]
            or envelope.get("authority", {}).get("fresh_oos") != {"status": "NOT_RUN", "no_read": True}
        ):
            raise ValueError("synthetic authority envelope is invalid")

    monkeypatch.setattr(authority_module, "validate_authority", validate_authority)
    monkeypatch.setattr(authority_module, "canonical_json", type1_report._canonical)
    monkeypatch.setattr(
        authority_module,
        "sha256_canonical",
        lambda value: type1_report._sha(type1_report._canonical(value)),
    )


def _revision(run, revision_id="type1-r0001", revision_ordinal=1, failure="EXPECTED_FAILURE"):
    sources = report_source_sha256(run)
    evidence = {
        label: sources[label]
        for label in type1_report._report_evidence_labels_for_sources(sources)
    }
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
        "claims": type1_report._report_claims_for_sources(sources),
    }

def _write_report_sources(run):
    from decimal import Decimal
    from stom_rl.daily_type1_market import FeatureScale, TrainOnlyNormalizer
    from stom_rl.daily_type1_public_data import _complete_receipt

    rows_bytes = type1_report._canonical([])
    (run.parent / "public_rows.json").write_bytes(rows_bytes)
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
    scales = tuple(FeatureScale(Decimal("0"), Decimal("1")) for _ in range(7))
    normalizer_digest = TrainOnlyNormalizer(scales).digest()
    normalizer_bytes = type1_report._canonical({
        "kind": "market_type7_train_only",
        "digest": normalizer_digest,
        "scales": [{"center": "0", "scale": "1"} for _ in scales],
    })
    members = {}
    for kind in ("primary", "shuffled_reward"):
        members[kind] = {}
        for seed in range(5):
            member = run / kind / f"seed_{seed}"
            member.mkdir(parents=True)
            model = f"{kind}-{seed}-model".encode()
            (member / "final_model.zip").write_bytes(model)
            (member / "normalizer.json").write_bytes(normalizer_bytes)
            artifacts = {
                "model_sha256": type1_report._sha(model),
                "normalizer_sha256": type1_report._sha(normalizer_bytes),
            }
            replay = {
                **artifacts,
                "normalizer_digest": normalizer_digest,
                "validation_pairs_sha256": "1" * 64,
                "model_device": "cpu",
                "num_timesteps": 200000,
            }
            members[kind][str(seed)] = {
                "seed": seed,
                "timesteps": 200000,
                "actual_sb3_timesteps": 200000,
                "device": "cpu",
                "artifact": "FINAL_MODEL_ONLY",
                "artifacts": artifacts,
                "reload_receipt": {**artifacts, "deterministic": True, "evidence": replay},
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
                "train_only_normalizer_digest": normalizer_digest,
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
    run_manifest_bytes = type1_report._canonical(manifest)
    (run / "run_manifest.json").write_bytes(run_manifest_bytes)
    run_receipt_bytes = type1_report._canonical({
        "manifest_sha256": type1_report._sha(run_manifest_bytes),
        "execution_status": "COMPLETE",
        "verdict": "NO_GO",
        "fresh_oos": {"state": "NOT_RUN", "metrics": None},
    })
    (run / "receipt.json").write_bytes(run_receipt_bytes)
    authority_sha = type1_report._sha((run / "authority.json").read_bytes())
    amendment_sha = type1_report._sha(type1_report.AMENDMENT_PATH.read_bytes())
    dataset_manifest = {
        "dataset_id": IDENTITY["dataset_id"],
        "authority": {"authority_id": IDENTITY["authority_id"], "sessions": {"ordered": [], "pairs": [], "trailing_embargo": []}},
        "authority_sha256": authority_sha,
        "amendment_id": "KRONOS-TYPE1-G002-RECOVERY-2026-07-24-004",
        "amendment_sha256": amendment_sha,
        "source_database_identity": {"daily": "fixture", "fivemin": "fixture"},
        "materializer_source_sha256": "2" * 64,
        "row_count": 0,
        "split_row_counts": {"train": 0, "reused_validation": 0},
        "split_symbol_counts": {"train": 0, "reused_validation": 0},
        "expected": {},
        "public_cutoff": "2025-06-30",
        "price_basis": "15:20_bar_close_proxy",
        "fresh_oos": {"state": "NOT_RUN", "read_performed": False},
    }
    dataset_manifest_bytes = type1_report._canonical(dataset_manifest)
    (run.parent / "dataset_manifest.json").write_bytes(dataset_manifest_bytes)
    amendment = json.loads(type1_report.AMENDMENT_PATH.read_text(encoding="utf-8"))
    (run.parent / "materializer_complete_receipt.json").write_bytes(type1_report._canonical(
        _complete_receipt(
            manifest=dataset_manifest,
            manifest_bytes=dataset_manifest_bytes,
            rows_bytes=rows_bytes,
            amendment=amendment,
        )
    ))
    materializer_evidence = {
        "public_rows_sha256": type1_report._sha(rows_bytes),
        "dataset_manifest_sha256": type1_report._sha(dataset_manifest_bytes),
        "materializer_complete_receipt_sha256": type1_report._sha(
            (run.parent / "materializer_complete_receipt.json").read_bytes()
        ),
    }
    member_artifact_sha256 = {
        f"{kind}/seed_{seed}/final_model.zip": members[kind][str(seed)]["artifacts"]["model_sha256"]
        for kind in ("primary", "shuffled_reward")
        for seed in range(5)
    }
    member_artifact_sha256.update({
        f"{kind}/seed_{seed}/normalizer.json": members[kind][str(seed)]["artifacts"]["normalizer_sha256"]
        for kind in ("primary", "shuffled_reward")
        for seed in range(5)
    })
    (run / "publication_receipt.json").write_bytes(type1_report._canonical(
        publication._publication_receipt(
            source_logical_path=publication.SOURCE_LOGICAL_PATH,
            destination_logical_path=publication.DESTINATION_LOGICAL_PATH,
            run_evidence={
                "run_manifest_sha256": type1_report._sha(run_manifest_bytes),
                "run_receipt_sha256": type1_report._sha(run_receipt_bytes),
                "artifact_sha256": member_artifact_sha256,
            },
            materializer_evidence=materializer_evidence,
        )
    ))
    report_source_sha256(run)

def _client(monkeypatch, tmp_path, *, recovered=False):
    root = tmp_path / "runs"
    old_run = root / "type1-close-20260803-001" / "train_type1-public-001"

    old_run.parent.mkdir(parents=True)
    run = root / IDENTITY["dataset_id"] / IDENTITY["train_run_id"]
    run.mkdir(parents=True)
    if recovered:
        _install_synthetic_authority(monkeypatch)
        _prepare_recovered_runner(run)
        type1_report.initialize_report_authority(run, run / "frozen_authority_envelope.json")
    else:
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


def test_recovered_type1_lifecycle_run_and_detail_project_complete_no_go_evidence(monkeypatch, tmp_path):
    client, _, _, _ = _client(monkeypatch, tmp_path, recovered=True)

    runs_payload = client.get("/api/v6/runs").get_json()
    type1_run = runs_payload["runs"][0]
    detail = client.get(
        f"/api/v6/run-detail?dataset={IDENTITY['dataset_id']}&train={IDENTITY['train_run_id']}"
    ).get_json()
    manifest = detail["manifest"]
    status = client.get("/api/v6/status").get_json()

    assert runs_payload["training_state"] == "HAS_RUNS"
    assert status["journey"]["training"]["state"] == "HAS_RUNS"
    assert status["journey"]["evaluation"]["state"] == "TEST_NOT_RUN"
    assert type1_run["dataset_run_id"] == "type1-close-20260803-005"
    assert type1_run["run_id"] == "train_type1-public-005"
    assert type1_run["family"] == "TYPE1"
    assert type1_run["state"] == type1_run["execution_status"] == "COMPLETE"
    assert type1_run["verdict"] == type1_run["verdict_candidate"]["value"] == "NO_GO"
    assert type1_run["evidence_mode"] == "RECOVERED_AFTER_BLOCK"
    assert type1_run["primary_seeds"] == type1_run["shuffled_reward_seeds"] == [0, 1, 2, 3, 4]
    assert type1_run["seed_counts"] == {"primary": 5, "shuffled_reward": 5}
    assert type1_run["timesteps_per_seed"] == 200000
    assert type1_run["fresh_oos"] == {"state": "NOT_RUN", "read_performed": False, "no_read": True}
    assert type1_run["training_state"] == "COMPLETE"
    assert type1_run["evaluation_state"] == "TEST_NOT_RUN"

    assert detail["status"] == "OK"
    assert detail["state"] == detail["execution_status"] == "COMPLETE"
    assert detail["verdict"] == "NO_GO"
    assert detail["evidence_mode"] == "RECOVERED_AFTER_BLOCK"
    assert detail["states"] == {
        "training_state": "COMPLETE",
        "validation_state": "REUSED_VALIDATION_COMPLETE",
        "test_state": "NOT_RUN",
        "evaluation_state": "TEST_NOT_RUN",
    }
    assert manifest["schema_version"] == "kronos_type1_lifecycle_projection.v1"
    assert manifest["family"] == "TYPE1"
    assert manifest["state"] == manifest["execution_status"] == "COMPLETE"
    assert manifest["verdict_candidate"]["value"] == "NO_GO"
    assert manifest["verdict_candidate"]["outcome"] == "NO_GO_ONLY"
    assert "RECOVERED_AFTER_BLOCK" in manifest["verdict_candidate"]["reasons"]
    assert manifest["original_block"]["status"] == "BLOCK"
    assert manifest["original_block"]["reason"] == "conversion from numpy.int8 to Decimal is not supported"
    assert manifest["original_block_preserved"] is True
    assert manifest["retraining_performed"] is False
    assert manifest["test"] == {"state": "NOT_RUN", "read_performed": False, "no_read": True}
    assert manifest["fresh_oos"] == {"state": "NOT_RUN", "read_performed": False, "no_read": True}
    assert "metrics" not in manifest["fresh_oos"]
    assert len(manifest["per_seed"]) == len(manifest["shuffled_label_control"]) == 5
    assert [seed["actual_sb3_timesteps"] for seed in manifest["per_seed"].values()] == [200000] * 5
    assert [seed["actual_sb3_timesteps"] for seed in manifest["shuffled_label_control"].values()] == [200000] * 5
    assert manifest["aggregation"]["metric"] == "FIVE_SEED_IQM"
    assert manifest["controls"]["integrity_ok"] is True
    assert manifest["claims"]["outcome"] == "NO_GO_ONLY"
    assert "fresh_oos_metrics" not in json.dumps(manifest, sort_keys=True)


def test_type1_lifecycle_projection_fails_closed_on_missing_and_tampered_custody(monkeypatch, tmp_path):
    import shutil

    client, run, _, _ = _client(monkeypatch, tmp_path, recovered=True)
    prepared_root = run.parents[1]
    cases = {}
    for tamper in ("missing_recovery_receipt", "tampered_recovery_manifest"):
        case_root = tmp_path / tamper
        shutil.copytree(prepared_root, case_root)
        case_run = case_root / IDENTITY["dataset_id"] / IDENTITY["train_run_id"]
        if tamper == "missing_recovery_receipt":
            (case_run / "recovery_receipt.json").unlink()
        else:
            recovery_manifest = json.loads((case_run / "recovery_manifest.json").read_text(encoding="utf-8"))
            recovery_manifest["training"]["timesteps_per_seed"] = 100
            (case_run / "recovery_manifest.json").write_text(json.dumps(recovery_manifest), encoding="utf-8")
        cases[tamper] = case_root

    for case_root in cases.values():
        monkeypatch.setattr(api, "RUNS_ROOT", case_root)
        runs = client.get("/api/v6/runs").get_json()["runs"]
        detail = client.get(
            f"/api/v6/run-detail?dataset={IDENTITY['dataset_id']}&train={IDENTITY['train_run_id']}"
        ).get_json()

        assert not any(run["dataset_run_id"] == IDENTITY["dataset_id"] for run in runs)
        assert detail["status"] == "BLOCKED"
        assert detail["reason"] == "TYPE1_CATALOG_INVALID"
        assert detail["manifest"] == {}



def test_type1_lifecycle_fails_closed_when_authority_verifier_is_missing(monkeypatch, tmp_path):
    import stom_rl.daily_type1_authority as authority_module

    client, _, _, first_materialization = _client(monkeypatch, tmp_path, recovered=True)
    calls = {"count": 0}

    def missing_rfc8785(_value):
        calls["count"] += 1
        raise authority_module.AuthorityError("rfc8785 is required to verify an authority artifact")

    monkeypatch.setattr(authority_module, "canonical_json", missing_rfc8785)

    runs = client.get("/api/v6/runs").get_json()["runs"]
    detail = client.get(
        f"/api/v6/run-detail?dataset={IDENTITY['dataset_id']}&train={IDENTITY['train_run_id']}"
    ).get_json()
    report_entry = client.get(
        f"/api/v6/reports?dataset={IDENTITY['dataset_id']}&train={IDENTITY['train_run_id']}"
    ).get_json()["reports"][0]
    report = client.get(
        f"/api/v6/report-html?dataset={IDENTITY['dataset_id']}&train={IDENTITY['train_run_id']}"
        f"&report_sha256={first_materialization['html_sha256']}"
    )

    assert calls["count"] >= 1
    assert not any(run["dataset_run_id"] == IDENTITY["dataset_id"] for run in runs)
    assert detail["status"] == "BLOCKED"
    assert detail["reason"] == "TYPE1_CATALOG_INVALID"
    assert detail["manifest"] == {}
    assert report_entry["availability"] == "BLOCKED"
    assert report_entry["integrity_reasons"] == ["TYPE1_CATALOG_INVALID"]
    assert report_entry["revisions"] == []
    assert report.status_code == 409
    assert report.get_json()["reason"] == "TYPE1_CATALOG_INVALID"


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
