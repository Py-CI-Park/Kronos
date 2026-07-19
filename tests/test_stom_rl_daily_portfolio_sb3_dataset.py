import csv
import hashlib
import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from stom_rl.daily_portfolio_sb3_dataset import (
    CANDIDATE_FILENAME,
    DailyPortfolioSb3DatasetConfig,
    DailyPortfolioSb3DatasetError,
    build_daily_portfolio_sb3_dataset,
    validate_daily_prediction_lineage,
    write_daily_portfolio_sb3_dataset,
)
from stom_rl.portfolio_env import PortfolioEnv


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _make_sqlite(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute('CREATE TABLE "A000250" (date TEXT PRIMARY KEY, close REAL)')
        conn.executemany(
            'INSERT INTO "A000250" (date, close) VALUES (?, ?)',
            [
                ("2024-01-02", 100.0),
                ("2024-01-03", 110.0),
                ("2024-01-04", 121.0),
                ("2024-01-05", 133.1),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _make_official_prediction_run(tmp_path: Path, *, mutate: str | None = None) -> Path:
    db_path = tmp_path / "daily.sqlite"
    _make_sqlite(db_path)
    dataset_dir = tmp_path / "d2_dataset"
    dataset_dir.mkdir()
    dataset_manifest = {
        "schema_version": 1,
        "daily_db_path": str(db_path),
        "daily_db_sha256": _sha(db_path),
        "split_policy": {"method": "chronological_train_val_test_with_purge_embargo"},
        "split_chronology_status": "PASS",
        "split_summary": {"train": {"rows": 1}, "val": {"rows": 1}, "test": {"rows": 1}},
    }
    if mutate == "missing_db_sha":
        del dataset_manifest["daily_db_sha256"]
    if mutate == "db_sha_mismatch":
        dataset_manifest["daily_db_sha256"] = "0" * 64
    if mutate == "bad_split_chronology":
        dataset_manifest["split_chronology_status"] = "FAIL"
    dataset_manifest_path = dataset_dir / "dataset_manifest.json"
    _write_json(dataset_manifest_path, dataset_manifest)

    run_dir = tmp_path / "d3_run"
    run_dir.mkdir()
    prereg_path = tmp_path / "daily_portfolio_sb3_prereg.md"
    prereg_path.write_text("# Frozen synthetic prereg\n23bp primary, 0/46 controls.\n", encoding="utf-8")
    predictions = [
        {
            "date": "2024-01-02",
            "table": "A000250",
            "code": "000250",
            "split": "train",
            "future_return_1d": "0.1",
            "score_supervised_linear_ranker": "0.90",
            "score_equal_weight_topk_momentum": "0.10",
        },
        {
            "date": "2024-01-03",
            "table": "A000250",
            "code": "000250",
            "split": "val",
            "future_return_1d": "0.1",
            "score_supervised_linear_ranker": "0.80",
            "score_equal_weight_topk_momentum": "0.20",
        },
        {
            "date": "2024-01-04",
            "table": "A000250",
            "code": "000250",
            "split": "test",
            "future_return_1d": "0.1",
            "score_supervised_linear_ranker": "0.70",
            "score_equal_weight_topk_momentum": "0.30",
        },
    ]
    if mutate == "missing_val_split":
        predictions[1]["split"] = "train"
    if mutate == "interleaved_split":
        predictions[0]["split"] = "val"
        predictions[1]["split"] = "train"
    if mutate == "val_after_test_interleaving":
        predictions[1]["split"] = "test"
        predictions[2]["split"] = "val"
    if mutate == "code_mismatch":
        predictions[0]["code"] = "000251"
    if mutate == "symbol_mismatch":
        predictions[0]["symbol"] = "000251"
    if mutate == "missing_future_return_header":
        for row in predictions:
            del row["future_return_1d"]
    if mutate == "blank_future_return":
        predictions[0]["future_return_1d"] = ""
    if mutate == "nonfinite_future_return":
        predictions[0]["future_return_1d"] = "nan"
    if mutate == "return_mismatch":
        predictions[0]["future_return_1d"] = "0.2"
    if mutate == "future_score_column":
        for row in predictions:
            row["score_future_return_1d"] = "1.0"
    predictions_path = run_dir / "predictions.csv"
    _write_csv(predictions_path, predictions)

    baseline_path = run_dir / "baseline_metrics.json"
    baseline_payload = {
        "metrics": [
            {"strategy": "no_trade_cash", "cost_bps": 23.0, "total_net_return": 0.0},
            {"strategy": "shuffle_control", "cost_bps": 23.0, "total_net_return": -0.01},
            {"strategy": "supervised_linear_ranker", "cost_bps": 23.0, "total_net_return": 0.01},
            {
                "strategy": "equal_weight_topk_momentum",
                "strategy_family": "rule_baseline",
                "cost_bps": 23.0,
                "total_net_return": 0.005,
            },
            {
                "strategy": "mean_reversion",
                "strategy_family": "rule_baseline",
                "cost_bps": 23.0,
                "total_net_return": -0.01,
            },
        ]
    }
    if mutate == "missing_control":
        baseline_payload["metrics"] = [baseline_payload["metrics"][0]]
    _write_json(baseline_path, baseline_payload)

    verdict_path = run_dir / "verdict.json"
    _write_json(
        verdict_path,
        {
            "schema_version": 1,
            "status": "WATCH",
            "model_build_allowed": False,
            "paper_forward_allowed": False,
            "live_broker_order_allowed": False,
        },
    )

    manifest = {
        "schema_version": 1,
        "run_id": "official_d3_000250",
        "stage": "D3",
        "status": "pass" if mutate == "input_status_pass" else ("watch" if mutate == "input_status_watch" else "completed"),
        "authoritative": mutate != "not_authoritative",
        "primary_cost_bps": 23.0 if mutate != "wrong_cost" else 25.0,
        "cost_controls_bps": [0.0, 23.0, 46.0],
        "dataset_manifest_path": str(dataset_manifest_path),
        "dataset_manifest_sha256": _sha(dataset_manifest_path),
        "prereg_doc": str(prereg_path),
        "prereg_doc_sha256": _sha(prereg_path),
        "artifact_hashes": {
            "predictions": _sha(predictions_path),
            "baseline_metrics": _sha(baseline_path),
            "verdict": _sha(verdict_path),
        },
    }
    if mutate == "missing_run_id":
        del manifest["run_id"]
    if mutate == "blank_run_id":
        manifest["run_id"] = ""
    if mutate == "missing_hash":
        del manifest["artifact_hashes"]["predictions"]
    if mutate == "missing_prereg":
        del manifest["prereg_doc"]
    if mutate == "missing_prereg_hash":
        del manifest["prereg_doc_sha256"]
    if mutate == "prereg_hash_mismatch":
        manifest["prereg_doc_sha256"] = "0" * 64
    manifest_path = run_dir / "prediction_manifest.json"
    _write_json(manifest_path, manifest)
    if mutate == "hash_mismatch":
        predictions_path.write_text(predictions_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    return run_dir


def test_build_and_write_daily_portfolio_sb3_dataset_preserves_zero_padded_codes_and_portfolio_env_contract(tmp_path):
    run_dir = _make_official_prediction_run(tmp_path)

    lineage = validate_daily_prediction_lineage(run_dir)
    dataset = build_daily_portfolio_sb3_dataset(DailyPortfolioSb3DatasetConfig(prediction_run_dir=run_dir))
    written = write_daily_portfolio_sb3_dataset(dataset, output_dir=tmp_path / "out", run_id="sb3_candidates")

    assert lineage["status"] == "PASS"
    assert list(dataset.candidates.columns) == [
        "timestamp",
        "symbol",
        "rank_score",
        "price",
        "fill_price",
        "fillable",
        "split",
        "future_return_1d",
        "table",
        "code",
        "source_prediction_run_id",
    ]
    assert dataset.candidates["symbol"].tolist() == ["000250", "000250", "000250"]
    assert dataset.candidates["code"].tolist() == ["000250", "000250", "000250"]
    assert dataset.candidates["price"].tolist() == [100.0, 110.0, 121.0]
    assert dataset.candidates["fill_price"].tolist() == [110.0, 121.0, 133.1]
    assert all(abs(value - 0.1) < 1e-10 for value in dataset.candidates["future_return_1d"])
    assert "feature_future_return_1d" not in dataset.candidates.columns
    assert lineage["daily_db_sha256"] == dataset.manifest["daily_db_sha256"]
    assert dataset.manifest["research_only"] is True
    assert dataset.manifest["model_build_allowed"] is False
    assert dataset.manifest["paper_forward_allowed"] is False
    assert dataset.manifest["live_broker_order_allowed"] is False
    assert dataset.manifest["profit_claim_allowed"] is False

    candidate_path = Path(written["daily_portfolio_sb3_candidates_path"])
    with candidate_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["symbol"] == "000250"
    assert rows[0]["code"] == "000250"
    assert written["output_hashes"]["daily_portfolio_sb3_candidates"] == _sha(candidate_path)
    manifest_path = Path(written["daily_portfolio_sb3_dataset_manifest_path"])
    written_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert written_manifest["daily_db_sha256"] == _sha(Path(written_manifest["daily_db_path"]))

    env = PortfolioEnv(candidates=pd.read_csv(candidate_path, dtype={"symbol": str, "code": str}))
    assert env._load_candidates(pd.read_csv(candidate_path, dtype={"symbol": str, "code": str}))["fillable"].all()


@pytest.mark.parametrize(
    "mutate",
    [
        "not_authoritative",
        "wrong_cost",
        "missing_control",
        "missing_hash",
        "hash_mismatch",
        "missing_prereg",
        "missing_prereg_hash",
        "prereg_hash_mismatch",
        "bad_split_chronology",
        "return_mismatch",
        "future_score_column",
        "missing_val_split",
        "interleaved_split",
        "val_after_test_interleaving",
        "code_mismatch",
        "symbol_mismatch",
        "missing_future_return_header",
        "blank_future_return",
        "nonfinite_future_return",
        "missing_db_sha",
        "db_sha_mismatch",
        "input_status_watch",
        "input_status_pass",
        "missing_run_id",
        "blank_run_id",
    ],
)
def test_daily_portfolio_sb3_dataset_fails_closed_before_trainer_boundary(tmp_path, mutate):
    run_dir = _make_official_prediction_run(tmp_path, mutate=mutate)

    with pytest.raises(DailyPortfolioSb3DatasetError):
        build_daily_portfolio_sb3_dataset(DailyPortfolioSb3DatasetConfig(prediction_run_dir=run_dir))


def test_write_rejects_unsafe_run_id(tmp_path):
    run_dir = _make_official_prediction_run(tmp_path)
    dataset = build_daily_portfolio_sb3_dataset(DailyPortfolioSb3DatasetConfig(prediction_run_dir=run_dir))

    with pytest.raises(DailyPortfolioSb3DatasetError):
        write_daily_portfolio_sb3_dataset(dataset, output_dir=tmp_path / "out", run_id="../escape")


def test_missing_next_close_fails_closed(tmp_path):
    run_dir = _make_official_prediction_run(tmp_path)
    prediction_path = run_dir / "predictions.csv"
    with prediction_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[-1]["date"] = "2024-01-05"
    rows[-1]["future_return_1d"] = "0.1"
    _write_csv(prediction_path, rows)
    manifest_path = run_dir / "prediction_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_hashes"]["predictions"] = _sha(prediction_path)
    _write_json(manifest_path, manifest)

    with pytest.raises(DailyPortfolioSb3DatasetError):
        build_daily_portfolio_sb3_dataset(DailyPortfolioSb3DatasetConfig(prediction_run_dir=run_dir))
