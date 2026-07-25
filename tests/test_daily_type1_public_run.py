from __future__ import annotations

import hashlib
import json
import shutil
import stat
from pathlib import Path
from decimal import Decimal

import pytest
import numpy as np
from stom_rl.daily_type1_contract import canonical_json_bytes

from stom_rl.daily_type1_public_run import (
    AMENDMENT_PATH,
    FINAL_MODEL_ONLY,
    REUSED_VALIDATION_END,
    REUSED_VALIDATION_START,
    PUBLIC_TRAIN_END,
    PUBLIC_TRAIN_START,
    RunConfig,
    TIMESTEPS_PER_SEED,
    build_parser,
    ORIGINAL_BLOCKED_REASON,
    ORIGINAL_BLOCK_RECEIPT,
    RECOVERY_MANIFEST_NAME,
    RECOVERY_RECEIPT_NAME,
    materialize_public_rows,
    reject_nonpublic_path,
    run_public_experiment,
    recover_public_experiment,
    split_public_rows,
    _ProductionOperations,
    REPLACEMENT_AUTHORITY_ID,
    REPLACEMENT_DATASET_ID,
    REPLACEMENT_RUN_ID,
    REPLACEMENT_TRAIN_ID,
    REPLACEMENT_CUSTODY_UID,
    _verified_inputs,
    _mutated_validation_rows,
)


class FakeOperations:
    def __init__(self) -> None:
        self.build_calls: list[tuple[str, int | None, tuple[dict[str, object], ...]]] = []
        self.train_calls: list[tuple[int, int]] = []

    def build_pairs(self, rows, *, split, shuffled_seed=None):
        copied = tuple(dict(row) for row in rows)
        self.build_calls.append((split, shuffled_seed, copied))
        return ({"split": split, "shuffled_seed": shuffled_seed},)

    def train(self, pairs, *, seed, timesteps):
        self.train_calls.append((seed, timesteps))
        return type("Model", (), {"num_timesteps": timesteps, "device": "cpu"})(), object()

    def save_final(self, model, normalizer, path):
        return {"model_sha256": f"model-{path.name}", "normalizer_sha256": f"normalizer-{path.name}"}

    def evaluate(self, model, pairs, *, seed):
        return {"nav_krw": 60_000_000 + seed, "deterministic": True}

    def controls(self, train_rows, validation_rows, primary, shuffled):
        return {"integrity_ok": True, "train_count": len(train_rows), "validation_count": len(validation_rows)}


def _rows():
    return [
        {"decision_date": PUBLIC_TRAIN_START, "symbol": "000001"},
        {"decision_date": PUBLIC_TRAIN_END, "symbol": "000002"},
        {"decision_date": REUSED_VALIDATION_START, "symbol": "000001"},
        {"decision_date": REUSED_VALIDATION_END, "symbol": "000002"},
    ]


