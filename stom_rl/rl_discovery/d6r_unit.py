"""One deterministic D6R fold unit from training through replay evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from stom_rl.rl_discovery.d3_env import D3Episode, D3Representation
from stom_rl.rl_discovery.d3_training import (
    D3Metrics,
    evaluate_d3_model,
    shuffled_d3_episodes,
)
from stom_rl.rl_discovery.d4_training import D4PlainPolicy
from stom_rl.rl_discovery.d6_evaluation import (
    D6RewardEvent,
    maximum_cumulative_reward_drawdown,
    parse_d6_events,
)
from stom_rl.rl_discovery.d6r_gate import D6RProfileId, D6RRewardArm
from stom_rl.rl_discovery.d6r_training import (
    D6RTrainable,
    advance_d6r_lineage,
    start_d6r_lineage,
    training_penalty_bp,
)


@dataclass(frozen=True, slots=True)
class D6RUnitRow:
    profile: D6RProfileId
    reward_arm: D6RRewardArm
    seed: int
    fold_id: int
    training_steps: int
    training_episode_count: int
    evaluation_episode_count: int
    additional_trade_penalty_bp: int
    evaluation_23bp: D3Metrics
    evaluation_0bp: D3Metrics
    maximum_drawdown_23bp: float


@dataclass(frozen=True, slots=True)
class D6RUnitExecution:
    row: D6RUnitRow
    model: D6RTrainable
    events_23bp: tuple[D6RewardEvent, ...]
    events_0bp: tuple[D6RewardEvent, ...]


def execute_d6r_unit(
    training_episodes: tuple[D3Episode, ...],
    evaluation_episodes: tuple[D3Episode, ...],
    *,
    profile: D6RProfileId,
    reward_arm: D6RRewardArm,
    seed: int,
    fold_id: int,
    training_steps: int,
    representation: D3Representation,
) -> D6RUnitExecution:
    fit_episodes = (
        training_episodes
        if reward_arm == "NATIVE"
        else shuffled_d3_episodes(training_episodes, seed=seed)
    )
    penalty_bp = training_penalty_bp(profile)
    lineage = start_d6r_lineage(
        fit_episodes,
        representation=representation,
        seed=seed,
        cost_bp=23,
        additional_trade_penalty_bp=penalty_bp,
    )
    lineage = advance_d6r_lineage(lineage, target_steps=training_steps)
    policy = D4PlainPolicy(lineage.model)
    metrics_23bp, raw_23bp = evaluate_d3_model(
        policy,
        evaluation_episodes,
        representation=representation,
        seed=seed,
        cost_bp=23,
    )
    metrics_0bp, raw_0bp = evaluate_d3_model(
        policy,
        evaluation_episodes,
        representation=representation,
        seed=seed,
        cost_bp=0,
    )
    events_23bp = parse_d6_events(raw_23bp)
    events_0bp = parse_d6_events(raw_0bp)
    row = D6RUnitRow(
        profile,
        reward_arm,
        seed,
        fold_id,
        training_steps,
        len(training_episodes),
        len(evaluation_episodes),
        penalty_bp,
        metrics_23bp,
        metrics_0bp,
        maximum_cumulative_reward_drawdown(
            tuple(event.reward for event in events_23bp)
        ),
    )
    return D6RUnitExecution(row, lineage.model, events_23bp, events_0bp)
