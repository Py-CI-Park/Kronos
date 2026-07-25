from __future__ import annotations

import hashlib
import json
from pathlib import Path
from decimal import Decimal

import pytest

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
    materialize_public_rows,
    reject_nonpublic_path,
    run_public_experiment,
    split_public_rows,
    _ProductionOperations,
    REPLACEMENT_AUTHORITY_ID,
    REPLACEMENT_DATASET_ID,
    REPLACEMENT_RUN_ID,
    REPLACEMENT_TRAIN_ID,
    REPLACEMENT_CUSTODY_UID,
    _verified_inputs,
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
    ])
    assert args.run_id == "g002"
    assert args.dataset_manifest == "manifest.json"
    assert args.authority == "authority.json"
    assert args.materializer_manifest == "materializer.json"
    assert "--universe-manifest" not in parser.format_help()
    assert "--seeds" not in parser.format_help()
    assert "--smoke" not in parser.format_help()
    assert "best" not in parser.format_help().lower()
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
    with pytest.raises(ValueError, match="materializer manifest"):
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