class RecoveryFakeOperations:
    normalizer_digest_value = "normalizer-digest"

    def __init__(self, *, reload_override: dict[str, object] | None = None) -> None:
        self.reload_override = reload_override or {}
        self.build_calls: list[tuple[str, int | None]] = []
        self.evaluate_saved_calls: list[Path] = []
        self.train_calls: list[tuple[int, int]] = []
        self.save_calls: list[Path] = []
        self.pretraining_calls = 0
        self.control_calls = 0
        self.numpy_mask_control_seen = False

    def build_pairs(self, rows, *, split, shuffled_seed=None):
        self.build_calls.append((split, shuffled_seed))
        return ({
            "candidate_values": np.asarray([[1.0], [2.0]], dtype=np.float32),
            "candidate_missing": np.asarray([[0], [0]], dtype=np.int8),
            "availability_mask": np.asarray([1, 0], dtype=np.int8),
            "post_decision_fill_available": np.asarray([1, 0], dtype=np.int8),
            "symbols": ("000001", "000002"),
            "gross_returns": (Decimal("0.0100"), None),
            "decision_date": "2024-01-02",
            "settlement_date": "2024-01-03",
        },)

    def normalizer_digest(self) -> str:
        return self.normalizer_digest_value

    def train(self, pairs, *, seed, timesteps):
        self.train_calls.append((seed, timesteps))
        raise AssertionError("recovery must not train")

    def save_final(self, model, normalizer, path):
        self.save_calls.append(path)
        raise AssertionError("recovery must not save final artifacts")

    def evaluate_saved(self, path, validation_rows, *, seed, expected_pair_bytes, expected_normalizer_digest, expected_normalizer_sha256):
        self.evaluate_saved_calls.append(path)
        normalizer = json.loads((path / "normalizer.json").read_text(encoding="utf-8"))
        evidence = {
            "model_sha256": hashlib.sha256((path / "final_model.zip").read_bytes()).hexdigest(),
            "normalizer_sha256": hashlib.sha256((path / "normalizer.json").read_bytes()).hexdigest(),
            "normalizer_digest": normalizer["digest"],
            "validation_pairs_sha256": hashlib.sha256(expected_pair_bytes).hexdigest(),
            "model_device": "cpu",
            "num_timesteps": TIMESTEPS_PER_SEED,
        }
        evidence.update(self.reload_override)
        return {
            "nav_krw": 60_000_000 + seed,
            "deterministic": True,
            "action_masks_dtype": "int8",
            "reload_evidence": evidence,
        }

    def pretraining_gate(self, train_rows, validation_rows, train_pairs, validation_pairs):
        self.pretraining_calls += 1
        return {"status": "PASS", "train_rows": len(train_rows), "validation_rows": len(validation_rows)}

    def controls(self, train_rows, validation_rows, primary, shuffled):
        self.control_calls += 1
        self.numpy_mask_control_seen = all(
            member["validation"]["action_masks_dtype"] == "int8"
            for members in (primary, shuffled)
            for member in members.values()
        )
        return {
            "integrity_ok": self.numpy_mask_control_seen,
            "integrity_reasons": [] if self.numpy_mask_control_seen else ["numpy_mask_control_missing"],
            "mutation_invariance": {"numpy_action_masks": self.numpy_mask_control_seen},
            "scientific_gates_pass": False,
            "scientific_gate_reasons": ["local_control_gate_miss"],
            "shuffle_retraining": {
                "seeds": list(range(5)),
                "timesteps_per_seed": TIMESTEPS_PER_SEED,
                "all_members_recorded": True,
            },
        }


def _write_recovery_run(out_root: Path) -> Path:
    root = out_root / REPLACEMENT_RUN_ID
    root.mkdir()
    (root / "receipt.json").write_bytes(canonical_json_bytes(ORIGINAL_BLOCK_RECEIPT))
    for kind in ("primary", "shuffled_reward"):
        for seed in range(5):
            member = root / kind / f"seed_{seed}"
            member.mkdir(parents=True)
            (member / "final_model.zip").write_bytes(f"{kind}-{seed}-model".encode("utf-8"))
            (member / "normalizer.json").write_bytes(canonical_json_bytes({
                "kind": "market_type7_train_only",
                "digest": RecoveryFakeOperations.normalizer_digest_value,
            }))
    return root


def _make_symlink_or_skip(link: Path, target: Path, *, is_dir: bool) -> None:
    try:
        link.symlink_to(target, target_is_directory=is_dir)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    assert link.is_symlink()


def _replace_with_symlink_or_skip(path: Path, target: Path, *, is_dir: bool) -> Path:
    if path.exists() or path.is_symlink():
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    _make_symlink_or_skip(path, target, is_dir=is_dir)
    return path


def _mark_path_as_reparse(monkeypatch: pytest.MonkeyPatch, target: Path) -> Path:
    target = target.absolute()
    original_lstat = Path.lstat
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

    class ReparseStat:
        def __init__(self, wrapped) -> None:
            self.st_mode = wrapped.st_mode
            self.st_file_attributes = reparse_flag

    def lstat_with_reparse(self):
        wrapped = original_lstat(self)
        if Path(self).absolute() == target:
            return ReparseStat(wrapped)
        return wrapped

    monkeypatch.setattr(Path, "lstat", lstat_with_reparse)
    return target


