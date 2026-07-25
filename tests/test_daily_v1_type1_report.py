import json

import pytest
import sqlite3
import stom_rl.daily_v1_type1_report as type1_report

from stom_rl.daily_v1_type1_report import (
    AMENDMENT_PATH, IDENTITY, LOCKS, M3E_STATEMENT, POLICY, REPORT_CLAIMS,
    REPORT_RESULT, REPLACEMENT_OUTER_IDENTITY, Type1ReportError,
    commit_report_tip, initialize_report_authority, insert_report_revision,
    materialize_report_revision, reconcile_report_tip, report_source_sha256,
    verify_report_catalog,
)


_AUTHORITY_SCHEMA = "kronos.type1.krx-public-authority.v2"
_AUTHORITY_FILES = (
    "type1_identity.json",
    "p6_public_run_seal.json",
    "deployment_lock.json",
    "attempt_parent.json",
    "authority.json",
)


@pytest.fixture(autouse=True)
def _allow_synthetic_authority(monkeypatch):
    import stom_rl.daily_type1_authority as authority_module

    def validate_authority(envelope):
        if not isinstance(envelope, dict) or set(envelope) != {"authority", "integrity", "schema"} or envelope.get("schema") != _AUTHORITY_SCHEMA:
            raise ValueError("synthetic authority envelope is invalid")

    monkeypatch.setattr(authority_module, "validate_authority", validate_authority)


def _authority_envelope(*, authority_id=IDENTITY["authority_id"], integrity="test"):
    return {
        "schema": _AUTHORITY_SCHEMA,
        "authority": {
            "authority_id": authority_id,
            "fresh_oos": {"status": "NOT_RUN", "no_read": True},
            "sessions": {"ordered": [], "pairs": [], "trailing_embargo": []},
        },
        "integrity": {"test_only": integrity},
    }


def _authority_bytes(*, authority_id=IDENTITY["authority_id"], integrity="test"):
    from stom_rl.daily_type1_authority import canonical_json

    return canonical_json(_authority_envelope(authority_id=authority_id, integrity=integrity))


def _write_authority(run, *, authority_id=IDENTITY["authority_id"], integrity="test"):
    path = run / "frozen_authority_envelope.json"
    path.write_bytes(_authority_bytes(authority_id=authority_id, integrity=integrity))
    return path


def _prepare_completed_runner(run, *, execution_status="COMPLETE", verdict="NO_GO"):
    from stom_rl.daily_type1_public_data import _complete_receipt
    from stom_rl.daily_type1_market import FeatureScale, TrainOnlyNormalizer
    from decimal import Decimal

    run.mkdir(parents=True, exist_ok=True)
    authority_path = _write_authority(run)
    authority_sha = type1_report._sha(authority_path.read_bytes())
    rows_bytes = type1_report._canonical([])
    (run.parent / "public_rows.json").write_bytes(rows_bytes)
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
            member.mkdir(parents=True, exist_ok=True)
            model = f"{kind}-{seed}-model".encode()
            (member / "final_model.zip").write_bytes(model)
            (member / "normalizer.json").write_bytes(normalizer_bytes)
            model_sha = type1_report._sha(model)
            normalizer_sha = type1_report._sha(normalizer_bytes)
            artifacts = {"model_sha256": model_sha, "normalizer_sha256": normalizer_sha}
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
        "identities": {**IDENTITY, "authority_sha256": authority_sha},
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
        "execution_status": execution_status,
        "verdict": verdict,
    }
    (run / "run_manifest.json").write_bytes(type1_report._canonical(manifest))
    (run / "receipt.json").write_bytes(type1_report._canonical({
        "manifest_sha256": type1_report._sha((run / "run_manifest.json").read_bytes()),
        "execution_status": execution_status,
        "verdict": verdict,
        "fresh_oos": {"state": "NOT_RUN", "metrics": None},
    }))
    amendment_sha = type1_report._sha(AMENDMENT_PATH.read_bytes())
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
    amendment = json.loads(AMENDMENT_PATH.read_text(encoding="utf-8"))
    (run.parent / "materializer_complete_receipt.json").write_bytes(type1_report._canonical(
        _complete_receipt(
            manifest=dataset_manifest,
            manifest_bytes=dataset_manifest_bytes,
            rows_bytes=rows_bytes,
            amendment=amendment,
        )
    ))
    return authority_path


