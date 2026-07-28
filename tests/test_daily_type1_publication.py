from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from stom_rl.daily_type1_contract import canonical_json_bytes, sha256_canonical
from stom_rl.daily_type1_public_data import write_public_materialization
import stom_rl.daily_type1_publication as publication
import stom_rl.daily_type1_public_run as public_run


DAILY_COLUMNS = 'date, open, high, low, close, volume, "상장주식수", "외국인주문한도수량", "외국인현보유수량", "외국인현보유비율", "기관순매수", "기관누적순매수"'
FIVE_COLUMNS = "date, open, high, low, close, volume"
FRESH_NO_READ = {"state": "NOT_RUN", "metrics": None, "read_performed": False}
NORMALIZER_DIGEST = hashlib.sha256(b"runner-normalizer").hexdigest()
VALIDATION_PAIRS_SHA256 = hashlib.sha256(b"runner-validation-pairs").hexdigest()
AUTHORITY_ORDERED_SESSIONS = ["2023-12-28", "2023-12-29", "2024-01-02", "2025-06-30"]


def _authority_sessions() -> dict[str, object]:
    return {
        "count": len(AUTHORITY_ORDERED_SESSIONS),
        "first": AUTHORITY_ORDERED_SESSIONS[0],
        "last": AUTHORITY_ORDERED_SESSIONS[-1],
        "ordered": list(AUTHORITY_ORDERED_SESSIONS),
        "pairs": [[0, 1], [2, 3]],
        "parity": 0,
        "trailing_embargo": [],
    }


def _authority() -> dict[str, object]:
    return {
        "authority_id": publication.REPLACEMENT_AUTHORITY_ID,
        "stable_symbols": ["000250"],
        "sessions": _authority_sessions(),
        "anchor_date": "2017-12-29",
        "ranking": {},
        "provider": {},
        "query_profile": {},
        "raw_sha256": "0" * 64,
    }


def _dbs(tmp_path: Path) -> tuple[Path, Path]:
    daily_path, five_path = tmp_path / "daily.sqlite", tmp_path / "five.sqlite"
    with sqlite3.connect(daily_path) as conn:
        conn.execute(f'CREATE TABLE "A000250" ({DAILY_COLUMNS})')
        for day in range(1, 26):
            conn.execute(
                'INSERT INTO "A000250" VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (20171200 + day, day, day, day, day, day * 10, 100, 0, 0, day, day, 0),
            )
        conn.executemany('INSERT INTO "A000250" VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', [
            (20231228, 100, 100, 100, 100, 10, 100, 0, 0, 1, 1, 0),
            (20231229, 101, 101, 101, 101, 11, 100, 0, 0, 2, 2, 0),
            (20240102, 102, 102, 102, 102, 12, 100, 0, 0, 3, 3, 0),
            (20250630, 103, 103, 103, 103, 13, 100, 0, 0, 4, 4, 0),
        ])
    with sqlite3.connect(five_path) as conn:
        conn.execute(f'CREATE TABLE "A000250" ({FIVE_COLUMNS})')
        conn.executemany('INSERT INTO "A000250" VALUES (?, ?, ?, ?, ?, ?)', [
            (202312281520, 1, 1, 1, 90, 1),
            (202312291520, 1, 1, 1, 100, 1),
            (202401021520, 1, 1, 1, 110, 1),
            (202506301520, 1, 1, 1, 120, 1),
        ])
    return daily_path, five_path


def _materialization_parent(tmp_path: Path) -> Path:
    daily_path, five_path = _dbs(tmp_path)
    return write_public_materialization(
        out_root=tmp_path / "webui" / "rl_runs" / "v6_daily_h1",
        daily_db_path=daily_path,
        fivemin_db_path=five_path,
        authority=_authority(),
        test_only=True,
    )["destination"]


def _normalizer(seed: int, kind: str) -> bytes:
    return canonical_json_bytes({
        "kind": "market_type7_train_only",
        "digest": NORMALIZER_DIGEST,
        "scales": [{"center": "0", "scale": "1"} for _ in range(7)],
    })


