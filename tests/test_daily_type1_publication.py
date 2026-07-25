from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path

import pytest

from stom_rl.daily_type1_contract import canonical_json_bytes, sha256_canonical
from stom_rl.daily_type1_public_data import write_public_materialization
import stom_rl.daily_type1_publication as publication


DAILY_COLUMNS = 'date, open, high, low, close, volume, "상장주식수", "외국인주문한도수량", "외국인현보유수량", "외국인현보유비율", "기관순매수", "기관누적순매수"'
FIVE_COLUMNS = "date, open, high, low, close, volume"


def _authority() -> dict[str, object]:
    return {
        "stable_symbols": ["000250"],
        "sessions": {
            "ordered": ["2023-12-28", "2023-12-29", "2024-01-02", "2025-06-30"],
            "pairs": [[0, 1], [2, 3]],
            "trailing_embargo": [],
        },
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
        "digest": hashlib.sha256(f"{kind}-{seed}-normalizer".encode()).hexdigest(),
        "scales": [{"center": "0", "scale": "1"} for _ in range(7)],
    })


def _write_run(root: Path, *, receipt_status: str = "COMPLETE") -> dict[str, object]:
    root.mkdir(parents=True)
    members: dict[str, dict[str, object]] = {"primary": {}, "shuffled_reward": {}}
    for kind in ("primary", "shuffled_reward"):
        for seed in range(5):
            member_dir = root / kind / f"seed_{seed}"
            member_dir.mkdir(parents=True)
            model_raw = f"{kind}-{seed}-final-model".encode()
            normalizer_raw = _normalizer(seed, kind)
            (member_dir / "final_model.zip").write_bytes(model_raw)
            (member_dir / "normalizer.json").write_bytes(normalizer_raw)
            artifacts = {
                "model_sha256": hashlib.sha256(model_raw).hexdigest(),
                "normalizer_sha256": hashlib.sha256(normalizer_raw).hexdigest(),
            }
            normalizer = json.loads(normalizer_raw.decode("utf-8"))
            evidence = {
                **artifacts,
                "normalizer_digest": normalizer["digest"],
                "validation_pairs_sha256": hashlib.sha256(f"validation-{kind}-{seed}".encode()).hexdigest(),
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
                "reload_receipt": {**artifacts, "deterministic": True, "evidence": evidence},
                "validation": {"nav_krw": 60000000 + seed},
            }
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
        "members": members,
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


def _rewrite_manifest(root: Path, manifest: dict[str, object]) -> None:
    (root / "run_manifest.json").write_bytes(canonical_json_bytes(manifest))
    (root / "receipt.json").write_bytes(canonical_json_bytes({
        "manifest_sha256": sha256_canonical(manifest),
        "execution_status": "COMPLETE",
        "verdict": "NO_GO",
        "fresh_oos": {"state": "NOT_RUN", "metrics": None},
    }))


def _publish(source: Path, destination: Path) -> dict[str, object]:
    return publication._publish_verified_run(
        source,
        destination,
        source_logical_path=publication.SOURCE_LOGICAL_PATH,
        destination_logical_path=publication.DESTINATION_LOGICAL_PATH,
    )


def test_success_moves_once_and_writes_canonical_publication_receipt(tmp_path: Path) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    _write_run(source)

    result = _publish(source, destination)

    assert result["publication_status"] == "COMPLETE"
    assert result["mode"] == "PUBLISHED"
    assert not source.exists()
    assert destination.is_dir()
    receipt_path = destination / publication.PUBLICATION_RECEIPT_NAME
    receipt_raw = receipt_path.read_bytes()
    receipt = json.loads(receipt_raw.decode("utf-8"))
    assert canonical_json_bytes(receipt) == receipt_raw
    assert receipt["source_logical_path"] == publication.SOURCE_LOGICAL_PATH
    assert receipt["destination_logical_path"] == publication.DESTINATION_LOGICAL_PATH
    assert receipt["move_contract"] == {
        "operation": "same_volume_atomic_directory_rename",
        "copy_performed": False,
        "overwrite_performed": False,
        "delete_performed": False,
    }
    assert receipt["fresh_oos"] == {
        "run": {"state": "NOT_RUN", "metrics": None},
        "materializer": {"state": "NOT_RUN", "read_performed": False},
        "read_performed": False,
    }
    assert receipt["materializer_sha256"]["dataset_manifest_sha256"] == hashlib.sha256((parent / "dataset_manifest.json").read_bytes()).hexdigest()
    assert receipt["publisher_source_sha256"] == hashlib.sha256(Path(publication.__file__).read_bytes()).hexdigest()


