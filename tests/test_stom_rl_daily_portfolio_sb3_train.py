import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stom_rl import portfolio_sb3_train as trainer  # noqa: E402
from stom_rl.daily_portfolio_sb3_dataset import DailyPortfolioSb3DatasetError  # noqa: E402


def _approved_candidates() -> pd.DataFrame:
    rows = []
    for day in range(6):
        ts = pd.Timestamp("2026-01-01") + pd.Timedelta(days=day)
        split = "train" if day < 3 else "val" if day < 5 else "test"
        for rank, symbol in enumerate(["000001", "000002"]):
            price = 100.0 + day + rank
            rows.append(
                {
                    "timestamp": ts.date().isoformat(),
                    "symbol": symbol,
                    "rank_score": float(10 - rank + day),
                    "price": price,
                    "fill_price": price + 1.0,
                    "fillable": True,
                    "split": split,
                    "future_return_1d": 0.01,
                    "table": f"A{symbol}",
                    "code": symbol,
                    "source_prediction_run_id": "pred_unit",
                    "feature_score_aux": float(rank),
                }
            )
    return pd.DataFrame(rows)


class _FakeModel:
    def __init__(self, device: str = "train-device") -> None:
        self.device = device
        self.learn_frames = []

    def learn(self, *, total_timesteps, progress_bar=False, callback=None):
        self.total_timesteps = total_timesteps
        self.progress_bar = progress_bar
        self.callback = callback
        return self

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"fake deterministic dqn model zip")

    def predict(self, observation, deterministic=True):
        return 1, None


def _patch_dataset(monkeypatch, candidates: pd.DataFrame) -> None:
    dataset = SimpleNamespace(
        candidates=candidates,
        manifest={
            "source_artifact_hashes": {
                "prediction_manifest": "p" * 64,
                "preregistration": "r" * 64,
            },
            "preregistration_path": "docs/stom_daily_sb3_ppo_prereg_2026-07-12.md",
            "preregistration_sha256": "r" * 64,
            "primary_cost_bps": 23.0,
        },
    )
    monkeypatch.setattr(trainer, "build_daily_portfolio_sb3_dataset", lambda config: dataset)


def test_daily_portfolio_sb3_fold_local_dqn_controls_do_not_retrain(tmp_path, monkeypatch):
    candidates = _approved_candidates()
    _patch_dataset(monkeypatch, candidates)
    train_calls = []
    loaded_paths = []

    def fake_train(config, *, candidates=None, live_events_path=None):
        assert live_events_path is None
        assert candidates is not None and not candidates.empty
        train_calls.append({"config": config, "timestamps": set(pd.to_datetime(candidates["timestamp"]))})
        model = _FakeModel(device="training-cuda")
        model.learn(total_timesteps=config.total_timesteps, progress_bar=False, callback=None)
        return model, {"device_pinned": config.device, "seed": config.seed}

    def fake_load(path, *, algorithm="ppo"):
        loaded_paths.append((path, algorithm))
        return _FakeModel(device="eval-cpu")

    monkeypatch.setattr(trainer, "train_portfolio_model", fake_train)
    monkeypatch.setattr(trainer, "load_trained_model", fake_load)

    summary = trainer.run_daily_portfolio_sb3(
        trainer.DailyPortfolioSb3TrainConfig(
            prediction_run_dir="unused-approved-adapter",
            output_dir=str(tmp_path),
            run_id="unit_dqn",
            algorithm="dqn",
            total_timesteps=512,
            n_folds=2,
            max_eval_steps=512,
        )
    )

    assert summary["algorithm"] == "dqn"
    assert summary["primary_cost_label"] == "base_23bp"
    assert len(train_calls) == summary["fold_count"] == 2
    assert all(call["config"].algorithm == "dqn" for call in train_calls)
    assert all(call["config"].total_timesteps == 512 for call in train_calls)
    assert all(algorithm == "dqn" for _path, algorithm in loaded_paths)
    assert summary["device_used"] == "training-cuda"
    assert all(row["training_device_used"] == "training-cuda" for row in summary["device_used_by_fold"])
    assert all(row["eval_device"] == "eval-cpu" for row in summary["device_used_by_fold"])
    assert summary["official_split_row_counts"]["test"] == 2
    assert summary["oos_rows_used_for_fit"] == 0
    official_test_ts = set(pd.to_datetime(candidates[candidates["split"] == "test"]["timestamp"]))
    for fold, call in zip(summary["folds"], train_calls):
        test_range = fold["test_range"]
        test_ts = set(
            pd.to_datetime(
                candidates[
                    (pd.to_datetime(candidates["timestamp"]) >= pd.Timestamp(test_range["start"]))
                    & (pd.to_datetime(candidates["timestamp"]) <= pd.Timestamp(test_range["end"]))
                ]["timestamp"]
            )
        )
        assert call["timestamps"].isdisjoint(test_ts)
        assert official_test_ts.isdisjoint(test_ts)
        assert call["timestamps"].isdisjoint(official_test_ts)
        assert fold["train_range"]["row_count"] > 0
        assert fold["validation_range"]["row_count"] > 0
        assert fold["official_test_oos_range"]["row_count"] == 2
        assert fold["oos_rows_used_for_fit"] == 0
        assert fold["model_path"].endswith("portfolio_dqn_model.zip")
        assert fold["model_sha256"]
        assert fold["headline"] == "base_23bp"
        assert fold["training_device_used"] == "training-cuda"
        assert fold["eval_device"] == "eval-cpu"
        assert fold["controls_retrained"] is False
        assert [m["cost_label"] for m in fold["control_metrics"]] == ["control_0bp", "control_46bp"]
        assert [m["cost_label"] for m in fold["untouched_test_oos_control_metrics"]] == ["control_0bp", "control_46bp"]
        assert fold["untouched_test_oos_primary_metrics"]["cost_label"] == "base_23bp"
        assert fold["maskable_ppo_trigger"]["recommendation_only"] is True
        assert fold["false_locks"]["live_broker_order_allowed"] is False


@pytest.mark.parametrize("fixture_label", ["lineage", "hash", "cost", "next-day"])
def test_daily_portfolio_sb3_adapter_fail_closed_before_trainer(tmp_path, monkeypatch, fixture_label):
    def bad_build(config):
        raise DailyPortfolioSb3DatasetError(f"bad {fixture_label} fixture")

    def forbidden_train(*args, **kwargs):  # pragma: no cover - should never execute
        raise AssertionError("trainer boundary was reached")

    monkeypatch.setattr(trainer, "build_daily_portfolio_sb3_dataset", bad_build)
    monkeypatch.setattr(trainer, "train_portfolio_model", forbidden_train)

    with pytest.raises(DailyPortfolioSb3DatasetError, match=fixture_label):
        trainer.run_daily_portfolio_sb3(
            trainer.DailyPortfolioSb3TrainConfig(
                prediction_run_dir="malformed",
                output_dir=str(tmp_path),
                run_id="bad",
                total_timesteps=512,
            )
        )