def _write_artifacts(root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    completed_members: dict[str, dict[str, object]] = {"primary": {}, "shuffled_reward": {}}
    recovered_members: dict[str, dict[str, object]] = {"primary": {}, "shuffled_reward": {}}
    artifact_sha256: dict[str, str] = {}
    for kind in ("primary", "shuffled_reward"):
        for seed in range(5):
            member_dir = root / kind / f"seed_{seed}"
            member_dir.mkdir(parents=True)
            model_raw = f"{kind}-{seed}-final-model".encode()
            normalizer_raw = _normalizer(seed, kind)
            (member_dir / "final_model.zip").write_bytes(model_raw)
            (member_dir / "normalizer.json").write_bytes(normalizer_raw)
            model_sha = hashlib.sha256(model_raw).hexdigest()
            normalizer_sha = hashlib.sha256(normalizer_raw).hexdigest()
            normalizer = json.loads(normalizer_raw.decode("utf-8"))
            artifacts = {"model_sha256": model_sha, "normalizer_sha256": normalizer_sha}
            evidence = {
                **artifacts,
                "normalizer_digest": normalizer["digest"],
                "validation_pairs_sha256": VALIDATION_PAIRS_SHA256,
                "model_device": "cpu",
                "num_timesteps": 200000,
            }
            completed_members[kind][str(seed)] = {
                "seed": seed,
                "timesteps": 200000,
                "actual_sb3_timesteps": 200000,
                "device": "cpu",
                "artifact": "FINAL_MODEL_ONLY",
                "artifacts": artifacts,
                "reload_receipt": {**artifacts, "deterministic": True, "evidence": evidence},
                "validation": {"nav_krw": 60000000 + seed, "deterministic": True},
            }
            directory = f"{kind}/seed_{seed}"
            recovered_members[kind][str(seed)] = {
                "seed": seed,
                "timesteps": 200000,
                "actual_sb3_timesteps": 200000,
                "device": "cpu",
                "artifact": "FINAL_MODEL_ONLY",
                "artifact_paths": {"model": f"{directory}/final_model.zip", "normalizer": f"{directory}/normalizer.json"},
                "artifacts": artifacts,
                "reload_receipt": {**artifacts, "deterministic": True, "evidence": evidence},
                "validation": {"nav_krw": 60000000 + seed, "deterministic": True},
            }
            artifact_sha256[f"{directory}/final_model.zip"] = model_sha
            artifact_sha256[f"{directory}/normalizer.json"] = normalizer_sha
    return {
        "completed_members": completed_members,
        "recovered_members": recovered_members,
        "artifact_sha256": dict(sorted(artifact_sha256.items())),
        "normalizer_digest": NORMALIZER_DIGEST,
        "validation_pairs_sha256": VALIDATION_PAIRS_SHA256,
    }


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _authority_file(parent: Path) -> Path:
    path = parent.parent / "authority.json"
    path.write_bytes(canonical_json_bytes(_authority()))
    return path


def _source_hashes(parent: Path) -> dict[str, str]:
    materializer_manifest = json.loads((parent / "dataset_manifest.json").read_text(encoding="utf-8"))
    materializer_hashes = materializer_manifest["source_hashes"]
    authority_path = _authority_file(parent)
    return {
        "runner": _sha_file(Path(public_run.__file__)),
        "market": _sha_file(publication.REPO_ROOT / "stom_rl" / "daily_type1_market.py"),
        "protocol": materializer_hashes["protocol"],
        "amendment": materializer_hashes["amendment"],
        "authority": _sha_file(authority_path),
        "public_rows": _sha_file(parent / "public_rows.json"),
        "dataset_manifest": _sha_file(parent / "dataset_manifest.json"),
        "materializer_manifest": _sha_file(parent / "dataset_manifest.json"),
        "materializer_complete_receipt": _sha_file(parent / "materializer_complete_receipt.json"),
    }


def _runner_identity(parent: Path) -> dict[str, object]:
    materializer_manifest = json.loads((parent / "dataset_manifest.json").read_text(encoding="utf-8"))
    materializer_hashes = materializer_manifest["source_hashes"]
    source_hashes = _source_hashes(parent)
    return {
        "authority_id": publication.REPLACEMENT_AUTHORITY_ID,
        "dataset_id": publication.DATASET_ID,
        "train_id": publication.REPLACEMENT_TRAIN_ID,
        "train_run_id": publication.REPLACEMENT_RUN_ID,
        "custody_uid": publication.REPLACEMENT_CUSTODY_UID,
        "amendment_sha256": source_hashes["amendment"],
        "authority_sha256": source_hashes["authority"],
        "materializer_sha256": source_hashes["materializer_manifest"],
        "materializer_complete_receipt_sha256": source_hashes["materializer_complete_receipt"],
        "source_database_identity": materializer_manifest["source_database_identity"],
        "materializer_source_sha256": materializer_hashes["materializer"],
        "preregistration_sha256": materializer_manifest["preregistration_sha256"],
        "parent_protocol_sha256": source_hashes["protocol"],
        "runner_source_sha256": source_hashes["runner"],
        "authority_sessions": _authority()["sessions"],
    }


def _runner_rows() -> list[dict[str, object]]:
    return [
        {"date": "2023-12-28"},
        {"date": "2023-12-29"},
        {"date": "2024-01-02"},
        {"date": "2025-06-30"},
    ]


class _RunnerFixtureOperations:
    def build_pairs(self, rows: list[dict[str, object]], *, split: str, shuffled_seed: int | None = None) -> list[dict[str, object]]:
        return [
            {
                "candidate_values": [[index + 1]],
                "candidate_missing": [[0]],
                "availability_mask": [True],
                "post_decision_fill_available": [True],
                "symbols": ["000250"],
                "gross_returns": ["0.01"],
                "decision_date": str(row["date"]),
                "settlement_date": str(row.get("settlement_date", row["date"])),
            }
            for index, row in enumerate(rows)
        ]

    def normalizer_digest(self) -> str:
        return NORMALIZER_DIGEST

    def evaluate_saved(
        self,
        path: Path,
        validation_rows: list[dict[str, object]],
        *,
        seed: int,
        expected_pair_bytes: bytes,
        expected_normalizer_digest: str,
        expected_normalizer_sha256: str,
    ) -> dict[str, object]:
        model_sha = _sha_file(path / "final_model.zip")
        normalizer_sha = _sha_file(path / "normalizer.json")
        if expected_normalizer_digest != NORMALIZER_DIGEST or expected_normalizer_sha256 != normalizer_sha:
            raise ValueError("fixture normalizer binding mismatch")
        return {
            "nav_krw": 60000000 + seed,
            "deterministic": True,
            "reload_evidence": {
                "model_sha256": model_sha,
                "normalizer_sha256": normalizer_sha,
                "normalizer_digest": NORMALIZER_DIGEST,
                "validation_pairs_sha256": hashlib.sha256(expected_pair_bytes).hexdigest(),
                "model_device": "cpu",
                "num_timesteps": 200000,
            },
        }

    def controls(
        self,
        train_rows: list[dict[str, object]],
        validation_rows: list[dict[str, object]],
        primary: dict[str, dict[str, object]],
        shuffled: dict[str, dict[str, object]],
    ) -> dict[str, object]:
        return {
            "integrity_ok": True,
            "integrity_reasons": [],
            "mutation_invariance": {"train_only_normalizer_unchanged": True, "train_pairs_byte_identical": True},
            "scientific_gates_pass": False,
            "scientific_gate_reasons": ["fixture_control_gate_miss"],
            "shuffle_retraining": {"seeds": [0, 1, 2, 3, 4], "timesteps_per_seed": 200000, "all_members_recorded": True},
        }


def _block_receipt(reason: str = publication._ORIGINAL_BLOCK_REASON) -> dict[str, object]:
    return {
        "execution_status": "BLOCK",
        "fresh_oos": {"state": "NOT_RUN", "metrics": None},
        "reason": reason,
        "verdict": "NO_GO",
    }


def _write_recovered_run(
    root: Path,
    parent: Path,
    *,
    reason: str = publication._ORIGINAL_BLOCK_REASON,
    retraining: bool = False,
    fresh_oos: dict[str, object] | None = None,
    controls_integrity: bool = True,
    receipt_status: str = "COMPLETE",
    receipt_decision: str = "NO_GO",
) -> dict[str, Any]:
    artifacts = _write_artifacts(root)
    block_raw = canonical_json_bytes(_block_receipt(reason))
    (root / "receipt.json").write_bytes(block_raw)
    blocked_sha = hashlib.sha256(block_raw).hexdigest()
    source_hashes = _source_hashes(parent)
    identity = _runner_identity(parent)
    protocol = json.loads(public_run.PROTOCOL_PATH.read_text(encoding="utf-8"))
    fresh = dict(fresh_oos or FRESH_NO_READ)
    manifest = {
        "schema_version": public_run.RECOVERY_MANIFEST_SCHEMA,
        "role": public_run.RECOVERY_ROLE,
        "status": "COMPLETE",
        "recovery_status": "COMPLETE",
        "recovery_mode": public_run.RECOVERY_MODE,
        "source_commit": public_run.RECOVERY_SOURCE_COMMIT,
        "original_run_id": publication.REPLACEMENT_RUN_ID,
        "reused_original_run_id": True,
        "original_block": {
            "path": "receipt.json",
            "receipt_sha256": blocked_sha,
            "status": "BLOCK",
            "execution_status": "BLOCK",
            "verdict": "NO_GO",
            "reason": reason,
            "fresh_oos": fresh,
            "preserved_byte_identical": True,
        },
        "protocol": {"id": protocol["protocol_id"], "sha256": source_hashes["protocol"]},
        "identities": identity,
        "features": list(public_run.FEATURES),
        "public_splits": {
            "train": {
                "frozen_start": public_run.PUBLIC_TRAIN_START,
                "frozen_end": public_run.PUBLIC_TRAIN_END,
                "actual_start": "2023-12-28",
                "actual_end": "2023-12-29",
            },
            "reused_validation": {
                "frozen_start": public_run.REUSED_VALIDATION_START,
                "frozen_end": public_run.REUSED_VALIDATION_END,
                "actual_start": "2024-01-02",
                "actual_end": "2025-06-30",
            },
        },
        "session_pairing": {
            "authority_bound": True,
            "trailing_embargo": list(identity["authority_sessions"]["trailing_embargo"]),
            "validation_pairs_sha256": artifacts["validation_pairs_sha256"],
            "normalizer_digest": artifacts["normalizer_digest"],
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
            "retraining_performed": retraining,
        },
        "members": artifacts["recovered_members"],
        "aggregation": {"metric": "FIVE_SEED_IQM", "primary_nav_krw": 60000002, "shuffled_nav_krw": 60000002},
        "pretraining_gate": {"status": "NOT_PRODUCTION"},
        "controls": {
            "integrity_ok": controls_integrity,
            "integrity_reasons": [] if controls_integrity else ["fixture_integrity_failure"],
            "mutation_invariance": {"train_only_normalizer_unchanged": True, "train_pairs_byte_identical": True},
            "scientific_gates_pass": False,
            "scientific_gate_reasons": ["fixture_control_gate_miss"],
            "shuffle_retraining": {"seeds": [0, 1, 2, 3, 4], "timesteps_per_seed": 200000, "all_members_recorded": True},
        },
        "source_sha256": source_hashes,
        "materializer_sha256": source_hashes["materializer_manifest"],
        "custody_bindings": {
            "blocked_receipt": {"path": "receipt.json", "sha256": blocked_sha},
            "protocol": {"path": str(public_run.PROTOCOL_PATH), "sha256": source_hashes["protocol"]},
            "amendment": {"path": str(public_run.AMENDMENT_PATH), "sha256": source_hashes["amendment"]},
            "public_rows": {"path": str(parent / "public_rows.json"), "sha256": source_hashes["public_rows"]},
            "dataset_manifest": {"path": str(parent / "dataset_manifest.json"), "sha256": source_hashes["dataset_manifest"]},
            "materializer_manifest": {"path": str(parent / "dataset_manifest.json"), "sha256": source_hashes["materializer_manifest"]},
            "materializer_complete_receipt": {"path": str(parent / "materializer_complete_receipt.json"), "sha256": source_hashes["materializer_complete_receipt"]},
            "authority": {"path": str(_authority_file(parent)), "sha256": source_hashes["authority"]},
            "runner": {"path": "stom_rl/daily_type1_public_run.py", "sha256": source_hashes["runner"]},
            "market": {"path": "stom_rl/daily_type1_market.py", "sha256": source_hashes["market"]},
        },
        "fresh_oos": fresh,
        "false_research_locks": dict(publication.FALSE_RESEARCH_LOCKS),
        "execution_status": "COMPLETE",
        "verdict": "NO_GO",
        "decision": "NO_GO",
        "claims": {
            "profitability": "NOT_CLAIMED",
            "live": "NOT_CLAIMED",
            "fresh_oos": "NOT_RUN_NO_READ",
            "outcome": "NO_GO_ONLY",
        },
    }
    manifest_raw = canonical_json_bytes(manifest)
    (root / "recovery_manifest.json").write_bytes(manifest_raw)
    manifest_sha = hashlib.sha256(manifest_raw).hexdigest()
    receipt = {
        "schema_version": public_run.RECOVERY_RECEIPT_SCHEMA,
        "role": public_run.RECOVERY_RECEIPT_ROLE,
        "status": receipt_status,
        "execution_status": receipt_status,
        "verdict": "NO_GO",
        "decision": receipt_decision,
        "run_id": publication.REPLACEMENT_RUN_ID,
        "recovery_manifest_sha256": manifest_sha,
        "blocked_receipt_sha256": blocked_sha,
        "blocked_receipt_path": "receipt.json",
        "blocked_reason": reason,
        "original_block_reason": reason,
        "original_block_preserved": True,
        "retraining_performed": retraining,
        "overwrite_performed": False,
        "move_performed": False,
        "delete_performed": False,
        "fresh_oos": fresh,
        "member_artifact_sha256": artifacts["artifact_sha256"],
        "source_sha256": source_hashes,
        "materializer_sha256": source_hashes["materializer_manifest"],
        "outcome": "NO_GO_ONLY",
    }
    receipt_raw = canonical_json_bytes(receipt)
    (root / "recovery_receipt.json").write_bytes(receipt_raw)
    return {
        "blocked_receipt_sha256": blocked_sha,
        "recovery_manifest_sha256": manifest_sha,
        "recovery_receipt_sha256": hashlib.sha256(receipt_raw).hexdigest(),
        "artifact_sha256": artifacts["artifact_sha256"],
        "source_hashes": source_hashes,
        "identity": identity,
        "manifest": manifest,
        "receipt": receipt,
    }


def _write_bare_block_run(root: Path) -> None:
    _write_artifacts(root)
    (root / "receipt.json").write_bytes(canonical_json_bytes(_block_receipt()))


def _write_completed_run(root: Path, *, receipt_status: str = "COMPLETE") -> dict[str, object]:
    artifacts = _write_artifacts(root)
    manifest = {
        "schema_version": "kronos_type1_g002_public_run.v1",
        "identities": {
            "authority_id": publication.REPLACEMENT_AUTHORITY_ID,
            "dataset_id": publication.DATASET_ID,
            "train_id": publication.REPLACEMENT_TRAIN_ID,
            "train_run_id": publication.REPLACEMENT_RUN_ID,
            "custody_uid": publication.REPLACEMENT_CUSTODY_UID,
        },
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
        "members": artifacts["completed_members"],
        "controls": {"integrity_ok": True, "integrity_reasons": []},
        "pretraining_gate": {
            "accounting": {"cost_bps": 23, "slot_notional_krw": 5000000, "max_slots": 10},
            "block_semantics": "BLOCK",
            "validation_noninterference": {
                "train_only_normalizer_digest": "1" * 64,
                "train_pairs_sha256": "2" * 64,
                "mutated_surfaces": ["features", "gross_return", "entry_available"],
                "unchanged": True,
            },
        },
        "fresh_oos": {"state": "NOT_RUN", "metrics": None},
        "false_research_locks": dict(publication.FALSE_RESEARCH_LOCKS),
        "execution_status": "COMPLETE",
        "verdict": "NO_GO",
    }
    (root / "run_manifest.json").write_bytes(canonical_json_bytes(manifest))
    (root / "receipt.json").write_bytes(canonical_json_bytes({
        "manifest_sha256": sha256_canonical(manifest),
        "execution_status": receipt_status,
        "verdict": "NO_GO",
        "fresh_oos": {"state": "NOT_RUN", "metrics": None},
    }))
    return manifest


def _publish(source: Path, destination: Path) -> dict[str, object]:
    return publication._publish_verified_run(
        source,
        destination,
        source_logical_path=publication.SOURCE_LOGICAL_PATH,
        destination_logical_path=publication.DESTINATION_LOGICAL_PATH,
    )


def test_successful_recovered_publication_moves_once_and_writes_v2_receipt(tmp_path: Path) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    evidence = _write_recovered_run(source, parent)

    assert {path.name for path in source.iterdir()} == {
        "receipt.json",
        "recovery_manifest.json",
        "recovery_receipt.json",
        "primary",
        "shuffled_reward",
    }

    result = _publish(source, destination)

    assert result["publication_status"] == "COMPLETE"
    assert result["mode"] == "PUBLISHED"
    assert result["publication_mode"] == "recovered"
    assert result["run_evidence_mode"] == "RECOVERED_AFTER_BLOCK"
    assert not source.exists()
    assert destination.is_dir()
    assert {path.name for path in destination.iterdir()} == {
        "receipt.json",
        "recovery_manifest.json",
        "recovery_receipt.json",
        "primary",
        "shuffled_reward",
        publication.PUBLICATION_RECEIPT_NAME,
    }
    receipt_path = destination / publication.PUBLICATION_RECEIPT_NAME
    receipt_raw = receipt_path.read_bytes()
    receipt = json.loads(receipt_raw.decode("utf-8"))
    assert canonical_json_bytes(receipt) == receipt_raw
    assert set(receipt) == {
        "schema_version",
        "role",
        "status",
        "verdict",
        "mode",
        "disclosure",
        "run_evidence_mode",
        "identity",
        "source_logical_path",
        "destination_logical_path",
        "move_contract",
        "recovery_receipt_sha256",
        "original_block_reason",
        "preserved_block_receipt",
        "retraining_performed",
        "fresh_oos",
        "false_research_locks",
        "materializer_sha256",
        "materializer_public_rows_sha256",
        "materializer_source_sha256",
        "materializer_source_hashes",
        "source_hashes",
        "publisher_source_sha256",
    }
    assert receipt["schema_version"] == publication.PUBLICATION_SCHEMA_VERSION
    assert receipt["role"] == publication.PUBLICATION_ROLE
    assert receipt["status"] == "COMPLETE"
    assert receipt["mode"] == "recovered"
    assert receipt["run_evidence_mode"] == "RECOVERED_AFTER_BLOCK"
    assert receipt["source_logical_path"] == publication.SOURCE_LOGICAL_PATH
    assert receipt["destination_logical_path"] == publication.DESTINATION_LOGICAL_PATH
    assert receipt["move_contract"] == {
        "operation": "same_volume_atomic_directory_rename",
        "copy_performed": False,
        "overwrite_performed": False,
        "delete_performed": False,
    }
    assert set(receipt["disclosure"]) == {"recovery_manifest_sha256", "blocked_receipt_sha256", "members"}
    assert receipt["disclosure"]["blocked_receipt_sha256"] == evidence["blocked_receipt_sha256"]
    assert receipt["disclosure"]["recovery_manifest_sha256"] == evidence["recovery_manifest_sha256"]
    assert receipt["disclosure"]["members"] == evidence["artifact_sha256"]
    assert len(receipt["disclosure"]["members"]) == 20
    assert receipt["recovery_receipt_sha256"] == evidence["recovery_receipt_sha256"]
    assert receipt["identity"] == evidence["identity"]
    assert receipt["original_block_reason"] == publication._ORIGINAL_BLOCK_REASON
    assert receipt["preserved_block_receipt"] is True
    assert receipt["retraining_performed"] is False
    assert receipt["fresh_oos"] == FRESH_NO_READ
    assert "append_only_recovery_disclosure" not in receipt
    assert "blocked_receipt_sha256" not in receipt
    assert "recovery_manifest_sha256" not in receipt
    assert "member_artifact_sha256" not in receipt
    assert "members" not in receipt
    assert "artifact_inventory_digest" not in receipt
    assert "run_manifest_sha256" not in receipt
    assert receipt["materializer_sha256"] == {
        "public_rows_sha256": hashlib.sha256((parent / "public_rows.json").read_bytes()).hexdigest(),
        "dataset_manifest_sha256": hashlib.sha256((parent / "dataset_manifest.json").read_bytes()).hexdigest(),
        "materializer_complete_receipt_sha256": hashlib.sha256((parent / "materializer_complete_receipt.json").read_bytes()).hexdigest(),
    }
    assert receipt["materializer_public_rows_sha256"] == receipt["materializer_sha256"]["public_rows_sha256"]
    assert receipt["source_hashes"]["publisher_source"] == hashlib.sha256(Path(publication.__file__).read_bytes()).hexdigest()
    for key, value in evidence["source_hashes"].items():
        assert receipt["source_hashes"][key] == value


def test_current_runner_recovery_contract_fixture_publishes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent = _materialization_parent(tmp_path)
    out_root = tmp_path / "artifacts" / "type1-public-runs"
    source = out_root / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    _write_artifacts(source)
    (source / "receipt.json").write_bytes(canonical_json_bytes(_block_receipt()))
    monkeypatch.setattr(public_run, "AUTHORIZED_RUN_ROOT", out_root)

    runner_result = public_run.recover_public_experiment(
        _runner_rows(),
        out_root=out_root,
        run_id=publication.REPLACEMENT_RUN_ID,
        operations=_RunnerFixtureOperations(),
        identity=_runner_identity(parent),
        rows_path=parent / "public_rows.json",
        dataset_manifest_path=parent / "dataset_manifest.json",
        authority_path=_authority_file(parent),
        materializer_manifest_path=parent / "dataset_manifest.json",
        materializer_complete_receipt_path=parent / "materializer_complete_receipt.json",
    )

    assert set(runner_result["manifest"]) == set(publication._RECOVERY_MANIFEST_KEYS)
    assert set(runner_result["receipt"]) == set(publication._RECOVERY_RECEIPT_KEYS)

    _publish(source, destination)

    receipt = json.loads((destination / publication.PUBLICATION_RECEIPT_NAME).read_text(encoding="utf-8"))
    assert set(receipt["disclosure"]) == {"recovery_manifest_sha256", "blocked_receipt_sha256", "members"}
    assert receipt["disclosure"]["recovery_manifest_sha256"] == hashlib.sha256((destination / "recovery_manifest.json").read_bytes()).hexdigest()
    assert receipt["disclosure"]["blocked_receipt_sha256"] == hashlib.sha256((destination / "receipt.json").read_bytes()).hexdigest()
    assert receipt["disclosure"]["members"] == runner_result["receipt"]["member_artifact_sha256"]
    assert len(receipt["disclosure"]["members"]) == 20


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
def test_recovered_publication_rejects_authority_session_schema_tampering(tmp_path: Path, tamper: str) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    _write_recovered_run(source, parent)
    manifest_path = source / "recovery_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sessions = manifest["identities"]["authority_sessions"]
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
    manifest_path.write_bytes(canonical_json_bytes(manifest))

    with pytest.raises(publication.Type1PublicationError):
        _publish(source, destination)

    assert source.is_dir()
    assert not destination.exists()

def test_recovered_publication_rejects_authority_session_artifact_mismatch(tmp_path: Path) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    _write_recovered_run(source, parent)

    manifest_path = source / "recovery_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["identities"]["authority_sessions"] = {
        "count": 4,
        "first": "2023-12-27",
        "last": "2025-06-30",
        "ordered": ["2023-12-27", "2023-12-28", "2024-01-02", "2025-06-30"],
        "pairs": [[0, 1], [2, 3]],
        "parity": 0,
        "trailing_embargo": [],
    }
    manifest_raw = canonical_json_bytes(manifest)
    manifest_path.write_bytes(manifest_raw)

    receipt_path = source / "recovery_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["recovery_manifest_sha256"] = hashlib.sha256(manifest_raw).hexdigest()
    receipt_path.write_bytes(canonical_json_bytes(receipt))

    with pytest.raises(publication.Type1PublicationError, match="authority_sessions"):
        _publish(source, destination)

    assert source.is_dir()
    assert not destination.exists()