def test_wrong_or_incomplete_run_is_rejected_before_move(tmp_path: Path) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    _write_run(source, receipt_status="RUNNING")

    with pytest.raises(publication.Type1PublicationError, match="receipt"):
        _publish(source, destination)

    assert source.is_dir()
    assert not destination.exists()


def test_block_manifest_is_rejected_even_with_matching_receipt_hash(tmp_path: Path) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    manifest = _write_run(source)
    manifest["execution_status"] = "BLOCK"
    _rewrite_manifest(source, manifest)

    with pytest.raises(publication.Type1PublicationError, match="manifest"):
        _publish(source, destination)

    assert source.is_dir()
    assert not destination.exists()


def test_wrong_destination_materialization_blocks_before_move(tmp_path: Path) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    _write_run(source)
    (parent / "materializer_complete_receipt.json").write_bytes(canonical_json_bytes({}))

    with pytest.raises(publication.Type1PublicationError, match="materialization"):
        _publish(source, destination)

    assert source.is_dir()
    assert not destination.exists()


def test_existing_destination_blocks_without_overwrite(tmp_path: Path) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    _write_run(source)
    destination.mkdir()
    marker = destination / "marker.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(publication.Type1PublicationError, match="both exist|already exists"):
        _publish(source, destination)

    assert source.is_dir()
    assert marker.read_text(encoding="utf-8") == "keep"


def test_reparse_member_artifact_is_rejected_where_supported(tmp_path: Path) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    _write_run(source)
    target = source / "primary" / "seed_0" / "final_model.zip"
    outside = tmp_path / "outside-final-model.zip"
    outside.write_bytes(target.read_bytes())
    target.unlink()
    try:
        os.symlink(outside, target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation is not supported: {exc}")

    with pytest.raises(publication.Type1PublicationError, match="symlink|reparse"):
        _publish(source, destination)

    assert source.is_dir()
    assert not destination.exists()


def test_exact_retry_recovery_accepts_source_absent_destination_with_valid_receipt(tmp_path: Path) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    _write_run(source)
    first = _publish(source, destination)

    second = _publish(source, destination)

    assert second["mode"] == "RECOVERED"
    assert second["publication_receipt_sha256"] == first["publication_receipt_sha256"]
    assert not source.exists()
    assert destination.is_dir()


def test_retry_with_mismatched_publication_receipt_blocks(tmp_path: Path) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    _write_run(source)
    _publish(source, destination)
    receipt_path = destination / publication.PUBLICATION_RECEIPT_NAME
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["destination_logical_path"] = "webui/rl_runs/v6_daily_h1/type1-close-20260803-005/tampered"
    receipt_path.write_bytes(canonical_json_bytes(receipt))

    with pytest.raises(publication.Type1PublicationError, match="publication receipt"):
        _publish(source, destination)

    assert not source.exists()
    assert destination.is_dir()


@pytest.mark.parametrize("tamper", ["missing_seed", "hash_tamper"])
def test_ten_model_completeness_and_member_hash_tamper_block(tmp_path: Path, tamper: str) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    _write_run(source)
    if tamper == "missing_seed":
        seed_dir = source / "shuffled_reward" / "seed_4"
        for child in seed_dir.iterdir():
            child.unlink()
        seed_dir.rmdir()
    else:
        (source / "primary" / "seed_2" / "final_model.zip").write_bytes(b"tampered-model")

    with pytest.raises(publication.Type1PublicationError):
        _publish(source, destination)

    assert source.is_dir()
    assert not destination.exists()


def test_source_and_valid_destination_both_present_blocks_without_delete_or_overwrite(tmp_path: Path) -> None:
    parent = _materialization_parent(tmp_path)
    source = tmp_path / "artifacts" / "type1-public-runs" / publication.REPLACEMENT_RUN_ID
    destination = parent / publication.REPLACEMENT_RUN_ID
    _write_run(source)
    _publish(source, destination)
    receipt_before = (destination / publication.PUBLICATION_RECEIPT_NAME).read_bytes()
    _write_run(source)

    with pytest.raises(publication.Type1PublicationError, match="both exist"):
        _publish(source, destination)

    assert source.is_dir()
    assert destination.is_dir()
    assert (destination / publication.PUBLICATION_RECEIPT_NAME).read_bytes() == receipt_before