def _sources(run):
    authority_path = _prepare_completed_runner(run)
    return initialize_report_authority(run, authority_path)

def _authority_file_paths(run):
    return [run / name for name in _AUTHORITY_FILES]


def test_initialize_report_authority_creates_sources_after_completed_runner(tmp_path):
    authority_path = _prepare_completed_runner(tmp_path)
    assert all(not path.exists() for path in _authority_file_paths(tmp_path))
    sources = initialize_report_authority(tmp_path, authority_path)
    assert all(path.is_file() for path in _authority_file_paths(tmp_path))
    assert sources == report_source_sha256(tmp_path)
    assert sources["authority"] == type1_report._sha(authority_path.read_bytes())
    parent = json.loads((tmp_path / "attempt_parent.json").read_text(encoding="utf-8"))
    assert parent["parent_identity"] == type1_report.PARENT_ATTEMPT_IDENTITY
    assert parent["parent_status"] == "MATERIALIZED_NOT_TRAINED_QUARANTINED"


def test_initialize_report_authority_exact_retry_is_idempotent(tmp_path):
    authority_path = _prepare_completed_runner(tmp_path)
    authority_raw = authority_path.read_bytes()
    authority_sha = type1_report._sha(authority_raw)
    prefix = type1_report._report_authority_artifact_bytes(authority_raw, authority_sha)
    (tmp_path / "type1_identity.json").write_bytes(prefix["type1_identity"])
    first = initialize_report_authority(tmp_path, authority_path)
    second = initialize_report_authority(tmp_path, authority_path)
    assert second == first == report_source_sha256(tmp_path)


def test_initialize_report_authority_blocks_differing_existing_bytes_before_writes(tmp_path):
    authority_path = _prepare_completed_runner(tmp_path)
    (tmp_path / "p6_public_run_seal.json").write_bytes(b"{}")
    with pytest.raises(Type1ReportError, match="different bytes"):
        initialize_report_authority(tmp_path, authority_path)
    assert not (tmp_path / "type1_identity.json").exists()
    assert not (tmp_path / "deployment_lock.json").exists()
    assert not (tmp_path / "attempt_parent.json").exists()
    assert not (tmp_path / "authority.json").exists()


def test_initialize_report_authority_rejects_block_runner_without_writes(tmp_path):
    authority_path = _prepare_completed_runner(tmp_path, execution_status="BLOCK")
    with pytest.raises(Type1ReportError, match="runner manifest or receipt"):
        initialize_report_authority(tmp_path, authority_path)
    assert all(not path.exists() for path in _authority_file_paths(tmp_path))


def test_initialize_report_authority_rejects_wrong_authority_without_writes(tmp_path):
    _prepare_completed_runner(tmp_path)
    wrong = tmp_path / "wrong_authority.json"
    wrong.write_bytes(_authority_bytes(integrity="different-local-envelope"))
    with pytest.raises(Type1ReportError, match="authority hash"):
        initialize_report_authority(tmp_path, wrong)
    assert all(not path.exists() for path in _authority_file_paths(tmp_path))


def test_initialize_report_authority_does_not_create_report_catalog(tmp_path):
    authority_path = _prepare_completed_runner(tmp_path)
    assert not (tmp_path / "type1_reports").exists()
    initialize_report_authority(tmp_path, authority_path)
    assert not (tmp_path / "type1_reports").exists()


