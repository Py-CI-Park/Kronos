"""Costed D-close to next-open binary portfolio transition engine."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP

from .daily_market_transition_contract import (
    ActionName,
    BinaryAction,
    BinaryMarketTransition,
    DailyMarketCandidate,
    MarketState,
    MarketTransitionConfig,
    SlotTransition,
    build_market_state,
)

MONEY_QUANTUM = Decimal("0.000001")
PERCENT_DENOMINATOR = Decimal("100")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _rate(percent: Decimal) -> Decimal:
    return percent / PERCENT_DENOMINATOR


def _drawdown(nav: Decimal, peak: Decimal) -> Decimal:
    return min(Decimal("0"), (nav / peak) - Decimal("1"))


def _validate_transition_identity(
    state: MarketState,
    candidates: Sequence[DailyMarketCandidate],
) -> dict[str, DailyMarketCandidate]:
    rebuilt = build_market_state(
        list(candidates),
        feature_vector=state.feature_vector,
        previous_exposure_ratio=state.previous_exposure_ratio,
        previous_drawdown=state.previous_drawdown,
    )
    if rebuilt.state_hash != state.state_hash:
        raise ValueError("candidate identity does not match the recorded market state")
    entry_dates = {candidate.entry_date for candidate in candidates}
    exit_dates = {candidate.exit_date for candidate in candidates}
    if len(entry_dates) != 1 or len(exit_dates) != 1:
        raise ValueError("one transition requires a shared entry and exit date")
    return {candidate.table: candidate for candidate in candidates}


def _cash_transition(
    state: MarketState,
    requested_action: ActionName,
    previous_nav: Decimal,
    previous_peak: Decimal,
    config: MarketTransitionConfig,
    reason: str,
) -> BinaryMarketTransition:
    peak = max(previous_peak, previous_nav)
    return BinaryMarketTransition(
        schema_version="kronos_daily_market_transition.v1",
        state_hash=state.state_hash,
        requested_action=requested_action,
        executed_action="CASH",
        action_recorded=True,
        execution_reason=reason,
        previous_nav_krw=_money(previous_nav),
        previous_peak_nav_krw=_money(previous_peak),
        final_nav_krw=_money(previous_nav),
        peak_nav_krw=_money(peak),
        cash_after_entry_krw=_money(previous_nav),
        deployed_at_entry_krw=Decimal("0"),
        gross_pnl_krw=Decimal("0"),
        total_cost_krw=Decimal("0"),
        net_pnl_krw=Decimal("0"),
        economic_return_fraction=Decimal("0"),
        reward_log_nav=Decimal("0"),
        drawdown_fraction=_drawdown(previous_nav, peak),
        round_trip_cost_percent=config.round_trip_cost_percent,
        filled_slots=0,
        ledger=(),
        reward_kind="log_nav_return",
        reward_unit="fraction",
        equity_kind="krw_nav",
        equity_unit="krw",
        research_scope="LOCAL_RETROSPECTIVE_RESEARCH",
        promotion_allowed=False,
        fresh_oos_read=False,
    )


def _slot_transition(
    slot: int,
    candidate: DailyMarketCandidate,
    slot_budget: Decimal,
    config: MarketTransitionConfig,
) -> SlotTransition | None:
    buy_rate = _rate(config.buy_commission_percent + config.buy_slippage_percent)
    sell_rate = _rate(
        config.sell_commission_percent
        + config.sell_tax_percent
        + config.sell_slippage_percent
    )
    effective_entry = candidate.entry_open_krw * (Decimal("1") + buy_rate)
    shares = int((slot_budget / effective_entry).to_integral_value(rounding=ROUND_FLOOR))
    if shares <= 0:
        return None
    entry_notional = _money(candidate.entry_open_krw * shares)
    exit_notional = _money(candidate.exit_open_krw * shares)
    buy_cost = _money(entry_notional * buy_rate)
    sell_cost = _money(exit_notional * sell_rate)
    gross_pnl = _money(exit_notional - entry_notional)
    net_pnl = _money(gross_pnl - buy_cost - sell_cost)
    return SlotTransition(
        slot=slot,
        table=candidate.table,
        code=candidate.code,
        shares=shares,
        entry_open_krw=candidate.entry_open_krw,
        exit_open_krw=candidate.exit_open_krw,
        entry_notional_krw=entry_notional,
        exit_notional_krw=exit_notional,
        buy_cost_krw=buy_cost,
        sell_cost_krw=sell_cost,
        gross_pnl_krw=gross_pnl,
        net_pnl_krw=net_pnl,
    )


def execute_binary_transition(
    state: MarketState,
    candidates: Sequence[DailyMarketCandidate],
    action: BinaryAction | int,
    *,
    previous_nav_krw: Decimal,
    previous_peak_nav_krw: Decimal,
    config: MarketTransitionConfig | None = None,
) -> BinaryMarketTransition:
    """Execute one research-only binary action without exposing future prices to state."""
    selected_config = config or MarketTransitionConfig()
    if previous_nav_krw <= 0 or previous_peak_nav_krw <= 0:
        raise ValueError("previous NAV and peak NAV must be positive")
    candidate_by_table = _validate_transition_identity(state, candidates)
    try:
        requested = BinaryAction(action)
    except ValueError as exc:
        raise ValueError(f"unsupported binary market action: {action}") from exc
    requested_name: ActionName = (
        "CASH" if requested is BinaryAction.CASH else "INVEST_TOP10_EQUAL_SLOT"
    )
    if requested is BinaryAction.CASH:
        return _cash_transition(
            state,
            requested_name,
            previous_nav_krw,
            previous_peak_nav_krw,
            selected_config,
            "REQUESTED_CASH",
        )

    investable = min(
        selected_config.stock_exposure_cap_krw,
        max(Decimal("0"), previous_nav_krw - selected_config.cash_reserve_floor_krw),
    )
    if investable <= 0:
        return _cash_transition(
            state,
            requested_name,
            previous_nav_krw,
            previous_peak_nav_krw,
            selected_config,
            "CASH_RESERVE_FLOOR_BLOCKED_INVESTMENT",
        )
    slot_budget = investable / selected_config.max_slots
    ledger = tuple(
        row
        for slot, table in enumerate(state.candidate_tables[: selected_config.max_slots])
        if (candidate := candidate_by_table.get(table)) is not None
        if (row := _slot_transition(slot, candidate, slot_budget, selected_config)) is not None
    )
    if not ledger:
        return _cash_transition(
            state,
            requested_name,
            previous_nav_krw,
            previous_peak_nav_krw,
            selected_config,
            "NO_AFFORDABLE_SLOT",
        )

    deployed = _money(sum((row.entry_notional_krw for row in ledger), Decimal("0")))
    buy_cost = _money(sum((row.buy_cost_krw for row in ledger), Decimal("0")))
    cash_after_entry = _money(previous_nav_krw - deployed - buy_cost)
    if cash_after_entry < selected_config.cash_reserve_floor_krw:
        raise AssertionError("cash reserve invariant violated")
    exit_value = _money(sum((row.exit_notional_krw for row in ledger), Decimal("0")))
    sell_cost = _money(sum((row.sell_cost_krw for row in ledger), Decimal("0")))
    gross_pnl = _money(sum((row.gross_pnl_krw for row in ledger), Decimal("0")))
    total_cost = _money(buy_cost + sell_cost)
    final_nav = _money(cash_after_entry + exit_value - sell_cost)
    net_pnl = _money(final_nav - previous_nav_krw)
    economic_return = (final_nav / previous_nav_krw) - Decimal("1")
    reward = (final_nav / previous_nav_krw).ln()
    peak = max(previous_peak_nav_krw, previous_nav_krw, final_nav)
    return BinaryMarketTransition(
        schema_version="kronos_daily_market_transition.v1",
        state_hash=state.state_hash,
        requested_action=requested_name,
        executed_action="INVEST_TOP10_EQUAL_SLOT",
        action_recorded=True,
        execution_reason="TOP10_EQUAL_SLOT_FILLED",
        previous_nav_krw=_money(previous_nav_krw),
        previous_peak_nav_krw=_money(previous_peak_nav_krw),
        final_nav_krw=final_nav,
        peak_nav_krw=_money(peak),
        cash_after_entry_krw=cash_after_entry,
        deployed_at_entry_krw=deployed,
        gross_pnl_krw=gross_pnl,
        total_cost_krw=total_cost,
        net_pnl_krw=net_pnl,
        economic_return_fraction=economic_return,
        reward_log_nav=reward,
        drawdown_fraction=_drawdown(final_nav, peak),
        round_trip_cost_percent=selected_config.round_trip_cost_percent,
        filled_slots=len(ledger),
        ledger=ledger,
        reward_kind="log_nav_return",
        reward_unit="fraction",
        equity_kind="krw_nav",
        equity_unit="krw",
        research_scope="LOCAL_RETROSPECTIVE_RESEARCH",
        promotion_allowed=False,
        fresh_oos_read=False,
    )


__all__ = ["execute_binary_transition"]
