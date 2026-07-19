"""Independent Decimal oracle for Kronos V5 close-slot accounting tests.

This file intentionally imports no production accounting helpers.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_HALF_UP
from typing import Any, Mapping, Sequence

ACCOUNTING_SCHEMA_VERSION = 1
ACCOUNTING_HORIZON_ID = "CS_T_CLOSE_TO_T1_CLOSE_V1"
TERMINAL_LIQUIDATION = "explicit_t1_close"
FILL_MODE = "close_to_next_close_research_label"
MONEY_QUANT = Decimal("0.000001")
RATIO_QUANT = Decimal("0.000000000001")
BP_DENOMINATOR = Decimal("10000")
DEFAULT_TOTAL_CAPITAL_KRW = 1_000_000
CANONICAL_MAX_POSITIONS = 2
CANONICAL_POSITION_FRACTION = Decimal("0.25")
CANONICAL_MAX_GROSS_FRACTION = Decimal("0.50")

COST_SCENARIOS = {
    "zero_control_0bp": {
        "sell_tax_bp": Decimal("0"),
        "buy_commission_bp": Decimal("0"),
        "sell_commission_bp": Decimal("0"),
        "buy_slippage_bp": Decimal("0"),
        "sell_slippage_bp": Decimal("0"),
    },
    "base_23bp": {
        "sell_tax_bp": Decimal("20"),
        "buy_commission_bp": Decimal("1.5"),
        "sell_commission_bp": Decimal("1.5"),
        "buy_slippage_bp": Decimal("0"),
        "sell_slippage_bp": Decimal("0"),
    },
    "stress_46bp": {
        "sell_tax_bp": Decimal("20"),
        "buy_commission_bp": Decimal("1.5"),
        "sell_commission_bp": Decimal("1.5"),
        "buy_slippage_bp": Decimal("11.5"),
        "sell_slippage_bp": Decimal("11.5"),
    },
}


def dec(value: Any, label: str = "value") -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{label} must be finite")
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError) as exc:
        raise ValueError(f"{label} must be finite") from exc
    if not parsed.is_finite():
        raise ValueError(f"{label} must be finite")
    return parsed


def positive_zero(value: Decimal) -> Decimal:
    return value.copy_abs() if value.is_zero() else value


def money(value: Decimal) -> Decimal:
    return positive_zero(value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))


def ratio(value: Decimal) -> Decimal:
    return positive_zero(value.quantize(RATIO_QUANT, rounding=ROUND_HALF_UP))


def money_public(value: Decimal) -> float:
    return float(money(value))


def ratio_public(value: Decimal) -> float:
    return float(ratio(value))


def bp_public(value: Decimal) -> int | float:
    normalized = value.normalize()
    if normalized == normalized.to_integral_value():
        return int(normalized)
    return float(normalized)


def scenario_total_bp(scenario: Mapping[str, Decimal]) -> Decimal:
    return sum(scenario[key] for key in ["sell_tax_bp", "buy_commission_bp", "sell_commission_bp", "buy_slippage_bp", "sell_slippage_bp"])


def scenario_for(cost_scenario_id: str | None = None, cost_bp: Any = 23) -> tuple[str, Mapping[str, Decimal]]:
    if cost_scenario_id is not None:
        return cost_scenario_id, COST_SCENARIOS[cost_scenario_id]
    target = dec(cost_bp, "cost_bp")
    for scenario_id, scenario in COST_SCENARIOS.items():
        if scenario_total_bp(scenario) == target:
            return scenario_id, scenario
    raise ValueError("unsupported cost_bp")


def normalize_code(value: Any) -> str:
    if value is None or isinstance(value, bool):
        raise ValueError("bad code")
    raw = str(value if not isinstance(value, int) else int(value)).strip()
    if raw and not raw.startswith("-") and not raw.isdigit():
        parsed = dec(raw, "code")
        if parsed != parsed.to_integral_value() or parsed < 0:
            raise ValueError("bad code")
        raw = str(int(parsed))
    if not raw or raw.startswith("-") or not raw.isdigit() or len(raw) > 6:
        raise ValueError("bad code")
    code = raw.zfill(6)
    if code == "000000":
        raise ValueError("bad code")
    return code


def validate_horizon(horizon_id: str) -> None:
    if horizon_id != ACCOUNTING_HORIZON_ID:
        raise ValueError("bad horizon")


def validate_cost_application(row: Mapping[str, Any]) -> None:
    raw = row.get("cost_application_count", row.get("cost_charge_count", 1))
    if isinstance(raw, bool) or str(raw).strip() not in {"1", "1.0"}:
        raise ValueError("cost applied more than once")


def component_cost(amount: Decimal, bp: Decimal) -> Decimal:
    return money((amount * bp) / BP_DENOMINATOR)


def lot_payload(
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
    scenario_id: str,
    scenario: Mapping[str, Decimal],
) -> dict[str, Any]:
    cost_total = money(buy_commission + buy_slippage + sell_tax + sell_commission + sell_slippage)
    net_pnl = money(gross_pnl - cost_total)
    return {
        "slot": int(slot),
        "code": code,
        "status": status,
        "unfilled_reason": unfilled_reason,
        "slot_state": slot_state,
        "blocked": bool(blocked),
        "horizon_id": ACCOUNTING_HORIZON_ID,
        "accounting_horizon_id": ACCOUNTING_HORIZON_ID,
        "carry_allowed": False,
        "terminal_liquidation": TERMINAL_LIQUIDATION,
        "cost_application_count": 1,
        "entry_close": money_public(entry_close) if entry_close is not None else None,
        "next_close": money_public(next_close) if next_close is not None else None,
        "shares": int(shares),
        "slot_cash_krw": money_public(slot_cash),
        "notional_krw": money_public(notional),
        "exit_value_krw": money_public(exit_value),
        "unused_cash_krw": money_public(unused_cash),
        "gross_pnl_krw": money_public(gross_pnl),
        "cost_krw": money_public(cost_total),
        "sell_tax_bp": bp_public(scenario["sell_tax_bp"]),
        "buy_commission_bp": bp_public(scenario["buy_commission_bp"]),
        "sell_commission_bp": bp_public(scenario["sell_commission_bp"]),
        "buy_slippage_bp": bp_public(scenario["buy_slippage_bp"]),
        "sell_slippage_bp": bp_public(scenario["sell_slippage_bp"]),
        "buy_commission_krw": money_public(buy_commission),
        "buy_slippage_krw": money_public(buy_slippage),
        "sell_tax_krw": money_public(sell_tax),
        "sell_commission_krw": money_public(sell_commission),
        "sell_slippage_krw": money_public(sell_slippage),
        "total_cost_krw": money_public(cost_total),
        "net_pnl_krw": money_public(net_pnl),
        "net_return_on_total_capital": ratio_public(net_pnl / total_capital),
        "terminal_nav_krw": money_public(slot_cash + net_pnl),
        "reward": float(ratio(net_pnl / total_capital)),
        "fill_mode": FILL_MODE,
    }


def empty_lot(
    *,
    slot: int,
    slot_cash: Decimal,
    total_capital: Decimal,
    scenario_id: str,
    scenario: Mapping[str, Decimal],
    code: str | None = None,
    reason: str = "EMPTY_SLOT",
    slot_state: str = "cash_hold",
    blocked: bool = False,
    entry_close: Any = None,
    next_close: Any = None,
) -> dict[str, Any]:
    return lot_payload(
        slot=slot,
        code=normalize_code(code) if code else None,
        status="unfilled",
        unfilled_reason=reason,
        slot_state=slot_state,
        blocked=blocked,
        entry_close=money(dec(entry_close)) if entry_close is not None else None,
        next_close=money(dec(next_close)) if next_close is not None else None,
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
        scenario_id=scenario_id,
        scenario=scenario,
    )


def account_lot(
    *,
    slot: int,
    code: Any,
    entry_close: Any,
    next_close: Any,
    slot_cash: Decimal,
    total_capital: Decimal,
    scenario_id: str,
    scenario: Mapping[str, Decimal],
) -> dict[str, Any]:
    code = normalize_code(code)
    entry = dec(entry_close, "entry_close")
    exit_mark = dec(next_close, "next_close")
    if entry <= 0 or exit_mark <= 0:
        raise ValueError("marks must be positive")
    buy_cost_bp = scenario["buy_commission_bp"] + scenario["buy_slippage_bp"]
    effective_unit_cost = entry * (Decimal("1") + buy_cost_bp / BP_DENOMINATOR)
    shares = int((slot_cash / effective_unit_cost).to_integral_value(rounding=ROUND_FLOOR))
    if shares <= 0:
        return empty_lot(
            slot=slot,
            slot_cash=slot_cash,
            total_capital=total_capital,
            scenario_id=scenario_id,
            scenario=scenario,
            code=code,
            reason="INSUFFICIENT_SLOT_CASH",
            slot_state="blocked_unfilled",
            blocked=True,
            entry_close=entry,
            next_close=exit_mark,
        )
    notional = money(Decimal(shares) * entry)
    exit_value = money(Decimal(shares) * exit_mark)
    buy_commission = component_cost(notional, scenario["buy_commission_bp"])
    buy_slippage = component_cost(notional, scenario["buy_slippage_bp"])
    sell_tax = component_cost(exit_value, scenario["sell_tax_bp"])
    sell_commission = component_cost(exit_value, scenario["sell_commission_bp"])
    sell_slippage = component_cost(exit_value, scenario["sell_slippage_bp"])
    unused_cash = money(slot_cash - notional - buy_commission - buy_slippage)
    if unused_cash < 0:
        raise ValueError("negative cash")
    return lot_payload(
        slot=slot,
        code=code,
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
        gross_pnl=money(exit_value - notional),
        buy_commission=buy_commission,
        buy_slippage=buy_slippage,
        sell_tax=sell_tax,
        sell_commission=sell_commission,
        sell_slippage=sell_slippage,
        scenario_id=scenario_id,
        scenario=scenario,
    )


def oracle_account_close_to_next_close_v1(
    rows: Sequence[Mapping[str, Any]],
    *,
    cost_scenario_id: str | None = None,
    cost_bp: Any = 23,
    total_capital_krw: Any = DEFAULT_TOTAL_CAPITAL_KRW,
    horizon_id: str = ACCOUNTING_HORIZON_ID,
) -> dict[str, Any]:
    validate_horizon(horizon_id)
    scenario_id, scenario = scenario_for(cost_scenario_id, cost_bp)
    total_capital = money(dec(total_capital_krw, "total_capital_krw"))
    if total_capital != Decimal(DEFAULT_TOTAL_CAPITAL_KRW):
        raise ValueError("bad canonical capital")
    slot_cash = money(total_capital * CANONICAL_POSITION_FRACTION)
    selected = []
    for row in rows:
        validate_cost_application(row)
        selected.append(
            {
                "code": normalize_code(row.get("code")),
                "entry_close": row.get("entry_close"),
                "next_close": row.get("next_close"),
            }
        )
    seen = set()
    for row in selected:
        if row["code"] in seen:
            raise ValueError("duplicate code")
        seen.add(row["code"])
    selected = sorted(selected, key=lambda row: row["code"])
    included = selected[:CANONICAL_MAX_POSITIONS]
    ledger = [
        account_lot(
            slot=index,
            code=row["code"],
            entry_close=row["entry_close"],
            next_close=row["next_close"],
            slot_cash=slot_cash,
            total_capital=total_capital,
            scenario_id=scenario_id,
            scenario=scenario,
        )
        for index, row in enumerate(included)
    ]
    while len(ledger) < CANONICAL_MAX_POSITIONS:
        ledger.append(empty_lot(slot=len(ledger), slot_cash=slot_cash, total_capital=total_capital, scenario_id=scenario_id, scenario=scenario))
    net_pnl = sum(dec(row["net_pnl_krw"]) for row in ledger)
    gross_pnl = sum(dec(row["gross_pnl_krw"]) for row in ledger)
    cost = sum(dec(row["cost_krw"]) for row in ledger)
    return {
        "schema_version": ACCOUNTING_SCHEMA_VERSION,
        "horizon_id": ACCOUNTING_HORIZON_ID,
        "accounting_horizon_id": ACCOUNTING_HORIZON_ID,
        "carry_allowed": False,
        "terminal_liquidation": TERMINAL_LIQUIDATION,
        "rounding_mode": "ROUND_HALF_UP",
        "money_quantum": "0.000001",
        "ratio_quantum": "0.000000000001",
        "total_capital_krw": money_public(total_capital),
        "max_positions": CANONICAL_MAX_POSITIONS,
        "position_fraction": ratio_public(CANONICAL_POSITION_FRACTION),
        "max_gross_fraction": ratio_public(CANONICAL_MAX_GROSS_FRACTION),
        "slot_cash_krw": money_public(slot_cash),
        "allocated_cash_krw": money_public(slot_cash * CANONICAL_MAX_POSITIONS),
        "unallocated_cash_krw": money_public(total_capital - slot_cash * CANONICAL_MAX_POSITIONS),
        "round_trip_cost_bp": bp_public(scenario_total_bp(scenario)),
        "round_trip_cost_rate": ratio_public(scenario_total_bp(scenario) / BP_DENOMINATOR),
        "cost_scenario_id": scenario_id,
        "cost_scenario": {"scenario_id": scenario_id, **{key: bp_public(value) for key, value in scenario.items()}, "total_bp": bp_public(scenario_total_bp(scenario))},
        "cost_application_count": 1,
        "filled_slots": sum(1 for row in ledger if row["status"] == "filled"),
        "unfilled_slots": sum(1 for row in ledger if row["status"] != "filled"),
        "blocked_slots": sum(1 for row in ledger if row["blocked"]),
        "gross_pnl_krw": money_public(gross_pnl),
        "cost_krw": money_public(cost),
        "net_pnl_krw": money_public(net_pnl),
        "terminal_nav_krw": money_public(total_capital + net_pnl),
        "reward": float(ratio(net_pnl / total_capital)),
        "ledger": ledger,
        "diagnostics": {
            "code_order": "zero_padded_6_digit_string_ascending",
            "excluded_codes_over_max_positions": [row["code"] for row in selected[CANONICAL_MAX_POSITIONS:]],
            "selected_count_before_cap": len(selected),
        },
    }


def source_mark(candidate: Mapping[str, Any], source_key: str, display_key: str) -> Any:
    return candidate.get(source_key) if source_key in candidate else candidate.get(display_key)


def oracle_account_normalized_slots(
    normalized_action: Mapping[str, Any],
    *,
    cost_scenario_id: str | None = None,
    cost_bp: Any = 23,
    total_capital_krw: Any,
    slot_count: int,
) -> dict[str, Any]:
    scenario_id, scenario = scenario_for(cost_scenario_id, cost_bp)
    total_capital = money(dec(total_capital_krw, "total_capital_krw"))
    slot_cash = money(total_capital / Decimal(int(slot_count)))
    ledger = []
    for slot in list(normalized_action.get("selection_slots") or [])[:slot_count]:
        slot_index = int(slot.get("slot", len(ledger)))
        candidate = dict(slot.get("candidate") or {})
        status = str(slot.get("status") or "empty")
        raw_code = slot.get("code") or candidate.get("code")
        code = normalize_code(raw_code) if raw_code else None
        entry = source_mark(candidate, "entry_close_source", "entry_close")
        nxt = source_mark(candidate, "next_close_source", "next_close")
        slot_state = str(slot.get("slot_state") or ("filled" if status == "selected" else "cash_hold" if status == "empty" else "replay_unfilled"))
        if status == "selected" and code and entry is not None and nxt is not None and dec(entry) > 0 and dec(nxt) > 0:
            ledger.append(account_lot(slot=slot_index, code=code, entry_close=entry, next_close=nxt, slot_cash=slot_cash, total_capital=total_capital, scenario_id=scenario_id, scenario=scenario))
        else:
            if status == "empty":
                slot_state = "cash_hold"
            reason = "EMPTY_SLOT" if status == "empty" else str(slot.get("reason") or "EMPTY_SLOT")
            if status == "selected" and (entry is None or dec(entry) <= 0):
                reason = "INVALID_ENTRY_CLOSE"
                slot_state = "blocked_unfilled"
            if status == "selected" and (nxt is None or dec(nxt) <= 0):
                reason = "MISSING_NEXT_CLOSE"
                slot_state = "blocked_unfilled"
            ledger.append(
                empty_lot(
                    slot=slot_index,
                    code=code,
                    slot_cash=slot_cash,
                    total_capital=total_capital,
                    scenario_id=scenario_id,
                    scenario=scenario,
                    reason=reason,
                    slot_state=slot_state,
                    blocked=status in {"selected", "unfilled"} and slot_state != "cash_hold",
                    entry_close=entry if entry is not None else None,
                    next_close=nxt if nxt is not None else None,
                )
            )
    while len(ledger) < slot_count:
        ledger.append(empty_lot(slot=len(ledger), slot_cash=slot_cash, total_capital=total_capital, scenario_id=scenario_id, scenario=scenario))
    net_pnl = sum(dec(row["net_pnl_krw"]) for row in ledger)
    gross_pnl = sum(dec(row["gross_pnl_krw"]) for row in ledger)
    cost = sum(dec(row["cost_krw"]) for row in ledger)
    unused_cash = sum(dec(row["unused_cash_krw"]) for row in ledger)
    return {
        "schema_version": 2,
        "date": normalized_action.get("date"),
        "action_label": normalized_action.get("action_label"),
        "slot_count": int(slot_count),
        "total_capital_krw": money_public(total_capital),
        "slot_cash_krw": money_public(slot_cash),
        "round_trip_cost_bp": bp_public(scenario_total_bp(scenario)),
        "round_trip_cost_rate": ratio_public(scenario_total_bp(scenario) / BP_DENOMINATOR),
        "cost_scenario": {"scenario_id": scenario_id, **{key: bp_public(value) for key, value in scenario.items()}, "total_bp": bp_public(scenario_total_bp(scenario))},
        "cost_scenario_id": scenario_id,
        "accounting_horizon_id": ACCOUNTING_HORIZON_ID,
        "horizon_id": ACCOUNTING_HORIZON_ID,
        "carry_allowed": False,
        "terminal_liquidation": TERMINAL_LIQUIDATION,
        "rounding_mode": "ROUND_HALF_UP",
        "money_quantum": "0.000001",
        "ratio_quantum": "0.000000000001",
        "cost_application_count": 1,
        "fill_mode": FILL_MODE,
        "gross_pnl_krw": money_public(gross_pnl),
        "cost_krw": money_public(cost),
        "net_pnl_krw": money_public(net_pnl),
        "terminal_nav_krw": money_public(total_capital + net_pnl),
        "reward": float(ratio(net_pnl / total_capital)),
        "unused_cash_krw": money_public(unused_cash),
        "filled_slots": sum(1 for row in ledger if row["status"] == "filled"),
        "unfilled_slots": sum(1 for row in ledger if row["status"] != "filled"),
        "blocked_slots": sum(1 for row in ledger if row["blocked"]),
        "selected_count": int(normalized_action.get("selected_count", 0)),
        "hold_cash_count": sum(1 for row in ledger if row["slot_state"] == "cash_hold"),
        "max_slot_count": int(normalized_action.get("max_slot_count", slot_count)),
        "ledger": ledger,
        "diagnostics": normalized_action.get("diagnostics", {}),
    }
