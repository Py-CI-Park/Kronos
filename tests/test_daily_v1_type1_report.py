import json

import pytest
import sqlite3
import stom_rl.daily_v1_type1_report as type1_report

from stom_rl.daily_v1_type1_report import (
    AMENDMENT_PATH, IDENTITY, LOCKS, M3E_STATEMENT, POLICY, REPORT_CLAIMS,
    RECOVERED_REPORT_CLAIMS, RECOVERED_REPORT_EVIDENCE_LABELS, REPORT_EVIDENCE_LABELS,
    REPORT_RESULT, REPLACEMENT_OUTER_IDENTITY,
    Type1ReportError, build_completed_report_revision, commit_report_tip,
    initialize_report_authority, insert_report_revision, materialize_report_revision,
    reconcile_report_tip, report_source_sha256, verify_report_catalog,
)


_AUTHORITY_SCHEMA = "kronos.type1.krx-public-authority.v2"
_AUTHORITY_FILES = (
    "type1_identity.json",
    "p6_public_run_seal.json",
    "deployment_lock.json",
    "attempt_parent.json",
    "authority.json",
)
_REPORT_EVIDENCE_LABELS = REPORT_EVIDENCE_LABELS
_AUTHORITY_ORDERED_SESSIONS = ["2023-12-28", "2023-12-29", "2024-01-02", "2025-06-30"]


def _authority_sessions():
    return {
        "count": len(_AUTHORITY_ORDERED_SESSIONS),
        "first": _AUTHORITY_ORDERED_SESSIONS[0],
        "last": _AUTHORITY_ORDERED_SESSIONS[-1],
        "ordered": list(_AUTHORITY_ORDERED_SESSIONS),
        "pairs": [[0, 1], [2, 3]],
        "parity": 0,
        "trailing_embargo": [],
    }


@pytest.fixture(autouse=True)
def _allow_synthetic_authority(monkeypatch):
    import stom_rl.daily_type1_authority as authority_module

    def validate_authority(envelope):
        if not isinstance(envelope, dict) or set(envelope) != {"authority", "integrity", "schema"} or envelope.get("schema") != _AUTHORITY_SCHEMA:
            raise ValueError("synthetic authority envelope is invalid")

    monkeypatch.setattr(authority_module, "validate_authority", validate_authority)
    monkeypatch.setattr(authority_module, "canonical_json", type1_report._canonical)


