"""Research-only close-to-next-close 10-slot reward environment.

This module is an isolated Mode A accounting surface for the daily close-slot
lane. It converts causal per-date scores into a deterministic top-10 selection,
then re-ledgers the selection with integer shares, unused slot cash, and a
round-trip cost assumption. It does not expose live, broker, account, order,
paper-forward, or profitability readiness.
"""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .daily_close_slot_dataset import (
    COST_SENSITIVITY_BP,
    DEFAULT_SLOT_COUNT,
    DEFAULT_TOTAL_CAPITAL_KRW,
    FILL_MODE,
    ROUND_TRIP_COST_BP,
)

CLOSE_SLOT_ENV_SCHEMA_VERSION = 2
POLICY_ACTION_LABEL = "deterministic_score_and_pick_policy_action"
REPLAY_ADAPTER_LABEL = "selected_code_replay_adapter_only_not_policy_action"
SCORE_COLUMN = "score"
FUTURE_RETURN_COLUMN = "future_return_1d"
COST_SCENARIO_ZERO_CONTROL_0BP = "zero_control_0bp"
COST_SCENARIO_BASE_23BP = "base_23bp"
COST_SCENARIO_STRESS_46BP = "stress_46bp"
_KRW_QUANT = Decimal("0.000001")
_REWARD_QUANT = Decimal("0.000000000001")
_BP_DENOMINATOR = Decimal("10000")


@dataclass(frozen=True)
class CloseSlotCostScenario:
    scenario_id: str
    sell_tax_bp: float
    buy_commission_bp: float
    sell_commission_bp: float
    buy_slippage_bp: float
    sell_slippage_bp: float

    @property
    def total_bp(self) -> float:
        return (
            self.sell_tax_bp
            + self.buy_commission_bp
            + self.sell_commission_bp
            + self.buy_slippage_bp
            + self.sell_slippage_bp
        )

    def as_payload(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "sell_tax_bp": self.sell_tax_bp,
            "buy_commission_bp": self.buy_commission_bp,
            "sell_commission_bp": self.sell_commission_bp,
            "buy_slippage_bp": self.buy_slippage_bp,
            "sell_slippage_bp": self.sell_slippage_bp,
            "total_bp": self.total_bp,
        }


COST_SCENARIOS: dict[str, CloseSlotCostScenario] = {
    COST_SCENARIO_ZERO_CONTROL_0BP: CloseSlotCostScenario(
        scenario_id=COST_SCENARIO_ZERO_CONTROL_0BP,
        sell_tax_bp=0.0,
        buy_commission_bp=0.0,
        sell_commission_bp=0.0,
        buy_slippage_bp=0.0,
        sell_slippage_bp=0.0,
    ),
    COST_SCENARIO_BASE_23BP: CloseSlotCostScenario(
        scenario_id=COST_SCENARIO_BASE_23BP,
        sell_tax_bp=20.0,
        buy_commission_bp=1.5,
        sell_commission_bp=1.5,
        buy_slippage_bp=0.0,
        sell_slippage_bp=0.0,
    ),
    COST_SCENARIO_STRESS_46BP: CloseSlotCostScenario(
        scenario_id=COST_SCENARIO_STRESS_46BP,
        sell_tax_bp=20.0,
        buy_commission_bp=1.5,
        sell_commission_bp=1.5,
        buy_slippage_bp=11.5,
        sell_slippage_bp=11.5,
    ),
}

COST_SCENARIOS_BY_TOTAL_BP = {scenario.total_bp: scenario for scenario in COST_SCENARIOS.values()}


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _round_krw(value: Decimal) -> float:
    return float(value.quantize(_KRW_QUANT, rounding=ROUND_HALF_UP))


def _round_reward(value: Decimal) -> float:
    return float(value.quantize(_REWARD_QUANT, rounding=ROUND_HALF_UP))


def _component_cost(amount: float, bp: float) -> float:
    return _round_krw((_decimal(amount) * _decimal(bp)) / _BP_DENOMINATOR)


def _cost_scenario_for(cost_bp: int | float, cost_scenario_id: str | None = None) -> CloseSlotCostScenario:
    if cost_scenario_id is not None:
        try:
            return COST_SCENARIOS[str(cost_scenario_id)]
        except KeyError as exc:
            raise ValueError(f"unknown close-slot cost scenario: {cost_scenario_id}") from exc
    total_bp = float(cost_bp)
    scenario = COST_SCENARIOS_BY_TOTAL_BP.get(total_bp)
    if scenario is not None:
        return scenario
    raise ValueError(
        "scalar-only close-slot v2 cost accounting is not allowed; "
        f"use one of {sorted(COST_SCENARIOS)} or a matching sensitivity bp"
    )

