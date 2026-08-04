"""Integer-share, multi-slot portfolio accounting for daily-close research."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from .contracts import validate_stock_code
from .costs import CostContract


class ActionKind(str, Enum):
    HOLD_CASH = "HOLD_CASH"
    HOLD = "HOLD"
    ADD_ONE = "ADD_ONE"
    EXIT_ONE = "EXIT_ONE"
    REPLACE_ONE = "REPLACE_ONE"
    REDUCE_RISK = "REDUCE_RISK"


@dataclass(frozen=True, slots=True)
class PortfolioContractError(Exception):
    reason: str

    def __str__(self) -> str:
        return self.reason


@dataclass(frozen=True, slots=True)
class PortfolioConfig:
    initial_cash: float
    maximum_exposure: float
    minimum_cash_reserve: float
    maximum_slots: int
    slot_notional: float

    @classmethod
    def registered(cls) -> PortfolioConfig:
        return cls(60_000_000.0, 50_000_000.0, 10_000_000.0, 10, 5_000_000.0)

    def __post_init__(self) -> None:
        if min(self.initial_cash, self.maximum_exposure, self.slot_notional) <= 0:
            raise PortfolioContractError("cash, exposure, and slot notional must be positive")
        if self.minimum_cash_reserve < 0 or self.maximum_slots < 1:
            raise PortfolioContractError("reserve and slot limit are invalid")
        if self.maximum_exposure + self.minimum_cash_reserve > self.initial_cash:
            raise PortfolioContractError("exposure plus reserve exceeds initial cash")


@dataclass(frozen=True, slots=True)
class MarketQuote:
    code: str
    execution_price: float
    mark_price: float
    rank: float

    def __post_init__(self) -> None:
        validate_stock_code(self.code)
        if self.execution_price <= 0 or self.mark_price <= 0:
            raise PortfolioContractError("quote prices must be positive")


@dataclass(frozen=True, slots=True)
class Position:
    code: str
    units: int
    average_price: float
    last_price: float
    opened_step: int


@dataclass(frozen=True, slots=True)
class PortfolioState:
    cash: float
    positions: tuple[Position, ...]
    nav: float
    peak_nav: float
    step_index: int

    @classmethod
    def initial(cls, config: PortfolioConfig) -> PortfolioState:
        return cls(config.initial_cash, (), config.initial_cash, config.initial_cash, 0)

    @property
    def market_value(self) -> float:
        return sum(position.units * position.last_price for position in self.positions)

    @property
    def drawdown(self) -> float:
        return 1.0 - self.nav / self.peak_nav


@dataclass(frozen=True, slots=True)
class PortfolioAction:
    kind: ActionKind
    source_code: str | None = None
    target_code: str | None = None


@dataclass(frozen=True, slots=True)
class PortfolioStep:
    state: PortfolioState
    action: PortfolioAction
    action_applied: bool
    transaction_cost: float
    turnover: float
    reward: float


def step_portfolio(
    state: PortfolioState,
    action: PortfolioAction,
    quotes: tuple[MarketQuote, ...],
    config: PortfolioConfig,
    costs: CostContract,
) -> PortfolioStep:
    quote_by_code = {quote.code: quote for quote in quotes}
    positions = list(state.positions)
    cash = state.cash
    transaction_cost = 0.0
    traded_notional = 0.0
    applied = False
    if action.kind in (ActionKind.EXIT_ONE, ActionKind.REDUCE_RISK, ActionKind.REPLACE_ONE):
        cash, positions, sell_cost, sell_notional, sold = _sell(
            cash, positions, action.source_code, quote_by_code, costs
        )
        transaction_cost += sell_cost
        traded_notional += sell_notional
        applied = applied or sold
    if action.kind in (ActionKind.ADD_ONE, ActionKind.REPLACE_ONE):
        cash, positions, buy_cost, buy_notional, bought = _buy(
            cash, positions, action.target_code, quote_by_code, config, costs, state.step_index
        )
        transaction_cost += buy_cost
        traded_notional += buy_notional
        applied = applied or bought
    marked = tuple(
        Position(
            position.code,
            position.units,
            position.average_price,
            _quote(quote_by_code, position.code).mark_price,
            position.opened_step,
        )
        for position in sorted(positions, key=lambda item: item.code)
    )
    nav = cash + sum(position.units * position.last_price for position in marked)
    peak = max(state.peak_nav, nav)
    next_state = PortfolioState(cash, marked, nav, peak, state.step_index + 1)
    if next_state.market_value > config.maximum_exposure + 1e-6:
        raise PortfolioContractError("maximum exposure breached")
    if next_state.cash < config.minimum_cash_reserve - 1e-6:
        raise PortfolioContractError("minimum cash reserve breached")
    reward = math.log(nav / state.nav) if nav > 0 and state.nav > 0 else float("-inf")
    turnover = traded_notional / state.nav if state.nav > 0 else 0.0
    return PortfolioStep(next_state, action, applied, transaction_cost, turnover, reward)


def _sell(
    cash: float,
    positions: list[Position],
    code: str | None,
    quotes: Mapping[str, MarketQuote],
    costs: CostContract,
) -> tuple[float, list[Position], float, float, bool]:
    if code is None:
        return cash, positions, 0.0, 0.0, False
    matching = next((position for position in positions if position.code == code), None)
    if matching is None:
        return cash, positions, 0.0, 0.0, False
    notional = matching.units * _quote(quotes, code).execution_price
    transaction_cost = costs.cost_for_sell(notional)
    remaining = [position for position in positions if position.code != code]
    return cash + notional - transaction_cost, remaining, transaction_cost, notional, True


def _buy(
    cash: float,
    positions: list[Position],
    code: str | None,
    quotes: Mapping[str, MarketQuote],
    config: PortfolioConfig,
    costs: CostContract,
    step_index: int,
) -> tuple[float, list[Position], float, float, bool]:
    if code is None or any(position.code == code for position in positions):
        return cash, positions, 0.0, 0.0, False
    if len(positions) >= config.maximum_slots:
        return cash, positions, 0.0, 0.0, False
    price = _quote(quotes, code).execution_price
    affordable = max(0.0, cash - config.minimum_cash_reserve)
    budget = min(config.slot_notional, affordable)
    unit_cost = price * (1.0 + costs.buy_total_percent / 100.0)
    units = int(budget // unit_cost)
    if units < 1:
        return cash, positions, 0.0, 0.0, False
    notional = units * price
    transaction_cost = costs.cost_for_buy(notional)
    position = Position(code, units, price, price, step_index)
    return cash - notional - transaction_cost, positions + [position], transaction_cost, notional, True


def _quote(quotes: Mapping[str, MarketQuote], code: str) -> MarketQuote:
    try:
        return quotes[code]
    except KeyError as error:
        raise PortfolioContractError(f"missing quote for {code}") from error
