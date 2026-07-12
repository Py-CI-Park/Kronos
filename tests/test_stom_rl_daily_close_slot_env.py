import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stom_rl.daily_close_slot_env import (  # noqa: E402
    COST_SCENARIO_BASE_23BP,
    COST_SCENARIO_STRESS_46BP,
    COST_SCENARIO_ZERO_CONTROL_0BP,
    POLICY_ACTION_LABEL,
    REPLAY_ADAPTER_LABEL,
    DailyCloseSlotEnv,
    evaluate_close_slot_cost_sensitivity,
    evaluate_close_slot_day,
    normalize_close_slot_action,
)


def _candidate_rows():
    return [
        {
            "date": "2024-03-04",
            "table": "A000010",
            "code": "000010",
            "score": 1.0,
            "entry_close": 1000,
            "next_close": 1100,
            "future_return_1d": 0.10,
            "eligible_for_selection": True,
            "split": "train",
        },
        {
            "date": "2024-03-04",
            "table": "A000009",
            "code": "000009",
            "score": 1.0,
            "entry_close": 1000,
            "next_close": 900,
            "future_return_1d": -0.10,
            "eligible_for_selection": True,
            "split": "train",
        },
        {
            "date": "2024-03-04",
            "table": "A000020",
            "code": "000020",
            "score": 0.8,
            "entry_close": 2000,
            "next_close": 2200,
            "future_return_1d": 0.10,
            "eligible_for_selection": True,
            "split": "train",
        },
        {
            "date": "2024-03-04",
            "table": "A000020_DUP",
            "code": "000020",
            "score": 0.7,
            "entry_close": 2000,
            "next_close": 2100,
            "future_return_1d": 0.05,
            "eligible_for_selection": True,
            "split": "train",
        },
        {
            "date": "2024-03-04",
            "table": "A000030",
            "code": "000030",
            "score": "bad",
            "entry_close": 1000,
            "next_close": 1100,
            "eligible_for_selection": True,
            "split": "train",
        },
        {
            "date": "2024-03-04",
            "table": "A000040",
            "code": "000040",
            "score": 0.6,
            "entry_close": 1000,
            "next_close": None,
            "eligible_for_selection": True,
            "split": "train",
        },
        {
            "date": "2024-03-04",
            "table": "A000050",
            "code": "000050",
            "score": 0.5,
            "entry_close": 1000,
            "next_close": 1100,
            "eligible_for_selection": False,
            "blocked_reason": "D0_D1_BLOCKED",
            "split": "train",
        },
    ]


def test_score_and_pick_normalization_tie_breaks_and_diagnostics():
    normalized = normalize_close_slot_action(_candidate_rows(), date="2024-03-04")

    assert normalized["action_label"] == POLICY_ACTION_LABEL
    assert normalized["selected_code_lists"] == REPLAY_ADAPTER_LABEL
    assert [slot["code"] for slot in normalized["selection_slots"][:3]] == ["000009", "000010", "000020"]
    assert normalized["selection_slots"][3]["status"] == "empty"
    assert normalized["selection_slots"][3]["reason"] == "EMPTY_SLOT"
    assert normalized["selection_slots"][3]["slot_state"] == "cash_hold"

    diagnostics = normalized["diagnostics"]
    assert {row["reason"] for row in diagnostics["invalid_rows"]} == {
        "INVALID_SCORE",
        "MISSING_NEXT_CLOSE",
        "D0_D1_BLOCKED",
    }
    assert diagnostics["duplicate_candidate_rows"] == [
        {
            "code": "000020",
            "table": "A000020_DUP",
            "candidate_index": 3,
            "reason": "DUPLICATE_CANDIDATE_CODE_EXCLUDED",
        }
    ]


def test_selected_code_replay_adapter_is_labeled_and_never_policy_action():
    normalized = normalize_close_slot_action(
        _candidate_rows(),
        date="2024-03-04",
        selected_codes=["000010", "000010", "000040", "999999"],
    )

    assert normalized["action_label"] == REPLAY_ADAPTER_LABEL
    assert normalized["diagnostics"]["selected_code_adapter_used"] is True
    assert normalized["diagnostics"]["selected_code_adapter_policy_allowed"] is False
    assert normalized["selection_slots"][0]["status"] == "selected"
    assert normalized["selection_slots"][0]["code"] == "000010"
    assert normalized["selection_slots"][1]["reason"] == "DUPLICATE_SELECTED_CODE"
    assert normalized["selection_slots"][2]["reason"] == "MISSING_NEXT_CLOSE"
    assert normalized["selection_slots"][3]["reason"] == "SELECTED_CODE_NOT_IN_VALID_CANDIDATES"
    assert normalized["selection_slots"][1]["slot_state"] == "replay_unfilled"
    assert normalized["selection_slots"][2]["slot_state"] == "replay_unfilled"
    assert normalized["diagnostics"]["selected_code_adapter_policy_allowed"] is False
    assert normalized["diagnostics"]["duplicate_selected_codes"] == [
        {"code": "000010", "reason": "DUPLICATE_SELECTED_CODE"}
    ]


