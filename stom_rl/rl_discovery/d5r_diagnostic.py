"""D5R near-optimal action and regret diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median
from typing import final

from stom_rl.rl_discovery.d3_env import D3Episode


@dataclass(frozen=True, slots=True)
class D5REvent:
    decision_date: str
    action: int
    expected_action: int
    reward: float


@dataclass(frozen=True, slots=True)
class D5RUnitDiagnostic:
    exact_accuracy: float
    near_optimal_5bp: float
    near_optimal_10bp: float
    near_optimal_25bp: float
    mean_regret_bp: float
    median_regret_bp: float


@final
class D5RDiagnosticError(ValueError):
    """A D5R source event cannot be bound to its registered episode."""

    __slots__: tuple[str] = ("reason",)
    reason: str

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def diagnose_d5r_unit(
    episodes: tuple[D3Episode, ...],
    events: tuple[D5REvent, ...],
    *,
    cost_bp: int,
) -> D5RUnitDiagnostic:
    if not episodes or len(episodes) != len(events) or cost_bp < 0:
        raise D5RDiagnosticError("D5R requires aligned episodes, events, and non-negative cost")
    regrets: list[float] = []
    exact = 0
    for episode, event in zip(episodes, events, strict=True):
        rewards = (0.0,) + tuple(
            gross_return - cost_bp / 10_000 for _symbol, _features, gross_return in episode.candidates
        )
        expected = max(range(len(rewards)), key=rewards.__getitem__)
        if episode.decision_date != event.decision_date or event.expected_action != expected:
            raise D5RDiagnosticError("D5R event date or oracle action is mismatched")
        if not 0 <= event.action < len(rewards) or abs(event.reward - rewards[event.action]) > 1e-12:
            raise D5RDiagnosticError("D5R realized action or reward is mismatched")
        regret = max(0.0, rewards[expected] - rewards[event.action])
        regrets.append(regret)
        exact += int(event.action == expected)
    count = len(regrets)
    return D5RUnitDiagnostic(
        exact / count,
        sum(value <= 0.0005 + 1e-12 for value in regrets) / count,
        sum(value <= 0.0010 + 1e-12 for value in regrets) / count,
        sum(value <= 0.0025 + 1e-12 for value in regrets) / count,
        mean(regrets) * 10_000,
        median(regrets) * 10_000,
    )