def _authority_envelope(*, authority_id=IDENTITY["authority_id"], integrity="test"):
    return {
        "schema": _AUTHORITY_SCHEMA,
        "authority": {
            "authority_id": authority_id,
            "fresh_oos": {"status": "NOT_RUN", "no_read": True},
            "sessions": _authority_sessions(),
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


def _member_artifact_sha256(run):
    return {
        f"{kind}/seed_{seed}/final_model.zip": type1_report._sha(
            (run / kind / f"seed_{seed}" / "final_model.zip").read_bytes()
        )
        for kind in ("primary", "shuffled_reward")
        for seed in range(5)
    } | {
        f"{kind}/seed_{seed}/normalizer.json": type1_report._sha(
            (run / kind / f"seed_{seed}" / "normalizer.json").read_bytes()
        )
        for kind in ("primary", "shuffled_reward")
        for seed in range(5)
    }



def _materializer_sha256(run):
    return {
        "public_rows_sha256": type1_report._sha((run.parent / "public_rows.json").read_bytes()),
        "dataset_manifest_sha256": type1_report._sha((run.parent / "dataset_manifest.json").read_bytes()),
        "materializer_complete_receipt_sha256": type1_report._sha((run.parent / "materializer_complete_receipt.json").read_bytes()),
    }


def _materializer_evidence(run):
    materializer_sha256 = _materializer_sha256(run)
    materializer_source_sha256 = "2" * 64
    authority_source = run / "authority.json"
    if not authority_source.exists():
        authority_source = run / "frozen_authority_envelope.json"
    return {
        **materializer_sha256,
        "materializer_output_sha256": materializer_sha256["public_rows_sha256"],
        "materializer_source_sha256": materializer_source_sha256,
        "materializer_source_hashes": {
            "protocol": type1_report._sha(type1_report.PROTOCOL_PATH.read_bytes()),
            "preregistration": type1_report._sha(type1_report.PREREG_PATH.read_bytes()),
            "amendment": type1_report._sha(type1_report.AMENDMENT_PATH.read_bytes()),
            "authority": type1_report._sha(authority_source.read_bytes()),
            "materializer": materializer_source_sha256,
        },
    }


def _runner_recovery_source_sha256(run):
    authority_source = run / "authority.json"
    if not authority_source.exists():
        authority_source = run / "frozen_authority_envelope.json"
    dataset_manifest_sha256 = type1_report._sha((run.parent / "dataset_manifest.json").read_bytes())
    return {
        "runner": type1_report._sha((type1_report.REPO_ROOT / "stom_rl" / "daily_type1_public_run.py").read_bytes()),
        "market": type1_report._sha((type1_report.REPO_ROOT / "stom_rl" / "daily_type1_market.py").read_bytes()),
        "protocol": type1_report._sha(type1_report.PROTOCOL_PATH.read_bytes()),
        "amendment": type1_report._sha(type1_report.AMENDMENT_PATH.read_bytes()),
        "authority": type1_report._sha(authority_source.read_bytes()),
        "public_rows": type1_report._sha((run.parent / "public_rows.json").read_bytes()),
        "dataset_manifest": dataset_manifest_sha256,
        "materializer_manifest": dataset_manifest_sha256,
        "materializer_complete_receipt": type1_report._sha((run.parent / "materializer_complete_receipt.json").read_bytes()),
    }


def _publication_member_inventory(run):
    manifest = json.loads((run / "recovery_manifest.json").read_text(encoding="utf-8"))
    inventory = []
    for kind in ("primary", "shuffled_reward"):
        for seed in range(5):
            member = manifest["members"][kind][str(seed)]
            evidence = member["reload_receipt"]["evidence"]
            inventory.append({
                "family": kind,
                "seed": seed,
                "directory": f"{kind}/seed_{seed}",
                "model_sha256": member["artifacts"]["model_sha256"],
                "normalizer_sha256": member["artifacts"]["normalizer_sha256"],
                "normalizer_digest": evidence["normalizer_digest"],
                "validation_pairs_digest": evidence["validation_pairs_sha256"],
                "timesteps": 200000,
                "device": "cpu",
            })
    return inventory


def _write_publication_receipt(run, *, mutate=None, recovered=False):
    import stom_rl.daily_type1_publication as publication

    authority_path = run / "frozen_authority_envelope.json"
    hidden_authority_path = None
    if authority_path.exists():
        hidden_authority_path = run.parent / f".{run.name}.frozen_authority_envelope.json"
        if hidden_authority_path.exists():
            raise AssertionError("stale hidden authority fixture")
        authority_path.replace(hidden_authority_path)
    try:
        run_evidence = publication._verify_run_root(
            run,
            allow_publication_receipt=(run / type1_report.PUBLICATION_RECEIPT_NAME).exists(),
            run_evidence_mode=(
                publication._RUN_EVIDENCE_MODE_RECOVERED
                if recovered
                else publication._RUN_EVIDENCE_MODE_COMPLETED
            ),
        )
    finally:
        if hidden_authority_path is not None:
            hidden_authority_path.replace(authority_path)
    receipt = publication._publication_receipt(
        source_logical_path=type1_report.PUBLICATION_SOURCE_LOGICAL_PATH,
        destination_logical_path=type1_report.PUBLICATION_DESTINATION_LOGICAL_PATH,
        run_evidence=run_evidence,
        materializer_evidence=_materializer_evidence(run),
    )
    if mutate is not None:
        mutate(receipt)
    (run / type1_report.PUBLICATION_RECEIPT_NAME).write_bytes(type1_report._canonical(receipt))
    return receipt


def _refresh_completed_publication_receipt_hashes(run):
    receipt_path = run / type1_report.PUBLICATION_RECEIPT_NAME
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["run_manifest_sha256"] = type1_report._sha((run / "run_manifest.json").read_bytes())
    receipt["run_receipt_sha256"] = type1_report._sha((run / "receipt.json").read_bytes())
    receipt["member_artifact_sha256"] = _member_artifact_sha256(run)
    receipt["materializer_sha256"] = _materializer_sha256(run)
    receipt_path.write_bytes(type1_report._canonical(receipt))


def _refresh_recovered_publication_receipt_hashes(run):
    receipt_path = run / type1_report.PUBLICATION_RECEIPT_NAME
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    recovery_manifest = json.loads((run / "recovery_manifest.json").read_text(encoding="utf-8"))
    materializer_evidence = _materializer_evidence(run)
    materializer_sha256 = _materializer_sha256(run)
    source_hashes = _runner_recovery_source_sha256(run)
    receipt["disclosure"] = {
        "recovery_manifest_sha256": type1_report._sha((run / "recovery_manifest.json").read_bytes()),
        "blocked_receipt_sha256": type1_report._sha((run / "receipt.json").read_bytes()),
        "members": _member_artifact_sha256(run),
    }
    receipt["identity"] = recovery_manifest["identities"]
    receipt["recovery_receipt_sha256"] = type1_report._sha((run / "recovery_receipt.json").read_bytes())
    receipt["materializer_sha256"] = materializer_sha256
    receipt["materializer_public_rows_sha256"] = materializer_sha256["public_rows_sha256"]
    receipt["materializer_source_sha256"] = materializer_evidence["materializer_source_sha256"]
    receipt["materializer_source_hashes"] = materializer_evidence["materializer_source_hashes"]
    receipt["source_hashes"] = {
        "publisher_source": type1_report._sha((type1_report.REPO_ROOT / "stom_rl" / "daily_type1_publication.py").read_bytes()),
        **source_hashes,
    }
    receipt_path.write_bytes(type1_report._canonical(receipt))


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
    train_pairs_sha256 = "1" * 64
    validation_pairs_sha256 = "2" * 64
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
                "validation_pairs_sha256": validation_pairs_sha256,
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
                "validation": {"nav_krw": 60000000 + seed, "deterministic": True},
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
                "train_pairs_sha256": train_pairs_sha256,
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
        "authority": {"authority_id": IDENTITY["authority_id"], "sessions": _authority_sessions()},
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
    if execution_status == "COMPLETE" and verdict == "NO_GO":
        _write_publication_receipt(run)
    return authority_path
def _prepare_recovered_runner(run):
    authority_path = _prepare_completed_runner(run)
    completed_manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    (run / "run_manifest.json").unlink()
    (run / type1_report.PUBLICATION_RECEIPT_NAME).unlink()
    blocked_receipt = dict(type1_report.BLOCKED_RUN_RECEIPT)
    (run / "receipt.json").write_bytes(type1_report._canonical(blocked_receipt))
    blocked_receipt_sha256 = type1_report._sha((run / "receipt.json").read_bytes())
    source_sha256 = _runner_recovery_source_sha256(run)
    report_sources = {
        "protocol": source_sha256["protocol"],
        "amendment": source_sha256["amendment"],
        "authority": source_sha256["authority"],
        "public_rows": source_sha256["public_rows"],
        "dataset_manifest": source_sha256["dataset_manifest"],
        "materializer_complete_receipt": source_sha256["materializer_complete_receipt"],
    }
    authority_envelope = json.loads(authority_path.read_text(encoding="utf-8"))
    dataset_manifest = json.loads((run.parent / "dataset_manifest.json").read_text(encoding="utf-8"))
    recovery_identity = {
        **type1_report.REPLACEMENT_IDENTITY,
        "amendment_sha256": source_sha256["amendment"],
        "authority_sha256": source_sha256["authority"],
        "materializer_sha256": source_sha256["materializer_manifest"],
        "materializer_complete_receipt_sha256": source_sha256["materializer_complete_receipt"],
        "source_database_identity": dataset_manifest["source_database_identity"],
        "materializer_source_sha256": dataset_manifest["materializer_source_sha256"],
        "preregistration_sha256": type1_report._sha(type1_report.PREREG_PATH.read_bytes()),
        "parent_protocol_sha256": source_sha256["protocol"],
        "runner_source_sha256": source_sha256["runner"],
        "authority_sessions": authority_envelope["authority"]["sessions"],
    }
    members = json.loads(type1_report._canonical(completed_manifest["members"]).decode("utf-8"))
    for kind in ("primary", "shuffled_reward"):
        for seed in range(5):
            members[kind][str(seed)]["artifact_paths"] = {
                "model": f"{kind}/seed_{seed}/final_model.zip",
                "normalizer": f"{kind}/seed_{seed}/normalizer.json",
            }
    validation_pairs_sha256 = members["primary"]["0"]["reload_receipt"]["evidence"]["validation_pairs_sha256"]
    normalizer_digest = members["primary"]["0"]["reload_receipt"]["evidence"]["normalizer_digest"]
    recovery_manifest = {
        "schema_version": type1_report.RECOVERY_MANIFEST_SCHEMA,
        "role": type1_report.RECOVERY_MANIFEST_ROLE,
        "status": "COMPLETE",
        "recovery_status": "COMPLETE",
        "recovery_mode": type1_report.RECOVERY_MODE,
        "source_commit": "4ba930c",
        "original_run_id": IDENTITY["train_run_id"],
        "reused_original_run_id": True,
        "original_block": {
            "path": "receipt.json",
            "receipt_sha256": blocked_receipt_sha256,
            "status": "BLOCK",
            "execution_status": "BLOCK",
            "verdict": "NO_GO",
            "reason": type1_report.ORIGINAL_BLOCK_REASON,
            "fresh_oos": dict(type1_report.RECOVERY_FRESH_OOS),
            "preserved_byte_identical": True,
        },
        "protocol": {
            "id": "KRONOS-TYPE1-G002-PUBLIC-2026-07-23",
            "sha256": source_sha256["protocol"],
        },
        "identities": recovery_identity,
        "features": list(type1_report.TYPE1_FEATURES),
        "public_splits": {
            "train": {
                "frozen_start": "2018-01-02",
                "frozen_end": "2023-12-29",
                "actual_start": "2018-01-02",
                "actual_end": "2023-12-29",
            },
            "reused_validation": {
                "frozen_start": "2024-01-02",
                "frozen_end": "2025-06-30",
                "actual_start": "2024-01-02",
                "actual_end": "2025-06-30",
            },
        },
        "session_pairing": {
            "authority_bound": True,
            "trailing_embargo": list(recovery_identity["authority_sessions"]["trailing_embargo"]),
            "validation_pairs_sha256": validation_pairs_sha256,
            "normalizer_digest": normalizer_digest,
        },
        "training": {
            "primary_seeds": [0, 1, 2, 3, 4],
            "shuffled_reward_seeds": [0, 1, 2, 3, 4],
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
            "retraining_performed": False,
        },
        "members": members,
        "aggregation": {"metric": "FIVE_SEED_IQM", "primary_nav_krw": "0", "shuffled_nav_krw": "0"},
        "pretraining_gate": completed_manifest["pretraining_gate"],
        "controls": completed_manifest["controls"],
        "source_sha256": source_sha256,
        "materializer_sha256": source_sha256["materializer_manifest"],
        "custody_bindings": type1_report._expected_recovery_custody_bindings(run, report_sources, blocked_receipt_sha256),
        "fresh_oos": dict(type1_report.RECOVERY_FRESH_OOS),
        "false_research_locks": dict(LOCKS),
        "execution_status": "COMPLETE",
        "verdict": "NO_GO",
        "decision": "NO_GO",
        "claims": dict(type1_report.RECOVERY_CLAIMS),
    }
    (run / "recovery_manifest.json").write_bytes(type1_report._canonical(recovery_manifest))
    recovery_manifest_sha256 = type1_report._sha((run / "recovery_manifest.json").read_bytes())
    recovery_receipt = {
        "schema_version": type1_report.RECOVERY_RECEIPT_SCHEMA,
        "role": type1_report.RECOVERY_RECEIPT_ROLE,
        "status": "COMPLETE",
        "execution_status": "COMPLETE",
        "verdict": "NO_GO",
        "decision": "NO_GO",
        "run_id": IDENTITY["train_run_id"],
        "recovery_manifest_sha256": recovery_manifest_sha256,
        "blocked_receipt_sha256": blocked_receipt_sha256,
        "blocked_receipt_path": "receipt.json",
        "blocked_reason": type1_report.ORIGINAL_BLOCK_REASON,
        "original_block_reason": type1_report.ORIGINAL_BLOCK_REASON,
        "original_block_preserved": True,
        "retraining_performed": False,
        "overwrite_performed": False,
        "move_performed": False,
        "delete_performed": False,
        "fresh_oos": dict(type1_report.RECOVERY_FRESH_OOS),
        "member_artifact_sha256": _member_artifact_sha256(run),
        "source_sha256": source_sha256,
        "materializer_sha256": source_sha256["materializer_manifest"],
        "outcome": "NO_GO_ONLY",
    }
    (run / "recovery_receipt.json").write_bytes(type1_report._canonical(recovery_receipt))
    _write_publication_receipt(run, recovered=True)
    return authority_path



def _sources(run):
    authority_path = run / "frozen_authority_envelope.json"
    if not (run / "run_manifest.json").exists():
        authority_path = _prepare_completed_runner(run)
    return initialize_report_authority(run, authority_path)
def _recovered_sources(run):
    authority_path = run / "frozen_authority_envelope.json"
    if not (run / "recovery_manifest.json").exists():
        authority_path = _prepare_recovered_runner(run)
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
    assert sources["publication_receipt"] == type1_report._sha(
        (tmp_path / type1_report.PUBLICATION_RECEIPT_NAME).read_bytes()
    )
    parent = json.loads((tmp_path / "attempt_parent.json").read_text(encoding="utf-8"))
    assert parent["parent_identity"] == type1_report.PARENT_ATTEMPT_IDENTITY
    assert parent["parent_status"] == "MATERIALIZED_NOT_TRAINED_QUARANTINED"
def test_initialize_report_authority_creates_sources_after_recovered_runner(tmp_path):
    authority_path = _prepare_recovered_runner(tmp_path)
    assert not (tmp_path / "run_manifest.json").exists()
    sources = initialize_report_authority(tmp_path, authority_path)
    assert all(path.is_file() for path in _authority_file_paths(tmp_path))
    assert sources == report_source_sha256(tmp_path)
    assert {"blocked_receipt", "recovery_manifest", "recovery_receipt", "publication_receipt"} <= set(sources)
    assert "run_manifest" not in sources and "run_receipt" not in sources
    paths = type1_report._report_source_paths(tmp_path)
    assert paths["blocked_receipt"] == (tmp_path / "receipt.json").absolute()
    assert paths["recovery_manifest"] == (tmp_path / "recovery_manifest.json").absolute()
    assert paths["recovery_receipt"] == (tmp_path / "recovery_receipt.json").absolute()
    recovery_receipt = json.loads((tmp_path / "recovery_receipt.json").read_text(encoding="utf-8"))
    publication_receipt = json.loads((tmp_path / type1_report.PUBLICATION_RECEIPT_NAME).read_text(encoding="utf-8"))
    assert recovery_receipt["blocked_reason"] == type1_report.ORIGINAL_BLOCK_REASON
    assert recovery_receipt["retraining_performed"] is False
    assert recovery_receipt["fresh_oos"] == type1_report.RECOVERY_FRESH_OOS
    assert len(recovery_receipt["member_artifact_sha256"]) == 20
    recovery_manifest = json.loads((tmp_path / "recovery_manifest.json").read_text(encoding="utf-8"))
    assert recovery_manifest["features"] == list(type1_report.TYPE1_FEATURES)
    assert recovery_manifest["training"]["primary_seeds"] == [0, 1, 2, 3, 4]
    assert recovery_manifest["training"]["shuffled_reward_seeds"] == [0, 1, 2, 3, 4]
    assert recovery_manifest["original_block"]["preserved_byte_identical"] is True
    assert (
        recovery_manifest["session_pairing"]["validation_pairs_sha256"]
        != recovery_manifest["pretraining_gate"]["validation_noninterference"]["train_pairs_sha256"]
    )
    assert publication_receipt["schema_version"] == type1_report.PUBLICATION_RECEIPT_SCHEMA_V2
    assert publication_receipt["run_evidence_mode"] == type1_report.PUBLICATION_RECOVERED_RUN_EVIDENCE_MODE
    assert "run_manifest_sha256" not in publication_receipt
    assert "run_receipt_sha256" not in publication_receipt
    assert "blocked_receipt_sha256" not in publication_receipt
    assert "recovery_manifest_sha256" not in publication_receipt
    assert "member_artifact_sha256" not in publication_receipt
    assert "members" not in publication_receipt
    assert "artifact_inventory_digest" not in publication_receipt
    assert publication_receipt["recovery_receipt_sha256"] == sources["recovery_receipt"]
    assert publication_receipt["identity"] == recovery_manifest["identities"]
    assert publication_receipt["original_block_reason"] == type1_report.ORIGINAL_BLOCK_REASON
    assert publication_receipt["retraining_performed"] is False
    assert publication_receipt["preserved_block_receipt"] is True
    disclosure = publication_receipt["disclosure"]
    expected_members = type1_report._expected_member_artifact_sha256(sources)
    assert disclosure == {
        "recovery_manifest_sha256": sources["recovery_manifest"],
        "blocked_receipt_sha256": sources["blocked_receipt"],
        "members": expected_members,
    }
    revision = build_completed_report_revision(tmp_path)
    assert revision["result"] == REPORT_RESULT
    assert revision["claims"] == RECOVERED_REPORT_CLAIMS
    assert revision["evidence"] == {label: sources[label] for label in RECOVERED_REPORT_EVIDENCE_LABELS}



def test_initialize_report_authority_exact_retry_is_idempotent(tmp_path):
    authority_path = _prepare_completed_runner(tmp_path)
    authority_raw = authority_path.read_bytes()
    authority_sha = type1_report._sha(authority_raw)
    prefix = type1_report._report_authority_artifact_bytes(authority_raw, authority_sha)
    for label, filename in (
        ("type1_identity", "type1_identity.json"),
        ("public_run_seal", "p6_public_run_seal.json"),
    ):
        (tmp_path / filename).write_bytes(prefix[label])
    first = initialize_report_authority(tmp_path, authority_path)
    second = initialize_report_authority(tmp_path, authority_path)
    assert second == first == report_source_sha256(tmp_path)


def test_initialize_report_authority_blocks_differing_existing_bytes_before_writes(tmp_path):
    authority_path = _prepare_completed_runner(tmp_path)
    authority_raw = authority_path.read_bytes()
    authority_sha = type1_report._sha(authority_raw)
    prefix = type1_report._report_authority_artifact_bytes(authority_raw, authority_sha)
    (tmp_path / "type1_identity.json").write_bytes(prefix["type1_identity"])
    (tmp_path / "p6_public_run_seal.json").write_bytes(b"{}")
    with pytest.raises(Type1ReportError, match="different bytes"):
        initialize_report_authority(tmp_path, authority_path)
    assert (tmp_path / "type1_identity.json").is_file()
    assert not (tmp_path / "deployment_lock.json").exists()
    assert not (tmp_path / "attempt_parent.json").exists()
    assert not (tmp_path / "authority.json").exists()


def test_initialize_report_authority_blocks_out_of_order_suffix_before_writes(tmp_path):
    authority_path = _prepare_completed_runner(tmp_path)
    authority_raw = authority_path.read_bytes()
    authority_sha = type1_report._sha(authority_raw)
    prefix = type1_report._report_authority_artifact_bytes(authority_raw, authority_sha)
    (tmp_path / "p6_public_run_seal.json").write_bytes(prefix["public_run_seal"])
    with pytest.raises(Type1ReportError, match="exact prefix"):
        initialize_report_authority(tmp_path, authority_path)
    assert not (tmp_path / "type1_identity.json").exists()
    assert (tmp_path / "p6_public_run_seal.json").is_file()
    assert not (tmp_path / "deployment_lock.json").exists()
    assert not (tmp_path / "attempt_parent.json").exists()
    assert not (tmp_path / "authority.json").exists()


def test_initialize_report_authority_requires_publication_receipt_before_writes(tmp_path):
    authority_path = _prepare_completed_runner(tmp_path)
    (tmp_path / type1_report.PUBLICATION_RECEIPT_NAME).unlink()
    with pytest.raises(Type1ReportError, match="publication_receipt"):
        initialize_report_authority(tmp_path, authority_path)
    assert all(not path.exists() for path in _authority_file_paths(tmp_path))


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
    _sources(run)
    return build_completed_report_revision(
        run,
        revision_id=f"type1-r{number:04d}",
        revision_ordinal=number,
    )
def _recovered_revision(run, number=1):
    _recovered_sources(run)
    return build_completed_report_revision(
        run,
        revision_id=f"type1-r{number:04d}",
        revision_ordinal=number,
    )



def test_build_completed_report_revision_derives_fixed_custody_sources(tmp_path):
    _sources(tmp_path)
    revision = build_completed_report_revision(tmp_path)
    sources = report_source_sha256(tmp_path)
    assert revision["schema_version"] == type1_report.REVISION_SCHEMA
    assert revision["identity"] == IDENTITY
    assert revision["identity"] is not IDENTITY
    assert revision["policy"] == POLICY
    assert revision["result"] == REPORT_RESULT
    assert revision["false_research_locks"] == LOCKS
    assert revision["claims"] == REPORT_CLAIMS
    assert revision["source_sha256"] == sources
    assert set(revision["source_sha256"]) == set(sources)
    assert revision["evidence"] == {label: sources[label] for label in REPORT_EVIDENCE_LABELS}
    assert revision["evidence"]["publication_receipt"] == sources["publication_receipt"]



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
    for label in ("Overview", "Type1 identity", "Protocol and accounting", "Training plan and observed completion", "Reused-validation", "Fresh OOS", "Failures, claims, locks, and source integrity"):
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
    with pytest.raises(Type1ReportError, match="publication receipt"):
        verify_report_catalog(tmp_path)


def test_revision_requires_publication_receipt_evidence(tmp_path):
    revision = _revision(tmp_path)
    revision["evidence"].pop("publication_receipt")
    with pytest.raises(Type1ReportError, match="evidence is incomplete"):
        insert_report_revision(tmp_path, revision)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda receipt: receipt.update({"schema_version": "kronos.type1.publication-receipt.v0"}),
        lambda receipt: receipt.update({"status": "RUNNING"}),
        lambda receipt: receipt.update({"role": "RUN_RECEIPT"}),
        lambda receipt: receipt.update({"source_logical_path": "artifacts/type1-public-runs/other"}),
        lambda receipt: receipt.update({"destination_logical_path": "webui/rl_runs/v6_daily_h1/other"}),
        lambda receipt: receipt["identity"].update({"train_run_id": "train_type1-public-004"}),
        lambda receipt: receipt["materializer_sha256"].update({"public_rows_sha256": "0" * 64}),
        lambda receipt: receipt["fresh_oos"].update({"read_performed": True}),
    ],
)
def test_report_rejects_invalid_publication_receipt(tmp_path, mutate):
    revision = _revision(tmp_path)
    receipt_path = tmp_path / type1_report.PUBLICATION_RECEIPT_NAME
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    mutate(receipt)
    receipt_path.write_bytes(type1_report._canonical(receipt))
    with pytest.raises(Type1ReportError, match="publication receipt"):
        insert_report_revision(tmp_path, revision)