def _revision(run, number=1):
    sources = _sources(run)
    evidence = {label: sources[label] for label in (
        "type1_identity", "public_run_seal", "deployment_lock", "attempt_parent",
        "amendment", "protocol", "preregistration", "authority", "builder_source",
    )}
    return {
        "schema_version": "kronos_type1_report_revision.v2",
        "revision_id": f"type1-r{number:04d}", "revision_ordinal": number,
        "identity": IDENTITY, "policy": POLICY,
        "result": REPORT_RESULT,
        "source_sha256": sources, "evidence": evidence, "false_research_locks": LOCKS,
        "claims": REPORT_CLAIMS,
    }


def test_catalog_is_alternating_immutable_and_no_go_visible(tmp_path):
    first = insert_report_revision(tmp_path, _revision(tmp_path))
    first_materialized = materialize_report_revision(tmp_path, first["event_sha256"])
    second = insert_report_revision(tmp_path, _revision(tmp_path, 2))
    second_materialized = materialize_report_revision(tmp_path, second["event_sha256"])
    tip = commit_report_tip(tmp_path, second_materialized["event_sha256"])
    snapshot = verify_report_catalog(tmp_path)
    assert snapshot["state"] == "COMMITTED"
    assert snapshot["event_count"] == 4
    assert tip["latest_revision_event_sha256"] == second["event_sha256"]
    assert snapshot["revision"]["result"]["verdict"] == "NO_GO"
    report = (tmp_path / "type1_reports" / "objects" / f"type1-r0002-{second_materialized['html_sha256']}.html").read_text(encoding="utf-8")
    assert "NOT_RUN" in report and "NO_GO_ONLY" in json.dumps(snapshot["revision"])
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
def test_catalog_rejects_semantic_authority_envelope_tamper(tmp_path):
    from stom_rl.daily_type1_authority import canonical_json

    _sources(tmp_path)
    source = tmp_path / "authority.json"
    value = json.loads(source.read_text())
    value["authority"]["fresh_oos"]["no_read"] = False
    source.write_bytes(canonical_json(value))
    with pytest.raises(Type1ReportError, match="frozen v5 authority"):
        report_source_sha256(tmp_path)
    assert REPLACEMENT_OUTER_IDENTITY == {
        "authority_id": "type1-krx-authority-20260724-004",
        "dataset_id": "type1-close-20260803-005",
        "train_id": "type1-public-005",
        "train_run_id": "train_type1-public-005",
        "custody_uid": "type1-fresh-oos-20260803-005",
        "report_family": "kronos.type1.report.v1",
    }
    amendment = json.loads(AMENDMENT_PATH.read_text(encoding="utf-8"))
    assert amendment["schema_version"] == "kronos.type1.g002-recovery-amendment.v4"
    assert amendment["amendment_id"] == "KRONOS-TYPE1-G002-RECOVERY-2026-07-24-004"
    assert amendment["replacement_identity"] == {
        key: REPLACEMENT_OUTER_IDENTITY[key]
        for key in ("authority_id", "dataset_id", "train_id", "train_run_id", "custody_uid")
    }
    assert [(item["dataset_id"], item["models_created"]) for item in amendment["preserved_aborted_evidence"]] == [
        ("type1-close-20260803-001", 0),
        ("type1-close-20260803-002", 0),
        ("type1-close-20260803-003", 0),
        ("type1-close-20260803-004", 0),
    ]
    assert amendment["preserved_aborted_evidence"][3]["status"] == "MATERIALIZED_NOT_TRAINED_QUARANTINED"
    assert amendment["quarantined_authorities"] == [
        {
            "authority_id": "type1-krx-authority-20260723-002",
            "authority_sha256": "7d0ea6d76e3181da6caef232ce0c152645c290a290021e906d700667f8a059a2",
            "status": "QUARANTINED", "models_created": 0,
            "fresh_oos": {"status": "NOT_RUN", "no_read": True},
        },
        {
            "authority_id": "type1-krx-authority-20260724-003",
            "authority_sha256": "30e34b05fe65e31b2cbb826a48628946fa3f03dc7fc7f868ebd41ff36fcef1fe",
            "rows_sha256": "0af2be6cba26827f48ea00bf0caf700b1ce40e6fc1c2cfdebf1710ae39dfbd11",
            "status": "QUARANTINED_MATERIALIZED_NOT_TRAINED", "models_created": 0,
            "fresh_oos": {"status": "NOT_RUN", "no_read": True},
        },
    ]
    assert amendment["authority_contract"]["authority_metadata_cutoff"] == "2026-07-24"
    assert amendment["authority_contract"]["authority_metadata_scope"] == (
        "MDCSTAT23801 instrument-master metadata only; price, calendar, ranking, "
        "public-row, and fresh-OOS access end at 2025-06-30."
    )
    assert amendment["fresh_oos"]["no_price_or_oos_query_after"] == "2025-06-30"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("authority_metadata_cutoff", "2026-07-25"),
        ("authority_metadata_scope", "metadata includes post-cutoff prices"),
    ],
)
def test_report_builder_rejects_amendment_authority_metadata_tampering(tmp_path, monkeypatch, field, value):
    original_read_json = type1_report._read_json

    def tampered_read_json(path, label):
        source = original_read_json(path, label)
        if label != "amendment":
            return source
        source = dict(source)
        authority_contract = dict(source["authority_contract"])
        authority_contract[field] = value
        source["authority_contract"] = authority_contract
        return source

    monkeypatch.setattr(type1_report, "_read_json", tampered_read_json)
    with pytest.raises(Type1ReportError, match="authority metadata scope"):
        _sources(tmp_path)


