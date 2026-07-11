import copy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from webui.app import app as flask_app  # noqa: E402
from tests.test_daily_ohlcv_dashboard_api import _prepare_close_slot_dashboard_run  # noqa: E402


def test_latest_selection_date_is_newest_not_oldest_sample(tmp_path, monkeypatch):
    _prepare_close_slot_dashboard_run(tmp_path, monkeypatch, with_d3=True)
    client = flask_app.test_client()

    # limit=1 forces the ascending sample truncation to surface the OLDEST date only.
    response = client.get("/api/daily-ohlcv/close-slot/selection?run=gate_for_dashboard&limit=1")
    payload = response.get_json()

    assert payload["selection_rows"][0]["date"] == "2024-04-01"
    assert payload["selection_rows_label"] == "sample_only_not_authoritative_latest"
    assert payload["latest_selection"]["date"] == "2024-04-04"
    assert payload["latest_selection"]["date"] != payload["selection_rows"][0]["date"]


def test_latest_selection_uses_test_split_and_primary_cost_scenario(tmp_path, monkeypatch):
    _prepare_close_slot_dashboard_run(tmp_path, monkeypatch, with_d3=True)
    client = flask_app.test_client()
    import webui.daily_ohlcv_dashboard as daily_dashboard

    response = client.get("/api/daily-ohlcv/close-slot/selection?run=gate_for_dashboard&limit=5")
    payload = response.get_json()
    selection = payload["latest_selection"]

    assert selection["policy"] == daily_dashboard.POLICY_CONTEXTUAL_BANDIT
    assert selection["split"] == "test"
    assert selection["cost_scenario_id"] == daily_dashboard.PRIMARY_COST_SCENARIO_ID
    assert selection["date"] == "2024-04-04"
    assert selection["source_run_id"] == payload["run_id"]
    assert selection["artifact_age_seconds"] >= 0
    assert selection["missing_test_split_evidence"] is False


def test_latest_selection_primary_is_test_secondary_is_train_val(tmp_path, monkeypatch):
    _prepare_close_slot_dashboard_run(tmp_path, monkeypatch, with_d3=True)
    client = flask_app.test_client()

    response = client.get("/api/daily-ohlcv/close-slot/selection?run=gate_for_dashboard&limit=5")
    payload = response.get_json()
    selection = payload["latest_selection"]

    assert selection["label"] == "primary_oos_test_result"
    secondary = selection["secondary"]
    assert secondary["train"]["split"] == "train"
    assert secondary["train"]["date"] == "2024-04-02"
    assert secondary["train"]["label"] == "secondary_in_sample_train_result"
    assert secondary["val"]["split"] == "val"
    assert secondary["val"]["date"] == "2024-04-03"
    assert secondary["val"]["label"] == "secondary_validation_result"
    assert secondary["val_plus_test"]["split"] == "val+test"
    assert secondary["val_plus_test"]["date"] == "2024-04-04"
    assert secondary["val_plus_test"]["label"] == "secondary_val_plus_test_combined_result"


def test_data_recency_labels_stored_replay_and_never_falsely_claims_today(tmp_path, monkeypatch):
    _prepare_close_slot_dashboard_run(tmp_path, monkeypatch, with_d3=True)
    client = flask_app.test_client()

    latest = client.get("/api/daily-ohlcv/close-slot/latest?run=gate_for_dashboard&limit=5").get_json()
    recency = latest["data_recency"]

    assert recency["latest_data_date"] == "2024-04-04"
    assert recency["configured_research_date"] is None
    assert recency["is_today"] is False
    assert recency["label"] == "stored replay 2024-04-04"

    selection = client.get("/api/daily-ohlcv/close-slot/selection?run=gate_for_dashboard&limit=5").get_json()
    assert selection["data_recency"] == recency


def test_data_recency_would_label_today_only_when_dates_match(tmp_path, monkeypatch):
    import webui.daily_ohlcv_dashboard as daily_dashboard

    date_ledgers = {"policy_a": [{"date": "2024-04-04"}, {"date": "2024-04-01"}]}
    recency_mismatch = daily_dashboard._close_slot_data_recency(date_ledgers)
    assert recency_mismatch["is_today"] is False
    assert recency_mismatch["label"] == "stored replay 2024-04-04"