def test_catalog_rejects_missing_publication_receipt_after_commit(tmp_path):
    inserted = insert_report_revision(tmp_path, _revision(tmp_path))
    materialized = materialize_report_revision(tmp_path, inserted["event_sha256"])
    commit_report_tip(tmp_path, materialized["event_sha256"])
    (tmp_path / type1_report.PUBLICATION_RECEIPT_NAME).unlink()
    with pytest.raises(Type1ReportError, match="publication_receipt"):
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


def test_report_uses_seven_tabbed_sections_and_no_go_not_run_visible(tmp_path):
    revision = insert_report_revision(tmp_path, _revision(tmp_path))
    object_event = materialize_report_revision(tmp_path, revision["event_sha256"])
    report = (tmp_path / "type1_reports" / "objects" / f"type1-r0001-{object_event['html_sha256']}.html").read_text(encoding="utf-8")
    assert report.count('role="tab"') == 7
    assert report.count('role="tabpanel"') == 7
    assert '<nav role="tablist"' in report
    for section in ("overview", "identity", "protocol", "training", "validation", "custody", "integrity"):
        assert f'id="{section}-tab"' in report
        assert f'href="#{section}"' in report
        assert f'id="{section}"' in report
        assert f'aria-labelledby="{section}-tab"' in report
    assert "NO_GO" in report
    assert "NO_GO_ONLY" in report
    assert "NOT_RUN" in report
    assert "payload was not read" in report
    assert "NOT_CLAIMED" in report
    assert M3E_STATEMENT == "LINUCB_CONTEXTUAL_BANDIT_NO_GO_FIVE_SEEDS_23BP_FRESH_OOS_NOT_RUN_UNCHANGED"
    assert M3E_STATEMENT in report