def _install_symlink_indirection(tmp_path: Path, case: str) -> tuple[Path, Path]:
    if case == "root":
        target_parent = tmp_path / "target"
        target_parent.mkdir()
        target_root = _write_recovery_run(target_parent)
        root = tmp_path / REPLACEMENT_RUN_ID
        return root, _replace_with_symlink_or_skip(root, target_root, is_dir=True)

    root = _write_recovery_run(tmp_path)
    outside_parent = tmp_path / "outside"
    outside_parent.mkdir()
    outside_root = _write_recovery_run(outside_parent)
    if case == "kind":
        path = root / "primary"
        target = outside_root / "primary"
        is_dir = True
    elif case == "seed":
        path = root / "primary" / "seed_0"
        target = outside_root / "primary" / "seed_0"
        is_dir = True
    elif case == "model_artifact":
        path = root / "primary" / "seed_0" / "final_model.zip"
        target = tmp_path / "outside_final_model.zip"
        target.write_bytes(b"outside-model")
        is_dir = False
    elif case == "normalizer_artifact":
        path = root / "primary" / "seed_0" / "normalizer.json"
        target = tmp_path / "outside_normalizer.json"
        target.write_bytes(canonical_json_bytes({
            "kind": "market_type7_train_only",
            "digest": RecoveryFakeOperations.normalizer_digest_value,
        }))
        is_dir = False
    elif case == "original_receipt":
        path = root / "receipt.json"
        target = tmp_path / "outside_original_receipt.json"
        target.write_bytes(canonical_json_bytes(ORIGINAL_BLOCK_RECEIPT))
        is_dir = False
    elif case == "recovery_manifest":
        path = root / RECOVERY_MANIFEST_NAME
        target = tmp_path / "outside_recovery_manifest.json"
        target.write_text("{}", encoding="utf-8")
        is_dir = False
    elif case == "recovery_receipt":
        path = root / RECOVERY_RECEIPT_NAME
        target = tmp_path / "outside_recovery_receipt.json"
        target.write_text("{}", encoding="utf-8")
        is_dir = False
    else:
        raise AssertionError(f"unknown symlink case: {case}")
    return root, _replace_with_symlink_or_skip(path, target, is_dir=is_dir)


def _install_reparse_indirection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str) -> tuple[Path, Path]:
    root = _write_recovery_run(tmp_path)
    if case == "root":
        path = root
    elif case == "kind":
        path = root / "primary"
    elif case == "seed":
        path = root / "primary" / "seed_0"
    elif case == "model_artifact":
        path = root / "primary" / "seed_0" / "final_model.zip"
    elif case == "normalizer_artifact":
        path = root / "primary" / "seed_0" / "normalizer.json"
    elif case == "original_receipt":
        path = root / "receipt.json"
    elif case == "recovery_manifest":
        path = root / RECOVERY_MANIFEST_NAME
        path.write_text("{}", encoding="utf-8")
    elif case == "recovery_receipt":
        path = root / RECOVERY_RECEIPT_NAME
        path.write_text("{}", encoding="utf-8")
    else:
        raise AssertionError(f"unknown reparse case: {case}")
    return root, _mark_path_as_reparse(monkeypatch, path)


def _recover(root: Path, operations: RecoveryFakeOperations | None = None, rows=None):
    return recover_public_experiment(
        _rows() if rows is None else rows,
        out_root=root.parent,
        run_id=REPLACEMENT_RUN_ID,
        operations=operations or RecoveryFakeOperations(),
    )


def test_validation_mutation_preserves_fill_invariant() -> None:
    rows = [
        {"features": {}, "entry_available": True, "gross_return": "0.1"},
        {"features": {}, "entry_available": False, "gross_return": None},
    ]
    mutated = _mutated_validation_rows(rows)
    assert mutated == [
        {
            "features": {
                "ret_1d_prev": "999999.125",
                "ret_5d_prev": "999999.125",
                "ret_20d_prev": "999999.125",
                "vol_z_20": "999999.125",
                "foreign_ratio_prev": "999999.125",
                "foreign_ratio_delta_5": "999999.125",
                "inst_netbuy_norm_5": "999999.125",
            },
            "entry_available": False,
            "gross_return": None,
        },
        {
            "features": {
                "ret_1d_prev": "999999.125",
                "ret_5d_prev": "999999.125",
                "ret_20d_prev": "999999.125",
                "vol_z_20": "999999.125",
                "foreign_ratio_prev": "999999.125",
                "foreign_ratio_delta_5": "999999.125",
                "inst_netbuy_norm_5": "999999.125",
            },
            "entry_available": True,
            "gross_return": "-0.9999",
        },
    ]
    assert rows[0]["gross_return"] == "0.1"

