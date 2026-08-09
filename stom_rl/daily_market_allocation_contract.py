"""Typed four-action contract for daily-close portfolio allocation research."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, unique
from typing import Final, Literal

from .daily_market_transition_contract import BinaryMarketTransition

AllocationActionName = Literal[
    "CASH",
    "INVEST_TOP3_EQUAL_SLOT",
    "INVEST_TOP5_EQUAL_SLOT",
    "INVEST_TOP10_EQUAL_SLOT",
]
SLOT_NOTIONAL_KRW: Final = 5_000_000
_ACTION_NAMES: Final[tuple[AllocationActionName, ...]] = (
    "CASH",
    "INVEST_TOP3_EQUAL_SLOT",
    "INVEST_TOP5_EQUAL_SLOT",
    "INVEST_TOP10_EQUAL_SLOT",
)
_ACTION_SLOTS: Final = (0, 3, 5, 10)


@unique
class AllocationAction(IntEnum):
    """Preregistered cash and fixed-slot exposure choices."""

    CASH = 0
    INVEST_TOP3_EQUAL_SLOT = 1
    INVEST_TOP5_EQUAL_SLOT = 2
    INVEST_TOP10_EQUAL_SLOT = 3


def allocation_action_name(action: AllocationAction) -> AllocationActionName:
    return _ACTION_NAMES[int(action)]


def allocation_slot_count(action: AllocationAction) -> int:
    return _ACTION_SLOTS[int(action)]


@dataclass(frozen=True, slots=True)
class AllocationMarketTransition:
    """Allocation identity paired with the reused audited accounting engine."""

    requested_action: AllocationActionName
    executed_action: AllocationActionName
    accounting: BinaryMarketTransition


__all__ = [
    "AllocationAction",
    "AllocationActionName",
    "AllocationMarketTransition",
    "SLOT_NOTIONAL_KRW",
    "allocation_action_name",
    "allocation_slot_count",
]