def _rebind_revision(run, revision):
    sources = report_source_sha256(run)
    revision["source_sha256"] = sources
    revision["evidence"] = {label: sources[label] for label in _REPORT_EVIDENCE_LABELS}
def _rebind_recovered_revision(run, revision):
    sources = report_source_sha256(run)
    revision["source_sha256"] = sources
    revision["evidence"] = {label: sources[label] for label in RECOVERED_REPORT_EVIDENCE_LABELS}
    revision["claims"] = RECOVERED_REPORT_CLAIMS


def _mutate_json(path, mutate):
    value = json.loads(path.read_text(encoding="utf-8"))
    mutate(value)
    path.write_bytes(type1_report._canonical(value))

def _recovery_source_sha256(run):
    return _runner_recovery_source_sha256(run)


def _refresh_recovered_hash_bindings(run):
    source_sha256 = _recovery_source_sha256(run)
    blocked_receipt_sha256 = type1_report._sha((run / "receipt.json").read_bytes())
    manifest_path = run / "recovery_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if isinstance(manifest.get("original_block"), dict):
        manifest["original_block"]["receipt_sha256"] = blocked_receipt_sha256
    manifest["source_sha256"] = source_sha256
    manifest["materializer_sha256"] = source_sha256["materializer_manifest"]
    report_sources = {
        "protocol": source_sha256["protocol"],
        "amendment": source_sha256["amendment"],
        "authority": source_sha256["authority"],
        "public_rows": source_sha256["public_rows"],
        "dataset_manifest": source_sha256["dataset_manifest"],
        "materializer_complete_receipt": source_sha256["materializer_complete_receipt"],
    }
    manifest["custody_bindings"] = type1_report._expected_recovery_custody_bindings(run, report_sources, blocked_receipt_sha256)
    manifest_path.write_bytes(type1_report._canonical(manifest))
    recovery_manifest_sha256 = type1_report._sha(manifest_path.read_bytes())
    receipt_path = run / "recovery_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["blocked_receipt_sha256"] = blocked_receipt_sha256
    receipt["recovery_manifest_sha256"] = recovery_manifest_sha256
    receipt["member_artifact_sha256"] = _member_artifact_sha256(run)
    receipt["source_sha256"] = source_sha256
    receipt["materializer_sha256"] = source_sha256["materializer_manifest"]
    receipt_path.write_bytes(type1_report._canonical(receipt))
    if (run / type1_report.PUBLICATION_RECEIPT_NAME).exists():
        _refresh_recovered_publication_receipt_hashes(run)


