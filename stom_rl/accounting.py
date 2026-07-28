"""Shared portfolio accounting primitives for STOM RL.

The portfolio pages use one source of truth for cash, holdings, NAV, and trade
costs.  The module is intentionally small and deterministic so the single
symbol environment, portfolio environment, risk gate, and paper replay can all
share the same invariants without introducing a broker dependency.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Dict, Mapping, Optional
from .v5_accounting import BP_DENOMINATOR, public_money, to_decimal




FLOAT_TOLERANCE = 1e-8
LEGACY_SCALAR_COST_MODEL = "legacy_scalar_per_fill"
LEGACY_SCALAR_ACCOUNTING_HORIZON = "SB3_LEGACY_SCALAR_PER_FILL_V0"
V5_SIDE_COMPONENT_COST_MODEL = "v5_side_components"

_COMPONENT_ATTRS = (
    "sell_tax_bps",
    "buy_commission_bps",
    "sell_commission_bps",
    "buy_slippage_bps",
    "sell_slippage_bps",
)




def _component_amount(gross_value: float, bp: float) -> float:
    return public_money((to_decimal(gross_value, "gross_value") * to_decimal(bp, "component_bp")) / BP_DENOMINATOR)


def _money_sum(values: Mapping[str, float]) -> float:
    total = Decimal("0")
    for value in values.values():
        total += to_decimal(value, "component_cost")
    return public_money(total)



@dataclass
class PositionLot:
    """Long-only position state for one symbol."""

    symbol: str
    quantity: float = 0.0
    average_price: float = 0.0

    def market_value(self, price: float) -> float:
        return float(self.quantity) * float(price)

    def to_dict(self, price: Optional[float] = None) -> Dict[str, float | str]:
        payload: Dict[str, float | str] = {
            "symbol": self.symbol,
            "quantity": float(self.quantity),
            "average_price": float(self.average_price),
        }
        if price is not None:
            payload["market_price"] = float(price)
            payload["market_value"] = self.market_value(float(price))
            payload["unrealized_pnl"] = (float(price) - self.average_price) * self.quantity
        return payload


@dataclass(frozen=True)
class TradeFill:
    """Executed trade record with explicit cost/slippage accounting."""

    timestamp: str
    symbol: str
    side: str
    price: float
    quantity: float
    gross_value: float
    cost: float
    cash_after: float
    realized_pnl: float = 0.0
    cost_scenario_id: str = LEGACY_SCALAR_COST_MODEL
    cost_model: str = LEGACY_SCALAR_COST_MODEL
    accounting_horizon: str = LEGACY_SCALAR_ACCOUNTING_HORIZON
    cost_application_count: int = 1
    sell_tax_bp: float = 0.0
    buy_commission_bp: float = 0.0
    sell_commission_bp: float = 0.0
    buy_slippage_bp: float = 0.0
    sell_slippage_bp: float = 0.0
    sell_tax_krw: float = 0.0
    buy_commission_krw: float = 0.0
    sell_commission_krw: float = 0.0
    buy_slippage_krw: float = 0.0
    sell_slippage_krw: float = 0.0
    total_cost_krw: float = 0.0


    def to_dict(self) -> Dict[str, object]:

        return asdict(self)


@dataclass
class PortfolioAccount:
    """Long-only cash account with explicit NAV invariants.

    Costs are applied exactly once per fill. Legacy scalar accounts charge
    ``cost_bps + slippage_bps`` per side; V5 component accounts charge the exact
    side component schedule supplied by the caller.

    unsupported; buy orders that would make cash negative are rejected.
    """

    initial_cash: float = 1_000_000.0
    cost_bps: float = 25.0
    slippage_bps: float = 0.0
    cost_scenario_id: Optional[str] = None
    cost_model: str = LEGACY_SCALAR_COST_MODEL
    accounting_horizon: str = LEGACY_SCALAR_ACCOUNTING_HORIZON
    sell_tax_bps: Optional[float] = None
    buy_commission_bps: Optional[float] = None
    sell_commission_bps: Optional[float] = None
    buy_slippage_bps: Optional[float] = None
    sell_slippage_bps: Optional[float] = None

    cash: Optional[float] = None
    positions: Dict[str, PositionLot] = field(default_factory=dict)
    realized_pnl: float = 0.0
    trade_count: int = 0

    def __post_init__(self) -> None:
        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        if self.cash is None:
            self.cash = float(self.initial_cash)
        if self.cash < -FLOAT_TOLERANCE:
            raise ValueError("cash cannot be negative")
        if self.cost_bps < 0 or self.slippage_bps < 0:
            raise ValueError("cost_bps and slippage_bps must be non-negative")
        if self._has_side_component_schedule():
            missing = [name for name in _COMPONENT_ATTRS if getattr(self, name) is None]
            if missing:
                raise ValueError(f"side component cost schedule is incomplete: {missing}")
        for label, value in self._component_bps().items():
            if value < 0:
                raise ValueError(f"{label}_bp must be non-negative")


    @property
    def buy_cost_pct(self) -> float:
        bps = self._component_bps()
        return (bps["buy_commission"] + bps["buy_slippage"]) / 10_000.0

    @property
    def sell_cost_pct(self) -> float:
        bps = self._component_bps()
        return (bps["sell_tax"] + bps["sell_commission"] + bps["sell_slippage"]) / 10_000.0

    @property
    def cost_pct(self) -> float:
        """Backward-compatible alias for the buy-side cash reservation rate."""

        return self.buy_cost_pct

    @property
    def effective_cost_scenario_id(self) -> str:
        return str(self.cost_scenario_id or self.cost_model)

    def _has_side_component_schedule(self) -> bool:
        return any(getattr(self, name) is not None for name in _COMPONENT_ATTRS)

    def _component_bps(self) -> Dict[str, float]:
        if self._has_side_component_schedule():
            return {
                "sell_tax": float(self.sell_tax_bps or 0.0),
                "buy_commission": float(self.buy_commission_bps or 0.0),
                "sell_commission": float(self.sell_commission_bps or 0.0),
                "buy_slippage": float(self.buy_slippage_bps or 0.0),
                "sell_slippage": float(self.sell_slippage_bps or 0.0),
            }
        return {
            "sell_tax": 0.0,
            "buy_commission": float(self.cost_bps),
            "sell_commission": float(self.cost_bps),
            "buy_slippage": float(self.slippage_bps),
            "sell_slippage": float(self.slippage_bps),
        }

    def cost_component_bps(self) -> Dict[str, float]:
        bps = self._component_bps()
        return {
            "sell_tax_bp": bps["sell_tax"],
            "buy_commission_bp": bps["buy_commission"],
            "sell_commission_bp": bps["sell_commission"],
            "buy_slippage_bp": bps["buy_slippage"],
            "sell_slippage_bp": bps["sell_slippage"],
        }

    def _fill_cost_details(self, side: str, gross_value: float) -> Dict[str, float | int | str]:
        bps = self._component_bps()
        amounts = {
            "sell_tax_krw": 0.0,
            "buy_commission_krw": 0.0,
            "sell_commission_krw": 0.0,
            "buy_slippage_krw": 0.0,
            "sell_slippage_krw": 0.0,
        }
        if side == "buy":
            amounts["buy_commission_krw"] = _component_amount(gross_value, bps["buy_commission"])
            amounts["buy_slippage_krw"] = _component_amount(gross_value, bps["buy_slippage"])
        elif side == "sell":
            amounts["sell_tax_krw"] = _component_amount(gross_value, bps["sell_tax"])
            amounts["sell_commission_krw"] = _component_amount(gross_value, bps["sell_commission"])
            amounts["sell_slippage_krw"] = _component_amount(gross_value, bps["sell_slippage"])
        else:
            raise ValueError(f"unsupported side for cost details: {side}")
        return {
            "cost_scenario_id": self.effective_cost_scenario_id,
            "cost_model": str(self.cost_model),
            "accounting_horizon": str(self.accounting_horizon),
            "cost_application_count": 1,
            **self.cost_component_bps(),
            **amounts,
            "total_cost_krw": _money_sum(amounts),
        }


    def clone(self) -> "PortfolioAccount":
        return PortfolioAccount(
            initial_cash=float(self.initial_cash),
            cost_bps=float(self.cost_bps),
            slippage_bps=float(self.slippage_bps),
            cash=float(self.cash or 0.0),
            positions={symbol: PositionLot(pos.symbol, pos.quantity, pos.average_price) for symbol, pos in self.positions.items()},
            realized_pnl=float(self.realized_pnl),
            trade_count=int(self.trade_count),
            cost_scenario_id=self.cost_scenario_id,
            cost_model=str(self.cost_model),
            accounting_horizon=str(self.accounting_horizon),
            sell_tax_bps=self.sell_tax_bps,
            buy_commission_bps=self.buy_commission_bps,
            sell_commission_bps=self.sell_commission_bps,
            buy_slippage_bps=self.buy_slippage_bps,
            sell_slippage_bps=self.sell_slippage_bps,
        )

    def position(self, symbol: str) -> PositionLot:
        return self.positions.get(str(symbol), PositionLot(str(symbol)))

    def holdings_value(self, prices: Mapping[str, float]) -> float:
        value = 0.0
        for symbol, position in self.positions.items():
            if position.quantity <= FLOAT_TOLERANCE:
                continue
            if symbol not in prices:
                raise KeyError(f"Missing mark price for held symbol: {symbol}")
            value += position.market_value(float(prices[symbol]))
        return float(value)

    def nav(self, prices: Mapping[str, float]) -> float:
        return float(self.cash or 0.0) + self.holdings_value(prices)

    def assert_invariants(self, prices: Mapping[str, float]) -> None:
        if (self.cash or 0.0) < -FLOAT_TOLERANCE:
            raise AssertionError(f"cash is negative: {self.cash}")
        for symbol, position in self.positions.items():
            if position.quantity < -FLOAT_TOLERANCE:
                raise AssertionError(f"{symbol} quantity is negative: {position.quantity}")
            if position.quantity > FLOAT_TOLERANCE and position.average_price <= 0:
                raise AssertionError(f"{symbol} average_price must be positive")
        expected_nav = float(self.cash or 0.0) + self.holdings_value(prices)
        actual_nav = self.nav(prices)
        if abs(actual_nav - expected_nav) > FLOAT_TOLERANCE:
            raise AssertionError(f"NAV drift: actual={actual_nav}, expected={expected_nav}")

    def buy(
        self,
        *,
        symbol: str,
        price: float,
        quantity: Optional[float] = None,
        notional: Optional[float] = None,
        timestamp: str = "",
    ) -> TradeFill:
        symbol = str(symbol)
        price = float(price)
        if price <= 0:
            raise ValueError("price must be positive")
        if quantity is None:
            if notional is None:
                raise ValueError("quantity or notional is required")
            quantity = float(notional) / price
        quantity = float(quantity)
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        gross = price * quantity
        cost_details = self._fill_cost_details("buy", gross)
        cost = float(cost_details["total_cost_krw"])
        cash_needed = gross + cost

        if cash_needed > float(self.cash or 0.0) + FLOAT_TOLERANCE:
            raise ValueError("buy would make cash negative")

        previous = self.positions.get(symbol, PositionLot(symbol))
        new_qty = previous.quantity + quantity
        new_avg = ((previous.quantity * previous.average_price) + gross) / new_qty
        self.positions[symbol] = PositionLot(symbol=symbol, quantity=float(new_qty), average_price=float(new_avg))
        self.cash = float(self.cash or 0.0) - cash_needed
        self.trade_count += 1
        return TradeFill(
            timestamp=timestamp,
            symbol=symbol,
            side="buy",
            price=price,
            quantity=quantity,
            gross_value=gross,
            cost=cost,
            cash_after=float(self.cash),
            **cost_details,

        )

    def sell(
        self,
        *,
        symbol: str,
        price: float,
        quantity: Optional[float] = None,
        timestamp: str = "",
    ) -> TradeFill:
        symbol = str(symbol)
        price = float(price)
        if price <= 0:
            raise ValueError("price must be positive")
        position = self.positions.get(symbol)
        if position is None or position.quantity <= FLOAT_TOLERANCE:
            raise ValueError(f"no position to sell for {symbol}")
        sell_qty = position.quantity if quantity is None else float(quantity)
        if sell_qty <= 0:
            raise ValueError("quantity must be positive")
        if sell_qty > position.quantity + FLOAT_TOLERANCE:
            raise ValueError("sell quantity exceeds position quantity")

        sell_qty = min(sell_qty, position.quantity)
        gross = price * sell_qty
        cost_details = self._fill_cost_details("sell", gross)
        cost = float(cost_details["total_cost_krw"])
        realized = (price - position.average_price) * sell_qty - cost
        self.cash = float(self.cash or 0.0) + gross - cost

        remaining = position.quantity - sell_qty
        if remaining <= FLOAT_TOLERANCE:
            self.positions.pop(symbol, None)
        else:
            self.positions[symbol] = PositionLot(symbol=symbol, quantity=float(remaining), average_price=position.average_price)
        self.realized_pnl += realized
        self.trade_count += 1
        return TradeFill(
            timestamp=timestamp,
            symbol=symbol,
            side="sell",
            price=price,
            quantity=sell_qty,
            gross_value=gross,
            cost=cost,
            cash_after=float(self.cash),
            realized_pnl=realized,
            **cost_details,
        )

    def snapshot(self, prices: Mapping[str, float]) -> Dict[str, object]:
        return {
            "cash": float(self.cash or 0.0),
            "holdings_value": self.holdings_value(prices),
            "nav": self.nav(prices),
            "realized_pnl": float(self.realized_pnl),
            "trade_count": int(self.trade_count),
            "positions": [position.to_dict(prices.get(symbol)) for symbol, position in sorted(self.positions.items())],
        }