def test_integer_share_reward_cost_and_missing_label_blocking():
    rows = [
        {
            "date": "2024-03-05",
            "table": "A000010",
            "code": "000010",
            "score": 1.0,
            "entry_close": 30000,
            "next_close": 33000,
            "future_return_1d": 0.10,
            "eligible_for_selection": True,
            "split": "train",
        },
        {
            "date": "2024-03-05",
            "table": "A000020",
            "code": "000020",
            "score": 0.9,
            "entry_close": 200000,
            "next_close": 210000,
            "future_return_1d": 0.05,
            "eligible_for_selection": True,
            "split": "train",
        },
        {
            "date": "2024-03-05",
            "table": "A000030",
            "code": "000030",
            "score": 0.8,
            "entry_close": 1000,
            "next_close": None,
            "eligible_for_selection": True,
            "split": "train",
        },
    ]

    result = evaluate_close_slot_day(
        rows,
        date="2024-03-05",
        total_capital_krw=1_000_000,
        selected_codes=["000010", "000020", "000030"],
    )
    ledger = result["ledger"]

    assert ledger["round_trip_cost_bp"] == 23
    assert ledger["slot_cash_krw"] == 100_000
    assert ledger["filled_slots"] == 1
    assert ledger["blocked_slots"] == 2
    first = ledger["ledger"][0]
    assert first["shares"] == 3
    assert first["notional_krw"] == 90_000
    assert first["gross_pnl_krw"] == 9_000
    assert first["buy_commission_krw"] == pytest.approx(13.5)
    assert first["sell_tax_krw"] == pytest.approx(198)
    assert first["sell_commission_krw"] == pytest.approx(14.85)
    assert first["cost_krw"] == pytest.approx(226.35)
    assert first["total_cost_krw"] == pytest.approx(first["cost_krw"])
    assert first["net_pnl_krw"] == pytest.approx(8_773.65)
    assert first["slot_state"] == "filled"
    assert ledger["reward"] == pytest.approx(8_773.65 / 1_000_000)
    assert ledger["ledger"][1]["unfilled_reason"] == "INSUFFICIENT_SLOT_CASH"
    assert ledger["ledger"][2]["unfilled_reason"] == "MISSING_NEXT_CLOSE"
    assert ledger["ledger"][2]["slot_state"] == "replay_unfilled"
    assert ledger["ledger"][2]["blocked"] is True
    assert all(row["gross_pnl_krw"] == 0 for row in ledger["ledger"][1:])

    sensitivity = evaluate_close_slot_cost_sensitivity(
        rows,
        date="2024-03-05",
        total_capital_krw=1_000_000,
        selected_codes=["000010"],
    )
    assert sensitivity["cost_sensitivity_bp"] == [0, 23, 46]
    assert sensitivity["results_by_cost_bp"]["0"]["reward"] > sensitivity["results_by_cost_bp"]["23"]["reward"]
    assert sensitivity["results_by_cost_bp"]["23"]["reward"] > sensitivity["results_by_cost_bp"]["46"]["reward"]


def _threshold_rows(count=10):
    return [
        {
            "date": "2024-03-08",
            "table": f"A{i:06d}",
            "code": f"{i:06d}",
            "score": (count - i + 1) / 10,
            "entry_close": 1000,
            "next_close": 1010,
            "future_return_1d": 0.01,
            "eligible_for_selection": True,
            "split": "train",
        }
        for i in range(1, count + 1)
    ]


@pytest.mark.parametrize(
    ("threshold", "expected_selected"),
    [
        (1.1, 0),
        (1.0, 1),
        (0.8, 3),
        (0.1, 10),
    ],
)
def test_threshold_selection_emits_cash_hold_slots_for_zero_one_n_and_ten(threshold, expected_selected):
    normalized = normalize_close_slot_action(
        _threshold_rows(),
        date="2024-03-08",
        selection_threshold=threshold,
    )

    selected = [slot for slot in normalized["selection_slots"] if slot["status"] == "selected"]
    cash_holds = [slot for slot in normalized["selection_slots"] if slot["slot_state"] == "cash_hold"]
    assert len(selected) == expected_selected
    assert len(cash_holds) == 10 - expected_selected
    assert all(slot["reason"] == "SELECTION_THRESHOLD_NOT_MET" for slot in cash_holds)