def test_close_slot_blockers_full_list_is_dynamic_not_hardcoded(tmp_path, monkeypatch):
    import webui.daily_ohlcv_dashboard as daily_dashboard

    _prepare_close_slot_dashboard_run(tmp_path, monkeypatch, with_d3=True)
    context = daily_dashboard._load_close_slot_context(run="gate_for_dashboard", sample_limit=5)
    assert "payload" not in context

    context_one = copy.deepcopy(context)
    context_one["gate_report"]["upstream_gate_blockers"] = ["REASON_ONE"]
    payload_one = daily_dashboard._close_slot_payload_from_context(context_one, sample_limit=5)

    context_three = copy.deepcopy(context)
    context_three["gate_report"]["upstream_gate_blockers"] = ["REASON_ONE", "REASON_TWO", "REASON_THREE"]
    payload_three = daily_dashboard._close_slot_payload_from_context(context_three, sample_limit=5)

    assert payload_one["close_slot_blockers"] == ["D0_PRICE_BASIS_NOT_VERIFIED", "REASON_ONE"]
    assert payload_three["close_slot_blockers"] == [
        "D0_PRICE_BASIS_NOT_VERIFIED",
        "REASON_ONE",
        "REASON_TWO",
        "REASON_THREE",
    ]
    assert len(payload_three["close_slot_blockers"]) == 4
    assert len(payload_one["close_slot_blockers"]) != len(payload_three["close_slot_blockers"])


def test_selection_accepts_linear_policy_alias(tmp_path, monkeypatch):
    import webui.daily_ohlcv_dashboard as daily_dashboard

    _prepare_close_slot_dashboard_run(tmp_path, monkeypatch, with_d3=True)
    client = flask_app.test_client()

    response = client.get("/api/daily-ohlcv/close-slot/selection?run=gate_for_dashboard&policy=linear&limit=5")
    payload = response.get_json()

    assert payload["policy"] == daily_dashboard.POLICY_CONTEXTUAL_BANDIT
    assert "linear" in payload["policy"]
    assert payload["latest_selection"]["policy"] == daily_dashboard.POLICY_CONTEXTUAL_BANDIT


def test_backward_compatible_payload_keys_still_present(tmp_path, monkeypatch):
    _prepare_close_slot_dashboard_run(tmp_path, monkeypatch, with_d3=True)
    client = flask_app.test_client()

    selection = client.get("/api/daily-ohlcv/close-slot/selection?run=gate_for_dashboard&limit=5").get_json()
    for key in (
        "surface",
        "status",
        "readiness_status",
        "run_id",
        "source_run_ids",
        "labels",
        "policy",
        "slot_count",
        "round_trip_cost_bp",
        "selection_rows",
        "policy_score_sample",
        "threshold_selection",
        "selected_hold_summary",
        "cost_scenarios",
        "cost_components",
        "false_locks",
        "no_claim_labels",
        "read_only",
        "promotion_allowed",
        "model_build_allowed",
        "paper_forward_allowed",
        "live_broker_order_allowed",
        "profitability_claim_allowed",
        "go_summary_allowed",
        "guardrail",
    ):
        assert key in selection, f"missing backward-compatible key: {key}"

    latest = client.get("/api/daily-ohlcv/close-slot/latest?run=gate_for_dashboard&limit=5").get_json()
    for key in (
        "surface",
        "status",
        "readiness_status",
        "run_id",
        "current_required_blockers",
        "upstream_gate_blockers",
        "fit_summary",
        "cost_scenarios",
        "samples",
    ):
        assert key in latest, f"missing backward-compatible key: {key}"
    assert latest["fit_summary"].get("chosen_is_no_trade_sentinel") is not None
    assert latest["chosen_is_no_trade_sentinel"] == latest["fit_summary"].get("chosen_is_no_trade_sentinel")
