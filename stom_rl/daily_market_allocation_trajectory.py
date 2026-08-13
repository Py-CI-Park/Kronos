"""Exploratory four-action behavior trajectories for offline RL."""

from __future__ import annotations

import random
from decimal import Decimal

from .daily_close_research.offline_data import OfflineTransition
from .daily_market_allocation_contract import AllocationAction
from .daily_market_allocation_transition import execute_allocation_transition
from .daily_market_rl_contract import DailyMarketRlContractError
from .daily_market_rl_dataset import MarketDay, TrainScoreScale
from .daily_market_rl_trajectory import (
    MODEL_INPUT_SIZE,
    build_model_observation,
    select_non_overlapping_days,
)
from .daily_market_transition_contract import MarketTransitionConfig, build_market_state


def build_allocation_behavior_transitions(
    days: tuple[MarketDay, ...],
    scale: TrainScoreScale,
    *,
    behavior_seeds: tuple[int, ...],
    cost_config: MarketTransitionConfig,
) -> tuple[OfflineTransition, ...]:
    """Generate uniform four-action TRAIN trajectories through actual accounting."""
    selected = select_non_overlapping_days(days, split="TRAIN")
    if not selected or not behavior_seeds:
        raise DailyMarketRlContractError("ALLOCATION_BEHAVIOR_INPUT_MISSING")
    output: list[OfflineTransition] = []
    sequence = 0
    actions = tuple(AllocationAction)
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
            action = generator.choice(actions)
            result = execute_allocation_transition(
                state,
                day.candidates,
                action,
                previous_nav_krw=nav,
                previous_peak_nav_krw=peak,
                config=cost_config,
            )
            accounting = result.accounting
            next_exposure = (
                accounting.deployed_at_entry_krw / accounting.previous_nav_krw
            )
            next_drawdown = accounting.drawdown_fraction
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
                    sequence=sequence,
                    state=observation,
                    action=int(action),
                    reward=float(accounting.reward_log_nav),
                    next_state=next_state,
                    done=done,
                )
            )
            sequence += 1
            nav = accounting.final_nav_krw
            peak = accounting.peak_nav_krw
            exposure = next_exposure
            drawdown = next_drawdown
    return tuple(output)


__all__ = ["build_allocation_behavior_transitions"]
