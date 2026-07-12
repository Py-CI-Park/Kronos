"""WP-R2 close-slot observability: round-level reward persistence + event
instrumentation (F3/F4) + run discoverability (F5).

Guardrails under test:
  C3 -- RULE/baseline evaluations (no_trade/shuffle/momentum/D3-frozen) must
        never be emitted as linear_score_and_pick_train_only events.
  C6 -- stom_rl/rl_events.py is untouched; schema_version stays
        'stom_rl_live_event.v1'.
"""

import csv
import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stom_rl.daily_close_slot_train import (  # noqa: E402
    CloseSlotTrainConfig,
    LIVE_EVENTS_FILE_NAME,
    run_close_slot_training,
)
from stom_rl.rl_events import RlLiveEventWriter, read_live_events  # noqa: E402


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        digest.update(handle.read())
    return digest.hexdigest()


def _write_csv(path: Path, rows: list[dict], fallback: list[str]) -> None:
    fields = sorted({key for row in rows for key in row}) if rows else fallback
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


# Reuse pattern from tests/test_stom_rl_daily_close_slot_train.py::_write_dataset_run.
def _write_dataset_run(root: Path, run_id: str = "dataset_unit") -> dict:
    out = root / run_id
    out.mkdir(parents=True)
    panel_rows = [
        {
            "date": "2024-04-01",
            "exit_date": "2024-04-02",
            "table": "A000001",
            "code": "000001",
            "split": "train",
            "entry_close": 1000,
            "next_close": 1100,
            "future_return_1d": 0.10,
            "eligible_for_selection": True,
            "candidate_score_causal_momentum": 0.5,
            "feature_a": 1.0,
        },
        {
            "date": "2024-04-01",
            "exit_date": "2024-04-02",
            "table": "A000002",
            "code": "000002",
            "split": "train",
            "entry_close": 1000,
            "next_close": 900,
            "future_return_1d": -0.10,
            "eligible_for_selection": True,
            "candidate_score_causal_momentum": -0.5,
            "feature_a": -1.0,
        },
        {
            "date": "2024-04-02",
            "exit_date": "2024-04-03",
            "table": "A000001",
            "code": "000001",
            "split": "train",
            "entry_close": 1000,
            "next_close": 1020,
            "future_return_1d": 0.02,
            "eligible_for_selection": True,
            "candidate_score_causal_momentum": 0.9,
            "feature_a": 2.0,
        },
        {
            "date": "2024-04-02",
            "exit_date": "2024-04-03",
            "table": "A000002",
            "code": "000002",
            "split": "train",
            "entry_close": 1000,
            "next_close": 980,
            "future_return_1d": -0.02,
            "eligible_for_selection": True,
            "candidate_score_causal_momentum": -0.9,
            "feature_a": -2.0,
        },
        {
            "date": "2024-04-03",
            "exit_date": "2024-04-04",
            "table": "A000001",
            "code": "000001",
            "split": "val",
            "entry_close": 1000,
            "next_close": 1030,
            "future_return_1d": 0.03,
            "eligible_for_selection": True,
            "candidate_score_causal_momentum": 0.1,
            "feature_a": 0.25,
        },
        {
            "date": "2024-04-03",
            "exit_date": "2024-04-04",
            "table": "A000002",
            "code": "000002",
            "split": "val",
            "entry_close": 1000,
            "next_close": 970,
            "future_return_1d": -0.03,
            "eligible_for_selection": True,
            "candidate_score_causal_momentum": -0.1,
            "feature_a": -0.25,
        },
        {
            "date": "2024-04-04",
            "exit_date": "2024-04-05",
            "table": "A000001",
            "code": "000001",
            "split": "test",
            "entry_close": 1000,
            "next_close": 1040,
            "future_return_1d": 0.04,
            "eligible_for_selection": True,
            "candidate_score_causal_momentum": 0.05,
            "feature_a": 0.15,
        },
        {
            "date": "2024-04-04",
            "exit_date": "2024-04-05",
            "table": "A000002",
            "code": "000002",
            "split": "test",
            "entry_close": 1000,
            "next_close": 960,
            "future_return_1d": -0.04,
            "eligible_for_selection": True,
            "candidate_score_causal_momentum": -0.05,
            "feature_a": -0.15,
        },
    ]
    paths = {
        "close_slot_panel": out / "close_slot_panel.csv",
        "candidate_scores_input_schema": out / "candidate_scores_input_schema.json",
        "candidate_score_rows": out / "candidate_score_rows.csv",
        "feature_contract": out / "feature_contract.json",
        "label_audit": out / "label_audit.csv",
        "split_summary": out / "split_summary.json",
        "source_hashes": out / "source_hashes.json",
    }
    _write_csv(paths["close_slot_panel"], panel_rows, [])
    _write_csv(paths["candidate_score_rows"], panel_rows, [])
    _write_csv(paths["label_audit"], panel_rows, [])
    paths["candidate_scores_input_schema"].write_text(json.dumps({"selected_code_lists": "test_or_replay_adapter_only_not_policy_action"}), encoding="utf-8")
    paths["feature_contract"].write_text(json.dumps({"feature_columns": ["feature_a", "candidate_score_causal_momentum"]}), encoding="utf-8")
    paths["split_summary"].write_text(json.dumps({"train": 2, "val": 2, "test": 2}), encoding="utf-8")
    paths["source_hashes"].write_text(json.dumps({"daily_db_fingerprint": "unit-db", "universe_manifest_sha": "unit-universe"}), encoding="utf-8")
    artifact_hashes = {key: _sha_file(path) for key, path in paths.items()}
    manifest_sha = "unit-dataset-manifest-sha"
    manifest = {
        "schema_version": 1,
        "lineage_schema_version": 1,
        "run_id": run_id,
        "manifest_sha": manifest_sha,
        "artifact_kind": "daily_close_slot_dataset",
        "artifact_dir": str(out),
        "status": "WATCH_RESEARCH_ONLY",
        "readiness_status": "WATCH_RESEARCH_ONLY",
        "promotion_allowed": False,
        "model_build_allowed": False,
        "paper_forward_allowed": False,
        "live_broker_order_allowed": False,
        "profitability_claim_allowed": False,
        "go_summary_allowed": False,
        "round_trip_cost_bp": 23,
        "cost_sensitivity_bp": [0, 23, 46],
        "split_policy": {
            "method": "chronological_train_val_test_with_purge_embargo",
            "purge_days": 1,
            "embargo_days": 1,
        },
        "slot_count": 10,
        "total_capital_krw": 1_000_000,
        "price_basis": "unknown",
        "price_basis_status": "UNKNOWN_CONFIRMED",
        "decision_grade_return_status": "BLOCKED_UNTIL_PRICE_BASIS_VERIFIED",
        "upstream_gate_blockers": ["D0_PRICE_BASIS_NOT_VERIFIED"],
        "fill_mode": "close_to_next_close_research_label",
        "execution_realism": "non_executable_upper_bound_without_preclose_features",
        "feature_columns": ["feature_a", "candidate_score_causal_momentum"],
        "artifacts": {key: str(path) for key, path in paths.items()},
        "artifact_hashes": artifact_hashes,
        "row_counts": {
            "close_slot_panel_rows": len(panel_rows),
            "candidate_score_rows": len(panel_rows),
            "label_audit_rows": len(panel_rows),
        },
        "source_run_ids": {"daily_db_fingerprint": "unit-db", "universe_manifest_sha": "unit-universe"},
        "lineage_validation_status": "PASS",
        "lineage_validation_errors": [],
    }
    manifest_path = out / "close_slot_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"root": root, "run_id": run_id, "manifest_sha": manifest_sha, "manifest_path": manifest_path, "panel_rows": panel_rows}


