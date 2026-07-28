"""Decimal-backed additive accounting for Type 1 research sessions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Context, Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
import re
from typing import Iterable

from stom_rl.daily_type1_contract import (
    COST_SCENARIOS_BP,
    INITIAL_NAV_KRW,
    MAX_SLOTS,
    REWARD_QUANTUM,
    SLOT_NOTIONAL_KRW,
)

_ZERO = Decimal("0")
_BASIS_POINTS = Decimal("10000")
_MONEY_QUANTUM = Decimal("0.000001")
_RETURN_QUANTUM = REWARD_QUANTUM
_ACCOUNTING_CONTEXT = Context(prec=50, rounding=ROUND_HALF_EVEN)
_SYMBOL_RE = re.compile(r"^\d{6}$")


def _decimal(value: Decimal | int | str, *, field: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError(f"{field} must be a finite Decimal, int, or string")
    try:
        result = value if isinstance(value, Decimal) else Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} is malformed") from exc
    if not result.is_finite():
        raise ValueError(f"{field} must be finite")
    return result


def _quantize(value: Decimal, quantum: Decimal) -> Decimal:
    """Quantize at a public accounting boundary under the frozen context."""
    with localcontext(_ACCOUNTING_CONTEXT):
        return value.quantize(quantum)


def _money(value: Decimal) -> Decimal:
    return _quantize(value, _MONEY_QUANTUM)


def _return(value: Decimal) -> Decimal:
    return _quantize(value, _RETURN_QUANTUM)


def _cost_bp(value: Decimal | int | str) -> Decimal:
    result = _decimal(value, field="cost_bp")
    if result not in {Decimal(item) for item in COST_SCENARIOS_BP}:
        raise ValueError("cost_bp must be one of 0, 23, or 46")
    return _return(result)


@dataclass(frozen=True)
class PortfolioState:
    """Research NAV state at a completed session boundary."""

    nav: Decimal = Decimal(INITIAL_NAV_KRW)
    high_water_nav: Decimal = Decimal(INITIAL_NAV_KRW)

    def __post_init__(self) -> None:
        nav = _money(_decimal(self.nav, field="nav"))
        high_water_nav = _money(_decimal(self.high_water_nav, field="high_water_nav"))
        if high_water_nav <= _ZERO:
            raise ValueError("high_water_nav must be positive")
        if high_water_nav < nav:
            raise ValueError("high_water_nav must be at least nav")
        object.__setattr__(self, "nav", nav)
        object.__setattr__(self, "high_water_nav", high_water_nav)

    @property
    def drawdown(self) -> Decimal:
        """Current peak-to-trough loss as a fraction of the high-water NAV."""
        with localcontext(_ACCOUNTING_CONTEXT):
            return _return((self.high_water_nav - self.nav) / self.high_water_nav)


@dataclass(frozen=True)
class SlotOutcome:
    """One requested slot's executable outcome; symbols remain strings exactly."""

    symbol: str
    status: str
    gross_return: Decimal = _ZERO

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not _SYMBOL_RE.fullmatch(self.symbol):
            raise ValueError("symbol must be a six-digit string; leading zeros are preserved")
        if self.status not in {"FILLED", "NO_FILL"}:
            raise ValueError("status must be FILLED or NO_FILL")
        gross_return = _decimal(self.gross_return, field="gross_return")
        if self.status == "NO_FILL" and gross_return != _ZERO:
            raise ValueError("NO_FILL must have zero gross_return")
        object.__setattr__(self, "gross_return", _return(gross_return))


@dataclass(frozen=True)
class Settlement:
    """Immutable result of settling a complete Type 1 session."""

    prior_state: PortfolioState
    state: PortfolioState
    outcomes: tuple[SlotOutcome, ...]
    cost_bp: Decimal
    nav_delta: Decimal
    reward: Decimal
    filled_slots: int
    no_fill_slots: int

    @property
    def drawdown(self) -> Decimal:
        return self.state.drawdown


def settle_session(
    state: PortfolioState,
    outcomes: Iterable[SlotOutcome],
    cost_bp: Decimal | int | str = 23,
) -> Settlement:
    """Settle up to ten requested slots using fixed-notional additive accounting.

    A filled slot contributes ``5,000,000 * (gross_return - cost_bp / 10,000)``.
    A no-fill contributes zero and pays no cost. Money and NAV are quantized to
    six decimals; returns, costs, drawdown, and reward use twelve decimals.
    """
    if not isinstance(state, PortfolioState):
        raise TypeError("state must be a PortfolioState")
    cost = _cost_bp(cost_bp)
    try:
        settled_outcomes = tuple(outcomes)
    except TypeError as exc:
        raise TypeError("outcomes must be iterable") from exc
    if len(settled_outcomes) > MAX_SLOTS:
        raise ValueError("a session may not contain more than 10 slots")
    if not all(isinstance(outcome, SlotOutcome) for outcome in settled_outcomes):
        raise TypeError("outcomes must contain SlotOutcome values")
    symbols = [outcome.symbol for outcome in settled_outcomes]
    if len(set(symbols)) != len(symbols):
        raise ValueError("a session may not contain duplicate symbols")

    with localcontext(_ACCOUNTING_CONTEXT):
        per_filled_cost = _return(cost / _BASIS_POINTS)
        contributions = tuple(
            _money(
                Decimal(SLOT_NOTIONAL_KRW)
                * _return(outcome.gross_return - per_filled_cost)
            )
            for outcome in settled_outcomes
            if outcome.status == "FILLED"
        )
        # Canonical numeric accumulation makes additive P&L independent of slot order.
        nav_delta = _money(sum(sorted(contributions), _ZERO))
        nav = _money(state.nav + nav_delta)
        next_state = PortfolioState(nav=nav, high_water_nav=max(state.high_water_nav, nav))
        reward = _return(nav_delta / Decimal(INITIAL_NAV_KRW))
    filled_slots = sum(outcome.status == "FILLED" for outcome in settled_outcomes)
    no_fill_slots = len(settled_outcomes) - filled_slots
    return Settlement(
        prior_state=state,
        state=next_state,
        outcomes=settled_outcomes,
        cost_bp=cost,
        nav_delta=nav_delta,
        reward=reward,
        filled_slots=filled_slots,
        no_fill_slots=no_fill_slots,
    )
