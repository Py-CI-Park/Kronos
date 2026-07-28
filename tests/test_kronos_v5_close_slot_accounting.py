import json
import copy
import hashlib
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
    build_v51_slot_accounting_manifest,
)
from tests.oracles.v5_close_slot_oracle import (  # noqa: E402
    oracle_account_close_to_next_close_v1,
    oracle_account_normalized_slots,
)
from tests.oracles.v51_slot_oracle import (  # noqa: E402
    oracle_build_v51_slot_accounting_manifest,
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


def _v51_exact_mark(symbol, session, close):
    table = f"A{symbol}"
    timestamp = f"{session}T15:20:00+09:00"
    return {
        "schema_version": "kronos_daily_1520_source.v1",
        "symbol": symbol,
        "session": session,
        "date": session,
        "session_date": session,
        "timestamp": timestamp,
        "timestamp_kst": timestamp,
        "timestamp_yyyymmddhhmm": session.replace("-", "") + "1520",
        "price_basis": "15:20_bar_close_proxy",
        "official_close": False,
        "price_1520_close_proxy": close,
        "close": close,
        "price": close,
        "source_table": table,
        "table": table,
    }


def _v51_horizon(horizon_id="H3"):
    labels = {
        "H1": "future_return_h1_1520_proxy",
        "H3": "future_return_h3_1520_proxy",
        "H5": "future_return_h5_1520_proxy",
    }
    reverse = {value: key for key, value in labels.items()}
    canonical = reverse.get(horizon_id, horizon_id)
    return {
        "horizon_id": canonical,
        "horizon_days": {"H1": 1, "H3": 3, "H5": 5}[canonical],
        "label_column": labels[canonical],
    }


def _v51_row_horizon_fields(exit_marks, horizon_id):
    horizon = _v51_horizon(horizon_id)
    return {
        **horizon,
        "exit_session": exit_marks[horizon["label_column"]]["session"],
    }


def _v51_rows(horizon_id="H3"):
    first_exits = {
        "future_return_h1_1520_proxy": _v51_exact_mark("000042", "2026-07-15", "51000.000000"),
        "future_return_h3_1520_proxy": _v51_exact_mark("000042", "2026-07-17", "52000.000000"),
        "future_return_h5_1520_proxy": _v51_exact_mark("000042", "2026-07-21", "53000.000000"),
    }
    second_exits = {
        "future_return_h1_1520_proxy": _v51_exact_mark("000007", "2026-07-15", "25250.123456"),
        "future_return_h3_1520_proxy": _v51_exact_mark("000007", "2026-07-17", "25555.654321"),
        "future_return_h5_1520_proxy": _v51_exact_mark("000007", "2026-07-21", "26000.123456"),
    }
    return [
        {
            "session": "2026-07-14",
            "entry_session": "2026-07-14",
            "symbol": "000042",
            "side": "buy",
            "quantity": "99",
            "entry_1520": _v51_exact_mark("000042", "2026-07-14", "50000.000000"),
            "exit_1520_by_label": first_exits,
            "source_db_sha256": "a" * 64,
            "source_identity_sha256": "b" * 64,
            "panel_sha256": "c" * 64,
            **_v51_row_horizon_fields(first_exits, horizon_id),
        },
        {
            "session": "2026-07-14",
            "entry_session": "2026-07-14",
            "symbol": "000007",
            "side": "long",
            "quantity": "120",
            "entry_1520": _v51_exact_mark("000007", "2026-07-14", "25000.123456"),
            "exit_1520_by_label": second_exits,
            "source_db_sha256": "d" * 64,
            "source_identity_sha256": "e" * 64,
            "panel_sha256": "f" * 64,
            "panel_row_sha256": "1" * 64,
            **_v51_row_horizon_fields(second_exits, horizon_id),
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


V51_SCENARIO_SUMMARY_KEYS = [
    "schema_version",
    "horizon_id",
    "horizon_days",
    "label_column",
    "cost_scenario_id",
    "round_trip_cost_display_percent",
    "filled_slots",
    "unfilled_slots",
    "hold_cash_slots",
    "deployed_principal_krw_decimal",
    "reserve_cash_krw_decimal",
    "entry_cash_after_buy_costs_krw_decimal",
    "gross_pnl_krw_decimal",
    "buy_side_cost_krw_decimal",
    "sell_side_cost_krw_decimal",
    "cost_krw_decimal",
    "net_pnl_krw_decimal",
    "account_nav_krw_decimal",
    "reward_decimal",
]
V51_LEDGER_COMPARE_KEYS = [
    "slot",
    "symbol",
    "quantity",
    "status",
    "slot_state",
    "horizon_id",
    "label_column",
    "cost_scenario_id",
    "entry_mark_krw_decimal",
    "exit_mark_krw_decimal",
    "notional_krw_decimal",
    "deployed_principal_krw_decimal",
    "buy_side_cost_krw_decimal",
    "budget_used_krw_decimal",
    "unused_cash_krw_decimal",
    "exit_value_krw_decimal",
    "gross_pnl_krw_decimal",
    "sell_side_cost_krw_decimal",
    "cost_krw_decimal",
    "net_pnl_krw_decimal",
    "terminal_nav_krw_decimal",
    "buy_commission_krw_decimal",
    "buy_slippage_krw_decimal",
    "sell_tax_krw_decimal",
    "sell_commission_krw_decimal",
    "sell_slippage_krw_decimal",
]


def _assert_v51_matches_oracle(actual, expected):
    top_level_keys = [
        "schema_version",
        "horizon_id",
        "horizon_days",
        "label_column",
        "total_capital_krw_decimal",
        "slot_count",
        "slot_buy_budget_krw_decimal",
        "max_deployed_principal_krw_decimal",
        "reserve_cash_krw_decimal",
        "selected_count",
        "symbols",
        "account_nav_krw_decimal",
        "deployed_principal_krw_decimal",
        "entry_cash_after_buy_costs_krw_decimal",
    ]
    for key in top_level_keys:
        assert actual[key] == expected[key]
    assert [item["display_percent"] for item in actual["cost_scenarios"]] == ["0.00%", "0.23%", "0.46%"]
    assert [item["display_percent"] for item in actual["cost_scenarios"]] == [
        item["display_percent"] for item in expected["cost_scenarios"]
    ]
    for scenario_id in SCENARIOS:
        actual_scenario = actual["scenario_manifests"][scenario_id]
        expected_scenario = expected["scenario_manifests"][scenario_id]
        for key in V51_SCENARIO_SUMMARY_KEYS:
            assert actual_scenario[key] == expected_scenario[key]
        assert len(actual_scenario["ledger"]) == 10
        assert actual_scenario["ledger"][2]["terminal_nav_krw_decimal"] == "5000000.000000"
        for actual_row, expected_row in zip(actual_scenario["ledger"], expected_scenario["ledger"], strict=True):
            for key in V51_LEDGER_COMPARE_KEYS:
                if key in expected_row:
                    assert actual_row[key] == expected_row[key]
            if expected_row["status"] == "filled":
                for component_name, expected_component in expected_row["cost_components"].items():
                    assert actual_row["cost_components"][component_name] == expected_component


def _mutated_v51_rows(case):
    rows = copy.deepcopy(_v51_rows())
    if case == "too_many":
        return [
            {"symbol": f"{index:06d}", "side": "buy", "quantity": "1", "entry_mark": "1000", "exit_mark": "1001"}
            for index in range(1, 12)
        ]
    if case == "duplicate":
        rows[1]["symbol"] = "000042"
    elif case == "invalid_side":
        rows[0]["side"] = "short"
    elif case == "leverage":
        rows[0]["leverage"] = "2"
    elif case == "fractional_quantity":
        rows[0]["quantity"] = "1.5"
    elif case == "missing_entry":
        rows[0].pop("entry_1520")
    elif case == "missing_exit":
        rows[0]["exit_1520_by_label"] = {}
    elif case == "bare_entry_mark":
        rows[0]["entry_1520"] = "50000.000000"
    elif case == "generic_entry_alias":
        rows[0].pop("entry_1520")
        rows[0]["entry_mark"] = _v51_exact_mark("000042", "2026-07-14", "50000.000000")
    elif case == "generic_exit_alias_no_requested_label":
        rows[0]["exit_mark"] = rows[0]["exit_1520_by_label"].pop("future_return_h3_1520_proxy")
    elif case == "budget_breach":
        rows[0]["quantity"] = "100"
    elif case == "forbidden_future_return":
        rows[0]["future_return_1d"] = 0.25
    elif case == "daily_ohlcv":
        rows[0]["close"] = "50000.000000"
    elif case == "official_close":
        rows[0]["entry_1520"]["official_close"] = True
    elif case == "bad_source_db_hash":
        rows[0]["source_db_sha256"] = "A" * 64
    elif case == "missing_source_identity_hash":
        rows[0].pop("source_identity_sha256")
    elif case == "short_panel_hash":
        rows[0]["panel_sha256"] = "f" * 63
    elif case == "entry_source_table_mismatch":
        rows[0]["entry_1520"]["source_table"] = "A000999"
    elif case == "exit_symbol_mismatch":
        rows[0]["exit_1520_by_label"]["future_return_h3_1520_proxy"]["symbol"] = "000999"
    elif case == "timestamp_without_kst_offset":
        rows[0]["entry_1520"]["timestamp_kst"] = "2026-07-14T15:20:00Z"
    elif case == "exit_session_mismatch":
        rows[0]["exit_session"] = "2026-07-16"
    elif case == "horizon_mismatch":
        rows[0]["horizon_id"] = "H1"
    elif case == "horizon_days_mismatch":
        rows[0]["horizon_days"] = 5
    else:
        raise AssertionError(case)
    return rows

def _recompute_v51_manifest_digest(manifest):
    payload = copy.deepcopy(manifest)
    payload.pop("accounting_manifest_sha256", None)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_kronos_v51_slot_accounting_matches_independent_oracle_for_h3():
    actual = build_v51_slot_accounting_manifest(_v51_rows(), "H3")
    expected = oracle_build_v51_slot_accounting_manifest(_v51_rows(), "H3")

    _assert_v51_matches_oracle(actual, expected)
    assert actual["total_capital_krw"] == 60_000_000
    assert actual["slot_count"] == 10
    assert actual["slot_buy_budget_krw"] == 5_000_000
    assert actual["max_deployed_principal_krw"] == 50_000_000
    assert actual["reserve_cash_krw"] == 10_000_000
    assert actual["price_basis"] == "15:20_bar_close_proxy"
    assert actual["official_close"] is False
    assert actual["false_locks"] == {
        "official_close": False,
        "full_day_daily_ohlcv": False,
        "live_trading": False,
        "profit_claim": False,
        "paper_trading": False,
        "broker_integration": False,
    }
    assert all(value is False for value in actual["promotion_claims"].values())
    assert actual["primary_accounting"] == actual["scenario_manifests"][COST_SCENARIO_BASE_23BP]
    assert len(actual["accounting_manifest_sha256"]) == 64
    assert set(actual["accounting_manifest_sha256"]) <= set("0123456789abcdef")
    first_source = actual["primary_accounting"]["ledger"][0]["source"]
    assert first_source["source_db_sha256"] == "a" * 64
    assert first_source["source_identity_sha256"] == "b" * 64
    assert first_source["panel_sha256"] == "c" * 64
    assert first_source["source_table"] == "A000042"
    assert first_source["entry_source_table"] == "A000042"
    assert first_source["exit_source_table"] == "A000042"


def test_kronos_v51_slot_accounting_accepts_label_horizon_alias_and_hash_is_stable():
    alias = "future_return_h5_1520_proxy"
    first = build_v51_slot_accounting_manifest(_v51_rows("H5"), alias)
    second = build_v51_slot_accounting_manifest(_v51_rows("H5"), alias)

    assert first["horizon_id"] == "H5"
    assert first["label_column"] == alias
    assert first["scenario_manifests"][COST_SCENARIO_STRESS_46BP]["ledger"][0]["exit_mark_krw_decimal"] == "53000.000000"
    assert first["accounting_manifest_sha256"] == second["accounting_manifest_sha256"]

def test_kronos_v51_slot_accounting_digest_recomputes_and_detects_tamper():
    actual = build_v51_slot_accounting_manifest(_v51_rows(), "H3")

    assert actual["accounting_manifest_sha256"] == _recompute_v51_manifest_digest(actual)

    tampered = copy.deepcopy(actual)
    tampered["scenario_manifests"][COST_SCENARIO_BASE_23BP]["ledger"][0][
        "exit_mark_krw_decimal"
    ] = "1.000000"
    assert _recompute_v51_manifest_digest(tampered) != actual["accounting_manifest_sha256"]
    tampered["accounting_manifest_sha256"] = _recompute_v51_manifest_digest(tampered)
    assert tampered["accounting_manifest_sha256"] != actual["accounting_manifest_sha256"]


@pytest.mark.parametrize(
    ("case", "match"),
    [
        ("too_many", "at most 10"),
        ("duplicate", "duplicate selected symbol"),
        ("invalid_side", "side"),
        ("leverage", "leverage"),
        ("fractional_quantity", "quantity"),
        ("missing_entry", "entry_1520"),
        ("missing_exit", "exit_1520_by_label"),
        ("bare_entry_mark", "structured exact 15:20 mark"),
        ("generic_entry_alias", "forbidden V5.1"),
        ("generic_exit_alias_no_requested_label", "forbidden V5.1"),
        ("budget_breach", "budget breach"),
        ("forbidden_future_return", "forbidden V5.1"),
        ("daily_ohlcv", "forbidden V5.1"),
        ("official_close", "official_close"),
        ("bad_source_db_hash", "source_db_sha256"),
        ("missing_source_identity_hash", "source_identity_sha256"),
        ("short_panel_hash", "panel_sha256"),
        ("entry_source_table_mismatch", "source_table"),
        ("exit_symbol_mismatch", "symbol"),
        ("timestamp_without_kst_offset", "timestamp_kst"),
        ("exit_session_mismatch", "session"),
        ("horizon_mismatch", "horizon_id"),
        ("horizon_days_mismatch", "horizon_days"),
    ],
)
def test_kronos_v51_slot_accounting_adversarial_rows_fail_closed(case, match):
    with pytest.raises(ValueError, match=match):
        build_v51_slot_accounting_manifest(_mutated_v51_rows(case), "H3")


def test_kronos_v51_slot_accounting_unsupported_horizon_fails_closed():
    with pytest.raises(ValueError, match="unsupported V5.1 accounting horizon"):
        build_v51_slot_accounting_manifest(_v51_rows(), "H2")
