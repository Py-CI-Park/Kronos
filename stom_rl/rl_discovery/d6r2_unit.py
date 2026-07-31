"""Shared immutable D6R2 unit evidence row."""

from __future__ import annotations

from dataclasses import dataclass

from stom_rl.rl_discovery.d3_training import D3Metrics
from stom_rl.rl_discovery.d6r2_gate import D6R2Algorithm, D6R2RewardArm


@dataclass(frozen=True, slots=True)
class D6R2UnitRow:
    algorithm: D6R2Algorithm
    classification: str
    reward_arm: D6R2RewardArm
    seed: int
    fold_id: int
    training_steps: int
    training_episode_count: int
    evaluation_episode_count: int
    normalizer_sha256: str
    normalizer_fit_session_count: int
    normalizer_fit_row_count: int
    normalizer_evaluation_row_count: int
    evaluation_23bp: D3Metrics
    evaluation_0bp: D3Metrics
    maximum_drawdown_23bp: float