def test_bare_block_without_recovery_manifest_and_receipt_is_rejected(tmp_path: Path) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    _write_bare_block_run(source)

    with pytest.raises(publication.Type1PublicationError, match="recovered run root"):
        _publish(source, destination)

    assert source.is_dir()
    assert not (source / publication.PUBLICATION_RECEIPT_NAME).exists()
    assert not destination.exists()


@pytest.mark.parametrize("tamper", ["run_manifest", "completed_receipt"])
def test_run_manifest_or_completed_receipt_is_rejected_in_recovered_production_identity(tmp_path: Path, tamper: str) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    _write_recovered_run(source, parent)
    if tamper == "run_manifest":
        (source / "run_manifest.json").write_bytes(canonical_json_bytes({"unexpected": True}))
    else:
        (source / "receipt.json").write_bytes(canonical_json_bytes({
            "manifest_sha256": "0" * 64,
            "execution_status": "COMPLETE",
            "verdict": "NO_GO",
            "fresh_oos": {"state": "NOT_RUN", "metrics": None},
        }))

    with pytest.raises(publication.Type1PublicationError, match="recovered run root|original BLOCK"):
        _publish(source, destination)

    assert source.is_dir()
    assert not destination.exists()


@pytest.mark.parametrize("tamper", ["wrong_reason", "wrong_hash", "retraining", "fresh_oos", "member", "controls", "missing_manifest_field", "extra_manifest_field", "missing_receipt_field", "extra_receipt_field"])
def test_recovered_publication_tamper_cases_are_rejected_before_move(tmp_path: Path, tamper: str) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    kwargs: dict[str, Any] = {}
    if tamper == "wrong_reason":
        kwargs["reason"] = "different reason"
    if tamper == "retraining":
        kwargs["retraining"] = True
    if tamper == "fresh_oos":
        kwargs["fresh_oos"] = {"state": "NOT_RUN", "metrics": None, "read_performed": True}
    if tamper == "controls":
        kwargs["controls_integrity"] = False
    _write_recovered_run(source, parent, **kwargs)
    if tamper in {"missing_manifest_field", "extra_manifest_field"}:
        manifest_path = source / "recovery_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if tamper == "missing_manifest_field":
            manifest.pop("source_commit")
        else:
            manifest["compatibility_alias"] = True
        manifest_path.write_bytes(canonical_json_bytes(manifest))
    if tamper in {"wrong_hash", "missing_receipt_field", "extra_receipt_field"}:
        receipt_path = source / "recovery_receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if tamper == "wrong_hash":
            receipt["blocked_receipt_sha256"] = "0" * 64
        elif tamper == "missing_receipt_field":
            receipt.pop("recovery_manifest_sha256")
        else:
            receipt["manifest"] = {"path": "recovery_manifest.json", "sha256": receipt["recovery_manifest_sha256"]}
        receipt_path.write_bytes(canonical_json_bytes(receipt))
    if tamper == "member":
        (source / "primary" / "seed_2" / "final_model.zip").write_bytes(b"tampered-model")

    with pytest.raises(publication.Type1PublicationError):
        _publish(source, destination)

    assert source.is_dir()
    assert not destination.exists()


