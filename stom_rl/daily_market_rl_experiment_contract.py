"""Evidence contracts for the registered actual-market RL experiment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from .daily_market_rl_contract import MarketAlgorithm
from .daily_market_rl_evaluation import MarketPolicyMetrics, MarketPolicyTrajectory
from .daily_market_rl_gate import EconomicGateResult


class ModelArmReceipt(BaseModel):
    """One trained seed with validation and historical TEST metrics."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    algorithm: MarketAlgorithm
    seed: int = Field(ge=0)
    shuffle_seed: int = Field(ge=0)
    loss_first: float
    loss_last: float
    checkpoint_path: str
    checkpoint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_base: MarketPolicyMetrics
    validation_stress: MarketPolicyMetrics
    historical_test_base: MarketPolicyMetrics
    historical_test_stress: MarketPolicyMetrics


class MarketExperimentReceipt(BaseModel):
    """Direct summary authority for one immutable actual-market run."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    schema_version: Literal["kronos_daily_market_offline_rl_experiment.v1"]
    research_id: Literal["DAILY_MARKET_CQL_2026_08_09_001"]
    verdict: Literal[
        "PASS_HISTORICAL_RESEARCH_ONLY",
        "NO_GO_HISTORICAL_ECONOMIC_GATE",
    ]
    status: Literal["COMPLETE_RESEARCH_ONLY"]
    algorithm: Literal["CQL"]
    dataset_id: str
    primary_headline: str
    reasons: tuple[str, ...]
    score_dataset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    state_dataset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    training_reward_read_splits: tuple[Literal["TRAIN", "VALIDATION"], ...]
    final_reward_read_splits: tuple[Literal["TEST"], ...]
    available_train_validation_days: int = Field(gt=0)
    blocked_train_validation_days: int = Field(ge=0)
    available_test_days: int = Field(gt=0)
    blocked_test_days: int = Field(ge=0)
    non_overlapping_train_days: int = Field(gt=0)
    non_overlapping_validation_days: int = Field(gt=0)
    non_overlapping_test_days: int = Field(gt=0)
    behavior_transition_count: int = Field(gt=0)
    controls_validation_base: tuple[MarketPolicyMetrics, ...]
    controls_validation_stress: tuple[MarketPolicyMetrics, ...]
    controls_historical_test_base: tuple[MarketPolicyMetrics, ...]
    controls_historical_test_stress: tuple[MarketPolicyMetrics, ...]
    model_runs: tuple[ModelArmReceipt, ...]
    economic_gate: EconomicGateResult
    fresh_oos_state: Literal["NOT_RUN_NO_READ"]
    promotion_allowed: Literal[False]
    live_ready: Literal[False]


class LabeledTrajectory(BaseModel):
    """One policy trajectory labeled for a separate action ledger."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    algorithm: str
    seed: int | None = Field(default=None, ge=0)
    scenario: Literal["BASE_0_230_PERCENT", "STRESS_0_460_PERCENT"]
    trajectory: MarketPolicyTrajectory


@dataclass(frozen=True, slots=True)
class MarketExperimentExecution:
    """Receipt plus generated trajectories that stay outside the summary."""

    receipt: MarketExperimentReceipt
    trajectories: tuple[LabeledTrajectory, ...]


class DashboardSummaryRow(BaseModel):
    """Bounded numeric row consumed by the V6 outcome viewer."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    policy: str
    date_count: int
    total_net_pnl_krw: float
    total_cost_krw: float
    mean_reward: float
    cumulative_reward: float


class DashboardExperimentSummary(BaseModel):
    """Small direct summary discoverable by the existing research catalog."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos_daily_market_dashboard_summary.v1"]
    verdict: str
    status: Literal["COMPLETE_RESEARCH_ONLY"]
    algorithm: Literal["CQL"]
    dataset_id: str
    primary_headline: str
    reasons: tuple[str, ...]
    summary: tuple[DashboardSummaryRow, ...]
    promotion_allowed: Literal[False]
    fresh_oos_read: Literal[False]


__all__ = [
    "DashboardExperimentSummary",
    "DashboardSummaryRow",
    "LabeledTrajectory",
    "MarketExperimentExecution",
    "MarketExperimentReceipt",
    "ModelArmReceipt",
]
