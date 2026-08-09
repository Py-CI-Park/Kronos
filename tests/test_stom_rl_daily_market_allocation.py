from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from stom_rl.daily_market_allocation_contract import AllocationAction
from stom_rl.daily_market_allocation_transition import execute_allocation_transition
from stom_rl.daily_market_transition_contract import (
    DailyMarketCandidate,
    build_market_state,
)


def _candidates() -> tuple[DailyMarketCandidate, ...]:
    return tuple(
        DailyMarketCandidate(
            decision_date=date(2026, 1, 2),
            entry_date=date(2026, 1, 5),
            exit_date=date(2026, 1, 6),
            code=f"{index:06d}",
            score=float(11 - index),
            entry_open_krw=Decimal("100000"),
            exit_open_krw=Decimal("101000"),
            split="TRAIN",
        )
        for index in range(1, 11)
    )


@pytest.mark.parametrize(
    ("action", "name", "slots", "exposure_cap"),
    (
        (AllocationAction.CASH, "CASH", 0, Decimal("0")),
        (
            AllocationAction.INVEST_TOP3_EQUAL_SLOT,
            "INVEST_TOP3_EQUAL_SLOT",
            3,
            Decimal("15000000"),
        ),
        (
            AllocationAction.INVEST_TOP5_EQUAL_SLOT,
            "INVEST_TOP5_EQUAL_SLOT",
            5,
            Decimal("25000000"),
        ),
        (
            AllocationAction.INVEST_TOP10_EQUAL_SLOT,
            "INVEST_TOP10_EQUAL_SLOT",
            10,
            Decimal("50000000"),
        ),
    ),
)
def test_allocation_actions_execute_fixed_five_million_slots(
    action: AllocationAction,
    name: str,
    slots: int,
    exposure_cap: Decimal,
) -> None:
    # Given: one full causal top-10 state and 60 million KRW NAV.
    candidates = _candidates()
    state = build_market_state(
        candidates,
        feature_vector=(0.1, -0.2),
        previous_exposure_ratio=Decimal("0"),
        previous_drawdown=Decimal("0"),
    )

    # When: one of the preregistered allocation actions is executed.
    transition = execute_allocation_transition(
        state,
        candidates,
        action,
        previous_nav_krw=Decimal("60000000"),
        previous_peak_nav_krw=Decimal("60000000"),
    )

    # Then: the action name, slot count, exposure cap, and cash floor are explicit.
    assert transition.requested_action == name
    assert transition.executed_action == name
    assert transition.accounting.filled_slots == slots
    assert transition.accounting.deployed_at_entry_krw <= exposure_cap
    assert transition.accounting.cash_after_entry_krw >= Decimal("10000000")
    assert tuple(row.code for row in transition.accounting.ledger) == tuple(
        f"{index:06d}" for index in range(1, slots + 1)
    )


def test_allocation_action_rejects_unregistered_integer() -> None:
    candidates = _candidates()
    state = build_market_state(
        candidates,
        feature_vector=(0.1, -0.2),
        previous_exposure_ratio=Decimal("0"),
        previous_drawdown=Decimal("0"),
    )

    with pytest.raises(ValueError, match="unsupported allocation action"):
        _ = execute_allocation_transition(
            state,
            candidates,
            4,
            previous_nav_krw=Decimal("60000000"),
            previous_peak_nav_krw=Decimal("60000000"),
        )