def test_staged_publication_receipt_crash_retries_without_overwrite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    _write_recovered_run(source, parent)
    original_write = publication._write_new_canonical

    def crash_after_receipt(path: Path, value: dict[str, object]) -> None:
        original_write(path, value)
        raise RuntimeError("simulated crash after staging receipt")

    monkeypatch.setattr(publication, "_write_new_canonical", crash_after_receipt)

    with pytest.raises(RuntimeError, match="simulated crash"):
        _publish(source, destination)

    assert source.is_dir()
    assert not destination.exists()
    staged_receipt = (source / publication.PUBLICATION_RECEIPT_NAME).read_bytes()

    monkeypatch.setattr(publication, "_write_new_canonical", original_write)
    result = _publish(source, destination)

    assert result["mode"] == "PUBLISHED"
    assert not source.exists()
    assert destination.is_dir()
    assert (destination / publication.PUBLICATION_RECEIPT_NAME).read_bytes() == staged_receipt


def test_rename_before_postcheck_crash_recovers_moved_recovered_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    _write_recovered_run(source, parent)
    original_rename = publication.os.rename

    def crash_after_rename(src: Path, dst: Path) -> None:
        original_rename(src, dst)
        raise RuntimeError("simulated crash immediately after rename")

    monkeypatch.setattr(publication.os, "rename", crash_after_rename)

    with pytest.raises(RuntimeError, match="simulated crash"):
        _publish(source, destination)

    assert not source.exists()
    assert destination.is_dir()
    receipt_before = (destination / publication.PUBLICATION_RECEIPT_NAME).read_bytes()

    monkeypatch.setattr(publication.os, "rename", original_rename)
    recovered = _publish(source, destination)

    assert recovered["mode"] == "RECOVERED"
    assert recovered["run_evidence_mode"] == "RECOVERED_AFTER_BLOCK"
    assert recovered["publication_receipt_sha256"] == hashlib.sha256(receipt_before).hexdigest()
    assert (destination / publication.PUBLICATION_RECEIPT_NAME).read_bytes() == receipt_before


