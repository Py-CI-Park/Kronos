from __future__ import annotations

import pytest

from stom_rl.daily_close_research.costs import InstrumentKind, TradingVenue, registered_cost_contract
from stom_rl.daily_close_research.portfolio import (
    ActionKind,
    MarketQuote,
    PortfolioAction,
    PortfolioConfig,
    PortfolioState,
    step_portfolio,
)


def test_add_one_uses_integer_shares_and_preserves_reserve_and_exposure_limits() -> None:
    config = PortfolioConfig.registered()
    costs = registered_cost_contract(InstrumentKind.STOCK, TradingVenue.KRX)
    state = PortfolioState.initial(config)

    step = step_portfolio(
        state,
        PortfolioAction(ActionKind.ADD_ONE, target_code="000250"),
        (MarketQuote("000250", execution_price=10_000.0, mark_price=10_100.0, rank=1.0),),
        config,
        costs,
    )

    assert step.state.positions[0].units == 499
    assert step.state.cash >= config.minimum_cash_reserve
    assert step.state.market_value <= config.maximum_exposure
    assert step.transaction_cost > 0
    assert step.reward > 0


def test_exit_one_realizes_sell_tax_and_returns_to_cash() -> None:
    config = PortfolioConfig.registered()
    costs = registered_cost_contract(InstrumentKind.STOCK, TradingVenue.KRX)
    bought = step_portfolio(
        PortfolioState.initial(config),
        PortfolioAction(ActionKind.ADD_ONE, target_code="000250"),
        (MarketQuote("000250", 10_000.0, 10_000.0, 1.0),),
        config,
        costs,
    ).state

    sold = step_portfolio(
        bought,
        PortfolioAction(ActionKind.EXIT_ONE, source_code="000250"),
        (MarketQuote("000250", 10_000.0, 10_000.0, 1.0),),
        config,
        costs,
    )

    assert sold.state.positions == ()
    assert sold.transaction_cost == pytest.approx(costs.cost_for_sell(4_990_000.0))
    assert sold.state.cash < config.initial_cash


def test_eleventh_position_is_rejected_by_slot_limit() -> None:
    config = PortfolioConfig(
        initial_cash=60_000_000.0,
        maximum_exposure=50_000_000.0,
        minimum_cash_reserve=0.0,
        maximum_slots=1,
        slot_notional=5_000_000.0,
    )
    costs = registered_cost_contract(InstrumentKind.STOCK, TradingVenue.KRX)
    first = step_portfolio(
        PortfolioState.initial(config),
        PortfolioAction(ActionKind.ADD_ONE, target_code="000250"),
        (MarketQuote("000250", 10_000.0, 10_000.0, 1.0),),
        config,
        costs,
    ).state

    second = step_portfolio(
        first,
        PortfolioAction(ActionKind.ADD_ONE, target_code="000660"),
        (
            MarketQuote("000250", 10_000.0, 10_000.0, 1.0),
            MarketQuote("000660", 100_000.0, 100_000.0, 2.0),
        ),
        config,
        costs,
    )

    assert tuple(position.code for position in second.state.positions) == ("000250",)
    assert second.action_applied is False