def test_parser_exposes_no_smoke_seed_or_selection_escape_hatches():
    parser = build_parser()
    args = parser.parse_args([
        "--rows-json", "public.json",
        "--dataset-manifest", "manifest.json",
        "--authority", "authority.json",
        "--materializer-manifest", "materializer.json",
        "--materializer-complete-receipt", "materializer_complete_receipt.json",
        "--out-root", "out",
        "--run-id", "g002",
        "--recover",
    ])
    assert args.run_id == "g002"
    assert args.dataset_manifest == "manifest.json"
    assert args.authority == "authority.json"
    assert args.materializer_manifest == "materializer.json"
    assert args.recover is True
    assert "--universe-manifest" not in parser.format_help()
    assert "--seeds" not in parser.format_help()
    assert "--smoke" not in parser.format_help()
    assert "best" not in parser.format_help().lower()


def test_recovery_happy_path_is_append_only_no_go_and_preserves_original_receipt(tmp_path: Path):
    root = _write_recovery_run(tmp_path)
    original_receipt = (root / "receipt.json").read_bytes()
    operations = RecoveryFakeOperations()

    result = _recover(root, operations)

    assert operations.train_calls == []
    assert operations.save_calls == []
    assert len(operations.evaluate_saved_calls) == 10
    assert operations.pretraining_calls == 1
    assert operations.control_calls == 1
    assert operations.numpy_mask_control_seen is True
    assert (root / "receipt.json").read_bytes() == original_receipt
    assert not (root / "run_manifest.json").exists()
    assert (root / RECOVERY_MANIFEST_NAME).exists()
    assert (root / RECOVERY_RECEIPT_NAME).exists()
    manifest = result["manifest"]
    receipt = result["receipt"]
    assert manifest["schema_version"] == "kronos_type1_g002_public_run_recovery.v1"
    assert manifest["status"] == "COMPLETE"
    assert manifest["recovery_mode"] == "APPEND_ONLY_REEVALUATE_SAVED_MODELS"
    assert manifest["original_run_id"] == REPLACEMENT_RUN_ID
    assert manifest["original_block"]["reason"] == ORIGINAL_BLOCKED_REASON
    assert manifest["original_block"]["preserved_byte_identical"] is True
    assert manifest["training"]["retraining_performed"] is False
    assert manifest["training"]["timesteps_per_seed"] == 200_000
    assert manifest["training"]["device"] == "cpu"
    assert manifest["fresh_oos"] == {"state": "NOT_RUN", "metrics": None, "read_performed": False}
    assert manifest["claims"] == {
        "profitability": "NOT_CLAIMED",
        "live": "NOT_CLAIMED",
        "fresh_oos": "NOT_RUN_NO_READ",
        "outcome": "NO_GO_ONLY",
    }
    assert receipt["schema_version"] == "kronos.type1.public-run-recovery-receipt.v1"
    assert receipt["status"] == "COMPLETE"
    assert receipt["verdict"] == "NO_GO"
    assert receipt["outcome"] == "NO_GO_ONLY"
    assert receipt["retraining_performed"] is False
    assert receipt["overwrite_performed"] is False
    assert receipt["move_performed"] is False
    assert receipt["delete_performed"] is False
    assert receipt["blocked_reason"] == ORIGINAL_BLOCKED_REASON
    assert receipt["blocked_receipt_sha256"] == hashlib.sha256(original_receipt).hexdigest()
    assert receipt["recovery_manifest_sha256"] == hashlib.sha256((root / RECOVERY_MANIFEST_NAME).read_bytes()).hexdigest()
    assert set(receipt["member_artifact_sha256"]) == {
        f"{kind}/seed_{seed}/{filename}"
        for kind in ("primary", "shuffled_reward")
        for seed in range(5)
        for filename in ("final_model.zip", "normalizer.json")
    }


RECOVERY_INDIRECTION_CASES = [
    "root",
    "kind",
    "seed",
    "model_artifact",
    "normalizer_artifact",
    "original_receipt",
    "recovery_manifest",
    "recovery_receipt",
]


@pytest.mark.parametrize("case", RECOVERY_INDIRECTION_CASES)
def test_recovery_rejects_symlink_indirection_before_reload_or_write(tmp_path: Path, case: str):
    root, _ = _install_symlink_indirection(tmp_path, case)
    operations = RecoveryFakeOperations()

    with pytest.raises(ValueError, match="symlink|junction|reparse"):
        _recover(root, operations)

    assert operations.evaluate_saved_calls == []
    assert operations.pretraining_calls == 0
    assert operations.control_calls == 0