def test_report_uses_seven_ordinary_anchor_linked_sections(tmp_path):
    revision = insert_report_revision(tmp_path, _revision(tmp_path))
    object_event = materialize_report_revision(tmp_path, revision["event_sha256"])
    report = (tmp_path / "type1_reports" / "objects" / f"type1-r0001-{object_event['html_sha256']}.html").read_text(encoding="utf-8")
    assert report.count("<section ") == 7
    assert 'role="tab"' not in report and 'role="tabpanel"' not in report
    for section in ("overview", "identity", "protocol", "training", "validation", "custody", "integrity"):
        assert f'href="#{section}"' in report
        assert f'id="{section}"' in report
    assert M3E_STATEMENT == "LINUCB_CONTEXTUAL_BANDIT_NO_GO_FIVE_SEEDS_23BP_FRESH_OOS_NOT_RUN_UNCHANGED"
    assert M3E_STATEMENT in report
def _rebind_revision(run, revision):
    sources = report_source_sha256(run)
    revision["source_sha256"] = sources
    revision["evidence"] = {
        label: sources[label] for label in (
            "type1_identity", "public_run_seal", "deployment_lock", "attempt_parent",
            "amendment", "protocol", "preregistration", "authority", "builder_source",
        )
    }

def _mutate_manifest(run, mutate):
    manifest_path = run / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutate(manifest)
    manifest_path.write_bytes(type1_report._canonical(manifest))
    sources = report_source_sha256(run)
    (run / "receipt.json").write_bytes(type1_report._canonical({
        "manifest_sha256": sources["run_manifest"], "execution_status": "COMPLETE",
        "verdict": "NO_GO", "fresh_oos": {"state": "NOT_RUN", "metrics": None},
    }))

@pytest.mark.parametrize(
    "mutate",
    [
        lambda manifest: manifest["members"]["primary"]["0"].update({"actual_sb3_timesteps": 199999}),
        lambda manifest: manifest["members"]["shuffled_reward"]["4"].update({"device": "cuda"}),
        lambda manifest: manifest["members"]["primary"].pop("4"),
        lambda manifest: manifest["members"]["primary"].update({"5": dict(manifest["members"]["primary"]["4"])}),
        lambda manifest: manifest["controls"].update({"integrity_ok": False}),
        lambda manifest: manifest.update({"fresh_oos": {"state": "RUN", "metrics": {}}}),
    ],
)
def test_report_rejects_invalid_runner_member_or_oos_evidence(tmp_path, mutate):
    revision = _revision(tmp_path)
    _mutate_manifest(tmp_path, mutate)
    _rebind_revision(tmp_path, revision)
    with pytest.raises(Type1ReportError):
        insert_report_revision(tmp_path, revision)

