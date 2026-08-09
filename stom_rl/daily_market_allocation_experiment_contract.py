"""Evidence contracts for the validation-only four-action RL screen."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from .daily_market_allocation_contract import AllocationActionName
from .daily_market_allocation_evaluation import (
    AllocationPolicyMetrics,
    AllocationPolicyTrajectory,
)
from .daily_market_allocation_gate import AllocationValidationGate
from .daily_market_allocation_rl_contract import AllocationAlgorithm


class AllocationModelReceipt(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
    )

    algorithm: AllocationAlgorithm
    seed: int = Field(ge=0)
    loss_first: float
    loss_last: float
    checkpoint_path: str
    checkpoint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_base: AllocationPolicyMetrics
    validation_stress: AllocationPolicyMetrics


class AllocationExperimentReceipt(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
    )

    schema_version: Literal["kronos_daily_market_allocation_screen.v1"]
    research_id: Literal["DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_001"]
    verdict: Literal["VALIDATION_CANDIDATE", "NO_GO_VALIDATION_SCREEN"]
    status: Literal["COMPLETE_RESEARCH_ONLY"]
    algorithm: Literal["CQL"]
    dataset_id: str
    primary_headline: str
    reasons: tuple[str, ...]
    score_dataset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    state_dataset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_research_id: str
    authority_status: Literal[
        "VERIFIED_RESEARCH_DATA_AUTHORITY",
        "BLOCKED_DATA_AUTHORITY",
    ]
    authority_blockers: tuple[str, ...]
    daily_database_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    action_space: tuple[AllocationActionName, ...]
    initial_capital_krw: Literal[60_000_000]
    cash_reserve_floor_krw: Literal[10_000_000]
    slot_notional_krw: Literal[5_000_000]
    base_round_trip_cost_percent: float = Field(ge=0)
    stress_round_trip_cost_percent: float = Field(ge=0)
    reward_read_splits: tuple[Literal["TRAIN", "VALIDATION"], ...]
    available_train_days: int = Field(gt=0)
    available_validation_days: int = Field(gt=0)
    blocked_train_validation_days: int = Field(ge=0)
    non_overlapping_train_days: int = Field(gt=0)
    non_overlapping_validation_days: int = Field(gt=0)
    behavior_transition_count: int = Field(gt=0)
    model_runs: tuple[AllocationModelReceipt, ...]
    validation_gate: AllocationValidationGate
    historical_test_state: Literal["NOT_RUN_NO_READ"]
    fresh_oos_state: Literal["NOT_RUN_NO_READ"]
    promotion_allowed: Literal[False]
    live_ready: Literal[False]


class LabeledAllocationTrajectory(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    algorithm: AllocationAlgorithm
    seed: int = Field(ge=0)
    scenario: Literal["BASE_0_230_PERCENT", "STRESS_0_460_PERCENT"]
    trajectory: AllocationPolicyTrajectory


@dataclass(frozen=True, slots=True)
class AllocationExperimentExecution:
    receipt: AllocationExperimentReceipt
    trajectories: tuple[LabeledAllocationTrajectory, ...]


class AllocationDashboardRow(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
    )

    policy: str
    seed: int = Field(ge=0)
    date_count: int = Field(gt=0)
    net_return_percent: float
    total_net_pnl_krw: float
    total_cost_krw: float = Field(ge=0)
    max_drawdown_percent: float
    distinct_action_count: int = Field(ge=1, le=4)
    action_cash_count: int = Field(ge=0)
    action_top3_count: int = Field(ge=0)
    action_top5_count: int = Field(ge=0)
    action_top10_count: int = Field(ge=0)
    mean_reward: float
    cumulative_reward: float


class AllocationDashboardSummary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos_daily_market_allocation_summary.v1"]
    verdict: Literal["VALIDATION_CANDIDATE", "NO_GO_VALIDATION_SCREEN"]
    status: Literal["COMPLETE_RESEARCH_ONLY"]
    algorithm: Literal["CQL"]
    dataset_id: str
    primary_headline: str
    reasons: tuple[str, ...]
    summary: tuple[AllocationDashboardRow, ...]
    historical_test_read: Literal[False]
    promotion_allowed: Literal[False]
    fresh_oos_read: Literal[False]


__all__ = [
    "AllocationDashboardRow",
    "AllocationDashboardSummary",
    "AllocationExperimentExecution",
    "AllocationExperimentReceipt",
    "AllocationModelReceipt",
    "LabeledAllocationTrajectory",
]
