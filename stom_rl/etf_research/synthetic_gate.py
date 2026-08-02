"""Deterministic Q2-B learnability checks for the stateful environment."""

from __future__ import annotations

import random
from dataclasses import dataclass

from .environment import MarketBar, PortfolioState, step_target_position


@dataclass(frozen=True, slots=True)
class SyntheticSeedResult:
    seed: int
    known_policy_value: float
    always_long_value: float
    no_trade_value: float
    passed: bool


@dataclass(frozen=True, slots=True)
class SyntheticGateReceipt:
    verdict: str
    passed_seed_count: int
    seed_count: int
    results: tuple[SyntheticSeedResult, ...]


@dataclass(frozen=True, slots=True)
class _SyntheticStep:
    signal: int
    bar: MarketBar


def evaluate_synthetic_environment(seeds: tuple[int, ...]) -> SyntheticGateReceipt:
    """Require a state-aware known policy to beat long and cash controls."""
    results = tuple(_evaluate_seed(seed) for seed in seeds)
    passed_count = sum(result.passed for result in results)
    verdict = "PASS_SYNTHETIC_STATEFUL_MDP" if passed_count == len(results) else "NO_GO_SYNTHETIC_STATEFUL_MDP"
    return SyntheticGateReceipt(verdict, passed_count, len(results), results)


def _evaluate_seed(seed: int) -> SyntheticSeedResult:
    steps = _make_steps(seed)
    known = _run_policy(steps, known=True)
    always_long = _run_policy(steps, known=False)
    no_trade = PortfolioState.initial(1_000_000.0).value
    return SyntheticSeedResult(seed, known, always_long, no_trade, known > always_long and known > no_trade)


def _make_steps(seed: int) -> tuple[_SyntheticStep, ...]:
    generator = random.Random(seed)
    opening = 100.0
    steps: list[_SyntheticStep] = []
    for index in range(24):
        signal = 1 if index % 2 == 0 else -1
        magnitude = generator.uniform(0.018, 0.024) if signal > 0 else generator.uniform(0.028, 0.034)
        close = opening * (1.0 + magnitude * signal)
        steps.append(_SyntheticStep(signal, MarketBar(opening, close)))
        opening = close
    return tuple(steps)


def _run_policy(steps: tuple[_SyntheticStep, ...], *, known: bool) -> float:
    state = PortfolioState.initial(1_000_000.0)
    for step in steps:
        target = 1.0 if (step.signal > 0 or not known) else 0.0
        state = step_target_position(state, target, step.bar, one_way_cost_bps=11.5).state
    if state.units > 0:
        state = step_target_position(
            state,
            0.0,
            MarketBar(state.last_price, state.last_price),
            one_way_cost_bps=11.5,
        ).state
    return state.value

