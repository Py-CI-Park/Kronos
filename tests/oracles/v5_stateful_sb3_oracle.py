"""Independent Decimal oracle for SB3_T_DECIDE_T1_FILL_STATEFUL_V1 tests.

This module intentionally imports no production accounting or environment helpers.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Any, Dict, Iterable, List, Mapping

getcontext().prec = 40

_QUANT = Decimal("0.000001")
BP_DENOMINATOR = Decimal("10000")
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


def dec(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def q(value: Any) -> str:
    amount = dec(value).quantize(_QUANT, rounding=ROUND_HALF_UP)
    if amount == 0:
        amount = abs(amount)
    return str(amount)

def money(value: Any) -> Decimal:
    amount = dec(value).quantize(_QUANT, rounding=ROUND_HALF_UP)
    return abs(amount) if amount == 0 else amount


def _scenario_for_cost(cost_bps: Any) -> tuple[str, Dict[str, Decimal]]:
    total = dec(cost_bps)
    for scenario_id, scenario in COST_SCENARIOS.items():
        scenario_total = sum(scenario.values(), Decimal("0"))
        if scenario_total == total:
            return scenario_id, scenario
    raise ValueError(f"oracle requires a V5 0/23/46 cost scenario, got {cost_bps!r}")


def _component_cost(gross: Decimal, bp: Decimal) -> Decimal:
    return money((gross * bp) / BP_DENOMINATOR)


def _zero_components() -> Dict[str, Decimal]:
    return {
        "buy_commission_krw": Decimal("0"),
        "buy_slippage_krw": Decimal("0"),
        "sell_tax_krw": Decimal("0"),
        "sell_commission_krw": Decimal("0"),
        "sell_slippage_krw": Decimal("0"),
    }


def _buy_rate(scenario: Mapping[str, Decimal]) -> Decimal:
    return (
        scenario["buy_commission_bp"] + scenario["buy_slippage_bp"]
    ) / BP_DENOMINATOR


def _buy_components(
    gross: Decimal,
    scenario: Mapping[str, Decimal],
) -> Dict[str, Decimal]:
    components = _zero_components()
    components["buy_commission_krw"] = _component_cost(
        gross,
        scenario["buy_commission_bp"],
    )
    components["buy_slippage_krw"] = _component_cost(
        gross,
        scenario["buy_slippage_bp"],
    )
    return components


def _buy_cash_needed(
    price: Decimal,
    quantity: Decimal,
    scenario: Mapping[str, Decimal],
) -> Decimal:
    gross = price * quantity
    components = _buy_components(gross, scenario)
    return gross + sum(components.values(), Decimal("0"))


def _buy_quantity(
    *,
    cash: Decimal,
    nav_before: Decimal,
    buy_fraction: Decimal,
    price: Decimal,
    scenario: Mapping[str, Decimal],
) -> Decimal:
    if price <= 0:
        return Decimal("0")
    target_notional = nav_before * buy_fraction
    target_quantity = (
        int(target_notional / price) if target_notional > 0 else 0
    )
    affordable_quantity = (
        int(cash / (price * (Decimal("1") + _buy_rate(scenario))))
        if cash > 0
        else 0
    )
    quantity = min(target_quantity, affordable_quantity)
    tolerance = Decimal("0.00000001")
    while (
        quantity > 0
        and _buy_cash_needed(price, Decimal(quantity), scenario) > cash + tolerance
    ):
        quantity -= 1
    return Decimal(max(0, quantity))


def _add_components(left: Dict[str, Decimal], right: Mapping[str, Decimal]) -> None:
    for key, value in right.items():
        left[key] += value


def _symbol(value: Any) -> str:
    raw = str(value)
    return raw.zfill(6) if raw.isdigit() else raw


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip().lower()
    return text in {"", "nan", "nat", "none"}


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _timestamps(records: Iterable[Mapping[str, Any]]) -> List[str]:
    return sorted({str(row["timestamp"]) for row in records})


def _rows_at(records: Iterable[Mapping[str, Any]], timestamp: str) -> List[Dict[str, Any]]:
    rows = [dict(row) for row in records if str(row["timestamp"]) == timestamp]
    return sorted(rows, key=lambda row: (-float(row["rank_score"]), _symbol(row["symbol"])))


def _top(rows: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    return rows[: max(1, int(top_k))]


def _marks(rows: List[Dict[str, Any]]) -> Dict[str, Decimal]:
    return {_symbol(row["symbol"]): dec(row["price"]) for row in rows}


def _fill_price(row: Mapping[str, Any] | None) -> Decimal | None:
    if row is None:
        return None
    if not _truthy(row.get("fillable", True)):
        return None
    value = row.get("fill_price")
    if _is_missing(value):
        return None
    price = dec(value)
    return price if price > 0 else None


def _nav(cash: Decimal, positions: Mapping[str, Mapping[str, Decimal]], marks: Mapping[str, Decimal]) -> Decimal:
    total = cash
    for symbol, lot in positions.items():
        if symbol not in marks:
            raise KeyError(f"Missing mark price for held symbol: {symbol}")
        total += lot["quantity"] * marks[symbol]
    return total


def _mask(
    *,
    top_rows: List[Dict[str, Any]],
    current_rows: List[Dict[str, Any]],
    positions: Mapping[str, Mapping[str, Decimal]],
    cash: Decimal,
    nav_before: Decimal,
    buy_fraction: Decimal,
    scenario: Mapping[str, Decimal],
    top_k: int,
    max_positions: int,
) -> List[int]:
    mask = [0] * (1 + int(top_k) + int(max_positions))
    mask[0] = 1
    can_buy = len(positions) < int(max_positions) and cash > 0
    for slot, row in enumerate(top_rows):
        symbol = _symbol(row["symbol"])
        price = _fill_price(row)
        if (
            slot < int(top_k)
            and can_buy
            and symbol not in positions
            and price is not None
            and _buy_quantity(
                cash=cash,
                nav_before=nav_before,
                buy_fraction=buy_fraction,
                price=price,
                scenario=scenario,
            )
            > 0
        ):
            mask[1 + slot] = 1
    sell_offset = 1 + int(top_k)
    for slot, symbol_value in enumerate(sorted(positions)[: int(max_positions)]):
        row = next(
            (
                candidate
                for candidate in current_rows
                if _symbol(candidate["symbol"]) == symbol_value
            ),
            None,
        )
        if _fill_price(row) is not None:
            mask[sell_offset + slot] = 1

    return mask


def _buy(
    *,
    positions: Dict[str, Dict[str, Decimal]],
    cash: Decimal,
    symbol: str,
    price: Decimal,
    quantity: Decimal,
    scenario: Mapping[str, Decimal],
) -> tuple[Decimal, Decimal, Dict[str, Decimal]]:
    gross = price * quantity
    components = _buy_components(gross, scenario)
    cost = sum(components.values(), Decimal("0"))
    previous = positions.get(symbol, {"quantity": Decimal("0"), "average_price": Decimal("0")})
    new_quantity = previous["quantity"] + quantity
    average_price = ((previous["quantity"] * previous["average_price"]) + gross) / new_quantity
    positions[symbol] = {"quantity": new_quantity, "average_price": average_price}
    return cash - gross - cost, gross, components


def _sell(
    *,
    positions: Dict[str, Dict[str, Decimal]],
    cash: Decimal,
    symbol: str,
    price: Decimal,
    scenario: Mapping[str, Decimal],
) -> tuple[Decimal, Decimal, Dict[str, Decimal]]:
    lot = positions[symbol]
    quantity = lot["quantity"]
    gross = quantity * price
    components = _zero_components()
    components["sell_tax_krw"] = _component_cost(gross, scenario["sell_tax_bp"])
    components["sell_commission_krw"] = _component_cost(gross, scenario["sell_commission_bp"])
    components["sell_slippage_krw"] = _component_cost(gross, scenario["sell_slippage_bp"])
    cost = sum(components.values(), Decimal("0"))
    del positions[symbol]
    return cash + gross - cost, gross, components


def simulate_stateful_sb3(
    records: Iterable[Mapping[str, Any]],
    actions: Iterable[int],
    *,
    initial_cash: Decimal | int | str = Decimal("1000"),
    buy_fraction: Decimal | str = Decimal("0.5"),
    cost_bps: Decimal | int | str = Decimal("23"),
    slippage_bps: Decimal | int | str = Decimal("0"),
    top_k: int = 3,
    max_positions: int = 2,
    turnover_penalty: Decimal | str = Decimal("0.001"),
    invalid_penalty: Decimal | str = Decimal("0.001"),
    reward_mode: str = "shaped",
    terminal_liquidation: bool = True,
) -> List[Dict[str, Any]]:
    rows = [dict(row) for row in records]
    timestamps = _timestamps(rows)
    cash = dec(initial_cash)
    buy_fraction_dec = dec(buy_fraction)
    if dec(slippage_bps) != 0:
        raise ValueError("oracle V5 stateful schedules include slippage in the 0/23/46 scenario")
    scenario_id, scenario = _scenario_for_cost(cost_bps)


    turnover_penalty_dec = dec(turnover_penalty)
    invalid_penalty_dec = dec(invalid_penalty)
    positions: Dict[str, Dict[str, Decimal]] = {}
    output: List[Dict[str, Any]] = []

    for step, raw_action in enumerate(actions):
        timestamp = timestamps[step]
        current_rows = _rows_at(rows, timestamp)
        top_rows = _top(current_rows, top_k)
        marks_before = _marks(current_rows)
        nav_before = _nav(cash, positions, marks_before)
        mask = _mask(
            top_rows=top_rows,
            current_rows=current_rows,
            positions=positions,
            cash=cash,
            nav_before=nav_before,
            buy_fraction=buy_fraction_dec,
            scenario=scenario,
            top_k=top_k,
            max_positions=max_positions,
        )
        action = int(raw_action)
        in_space = 0 <= action < len(mask)
        invalid = (not in_space) or not bool(mask[action])
        executed_action = 0 if invalid else action
        step_gross = Decimal("0")
        step_components = _zero_components()
        terminal_count = 0


        if not invalid and action != 0:
            if 1 <= action <= int(top_k):
                row = top_rows[action - 1]
                symbol = _symbol(row["symbol"])
                price = _fill_price(row)
                if price is None:
                    raise AssertionError("oracle buy mask allowed an unfillable row")
                quantity = _buy_quantity(
                    cash=cash,
                    nav_before=nav_before,
                    buy_fraction=buy_fraction_dec,
                    price=price,
                    scenario=scenario,
                )
                if quantity <= 0:
                    raise AssertionError("oracle buy mask allowed an unaffordable row")
                cash, gross, components = _buy(
                    positions=positions,
                    cash=cash,
                    symbol=symbol,
                    price=price,
                    quantity=quantity,
                    scenario=scenario,
                )
                step_gross += gross
                _add_components(step_components, components)

            else:
                sell_slot = action - int(top_k) - 1
                symbol = sorted(positions)[sell_slot]
                row = next((candidate for candidate in current_rows if _symbol(candidate["symbol"]) == symbol), None)
                price = _fill_price(row) if row is not None else None
                if price is None:
                    raise AssertionError("oracle sell mask allowed an unfillable row")
                cash, gross, components = _sell(positions=positions, cash=cash, symbol=symbol, price=price, scenario=scenario)
                step_gross += gross
                _add_components(step_components, components)


        terminated = step + 1 >= len(timestamps)
        after_rows = current_rows if terminated else _rows_at(rows, timestamps[step + 1])
        marks_after = _marks(after_rows)
        if terminated and terminal_liquidation:
            for symbol in list(sorted(positions)):
                cash, gross, components = _sell(positions=positions, cash=cash, symbol=symbol, price=marks_after[symbol], scenario=scenario)
                step_gross += gross
                _add_components(step_components, components)
                terminal_count += 1

        nav_after = _nav(cash, positions, marks_after)
        nav_return = (nav_after - nav_before) / nav_before if nav_before else Decimal("0")
        turnover_ratio = step_gross / nav_before if nav_before else Decimal("0")
        step_cost = sum(step_components.values(), Decimal("0"))

        reward = nav_return
        if reward_mode == "shaped":
            reward -= turnover_penalty_dec * turnover_ratio

            if invalid:
                reward -= invalid_penalty_dec
        output.append(
            {
                "step": step,
                "raw_action": action,
                "executed_action": executed_action,
                "invalid_action": invalid,
                "cash": q(cash),
                "nav": q(nav_after),
                "nav_return": q(nav_return),
                "turnover_krw": q(step_gross),
                "turnover_ratio": q(turnover_ratio),
                "cost_scenario_id": scenario_id,
                "buy_commission_krw": q(step_components["buy_commission_krw"]),
                "buy_slippage_krw": q(step_components["buy_slippage_krw"]),
                "sell_tax_krw": q(step_components["sell_tax_krw"]),
                "sell_commission_krw": q(step_components["sell_commission_krw"]),
                "sell_slippage_krw": q(step_components["sell_slippage_krw"]),
                "total_cost_krw": q(step_cost),
                "reward": q(reward),
                "terminal_liquidation_count": terminal_count,
                "positions": {symbol: q(lot["quantity"]) for symbol, lot in sorted(positions.items())},
            }
        )
    return output