def _mutate_manifest(run, mutate):
    manifest_path = run / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutate(manifest)
    manifest_raw = type1_report._canonical(manifest)
    manifest_path.write_bytes(manifest_raw)
    (run / "receipt.json").write_bytes(type1_report._canonical({
        "manifest_sha256": type1_report._sha(manifest_raw), "execution_status": "COMPLETE",
        "verdict": "NO_GO", "fresh_oos": {"state": "NOT_RUN", "metrics": None},
    }))
    _refresh_completed_publication_receipt_hashes(run)


def test_build_completed_report_revision_revalidates_runner_evidence(tmp_path):
    _revision(tmp_path)
    _mutate_manifest(tmp_path, lambda manifest: manifest["controls"].update({"integrity_ok": False}))
    with pytest.raises(Type1ReportError, match="controls"):
        build_completed_report_revision(tmp_path)


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
    "mutate,refresh",
    [
        (lambda run: _mutate_json(run / "receipt.json", lambda receipt: receipt.update({"reason": "different"})), True),
        (lambda run: _mutate_json(run / "receipt.json", lambda receipt: receipt.update({"execution_status": "COMPLETE"})), True),
        (lambda run: _mutate_json(run / "recovery_manifest.json", lambda manifest: manifest.update({"execution_status": "BLOCK"})), True),
        (lambda run: _mutate_json(run / "recovery_manifest.json", lambda manifest: manifest.update({"features": {"kind": "fixture"}})), True),
        (lambda run: _mutate_json(run / "recovery_manifest.json", lambda manifest: manifest["training"].update({"seeds": [0, 1, 2, 3, 4]})), True),
        (lambda run: _mutate_json(run / "recovery_manifest.json", lambda manifest: manifest["session_pairing"].update({"validation_pairs_sha256": manifest["pretraining_gate"]["validation_noninterference"]["train_pairs_sha256"]})), True),
        (lambda run: _mutate_json(run / "recovery_manifest.json", lambda manifest: manifest.update({"original_block": {**type1_report.BLOCKED_RUN_RECEIPT, "receipt_sha256": manifest["original_block"]["receipt_sha256"]}})), True),
        (lambda run: _mutate_json(run / "recovery_manifest.json", lambda manifest: manifest["training"].update({"retraining_performed": True})), True),
        (lambda run: _mutate_json(run / "recovery_manifest.json", lambda manifest: manifest["false_research_locks"].update({"live_broker_order_allowed": True})), True),
        (lambda run: _mutate_json(run / "recovery_manifest.json", lambda manifest: manifest.update({"fresh_oos": {"state": "NOT_RUN", "metrics": None, "read_performed": True}})), True),
        (lambda run: _mutate_json(run / "recovery_manifest.json", lambda manifest: manifest["members"]["primary"]["0"]["reload_receipt"]["evidence"].update({"normalizer_digest": "0" * 64})), True),
        (lambda run: _mutate_json(run / "recovery_manifest.json", lambda manifest: manifest["members"]["primary"]["0"]["reload_receipt"]["evidence"].update({"validation_pairs_sha256": "0" * 64})), True),
        (lambda run: _mutate_json(run / "recovery_manifest.json", lambda manifest: manifest["members"]["primary"]["0"]["reload_receipt"]["evidence"].update({"validation_pairs_sha256": manifest["pretraining_gate"]["validation_noninterference"]["train_pairs_sha256"]})), True),
        (lambda run: _mutate_json(run / "recovery_receipt.json", lambda receipt: receipt.update({"recovery_manifest_sha256": "0" * 64})), False),
        (lambda run: _mutate_json(run / "recovery_receipt.json", lambda receipt: receipt.update({"retraining_performed": True})), False),
        (lambda run: _mutate_json(run / "recovery_receipt.json", lambda receipt: receipt["fresh_oos"].update({"read_performed": True})), False),
        (lambda run: _mutate_json(run / "recovery_receipt.json", lambda receipt: receipt["source_sha256"].update({"recovery_manifest": "0" * 64})), False),
        (lambda run: _mutate_json(run / type1_report.PUBLICATION_RECEIPT_NAME, lambda receipt: receipt["disclosure"].update({"blocked_receipt_sha256": "0" * 64})), False),
        (lambda run: _mutate_json(run / type1_report.PUBLICATION_RECEIPT_NAME, lambda receipt: receipt.update({"original_block_reason": "different"})), False),
        (lambda run: _mutate_json(run / type1_report.PUBLICATION_RECEIPT_NAME, lambda receipt: receipt.update({"retraining_performed": True})), False),
        (lambda run: _mutate_json(run / type1_report.PUBLICATION_RECEIPT_NAME, lambda receipt: receipt["fresh_oos"].update({"read_performed": True})), False),
        (lambda run: _mutate_json(run / type1_report.PUBLICATION_RECEIPT_NAME, lambda receipt: receipt["disclosure"]["members"].update({"primary/seed_0/final_model.zip": "0" * 64})), False),
        (lambda run: _mutate_json(run / type1_report.PUBLICATION_RECEIPT_NAME, lambda receipt: receipt.update({"run_evidence_mode": "recovered"})), False),
        (lambda run: _mutate_json(run / type1_report.PUBLICATION_RECEIPT_NAME, lambda receipt: receipt.update({"disclosure": {"run_manifest_created": False, "original_block_preserved": True}})), False),
    ],
)
def test_report_rejects_recovered_block_recovery_publication_tampering(tmp_path, mutate, refresh):
    revision = _recovered_revision(tmp_path)
    mutate(tmp_path)
    if refresh:
        _refresh_recovered_hash_bindings(tmp_path)
        _rebind_recovered_revision(tmp_path, revision)
    with pytest.raises(Type1ReportError):
        insert_report_revision(tmp_path, revision)

