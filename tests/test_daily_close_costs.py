from __future__ import annotations

import pytest

from stom_rl.daily_close_research.costs import (
    CostContractError,
    InstrumentKind,
    TradingVenue,
    registered_cost_contract,
)


def test_krx_stock_contract_sums_to_point_23_percent_round_trip() -> None:
    contract = registered_cost_contract(InstrumentKind.STOCK, TradingVenue.KRX)

    assert contract.buy_total_percent == pytest.approx(0.015)
    assert contract.sell_total_percent == pytest.approx(0.215)
    assert contract.round_trip_percent == pytest.approx(0.230)
    assert contract.round_trip_bps == pytest.approx(23.0)
    assert contract.cost_for_buy(5_000_000) == pytest.approx(750)
    assert contract.cost_for_sell(5_000_000) == pytest.approx(10_750)


def test_nxt_stock_and_krx_equity_etf_use_distinct_actual_costs() -> None:
    nxt_stock = registered_cost_contract(InstrumentKind.STOCK, TradingVenue.NXT)
    krx_etf = registered_cost_contract(InstrumentKind.EQUITY_ETF, TradingVenue.KRX)

    assert nxt_stock.round_trip_percent == pytest.approx(0.229)
    assert krx_etf.round_trip_percent == pytest.approx(0.030)
    assert krx_etf.sell_tax_percent == pytest.approx(0.0)


def test_unsupported_instrument_venue_pair_fails_closed() -> None:
    with pytest.raises(CostContractError, match="unsupported"):
        registered_cost_contract(InstrumentKind.EQUITY_ETF, TradingVenue.NXT)

