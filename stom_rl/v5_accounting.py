"""Decimal accounting oracle for Kronos V5 close-slot research ledgers.

This module is a research-only accounting surface. It does not authorize live,
broker, account, order, paper-forward, model-build, profitability, GO, or
readiness claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_HALF_UP
from typing import Any, Final, Mapping, Sequence

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
    "V5CostScenario",
    "account_close_slot_lot",
    "account_close_to_next_close_v1",
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
