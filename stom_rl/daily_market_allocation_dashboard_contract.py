"""Bounded browser summary contracts for daily-market allocation runs."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field


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
    filled_slots: int = Field(ge=0)
    mean_reward: float
    cumulative_reward: float


class AllocationDashboardSummary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos_daily_market_allocation_summary.v1"]
    verdict: Literal[
        "VALIDATION_CANDIDATE",
        "NO_GO_VALIDATION_SCREEN",
        "REPRODUCTION_ONLY_VALIDATION_CONSUMED",
        "REPRODUCTION_MISMATCH_VALIDATION_CONSUMED",
    ]
    status: Literal["COMPLETE_RESEARCH_ONLY"]
    algorithm: Literal["CQL"]
    dataset_id: str
    primary_headline: str
    reasons: tuple[str, ...]
    summary: tuple[AllocationDashboardRow, ...]
    historical_test_read: bool
    promotion_allowed: Literal[False]
    fresh_oos_read: Literal[False]
    evidence_classification: Literal[
        "LEGACY_EXPLORATORY_CANDIDATE",
        "POST_HOC_CUSTODY_REPRODUCTION",
    ] = "LEGACY_EXPLORATORY_CANDIDATE"


__all__ = ["AllocationDashboardRow", "AllocationDashboardSummary"]