@pytest.mark.parametrize(
    "tamper",
    [
        "missing_count",
        "extra_field",
        "bad_count",
        "bad_first",
        "bad_last",
        "bad_parity",
        "duplicate_interior_date",
        "swapped_interior_dates",
        "invalid_date",
        "bad_pairs",
        "bad_trailing_embargo",
    ],
)
def test_report_rejects_authority_session_schema_tampering(tamper):
    sessions = _authority_sessions()
    assert type1_report._validate_authority_sessions(sessions, "fixture") == sessions
    if tamper == "missing_count":
        sessions.pop("count")
    elif tamper == "extra_field":
        sessions["legacy_pairs"] = []
    elif tamper == "bad_count":
        sessions["count"] += 1
    elif tamper == "bad_first":
        sessions["first"] = "2023-12-29"
    elif tamper == "bad_last":
        sessions["last"] = "2024-01-02"
    elif tamper == "bad_parity":
        sessions["parity"] = 1
    elif tamper == "duplicate_interior_date":
        sessions["ordered"][2] = sessions["ordered"][1]
    elif tamper == "swapped_interior_dates":
        sessions["ordered"][1], sessions["ordered"][2] = sessions["ordered"][2], sessions["ordered"][1]
    elif tamper == "invalid_date":
        sessions["ordered"][2] = "2024-02-30"
    elif tamper == "bad_pairs":
        sessions["pairs"] = [[0, 2], [1, 3]]
    elif tamper == "bad_trailing_embargo":
        sessions["trailing_embargo"] = [3]
    else:
        raise AssertionError(tamper)

    with pytest.raises(Type1ReportError, match="authority session"):
        type1_report._validate_authority_sessions(sessions, "fixture")