def test_threshold_selection_honors_max_slot_count_with_cash_hold_slots():
    normalized = normalize_close_slot_action(
        _threshold_rows(),
        date="2024-03-08",
        selection_threshold=0.1,
        max_slot_count=2,
    )

    assert [slot["code"] for slot in normalized["selection_slots"][:2]] == ["000001", "000002"]
    assert normalized["max_slot_count"] == 2
    assert [slot["slot_state"] for slot in normalized["selection_slots"][2:]] == ["cash_hold"] * 8


def test_component_cost_scenarios_zero_base_and_stress_formulas():
    rows = [
        {
            "date": "2024-03-09",
            "table": "A000001",
            "code": "000001",
            "score": 1.0,
            "entry_close": 10000,
            "next_close": 11000,
            "future_return_1d": 0.10,
            "eligible_for_selection": True,
            "split": "train",
        }
    ]

    zero = evaluate_close_slot_day(
        rows,
        date="2024-03-09",
        total_capital_krw=101_000,
        cost_scenario_id=COST_SCENARIO_ZERO_CONTROL_0BP,
    )["ledger"]["ledger"][0]
    base = evaluate_close_slot_day(
        rows,
        date="2024-03-09",
        total_capital_krw=101_000,
        cost_scenario_id=COST_SCENARIO_BASE_23BP,
    )["ledger"]["ledger"][0]
    stress = evaluate_close_slot_day(
        rows,
        date="2024-03-09",
        total_capital_krw=101_000,
        cost_scenario_id=COST_SCENARIO_STRESS_46BP,
    )["ledger"]["ledger"][0]

    assert zero["total_cost_krw"] == 0
    assert zero["net_pnl_krw"] == pytest.approx(1000)
    assert base["buy_commission_krw"] == pytest.approx(1.5)
    assert base["sell_tax_krw"] == pytest.approx(22)
    assert base["sell_commission_krw"] == pytest.approx(1.65)
    assert base["total_cost_krw"] == pytest.approx(25.15)
    assert stress["buy_slippage_krw"] == pytest.approx(11.5)
    assert stress["sell_slippage_krw"] == pytest.approx(12.65)
    assert stress["total_cost_krw"] == pytest.approx(49.3)
    assert evaluate_close_slot_day(rows, date="2024-03-09")["ledger"]["schema_version"] == 2

    with pytest.raises(ValueError, match="scalar-only close-slot v2 cost accounting"):
        evaluate_close_slot_day(rows, date="2024-03-09", cost_bp=17)

def test_numeric_codes_are_padded_without_int_coercion():
    rows = [
        {
            "date": "2024-03-10",
            "table": "A250",
            "code": 250,
            "score": 1.0,
            "entry_close": 1000,
            "next_close": 1010,
            "future_return_1d": 0.01,
            "eligible_for_selection": True,
            "split": "train",
        }
    ]

    normalized = normalize_close_slot_action(rows, date="2024-03-10")

    assert normalized["schema_version"] == 2
    assert normalized["selection_slots"][0]["code"] == "000250"
    assert normalized["ranked_candidates"][0]["code"] == "000250"


def test_daily_close_slot_env_steps_scores_and_replay_actions():
    rows = [
        {
            "date": "2024-03-06",
            "table": "A000010",
            "code": "000010",
            "score": 0.1,
            "entry_close": 1000,
            "next_close": 1100,
            "future_return_1d": 0.10,
            "eligible_for_selection": True,
            "split": "train",
        },
        {
            "date": "2024-03-06",
            "table": "A000020",
            "code": "000020",
            "score": 0.2,
            "entry_close": 1000,
            "next_close": 900,
            "future_return_1d": -0.10,
            "eligible_for_selection": True,
            "split": "train",
        },
        {
            "date": "2024-03-07",
            "table": "A000030",
            "code": "000030",
            "score": 0.3,
            "entry_close": 1000,
            "next_close": 1200,
            "future_return_1d": 0.20,
            "eligible_for_selection": True,
            "split": "train",
        },
    ]
    env = DailyCloseSlotEnv(rows, total_capital_krw=1_000_000)

    assert env.reset()["date"] == "2024-03-06"
    state, reward, done, info = env.step({"000010": 0.9, "000020": 0.1})
    assert done is False
    assert state["date"] == "2024-03-07"
    assert info["normalized_action"]["action_label"] == POLICY_ACTION_LABEL
    assert info["ledger"]["ledger"][0]["code"] == "000010"
    assert reward == info["ledger"]["reward"]

    state, reward, done, info = env.step(["000030"])
    assert done is True
    assert state["done"] is True
    assert info["selected_codes_replay_adapter"] is True
    assert info["normalized_action"]["action_label"] == REPLAY_ADAPTER_LABEL
    assert info["ledger"]["filled_slots"] == 1
    assert reward > 0
    with pytest.raises(StopIteration):
        env.step()