@pytest.mark.parametrize(
    "field,value",
    [
        ("policy", dict(POLICY, primary_cost_rate="0.0022")),
        ("result", dict(REPORT_RESULT, fresh_oos_read_performed=True)),
        ("claims", dict(REPORT_CLAIMS, execution_outcome="GO")),
        ("claims", {"profitability": "PROFITABLE"}),
        ("false_research_locks", dict(LOCKS, live_broker_order_allowed=True)),
    ],
)
def test_report_rejects_contradictory_completion_claims_cost_and_locks(tmp_path, field, value):
    revision = _revision(tmp_path)
    revision[field] = value
    with pytest.raises(Type1ReportError):
        insert_report_revision(tmp_path, revision)

def test_verification_is_pure_and_tip_reconciliation_is_explicit_cas(tmp_path):
    revision = insert_report_revision(tmp_path, _revision(tmp_path))
    materialization = materialize_report_revision(tmp_path, revision["event_sha256"])
    tip = commit_report_tip(tmp_path, materialization["event_sha256"])
    db = tmp_path / "type1_reports" / "current_parent.sqlite3"
    con = sqlite3.connect(db)
    con.execute("UPDATE current_parent SET state='MATERIALIZED' WHERE singleton=1")
    con.commit()
    con.close()
    with pytest.raises(Type1ReportError, match="current-parent"):
        verify_report_catalog(tmp_path)
    con = sqlite3.connect(db)
    assert con.execute("SELECT event_sha256,state FROM current_parent").fetchone() == (
        materialization["event_sha256"], "MATERIALIZED"
    )
    con.close()
    assert reconcile_report_tip(tmp_path) == tip
    assert verify_report_catalog(tmp_path)["state"] == "COMMITTED"

def test_materialized_orphan_and_stale_writer_cas_fail_closed(tmp_path):
    revision = insert_report_revision(tmp_path, _revision(tmp_path))
    materialization = materialize_report_revision(tmp_path, revision["event_sha256"])
    db = tmp_path / "type1_reports" / "current_parent.sqlite3"
    con = sqlite3.connect(db)
    con.execute("UPDATE current_parent SET event_sha256=?,state='REVISION'", (revision["event_sha256"],))
    con.commit()
    con.close()
    with pytest.raises(Type1ReportError, match="current-parent"):
        verify_report_catalog(tmp_path)
    with pytest.raises(Type1ReportError, match="no committed tip orphan"):
        reconcile_report_tip(tmp_path)
    with pytest.raises(Type1ReportError):
        commit_report_tip(tmp_path, materialization["event_sha256"])
@pytest.mark.parametrize(
    "mutate",
    [
        lambda receipt: receipt.update({"role": "runner_receipt"}),
        lambda receipt: receipt.update({"status": "RUNNING"}),
        lambda receipt: receipt.update({"dataset_id": "type1-close-20260803-004"}),
    ],
)
def test_report_rejects_nonmaterializer_completion_receipt(tmp_path, mutate):
    revision = _revision(tmp_path)
    receipt_path = tmp_path.parent / "materializer_complete_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    mutate(receipt)
    receipt_path.write_bytes(type1_report._canonical(receipt))
    _rebind_revision(tmp_path, revision)
    with pytest.raises(Type1ReportError, match="materializer completion"):
        insert_report_revision(tmp_path, revision)

def test_report_rejects_missing_pretraining_evidence(tmp_path):
    revision = _revision(tmp_path)
    _mutate_manifest(tmp_path, lambda manifest: manifest.pop("pretraining_gate"))
    _rebind_revision(tmp_path, revision)
    with pytest.raises(Type1ReportError, match="pretraining"):
        insert_report_revision(tmp_path, revision)
