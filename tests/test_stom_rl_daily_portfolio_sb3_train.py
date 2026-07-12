import json
from dataclasses import replace
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

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
                "baseline_metrics": "b" * 64,
            },
            "source_baseline_metrics_sha256": "b" * 64,
            "source_baseline_metrics": [
                {"strategy": "no_trade_cash", "cost_bps": 23.0, "total_net_return": 0.0},
                {"strategy": "shuffle_control", "cost_bps": 23.0, "total_net_return": -0.01},
                {
                    "strategy": "equal_weight_topk_momentum",
                    "strategy_family": "rule_baseline",
                    "cost_bps": 23.0,
                    "total_net_return": 0.01,
                },
                {
                    "strategy": "mean_reversion",
                    "strategy_family": "rule_baseline",
                    "cost_bps": 23.0,
                    "total_net_return": 0.02,
                },
            ],
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

    def fake_train(config, *, candidates=None, live_events_path=None, **_kwargs):
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

def test_daily_portfolio_sb3_g017_smoke_contract_streams_training_events(tmp_path, monkeypatch):
    candidates = _approved_candidates()
    _patch_dataset(monkeypatch, candidates)

    def fake_train(
        config,
        *,
        candidates=None,
        live_events_path=None,
        live_event_step_offset=0,
        live_event_info=None,
        validation_candidates=None,
        validation_evidence_path=None,
        validation_fold_index=0,
        validation_cost_label="base_23bp",
        **_kwargs,
    ):
        assert config.write_training_events is True
        assert live_events_path is not None
        assert candidates is not None and set(candidates["split"]) <= {"train", "val"}
        assert validation_candidates is not None
        assert "test" not in set(validation_candidates["split"])
        writer = trainer.RlLiveEventWriter(live_events_path, run_id="unit_g017")
        writer.write_step(
            algorithm="portfolio_ppo",
            phase="train",
            global_step=int(live_event_step_offset) + 10,
            action=None,
            reward=1.0,
            equity=None,
            source="daily_portfolio_sb3_train",
            info={**dict(live_event_info or {}), "action_recorded": False},
        )
        model = _FakeModel(device="training-cuda")
        metrics = trainer._evaluate_model_on_candidates(
            model,
            config,
            validation_candidates,
            fold_index=int(validation_fold_index),
            cost_label=validation_cost_label,
        )
        trainer._write_json_sorted(
            validation_evidence_path,
            {
                "schema_version": "daily_portfolio_sb3_validation_callback_evidence.v1",
                "callback_executed": True,
                "fold_index": int(validation_fold_index),
                "source": "synthetic_callback_validation_frame_only",
                "official_test_used": False,
                "metrics": metrics,
                "finite_metrics": True,
            },
        )
        return model, {"last_training_event_step": int(live_event_step_offset) + 10}

    monkeypatch.setattr(trainer, "train_portfolio_model", fake_train)
    monkeypatch.setattr(trainer, "load_trained_model", lambda *_args, **_kwargs: _FakeModel(device="eval-cpu"))

    summary = trainer.run_daily_portfolio_sb3(
        trainer.DailyPortfolioSb3TrainConfig(
            prediction_run_dir="unused-approved-adapter",
            output_dir=str(tmp_path),
            run_id="unit_g017",
            algorithm="ppo",
            total_timesteps=5_000,
            seed=7,
            n_folds=2,
            run_stage="smoke",
            run_status="completed",
            run_authority="G017_preregistered_smoke",
            authoritative=True,
            is_smoke=True,
            stream_training_events=True,
        )
    )

    run_dir = tmp_path / "unit_g017"
    rl_manifest = json.loads((run_dir / "rl_manifest.json").read_text(encoding="utf-8"))
    assert summary["stage"] == rl_manifest["stage"] == "smoke"
    assert summary["status"] == rl_manifest["status"] == "completed"
    assert rl_manifest["authoritative"] is True
    assert rl_manifest["is_smoke"] is True
    assert summary["live_events"]["phases"]["train"] == summary["fold_count"]
    assert summary["live_events"]["event_count"] == summary["fold_count"] * 2 + 1
    assert all(fold["validation_callback_evidence"]["official_test_used"] is False for fold in summary["folds"])
    assert summary["source_baselines"]["usage"]["secondary_label"] == "combined_val_test_source_metrics_secondary"


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"algorithm": "dqn"}, "algorithm='ppo'"),
        ({"total_timesteps": 4_999}, "total_timesteps=5000"),
        ({"seed": 8}, "seed=7"),
        ({"primary_cost_bps": 22.0}, "primary_cost_bps=23.0"),
        ({"control_cost_bps": (0.0, 45.0)}, r"control_cost_bps=\(0.0, 46.0\)"),
        ({"write_artifacts": False}, "write_artifacts=True"),
        ({"stream_training_events": False}, "stream_training_events=True"),
    ],
)
def test_daily_portfolio_sb3_g017_smoke_contract_rejects_frozen_tuple_drift(changes, message):
    config = trainer.DailyPortfolioSb3TrainConfig(
        prediction_run_dir="approved-adapter",
        algorithm="ppo",
        total_timesteps=5_000,
        seed=7,
        primary_cost_bps=23.0,
        control_cost_bps=(0.0, 46.0),
        write_artifacts=True,
        run_stage="smoke",
        run_status="completed",
        run_authority="G017_preregistered_smoke",
        authoritative=True,
        is_smoke=True,
        stream_training_events=True,
    )

    with pytest.raises(ValueError, match=message):
        trainer._daily_run_contract(replace(config, **changes))


