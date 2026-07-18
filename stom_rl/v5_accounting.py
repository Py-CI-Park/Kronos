"""Decimal accounting oracle for Kronos V5 close-slot research ledgers.

This module is a research-only accounting surface. It does not authorize live,
broker, account, order, paper-forward, model-build, profitability, GO, or
readiness claims.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_HALF_UP
from typing import Any, Final, Iterable, Mapping, Sequence

ACCOUNTING_SCHEMA_VERSION: Final = 1
ACCOUNTING_HORIZON_ID: Final = "CS_T_CLOSE_TO_T1_CLOSE_V1"
TERMINAL_LIQUIDATION: Final = "explicit_t1_close"
CARRY_ALLOWED: Final = False
ROUNDING_MODE: Final = "ROUND_HALF_UP"

COST_SCENARIO_ZERO_CONTROL_0BP: Final = "zero_control_0bp"
COST_SCENARIO_BASE_23BP: Final = "base_23bp"
COST_SCENARIO_STRESS_46BP: Final = "stress_46bp"
PRIMARY_COST_SCENARIO_ID: Final = COST_SCENARIO_BASE_23BP

DEFAULT_TOTAL_CAPITAL_KRW: Final = 1_000_000
CANONICAL_MAX_POSITIONS: Final = 2
CANONICAL_POSITION_FRACTION: Final = Decimal("0.25")
CANONICAL_MAX_GROSS_FRACTION: Final = Decimal("0.50")

MONEY_QUANT: Final = Decimal("0.000001")
RATIO_QUANT: Final = Decimal("0.000000000001")
BP_DENOMINATOR: Final = Decimal("10000")
FILL_MODE: Final = "close_to_next_close_research_label"

V51_ACCOUNTING_SCHEMA_VERSION: Final = "kronos_v51_slot_accounting.v1"
V51_PRICE_BASIS: Final = "15:20_bar_close_proxy"
V51_CAUSAL_CUTOFF_KST: Final = "15:20:00"
V51_TOTAL_CAPITAL_KRW: Final = Decimal("60000000")
V51_SLOT_COUNT: Final = 10
V51_SLOT_BUY_BUDGET_KRW: Final = Decimal("5000000")
V51_MAX_DEPLOYED_PRINCIPAL_KRW: Final = Decimal("50000000")
V51_RESERVE_KRW: Final = Decimal("10000000")
V51_FILL_MODE: Final = "exact_1520_proxy_fixed_horizon_research_label"
V51_SOURCE_MARK_SCHEMA_VERSION: Final = "kronos_daily_1520_source.v1"
V51_SUPPORTED_HORIZON_IDS: Final = ("H1", "H3", "H5")
V51_HORIZON_DAYS: Final[dict[str, int]] = {"H1": 1, "H3": 3, "H5": 5}
V51_HORIZON_LABELS: Final[dict[str, str]] = {
    "H1": "future_return_h1_1520_proxy",
    "H3": "future_return_h3_1520_proxy",
    "H5": "future_return_h5_1520_proxy",
}
V51_COST_SCENARIO_IDS: Final = (
    COST_SCENARIO_ZERO_CONTROL_0BP,
    COST_SCENARIO_BASE_23BP,
    COST_SCENARIO_STRESS_46BP,
)
V51_PRIMARY_COST_SCENARIO_ID: Final = COST_SCENARIO_BASE_23BP
V51_FALSE_LOCKS: Final[dict[str, bool]] = {
    "official_close": False,
    "full_day_daily_ohlcv": False,
    "live_trading": False,
    "profit_claim": False,
    "paper_trading": False,
    "broker_integration": False,
}
V51_PROMOTION_CLAIMS: Final[dict[str, bool]] = {
    "live_trading": False,
    "profit": False,
    "paper_trading": False,
    "broker_integration": False,
}
_V51_FORBIDDEN_ROW_FIELDS: Final = frozenset(
    {
        "future_return_1d",
        "legacy_future_return_1d",
        "future_direction_1d",
        "future_rank_pct_1d",
        "code",
        "entry_mark",
        "entry_close",
        "entry_price",
        "entry_price_1520_close_proxy",
        "exit_mark",
        "exit_1520",
        "exit_close",
        "exit_price",
        "next_close",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "daily_open",
        "daily_high",
        "daily_low",
        "daily_close",
        "daily_volume",
        "daily_amount",
        "full_day_daily_ohlcv",
        "daily_ohlcv",
    }
)


@dataclass(frozen=True)
class V5CostScenario:
    scenario_id: str
    sell_tax_bp: Decimal
    buy_commission_bp: Decimal
    sell_commission_bp: Decimal
    buy_slippage_bp: Decimal
    sell_slippage_bp: Decimal

    @property
    def total_bp(self) -> Decimal:
        return (
            self.sell_tax_bp
            + self.buy_commission_bp
            + self.sell_commission_bp
            + self.buy_slippage_bp
            + self.sell_slippage_bp
        )

    @property
    def buy_cost_bp(self) -> Decimal:
        return self.buy_commission_bp + self.buy_slippage_bp

    @property
    def sell_cost_bp(self) -> Decimal:
        return self.sell_tax_bp + self.sell_commission_bp + self.sell_slippage_bp

    def as_payload(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "sell_tax_bp": public_bp(self.sell_tax_bp),
            "buy_commission_bp": public_bp(self.buy_commission_bp),
            "sell_commission_bp": public_bp(self.sell_commission_bp),
            "buy_slippage_bp": public_bp(self.buy_slippage_bp),
            "sell_slippage_bp": public_bp(self.sell_slippage_bp),
            "total_bp": public_bp(self.total_bp),
        }


def to_decimal(value: Any, label: str = "value") -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{label} must be a finite decimal value")
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError) as exc:
        raise ValueError(f"{label} must be a finite decimal value") from exc
    if not parsed.is_finite():
        raise ValueError(f"{label} must be a finite decimal value")
    return parsed


def positive_decimal(value: Any, label: str) -> Decimal:
    parsed = to_decimal(value, label)
    if parsed <= 0:
        raise ValueError(f"{label} must be positive")
    return parsed


def _positive_quantized_zero(value: Decimal) -> Decimal:
    return value.copy_abs() if value.is_zero() else value


def quantize_money(value: Decimal) -> Decimal:
    return _positive_quantized_zero(value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))


def quantize_ratio(value: Decimal) -> Decimal:
    return _positive_quantized_zero(value.quantize(RATIO_QUANT, rounding=ROUND_HALF_UP))


def public_money(value: Decimal) -> float:
    return float(quantize_money(value))


def public_ratio(value: Decimal) -> float:
    return float(quantize_ratio(value))


def public_bp(value: Decimal) -> int | float:
    normalized = value.normalize()
    if normalized == normalized.to_integral_value():
        return int(normalized)
    return float(normalized)


def _scenario(**kwargs: str) -> V5CostScenario:
    return V5CostScenario(
        scenario_id=kwargs["scenario_id"],
        sell_tax_bp=Decimal(kwargs["sell_tax_bp"]),
        buy_commission_bp=Decimal(kwargs["buy_commission_bp"]),
        sell_commission_bp=Decimal(kwargs["sell_commission_bp"]),
        buy_slippage_bp=Decimal(kwargs["buy_slippage_bp"]),
        sell_slippage_bp=Decimal(kwargs["sell_slippage_bp"]),
    )


COST_SCENARIOS: Final[dict[str, V5CostScenario]] = {
    COST_SCENARIO_ZERO_CONTROL_0BP: _scenario(
        scenario_id=COST_SCENARIO_ZERO_CONTROL_0BP,
        sell_tax_bp="0",
        buy_commission_bp="0",
        sell_commission_bp="0",
        buy_slippage_bp="0",
        sell_slippage_bp="0",
    ),
    COST_SCENARIO_BASE_23BP: _scenario(
        scenario_id=COST_SCENARIO_BASE_23BP,
        sell_tax_bp="20",
        buy_commission_bp="1.5",
        sell_commission_bp="1.5",
        buy_slippage_bp="0",
        sell_slippage_bp="0",
    ),
    COST_SCENARIO_STRESS_46BP: _scenario(
        scenario_id=COST_SCENARIO_STRESS_46BP,
        sell_tax_bp="20",
        buy_commission_bp="1.5",
        sell_commission_bp="1.5",
        buy_slippage_bp="11.5",
        sell_slippage_bp="11.5",
    ),
}


def scenario_for_cost(cost_bp: int | float | Decimal = 23, cost_scenario_id: str | None = None) -> V5CostScenario:
    if cost_scenario_id is not None:
        try:
            return COST_SCENARIOS[str(cost_scenario_id)]
        except KeyError as exc:
            raise ValueError(f"unknown close-slot cost scenario: {cost_scenario_id}") from exc
    total_bp = to_decimal(cost_bp, "cost_bp")
    for scenario in COST_SCENARIOS.values():
        if scenario.total_bp == total_bp:
            return scenario
    raise ValueError(
        "scalar-only close-slot v2 cost accounting is not allowed; "
        f"v5 requires one of {sorted(COST_SCENARIOS)} or a matching sensitivity bp"
    )


def normalize_v5_code(value: Any) -> str:
    if value is None or isinstance(value, bool):
        raise ValueError("code must be a non-negative six-digit-preservable value")
    if isinstance(value, int):
        raw = str(value)
    else:
        raw = str(value).strip()
        if raw and not raw.startswith("-") and not raw.isdigit():
            try:
                parsed = Decimal(raw)
            except InvalidOperation as exc:
                raise ValueError("code must be a non-negative six-digit-preservable value") from exc
            if not parsed.is_finite() or parsed != parsed.to_integral_value() or parsed < 0:
                raise ValueError("code must be a non-negative six-digit-preservable value")
            raw = str(int(parsed))
    if not raw or raw.startswith("-") or not raw.isdigit() or len(raw) > 6:
        raise ValueError("code must be a non-negative six-digit-preservable value")
    code = raw.zfill(6)
    if code == "000000":
        raise ValueError("code must be a non-zero six-digit-preservable value")
    return code


def _validate_horizon(horizon_id: str) -> None:
    if horizon_id != ACCOUNTING_HORIZON_ID:
        raise ValueError(f"unsupported accounting horizon: {horizon_id}")


def _validate_cost_application(row: Mapping[str, Any]) -> None:
    raw = row.get("cost_application_count", row.get("cost_charge_count", 1))
    if isinstance(raw, bool):
        raise ValueError("cost_application_count must be exactly 1")
    try:
        count = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("cost_application_count must be exactly 1") from exc
    if str(raw).strip() not in {"1", "1.0"} and raw != 1:
        raise ValueError("cost_application_count must be exactly 1")
    if count != 1:
        raise ValueError("cost_application_count must be exactly 1")


def _first_present(row: Mapping[str, Any], keys: Sequence[str], label: str) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    raise ValueError(f"{label} is required for {ACCOUNTING_HORIZON_ID}")


def _component_cost(amount: Decimal, bp: Decimal) -> Decimal:
    return quantize_money((amount * bp) / BP_DENOMINATOR)


def _floor_shares(slot_cash: Decimal, entry_close: Decimal, buy_cost_bp: Decimal) -> int:
    effective_unit_cost = entry_close * (Decimal("1") + (buy_cost_bp / BP_DENOMINATOR))
    return int((slot_cash / effective_unit_cost).to_integral_value(rounding=ROUND_FLOOR))


def _lot_payload(
    *,
    slot: int,
    code: str | None,
    status: str,
    unfilled_reason: str | None,
    slot_state: str,
    blocked: bool,
    entry_close: Decimal | None,
    next_close: Decimal | None,
    shares: int,
    slot_cash: Decimal,
    total_capital: Decimal,
    notional: Decimal,
    exit_value: Decimal,
    unused_cash: Decimal,
    gross_pnl: Decimal,
    buy_commission: Decimal,
    buy_slippage: Decimal,
    sell_tax: Decimal,
    sell_commission: Decimal,
    sell_slippage: Decimal,
    cost_total: Decimal,
    net_pnl: Decimal,
    scenario: V5CostScenario,
    fill_mode: str,
) -> dict[str, Any]:
    terminal_nav = quantize_money(slot_cash + net_pnl)
    reward = quantize_ratio(net_pnl / total_capital) if total_capital else Decimal("0")
    return {
        "slot": int(slot),
        "code": code,
        "status": status,
        "unfilled_reason": unfilled_reason,
        "slot_state": slot_state,
        "blocked": bool(blocked),
        "horizon_id": ACCOUNTING_HORIZON_ID,
        "accounting_horizon_id": ACCOUNTING_HORIZON_ID,
        "carry_allowed": CARRY_ALLOWED,
        "terminal_liquidation": TERMINAL_LIQUIDATION,
        "cost_application_count": 1,
        "entry_close": public_money(entry_close) if entry_close is not None else None,
        "next_close": public_money(next_close) if next_close is not None else None,
        "shares": int(shares),
        "slot_cash_krw": public_money(slot_cash),
        "notional_krw": public_money(notional),
        "exit_value_krw": public_money(exit_value),
        "unused_cash_krw": public_money(unused_cash),
        "gross_pnl_krw": public_money(gross_pnl),
        "cost_krw": public_money(cost_total),
        "sell_tax_bp": public_bp(scenario.sell_tax_bp),
        "buy_commission_bp": public_bp(scenario.buy_commission_bp),
        "sell_commission_bp": public_bp(scenario.sell_commission_bp),
        "buy_slippage_bp": public_bp(scenario.buy_slippage_bp),
        "sell_slippage_bp": public_bp(scenario.sell_slippage_bp),
        "buy_commission_krw": public_money(buy_commission),
        "buy_slippage_krw": public_money(buy_slippage),
        "sell_tax_krw": public_money(sell_tax),
        "sell_commission_krw": public_money(sell_commission),
        "sell_slippage_krw": public_money(sell_slippage),
        "total_cost_krw": public_money(cost_total),
        "net_pnl_krw": public_money(net_pnl),
        "net_return_on_total_capital": public_ratio(net_pnl / total_capital) if total_capital else 0.0,
        "terminal_nav_krw": public_money(terminal_nav),
        "reward": float(reward),
        "fill_mode": fill_mode,
    }


def empty_close_slot_lot(
    *,
    slot: int,
    code: Any = None,
    slot_cash_krw: Any,
    total_capital_krw: Any,
    cost_scenario: V5CostScenario,
    reason: str = "EMPTY_SLOT",
    slot_state: str = "cash_hold",
    blocked: bool = False,
    entry_close: Any = None,
    next_close: Any = None,
    fill_mode: str = FILL_MODE,
) -> dict[str, Any]:
    slot_cash = quantize_money(to_decimal(slot_cash_krw, "slot_cash_krw"))
    total_capital = positive_decimal(total_capital_krw, "total_capital_krw")
    normalized_code = normalize_v5_code(code) if code is not None and str(code).strip() else None
    entry = quantize_money(to_decimal(entry_close, "entry_close")) if entry_close is not None else None
    exit_mark = quantize_money(to_decimal(next_close, "next_close")) if next_close is not None else None
    return _lot_payload(
        slot=slot,
        code=normalized_code,
        status="unfilled",
        unfilled_reason=reason,
        slot_state=slot_state,
        blocked=blocked,
        entry_close=entry,
        next_close=exit_mark,
        shares=0,
        slot_cash=slot_cash,
        total_capital=total_capital,
        notional=Decimal("0"),
        exit_value=Decimal("0"),
        unused_cash=slot_cash,
        gross_pnl=Decimal("0"),
        buy_commission=Decimal("0"),
        buy_slippage=Decimal("0"),
        sell_tax=Decimal("0"),
        sell_commission=Decimal("0"),
        sell_slippage=Decimal("0"),
        cost_total=Decimal("0"),
        net_pnl=Decimal("0"),
        scenario=cost_scenario,
        fill_mode=fill_mode,
    )


def account_close_slot_lot(
    *,
    slot: int,
    code: Any,
    entry_close: Any,
    next_close: Any,
    slot_cash_krw: Any,
    total_capital_krw: Any,
    cost_scenario: V5CostScenario,
    fill_mode: str = FILL_MODE,
    horizon_id: str = ACCOUNTING_HORIZON_ID,
) -> dict[str, Any]:
    _validate_horizon(horizon_id)
    normalized_code = normalize_v5_code(code)
    entry = positive_decimal(entry_close, "entry_close")
    exit_mark = positive_decimal(next_close, "next_close")
    slot_cash = quantize_money(to_decimal(slot_cash_krw, "slot_cash_krw"))
    if slot_cash <= 0:
        raise ValueError("slot_cash_krw must be positive")
    total_capital = positive_decimal(total_capital_krw, "total_capital_krw")

    shares = _floor_shares(slot_cash, entry, cost_scenario.buy_cost_bp)
    if shares <= 0:
        return empty_close_slot_lot(
            slot=slot,
            code=normalized_code,
            slot_cash_krw=slot_cash,
            total_capital_krw=total_capital,
            cost_scenario=cost_scenario,
            reason="INSUFFICIENT_SLOT_CASH",
            slot_state="blocked_unfilled",
            blocked=True,
            entry_close=entry,
            next_close=exit_mark,
            fill_mode=fill_mode,
        )

    share_count = Decimal(shares)
    notional = quantize_money(share_count * entry)
    exit_value = quantize_money(share_count * exit_mark)
    gross_pnl = quantize_money(exit_value - notional)
    buy_commission = _component_cost(notional, cost_scenario.buy_commission_bp)
    buy_slippage = _component_cost(notional, cost_scenario.buy_slippage_bp)
    sell_tax = _component_cost(exit_value, cost_scenario.sell_tax_bp)
    sell_commission = _component_cost(exit_value, cost_scenario.sell_commission_bp)
    sell_slippage = _component_cost(exit_value, cost_scenario.sell_slippage_bp)
    cost_total = quantize_money(buy_commission + buy_slippage + sell_tax + sell_commission + sell_slippage)
    net_pnl = quantize_money(gross_pnl - cost_total)
    unused_cash = quantize_money(slot_cash - notional - buy_commission - buy_slippage)
    if unused_cash < 0:
        raise ValueError("buy costs exceed slot cash")

    return _lot_payload(
        slot=slot,
        code=normalized_code,
        status="filled",
        unfilled_reason=None,
        slot_state="filled",
        blocked=False,
        entry_close=entry,
        next_close=exit_mark,
        shares=shares,
        slot_cash=slot_cash,
        total_capital=total_capital,
        notional=notional,
        exit_value=exit_value,
        unused_cash=unused_cash,
        gross_pnl=gross_pnl,
        buy_commission=buy_commission,
        buy_slippage=buy_slippage,
        sell_tax=sell_tax,
        sell_commission=sell_commission,
        sell_slippage=sell_slippage,
        cost_total=cost_total,
        net_pnl=net_pnl,
        scenario=cost_scenario,
        fill_mode=fill_mode,
    )


def _selected_row(row: Mapping[str, Any]) -> dict[str, Any]:
    _validate_cost_application(row)
    code = normalize_v5_code(row.get("code"))
    entry = _first_present(row, ("entry_close", "t_close", "close_t"), "entry_close")
    exit_mark = _first_present(row, ("next_close", "t1_close", "exit_close", "mark_close"), "next_close")
    return {"code": code, "entry_close": entry, "next_close": exit_mark, "source_row": row}


def account_close_to_next_close_v1(
    rows: Sequence[Mapping[str, Any]],
    *,
    total_capital_krw: int | float | Decimal = DEFAULT_TOTAL_CAPITAL_KRW,
    cost_bp: int | float | Decimal = 23,
    cost_scenario_id: str | None = None,
    horizon_id: str = ACCOUNTING_HORIZON_ID,
    max_positions: int = CANONICAL_MAX_POSITIONS,
    position_fraction: Decimal | str | float = CANONICAL_POSITION_FRACTION,
    sort_by_code: bool = True,
    fill_mode: str = FILL_MODE,
) -> dict[str, Any]:
    """Return the canonical max-2 close-to-next-close Decimal ledger.

    The canonical schedule uses 1,000,000 KRW by default, at most two lots,
    25% capital per lot, and the other 50% held as cash. Positions are opened
    at T close and explicitly liquidated at T+1 close; carry is not allowed.
    """

    _validate_horizon(horizon_id)
    if int(max_positions) != CANONICAL_MAX_POSITIONS:
        raise ValueError("canonical close-slot v5 accounting requires max_positions=2")
    fraction = to_decimal(position_fraction, "position_fraction")
    if fraction != CANONICAL_POSITION_FRACTION:
        raise ValueError("canonical close-slot v5 accounting requires position_fraction=0.25")
    total_capital = quantize_money(positive_decimal(total_capital_krw, "total_capital_krw"))
    if total_capital != Decimal(DEFAULT_TOTAL_CAPITAL_KRW):
        raise ValueError("canonical close-slot v5 accounting requires total_capital_krw=1000000")
    cost_scenario = scenario_for_cost(cost_bp, cost_scenario_id)
    slot_cash = quantize_money(total_capital * fraction)
    selected = [_selected_row(row) for row in rows]
    seen_codes: set[str] = set()
    for row in selected:
        code = row["code"]
        if code in seen_codes:
            raise ValueError(f"duplicate selected code: {code}")
        seen_codes.add(code)
    if sort_by_code:
        selected = sorted(selected, key=lambda item: item["code"])
    included = selected[:CANONICAL_MAX_POSITIONS]
    excluded = [row["code"] for row in selected[CANONICAL_MAX_POSITIONS:]]

    ledger: list[dict[str, Any]] = []
    for slot, row in enumerate(included):
        ledger.append(
            account_close_slot_lot(
                slot=slot,
                code=row["code"],
                entry_close=row["entry_close"],
                next_close=row["next_close"],
                slot_cash_krw=slot_cash,
                total_capital_krw=total_capital,
                cost_scenario=cost_scenario,
                fill_mode=fill_mode,
                horizon_id=horizon_id,
            )
        )
    while len(ledger) < CANONICAL_MAX_POSITIONS:
        ledger.append(
            empty_close_slot_lot(
                slot=len(ledger),
                slot_cash_krw=slot_cash,
                total_capital_krw=total_capital,
                cost_scenario=cost_scenario,
                fill_mode=fill_mode,
            )
        )

    allocated_cash = quantize_money(slot_cash * Decimal(CANONICAL_MAX_POSITIONS))
    unallocated_cash = quantize_money(total_capital - allocated_cash)
    gross_pnl_total = sum(to_decimal(row["gross_pnl_krw"], "gross_pnl_krw") for row in ledger)
    cost_total = sum(to_decimal(row["cost_krw"], "cost_krw") for row in ledger)
    net_pnl_total = sum(to_decimal(row["net_pnl_krw"], "net_pnl_krw") for row in ledger)
    terminal_nav = quantize_money(total_capital + net_pnl_total)
    reward = quantize_ratio(net_pnl_total / total_capital)

    return {
        "schema_version": ACCOUNTING_SCHEMA_VERSION,
        "horizon_id": ACCOUNTING_HORIZON_ID,
        "accounting_horizon_id": ACCOUNTING_HORIZON_ID,
        "carry_allowed": CARRY_ALLOWED,
        "terminal_liquidation": TERMINAL_LIQUIDATION,
        "rounding_mode": ROUNDING_MODE,
        "money_quantum": "0.000001",
        "ratio_quantum": "0.000000000001",
        "total_capital_krw": public_money(total_capital),
        "max_positions": CANONICAL_MAX_POSITIONS,
        "position_fraction": public_ratio(fraction),
        "max_gross_fraction": public_ratio(CANONICAL_MAX_GROSS_FRACTION),
        "slot_cash_krw": public_money(slot_cash),
        "allocated_cash_krw": public_money(allocated_cash),
        "unallocated_cash_krw": public_money(unallocated_cash),
        "round_trip_cost_bp": public_bp(cost_scenario.total_bp),
        "round_trip_cost_rate": public_ratio(cost_scenario.total_bp / BP_DENOMINATOR),
        "cost_scenario_id": cost_scenario.scenario_id,
        "cost_scenario": cost_scenario.as_payload(),
        "cost_application_count": 1,
        "filled_slots": sum(1 for row in ledger if row["status"] == "filled"),
        "unfilled_slots": sum(1 for row in ledger if row["status"] != "filled"),
        "blocked_slots": sum(1 for row in ledger if row["blocked"]),
        "gross_pnl_krw": public_money(gross_pnl_total),
        "cost_krw": public_money(cost_total),
        "net_pnl_krw": public_money(net_pnl_total),
        "terminal_nav_krw": public_money(terminal_nav),
        "reward": float(reward),
        "ledger": ledger,
        "diagnostics": {
            "code_order": "zero_padded_6_digit_string_ascending" if sort_by_code else "input_order",
            "excluded_codes_over_max_positions": excluded,
            "selected_count_before_cap": len(selected),
        },
    }


def _v51_money_decimal(value: Decimal) -> str:
    return format(quantize_money(value), "f")


def _v51_ratio_decimal(value: Decimal) -> str:
    return format(quantize_ratio(value), "f")


def _v51_bp_display_percent(value: Decimal) -> str:
    percent = value / Decimal("100")
    two_decimals = percent.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if percent == two_decimals:
        return f"{two_decimals:.2f}%"
    three_decimals = percent.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    return f"{three_decimals:f}%"


def _v51_cost_component_payload(*, bp: Decimal, amount: Decimal) -> dict[str, Any]:
    return {
        "bp": public_bp(bp),
        "display_percent": _v51_bp_display_percent(bp),
        "krw": public_money(amount),
        "krw_decimal": _v51_money_decimal(amount),
    }


def _v51_cost_scenario_payload(scenario: V5CostScenario) -> dict[str, Any]:
    payload = scenario.as_payload()
    payload["total_cost_display_percent"] = _v51_bp_display_percent(scenario.total_bp)
    payload["display_percent"] = payload["total_cost_display_percent"]
    payload["components_display_percent"] = {
        "sell_tax": _v51_bp_display_percent(scenario.sell_tax_bp),
        "buy_commission": _v51_bp_display_percent(scenario.buy_commission_bp),
        "sell_commission": _v51_bp_display_percent(scenario.sell_commission_bp),
        "buy_slippage": _v51_bp_display_percent(scenario.buy_slippage_bp),
        "sell_slippage": _v51_bp_display_percent(scenario.sell_slippage_bp),
    }
    return payload


def _normalize_v51_horizon_id(horizon_id: Any) -> dict[str, Any]:
    if horizon_id is None or isinstance(horizon_id, bool):
        raise ValueError("unsupported V5.1 accounting horizon: missing")
    raw = str(horizon_id).strip()
    upper = raw.upper()
    if upper in V51_SUPPORTED_HORIZON_IDS:
        canonical = upper
    else:
        matches = [key for key, label in V51_HORIZON_LABELS.items() if raw == label]
        if len(matches) != 1:
            raise ValueError(f"unsupported V5.1 accounting horizon: {horizon_id}")
        canonical = matches[0]
    return {
        "horizon_id": canonical,
        "horizon_days": V51_HORIZON_DAYS[canonical],
        "label_column": V51_HORIZON_LABELS[canonical],
    }


def _v51_first_present(row: Mapping[str, Any], keys: Sequence[str], label: str) -> Any:
    for key in keys:
        if key in row and row[key] is not None and row[key] != "":
            return row[key]
    raise ValueError(f"{label} is required for V5.1 slot accounting")


def _v51_validate_session(value: Any, label: str) -> str:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{label} must be an exact YYYY-MM-DD session")
    session = str(value).strip()
    if (
        len(session) != 10
        or session[4] != "-"
        or session[7] != "-"
        or not (session[:4] + session[5:7] + session[8:10]).isdigit()
    ):
        raise ValueError(f"{label} must be an exact YYYY-MM-DD session")
    try:
        date.fromisoformat(session)
    except ValueError as exc:
        raise ValueError(f"{label} must be an exact YYYY-MM-DD session") from exc
    return session


def _v51_required_symbol(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a complete six-digit symbol string")
    symbol = value.strip()
    if len(symbol) != 6 or not symbol.isdigit() or symbol == "000000":
        raise ValueError(f"{label} must be a complete six-digit symbol string")
    return symbol


def _v51_required_sha256(row: Mapping[str, Any], key: str, row_index: int) -> str:
    value = _v51_first_present(row, (key,), key)
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"row {row_index} {key} must be a lowercase 64-character sha256")
    return value


def _v51_required_source_table(value: Any, label: str, *, symbol: str) -> str:
    expected = f"A{symbol}"
    if not isinstance(value, str):
        raise ValueError(f"{label} source_table must match symbol {expected}")
    table = value.strip()
    if table != expected:
        raise ValueError(f"{label} source_table must match symbol {expected}")
    return table


def _v51_exact_timestamp(value: Any, label: str) -> tuple[str, str]:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an exact +09:00 15:20 timestamp")
    timestamp = value.strip()
    if len(timestamp) != 25 or timestamp[10:] != "T15:20:00+09:00":
        raise ValueError(f"{label} must be an exact +09:00 15:20 timestamp")
    session = _v51_validate_session(timestamp[:10], f"{label} session")
    return timestamp, session


def _v51_exact_mark_contract(
    raw: Any,
    *,
    label: str,
    row_index: int,
    symbol: str,
    expected_session: str,
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"row {row_index} {label} must be a structured exact 15:20 mark")
    mark_symbol = _v51_required_symbol(
        _v51_first_present(raw, ("symbol",), f"{label} symbol"),
        f"row {row_index} {label} symbol",
    )
    if mark_symbol != symbol:
        raise ValueError(f"row {row_index} {label} symbol must match row symbol")
    mark_session = _v51_validate_session(
        _v51_first_present(raw, ("session",), f"{label} session"),
        f"row {row_index} {label} session",
    )
    if mark_session != expected_session:
        raise ValueError(f"row {row_index} {label} session must match requested session")
    timestamp, timestamp_session = _v51_exact_timestamp(
        _v51_first_present(raw, ("timestamp",), f"{label} timestamp"),
        f"row {row_index} {label} timestamp",
    )
    timestamp_kst, timestamp_kst_session = _v51_exact_timestamp(
        _v51_first_present(raw, ("timestamp_kst",), f"{label} timestamp_kst"),
        f"row {row_index} {label} timestamp_kst",
    )
    if timestamp != timestamp_kst or timestamp_session != timestamp_kst_session:
        raise ValueError(f"row {row_index} {label} timestamp_kst must match timestamp")
    if timestamp_session != mark_session:
        raise ValueError(f"row {row_index} {label} timestamp must match session")
    compact = _v51_first_present(raw, ("timestamp_yyyymmddhhmm",), f"{label} compact timestamp")
    if not isinstance(compact, str) or compact != f"{mark_session.replace('-', '')}1520":
        raise ValueError(f"row {row_index} {label} compact timestamp must match exact 15:20 session")
    if raw.get("official_close") is not False:
        raise ValueError(f"row {row_index} {label} official_close must be false")
    if raw.get("price_basis") != V51_PRICE_BASIS:
        raise ValueError(f"row {row_index} {label} price_basis must be {V51_PRICE_BASIS}")
    if raw.get("schema_version") != V51_SOURCE_MARK_SCHEMA_VERSION:
        raise ValueError(f"row {row_index} {label} schema_version must be {V51_SOURCE_MARK_SCHEMA_VERSION}")
    source_table = _v51_required_source_table(
        _v51_first_present(raw, ("source_table",), f"{label} source_table"),
        f"row {row_index} {label}",
        symbol=symbol,
    )
    table = _v51_required_source_table(
        _v51_first_present(raw, ("table",), f"{label} table"),
        f"row {row_index} {label} table",
        symbol=symbol,
    )
    if table != source_table:
        raise ValueError(f"row {row_index} {label} table must match source_table")
    price = positive_decimal(
        _v51_first_present(raw, ("price_1520_close_proxy",), f"{label} price_1520_close_proxy"),
        f"{label} price_1520_close_proxy",
    )
    for alias in ("close", "price"):
        if alias in raw and raw[alias] is not None and raw[alias] != "":
            alias_price = positive_decimal(raw[alias], f"{label} {alias}")
            if alias_price != price:
                raise ValueError(f"row {row_index} {label} {alias} must match price_1520_close_proxy")
    return {
        "price": price,
        "session": mark_session,
        "timestamp": timestamp,
        "source_table": source_table,
    }


def _v51_entry_mark(row: Mapping[str, Any], row_index: int, symbol: str, session: str) -> dict[str, Any]:
    raw = _v51_first_present(row, ("entry_1520",), "entry_1520")
    return _v51_exact_mark_contract(
        raw,
        label="entry_1520",
        row_index=row_index,
        symbol=symbol,
        expected_session=session,
    )


def _v51_exit_mark(
    row: Mapping[str, Any],
    horizon: Mapping[str, Any],
    row_index: int,
    symbol: str,
    exit_session: str,
) -> dict[str, Any]:
    label_column = str(horizon["label_column"])
    exits_by_label = row.get("exit_1520_by_label")
    if not isinstance(exits_by_label, Mapping):
        raise ValueError(f"row {row_index} exit_1520_by_label must be a mapping")
    if label_column not in exits_by_label or exits_by_label[label_column] is None:
        raise ValueError(f"row {row_index} exit_1520_by_label must contain requested label {label_column}")
    for key in exits_by_label:
        if str(key) not in V51_HORIZON_LABELS.values():
            raise ValueError(f"row {row_index} exit_1520_by_label contains unsupported label {key}")
    return _v51_exact_mark_contract(
        exits_by_label[label_column],
        label=f"exit_1520_by_label[{label_column}]",
        row_index=row_index,
        symbol=symbol,
        expected_session=exit_session,
    )


def _v51_reject_forbidden_row_fields(row: Mapping[str, Any], row_index: int) -> None:
    for key in row:
        lower = str(key).lower()
        if (
            lower in _V51_FORBIDDEN_ROW_FIELDS
            or lower.startswith("daily_")
            or "daily_ohlcv" in lower
            or "ohlcv_1day" in lower
            or "ohlcv_1d" in lower
        ):
            raise ValueError(
                f"row {row_index} includes forbidden V5.1 accounting input field: {key}"
            )
        if lower in {"short", "is_short"} and bool(row[key]):
            raise ValueError(f"row {row_index} short exposure is unsupported")
        if lower in {"leverage", "leverage_ratio", "margin_multiplier"}:
            leverage = to_decimal(row[key], str(key))
            if leverage not in {Decimal("0"), Decimal("1")}:
                raise ValueError(f"row {row_index} leverage is unsupported")
        if lower in {"is_leveraged", "margin"} and bool(row[key]):
            raise ValueError(f"row {row_index} leverage is unsupported")
    if "official_close" in row and row["official_close"] is not False:
        raise ValueError(f"row {row_index} official_close must be false")
    if "price_basis" in row and row["price_basis"] != V51_PRICE_BASIS:
        raise ValueError(f"row {row_index} price_basis must be {V51_PRICE_BASIS}")


def _v51_validate_row_horizon(row: Mapping[str, Any], horizon: Mapping[str, Any], row_index: int) -> None:
    row_horizon = _normalize_v51_horizon_id(_v51_first_present(row, ("horizon_id",), "horizon_id"))
    if row_horizon["horizon_id"] != str(horizon["horizon_id"]):
        raise ValueError(f"row {row_index} horizon_id must match requested horizon_id")
    label_column = _v51_first_present(row, ("label_column",), "label_column")
    if str(label_column) != str(horizon["label_column"]):
        raise ValueError(f"row {row_index} label_column must match requested horizon_id")
    try:
        horizon_days = int(_v51_first_present(row, ("horizon_days",), "horizon_days"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row_index} horizon_days must be an integer") from exc
    if horizon_days != int(horizon["horizon_days"]):
        raise ValueError(f"row {row_index} horizon_days must match requested horizon_id")


def _v51_side(row: Mapping[str, Any]) -> str:
    raw = _v51_first_present(row, ("side", "order_side"), "side")
    side = str(raw).strip().lower()
    if side not in {"buy", "long"}:
        raise ValueError("side must be buy/long only; sell, short, and leverage are unsupported")
    return "buy"


def _v51_quantity(row: Mapping[str, Any]) -> int:
    raw = _v51_first_present(row, ("quantity", "shares", "share_count"), "quantity")
    quantity = to_decimal(raw, "quantity")
    if quantity <= 0 or quantity != quantity.to_integral_value():
        raise ValueError("quantity must be a positive whole-share integer")
    return int(quantity)


def _v51_source_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Mapping):
        return {str(key): _v51_source_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_v51_source_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _v51_source_hash_payload(row: Mapping[str, Any], row_index: int) -> dict[str, str]:
    return {
        "source_db_sha256": _v51_required_sha256(row, "source_db_sha256", row_index),
        "source_identity_sha256": _v51_required_sha256(row, "source_identity_sha256", row_index),
        "panel_sha256": _v51_required_sha256(row, "panel_sha256", row_index),
    }


def _v51_validate_label_status_if_present(
    row: Mapping[str, Any],
    horizon: Mapping[str, Any],
    row_index: int,
    *,
    entry_session: str,
    exit_session: str,
    entry_timestamp: str,
    exit_timestamp: str,
) -> None:
    statuses = row.get("label_statuses")
    if statuses is None:
        return
    if not isinstance(statuses, Mapping):
        raise ValueError(f"row {row_index} label_statuses must be a mapping")
    label_column = str(horizon["label_column"])
    status = statuses.get(label_column)
    if not isinstance(status, Mapping):
        raise ValueError(f"row {row_index} label_statuses must contain requested label {label_column}")
    if status.get("status") != "available":
        raise ValueError(f"row {row_index} label_statuses requested label must be available")
    try:
        status_horizon_days = int(status.get("horizon_trading_sessions"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row_index} label_statuses horizon must match requested horizon_id") from exc
    if status_horizon_days != int(horizon["horizon_days"]):
        raise ValueError(f"row {row_index} label_statuses horizon must match requested horizon_id")
    if status.get("entry_session") != entry_session or status.get("exit_session") != exit_session:
        raise ValueError(f"row {row_index} label_statuses sessions must match requested horizon_id")
    if status.get("entry_timestamp") != entry_timestamp or status.get("exit_timestamp") != exit_timestamp:
        raise ValueError(f"row {row_index} label_statuses timestamps must match exact marks")
    if status.get("official_close") is not False or status.get("fallback_used") is not False:
        raise ValueError(f"row {row_index} label_statuses must be 15:20 proxy with no fallback")


def _v51_source_payload(
    row: Mapping[str, Any],
    row_index: int,
    symbol: str,
    entry_mark: Mapping[str, Any],
    exit_mark: Mapping[str, Any],
    source_hashes: Mapping[str, str],
) -> dict[str, Any]:
    expected_source_table = f"A{symbol}"
    source: dict[str, Any] = {
        "session": _v51_source_value(row["session"]),
        "exit_session": _v51_source_value(row["exit_session"]),
        "source_table": expected_source_table,
        "entry_source_table": entry_mark["source_table"],
        "exit_source_table": exit_mark["source_table"],
        **dict(source_hashes),
    }
    if row.get("entry_session") is not None:
        source["entry_session"] = _v51_source_value(row["entry_session"])
    for key in ("source_table", "entry_source_table", "exit_source_table"):
        if row.get(key) is not None:
            source[key] = _v51_required_source_table(row[key], f"row {row_index} {key}", symbol=symbol)
    for key in ("source_path", "source_db_path", "panel_row_sha256"):
        if row.get(key) is not None:
            source[key] = _v51_source_value(row[key])
    return source


def _v51_normalized_selections(rows: Iterable[Any], horizon: Mapping[str, Any]) -> list[dict[str, Any]]:
    if isinstance(rows, (str, bytes, Mapping)):
        raise ValueError("rows must be a collection of selected V5.1 accounting rows")
    try:
        raw_rows = list(rows)
    except TypeError as exc:
        raise ValueError("rows must be a collection of selected V5.1 accounting rows") from exc
    if len(raw_rows) > V51_SLOT_COUNT:
        raise ValueError("V5.1 slot accounting accepts at most 10 selections")
    selected: list[dict[str, Any]] = []
    seen_symbols: set[str] = set()
    for row_index, raw_row in enumerate(raw_rows):
        if not isinstance(raw_row, Mapping):
            raise ValueError(f"row {row_index} must be a mapping")
        _v51_reject_forbidden_row_fields(raw_row, row_index)
        _v51_validate_row_horizon(raw_row, horizon, row_index)
        symbol = _v51_required_symbol(_v51_first_present(raw_row, ("symbol",), "symbol"), f"row {row_index} symbol")
        if symbol in seen_symbols:
            raise ValueError(f"duplicate selected symbol: {symbol}")
        seen_symbols.add(symbol)
        session = _v51_validate_session(_v51_first_present(raw_row, ("session",), "session"), f"row {row_index} session")
        if raw_row.get("entry_session") is not None:
            entry_session = _v51_validate_session(raw_row["entry_session"], f"row {row_index} entry_session")
            if entry_session != session:
                raise ValueError(f"row {row_index} entry_session must match session")
        exit_session = _v51_validate_session(
            _v51_first_present(raw_row, ("exit_session",), "exit_session"),
            f"row {row_index} exit_session",
        )
        source_hashes = _v51_source_hash_payload(raw_row, row_index)
        entry_mark = _v51_entry_mark(raw_row, row_index, symbol, session)
        exit_mark = _v51_exit_mark(raw_row, horizon, row_index, symbol, exit_session)
        _v51_validate_label_status_if_present(
            raw_row,
            horizon,
            row_index,
            entry_session=session,
            exit_session=exit_session,
            entry_timestamp=str(entry_mark["timestamp"]),
            exit_timestamp=str(exit_mark["timestamp"]),
        )
        selected.append(
            {
                "slot": row_index,
                "symbol": symbol,
                "side": _v51_side(raw_row),
                "quantity": _v51_quantity(raw_row),
                "entry_mark": entry_mark["price"],
                "exit_mark": exit_mark["price"],
                "source": _v51_source_payload(
                    raw_row,
                    row_index,
                    symbol,
                    entry_mark,
                    exit_mark,
                    source_hashes,
                ),
            }
        )
    return selected


def _v51_empty_slot_payload(
    *,
    slot: int,
    scenario: V5CostScenario,
    horizon: Mapping[str, Any],
) -> dict[str, Any]:
    zero = Decimal("0")
    components = {
        "buy_commission": _v51_cost_component_payload(bp=scenario.buy_commission_bp, amount=zero),
        "buy_slippage": _v51_cost_component_payload(bp=scenario.buy_slippage_bp, amount=zero),
        "sell_tax": _v51_cost_component_payload(bp=scenario.sell_tax_bp, amount=zero),
        "sell_commission": _v51_cost_component_payload(bp=scenario.sell_commission_bp, amount=zero),
        "sell_slippage": _v51_cost_component_payload(bp=scenario.sell_slippage_bp, amount=zero),
    }
    return {
        "slot": int(slot),
        "symbol": None,
        "code": None,
        "side": None,
        "quantity": 0,
        "status": "unfilled",
        "unfilled_reason": "EMPTY_SLOT",
        "slot_state": "cash_hold",
        "blocked": False,
        "horizon_id": horizon["horizon_id"],
        "horizon_days": horizon["horizon_days"],
        "label_column": horizon["label_column"],
        "price_basis": V51_PRICE_BASIS,
        "official_close": False,
        "causal_cutoff_kst": V51_CAUSAL_CUTOFF_KST,
        "cost_scenario_id": scenario.scenario_id,
        "cost_application_count": 1,
        "entry_mark_krw": None,
        "entry_mark_krw_decimal": None,
        "exit_mark_krw": None,
        "exit_mark_krw_decimal": None,
        "slot_buy_budget_krw": public_money(V51_SLOT_BUY_BUDGET_KRW),
        "slot_buy_budget_krw_decimal": _v51_money_decimal(V51_SLOT_BUY_BUDGET_KRW),
        "notional_krw": 0.0,
        "notional_krw_decimal": _v51_money_decimal(zero),
        "deployed_principal_krw": 0.0,
        "deployed_principal_krw_decimal": _v51_money_decimal(zero),
        "buy_side_cost_krw": 0.0,
        "buy_side_cost_krw_decimal": _v51_money_decimal(zero),
        "budget_used_krw": 0.0,
        "budget_used_krw_decimal": _v51_money_decimal(zero),
        "unused_cash_krw": public_money(V51_SLOT_BUY_BUDGET_KRW),
        "unused_cash_krw_decimal": _v51_money_decimal(V51_SLOT_BUY_BUDGET_KRW),
        "exit_value_krw": 0.0,
        "exit_value_krw_decimal": _v51_money_decimal(zero),
        "gross_pnl_krw": 0.0,
        "gross_pnl_krw_decimal": _v51_money_decimal(zero),
        "sell_side_cost_krw": 0.0,
        "sell_side_cost_krw_decimal": _v51_money_decimal(zero),
        "cost_krw": 0.0,
        "cost_krw_decimal": _v51_money_decimal(zero),
        "total_cost_krw": 0.0,
        "total_cost_krw_decimal": _v51_money_decimal(zero),
        "net_pnl_krw": 0.0,
        "net_pnl_krw_decimal": _v51_money_decimal(zero),
        "terminal_nav_krw": public_money(V51_SLOT_BUY_BUDGET_KRW),
        "terminal_nav_krw_decimal": _v51_money_decimal(V51_SLOT_BUY_BUDGET_KRW),
        "net_return_on_total_capital": 0.0,
        "net_return_on_total_capital_decimal": _v51_ratio_decimal(zero),
        "slot_nav_return": 0.0,
        "slot_nav_return_decimal": _v51_ratio_decimal(zero),
        "cost_components": components,
        "buy_commission_bp": public_bp(scenario.buy_commission_bp),
        "buy_commission_display_percent": _v51_bp_display_percent(scenario.buy_commission_bp),
        "buy_commission_krw": 0.0,
        "buy_commission_krw_decimal": _v51_money_decimal(zero),
        "buy_slippage_bp": public_bp(scenario.buy_slippage_bp),
        "buy_slippage_display_percent": _v51_bp_display_percent(scenario.buy_slippage_bp),
        "buy_slippage_krw": 0.0,
        "buy_slippage_krw_decimal": _v51_money_decimal(zero),
        "sell_tax_bp": public_bp(scenario.sell_tax_bp),
        "sell_tax_display_percent": _v51_bp_display_percent(scenario.sell_tax_bp),
        "sell_tax_krw": 0.0,
        "sell_tax_krw_decimal": _v51_money_decimal(zero),
        "sell_commission_bp": public_bp(scenario.sell_commission_bp),
        "sell_commission_display_percent": _v51_bp_display_percent(scenario.sell_commission_bp),
        "sell_commission_krw": 0.0,
        "sell_commission_krw_decimal": _v51_money_decimal(zero),
        "sell_slippage_bp": public_bp(scenario.sell_slippage_bp),
        "sell_slippage_display_percent": _v51_bp_display_percent(scenario.sell_slippage_bp),
        "sell_slippage_krw": 0.0,
        "sell_slippage_krw_decimal": _v51_money_decimal(zero),
        "fill_mode": V51_FILL_MODE,
        "source": {},
    }


def _v51_filled_slot_payload(
    *,
    selection: Mapping[str, Any],
    scenario: V5CostScenario,
    horizon: Mapping[str, Any],
) -> dict[str, Any]:
    quantity = int(selection["quantity"])
    entry_mark = quantize_money(selection["entry_mark"])
    exit_mark = quantize_money(selection["exit_mark"])
    share_count = Decimal(quantity)
    notional = quantize_money(share_count * entry_mark)
    exit_value = quantize_money(share_count * exit_mark)
    buy_commission = _component_cost(notional, scenario.buy_commission_bp)
    buy_slippage = _component_cost(notional, scenario.buy_slippage_bp)
    buy_side_cost = quantize_money(buy_commission + buy_slippage)
    budget_used = quantize_money(notional + buy_side_cost)
    symbol = str(selection["symbol"])
    if budget_used > V51_SLOT_BUY_BUDGET_KRW:
        raise ValueError(
            f"slot buy budget breach for {symbol} under {scenario.scenario_id}: "
            f"{_v51_money_decimal(budget_used)} > {_v51_money_decimal(V51_SLOT_BUY_BUDGET_KRW)}"
        )
    unused_cash = quantize_money(V51_SLOT_BUY_BUDGET_KRW - budget_used)
    gross_pnl = quantize_money(exit_value - notional)
    sell_tax = _component_cost(exit_value, scenario.sell_tax_bp)
    sell_commission = _component_cost(exit_value, scenario.sell_commission_bp)
    sell_slippage = _component_cost(exit_value, scenario.sell_slippage_bp)
    sell_side_cost = quantize_money(sell_tax + sell_commission + sell_slippage)
    cost_total = quantize_money(buy_side_cost + sell_side_cost)
    net_pnl = quantize_money(gross_pnl - cost_total)
    terminal_nav = quantize_money(V51_SLOT_BUY_BUDGET_KRW + net_pnl)
    components = {
        "buy_commission": _v51_cost_component_payload(bp=scenario.buy_commission_bp, amount=buy_commission),
        "buy_slippage": _v51_cost_component_payload(bp=scenario.buy_slippage_bp, amount=buy_slippage),
        "sell_tax": _v51_cost_component_payload(bp=scenario.sell_tax_bp, amount=sell_tax),
        "sell_commission": _v51_cost_component_payload(bp=scenario.sell_commission_bp, amount=sell_commission),
        "sell_slippage": _v51_cost_component_payload(bp=scenario.sell_slippage_bp, amount=sell_slippage),
    }
    slot_nav_return = quantize_ratio((terminal_nav - V51_SLOT_BUY_BUDGET_KRW) / V51_SLOT_BUY_BUDGET_KRW)
    account_return = quantize_ratio(net_pnl / V51_TOTAL_CAPITAL_KRW)
    return {
        "slot": int(selection["slot"]),
        "symbol": symbol,
        "code": symbol,
        "side": "buy",
        "quantity": quantity,
        "status": "filled",
        "unfilled_reason": None,
        "slot_state": "filled",
        "blocked": False,
        "horizon_id": horizon["horizon_id"],
        "horizon_days": horizon["horizon_days"],
        "label_column": horizon["label_column"],
        "price_basis": V51_PRICE_BASIS,
        "official_close": False,
        "causal_cutoff_kst": V51_CAUSAL_CUTOFF_KST,
        "cost_scenario_id": scenario.scenario_id,
        "cost_application_count": 1,
        "entry_mark_krw": public_money(entry_mark),
        "entry_mark_krw_decimal": _v51_money_decimal(entry_mark),
        "exit_mark_krw": public_money(exit_mark),
        "exit_mark_krw_decimal": _v51_money_decimal(exit_mark),
        "slot_buy_budget_krw": public_money(V51_SLOT_BUY_BUDGET_KRW),
        "slot_buy_budget_krw_decimal": _v51_money_decimal(V51_SLOT_BUY_BUDGET_KRW),
        "notional_krw": public_money(notional),
        "notional_krw_decimal": _v51_money_decimal(notional),
        "deployed_principal_krw": public_money(notional),
        "deployed_principal_krw_decimal": _v51_money_decimal(notional),
        "buy_side_cost_krw": public_money(buy_side_cost),
        "buy_side_cost_krw_decimal": _v51_money_decimal(buy_side_cost),
        "budget_used_krw": public_money(budget_used),
        "budget_used_krw_decimal": _v51_money_decimal(budget_used),
        "unused_cash_krw": public_money(unused_cash),
        "unused_cash_krw_decimal": _v51_money_decimal(unused_cash),
        "exit_value_krw": public_money(exit_value),
        "exit_value_krw_decimal": _v51_money_decimal(exit_value),
        "gross_pnl_krw": public_money(gross_pnl),
        "gross_pnl_krw_decimal": _v51_money_decimal(gross_pnl),
        "sell_side_cost_krw": public_money(sell_side_cost),
        "sell_side_cost_krw_decimal": _v51_money_decimal(sell_side_cost),
        "cost_krw": public_money(cost_total),
        "cost_krw_decimal": _v51_money_decimal(cost_total),
        "total_cost_krw": public_money(cost_total),
        "total_cost_krw_decimal": _v51_money_decimal(cost_total),
        "net_pnl_krw": public_money(net_pnl),
        "net_pnl_krw_decimal": _v51_money_decimal(net_pnl),
        "terminal_nav_krw": public_money(terminal_nav),
        "terminal_nav_krw_decimal": _v51_money_decimal(terminal_nav),
        "net_return_on_total_capital": public_ratio(account_return),
        "net_return_on_total_capital_decimal": _v51_ratio_decimal(account_return),
        "slot_nav_return": public_ratio(slot_nav_return),
        "slot_nav_return_decimal": _v51_ratio_decimal(slot_nav_return),
        "cost_components": components,
        "buy_commission_bp": public_bp(scenario.buy_commission_bp),
        "buy_commission_display_percent": _v51_bp_display_percent(scenario.buy_commission_bp),
        "buy_commission_krw": public_money(buy_commission),
        "buy_commission_krw_decimal": _v51_money_decimal(buy_commission),
        "buy_slippage_bp": public_bp(scenario.buy_slippage_bp),
        "buy_slippage_display_percent": _v51_bp_display_percent(scenario.buy_slippage_bp),
        "buy_slippage_krw": public_money(buy_slippage),
        "buy_slippage_krw_decimal": _v51_money_decimal(buy_slippage),
        "sell_tax_bp": public_bp(scenario.sell_tax_bp),
        "sell_tax_display_percent": _v51_bp_display_percent(scenario.sell_tax_bp),
        "sell_tax_krw": public_money(sell_tax),
        "sell_tax_krw_decimal": _v51_money_decimal(sell_tax),
        "sell_commission_bp": public_bp(scenario.sell_commission_bp),
        "sell_commission_display_percent": _v51_bp_display_percent(scenario.sell_commission_bp),
        "sell_commission_krw": public_money(sell_commission),
        "sell_commission_krw_decimal": _v51_money_decimal(sell_commission),
        "sell_slippage_bp": public_bp(scenario.sell_slippage_bp),
        "sell_slippage_display_percent": _v51_bp_display_percent(scenario.sell_slippage_bp),
        "sell_slippage_krw": public_money(sell_slippage),
        "sell_slippage_krw_decimal": _v51_money_decimal(sell_slippage),
        "fill_mode": V51_FILL_MODE,
        "source": dict(selection["source"]),
    }


def _v51_scenario_manifest(
    *,
    selections: Sequence[Mapping[str, Any]],
    scenario: V5CostScenario,
    horizon: Mapping[str, Any],
) -> dict[str, Any]:
    ledger: list[dict[str, Any]] = [
        _v51_filled_slot_payload(selection=selection, scenario=scenario, horizon=horizon)
        for selection in selections
    ]
    while len(ledger) < V51_SLOT_COUNT:
        ledger.append(_v51_empty_slot_payload(slot=len(ledger), scenario=scenario, horizon=horizon))
    deployed_principal = sum(to_decimal(row["deployed_principal_krw"], "deployed_principal_krw") for row in ledger)
    if deployed_principal > V51_MAX_DEPLOYED_PRINCIPAL_KRW:
        raise ValueError("deployed principal exceeds V5.1 50,000,000 KRW maximum")
    gross_pnl_total = sum(to_decimal(row["gross_pnl_krw"], "gross_pnl_krw") for row in ledger)
    buy_side_cost_total = sum(to_decimal(row["buy_side_cost_krw"], "buy_side_cost_krw") for row in ledger)
    sell_side_cost_total = sum(to_decimal(row["sell_side_cost_krw"], "sell_side_cost_krw") for row in ledger)
    cost_total = sum(to_decimal(row["cost_krw"], "cost_krw") for row in ledger)
    net_pnl_total = sum(to_decimal(row["net_pnl_krw"], "net_pnl_krw") for row in ledger)
    unused_cash_total = sum(to_decimal(row["unused_cash_krw"], "unused_cash_krw") for row in ledger)
    slot_terminal_nav_total = sum(to_decimal(row["terminal_nav_krw"], "terminal_nav_krw") for row in ledger)
    entry_cash_after_buy_costs = quantize_money(V51_RESERVE_KRW + unused_cash_total)
    terminal_account_nav = quantize_money(V51_RESERVE_KRW + slot_terminal_nav_total)
    reward = quantize_ratio(net_pnl_total / V51_TOTAL_CAPITAL_KRW)
    return {
        "schema_version": V51_ACCOUNTING_SCHEMA_VERSION,
        "horizon_id": horizon["horizon_id"],
        "accounting_horizon_id": horizon["horizon_id"],
        "horizon_days": horizon["horizon_days"],
        "label_column": horizon["label_column"],
        "cost_scenario_id": scenario.scenario_id,
        "cost_scenario": _v51_cost_scenario_payload(scenario),
        "round_trip_cost_bp": public_bp(scenario.total_bp),
        "round_trip_cost_display_percent": _v51_bp_display_percent(scenario.total_bp),
        "round_trip_cost_rate": public_ratio(scenario.total_bp / BP_DENOMINATOR),
        "cost_application_count": 1,
        "total_capital_krw": public_money(V51_TOTAL_CAPITAL_KRW),
        "total_capital_krw_decimal": _v51_money_decimal(V51_TOTAL_CAPITAL_KRW),
        "slot_count": V51_SLOT_COUNT,
        "filled_slots": sum(1 for row in ledger if row["status"] == "filled"),
        "unfilled_slots": sum(1 for row in ledger if row["status"] != "filled"),
        "blocked_slots": sum(1 for row in ledger if row["blocked"]),
        "hold_cash_slots": sum(1 for row in ledger if row["slot_state"] == "cash_hold"),
        "slot_buy_budget_krw": public_money(V51_SLOT_BUY_BUDGET_KRW),
        "slot_buy_budget_krw_decimal": _v51_money_decimal(V51_SLOT_BUY_BUDGET_KRW),
        "slot_budget_total_krw": public_money(V51_SLOT_BUY_BUDGET_KRW * Decimal(V51_SLOT_COUNT)),
        "slot_budget_total_krw_decimal": _v51_money_decimal(V51_SLOT_BUY_BUDGET_KRW * Decimal(V51_SLOT_COUNT)),
        "max_deployed_principal_krw": public_money(V51_MAX_DEPLOYED_PRINCIPAL_KRW),
        "max_deployed_principal_krw_decimal": _v51_money_decimal(V51_MAX_DEPLOYED_PRINCIPAL_KRW),
        "deployed_principal_krw": public_money(deployed_principal),
        "deployed_principal_krw_decimal": _v51_money_decimal(deployed_principal),
        "reserve_cash_krw": public_money(V51_RESERVE_KRW),
        "reserve_cash_krw_decimal": _v51_money_decimal(V51_RESERVE_KRW),
        "reserve_ratio": public_ratio(V51_RESERVE_KRW / V51_TOTAL_CAPITAL_KRW),
        "max_deployed_principal_ratio": public_ratio(V51_MAX_DEPLOYED_PRINCIPAL_KRW / V51_TOTAL_CAPITAL_KRW),
        "entry_cash_after_buy_costs_krw": public_money(entry_cash_after_buy_costs),
        "entry_cash_after_buy_costs_krw_decimal": _v51_money_decimal(entry_cash_after_buy_costs),
        "unused_slot_cash_krw": public_money(unused_cash_total),
        "unused_slot_cash_krw_decimal": _v51_money_decimal(unused_cash_total),
        "gross_pnl_krw": public_money(gross_pnl_total),
        "gross_pnl_krw_decimal": _v51_money_decimal(gross_pnl_total),
        "buy_side_cost_krw": public_money(buy_side_cost_total),
        "buy_side_cost_krw_decimal": _v51_money_decimal(buy_side_cost_total),
        "sell_side_cost_krw": public_money(sell_side_cost_total),
        "sell_side_cost_krw_decimal": _v51_money_decimal(sell_side_cost_total),
        "cost_krw": public_money(cost_total),
        "cost_krw_decimal": _v51_money_decimal(cost_total),
        "net_pnl_krw": public_money(net_pnl_total),
        "net_pnl_krw_decimal": _v51_money_decimal(net_pnl_total),
        "account_nav_krw": public_money(terminal_account_nav),
        "account_nav_krw_decimal": _v51_money_decimal(terminal_account_nav),
        "terminal_nav_krw": public_money(terminal_account_nav),
        "terminal_nav_krw_decimal": _v51_money_decimal(terminal_account_nav),
        "reward": public_ratio(reward),
        "reward_decimal": _v51_ratio_decimal(reward),
        "ledger": ledger,
        "blockers": [],
    }


def _v51_jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Mapping):
        return {str(key): _v51_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_v51_jsonable(item) for item in value]
    return value


def _v51_manifest_digest(manifest: Mapping[str, Any]) -> str:
    payload = {str(key): value for key, value in manifest.items() if key != "accounting_manifest_sha256"}
    encoded = json.dumps(
        _v51_jsonable(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_v51_slot_accounting_manifest(rows: Iterable[Mapping[str, Any]], horizon_id: str) -> dict[str, Any]:
    """Return the additive V5.1 exact-15:20 fixed-horizon slot accounting manifest.

    The helper does not size positions. The evaluator must pass selected rows with
    a complete six-digit symbol, horizon/session binding, long/buy side, positive
    whole-share quantity, lowercase source/panel hashes, and structured exact
    entry/exit 15:20 marks. Any invalid row fails closed before a manifest is emitted.
    """

    horizon = _normalize_v51_horizon_id(horizon_id)
    selections = _v51_normalized_selections(rows, horizon)
    scenario_manifests = {
        scenario_id: _v51_scenario_manifest(
            selections=selections,
            scenario=COST_SCENARIOS[scenario_id],
            horizon=horizon,
        )
        for scenario_id in V51_COST_SCENARIO_IDS
    }
    primary_accounting = scenario_manifests[V51_PRIMARY_COST_SCENARIO_ID]
    manifest: dict[str, Any] = {
        "schema_version": V51_ACCOUNTING_SCHEMA_VERSION,
        "v5_schema_version": ACCOUNTING_SCHEMA_VERSION,
        "horizon_id": horizon["horizon_id"],
        "accounting_horizon_id": horizon["horizon_id"],
        "horizon_days": horizon["horizon_days"],
        "label_column": horizon["label_column"],
        "supported_horizon_ids": list(V51_SUPPORTED_HORIZON_IDS),
        "price_basis": V51_PRICE_BASIS,
        "official_close": False,
        "causal_cutoff_kst": V51_CAUSAL_CUTOFF_KST,
        "fill_mode": V51_FILL_MODE,
        "rounding_mode": ROUNDING_MODE,
        "money_quantum": "0.000001",
        "ratio_quantum": "0.000000000001",
        "total_capital_krw": public_money(V51_TOTAL_CAPITAL_KRW),
        "total_capital_krw_decimal": _v51_money_decimal(V51_TOTAL_CAPITAL_KRW),
        "slot_count": V51_SLOT_COUNT,
        "max_positions": V51_SLOT_COUNT,
        "slot_buy_budget_krw": public_money(V51_SLOT_BUY_BUDGET_KRW),
        "slot_buy_budget_krw_decimal": _v51_money_decimal(V51_SLOT_BUY_BUDGET_KRW),
        "slot_budget_total_krw": public_money(V51_SLOT_BUY_BUDGET_KRW * Decimal(V51_SLOT_COUNT)),
        "slot_budget_total_krw_decimal": _v51_money_decimal(V51_SLOT_BUY_BUDGET_KRW * Decimal(V51_SLOT_COUNT)),
        "max_deployed_principal_krw": public_money(V51_MAX_DEPLOYED_PRINCIPAL_KRW),
        "max_deployed_principal_krw_decimal": _v51_money_decimal(V51_MAX_DEPLOYED_PRINCIPAL_KRW),
        "reserve_cash_krw": public_money(V51_RESERVE_KRW),
        "reserve_cash_krw_decimal": _v51_money_decimal(V51_RESERVE_KRW),
        "reserve_ratio": public_ratio(V51_RESERVE_KRW / V51_TOTAL_CAPITAL_KRW),
        "max_deployed_principal_ratio": public_ratio(V51_MAX_DEPLOYED_PRINCIPAL_KRW / V51_TOTAL_CAPITAL_KRW),
        "selected_count": len(selections),
        "symbols": [selection["symbol"] for selection in selections],
        "duplicate_policy": "fail_closed_one_slot_per_six_digit_symbol",
        "short_allowed": False,
        "leverage_allowed": False,
        "cost_application_count": 1,
        "cost_scenario_ids": list(V51_COST_SCENARIO_IDS),
        "primary_cost_scenario_id": V51_PRIMARY_COST_SCENARIO_ID,
        "cost_scenarios": [
            _v51_cost_scenario_payload(COST_SCENARIOS[scenario_id])
            for scenario_id in V51_COST_SCENARIO_IDS
        ],
        "scenario_manifests": scenario_manifests,
        "primary_accounting": primary_accounting,
        "account_nav_krw": primary_accounting["account_nav_krw"],
        "account_nav_krw_decimal": primary_accounting["account_nav_krw_decimal"],
        "deployed_principal_krw": primary_accounting["deployed_principal_krw"],
        "deployed_principal_krw_decimal": primary_accounting["deployed_principal_krw_decimal"],
        "entry_cash_after_buy_costs_krw": primary_accounting["entry_cash_after_buy_costs_krw"],
        "entry_cash_after_buy_costs_krw_decimal": primary_accounting["entry_cash_after_buy_costs_krw_decimal"],
        "gross_pnl_krw": primary_accounting["gross_pnl_krw"],
        "cost_krw": primary_accounting["cost_krw"],
        "net_pnl_krw": primary_accounting["net_pnl_krw"],
        "reward": primary_accounting["reward"],
        "blockers": [],
        "false_locks": dict(V51_FALSE_LOCKS),
        "promotion_claims": dict(V51_PROMOTION_CLAIMS),
        "no_claims": [
            "NO_LIVE_TRADING",
            "NO_BROKER_INTEGRATION",
            "NO_PAPER_TRADING",
            "NO_PROFIT_CLAIM",
        ],
        "contract": {
            "research_only": True,
            "proxy_1520_not_official_close": True,
            "no_daily_ohlcv": True,
            "no_future_return_1d": True,
            "one_slot_per_symbol": True,
            "no_short": True,
            "no_leverage": True,
            "budget_includes_buy_side_costs": True,
            "immutable_manifest_hash": "accounting_manifest_sha256",
        },
        "diagnostics": {
            "slot_order": "input_selection_order",
            "budget_breach_policy": "fail_closed",
            "duplicate_symbol_policy": "fail_closed",
            "unsupported_horizon_policy": "fail_closed",
        },
    }
    manifest["accounting_manifest_sha256"] = _v51_manifest_digest(manifest)
    return manifest


__all__ = [
    "ACCOUNTING_HORIZON_ID",
    "ACCOUNTING_SCHEMA_VERSION",
    "BP_DENOMINATOR",
    "CANONICAL_MAX_GROSS_FRACTION",
    "CANONICAL_MAX_POSITIONS",
    "CANONICAL_POSITION_FRACTION",
    "CARRY_ALLOWED",
    "COST_SCENARIOS",
    "COST_SCENARIO_BASE_23BP",
    "COST_SCENARIO_STRESS_46BP",
    "COST_SCENARIO_ZERO_CONTROL_0BP",
    "DEFAULT_TOTAL_CAPITAL_KRW",
    "FILL_MODE",
    "MONEY_QUANT",
    "PRIMARY_COST_SCENARIO_ID",
    "RATIO_QUANT",
    "ROUNDING_MODE",
    "TERMINAL_LIQUIDATION",
    "V51_ACCOUNTING_SCHEMA_VERSION",
    "V51_CAUSAL_CUTOFF_KST",
    "V51_COST_SCENARIO_IDS",
    "V51_FALSE_LOCKS",
    "V51_FILL_MODE",
    "V51_HORIZON_DAYS",
    "V51_HORIZON_LABELS",
    "V51_MAX_DEPLOYED_PRINCIPAL_KRW",
    "V51_PRICE_BASIS",
    "V51_PRIMARY_COST_SCENARIO_ID",
    "V51_PROMOTION_CLAIMS",
    "V51_RESERVE_KRW",
    "V51_SLOT_BUY_BUDGET_KRW",
    "V51_SLOT_COUNT",
    "V51_SUPPORTED_HORIZON_IDS",
    "V51_TOTAL_CAPITAL_KRW",
    "V5CostScenario",
    "account_close_slot_lot",
    "account_close_to_next_close_v1",
    "build_v51_slot_accounting_manifest",
    "empty_close_slot_lot",
    "normalize_v5_code",
    "positive_decimal",
    "public_bp",
    "public_money",
    "public_ratio",
    "quantize_money",
    "quantize_ratio",
    "scenario_for_cost",
    "to_decimal",
]