@dataclass(frozen=True)
class CloseSlotCandidate:
    date: str
    table: str
    code: str
    score: float
    entry_close: float
    next_close: float
    future_return_1d: float
    split: str
    candidate_index: int
    source_row: Mapping[str, Any]


def _safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _truthy(value: Any, *, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    return default


def _candidate_code(row: Mapping[str, Any]) -> str:
    return str(row.get("code") or "").strip().zfill(6)


def _candidate_table(row: Mapping[str, Any], code: str) -> str:
    table = str(row.get("table") or "").strip()
    return table or f"A{code}"


def _row_score(row: Mapping[str, Any], score_column: str) -> float | None:
    if score_column in row:
        return _safe_float(row.get(score_column))
    return _safe_float(row.get("candidate_score_causal_momentum"))


def _row_future_return(row: Mapping[str, Any], entry_close: float | None, next_close: float | None) -> float | None:
    explicit = _safe_float(row.get(FUTURE_RETURN_COLUMN))
    if explicit is not None:
        return explicit
    if entry_close is None or next_close is None or entry_close <= 0:
        return None
    return (next_close - entry_close) / entry_close


def _invalid_row_reason(row: Mapping[str, Any], *, score_column: str) -> str | None:
    code = _candidate_code(row)
    if not code or code == "000000":
        return "MISSING_CODE"
    if not _truthy(row.get("eligible_for_selection"), default=True):
        return str(row.get("blocked_reason") or "INELIGIBLE_CANDIDATE")
    score = _row_score(row, score_column)
    if score is None:
        return "INVALID_SCORE"
    entry_close = _safe_float(row.get("entry_close"))
    if entry_close is None or entry_close <= 0:
        return "INVALID_ENTRY_CLOSE"
    next_close = _safe_float(row.get("next_close"))
    future_return = _row_future_return(row, entry_close, next_close)
    if next_close is None or next_close <= 0 or future_return is None:
        return "MISSING_NEXT_CLOSE"
    return None


def _candidate_from_row(row: Mapping[str, Any], *, score_column: str, candidate_index: int) -> CloseSlotCandidate:
    code = _candidate_code(row)
    entry_close = float(_safe_float(row.get("entry_close")) or 0.0)
    next_close = float(_safe_float(row.get("next_close")) or 0.0)
    future_return = _row_future_return(row, entry_close, next_close)
    return CloseSlotCandidate(
        date=str(row.get("date")),
        table=_candidate_table(row, code),
        code=code,
        score=float(_row_score(row, score_column) or 0.0),
        entry_close=entry_close,
        next_close=next_close,
        future_return_1d=float(future_return if future_return is not None else 0.0),
        split=str(row.get("split") or ""),
        candidate_index=int(candidate_index),
        source_row=row,
    )


def _candidate_payload(candidate: CloseSlotCandidate) -> dict[str, Any]:
    return {
        "date": candidate.date,
        "table": candidate.table,
        "code": candidate.code,
        "score": candidate.score,
        "entry_close": candidate.entry_close,
        "next_close": candidate.next_close,
        "future_return_1d": candidate.future_return_1d,
        "split": candidate.split,
        "candidate_index": candidate.candidate_index,
    }


def _slot_payload(
    slot: int,
    *,
    status: str,
    reason: str | None = None,
    candidate: CloseSlotCandidate | None = None,
    code: str | None = None,
    slot_state: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "slot": int(slot),
        "status": status,
        "reason": reason,
        "code": str(code or (candidate.code if candidate else "")) or None,
        "slot_state": slot_state or ("filled" if status == "selected" else "cash_hold" if status == "empty" else "replay_unfilled"),
    }
    if candidate is not None:
        payload["candidate"] = _candidate_payload(candidate)
    return payload


def normalize_close_slot_action(
    rows: Sequence[Mapping[str, Any]],
    *,
    date: str | None = None,
    score_column: str = SCORE_COLUMN,
    slot_count: int = DEFAULT_SLOT_COUNT,
    selected_codes: Sequence[str] | None = None,
    selection_threshold: float | None = None,
    threshold_inclusive: bool = True,
    max_slot_count: int | None = None,
) -> dict[str, Any]:
    """Normalize score rows into exact 10-slot deterministic research actions.

    ``selected_codes`` exists only for tests and replay adapters. Policy actions
    must provide scores and let this normalizer choose by score descending with
    stable code/table/index tie-breaking.
    """

    if int(slot_count) != DEFAULT_SLOT_COUNT:
        raise ValueError("daily close-slot action normalization requires slot_count=10")
    max_selection_count = int(max_slot_count if max_slot_count is not None else slot_count)
    if max_selection_count < 0 or max_selection_count > int(slot_count):
        raise ValueError("max_slot_count must be between 0 and slot_count")
    threshold = _safe_float(selection_threshold) if selection_threshold is not None else None
    scoped_rows = [dict(row) for row in rows if date is None or str(row.get("date")) == str(date)]
    diagnostics: dict[str, Any] = {
        "invalid_rows": [],
        "duplicate_candidate_rows": [],
        "duplicate_selected_codes": [],
        "missing_selected_codes": [],
        "selected_code_adapter_used": selected_codes is not None,
        "selected_code_adapter_policy_allowed": False,
    }
    candidates: list[CloseSlotCandidate] = []
    invalid_by_code: dict[str, str] = {}
    for index, row in enumerate(scoped_rows):
        code = _candidate_code(row)
        reason = _invalid_row_reason(row, score_column=score_column)
        if reason is not None:
            diagnostics["invalid_rows"].append({"row_index": index, "code": code or None, "reason": reason})
            if code:
                invalid_by_code.setdefault(code, reason)
            continue
        candidates.append(_candidate_from_row(row, score_column=score_column, candidate_index=index))

    ranked: list[CloseSlotCandidate] = []
    seen_codes: set[str] = set()
    for candidate in sorted(candidates, key=lambda item: (-item.score, item.code, item.table, item.candidate_index)):
        if candidate.code in seen_codes:
            diagnostics["duplicate_candidate_rows"].append(
                {
                    "code": candidate.code,
                    "table": candidate.table,
                    "candidate_index": candidate.candidate_index,
                    "reason": "DUPLICATE_CANDIDATE_CODE_EXCLUDED",
                }
            )
            continue
        seen_codes.add(candidate.code)
        ranked.append(candidate)

    def passes_threshold(candidate: CloseSlotCandidate) -> bool:
        if threshold is None:
            return True
        if threshold_inclusive:
            return candidate.score >= threshold
        return candidate.score > threshold

    slots: list[dict[str, Any]] = []
    action_label = POLICY_ACTION_LABEL
    if selected_codes is None:
        selectable = [candidate for candidate in ranked if passes_threshold(candidate)]
        for slot_index, candidate in enumerate(selectable[:max_selection_count]):
            slots.append(_slot_payload(slot_index, status="selected", candidate=candidate, slot_state="filled"))
    else:
        action_label = REPLAY_ADAPTER_LABEL
        ranked_by_code = {candidate.code: candidate for candidate in ranked}
        selected_seen: set[str] = set()
        for raw_code in selected_codes[:slot_count]:
            code = str(raw_code or "").strip().zfill(6)
            slot_index = len(slots)
            if code in selected_seen:
                diagnostics["duplicate_selected_codes"].append({"code": code, "reason": "DUPLICATE_SELECTED_CODE"})
                slots.append(
                    _slot_payload(
                        slot_index,
                        status="unfilled",
                        reason="DUPLICATE_SELECTED_CODE",
                        code=code,
                        slot_state="replay_unfilled",
                    )
                )
                continue
            selected_seen.add(code)
            candidate = ranked_by_code.get(code)
            if candidate is None:
                reason = invalid_by_code.get(code, "SELECTED_CODE_NOT_IN_VALID_CANDIDATES")
                diagnostics["missing_selected_codes"].append({"code": code, "reason": reason})
                slots.append(_slot_payload(slot_index, status="unfilled", reason=reason, code=code, slot_state="replay_unfilled"))
                continue
            slots.append(_slot_payload(slot_index, status="selected", candidate=candidate, slot_state="filled"))

    hold_reason = "SELECTION_THRESHOLD_NOT_MET" if threshold is not None else "EMPTY_SLOT"
    while len(slots) < slot_count:
        slots.append(_slot_payload(len(slots), status="empty", reason=hold_reason, slot_state="cash_hold"))
    selected_count = sum(1 for slot in slots if slot.get("status") == "selected")
    hold_cash_count = sum(1 for slot in slots if slot.get("slot_state") == "cash_hold")


    return {
        "schema_version": CLOSE_SLOT_ENV_SCHEMA_VERSION,
        "date": str(date or (scoped_rows[0].get("date") if scoped_rows else "")),
        "score_column": score_column,
        "slot_count": int(slot_count),
        "max_slot_count": max_selection_count,
        "selection_threshold": threshold,
        "threshold_inclusive": bool(threshold_inclusive),
        "action_label": action_label,
        "selected_code_lists": REPLAY_ADAPTER_LABEL,
        "ranked_candidates": [_candidate_payload(candidate) for candidate in ranked],
        "selected_count": selected_count,
        "hold_cash_count": hold_cash_count,
        "selection_slots": slots,
        "diagnostics": diagnostics,
    }


def account_close_slot_selection(
    normalized_action: Mapping[str, Any],
    *,
    total_capital_krw: int = DEFAULT_TOTAL_CAPITAL_KRW,
    slot_count: int = DEFAULT_SLOT_COUNT,
    cost_bp: int = ROUND_TRIP_COST_BP,
    cost_scenario_id: str | None = None,
) -> dict[str, Any]:
    """Ledger normalized slots with integer shares and round-trip cost."""

    if int(slot_count) != DEFAULT_SLOT_COUNT:
        raise ValueError("daily close-slot accounting requires slot_count=10")
    total_capital = int(total_capital_krw)
    if total_capital <= 0:
        raise ValueError("total_capital_krw must be positive")
    slot_cash = total_capital / int(slot_count)
    cost_scenario = _cost_scenario_for(cost_bp, cost_scenario_id)
    compatibility_cost_bp = int(cost_scenario.total_bp) if cost_scenario.total_bp.is_integer() else cost_scenario.total_bp
    cost_rate = cost_scenario.total_bp / 10_000.0
    ledger: list[dict[str, Any]] = []
    filled_slots = 0
    blocked_slots = 0
    unfilled_slots = 0
    gross_pnl_total = 0.0
    cost_total = 0.0
    net_pnl_total = 0.0
    unused_cash_total = 0.0
    hold_cash_slots = 0

    for slot in list(normalized_action.get("selection_slots") or [])[:slot_count]:
        slot_index = int(slot.get("slot", len(ledger)))
        candidate_payload = dict(slot.get("candidate") or {})
        status = str(slot.get("status") or "empty")
        reason = slot.get("reason")
        code = str(slot.get("code") or candidate_payload.get("code") or "").zfill(6) if (slot.get("code") or candidate_payload.get("code")) else None
        entry_close = _safe_float(candidate_payload.get("entry_close"))
        next_close = _safe_float(candidate_payload.get("next_close"))
        shares = 0
        notional = 0.0
        exit_value = 0.0
        gross_pnl = 0.0
        cost_krw = 0.0
        buy_commission_krw = 0.0
        buy_slippage_krw = 0.0
        sell_tax_krw = 0.0
        sell_commission_krw = 0.0
        sell_slippage_krw = 0.0
        net_pnl = 0.0
        unused_cash = slot_cash
        filled = False
        blocked = False
        slot_state = str(slot.get("slot_state") or ("filled" if status == "selected" else "cash_hold" if status == "empty" else "replay_unfilled"))
        if status == "selected":
            if entry_close is None or entry_close <= 0:
                reason = "INVALID_ENTRY_CLOSE"
                blocked = True
            elif next_close is None or next_close <= 0:
                reason = "MISSING_NEXT_CLOSE"
                blocked = True
            else:
                shares = int(math.floor(slot_cash / entry_close))
                if shares <= 0:
                    reason = "INSUFFICIENT_SLOT_CASH"
                    blocked = True
                else:
                    notional = shares * entry_close
                    exit_value = shares * next_close
                    gross_pnl = exit_value - notional
                    buy_commission_krw = _component_cost(notional, cost_scenario.buy_commission_bp)
                    buy_slippage_krw = _component_cost(notional, cost_scenario.buy_slippage_bp)
                    sell_tax_krw = _component_cost(exit_value, cost_scenario.sell_tax_bp)
                    sell_commission_krw = _component_cost(exit_value, cost_scenario.sell_commission_bp)
                    sell_slippage_krw = _component_cost(exit_value, cost_scenario.sell_slippage_bp)
                    cost_krw = _round_krw(
                        _decimal(buy_commission_krw)
                        + _decimal(buy_slippage_krw)
                        + _decimal(sell_tax_krw)
                        + _decimal(sell_commission_krw)
                        + _decimal(sell_slippage_krw)
                    )
                    net_pnl = _round_krw(_decimal(gross_pnl) - _decimal(cost_krw))
                    unused_cash = slot_cash - notional
                    filled = True
                    reason = None
                    slot_state = "filled"
        else:
            reason = str(reason or "EMPTY_SLOT")
            blocked = status == "unfilled"
            if status == "empty":
                slot_state = "cash_hold"
        if blocked and status == "selected":
            slot_state = "blocked_unfilled"
        if slot_state == "cash_hold":
            hold_cash_slots += 1


        if filled:
            filled_slots += 1
        else:
            unfilled_slots += 1
        if blocked:
            blocked_slots += 1
        gross_pnl_total += gross_pnl
        cost_total += cost_krw
        net_pnl_total += net_pnl
        unused_cash_total += unused_cash
        ledger.append(
            {
                "slot": slot_index,
                "code": code,
                "status": "filled" if filled else "unfilled",
                "unfilled_reason": None if filled else reason,
                "slot_state": slot_state if not filled else "filled",
                "blocked": bool(blocked),
                "entry_close": entry_close,
                "next_close": next_close,
                "shares": shares,
                "slot_cash_krw": slot_cash,
                "notional_krw": notional,
                "exit_value_krw": exit_value,
                "unused_cash_krw": unused_cash,
                "gross_pnl_krw": gross_pnl,
                "cost_krw": cost_krw,
                "sell_tax_bp": cost_scenario.sell_tax_bp,
                "buy_commission_bp": cost_scenario.buy_commission_bp,
                "sell_commission_bp": cost_scenario.sell_commission_bp,
                "buy_slippage_bp": cost_scenario.buy_slippage_bp,
                "sell_slippage_bp": cost_scenario.sell_slippage_bp,
                "buy_commission_krw": buy_commission_krw,
                "buy_slippage_krw": buy_slippage_krw,
                "sell_tax_krw": sell_tax_krw,
                "sell_commission_krw": sell_commission_krw,
                "sell_slippage_krw": sell_slippage_krw,
                "total_cost_krw": cost_krw,
                "net_pnl_krw": net_pnl,
                "net_return_on_total_capital": net_pnl / total_capital,
                "fill_mode": FILL_MODE,
            }
        )

    while len(ledger) < slot_count:
        slot_index = len(ledger)
        unfilled_slots += 1
        hold_cash_slots += 1
        unused_cash_total += slot_cash
        ledger.append(
            {
                "slot": slot_index,
                "code": None,
                "status": "unfilled",
                "unfilled_reason": "EMPTY_SLOT",
                "slot_state": "cash_hold",
                "blocked": False,
                "entry_close": None,
                "next_close": None,
                "shares": 0,
                "slot_cash_krw": slot_cash,
                "notional_krw": 0.0,
                "exit_value_krw": 0.0,
                "unused_cash_krw": slot_cash,
                "gross_pnl_krw": 0.0,
                "cost_krw": 0.0,
                "sell_tax_bp": cost_scenario.sell_tax_bp,
                "buy_commission_bp": cost_scenario.buy_commission_bp,
                "sell_commission_bp": cost_scenario.sell_commission_bp,
                "buy_slippage_bp": cost_scenario.buy_slippage_bp,
                "sell_slippage_bp": cost_scenario.sell_slippage_bp,
                "buy_commission_krw": 0.0,
                "buy_slippage_krw": 0.0,
                "sell_tax_krw": 0.0,
                "sell_commission_krw": 0.0,
                "sell_slippage_krw": 0.0,
                "total_cost_krw": 0.0,
                "net_pnl_krw": 0.0,
                "net_return_on_total_capital": 0.0,
                "fill_mode": FILL_MODE,
            }
        )

    return {
        "schema_version": CLOSE_SLOT_ENV_SCHEMA_VERSION,
        "date": normalized_action.get("date"),
        "action_label": normalized_action.get("action_label"),
        "slot_count": int(slot_count),
        "total_capital_krw": total_capital,
        "slot_cash_krw": slot_cash,
        "round_trip_cost_bp": compatibility_cost_bp,
        "round_trip_cost_rate": cost_rate,
        "cost_scenario": cost_scenario.as_payload(),
        "cost_scenario_id": cost_scenario.scenario_id,
        "fill_mode": FILL_MODE,
        "gross_pnl_krw": gross_pnl_total,
        "cost_krw": cost_total,
        "net_pnl_krw": net_pnl_total,
        "reward": _round_reward(_decimal(net_pnl_total) / _decimal(total_capital)),
        "unused_cash_krw": unused_cash_total,
        "filled_slots": filled_slots,
        "unfilled_slots": unfilled_slots,
        "blocked_slots": blocked_slots,
        "selected_count": int(normalized_action.get("selected_count", filled_slots)),
        "hold_cash_count": hold_cash_slots,
        "max_slot_count": int(normalized_action.get("max_slot_count", slot_count)),
        "ledger": ledger,
        "diagnostics": normalized_action.get("diagnostics", {}),
    }


def evaluate_close_slot_day(
    rows: Sequence[Mapping[str, Any]],
    *,
    date: str | None = None,
    score_column: str = SCORE_COLUMN,
    slot_count: int = DEFAULT_SLOT_COUNT,
    total_capital_krw: int = DEFAULT_TOTAL_CAPITAL_KRW,
    cost_bp: int = ROUND_TRIP_COST_BP,
    selected_codes: Sequence[str] | None = None,
    cost_scenario_id: str | None = None,
    selection_threshold: float | None = None,
    threshold_inclusive: bool = True,
    max_slot_count: int | None = None,
) -> dict[str, Any]:
    normalized = normalize_close_slot_action(
        rows,
        date=date,
        score_column=score_column,
        slot_count=slot_count,
        selected_codes=selected_codes,
        selection_threshold=selection_threshold,
        threshold_inclusive=threshold_inclusive,
        max_slot_count=max_slot_count,
    )
    ledger = account_close_slot_selection(
        normalized,
        total_capital_krw=total_capital_krw,
        slot_count=slot_count,
        cost_bp=cost_bp,
        cost_scenario_id=cost_scenario_id,
    )
    return {"normalized_action": normalized, "ledger": ledger}


def evaluate_close_slot_cost_sensitivity(
    rows: Sequence[Mapping[str, Any]],
    *,
    date: str | None = None,
    score_column: str = SCORE_COLUMN,
    slot_count: int = DEFAULT_SLOT_COUNT,
    total_capital_krw: int = DEFAULT_TOTAL_CAPITAL_KRW,
    cost_bp_values: Sequence[int] = tuple(COST_SENSITIVITY_BP),
    selected_codes: Sequence[str] | None = None,
    selection_threshold: float | None = None,
    threshold_inclusive: bool = True,
    max_slot_count: int | None = None,
) -> dict[str, Any]:
    normalized = normalize_close_slot_action(
        rows,
        date=date,
        score_column=score_column,
        slot_count=slot_count,
        selected_codes=selected_codes,
        selection_threshold=selection_threshold,
        threshold_inclusive=threshold_inclusive,
        max_slot_count=max_slot_count,
    )
    results = {
        str(int(cost_bp)): account_close_slot_selection(
            normalized,
            total_capital_krw=total_capital_krw,
            slot_count=slot_count,
            cost_bp=int(cost_bp),
        )
        for cost_bp in cost_bp_values
    }
    return {
        "schema_version": CLOSE_SLOT_ENV_SCHEMA_VERSION,
        "date": normalized.get("date"),
        "cost_sensitivity_bp": [int(value) for value in cost_bp_values],
        "primary_cost_bp": ROUND_TRIP_COST_BP,
        "normalized_action": normalized,
        "results_by_cost_bp": results,
    }


class DailyCloseSlotEnv:
    """Small deterministic environment over per-date close-slot candidate rows."""

    def __init__(
        self,
        rows: Sequence[Mapping[str, Any]],
        *,
        split: str | None = None,
        score_column: str = SCORE_COLUMN,
        slot_count: int = DEFAULT_SLOT_COUNT,
        total_capital_krw: int = DEFAULT_TOTAL_CAPITAL_KRW,
        cost_bp: int = ROUND_TRIP_COST_BP,
        cost_scenario_id: str | None = None,
        selection_threshold: float | None = None,
        threshold_inclusive: bool = True,
        max_slot_count: int | None = None,
    ) -> None:
        self.rows = [dict(row) for row in rows if split is None or str(row.get("split")) == str(split)]
        self.score_column = score_column
        self.slot_count = int(slot_count)
        self.total_capital_krw = int(total_capital_krw)
        self.cost_bp = int(cost_bp)
        self.cost_scenario_id = cost_scenario_id
        self.selection_threshold = selection_threshold
        self.threshold_inclusive = bool(threshold_inclusive)
        self.max_slot_count = max_slot_count
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in self.rows:
            grouped.setdefault(str(row.get("date")), []).append(row)
        self.rows_by_date = grouped
        self.dates = sorted(grouped)
        self.index = 0
        self.last_info: dict[str, Any] = {}

    def reset(self) -> dict[str, Any]:
        self.index = 0
        self.last_info = {"event": "reset", "date_count": len(self.dates), "fill_mode": FILL_MODE}
        return self.state()

    def done(self) -> bool:
        return self.index >= len(self.dates)

    def state(self) -> dict[str, Any]:
        if self.done():
            return {"done": True, "date": None, "candidate_count": 0, "slot_count": self.slot_count}
        date = self.dates[self.index]
        return {
            "done": False,
            "date": date,
            "candidate_count": len(self.rows_by_date.get(date, [])),
            "slot_count": self.slot_count,
            "score_column": self.score_column,
            "fill_mode": FILL_MODE,
            "selection_threshold": self.selection_threshold,
            "max_slot_count": self.max_slot_count if self.max_slot_count is not None else self.slot_count,
        }

    def _rows_with_action_scores(self, action: Any, date: str) -> tuple[list[dict[str, Any]], Sequence[str] | None]:
        base_rows = [dict(row) for row in self.rows_by_date.get(date, [])]
        if action is None:
            return base_rows, None
        if isinstance(action, Mapping):
            scores_by_code = {str(code).zfill(6): _safe_float(score) for code, score in action.items()}
            for row in base_rows:
                code = _candidate_code(row)
                if code in scores_by_code:
                    row[self.score_column] = scores_by_code[code]
            return base_rows, None
        if isinstance(action, Sequence) and not isinstance(action, (str, bytes)):
            values = list(action)
            if all(not isinstance(value, Mapping) for value in values):
                return base_rows, [str(value).zfill(6) for value in values]
            scores_by_code = {
                _candidate_code(value): _safe_float(value.get(self.score_column, value.get("score")))
                for value in values
                if isinstance(value, Mapping)
            }
            for row in base_rows:
                code = _candidate_code(row)
                if code in scores_by_code:
                    row[self.score_column] = scores_by_code[code]
            return base_rows, None
        raise TypeError("action must be None, a code->score mapping, a score-row sequence, or a selected-code replay sequence")

    def step(self, action: Any = None) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        if self.done():
            raise StopIteration("DailyCloseSlotEnv is done")
        date = self.dates[self.index]
        rows, selected_codes = self._rows_with_action_scores(action, date)
        result = evaluate_close_slot_day(
            rows,
            date=date,
            score_column=self.score_column,
            slot_count=self.slot_count,
            total_capital_krw=self.total_capital_krw,
            cost_bp=self.cost_bp,
            selected_codes=selected_codes,
            cost_scenario_id=self.cost_scenario_id,
            selection_threshold=self.selection_threshold,
            threshold_inclusive=self.threshold_inclusive,
            max_slot_count=self.max_slot_count,
        )
        self.index += 1
        info = {
            "date": date,
            "normalized_action": result["normalized_action"],
            "ledger": result["ledger"],
            "selected_codes_replay_adapter": selected_codes is not None,
            "fill_mode": FILL_MODE,
        }
        self.last_info = info
        return self.state(), float(result["ledger"]["reward"]), self.done(), info


__all__ = [
    "CLOSE_SLOT_ENV_SCHEMA_VERSION",
    "POLICY_ACTION_LABEL",
    "REPLAY_ADAPTER_LABEL",
    "COST_SCENARIOS",
    "COST_SCENARIO_ZERO_CONTROL_0BP",
    "COST_SCENARIO_BASE_23BP",
    "COST_SCENARIO_STRESS_46BP",
    "CloseSlotCostScenario",
    "CloseSlotCandidate",
    "DailyCloseSlotEnv",
    "account_close_slot_selection",
    "evaluate_close_slot_cost_sensitivity",
    "evaluate_close_slot_day",
    "normalize_close_slot_action",
]