@pytest.mark.parametrize("case", RECOVERY_INDIRECTION_CASES)
def test_recovery_rejects_reparse_indirection_before_reload_or_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
):
    root, _ = _install_reparse_indirection(tmp_path, monkeypatch, case)
    operations = RecoveryFakeOperations()

    with pytest.raises(ValueError, match="symlink|junction|reparse"):
        _recover(root, operations)

    assert operations.evaluate_saved_calls == []
    assert operations.pretraining_calls == 0
    assert operations.control_calls == 0


@pytest.mark.parametrize("case", ["model_artifact", "normalizer_artifact"])
def test_recovery_rejects_artifact_symlink_before_out_of_root_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
):
    root, protected_path = _install_symlink_indirection(tmp_path, case)
    protected_path = protected_path.absolute()
    operations = RecoveryFakeOperations()
    original_read_bytes = Path.read_bytes

    def read_bytes_without_artifact_symlink(self):
        if Path(self).absolute() == protected_path:
            raise AssertionError("artifact symlink was read before rejection")
        return original_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes_without_artifact_symlink)

    with pytest.raises(ValueError, match="symlink|junction|reparse"):
        _recover(root, operations)

    assert operations.evaluate_saved_calls == []

@pytest.mark.parametrize("case", ["missing_artifact", "missing_seed", "extra_artifact", "extra_seed", "run_manifest"])
def test_recovery_rejects_missing_extra_or_run_manifest_members(tmp_path: Path, case: str):
    root = _write_recovery_run(tmp_path)
    if case == "missing_artifact":
        (root / "primary" / "seed_0" / "final_model.zip").unlink()
    elif case == "missing_seed":
        (root / "primary" / "seed_0" / "normalizer.json").unlink()
        (root / "primary" / "seed_0" / "final_model.zip").unlink()
        (root / "primary" / "seed_0").rmdir()
    elif case == "extra_artifact":
        (root / "primary" / "seed_0" / "debug.txt").write_text("debug", encoding="utf-8")
    elif case == "extra_seed":
        (root / "primary" / "seed_5").mkdir()
    else:
        (root / "run_manifest.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError):
        _recover(root)

    assert not (root / RECOVERY_MANIFEST_NAME).exists()
    assert not (root / RECOVERY_RECEIPT_NAME).exists()


def test_recovery_rejects_noncanonical_original_block_receipt(tmp_path: Path):
    root = _write_recovery_run(tmp_path)
    receipt = dict(ORIGINAL_BLOCK_RECEIPT)
    receipt["reason"] = "different"
    (root / "receipt.json").write_bytes(canonical_json_bytes(receipt))

    with pytest.raises(ValueError, match="original BLOCK receipt"):
        _recover(root)

    assert not (root / RECOVERY_MANIFEST_NAME).exists()


def test_recovery_rejects_tampered_member_normalizer_digest(tmp_path: Path):
    root = _write_recovery_run(tmp_path)
    (root / "primary" / "seed_0" / "normalizer.json").write_bytes(canonical_json_bytes({
        "kind": "market_type7_train_only",
        "digest": "tampered",
    }))

    with pytest.raises(ValueError, match="reload evidence"):
        _recover(root)

    assert not (root / RECOVERY_MANIFEST_NAME).exists()


def test_numpy_int8_control_gross_return_is_decimal_sanitized():
    pnl = _ProductionOperations._pnl([
        {"symbol": "000001", "status": "FILLED", "gross_return": np.int8(1)}
    ])

    assert pnl == Decimal("4988500.0000")


@pytest.mark.parametrize(
    "override",
    [
        {"model_device": "cuda"},
        {"num_timesteps": TIMESTEPS_PER_SEED - 1},
        {"normalizer_digest": "wrong-digest"},
        {"validation_pairs_sha256": "0" * 64},
    ],
)
def test_recovery_rejects_wrong_device_timesteps_or_digest(tmp_path: Path, override: dict[str, object]):
    root = _write_recovery_run(tmp_path)
    operations = RecoveryFakeOperations(reload_override=override)

    with pytest.raises(ValueError, match="persisted CPU artifacts"):
        _recover(root, operations)

    assert operations.train_calls == []
    assert operations.save_calls == []
    assert not (root / RECOVERY_MANIFEST_NAME).exists()


def test_recovery_rejects_fresh_oos_rows_without_read_or_artifact_write(tmp_path: Path):
    root = _write_recovery_run(tmp_path)
    rows = [
        {"decision_date": PUBLIC_TRAIN_START, "fresh_oos": {"state": "AVAILABLE"}},
        {"decision_date": REUSED_VALIDATION_START},
    ]

    with pytest.raises(ValueError, match="fresh/test"):
        _recover(root, rows=rows)

    assert not (root / RECOVERY_MANIFEST_NAME).exists()
    assert not (root / RECOVERY_RECEIPT_NAME).exists()


def test_recovery_manifest_only_retry_creates_matching_receipt(tmp_path: Path):
    root = _write_recovery_run(tmp_path)
    first = _recover(root)
    manifest_bytes = (root / RECOVERY_MANIFEST_NAME).read_bytes()
    (root / RECOVERY_RECEIPT_NAME).unlink()

    second = _recover(root, RecoveryFakeOperations())

    assert second["manifest"] == first["manifest"]
    assert (root / RECOVERY_MANIFEST_NAME).read_bytes() == manifest_bytes
    assert (root / RECOVERY_RECEIPT_NAME).exists()
    assert second["receipt"]["recovery_manifest_sha256"] == hashlib.sha256(manifest_bytes).hexdigest()


def test_recovery_exact_completed_retry_is_idempotent(tmp_path: Path):
    root = _write_recovery_run(tmp_path)
    _recover(root)
    manifest_bytes = (root / RECOVERY_MANIFEST_NAME).read_bytes()
    receipt_bytes = (root / RECOVERY_RECEIPT_NAME).read_bytes()

    _recover(root, RecoveryFakeOperations())

    assert (root / RECOVERY_MANIFEST_NAME).read_bytes() == manifest_bytes
    assert (root / RECOVERY_RECEIPT_NAME).read_bytes() == receipt_bytes


def test_recovery_existing_manifest_mismatch_fails_closed_without_receipt_overwrite(tmp_path: Path):
    root = _write_recovery_run(tmp_path)
    _recover(root)
    receipt_bytes = (root / RECOVERY_RECEIPT_NAME).read_bytes()
    (root / RECOVERY_MANIFEST_NAME).write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="non-identical recovery content"):
        _recover(root, RecoveryFakeOperations())

    assert (root / RECOVERY_RECEIPT_NAME).read_bytes() == receipt_bytes

