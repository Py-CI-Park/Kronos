"""Non-overlapping behavior trajectories for actual-market offline RL."""

from __future__ import annotations

import random
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Final

from .daily_close_research.offline_data import OfflineTransition
from .daily_market_rl_contract import DailyMarketRlContractError
from .daily_market_rl_dataset import MarketDay, TrainScoreScale
from .daily_market_state_dataset import STATE_VECTOR_SIZE
from .daily_market_transition import execute_binary_transition
from .daily_market_transition_contract import (
    BinaryAction,
    MarketTransitionConfig,
    SplitName,
    build_market_state,
)

SCORE_COUNT: Final = 10
MODEL_INPUT_SIZE: Final = STATE_VECTOR_SIZE + SCORE_COUNT + 2


def select_non_overlapping_days(
    days: tuple[MarketDay, ...],
    *,
    split: SplitName,
) -> tuple[MarketDay, ...]:
    """Greedily select decisions known after the preceding position exits."""
    selected: list[MarketDay] = []
    previous_exit: date | None = None
    for day in sorted((row for row in days if row.split == split), key=lambda row: row.decision_date):
        if previous_exit is not None and day.decision_date < previous_exit:
            continue
        selected.append(day)
        previous_exit = day.exit_date
    return tuple(selected)


def build_model_observation(
    day: MarketDay,
    scale: TrainScoreScale,
    *,
    previous_exposure_ratio: Decimal,
    previous_drawdown: Decimal,
) -> tuple[float, ...]:
    """Compose 160 causal features, 10 TRAIN-scaled scores, and 2 portfolio values."""
    normalized_scores = tuple(
        (score.score - scale.mean) / scale.scaling_denominator
        for score in day.score_day.scores
    )
    values = (*day.state_day.feature_vector, *normalized_scores, float(previous_exposure_ratio), float(previous_drawdown))
    if len(values) != MODEL_INPUT_SIZE:
        raise DailyMarketRlContractError("MODEL_OBSERVATION_SIZE_MISMATCH", str(len(values)))
    return values


def build_behavior_transitions(
    days: tuple[MarketDay, ...],
    scale: TrainScoreScale,
    *,
    behavior_seeds: tuple[int, ...],
    cost_config: MarketTransitionConfig,
) -> tuple[OfflineTransition, ...]:
    """Generate deterministic 50:50 exploratory TRAIN trajectories through real accounting."""
    selected = select_non_overlapping_days(days, split="TRAIN")
    if not selected or not behavior_seeds:
        raise DailyMarketRlContractError("BEHAVIOR_TRAJECTORY_INPUT_MISSING")
    output: list[OfflineTransition] = []
    sequence = 0
    for seed in behavior_seeds:
        generator = random.Random(seed)
        nav = cost_config.initial_capital_krw
        peak = nav
        exposure = Decimal("0")
        drawdown = Decimal("0")
        for index, day in enumerate(selected):
            state = build_market_state(
                day.score_day.scores,
                feature_vector=day.state_day.feature_vector,
                previous_exposure_ratio=exposure,
                previous_drawdown=drawdown,
            )
            observation = build_model_observation(
                day,
                scale,
                previous_exposure_ratio=exposure,
                previous_drawdown=drawdown,
            )
            action = BinaryAction(generator.choice((0, 1)))
            result = execute_binary_transition(
                state,
                day.candidates,
                action,
                previous_nav_krw=nav,
                previous_peak_nav_krw=peak,
                config=cost_config,
            )
            next_exposure = result.deployed_at_entry_krw / result.previous_nav_krw
            next_drawdown = result.drawdown_fraction
            done = index == len(selected) - 1
            next_state = (
                (0.0,) * MODEL_INPUT_SIZE
                if done
                else build_model_observation(
                    selected[index + 1],
                    scale,
                    previous_exposure_ratio=next_exposure,
                    previous_drawdown=next_drawdown,
                )
            )
            output.append(
                OfflineTransition(
                    sequence,
                    observation,
                    int(action),
                    float(result.reward_log_nav),
                    next_state,
                    done,
                )
            )
            sequence += 1
            nav = result.final_nav_krw
            peak = result.peak_nav_krw
            exposure = next_exposure
            drawdown = next_drawdown
    return tuple(output)


def shuffle_transition_rewards(
    transitions: tuple[OfflineTransition, ...],
    *,
    seed: int,
) -> tuple[OfflineTransition, ...]:
    """Break reward identity while preserving states, actions, and episode boundaries."""
    rewards = [row.reward for row in transitions]
    random.Random(seed).shuffle(rewards)
    return tuple(replace(row, reward=reward) for row, reward in zip(transitions, rewards, strict=True))


def shuffle_transition_actions(
    transitions: tuple[OfflineTransition, ...],
    *,
    seed: int,
) -> tuple[OfflineTransition, ...]:
    """Break action identity while preserving states, rewards, and episode boundaries."""
    actions = [row.action for row in transitions]
    random.Random(seed).shuffle(actions)
    return tuple(replace(row, action=action) for row, action in zip(transitions, actions, strict=True))


__all__ = [
    "MODEL_INPUT_SIZE",
    "build_behavior_transitions",
    "build_model_observation",
    "select_non_overlapping_days",
    "shuffle_transition_actions",
    "shuffle_transition_rewards",
]