def test_retry_with_mismatched_recovered_publication_receipt_blocks(tmp_path: Path) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    _write_recovered_run(source, parent)
    _publish(source, destination)
    receipt_path = destination / publication.PUBLICATION_RECEIPT_NAME
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["recovery_receipt_sha256"] = "0" * 64
    receipt_path.write_bytes(canonical_json_bytes(receipt))

    with pytest.raises(publication.Type1PublicationError, match="publication receipt"):
        _publish(source, destination)

    assert not source.exists()
    assert destination.is_dir()


def test_source_and_valid_destination_both_present_blocks_without_delete_or_overwrite(tmp_path: Path) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    _write_recovered_run(source, parent)
    _publish(source, destination)
    receipt_before = (destination / publication.PUBLICATION_RECEIPT_NAME).read_bytes()
    _write_recovered_run(source, parent)

    with pytest.raises(publication.Type1PublicationError, match="both exist"):
        _publish(source, destination)

    assert source.is_dir()
    assert destination.is_dir()
    assert (destination / publication.PUBLICATION_RECEIPT_NAME).read_bytes() == receipt_before


def test_existing_destination_blocks_without_overwrite(tmp_path: Path) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    _write_recovered_run(source, parent)
    destination.mkdir()
    marker = destination / "marker.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(publication.Type1PublicationError, match="both exist|already exists"):
        _publish(source, destination)

    assert source.is_dir()
    assert marker.read_text(encoding="utf-8") == "keep"


def test_nonproduction_completed_fixture_remains_publishable_with_v1_receipt(tmp_path: Path) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / "fixture-completed-run"
    destination = parent / "fixture-completed-run"
    _write_completed_run(source)

    result = publication._publish_verified_run(
        source,
        destination,
        source_logical_path="artifacts/type1-public-runs/fixture-completed-run",
        destination_logical_path="webui/rl_runs/v6_daily_h1/type1-close-20260803-005/fixture-completed-run",
    )

    assert result["publication_status"] == "COMPLETE"
    assert result["run_evidence_mode"] == "COMPLETED_RUN"
    assert not source.exists()
    receipt = json.loads((destination / publication.PUBLICATION_RECEIPT_NAME).read_text(encoding="utf-8"))
    assert receipt["schema_version"] == publication._COMPLETED_PUBLICATION_SCHEMA_VERSION
    assert receipt["run_manifest_sha256"] == hashlib.sha256((destination / "run_manifest.json").read_bytes()).hexdigest()
    assert receipt["fresh_oos"] == {
        "run": {"state": "NOT_RUN", "metrics": None},
        "materializer": {"state": "NOT_RUN", "read_performed": False},
        "read_performed": False,
    }
