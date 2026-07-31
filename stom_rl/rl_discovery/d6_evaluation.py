"""Typed reward events and drawdown metrics for D6."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import ClassVar, TypeAlias

from pydantic import BaseModel, ConfigDict

EventValue: TypeAlias = str | int | float | None


class D6RewardEvent(BaseModel):
    """One deterministic validation decision emitted by the shared evaluator."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)

    decision_date: str
    symbol: str | None
    action: int
    gross_return: float
    cost_bp: int
    expected_action: int
    reward: float


def parse_d6_events(events: Sequence[Mapping[str, EventValue]]) -> tuple[D6RewardEvent, ...]:
    return tuple(D6RewardEvent.model_validate(event) for event in events)


def maximum_cumulative_reward_drawdown(rewards: Sequence[float]) -> float:
    """Return the largest peak-to-later-trough loss in cumulative reward units."""

    cumulative = 0.0
    peak = 0.0
    maximum = 0.0
    for reward in rewards:
        cumulative += reward
        peak = max(peak, cumulative)
        maximum = max(maximum, peak - cumulative)
    return maximum
