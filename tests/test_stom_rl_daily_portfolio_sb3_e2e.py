import csv
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stom_rl import portfolio_sb3_train as trainer  # noqa: E402
from stom_rl.rl_events import SCHEMA_VERSION  # noqa: E402
from webui import rl_dashboard  # noqa: E402


_EVENT_KEYS = {
    "run_id",
    "algorithm",
    "phase",
    "global_step",
    "action",
    "reward",
    "episode",
    "episode_id",
    "timestamp",
    "price",
    "position",
    "equity",
    "loss",
    "exploration",
    "source",
    "schema_version",
    "timestamp_utc",
    "info",
    "action_name",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
class _FakeSb3Model:
    device = "cpu"

    def predict(self, _observation, *, deterministic=True):
        assert deterministic is True
        return 0, None

    def save(self, path: str) -> None:
        Path(path).write_bytes(b"synthetic-sb3-model-zip")


def _fake_train_portfolio_model(_config, *, candidates):
    assert not candidates.empty
    return _FakeSb3Model(), {
        "device_requested": "cpu",
        "device_used": "cpu",
        "deterministic": True,
        "test_double": True,
    }




def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _make_daily_prediction_run(tmp_path: Path) -> Path:
    dates = [f"2024-01-{day:02d}" for day in range(2, 11)]
    symbols = ["000250", "000660"]
    db_path = tmp_path / "daily.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        for offset, symbol in enumerate(symbols):
            conn.execute(f'CREATE TABLE "A{symbol}" (date TEXT PRIMARY KEY, close REAL)')
            rows = [(date, 100.0 + offset * 20.0 + idx * (1.0 + offset * 0.5)) for idx, date in enumerate(dates)]
            conn.executemany(f'INSERT INTO "A{symbol}" (date, close) VALUES (?, ?)', rows)
        conn.commit()
    finally:
        conn.close()

    dataset_dir = tmp_path / "d2_dataset"
    dataset_dir.mkdir()
    dataset_manifest = {
        "schema_version": 1,
        "daily_db_path": str(db_path),
        "daily_db_sha256": _sha(db_path),
        "split_policy": {"method": "chronological_train_val_test_with_purge_embargo"},
        "split_chronology_status": "PASS",
        "split_summary": {"train": {"rows": 8}, "val": {"rows": 4}, "test": {"rows": 4}},
    }
    dataset_manifest_path = dataset_dir / "dataset_manifest.json"
    _write_json(dataset_manifest_path, dataset_manifest)

    run_dir = tmp_path / "official_d3"
    run_dir.mkdir()
    predictions = []
    for day_index, date in enumerate(dates[:-1]):
        split = "train" if day_index < 4 else "val" if day_index < 6 else "test"
        for rank, symbol in enumerate(symbols):
            current = 100.0 + rank * 20.0 + day_index * (1.0 + rank * 0.5)
            next_close = 100.0 + rank * 20.0 + (day_index + 1) * (1.0 + rank * 0.5)
            predictions.append(
                {
                    "date": date,
                    "table": f"A{symbol}",
                    "code": symbol,
                    "split": split,
                    "future_return_1d": repr((next_close / current) - 1.0),
                    "score_supervised_linear_ranker": repr(1.0 - rank * 0.1 + day_index * 0.01),
                    "score_equal_weight_topk_momentum": repr(0.5 + rank * 0.05),
                }
            )
    predictions_path = run_dir / "predictions.csv"
    _write_csv(predictions_path, predictions)

    baseline_path = run_dir / "baseline_metrics.json"
    _write_json(
        baseline_path,
        {
            "metrics": [
                {"strategy": "no_trade_cash", "cost_bps": 23.0, "total_net_return": 0.0},
                {"strategy": "shuffle_control", "cost_bps": 23.0, "total_net_return": -0.01},
                {"strategy": "supervised_linear_ranker", "cost_bps": 23.0, "total_net_return": 0.01},
            ]
        },
    )
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
    prereg_path = tmp_path / "daily_portfolio_sb3_prereg.md"
    prereg_path.write_text("# Synthetic daily portfolio SB3 prereg\n23bp primary, 0/46 controls.\n", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "run_id": "official_d3_synthetic",
        "stage": "D3",
        "status": "completed",
        "authoritative": True,
        "primary_cost_bps": 23.0,
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
    _write_json(run_dir / "prediction_manifest.json", manifest)
    return run_dir


def _write_legacy_daily_fixture(root: Path) -> None:
    run = root / "legacy_daily_tabular"
    run.mkdir(parents=True)
    _write_json(
        run / "rl_manifest.json",
        {
            "schema_version": "legacy_daily_ohlcv_portfolio.v1",
            "summary": {"policy": "legacy_tabular", "final_nav": 1000000.0},
        },
    )


def test_daily_portfolio_sb3_e2e_artifacts_dashboard_discovery_and_v1_events(tmp_path, monkeypatch):
    prediction_run = _make_daily_prediction_run(tmp_path)
    run_root = tmp_path / "webui" / "rl_runs"
    output_dir = run_root / "daily_ohlcv_portfolio_sb3"
    _write_legacy_daily_fixture(run_root)
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [run_root])
    monkeypatch.setattr(trainer, "train_portfolio_model", _fake_train_portfolio_model)
    monkeypatch.setattr(trainer, "load_trained_model", lambda *_args, **_kwargs: _FakeSb3Model())

    summary = trainer.run_daily_portfolio_sb3(
        trainer.DailyPortfolioSb3TrainConfig(
            prediction_run_dir=str(prediction_run),
            output_dir=str(output_dir),
            run_id="e2e_512_step_daily_sb3",
            algorithm="ppo",
            total_timesteps=512,
            seed=7,
            n_folds=2,
            max_eval_steps=512,
            device="cpu",
        )
    )

    run_dir = output_dir / "e2e_512_step_daily_sb3"
    required = {
        "rl_manifest.json",
        "training_manifest.json",
        "daily_portfolio_sb3_candidates.csv",
        "daily_portfolio_sb3_dataset_manifest.json",
        "source_hashes.json",
        "rl_live_events.jsonl",
        "rl_live_summary.json",
        "sb3_smoke_summary.json",
    }
    assert required.issubset({path.name for path in run_dir.iterdir()})
    assert len(list((run_dir / "models").glob("fold_*/portfolio_ppo_model.zip"))) == summary["fold_count"] == 2

    runs = rl_dashboard.list_rl_runs(limit=20)
    by_name = {run["name"]: run for run in runs}
    assert by_name["e2e_512_step_daily_sb3"]["artifact_type"] == "sb3_smoke"
    assert by_name["legacy_daily_tabular"]["artifact_type"] == "daily_ohlcv_portfolio"

    detail = rl_dashboard.load_rl_run("e2e_512_step_daily_sb3")
    assert detail["artifact_type"] == "sb3_smoke"
    assert detail["model"]["model_type"] == "stable_baselines3_ppo"
    assert detail["live_events"]["event_count"] == summary["fold_count"] + 1
    assert detail["lifecycle"]["status"] == "COMPLETED"
    assert detail["lifecycle"]["is_live"] is False

    rows = rl_dashboard.load_rl_events("e2e_512_step_daily_sb3", limit=20)["rows"]
    assert [row["global_step"] for row in rows] == sorted(row["global_step"] for row in rows)
    assert rows[-1]["phase"] == "completed"
    for row in rows:
        assert set(row) == _EVENT_KEYS
        assert row["schema_version"] == SCHEMA_VERSION
        assert row["action"] is None
        assert row["action_name"] is None
        assert row["info"]["action_recorded"] is False
        assert row["info"]["cost_scenario"] == "base_23bp"
        assert row["info"]["reward_kind"] == "raw_reward"
        assert row["info"]["reward_unit"] == "score"
        assert row["info"]["equity_kind"] == "krw_nav"
        assert row["info"]["equity_unit"] == "krw"
        assert row["info"]["device"]["requested"] == "cpu"
        assert row["info"]["source_lineage"]["d2_daily_db_sha256"]

    source_hashes = json.loads((run_dir / "source_hashes.json").read_text(encoding="utf-8"))
    assert source_hashes["config_sha256"]
    assert source_hashes["model_hashes"] and all(len(value) == 64 for value in source_hashes["model_hashes"].values())
    assert source_hashes["lineage_hashes"]["d3_prediction_manifest_sha256"]
    assert source_hashes["lineage_hashes"]["d2_dataset_manifest_sha256"]
    assert source_hashes["lineage_hashes"]["d2_daily_db_sha256"]
    assert source_hashes["lineage_hashes"]["prereg_sha256"]

    training_manifest = json.loads((run_dir / "training_manifest.json").read_text(encoding="utf-8"))
    assert training_manifest["oos_rows_used_for_fit"] == 0
    assert training_manifest["primary_cost_label"] == "base_23bp"
    assert training_manifest["control_cost_bps"] == [0.0, 46.0]
    assert training_manifest["false_locks"] == {
        "live_broker_order_allowed": False,
        "model_build_allowed": False,
        "paper_forward_allowed": False,
        "profit_claim_allowed": False,
    }
    assert all(fold["oos_rows_used_for_fit"] == 0 for fold in training_manifest["folds"])
