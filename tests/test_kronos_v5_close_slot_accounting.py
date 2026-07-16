import json
import math
from collections.abc import Mapping
from decimal import Decimal
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stom_rl.daily_close_slot_env import (  # noqa: E402
    REPLAY_ADAPTER_LABEL,
    account_close_slot_selection,
    normalize_close_slot_action,
)
from stom_rl.v5_accounting import (  # noqa: E402
    ACCOUNTING_HORIZON_ID,
    COST_SCENARIO_BASE_23BP,
    COST_SCENARIO_STRESS_46BP,
    COST_SCENARIO_ZERO_CONTROL_0BP,
    account_close_to_next_close_v1,
)
from tests.oracles.v5_close_slot_oracle import (  # noqa: E402
    oracle_account_close_to_next_close_v1,
    oracle_account_normalized_slots,
)


SCENARIOS = [
    COST_SCENARIO_ZERO_CONTROL_0BP,
    COST_SCENARIO_BASE_23BP,
    COST_SCENARIO_STRESS_46BP,
]
BOUNDARY_ONE_SHARE_PLUS_ONE_PICOMARK = Decimal("99985.002249662551617407388891")


def _canonical_rows():
    return [
        {
            "date": "2026-07-14",
            "code": "000042",
            "entry_close": "12345.678901",
            "next_close": "12456.789012",
            "cost_application_count": 1,
        },
        {
            "date": "2026-07-14",
            "code": 7,
            "entry_close": "8000.333333",
            "next_close": "7900.111111",
            "cost_application_count": 1,
        },
        {
            "date": "2026-07-14",
            "code": "000999",
            "entry_close": "5000.000001",
            "next_close": "5200.000001",
            "cost_application_count": 1,
        },
    ]


def _legacy_rows():
    return [
        {
            "date": "2026-07-14",
            "table": "A000010",
            "code": "000010",
            "score": 0.9,
            "entry_close": "30000.000001",
            "next_close": "33000.000001",
            "future_return_1d": 0.1,
            "eligible_for_selection": True,
        },
        {
            "date": "2026-07-14",
            "table": "A000020",
            "code": "000020",
            "score": 0.8,
            "entry_close": "200000.000001",
            "next_close": "210000.000001",
            "future_return_1d": 0.05,
            "eligible_for_selection": True,
        },
        {
            "date": "2026-07-14",
            "table": "A000030",
            "code": "000030",
            "score": 0.7,
            "entry_close": "1000.000001",
            "next_close": None,
            "eligible_for_selection": True,
        },
    ]


def _hand_authored_normalized_action():
    return {
        "schema_version": 2,
        "date": "2026-07-14",
        "action_label": REPLAY_ADAPTER_LABEL,
        "slot_count": 10,
        "max_slot_count": 10,
        "selected_count": 2,
        "selection_slots": [
            {
                "slot": 0,
                "status": "selected",
                "code": "000042",
                "slot_state": "filled",
                "candidate": {
                    "date": "2026-07-14",
                    "table": "A000042",
                    "code": "000042",
                    "score": 0.99,
                    "tie_score": None,
                    "entry_close": 99985.00224966255,
                    "next_close": 100000.0,
                    "entry_close_source": BOUNDARY_ONE_SHARE_PLUS_ONE_PICOMARK,
                    "next_close_source": "100000.000000",
                    "future_return_1d": 0.0,
                    "split": "test",
                    "candidate_index": 0,
                },
            },
            {
                "slot": 1,
                "status": "selected",
                "code": "7",
                "slot_state": "filled",
                "candidate": {
                    "date": "2026-07-14",
                    "table": "A000007",
                    "code": "000007",
                    "score": 0.98,
                    "tie_score": None,
                    "entry_close": 1000.0,
                    "next_close": 1001.0,
                    "entry_close_source": "1000.000000",
                    "next_close_source": Decimal("1001.000000"),
                    "future_return_1d": 0.001,
                    "split": "test",
                    "candidate_index": 1,
                },
            },
            {
                "slot": 2,
                "status": "unfilled",
                "reason": "NEGATIVE_ZERO_PUBLIC_SERIALIZATION_PROBE",
                "code": "000123",
                "slot_state": "replay_unfilled",
                "candidate": {
                    "date": "2026-07-14",
                    "table": "A000123",
                    "code": "000123",
                    "score": 0.1,
                    "tie_score": None,
                    "entry_close": -0.0,
                    "next_close": -0.0,
                    "entry_close_source": "-0.0000004",
                    "next_close_source": Decimal("-0.0000004"),
                    "future_return_1d": 0.0,
                    "split": "test",
                    "candidate_index": 2,
                },
            },
        ],
        "diagnostics": {
            "selected_code_adapter_used": True,
            "selected_code_adapter_policy_allowed": False,
            "invalid_rows": [],
            "duplicate_candidate_rows": [],
            "duplicate_selected_codes": [],
            "missing_selected_codes": [],
        },
    }