def test_daily_portfolio_sb3_full_contract_exposes_bounded_200k_per_seed_path():
    config = trainer.DailyPortfolioSb3TrainConfig(
        prediction_run_dir="approved-adapter",
        algorithm="ppo",
        total_timesteps=200_000,
        seed=17,
        primary_cost_bps=23.0,
        control_cost_bps=(0.0, 46.0),
        write_artifacts=True,
        run_stage="full",
        run_status="completed",
        run_authority="PREREG_REQUIRED_BEFORE_EXECUTION",
        authoritative=True,
        is_smoke=False,
        stream_training_events=True,
    )

    contract = trainer._daily_run_contract(config)

    assert contract == {
        "stage": "full",
        "status": "completed",
        "authority": "PREREG_REQUIRED_BEFORE_EXECUTION",
        "authoritative": True,
        "is_smoke": False,
        "is_full": True,
    }


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"total_timesteps": 199_999}, "total_timesteps>=200000"),
        ({"primary_cost_bps": 22.0}, "primary_cost_bps=23.0"),
        ({"control_cost_bps": (0.0, 45.0)}, r"control_cost_bps=\(0.0, 46.0\)"),
        ({"write_artifacts": False}, "write_artifacts=True"),
        ({"stream_training_events": False}, "stream_training_events=True"),
        ({"is_smoke": True}, "stage='smoke'"),
    ],
)
def test_daily_portfolio_sb3_full_contract_fails_closed_on_path_drift(changes, message):
    config = trainer.DailyPortfolioSb3TrainConfig(
        prediction_run_dir="approved-adapter",
        algorithm="ppo",
        total_timesteps=200_000,
        seed=17,
        primary_cost_bps=23.0,
        control_cost_bps=(0.0, 46.0),
        write_artifacts=True,
        run_stage="full",
        run_status="completed",
        run_authority="PREREG_REQUIRED_BEFORE_EXECUTION",
        authoritative=True,
        is_smoke=False,
        stream_training_events=True,
    )

    with pytest.raises(ValueError, match=message):
        trainer._daily_run_contract(replace(config, **changes))


def test_real_training_callback_streams_rollouts_and_writes_validation_evidence(tmp_path, monkeypatch):
    class _BaseCallback:
        def __init__(self, verbose=0):
            self.verbose = verbose
            self.model = None
            self.logger = None
            self.num_timesteps = 0

    sb3_module = ModuleType("stable_baselines3")
    common_module = ModuleType("stable_baselines3.common")
    callbacks_module = ModuleType("stable_baselines3.common.callbacks")
    callbacks_module.BaseCallback = _BaseCallback
    monkeypatch.setitem(sys.modules, "stable_baselines3", sb3_module)
    monkeypatch.setitem(sys.modules, "stable_baselines3.common", common_module)
    monkeypatch.setitem(sys.modules, "stable_baselines3.common.callbacks", callbacks_module)

    candidates = _approved_candidates()
    validation_candidates = candidates[candidates["split"] == "val"].reset_index(drop=True)
    live_events_path = tmp_path / "real_callback" / "rl_live_events.jsonl"
    validation_evidence_path = tmp_path / "real_callback" / "validation_callback_evidence.json"
    validation_config = trainer.PortfolioSb3TrainConfig(
        algorithm="ppo",
        total_timesteps=16,
        seed=7,
        device="cpu",
        max_eval_steps=16,
        write_artifacts=False,
        write_training_events=True,
    )
    writer = trainer.RlLiveEventWriter(live_events_path, run_id="real_callback")
    writer.reset()
    callback = trainer._make_training_callback(
        "ppo",
        event_writer=writer,
        step_offset=11,
        event_info={"fold_index": 0, "device": {"requested": "cpu", "used": "cpu"}},
        event_source="daily_portfolio_sb3_train",
        validation_config=validation_config,
        validation_candidates=validation_candidates,
        validation_evidence_path=validation_evidence_path,
        validation_fold_index=0,
        validation_cost_label="base_23bp",
    )
    model = _FakeModel(device="cpu")
    model.ep_info_buffer = [{"r": 0.5}]
    callback.model = model
    callback.logger = SimpleNamespace(name_to_value={"train/loss": 0.25})
    callback.num_timesteps = 8
    callback._on_rollout_end()
    callback.logger.name_to_value["train/loss"] = 0.125
    callback.num_timesteps = 16
    callback._on_rollout_end()
    callback._on_training_end()

    rows = [
        json.loads(line)
        for line in live_events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    steps = [row["global_step"] for row in rows]
    assert len(rows) == 3
    assert steps == [19, 27, 27]
    assert callback.last_global_step == 27
    assert [row["loss"] for row in rows] == [0.25, 0.125, 0.125]
    assert all(row["phase"] == "train" for row in rows)
    assert all(row["action"] is None for row in rows)
    assert all(row["info"]["action_recorded"] is False for row in rows)
    assert all(row["info"]["device"]["used"] == "cpu" for row in rows)

    evidence = json.loads(validation_evidence_path.read_text(encoding="utf-8"))
    assert evidence["callback_executed"] is True
    assert evidence["source"] == "sb3_on_training_end_fold_validation_frame_only"
    assert evidence["official_test_used"] is False
    assert evidence["finite_metrics"] is True
    assert evidence["validation_range"]["row_count"] == len(validation_candidates)
    assert evidence["validation_range"]["start"] == pd.Timestamp(validation_candidates["timestamp"].min()).isoformat()
    assert evidence["validation_range"]["end"] == pd.Timestamp(validation_candidates["timestamp"].max()).isoformat()
    assert trainer._finite_metrics(evidence["metrics"])


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