def test_replacement_input_binding_exposes_v4_identity_and_source_hashes(tmp_path: Path, monkeypatch):
    import stom_rl.daily_type1_authority as authority_module

    amendment = json.loads(AMENDMENT_PATH.read_text(encoding="utf-8"))
    assert (REPLACEMENT_AUTHORITY_ID, REPLACEMENT_DATASET_ID, REPLACEMENT_TRAIN_ID, REPLACEMENT_RUN_ID, REPLACEMENT_CUSTODY_UID) == (
        "type1-krx-authority-20260724-004",
        "type1-close-20260803-005",
        "type1-public-005",
        "train_type1-public-005",
        "type1-fresh-oos-20260803-005",
    )
    assert amendment["schema_version"] == "kronos.type1.g002-recovery-amendment.v4"
    assert amendment["amendment_id"] == "KRONOS-TYPE1-G002-RECOVERY-2026-07-24-004"
    assert amendment["replacement_identity"] == {
        "authority_id": REPLACEMENT_AUTHORITY_ID,
        "dataset_id": REPLACEMENT_DATASET_ID,
        "train_id": REPLACEMENT_TRAIN_ID,
        "train_run_id": REPLACEMENT_RUN_ID,
        "custody_uid": REPLACEMENT_CUSTODY_UID,
    }
    assert amendment["execution_contract"] == {
        "proxy_time": "15:20:00",
        "cost_bps": 23,
        "fixed_notional": 60_000_000,
        "primary_seeds": 5,
        "shuffled_seeds": 5,
        "timesteps_per_seed": 200_000,
        "outcome": "NO_GO_ONLY",
    }
    assert amendment["fresh_oos"] == {
        "custody_uid": REPLACEMENT_CUSTODY_UID,
        "status": "NOT_RUN",
        "no_read": True,
        "no_price_or_oos_query_after": "2025-06-30",
    }
    assert amendment["authority_contract"]["authority_metadata_cutoff"] == "2026-07-24"
    assert amendment["authority_contract"]["authority_metadata_scope"] == (
        "MDCSTAT23801 instrument-master metadata only; price, calendar, ranking, "
        "public-row, and fresh-OOS access end at 2025-06-30."
    )
    symbols = [f"{index:06d}" for index in range(500)]
    authority_path = tmp_path / "authority.json"
    authority_path.write_text(json.dumps({"authority": {
        "authority_id": REPLACEMENT_AUTHORITY_ID,
        "stable_symbols": symbols,
        "sessions": {"ordered": [], "pairs": [], "trailing_embargo": []},
    }}), encoding="utf-8")
    amendment_path = AMENDMENT_PATH
    authority_sha = hashlib.sha256(authority_path.read_bytes()).hexdigest()
    amendment_sha = hashlib.sha256(amendment_path.read_bytes()).hexdigest()
    rows_path = tmp_path / "rows.json"
    rows_path.write_text("[]", encoding="utf-8")
    manifest_path = tmp_path / "dataset.json"
    manifest_path.write_text(json.dumps({
        "dataset_id": REPLACEMENT_DATASET_ID,
        "output_sha256": hashlib.sha256(rows_path.read_bytes()).hexdigest(),
        "authority_sha256": authority_sha, "amendment_sha256": amendment_sha,
        "stable_symbols": symbols,
        "fresh_oos": {"state": "NOT_RUN", "read_performed": False},
        "preregistration_sha256": "a" * 64,
    }), encoding="utf-8")
    materializer_path = tmp_path / "materializer.json"
    materializer_path.write_text(json.dumps({
        "dataset_id": REPLACEMENT_DATASET_ID,
        "authority_sha256": authority_sha, "amendment_sha256": amendment_sha,
        "stable_symbols": symbols, "source_database_identity": {"path": "public"},
        "materializer_source_sha256": "b" * 64,
    }), encoding="utf-8")
    monkeypatch.setattr(authority_module, "validate_authority", lambda _: None)
    completion_receipt = tmp_path / "materializer_complete_receipt.json"
    completion_receipt.write_text(json.dumps({
        "schema_version": "kronos.type1.materializer-complete-receipt.v1",
        "role": "materializer_complete_receipt",
        "status": "COMPLETE",
        "dataset_id": REPLACEMENT_DATASET_ID,
        "materializer_manifest_sha256": hashlib.sha256(materializer_path.read_bytes()).hexdigest(),
        "rows_sha256": hashlib.sha256(rows_path.read_bytes()).hexdigest(),
        "authority_sha256": authority_sha,
        "amendment_sha256": amendment_sha,
        "source_hashes": {},
        "materializer_source_sha256": "b" * 64,
        "expected": {},
        "price_basis": None,
        "fresh_oos": {"state": "NOT_RUN", "read_performed": False},
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="three physically distinct canonical dataset artifacts"):
        _verified_inputs(rows_path, manifest_path, authority_path, materializer_path, completion_receipt, amendment_path)



def test_fixed_production_budget_and_members_are_exhaustive(tmp_path: Path):
    operations = FakeOperations()
    result = run_public_experiment(_rows(), out_root=tmp_path, run_id="g002", operations=operations)
    manifest = result["manifest"]
    assert RunConfig().timesteps_per_seed == TIMESTEPS_PER_SEED == 200_000
    assert operations.train_calls == [(seed, 200_000) for seed in range(5) for _ in range(2)]
    assert set(manifest["members"]["primary"]) == {str(seed) for seed in range(5)}
    assert set(manifest["members"]["shuffled_reward"]) == {str(seed) for seed in range(5)}
    assert manifest["training"]["validation_visible_to_training"] is False
    assert manifest["training"]["best_model_selection"] is False
    assert manifest["training"]["synthetic_oracle_calibration"] is False
    assert manifest["fresh_oos"] == {"state": "NOT_RUN", "metrics": None}
    assert manifest["execution_status"] == "BLOCK"
    assert manifest["verdict"] == "NO_GO"
    assert manifest["identities"] == {"production_authoritative": False}
    assert (result["output_dir"] / "run_manifest.json").read_bytes() == json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def test_training_construction_never_receives_reused_validation_rows(tmp_path: Path):
    operations = FakeOperations()
    run_public_experiment(_rows(), out_root=tmp_path, run_id="g002", operations=operations)
    train_calls = [rows for split, _, rows in operations.build_calls if split == "train"]
    assert len(train_calls) == 6
    assert all(all(row["decision_date"] <= PUBLIC_TRAIN_END for row in rows) for rows in train_calls)
    assert all(split == "reused_validation" for split, _, _ in operations.build_calls if split != "train")


@pytest.mark.parametrize(
    "rows",
    [
        [{"decision_date": "2025-07-01"}],
        [{"decision_date": PUBLIC_TRAIN_START, "partition": "fresh_oos"}],
        [{"decision_date": PUBLIC_TRAIN_START, "test_metrics": None}],
    ],
)
def test_fresh_test_rows_are_rejected_fail_closed(rows):
    with pytest.raises(ValueError):
        split_public_rows(rows)


@pytest.mark.parametrize("path", ["dataset_full_001/dataset.csv", "sealed/public.json", "fresh_oos.json", "test.json"])
def test_nonpublic_paths_are_rejected(path: str):
    with pytest.raises(ValueError):
        reject_nonpublic_path(path)


def test_public_loader_is_hard_bounded_to_reused_validation_end():
    captured = {}

    def loader(**kwargs):
        captured.update(kwargs)
        return _rows()

    train, validation = materialize_public_rows(loader, daily_db_path="daily.db", fivemin_db_path="bars.db")
    assert captured["start_date"] == PUBLIC_TRAIN_START
    assert captured["end_date"] == REUSED_VALIDATION_END
    assert len(train) == 2
    assert len(validation) == 2


def test_integrity_failure_is_block_but_scientific_result_remains_no_go(tmp_path: Path):
    operations = FakeOperations()
    operations.controls = lambda *args: {"integrity_ok": False}  # type: ignore[method-assign]
    result = run_public_experiment(_rows(), out_root=tmp_path, run_id="blocked", operations=operations)
    assert result["manifest"]["execution_status"] == "BLOCK"
    assert result["manifest"]["verdict"] == "NO_GO"
    assert result["receipt"]["manifest_sha256"]
    assert result["receipt"]["fresh_oos"] == {"state": "NOT_RUN", "metrics": None}
def test_actual_sb3_timestep_mismatch_is_forced_to_block(tmp_path: Path):
    class WrongTraceOperations(FakeOperations):
        def train(self, pairs, *, seed, timesteps):
            self.train_calls.append((seed, timesteps))
            return type("Model", (), {"num_timesteps": timesteps - 1})(), object()

    operations = WrongTraceOperations()
    with pytest.raises(ValueError, match="exactly 200000"):
        run_public_experiment(_rows(), out_root=tmp_path, run_id="wrong-trace", operations=operations)
    assert operations.train_calls == [(0, 200_000)]
def test_mutation_control_failure_is_blocked(tmp_path: Path):
    operations = FakeOperations()
    operations.controls = lambda *args: {
        "integrity_ok": False,
        "integrity_reasons": ["reused_validation_mutated_train_normalizer"],
    }  # type: ignore[method-assign]
    result = run_public_experiment(_rows(), out_root=tmp_path, run_id="mutation", operations=operations)
    assert result["manifest"]["execution_status"] == "BLOCK"
    assert result["manifest"]["controls"]["integrity_reasons"] == [
        "reused_validation_mutated_train_normalizer",
        "incomplete_or_failed_controls_schema",
    ]


def test_production_pairs_accept_materialized_split_metadata():
    symbols = tuple(f"{index:06d}" for index in range(500))
    rows = [
        {
            "decision_date": decision_date,
            "symbol": "000000",
            "split": "train",
            "features": {
                "ret_1d_prev": value,
                "ret_5d_prev": value,
                "ret_20d_prev": value,
                "vol_z_20": value,
                "foreign_ratio_prev": value,
                "foreign_ratio_delta_5": value,
                "inst_netbuy_norm_5": value,
            },
            "gross_return": "0.01",
            "entry_available": True,
        }
        for decision_date, value in (("2018-01-02", "0"), ("2018-01-03", "1"))
    ]
    rows.append({
        "decision_date": "2018-01-02",
        "symbol": "000001",
        "split": "train",
        "features": {name: "0" for name in rows[0]["features"]},
        "gross_return": "0.50",
        "entry_available": True,
    })
    rows.sort(key=lambda row: (row["decision_date"], row["symbol"]))
    pairs = _ProductionOperations(stable_symbols=symbols).build_pairs(rows, split="train")
    assert len(pairs) == 1
    assert pairs[0]["symbols"] == symbols
    assert pairs[0]["availability_mask"].sum() == 2
    assert pairs[0]["gross_returns"][0] == Decimal("0.01")
    assert pairs[0]["gross_returns"][1] is None
    assert pairs[0]["post_decision_fill_available"][:2].tolist() == [1, 0]
