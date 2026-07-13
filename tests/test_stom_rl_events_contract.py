"""Contract tests for the additive live-event metric/action/freshness contract.

Covers: (a) rl_events.py public API (schema version stability, archived v1
fixture back-compat, action availability, overlay compatibility, run-status
derivation with LIVE fail-closed semantics) and (b) end-to-end proof that the
wired trainer emission points (daily_rl_train.py, daily_close_slot_train.py)
truthfully populate ``info`` with the declared metric/action metadata.
"""

import csv
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stom_rl.rl_events import (  # noqa: E402
    ACTION_NOT_RECORDED,
    ACTION_RECORDED,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_IDLE,
    RUN_STATUS_MISSING,
    RUN_STATUS_REPLAY,
    RUN_STATUS_RUNNING,
    RUN_STATUS_STALE,
    RlLiveEventWriter,
    SCHEMA_VERSION,
    action_availability,
    default_run_metric_metadata,
    derive_run_status,
    is_live_status,
    metrics_overlay_compatible,
    resolve_event_metric_metadata,
)

from stom_rl.daily_rl_train import run_daily_rl  # noqa: E402
from stom_rl.daily_close_slot_train import CloseSlotTrainConfig, run_close_slot_training  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helpers shared with existing gate tests (kept minimal/local so this
# file is self-contained rather than importing test-module internals).
# ---------------------------------------------------------------------------


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _sha_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        digest.update(handle.read())
    return digest.hexdigest()


def _create_prediction_run(root: Path) -> Path:
    run_dir = root / "prediction_unit"
    run_dir.mkdir(parents=True)
    manifest = {
        "schema_version": 1,
        "manifest_sha": "prediction-sha-unit",
        "price_basis": "unknown",
        "price_basis_evidence": "unit unknown",
        "universe_review_status": "WATCH_REQUIRES_OFFICIAL_OR_MANUAL_REVIEW",
        "verdict": {"status": "WATCH", "go_summary_allowed": False},
    }
    verdict = {
        "schema_version": 1,
        "status": "WATCH",
        "go_summary_allowed": False,
        "reasons": ["UNIT_TEST"],
    }
    baseline_metrics = {
        "metrics": [
            {"strategy": "no_trade_cash", "total_net_return": 0.0, "max_drawdown": 0.0, "mean_turnover": 0.0},
            {"strategy": "equal_weight_topk_momentum", "total_net_return": 0.01, "max_drawdown": -0.01, "mean_turnover": 0.5},
            {"strategy": "supervised_linear_ranker", "total_net_return": 0.02, "max_drawdown": -0.02, "mean_turnover": 0.4},
        ]
    }
    rows = []
    split_by_index = {0: "train", 1: "train", 2: "train", 3: "val", 4: "val", 5: "test", 6: "test"}
    for idx in range(7):
        date = f"2024-01-{idx + 1:02d}"
        split = split_by_index[idx]
        for offset, code in enumerate(["000020", "000030", "000040"]):
            score = 0.5 - offset * 0.1 + idx * 0.01
            future = (0.01 if offset == 0 else -0.002) + idx * 0.0005
            rows.append(
                {
                    "date": date,
                    "table": f"A{code}",
                    "code": code,
                    "split": split,
                    "future_return_1d": future,
                    "score_supervised_linear_ranker": score,
                    "score_equal_weight_topk_momentum": score,
                }
            )
    (run_dir / "prediction_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "baseline_metrics.json").write_text(json.dumps(baseline_metrics), encoding="utf-8")
    (run_dir / "verdict.json").write_text(json.dumps(verdict), encoding="utf-8")
    _write_csv(run_dir / "predictions.csv", rows)
    return run_dir


def _write_close_slot_dataset_run(root: Path, run_id: str = "dataset_unit") -> dict:
    out = root / run_id
    out.mkdir(parents=True)
    panel_rows = [
        {
            "date": "2024-04-01", "exit_date": "2024-04-02", "table": "A000001", "code": "000001",
            "split": "train", "entry_close": 1000, "next_close": 1100, "future_return_1d": 0.10,
            "eligible_for_selection": True, "candidate_score_causal_momentum": 0.5, "feature_a": 1.0,
        },
        {
            "date": "2024-04-01", "exit_date": "2024-04-02", "table": "A000002", "code": "000002",
            "split": "train", "entry_close": 1000, "next_close": 900, "future_return_1d": -0.10,
            "eligible_for_selection": True, "candidate_score_causal_momentum": -0.5, "feature_a": -1.0,
        },
        {
            "date": "2024-04-02", "exit_date": "2024-04-03", "table": "A000001", "code": "000001",
            "split": "train", "entry_close": 1000, "next_close": 1020, "future_return_1d": 0.02,
            "eligible_for_selection": True, "candidate_score_causal_momentum": 0.9, "feature_a": 2.0,
        },
        {
            "date": "2024-04-02", "exit_date": "2024-04-03", "table": "A000002", "code": "000002",
            "split": "train", "entry_close": 1000, "next_close": 980, "future_return_1d": -0.02,
            "eligible_for_selection": True, "candidate_score_causal_momentum": -0.9, "feature_a": -2.0,
        },
        {
            "date": "2024-04-03", "exit_date": "2024-04-04", "table": "A000001", "code": "000001",
            "split": "val", "entry_close": 1000, "next_close": 1030, "future_return_1d": 0.03,
            "eligible_for_selection": True, "candidate_score_causal_momentum": 0.1, "feature_a": 0.25,
        },
        {
            "date": "2024-04-03", "exit_date": "2024-04-04", "table": "A000002", "code": "000002",
            "split": "val", "entry_close": 1000, "next_close": 970, "future_return_1d": -0.03,
            "eligible_for_selection": True, "candidate_score_causal_momentum": -0.1, "feature_a": -0.25,
        },
        {
            "date": "2024-04-04", "exit_date": "2024-04-05", "table": "A000001", "code": "000001",
            "split": "test", "entry_close": 1000, "next_close": 1040, "future_return_1d": 0.04,
            "eligible_for_selection": True, "candidate_score_causal_momentum": 0.05, "feature_a": 0.15,
        },
        {
            "date": "2024-04-04", "exit_date": "2024-04-05", "table": "A000002", "code": "000002",
            "split": "test", "entry_close": 1000, "next_close": 960, "future_return_1d": -0.04,
            "eligible_for_selection": True, "candidate_score_causal_momentum": -0.05, "feature_a": -0.15,
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
    _write_csv(paths["close_slot_panel"], panel_rows)
    _write_csv(paths["candidate_score_rows"], panel_rows)
    _write_csv(paths["label_audit"], panel_rows)
    paths["candidate_scores_input_schema"].write_text(
        json.dumps({"selected_code_lists": "test_or_replay_adapter_only_not_policy_action"}), encoding="utf-8"
    )
    paths["feature_contract"].write_text(
        json.dumps({"feature_columns": ["feature_a", "candidate_score_causal_momentum"]}), encoding="utf-8"
    )
    paths["split_summary"].write_text(json.dumps({"train": 2, "val": 2, "test": 2}), encoding="utf-8")
    paths["source_hashes"].write_text(
        json.dumps({"daily_db_fingerprint": "unit-db", "universe_manifest_sha": "unit-universe"}), encoding="utf-8"
    )
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
        "split_policy": {"method": "chronological_train_val_test_with_purge_embargo", "purge_days": 1, "embargo_days": 1},
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
        "artifact_hashes": {key: _sha_file(path) for key, path in paths.items()},
        "row_counts": {"close_slot_panel_rows": len(panel_rows), "candidate_score_rows": len(panel_rows), "label_audit_rows": len(panel_rows)},
        "source_run_ids": {"daily_db_fingerprint": "unit-db", "universe_manifest_sha": "unit-universe"},
        "lineage_validation_status": "PASS",
        "lineage_validation_errors": [],
    }
    manifest_path = out / "close_slot_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"root": root, "run_id": run_id, "manifest_sha": manifest_sha}


# ---------------------------------------------------------------------------
# Schema version stability + archived v1 fixture back-compat.
# ---------------------------------------------------------------------------


def test_schema_version_unchanged():
    assert SCHEMA_VERSION == "stom_rl_live_event.v1"


def test_archived_v1_event_without_info_resolves_all_none_and_not_recorded():
    archived_event = {
        "run_id": "archived-run",
        "algorithm": "tabular_q",
        "phase": "train",
        "global_step": 1,
        "action": None,
        "reward": 0.1,
        "equity": 1.01,
        "source": "sb3_smoke",
        "schema_version": SCHEMA_VERSION,
    }
    meta = resolve_event_metric_metadata(archived_event)
    assert meta == default_run_metric_metadata()
    assert all(value is None for value in meta.values())
    assert action_availability(archived_event) == ACTION_NOT_RECORDED


def test_run_defaults_fill_but_per_event_info_wins():
    run_defaults = {
        "reward_kind": "raw_reward",
        "reward_unit": "score",
        "equity_kind": "normalized_nav",
        "equity_unit": "normalized",
        "action_recorded": None,
    }
    event_with_override = {
        "info": {"equity_kind": "krw_nav", "equity_unit": "krw"},
    }
    meta = resolve_event_metric_metadata(event_with_override, run_defaults=run_defaults)
    assert meta["reward_kind"] == "raw_reward"
    assert meta["reward_unit"] == "score"
    assert meta["equity_kind"] == "krw_nav"
    assert meta["equity_unit"] == "krw"
    assert meta["action_recorded"] is None

    event_no_info = {"info": {}}
    meta_defaults_only = resolve_event_metric_metadata(event_no_info, run_defaults=run_defaults)
    assert meta_defaults_only["equity_kind"] == "normalized_nav"


# ---------------------------------------------------------------------------
# action_availability
# ---------------------------------------------------------------------------


def test_action_availability_null_action_no_info_is_not_recorded():
    assert action_availability({"action": None}) == ACTION_NOT_RECORDED
    assert action_availability({}) == ACTION_NOT_RECORDED


def test_action_availability_info_false_overrides_present_action():
    assert action_availability({"action": 1, "info": {"action_recorded": False}}) == ACTION_NOT_RECORDED


def test_action_availability_info_true_is_recorded():
    assert action_availability({"action": None, "info": {"action_recorded": True}}) == ACTION_RECORDED


def test_action_availability_real_action_no_info_is_recorded():
    assert action_availability({"action": 2}) == ACTION_RECORDED


# ---------------------------------------------------------------------------
# metrics_overlay_compatible
# ---------------------------------------------------------------------------


def test_overlay_compatible_same_kind_and_unit():
    a = {"equity_kind": "normalized_nav", "equity_unit": "normalized"}
    b = {"equity_kind": "normalized_nav", "equity_unit": "normalized"}
    assert metrics_overlay_compatible(a, b, metric="equity") is True


def test_overlay_incompatible_normalized_nav_vs_krw_nav():
    a = {"equity_kind": "normalized_nav", "equity_unit": "normalized"}
    b = {"equity_kind": "krw_nav", "equity_unit": "krw"}
    assert metrics_overlay_compatible(a, b, metric="equity") is False


def test_overlay_incompatible_missing_or_unknown_kind():
    a = {"equity_kind": None, "equity_unit": "unknown"}
    b = {"equity_kind": "krw_nav", "equity_unit": "krw"}
    assert metrics_overlay_compatible(a, b, metric="equity") is False
    assert metrics_overlay_compatible({}, {}, metric="equity") is False


def test_overlay_compatible_identical_explicit_normalization():
    a = {"equity_kind": "raw_equity", "equity_unit": "unknown", "normalization": "custom_scale_v1"}
    b = {"equity_kind": "cumulative_pnl", "equity_unit": "krw", "normalization": "custom_scale_v1"}
    assert metrics_overlay_compatible(a, b, metric="equity") is True


# ---------------------------------------------------------------------------
# derive_run_status: all six statuses + LIVE fail-closed.
# ---------------------------------------------------------------------------


def test_derive_run_status_running_requires_declared_advancing_and_within_window():
    status = derive_run_status(
        event_file_exists=True,
        event_count=5,
        declared_running=True,
        last_step=10,
        prev_step=9,
        seconds_since_last_advance=3.0,
        poll_interval_seconds=5.0,
    )
    assert status == RUN_STATUS_RUNNING
    assert is_live_status(status) is True


def test_derive_run_status_not_advancing_is_stale():
    status = derive_run_status(
        event_file_exists=True,
        event_count=5,
        declared_running=True,
        last_step=10,
        prev_step=10,
        seconds_since_last_advance=1.0,
        poll_interval_seconds=5.0,
    )
    assert status == RUN_STATUS_STALE
    assert is_live_status(status) is False


def test_derive_run_status_advance_older_than_two_intervals_is_stale():
    status = derive_run_status(
        event_file_exists=True,
        event_count=5,
        declared_running=True,
        last_step=10,
        prev_step=9,
        seconds_since_last_advance=11.0,
        poll_interval_seconds=5.0,
    )
    assert status == RUN_STATUS_STALE
    assert is_live_status(status) is False


def test_derive_run_status_declared_false_is_completed():
    status = derive_run_status(event_file_exists=True, event_count=5, declared_running=False)
    assert status == RUN_STATUS_COMPLETED
    assert is_live_status(status) is False


def test_derive_run_status_declared_none_with_events_is_stale_never_running():
    status = derive_run_status(
        event_file_exists=True,
        event_count=5,
        declared_running=None,
        last_step=10,
        prev_step=9,
        seconds_since_last_advance=1.0,
        poll_interval_seconds=5.0,
    )
    assert status == RUN_STATUS_STALE
    assert is_live_status(status) is False


def test_derive_run_status_no_file_is_missing():
    status = derive_run_status(event_file_exists=False, event_count=0, declared_running=True)
    assert status == RUN_STATUS_MISSING
    assert is_live_status(status) is False


def test_derive_run_status_file_zero_events_is_idle():
    status = derive_run_status(event_file_exists=True, event_count=0, declared_running=True)
    assert status == RUN_STATUS_IDLE
    assert is_live_status(status) is False


def test_derive_run_status_replay_flag_wins():
    status = derive_run_status(event_file_exists=True, event_count=5, declared_running=True, is_replay=True)
    assert status == RUN_STATUS_REPLAY
    assert is_live_status(status) is False


def test_is_live_status_true_only_for_running():
    all_statuses = {
        RUN_STATUS_RUNNING,
        RUN_STATUS_COMPLETED,
        RUN_STATUS_STALE,
        RUN_STATUS_REPLAY,
        RUN_STATUS_IDLE,
        RUN_STATUS_MISSING,
    }
    live = {status for status in all_statuses if is_live_status(status)}
    assert live == {RUN_STATUS_RUNNING}


# ---------------------------------------------------------------------------
# Trainer-emission proof: real write path through the wired trainers.
# ---------------------------------------------------------------------------


def test_daily_rl_train_emits_declared_metric_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import stom_rl.daily_rl_train as rl_train

    prediction_root = tmp_path / "webui" / "rl_runs" / "daily_ohlcv_prediction"
    portfolio_root = tmp_path / "webui" / "rl_runs" / "daily_ohlcv_portfolio"
    run_dir = _create_prediction_run(prediction_root)
    monkeypatch.setattr(rl_train, "DEFAULT_PREDICTION_ROOT", prediction_root)
    monkeypatch.setattr(rl_train, "DEFAULT_PORTFOLIO_ROOT", portfolio_root)

    events_path = tmp_path / "daily_rl_events.jsonl"
    writer = RlLiveEventWriter(events_path, run_id="events-contract-unit")
    writer.reset()

    run_daily_rl(prediction_run_dir=run_dir, episodes=2, candidate_limit=2, max_positions=2, seed=3, event_writer=writer)

    lines = events_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines, "expected at least one emitted event"
    events = [json.loads(line) for line in lines]

    train_events = [event for event in events if event["phase"] == "train"]
    eval_events = [event for event in events if event["phase"].startswith("eval_")]
    assert train_events and eval_events

    for event in train_events + eval_events:
        assert event["algorithm"] == "tabular_q"
        info = event["info"]
        assert info["reward_kind"] == "raw_reward"
        assert info["reward_unit"] == "score"
        assert info["equity_kind"] == "normalized_nav"
        assert info["equity_unit"] == "normalized"
        assert info["action_recorded"] is False
        # No discrete action was written -> availability must be NOT_RECORDED
        # even though action_recorded is explicitly declared False.
        assert action_availability(event) == ACTION_NOT_RECORDED
        meta = resolve_event_metric_metadata(event)
        assert meta["equity_kind"] == "normalized_nav"


def test_daily_close_slot_train_emits_declared_metric_metadata_and_keeps_threshold_text(tmp_path: Path):
    dataset = _write_close_slot_dataset_run(tmp_path / "dataset_root")
    config = CloseSlotTrainConfig(
        dataset_run_id=dataset["run_id"],
        dataset_manifest_sha=dataset["manifest_sha"],
        dataset_artifact_root=dataset["root"],
        output_root=tmp_path / "train_root",
        run_id="train_unit",
        total_capital_krw=1_000_000,
        seed=7,
        min_fit_dates=1,
        replay_window_dates=1,
        freeze_cadence_dates=1,
    )

    events_path = tmp_path / "close_slot_events.jsonl"
    writer = RlLiveEventWriter(events_path, run_id="events-contract-unit")
    writer.reset()

    run_close_slot_training(config, event_writer=writer)

    lines = events_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines, "expected at least one emitted event"
    events = [json.loads(line) for line in lines]

    primary_eval_events = [event for event in events if event["phase"] == "primary_eval"]
    assert primary_eval_events, "expected primary_eval events from the linear score-and-pick eval loop"

    for event in primary_eval_events:
        assert event["algorithm"] == "linear_score_and_pick_train_only"
        info = event["info"]
        # threshold_text must survive the additive extension, not be dropped.
        assert "threshold_text" in info
        assert info["reward_kind"] == "return_fraction"
        assert info["reward_unit"] == "fraction"
        assert info["equity_kind"] == "cumulative_pnl"
        assert info["equity_unit"] == "krw"
        assert info["action_recorded"] is False
        assert action_availability(event) == ACTION_NOT_RECORDED