def _base_config(tmp_path: Path, dataset: dict, *, run_id: str = "train_unit") -> CloseSlotTrainConfig:
    return CloseSlotTrainConfig(
        dataset_run_id=dataset["run_id"],
        dataset_manifest_sha=dataset["manifest_sha"],
        dataset_artifact_root=dataset["root"],
        output_root=tmp_path / "train_root",
        run_id=run_id,
        total_capital_krw=1_000_000,
        seed=7,
        min_fit_dates=1,
        replay_window_dates=1,
        freeze_cadence_dates=1,
    )


def test_close_slot_events_schema(tmp_path: Path):
    dataset = _write_dataset_run(tmp_path / "dataset_root")
    events_path = tmp_path / "live" / LIVE_EVENTS_FILE_NAME
    writer = RlLiveEventWriter(events_path, run_id="train_unit")
    config = _base_config(tmp_path, dataset)

    run_close_slot_training(config, event_writer=writer)

    rows, _truncated = read_live_events(events_path, limit=500, tail=False)
    assert rows, "expected event_writer to emit at least one live event"
    for row in rows:
        assert row["schema_version"] == "stom_rl_live_event.v1"
        # rl_events.py source default is 'sb3_smoke' -- the trainer must set it explicitly.
        assert row["source"] == "daily_close_slot_train"
        assert row["algorithm"] == "linear_score_and_pick_train_only"
        assert row["info"]["reward_kind"] == "return_fraction"
        assert row["info"]["reward_unit"] == "fraction"
        assert row["info"]["equity_kind"] == "cumulative_pnl"
        assert row["info"]["equity_unit"] == "krw"
        assert row["info"]["action_recorded"] is False