def test_report_rejects_recovered_identity_authority_session_artifact_mismatch(tmp_path):
    _recovered_revision(tmp_path)
    mismatch = {
        "count": 4,
        "first": "2023-12-27",
        "last": "2025-06-30",
        "ordered": ["2023-12-27", "2023-12-28", "2024-01-02", "2025-06-30"],
        "pairs": [[0, 1], [2, 3]],
        "parity": 0,
        "trailing_embargo": [],
    }
    _mutate_json(
        tmp_path / "recovery_manifest.json",
        lambda manifest: manifest["identities"].update({"authority_sessions": mismatch}),
    )
    _refresh_recovered_hash_bindings(tmp_path)
    with pytest.raises(Type1ReportError, match="authority sessions"):
        report_source_sha256(tmp_path)


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
    _refresh_completed_publication_receipt_hashes(tmp_path)
    _rebind_revision(tmp_path, revision)
    with pytest.raises(Type1ReportError, match="materializer completion"):
        insert_report_revision(tmp_path, revision)

def test_report_rejects_missing_pretraining_evidence(tmp_path):
    revision = _revision(tmp_path)
    _mutate_manifest(tmp_path, lambda manifest: manifest.pop("pretraining_gate"))
    _rebind_revision(tmp_path, revision)
    with pytest.raises(Type1ReportError, match="pretraining"):
        insert_report_revision(tmp_path, revision)

def _prepare_one_shot_fixture(tmp_path, monkeypatch, *, recovered=False):
    run = (
        tmp_path
        / "webui"
        / "rl_runs"
        / "v6_daily_h1"
        / IDENTITY["dataset_id"]
        / IDENTITY["train_run_id"]
    )
    staged_authority = _prepare_recovered_runner(run) if recovered else _prepare_completed_runner(run)
    authority = (
        tmp_path
        / "webui"
        / "rl_runs"
        / "v6_daily_h1"
        / "type1_authorities"
        / f"{IDENTITY['authority_id']}.json"
    )
    authority.parent.mkdir(parents=True, exist_ok=True)
    authority.write_bytes(staged_authority.read_bytes())
    monkeypatch.setattr(type1_report, "COMPLETED_REPORT_RUN_DIR", run.absolute())
    monkeypatch.setattr(type1_report, "FROZEN_AUTHORITY_ENVELOPE_PATH", authority.absolute())
    return run, authority


def _run_one_shot_cli(capsys, run, authority):
    code = type1_report.main([
        "--run-dir", str(run),
        "--frozen-authority-envelope", str(authority),
    ])
    output = capsys.readouterr().out.strip()
    return code, json.loads(output)


def test_completed_report_one_shot_parser_requires_explicit_paths():
    parser = type1_report.build_parser()
    help_text = parser.format_help()
    assert "Documented production command" in help_text
    assert "--run-dir" in help_text
    assert "--frozen-authority-envelope" in help_text
    with pytest.raises(SystemExit):
        parser.parse_args([])
    args = parser.parse_args([
        "--run-dir", str(type1_report.COMPLETED_REPORT_RUN_DIR),
        "--frozen-authority-envelope", str(type1_report.FROZEN_AUTHORITY_ENVELOPE_PATH),
    ])
    assert args.run_dir == type1_report.COMPLETED_REPORT_RUN_DIR
    assert args.frozen_authority_envelope == type1_report.FROZEN_AUTHORITY_ENVELOPE_PATH


def test_completed_report_one_shot_cli_creates_single_committed_report(tmp_path, monkeypatch, capsys):
    run, authority = _prepare_one_shot_fixture(tmp_path, monkeypatch)
    code, receipt = _run_one_shot_cli(capsys, run, authority)
    assert code == 0
    assert receipt["report_status"] == "COMMITTED"
    assert receipt["mode"] == "CREATED"
    assert receipt["verdict"] == "NO_GO"
    assert receipt["fresh_oos"] == {"state": "NOT_RUN", "read_performed": False}
    assert receipt["revision_id"] == "type1-r0001"
    assert receipt["revision_ordinal"] == 1
    assert receipt["catalog_event_count"] == 2
    assert receipt["object_count"] == 1
    snapshot = verify_report_catalog(run)
    assert snapshot["state"] == "COMMITTED"
    assert snapshot["event_count"] == 2
    assert snapshot["revision"]["source_sha256"] == report_source_sha256(run)
    assert snapshot["revision"]["evidence"]["publication_receipt"] == receipt["publication_receipt_sha256"]
    events = list((run / "type1_reports" / "events").iterdir())
    objects = list((run / "type1_reports" / "objects").iterdir())
    assert len(events) == 2
    assert len(objects) == 1
    html = objects[0].read_text(encoding="utf-8")
    assert html.count('role="tab"') == 7
    assert "NO_GO" in html and "NO_GO_ONLY" in html and "NOT_RUN" in html
