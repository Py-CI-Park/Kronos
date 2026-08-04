"""Typed, product-specific explicit trading-cost contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class InstrumentKind(str, Enum):
    STOCK = "STOCK"
    EQUITY_ETF = "EQUITY_ETF"


class TradingVenue(str, Enum):
    KRX = "KRX"
    NXT = "NXT"


@dataclass(frozen=True, slots=True)
class CostContractError(Exception):
    reason: str

    def __str__(self) -> str:
        return self.reason


@dataclass(frozen=True, slots=True)
class CostContract:
    instrument: InstrumentKind
    venue: TradingVenue
    buy_commission_percent: float
    sell_commission_percent: float
    sell_tax_percent: float
    source: str

    def __post_init__(self) -> None:
        values = (
            self.buy_commission_percent,
            self.sell_commission_percent,
            self.sell_tax_percent,
        )
        if any(value < 0 for value in values):
            raise CostContractError("cost percentages must be non-negative")

    @property
    def buy_total_percent(self) -> float:
        return self.buy_commission_percent

    @property
    def sell_total_percent(self) -> float:
        return self.sell_commission_percent + self.sell_tax_percent

    @property
    def round_trip_percent(self) -> float:
        return self.buy_total_percent + self.sell_total_percent

    @property
    def round_trip_bps(self) -> float:
        return self.round_trip_percent * 100.0

    def cost_for_buy(self, notional: float) -> float:
        return _cost_for_notional(notional, self.buy_total_percent)

    def cost_for_sell(self, notional: float) -> float:
        return _cost_for_notional(notional, self.sell_total_percent)


def registered_cost_contract(
    instrument: InstrumentKind,
    venue: TradingVenue,
) -> CostContract:
    """Return the preregistered research default, never an account quote."""
    if instrument is InstrumentKind.STOCK and venue is TradingVenue.KRX:
        return CostContract(instrument, venue, 0.015, 0.015, 0.200, "RESEARCH_DEFAULT_KIWOOM_KRX")
    if instrument is InstrumentKind.STOCK and venue is TradingVenue.NXT:
        return CostContract(instrument, venue, 0.014, 0.014, 0.201, "RESEARCH_DEFAULT_KIWOOM_NXT")
    if instrument is InstrumentKind.EQUITY_ETF and venue is TradingVenue.KRX:
        return CostContract(instrument, venue, 0.015, 0.015, 0.000, "RESEARCH_DEFAULT_KIWOOM_KRX_ETF")
    raise CostContractError(f"unsupported instrument/venue pair: {instrument.value}/{venue.value}")


def _cost_for_notional(notional: float, percent: float) -> float:
    if notional < 0:
        raise CostContractError("notional must be non-negative")
    return notional * percent / 100.0

