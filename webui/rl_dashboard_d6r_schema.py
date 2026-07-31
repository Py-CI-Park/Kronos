"""Strict Pydantic schemas for D6R dashboard evidence."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat


class FrozenEvidence(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)


class D6RMetric(FrozenEvidence):
    accuracy: FiniteFloat
    reward_ratio: FiniteFloat
    total_reward: FiniteFloat
    oracle_reward: FiniteFloat
    trade_rate: FiniteFloat
    dominant_action_rate: FiniteFloat
    invalid_action_count: Literal[0]


class D6REvaluation(FrozenEvidence):
    profile: Literal["COST_ONLY", "TURNOVER_10BP"]
    reward_arm: Literal["NATIVE", "SHUFFLED"]
    seed: int = Field(ge=0, le=2)
    fold_id: int = Field(ge=0, le=4)
    training_steps: Literal[50000]
    training_episode_count: int = Field(ge=323, le=523)
    evaluation_episode_count: Literal[50]
    additional_trade_penalty_bp: Literal[0, 10]
    evaluation_23bp: D6RMetric
    evaluation_0bp: D6RMetric
    maximum_drawdown_23bp: FiniteFloat = Field(ge=0)


class D6RTradeEvent(FrozenEvidence):
    action: int = Field(ge=0, le=5)
    cost_bp: Literal[0, 23]
    decision_date: str = Field(min_length=1)
    expected_action: int = Field(ge=0, le=5)
    gross_return: FiniteFloat
    reward: FiniteFloat
    symbol: str | None


class D6REvents(FrozenEvidence):
    evaluation_23bp: tuple[D6RTradeEvent, ...]
    evaluation_0bp: tuple[D6RTradeEvent, ...]


class D6ROutcome(D6REvaluation):
    events: D6REvents


class D6RGateEvidence(FrozenEvidence):
    verdict: Literal[
        "D6R_TRAIN_FALSIFICATION_CANDIDATE",
        "D6R_TRAIN_FALSIFICATION_NOT_CONFIRMED",
    ]
    native_median_accuracy: FiniteFloat
    native_median_reward_ratio: FiniteFloat
    native_median_total_reward: FiniteFloat
    native_reward_delta_vs_shuffled: FiniteFloat
    positive_fold_fraction: FiniteFloat
    positive_seed_fraction: FiniteFloat
    native_median_trade_rate: FiniteFloat
    trade_rate_reduction_vs_cost_only: FiniteFloat
    native_median_reward_drawdown: FiniteFloat
    invalid_action_count: Literal[0]
    passed_gate_count: int = Field(ge=0, le=10)
    total_gate_count: Literal[10]


class D6RReceipt(FrozenEvidence):
    schema_version: Literal["kronos.rl-discovery.d6r.receipt.v1"]
    profile: Literal["PRIMARY"]
    status: Literal["COMPLETE"]
    verdict: Literal[
        "D6R_TRAIN_FALSIFICATION_CANDIDATE",
        "D6R_TRAIN_FALSIFICATION_NOT_CONFIRMED",
    ]
    artifact_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prereg_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_episode_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    unit_count: Literal[60]
    invalid_action_count: Literal[0]
    approved_smoke: Literal["type2-d6r-smoke-20260731-001"]
    reused_validation: Literal["NO_READ_ALREADY_CONSUMED_DIAGNOSTIC_ONLY"]
    fresh_oos: Literal["NOT_RUN_NO_READ"]
    d7: Literal["LOCKED"]
    live_broker_order_allowed: Literal[False]


class D6RCustody(FrozenEvidence):
    schema_version: Literal["kronos.rl-discovery.d6r.custody.v1"]
    run_name: Literal["type2-d6r-primary-20260731-001"]
    artifact_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    summary_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_episode_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_episode_count: Literal[573]
    unit_count: Literal[60]
    verdict: Literal[
        "D6R_TRAIN_FALSIFICATION_CANDIDATE",
        "D6R_TRAIN_FALSIFICATION_NOT_CONFIRMED",
    ]
    prereg_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    producer_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    producer_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    research_branch: str
    base_release: Literal["fork-v1.18.0-kronos-rl-d6-reused-validation"]
    release_status: Literal["PR_PENDING"]