def test_recovered_report_one_shot_cli_discloses_append_only_recovery(tmp_path, monkeypatch, capsys):
    run, authority = _prepare_one_shot_fixture(tmp_path, monkeypatch, recovered=True)
    code, receipt = _run_one_shot_cli(capsys, run, authority)
    assert code == 0
    assert receipt["report_status"] == "COMMITTED"
    assert receipt["mode"] == "CREATED"
    assert receipt["verdict"] == "NO_GO"
    assert receipt["fresh_oos"] == {"state": "NOT_RUN", "read_performed": False}
    assert receipt["run_evidence_mode"] == type1_report.RECOVERED_RUN_EVIDENCE_MODE
    for label in ("blocked_receipt", "recovery_manifest", "recovery_receipt", "publication_receipt"):
        assert label in receipt["evidence"]
    snapshot = verify_report_catalog(run)
    revision = snapshot["revision"]
    assert revision["result"] == REPORT_RESULT
    assert revision["claims"] == RECOVERED_REPORT_CLAIMS
    assert revision["evidence"] == {label: report_source_sha256(run)[label] for label in RECOVERED_REPORT_EVIDENCE_LABELS}
    assert revision["evidence"]["blocked_receipt"] == receipt["evidence"]["blocked_receipt"]
    assert revision["evidence"]["recovery_manifest"] == receipt["evidence"]["recovery_manifest"]
    assert revision["evidence"]["recovery_receipt"] == receipt["evidence"]["recovery_receipt"]
    objects = list((run / "type1_reports" / "objects").iterdir())
    assert len(objects) == 1
    html = objects[0].read_text(encoding="utf-8")
    assert html.count('role="tab"') == 7
    assert html.count('role="tabpanel"') == 7
    assert "Append-only recovery disclosure" in html
    assert "recovery_from_blocked_controls:true" in html
    assert type1_report.RECOVERY_MODE in html
    assert type1_report.ORIGINAL_BLOCK_REASON in html
    assert "original receipt remains" in html
    assert "retraining_performed:false" in html
    assert "Fresh OOS remains NOT_RUN/no-read" in html
    assert "NO_GO" in html and "NO_GO_ONLY" in html and "NOT_RUN" in html
    assert "NOT_CLAIMED" in html and "PROFITABLE" not in html and "LIVE" not in html



def test_completed_report_one_shot_cli_is_idempotent_for_matching_committed_tip(tmp_path, monkeypatch, capsys):
    run, authority = _prepare_one_shot_fixture(tmp_path, monkeypatch)
    code, first = _run_one_shot_cli(capsys, run, authority)
    assert code == 0
    events_before = sorted(path.name for path in (run / "type1_reports" / "events").iterdir())
    objects_before = sorted(path.name for path in (run / "type1_reports" / "objects").iterdir())
    code, second = _run_one_shot_cli(capsys, run, authority)
    assert code == 0
    assert second["mode"] == "VERIFIED"
    assert second["revision_event_sha256"] == first["revision_event_sha256"]
    assert second["materialization_event_sha256"] == first["materialization_event_sha256"]
    assert sorted(path.name for path in (run / "type1_reports" / "events").iterdir()) == events_before
    assert sorted(path.name for path in (run / "type1_reports" / "objects").iterdir()) == objects_before


def test_completed_report_one_shot_cli_reconciles_exact_committed_tip_orphan(tmp_path, monkeypatch, capsys):
    run, authority = _prepare_one_shot_fixture(tmp_path, monkeypatch)
    code, _ = _run_one_shot_cli(capsys, run, authority)
    assert code == 0
    db = run / "type1_reports" / "current_parent.sqlite3"
    con = sqlite3.connect(db)
    con.execute("UPDATE current_parent SET state='MATERIALIZED' WHERE singleton=1")
    con.commit()
    con.close()
    code, receipt = _run_one_shot_cli(capsys, run, authority)
    assert code == 0
    assert receipt["mode"] == "RECONCILED"
    con = sqlite3.connect(db)
    assert con.execute("SELECT state FROM current_parent WHERE singleton=1").fetchone() == ("COMMITTED",)
    con.close()
    assert verify_report_catalog(run)["state"] == "COMMITTED"


def test_completed_report_one_shot_cli_rejects_partial_catalog_before_writes(tmp_path, monkeypatch, capsys):
    run, authority = _prepare_one_shot_fixture(tmp_path, monkeypatch)
    (run / "type1_reports" / "events").mkdir(parents=True)
    (run / "type1_reports" / "objects").mkdir()
    code, receipt = _run_one_shot_cli(capsys, run, authority)
    assert code == 1
    assert receipt["report_status"] == "BLOCKED"
    assert "partial" in receipt["error"]
    assert all(not path.exists() for path in _authority_file_paths(run))


def test_completed_report_one_shot_cli_rejects_wrong_path_and_authority(tmp_path, monkeypatch, capsys):
    run, authority = _prepare_one_shot_fixture(tmp_path, monkeypatch)
    code, receipt = _run_one_shot_cli(capsys, run.parent, authority)
    assert code == 1
    assert "exact published destination" in receipt["error"]
    code, receipt = _run_one_shot_cli(capsys, run, run / "frozen_authority_envelope.json")
    assert code == 1
    assert "exact type1_authorities" in receipt["error"]
    authority.write_bytes(_authority_bytes(integrity="different-authority"))
    code, receipt = _run_one_shot_cli(capsys, run, authority)
    assert code == 1
    assert "authority hash" in receipt["error"]
    assert not (run / "type1_reports").exists()
    assert all(not path.exists() for path in _authority_file_paths(run))
