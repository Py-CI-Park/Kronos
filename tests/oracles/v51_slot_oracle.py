"""Independent V5.1 fixed-horizon slot accounting oracle for tests.

This test-only module deliberately imports no production accounting helpers.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "kronos_v51_slot_accounting.v1"
PRICE_BASIS = "15:20_bar_close_proxy"
SOURCE_MARK_SCHEMA_VERSION = "kronos_daily_1520_source.v1"
CAUSAL_CUTOFF_KST = "15:20:00"
TOTAL_CAPITAL = Decimal("60000000")
SLOT_COUNT = 10
SLOT_BUY_BUDGET = Decimal("5000000")
MAX_DEPLOYED_PRINCIPAL = Decimal("50000000")
RESERVE = Decimal("10000000")
MONEY_QUANT = Decimal("0.000001")
RATIO_QUANT = Decimal("0.000000000001")
BP_DENOMINATOR = Decimal("10000")
HORIZON_DAYS = {"H1": 1, "H3": 3, "H5": 5}
HORIZON_LABELS = {
    "H1": "future_return_h1_1520_proxy",
    "H3": "future_return_h3_1520_proxy",
    "H5": "future_return_h5_1520_proxy",
}
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
SCENARIO_IDS = ("zero_control_0bp", "base_23bp", "stress_46bp")
PRIMARY_SCENARIO_ID = "base_23bp"


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


def money_decimal(value: Decimal) -> str:
    return format(money(value), "f")


def ratio_public(value: Decimal) -> float:
    return float(ratio(value))


def ratio_decimal(value: Decimal) -> str:
    return format(ratio(value), "f")


def bp_public(value: Decimal) -> int | float:
    normalized = value.normalize()
    if normalized == normalized.to_integral_value():
        return int(normalized)
    return float(normalized)


def display_percent(bp: Decimal) -> str:
    percent = bp / Decimal("100")
    two = percent.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if percent == two:
        return f"{two:.2f}%"
    return f"{percent.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP):f}%"


def scenario_total_bp(scenario: Mapping[str, Decimal]) -> Decimal:
    return sum(scenario[key] for key in scenario)


def component_cost(amount: Decimal, bp: Decimal) -> Decimal:
    return money((amount * bp) / BP_DENOMINATOR)


def normalize_code(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("canonical symbol required")
    symbol = value.strip()
    if len(symbol) != 6 or not symbol.isdigit() or symbol == "000000":
        raise ValueError("canonical symbol required")
    return symbol


def normalize_horizon(horizon_id: Any) -> dict[str, Any]:
    raw = str(horizon_id).strip()
    upper = raw.upper()
    if upper in HORIZON_DAYS:
        canonical = upper
    else:
        matches = [key for key, label in HORIZON_LABELS.items() if raw == label]
        if len(matches) != 1:
            raise ValueError("bad horizon")
        canonical = matches[0]
    return {"horizon_id": canonical, "horizon_days": HORIZON_DAYS[canonical], "label_column": HORIZON_LABELS[canonical]}


def first_present(row: Mapping[str, Any], keys: Sequence[str], label: str) -> Any:
    for key in keys:
        if key in row and row[key] is not None and row[key] != "":
            return row[key]
    raise ValueError(f"missing {label}")


def canonical_session(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"missing canonical {label}")
    session = value.strip()
    if (
        len(session) != 10
        or session[4] != "-"
        or session[7] != "-"
        or not (session[:4] + session[5:7] + session[8:10]).isdigit()
    ):
        raise ValueError(f"bad canonical {label}")
    return session


def canonical_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"bad canonical {label}")
    return value


def source_table(value: Any, symbol: str, label: str) -> str:
    expected = f"A{symbol}"
    if not isinstance(value, str) or value.strip() != expected:
        raise ValueError(f"bad canonical {label}")
    return expected


def exact_timestamp(value: Any, label: str) -> tuple[str, str]:
    if not isinstance(value, str):
        raise ValueError(f"bad canonical {label}")
    timestamp = value.strip()
    if len(timestamp) != 25 or timestamp[10:] != "T15:20:00+09:00":
        raise ValueError(f"bad canonical {label}")
    return timestamp, canonical_session(timestamp[:10], label)


def mark_value(raw: Any, label: str, *, symbol: str, expected_session: str) -> Decimal:
    if not isinstance(raw, Mapping):
        raise ValueError(f"missing canonical {label}")
    if normalize_code(first_present(raw, ("symbol",), f"{label} symbol")) != symbol:
        raise ValueError(f"bad canonical {label} symbol")
    session = canonical_session(first_present(raw, ("session",), f"{label} session"), f"{label} session")
    if session != expected_session:
        raise ValueError(f"bad canonical {label} session")
    timestamp, timestamp_session = exact_timestamp(first_present(raw, ("timestamp",), f"{label} timestamp"), f"{label} timestamp")
    timestamp_kst, timestamp_kst_session = exact_timestamp(
        first_present(raw, ("timestamp_kst",), f"{label} timestamp_kst"),
        f"{label} timestamp_kst",
    )
    if timestamp != timestamp_kst or timestamp_session != timestamp_kst_session or timestamp_session != session:
        raise ValueError(f"bad canonical {label} timestamp")
    compact = first_present(raw, ("timestamp_yyyymmddhhmm",), f"{label} compact timestamp")
    if not isinstance(compact, str) or compact != f"{session.replace('-', '')}1520":
        raise ValueError(f"bad canonical {label} compact timestamp")
    if raw.get("price_basis") != PRICE_BASIS or raw.get("official_close") is not False:
        raise ValueError(f"bad canonical {label} price basis")
    if raw.get("schema_version") != SOURCE_MARK_SCHEMA_VERSION:
        raise ValueError(f"bad canonical {label} schema_version")
    source = source_table(first_present(raw, ("source_table",), f"{label} source_table"), symbol, f"{label} source_table")
    table = source_table(first_present(raw, ("table",), f"{label} table"), symbol, f"{label} table")
    if table != source:
        raise ValueError(f"bad canonical {label} table")
    parsed = dec(first_present(raw, ("price_1520_close_proxy",), f"{label} price"), label)
    if parsed <= 0:
        raise ValueError(f"{label} must be positive")
    return parsed


def exit_mark(row: Mapping[str, Any], horizon: Mapping[str, Any], *, symbol: str, exit_session: str) -> Decimal:
    by_label = row.get("exit_1520_by_label")
    if not isinstance(by_label, Mapping):
        raise ValueError("missing canonical exit marks")
    label_column = horizon["label_column"]
    return mark_value(by_label[label_column], "exit_mark", symbol=symbol, expected_session=exit_session)


def normalize_rows(rows: Sequence[Mapping[str, Any]], horizon: Mapping[str, Any]) -> list[dict[str, Any]]:
    selections = []
    seen = set()
    for index, row in enumerate(rows):
        symbol = normalize_code(first_present(row, ("symbol",), "symbol"))
        if symbol in seen:
            raise ValueError("duplicate symbol")
        seen.add(symbol)
        for hash_key in ("source_db_sha256", "source_identity_sha256", "panel_sha256"):
            canonical_sha(first_present(row, (hash_key,), hash_key), hash_key)
        row_horizon = normalize_horizon(first_present(row, ("horizon_id",), "horizon_id"))
        if row_horizon["horizon_id"] != horizon["horizon_id"]:
            raise ValueError("bad canonical horizon")
        if first_present(row, ("label_column",), "label_column") != horizon["label_column"]:
            raise ValueError("bad canonical label")
        if int(first_present(row, ("horizon_days",), "horizon_days")) != horizon["horizon_days"]:
            raise ValueError("bad canonical horizon days")
        session = canonical_session(first_present(row, ("session",), "session"), "session")
        exit_session = canonical_session(first_present(row, ("exit_session",), "exit_session"), "exit_session")
        side = str(first_present(row, ("side", "order_side"), "side")).strip().lower()
        if side not in {"buy", "long"}:
            raise ValueError("bad side")
        quantity = dec(first_present(row, ("quantity", "shares", "share_count"), "quantity"), "quantity")
        if quantity <= 0 or quantity != quantity.to_integral_value():
            raise ValueError("bad quantity")
        selections.append(
            {
                "slot": index,
                "symbol": symbol,
                "quantity": int(quantity),
                "entry_mark": mark_value(
                    first_present(row, ("entry_1520",), "entry_1520"),
                    "entry_mark",
                    symbol=symbol,
                    expected_session=session,
                ),
                "exit_mark": exit_mark(row, horizon, symbol=symbol, exit_session=exit_session),
            }
        )
    return selections


def component_payload(bp: Decimal, amount: Decimal) -> dict[str, Any]:
    return {"bp": bp_public(bp), "display_percent": display_percent(bp), "krw": money_public(amount), "krw_decimal": money_decimal(amount)}


def empty_slot(slot: int, scenario_id: str, scenario: Mapping[str, Decimal], horizon: Mapping[str, Any]) -> dict[str, Any]:
    zero = Decimal("0")
    return {
        "slot": slot,
        "symbol": None,
        "quantity": 0,
        "status": "unfilled",
        "slot_state": "cash_hold",
        "horizon_id": horizon["horizon_id"],
        "label_column": horizon["label_column"],
        "cost_scenario_id": scenario_id,
        "notional_krw_decimal": money_decimal(zero),
        "deployed_principal_krw_decimal": money_decimal(zero),
        "buy_side_cost_krw_decimal": money_decimal(zero),
        "budget_used_krw_decimal": money_decimal(zero),
        "unused_cash_krw_decimal": money_decimal(SLOT_BUY_BUDGET),
        "exit_value_krw_decimal": money_decimal(zero),
        "gross_pnl_krw_decimal": money_decimal(zero),
        "sell_side_cost_krw_decimal": money_decimal(zero),
        "cost_krw_decimal": money_decimal(zero),
        "net_pnl_krw_decimal": money_decimal(zero),
        "terminal_nav_krw_decimal": money_decimal(SLOT_BUY_BUDGET),
        "buy_commission_krw_decimal": money_decimal(zero),
        "buy_slippage_krw_decimal": money_decimal(zero),
        "sell_tax_krw_decimal": money_decimal(zero),
        "sell_commission_krw_decimal": money_decimal(zero),
        "sell_slippage_krw_decimal": money_decimal(zero),
    }


def filled_slot(selection: Mapping[str, Any], scenario_id: str, scenario: Mapping[str, Decimal], horizon: Mapping[str, Any]) -> dict[str, Any]:
    quantity = Decimal(int(selection["quantity"]))
    entry = money(selection["entry_mark"])
    exit_ = money(selection["exit_mark"])
    notional = money(quantity * entry)
    exit_value = money(quantity * exit_)
    buy_commission = component_cost(notional, scenario["buy_commission_bp"])
    buy_slippage = component_cost(notional, scenario["buy_slippage_bp"])
    buy_side = money(buy_commission + buy_slippage)
    budget_used = money(notional + buy_side)
    if budget_used > SLOT_BUY_BUDGET:
        raise ValueError("budget breach")
    unused_cash = money(SLOT_BUY_BUDGET - budget_used)
    gross_pnl = money(exit_value - notional)
    sell_tax = component_cost(exit_value, scenario["sell_tax_bp"])
    sell_commission = component_cost(exit_value, scenario["sell_commission_bp"])
    sell_slippage = component_cost(exit_value, scenario["sell_slippage_bp"])
    sell_side = money(sell_tax + sell_commission + sell_slippage)
    cost_total = money(buy_side + sell_side)
    net_pnl = money(gross_pnl - cost_total)
    terminal_nav = money(SLOT_BUY_BUDGET + net_pnl)
    return {
        "slot": int(selection["slot"]),
        "symbol": selection["symbol"],
        "quantity": int(selection["quantity"]),
        "status": "filled",
        "slot_state": "filled",
        "horizon_id": horizon["horizon_id"],
        "label_column": horizon["label_column"],
        "cost_scenario_id": scenario_id,
        "entry_mark_krw_decimal": money_decimal(entry),
        "exit_mark_krw_decimal": money_decimal(exit_),
        "notional_krw_decimal": money_decimal(notional),
        "deployed_principal_krw_decimal": money_decimal(notional),
        "buy_side_cost_krw_decimal": money_decimal(buy_side),
        "budget_used_krw_decimal": money_decimal(budget_used),
        "unused_cash_krw_decimal": money_decimal(unused_cash),
        "exit_value_krw_decimal": money_decimal(exit_value),
        "gross_pnl_krw_decimal": money_decimal(gross_pnl),
        "sell_side_cost_krw_decimal": money_decimal(sell_side),
        "cost_krw_decimal": money_decimal(cost_total),
        "net_pnl_krw_decimal": money_decimal(net_pnl),
        "terminal_nav_krw_decimal": money_decimal(terminal_nav),
        "buy_commission_krw_decimal": money_decimal(buy_commission),
        "buy_slippage_krw_decimal": money_decimal(buy_slippage),
        "sell_tax_krw_decimal": money_decimal(sell_tax),
        "sell_commission_krw_decimal": money_decimal(sell_commission),
        "sell_slippage_krw_decimal": money_decimal(sell_slippage),
        "cost_components": {
            "buy_commission": component_payload(scenario["buy_commission_bp"], buy_commission),
            "buy_slippage": component_payload(scenario["buy_slippage_bp"], buy_slippage),
            "sell_tax": component_payload(scenario["sell_tax_bp"], sell_tax),
            "sell_commission": component_payload(scenario["sell_commission_bp"], sell_commission),
            "sell_slippage": component_payload(scenario["sell_slippage_bp"], sell_slippage),
        },
    }


def scenario_payload(scenario_id: str, scenario: Mapping[str, Decimal]) -> dict[str, Any]:
    total_bp = scenario_total_bp(scenario)
    return {
        "scenario_id": scenario_id,
        "sell_tax_bp": bp_public(scenario["sell_tax_bp"]),
        "buy_commission_bp": bp_public(scenario["buy_commission_bp"]),
        "sell_commission_bp": bp_public(scenario["sell_commission_bp"]),
        "buy_slippage_bp": bp_public(scenario["buy_slippage_bp"]),
        "sell_slippage_bp": bp_public(scenario["sell_slippage_bp"]),
        "total_bp": bp_public(total_bp),
        "total_cost_display_percent": display_percent(total_bp),
        "display_percent": display_percent(total_bp),
    }


def scenario_manifest(selections: Sequence[Mapping[str, Any]], scenario_id: str, horizon: Mapping[str, Any]) -> dict[str, Any]:
    scenario = COST_SCENARIOS[scenario_id]
    ledger = [filled_slot(selection, scenario_id, scenario, horizon) for selection in selections]
    while len(ledger) < SLOT_COUNT:
        ledger.append(empty_slot(len(ledger), scenario_id, scenario, horizon))
    deployed = sum(dec(row["deployed_principal_krw_decimal"]) for row in ledger)
    gross = sum(dec(row["gross_pnl_krw_decimal"]) for row in ledger)
    buy_side = sum(dec(row["buy_side_cost_krw_decimal"]) for row in ledger)
    sell_side = sum(dec(row["sell_side_cost_krw_decimal"]) for row in ledger)
    cost = sum(dec(row["cost_krw_decimal"]) for row in ledger)
    net = sum(dec(row["net_pnl_krw_decimal"]) for row in ledger)
    unused = sum(dec(row["unused_cash_krw_decimal"]) for row in ledger)
    slot_nav = sum(dec(row["terminal_nav_krw_decimal"]) for row in ledger)
    account_nav = money(RESERVE + slot_nav)
    return {
        "schema_version": SCHEMA_VERSION,
        "horizon_id": horizon["horizon_id"],
        "horizon_days": horizon["horizon_days"],
        "label_column": horizon["label_column"],
        "cost_scenario_id": scenario_id,
        "cost_scenario": scenario_payload(scenario_id, scenario),
        "round_trip_cost_display_percent": display_percent(scenario_total_bp(scenario)),
        "filled_slots": len(selections),
        "unfilled_slots": SLOT_COUNT - len(selections),
        "hold_cash_slots": SLOT_COUNT - len(selections),
        "deployed_principal_krw_decimal": money_decimal(deployed),
        "reserve_cash_krw_decimal": money_decimal(RESERVE),
        "entry_cash_after_buy_costs_krw_decimal": money_decimal(RESERVE + unused),
        "gross_pnl_krw_decimal": money_decimal(gross),
        "buy_side_cost_krw_decimal": money_decimal(buy_side),
        "sell_side_cost_krw_decimal": money_decimal(sell_side),
        "cost_krw_decimal": money_decimal(cost),
        "net_pnl_krw_decimal": money_decimal(net),
        "account_nav_krw_decimal": money_decimal(account_nav),
        "reward_decimal": ratio_decimal(net / TOTAL_CAPITAL),
        "ledger": ledger,
    }


def jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def manifest_hash(manifest: Mapping[str, Any]) -> str:
    payload = {str(key): value for key, value in manifest.items() if key != "accounting_manifest_sha256"}
    encoded = json.dumps(jsonable(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def oracle_build_v51_slot_accounting_manifest(rows: Sequence[Mapping[str, Any]], horizon_id: str) -> dict[str, Any]:
    horizon = normalize_horizon(horizon_id)
    selections = normalize_rows(rows, horizon)
    scenarios = {scenario_id: scenario_manifest(selections, scenario_id, horizon) for scenario_id in SCENARIO_IDS}
    primary = scenarios[PRIMARY_SCENARIO_ID]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "horizon_id": horizon["horizon_id"],
        "horizon_days": horizon["horizon_days"],
        "label_column": horizon["label_column"],
        "total_capital_krw_decimal": money_decimal(TOTAL_CAPITAL),
        "slot_count": SLOT_COUNT,
        "slot_buy_budget_krw_decimal": money_decimal(SLOT_BUY_BUDGET),
        "max_deployed_principal_krw_decimal": money_decimal(MAX_DEPLOYED_PRINCIPAL),
        "reserve_cash_krw_decimal": money_decimal(RESERVE),
        "selected_count": len(selections),
        "symbols": [selection["symbol"] for selection in selections],
        "cost_scenarios": [scenario_payload(scenario_id, COST_SCENARIOS[scenario_id]) for scenario_id in SCENARIO_IDS],
        "scenario_manifests": scenarios,
        "primary_accounting": primary,
        "account_nav_krw_decimal": primary["account_nav_krw_decimal"],
        "deployed_principal_krw_decimal": primary["deployed_principal_krw_decimal"],
        "entry_cash_after_buy_costs_krw_decimal": primary["entry_cash_after_buy_costs_krw_decimal"],
    }
    manifest["accounting_manifest_sha256"] = manifest_hash(manifest)
    return manifest