def _contains_negative_zero(value):
    if isinstance(value, float):
        return value == 0.0 and math.copysign(1.0, value) < 0.0
    if isinstance(value, Mapping):
        return any(_contains_negative_zero(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_negative_zero(item) for item in value)
    return False


def _assert_ledgers_equal(actual, expected):
    summary_keys = [
        "schema_version",
        "horizon_id",
        "accounting_horizon_id",
        "carry_allowed",
        "terminal_liquidation",
        "rounding_mode",
        "money_quantum",
        "ratio_quantum",
        "total_capital_krw",
        "slot_cash_krw",
        "round_trip_cost_bp",
        "round_trip_cost_rate",
        "cost_scenario",
        "cost_scenario_id",
        "cost_application_count",
        "filled_slots",
        "unfilled_slots",
        "blocked_slots",
        "gross_pnl_krw",
        "cost_krw",
        "net_pnl_krw",
        "terminal_nav_krw",
        "reward",
        "ledger",
    ]
    for key in summary_keys:
        assert actual[key] == expected[key]


@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_kronos_v5_canonical_decimal_ledger_matches_independent_oracle(scenario_id):
    actual = account_close_to_next_close_v1(_canonical_rows(), cost_scenario_id=scenario_id)
    expected = oracle_account_close_to_next_close_v1(_canonical_rows(), cost_scenario_id=scenario_id)

    _assert_ledgers_equal(actual, expected)
    assert [row["code"] for row in actual["ledger"]] == ["000007", "000042"]
    assert actual["total_capital_krw"] == 1_000_000
    assert actual["max_positions"] == 2
    assert actual["position_fraction"] == 0.25
    assert actual["max_gross_fraction"] == 0.5
    assert actual["allocated_cash_krw"] == 500_000
    assert actual["unallocated_cash_krw"] == 500_000
    assert actual["diagnostics"]["excluded_codes_over_max_positions"] == ["000999"]


@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_daily_close_slot_adapter_matches_independent_oracle_for_hand_authored_slots(scenario_id):
    normalized = _hand_authored_normalized_action()
    actual = account_close_slot_selection(
        normalized,
        total_capital_krw=1_000_000,
        cost_scenario_id=scenario_id,
    )
    expected = oracle_account_normalized_slots(
        normalized,
        total_capital_krw=1_000_000,
        slot_count=10,
        cost_scenario_id=scenario_id,
    )

    _assert_ledgers_equal(actual, expected)
    assert [row["code"] for row in actual["ledger"][:3]] == ["000042", "000007", "000123"]
    assert actual["ledger"][0]["terminal_liquidation"] == "explicit_t1_close"
    assert actual["ledger"][0]["cost_application_count"] == 1
    assert actual["ledger"][2]["unfilled_reason"] == "NEGATIVE_ZERO_PUBLIC_SERIALIZATION_PROBE"
    assert actual["ledger"][2]["entry_close"] == 0.0
    assert actual["ledger"][2]["next_close"] == 0.0
    assert not _contains_negative_zero(actual)


def test_daily_close_slot_adapter_uses_source_exact_mark_at_share_floor_boundary():
    normalized = _hand_authored_normalized_action()
    actual = account_close_slot_selection(
        normalized,
        total_capital_krw=1_000_000,
        cost_scenario_id=COST_SCENARIO_BASE_23BP,
    )
    expected = oracle_account_normalized_slots(
        normalized,
        total_capital_krw=1_000_000,
        slot_count=10,
        cost_scenario_id=COST_SCENARIO_BASE_23BP,
    )

    _assert_ledgers_equal(actual, expected)
    assert actual["ledger"][0]["status"] == "unfilled"
    assert actual["ledger"][0]["shares"] == 0
    assert actual["ledger"][0]["unfilled_reason"] == "INSUFFICIENT_SLOT_CASH"


def test_normalizer_preserves_source_exact_decimal_marks_for_accounting():
    rows = [
        {
            "date": "2026-07-14",
            "table": "A000042",
            "code": "000042",
            "score": 1.0,
            "entry_close": BOUNDARY_ONE_SHARE_PLUS_ONE_PICOMARK,
            "next_close": "100000.000000",
            "future_return_1d": 0.0,
            "eligible_for_selection": True,
        }
    ]
    normalized = normalize_close_slot_action(
        rows,
        date="2026-07-14",
        selected_codes=["000042"],
    )
    candidate = normalized["selection_slots"][0]["candidate"]

    assert candidate["entry_close_source"] == BOUNDARY_ONE_SHARE_PLUS_ONE_PICOMARK
    assert candidate["entry_close"] == float(BOUNDARY_ONE_SHARE_PLUS_ONE_PICOMARK)
    actual = account_close_slot_selection(
        normalized,
        total_capital_krw=1_000_000,
        cost_scenario_id=COST_SCENARIO_BASE_23BP,
    )
    assert actual["ledger"][0]["status"] == "unfilled"
    assert actual["ledger"][0]["unfilled_reason"] == "INSUFFICIENT_SLOT_CASH"


@pytest.mark.parametrize(
    ("bad_row", "match"),
    [
        ({"code": "000001", "entry_close": 1000, "next_close": 1010, "cost_application_count": 2}, "cost_application_count"),
        ({"code": "000001", "entry_close": 1000}, "next_close"),
        ({"code": "000001", "entry_close": 1000, "next_close": "NaN"}, "finite"),
        ({"code": "-1", "entry_close": 1000, "next_close": 1010}, "six-digit"),
    ],
)
def test_kronos_v5_adversarial_rows_fail_closed(bad_row, match):
    with pytest.raises(ValueError, match=match):
        account_close_to_next_close_v1([bad_row], cost_scenario_id=COST_SCENARIO_BASE_23BP)


def test_kronos_v5_wrong_horizon_fails_closed():
    with pytest.raises(ValueError, match="unsupported accounting horizon"):
        account_close_to_next_close_v1(
            _canonical_rows()[:1],
            cost_scenario_id=COST_SCENARIO_BASE_23BP,
            horizon_id="CS_T_OPEN_TO_T1_CLOSE_WRONG",
        )


def test_kronos_v5_canonical_capital_is_fixed_at_one_million_krw():
    with pytest.raises(ValueError, match="total_capital_krw=1000000"):
        account_close_to_next_close_v1(
            _canonical_rows()[:1],
            cost_scenario_id=COST_SCENARIO_BASE_23BP,
            total_capital_krw=2_000_000,
        )


def test_selected_code_replay_rejects_negative_six_digit_adapter_code():
    with pytest.raises(ValueError, match="six-digit"):
        normalize_close_slot_action(_legacy_rows(), date="2026-07-14", selected_codes=["-1"])


def test_cost_scenarios_are_charged_once_not_as_double_round_trip_scalar():
    single = account_close_to_next_close_v1(_canonical_rows()[:1], cost_scenario_id=COST_SCENARIO_BASE_23BP)

    assert single["cost_application_count"] == 1
    assert single["ledger"][0]["cost_application_count"] == 1
    assert single["round_trip_cost_bp"] == 23
    with pytest.raises(ValueError, match="cost_application_count"):
        account_close_to_next_close_v1(
            [{**_canonical_rows()[0], "cost_application_count": 2}],
            cost_scenario_id=COST_SCENARIO_BASE_23BP,
        )


@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_cost_bp_aliases_match_scenario_ids(scenario_id):
    by_scenario = account_close_to_next_close_v1(_canonical_rows()[:1], cost_scenario_id=scenario_id)
    by_bp = account_close_to_next_close_v1(_canonical_rows()[:1], cost_bp=by_scenario["round_trip_cost_bp"])

    assert by_bp["cost_scenario_id"] == scenario_id
    assert by_bp["ledger"] == by_scenario["ledger"]
    assert by_bp["reward"] == by_scenario["reward"]
    assert by_bp["horizon_id"] == ACCOUNTING_HORIZON_ID
