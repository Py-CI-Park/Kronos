from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from stom_rl.daily_market_transition import execute_binary_transition
from stom_rl.daily_market_transition_contract import (
    BinaryAction,
    DailyMarketCandidate,
    MarketTransitionConfig,
    MarketState,
    SplitName,
    build_market_state,
)


def _candidate(
    index: int,
    *,
    score: float | None = None,
    entry: str = "100000",
    exit_price: str = "110000",
    split: SplitName = "TRAIN",
) -> DailyMarketCandidate:
    return DailyMarketCandidate(
        decision_date=date(2026, 1, 2),
        entry_date=date(2026, 1, 5),
        exit_date=date(2026, 1, 6),
        code=f"{index:06d}",
        score=float(score if score is not None else 100 - index),
        entry_open_krw=Decimal(entry),
        exit_open_krw=Decimal(exit_price),
        split=split,
    )


def _state(candidates: list[DailyMarketCandidate]) -> MarketState:
    return build_market_state(
        candidates,
        feature_vector=(0.01, -0.02, 1.1, 0.4),
        previous_exposure_ratio=Decimal("0"),
        previous_drawdown=Decimal("0"),
    )


def test_default_contract_is_sixty_million_with_percent_first_costs() -> None:
    config = MarketTransitionConfig()

    assert config.initial_capital_krw == Decimal("60000000")
    assert config.stock_exposure_cap_krw == Decimal("50000000")
    assert config.cash_reserve_floor_krw == Decimal("10000000")
    assert config.max_slots == 10
    assert config.round_trip_cost_percent == Decimal("0.230")


def test_state_hash_and_ranking_do_not_depend_on_future_open_prices() -> None:
    original = [_candidate(250, score=1.0), _candidate(30, score=1.0)]
    changed = [
        candidate.model_copy(
            update={"entry_open_krw": Decimal("999999"), "exit_open_krw": Decimal("1")}
        )
        for candidate in original
    ]

    original_state = _state(original)
    changed_state = _state(changed)

    assert original_state.state_hash == changed_state.state_hash
    assert original_state.candidate_codes == ("000030", "000250")
    assert original_state.feature_vector == changed_state.feature_vector


def test_cash_action_preserves_nav_and_records_no_trade() -> None:
    candidates = [_candidate(index) for index in range(1, 13)]

    transition = execute_binary_transition(
        _state(candidates),
        candidates,
        BinaryAction.CASH,
        previous_nav_krw=Decimal("60000000"),
        previous_peak_nav_krw=Decimal("60000000"),
    )

    assert transition.requested_action == "CASH"
    assert transition.executed_action == "CASH"
    assert transition.final_nav_krw == Decimal("60000000")
    assert transition.cash_after_entry_krw == Decimal("60000000")
    assert transition.reward_log_nav == Decimal("0")
    assert transition.ledger == ()


def test_invest_action_uses_top_ten_integer_slots_and_preserves_cash_floor() -> None:
    candidates = [_candidate(index) for index in range(1, 13)]

    transition = execute_binary_transition(
        _state(candidates),
        candidates,
        BinaryAction.INVEST_TOP10_EQUAL_SLOT,
        previous_nav_krw=Decimal("60000000"),
        previous_peak_nav_krw=Decimal("60000000"),
    )

    assert transition.executed_action == "INVEST_TOP10_EQUAL_SLOT"
    assert tuple(row.code for row in transition.ledger) == tuple(f"{index:06d}" for index in range(1, 11))
    assert all(row.shares == int(row.shares) and row.shares > 0 for row in transition.ledger)
    assert transition.deployed_at_entry_krw <= Decimal("50000000")
    assert transition.cash_after_entry_krw >= Decimal("10000000")
    assert transition.total_cost_krw > 0
    assert transition.final_nav_krw > Decimal("60000000")
    assert transition.reward_log_nav > 0
    assert transition.equity_kind == "krw_nav"
    assert transition.equity_unit == "krw"


def test_lower_nav_reduces_exposure_before_breaking_ten_million_cash_floor() -> None:
    candidates = [_candidate(index) for index in range(1, 11)]

    transition = execute_binary_transition(
        _state(candidates),
        candidates,
        BinaryAction.INVEST_TOP10_EQUAL_SLOT,
        previous_nav_krw=Decimal("55000000"),
        previous_peak_nav_krw=Decimal("60000000"),
    )

    assert transition.deployed_at_entry_krw <= Decimal("45000000")
    assert transition.cash_after_entry_krw >= Decimal("10000000")
    assert transition.drawdown_fraction < 0


def test_fresh_oos_is_sealed_and_cost_stress_increases_cost() -> None:
    fresh = [_candidate(index, split="FRESH_OOS") for index in range(1, 3)]
    with pytest.raises(ValueError, match="FRESH_OOS"):
        _ = _state(fresh)

    candidates = [_candidate(index) for index in range(1, 11)]
    state = _state(candidates)
    base = execute_binary_transition(
        state,
        candidates,
        BinaryAction.INVEST_TOP10_EQUAL_SLOT,
        previous_nav_krw=Decimal("60000000"),
        previous_peak_nav_krw=Decimal("60000000"),
    )
    stress_config = replace(
        MarketTransitionConfig(),
        buy_slippage_percent=Decimal("0.115"),
        sell_slippage_percent=Decimal("0.115"),
    )
    stress = execute_binary_transition(
        state,
        candidates,
        BinaryAction.INVEST_TOP10_EQUAL_SLOT,
        previous_nav_krw=Decimal("60000000"),
        previous_peak_nav_krw=Decimal("60000000"),
        config=stress_config,
    )

    assert stress_config.round_trip_cost_percent == Decimal("0.460")
    assert stress.total_cost_krw > base.total_cost_krw
    assert stress.final_nav_krw < base.final_nav_krw
