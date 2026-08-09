"""Four-action wrapper around the audited daily-market accounting engine."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from decimal import Decimal

from .daily_market_allocation_contract import (
    SLOT_NOTIONAL_KRW,
    AllocationAction,
    AllocationMarketTransition,
    allocation_action_name,
    allocation_slot_count,
)
from .daily_market_errors import DailyMarketTransitionError
from .daily_market_transition import execute_binary_transition
from .daily_market_transition_contract import (
    BinaryAction,
    DailyMarketCandidate,
    MarketState,
    MarketTransitionConfig,
    build_market_state,
)


def _ranked_candidates(
    state: MarketState,
    candidates: Sequence[DailyMarketCandidate],
) -> tuple[DailyMarketCandidate, ...]:
    rebuilt = build_market_state(
        candidates,
        feature_vector=state.feature_vector,
        previous_exposure_ratio=state.previous_exposure_ratio,
        previous_drawdown=state.previous_drawdown,
    )
    if rebuilt.state_hash != state.state_hash:
        raise DailyMarketTransitionError(
            "candidate identity does not match the recorded allocation state"
        )
    return tuple(
        sorted(candidates, key=lambda candidate: (-candidate.score, candidate.code))[
            :10
        ]
    )


def execute_allocation_transition(
    state: MarketState,
    candidates: Sequence[DailyMarketCandidate],
    action: AllocationAction | int,
    *,
    previous_nav_krw: Decimal,
    previous_peak_nav_krw: Decimal,
    config: MarketTransitionConfig | None = None,
) -> AllocationMarketTransition:
    """Execute cash/top-3/top-5/top-10 with a fixed 5 million KRW slot budget."""
    try:
        requested = AllocationAction(action)
    except ValueError as exc:
        raise DailyMarketTransitionError(
            f"unsupported allocation action: {action}"
        ) from exc
    requested_name = allocation_action_name(requested)
    ranked = _ranked_candidates(state, candidates)
    selected_config = config or MarketTransitionConfig()
    slot_count = allocation_slot_count(requested)
    if slot_count == 0:
        accounting = execute_binary_transition(
            state,
            ranked,
            BinaryAction.CASH,
            previous_nav_krw=previous_nav_krw,
            previous_peak_nav_krw=previous_peak_nav_krw,
            config=selected_config,
        )
        return AllocationMarketTransition(requested_name, "CASH", accounting)

    selected = ranked[:slot_count]
    selected_state = build_market_state(
        selected,
        feature_vector=state.feature_vector,
        previous_exposure_ratio=state.previous_exposure_ratio,
        previous_drawdown=state.previous_drawdown,
    )
    allocation_config = replace(
        selected_config,
        stock_exposure_cap_krw=Decimal(SLOT_NOTIONAL_KRW * slot_count),
        max_slots=slot_count,
    )
    accounting = execute_binary_transition(
        selected_state,
        selected,
        BinaryAction.INVEST_TOP10_EQUAL_SLOT,
        previous_nav_krw=previous_nav_krw,
        previous_peak_nav_krw=previous_peak_nav_krw,
        config=allocation_config,
    )
    executed_name = requested_name if accounting.executed_action != "CASH" else "CASH"
    return AllocationMarketTransition(requested_name, executed_name, accounting)


__all__ = ["execute_allocation_transition"]