def test_rule_baseline_never_labeled_rl(tmp_path: Path):
    dataset = _write_dataset_run(tmp_path / "dataset_root")
    events_path = tmp_path / "live" / LIVE_EVENTS_FILE_NAME
    writer = RlLiveEventWriter(events_path, run_id="train_unit")
    config = _base_config(tmp_path, dataset)

    result = run_close_slot_training(config, event_writer=writer)

    rows, _truncated = read_live_events(events_path, limit=500, tail=False)
    assert rows
    expected_algorithm = "linear_score_and_pick_train_only"
    mislabeled = [row for row in rows if row.get("algorithm") != expected_algorithm]
    assert mislabeled == [], f"non-bandit events leaked into the live stream: {mislabeled}"

    # The walk-forward window event count plus the primary per-date event
    # count must exactly account for every emitted row -- proving no baseline
    # (no_trade/shuffle/momentum/D3-frozen/forced-top10-diagnostic) call ever
    # reached the writer.
    manifest = result["manifest"]
    walk_forward_windows = json.loads(Path(result["paths"]["walk_forward_windows"]).read_text(encoding="utf-8"))
    refit_window_count = sum(
        1 for window in walk_forward_windows["windows"] if str(window["window_id"]).startswith("train_replay_refit_")
    )
    primary_eval_dates = {row["policy"]: row for row in manifest["summary"]}["linear_score_and_pick_train_only"]["date_count"]
    assert len(rows) == refit_window_count + primary_eval_dates


def test_walk_forward_windows_carry_rewards(tmp_path: Path):
    dataset = _write_dataset_run(tmp_path / "dataset_root")
    config = _base_config(tmp_path, dataset)

    result = run_close_slot_training(config)

    walk_forward_windows = json.loads(Path(result["paths"]["walk_forward_windows"]).read_text(encoding="utf-8"))
    refit_windows = [
        window for window in walk_forward_windows["windows"] if str(window["window_id"]).startswith("train_replay_refit_")
    ]
    assert refit_windows, "expected at least one train-replay-refit window"
    for window in refit_windows:
        assert "replay_mean_reward_base_23bp" in window
        assert "replay_cumulative_reward" in window
        assert "mean_selected_count" in window
        assert "date_count" in window
        assert isinstance(window["replay_mean_reward_base_23bp"], (int, float))
        assert isinstance(window["date_count"], int)

    replay_episode_ledgers = json.loads(Path(result["paths"]["replay_episode_ledgers"]).read_text(encoding="utf-8"))
    assert replay_episode_ledgers["episodes"], "expected persisted per-round episode ledgers"
    for episode in replay_episode_ledgers["episodes"]:
        assert "reward" in episode
        assert "net_pnl_krw" in episode
        assert "cost_krw" in episode
        assert "filled_slots" in episode


def test_daily_runs_discoverable(tmp_path: Path, monkeypatch):
    from webui import rl_dashboard

    root = tmp_path / "rl_runs"
    root.mkdir()

    portfolio_run = root / "daily_ohlcv_portfolio_run"
    portfolio_run.mkdir()
    (portfolio_run / "rl_manifest.json").write_text(json.dumps({"artifact_kind": "daily_ohlcv_portfolio"}), encoding="utf-8")

    close_slot_run = root / "daily_close_slot_train_run"
    close_slot_run.mkdir()
    (close_slot_run / "close_slot_train_manifest.json").write_text(json.dumps({"artifact_kind": "daily_close_slot_train"}), encoding="utf-8")

    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [root])

    runs = rl_dashboard.list_rl_runs(limit=10)
    by_name = {run["name"]: run for run in runs}

    assert by_name["daily_ohlcv_portfolio_run"]["artifact_type"] == "daily_ohlcv_portfolio"
    assert by_name["daily_close_slot_train_run"]["artifact_type"] == "daily_close_slot_train"


def test_writer_none_byte_identical(tmp_path: Path):
    dataset = _write_dataset_run(tmp_path / "dataset_root")
    config = _base_config(tmp_path, dataset)

    result = run_close_slot_training(config, event_writer=None)
    manifest = result["manifest"]

    # Same key assertions as the pre-existing WP-R1 regression test -- the
    # hoisted run_id/output_dir resolution and the optional event_writer must
    # not change the default (event_writer=None) artifact contents.
    assert manifest["schema_version"] == 2
    assert manifest["round_trip_cost_bp"] == 23
    assert manifest["train_only_fit"] is True
    assert manifest["validation_test_no_retune"] is True
    assert manifest["fit_summary"]["train_rows"] == 4
    assert manifest["fit_summary"]["oos_rows_used_for_fit"] == 0
    assert set(manifest["required_baselines"]) == {
        "no_trade_control",
        "deterministic_shuffle_top10_control",
        "momentum_top10_score_and_pick",
        "linear_score_and_pick_train_only",
    }
    summaries = {row["policy"]: row for row in manifest["summary"]}
    assert summaries["no_trade_control"]["filled_slots"] == 0
    assert summaries["linear_score_and_pick_train_only"]["filled_slots"] > 0

    # Default training constructs the standard CLI live-events writer.
    output_dir = Path(result["manifest"]["artifact_dir"])
    default_events = output_dir / LIVE_EVENTS_FILE_NAME
    assert default_events.exists()
    rows, _truncated = read_live_events(default_events, limit=500, tail=False)
    assert rows

    # Calling again without passing event_writer at all (relying on the
    # default) must be accepted identically.
    config2 = _base_config(tmp_path, dataset, run_id="train_unit_no_kw")
    result2 = run_close_slot_training(config2)
    assert result2["manifest"]["schema_version"] == manifest["schema_version"]
    assert result2["manifest"]["summary"] == manifest["summary"]
