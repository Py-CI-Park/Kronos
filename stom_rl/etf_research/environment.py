"""Single-ETF target-position accounting environment primitives."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PositionContractError(Exception):
    field: str
    value: float

    def __str__(self) -> str:
        return f"invalid {self.field}: {self.value}"


@dataclass(frozen=True, slots=True)
class MarketBar:
    open: float
    close: float

    def __post_init__(self) -> None:
        if self.open <= 0:
            raise PositionContractError("open", self.open)
        if self.close <= 0:
            raise PositionContractError("close", self.close)


@dataclass(frozen=True, slots=True)
class PortfolioState:
    starting_cash: float
    cash: float
    units: float
    last_price: float
    value: float
    peak_value: float

    @classmethod
    def initial(cls, cash: float) -> PortfolioState:
        if cash <= 0:
            raise PositionContractError("cash", cash)
        return cls(cash, cash, 0.0, 0.0, cash, cash)

    @property
    def cumulative_return(self) -> float:
        return self.value / self.starting_cash - 1.0

    @property
    def drawdown(self) -> float:
        return 1.0 - self.value / self.peak_value

    @property
    def position_ratio(self) -> float:
        if self.value <= 0 or self.units == 0:
            return 0.0
        return self.units * self.last_price / self.value


@dataclass(frozen=True, slots=True)
class PositionStep:
    state: PortfolioState
    target_position: float
    turnover: float
    transaction_cost: float
    period_return: float


def step_target_position(
    state: PortfolioState,
    target_position: float,
    bar: MarketBar,
    *,
    one_way_cost_bps: float,
) -> PositionStep:
    """Rebalance at open, charge side-specific cost, and mark at close."""
    if not 0.0 <= target_position <= 1.0:
        raise PositionContractError("target_position", target_position)
    if one_way_cost_bps < 0:
        raise PositionContractError("one_way_cost_bps", one_way_cost_bps)
    opening_value = state.cash + state.units * bar.open
    current_market_value = state.units * bar.open
    target_market_value = opening_value * target_position
    difference = target_market_value - current_market_value
    cost_rate = one_way_cost_bps / 10_000.0
    if difference > 0:
        transaction_cost = difference * cost_rate
        acquired_value = difference - transaction_cost
        cash = state.cash - difference
        units = state.units + acquired_value / bar.open
    else:
        sold_value = -difference
        transaction_cost = sold_value * cost_rate
        cash = state.cash + sold_value - transaction_cost
        units = max(0.0, state.units - sold_value / bar.open)
    ending_value = cash + units * bar.close
    peak_value = max(state.peak_value, ending_value)
    next_state = PortfolioState(
        starting_cash=state.starting_cash,
        cash=cash,
        units=units,
        last_price=bar.close,
        value=ending_value,
        peak_value=peak_value,
    )
    turnover = abs(difference) / opening_value if opening_value > 0 else 0.0
    return PositionStep(next_state, target_position, turnover, transaction_cost, ending_value / state.value - 1.0)

