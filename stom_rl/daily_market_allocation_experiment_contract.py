"""Evidence contracts for the validation-only four-action RL screen."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .daily_market_allocation_contract import AllocationActionName
from .daily_market_allocation_dashboard_contract import (
    AllocationDashboardRow as AllocationDashboardRow,
)
from .daily_market_allocation_dashboard_contract import (
    AllocationDashboardSummary as AllocationDashboardSummary,
)
from .daily_market_allocation_evaluation_contract import (
    AllocationPolicyMetrics,
    AllocationPolicyTrajectory,
)
from .daily_market_allocation_gate import (
    AllocationSeedOutcome,
    AllocationValidationGate,
    evaluate_allocation_validation_gate,
)
from .daily_market_allocation_lineage_contract import AllocationLineageEvidence
from .daily_market_allocation_rl_contract import (
    ALLOCATION_MODEL_SEEDS,
    AllocationAlgorithm,
)


class AllocationModelReceipt(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
    )

    algorithm: AllocationAlgorithm
    seed: int = Field(ge=0, le=4)
    loss_first: float
    loss_last: float
    checkpoint_path: str
    checkpoint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_base: AllocationPolicyMetrics
    validation_stress: AllocationPolicyMetrics

    @model_validator(mode="after")
    def _model_evidence_is_canonical(self) -> Self:
        expected_path = f"models/{self.algorithm.value}/seed-{self.seed}.kq"
        if self.checkpoint_path != expected_path:
            raise ValueError("allocation checkpoint path is not canonical")
        if (
            self.validation_base.split != "VALIDATION"
            or self.validation_stress.split != "VALIDATION"
            or self.validation_base.round_trip_cost_percent != 0.23
            or self.validation_stress.round_trip_cost_percent != 0.46
        ):
            raise ValueError("allocation validation split or cost is invalid")
        return self


class AllocationExperimentReceipt(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
    )

    schema_version: Literal["kronos_daily_market_allocation_screen.v1"]
    research_id: Literal[
        "DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_001",
        "DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_002",
    ]
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
    historical_test_state: Literal[
        "NOT_RUN_NO_READ",
        "FEATURES_PARSED_REWARDS_NOT_READ_CONTAMINATED",
    ]
    fresh_oos_state: Literal["NOT_RUN_NO_READ"]
    promotion_allowed: Literal[False]
    live_ready: Literal[False]
    lineage: AllocationLineageEvidence | None = None

    @model_validator(mode="after")
    def _experiment_evidence_is_canonical(self) -> Self:
        if self.research_id.endswith("_002") and (
            self.lineage is None or self.lineage.reproduction is None
        ):
            raise ValueError(
                "allocation 002 requires committed lineage and reference comparison"
            )
        if self.research_id.endswith(
            "_002"
        ) and not self.authority_research_id.endswith("_002"):
            raise ValueError("allocation 002 requires authority receipt 002")
        if self.research_id.endswith("_001") and self.lineage is not None:
            raise ValueError("legacy allocation 001 cannot claim 002 preregistration")
        expected_actions = (
            "CASH",
            "INVEST_TOP3_EQUAL_SLOT",
            "INVEST_TOP5_EQUAL_SLOT",
            "INVEST_TOP10_EQUAL_SLOT",
        )
        if self.action_space != expected_actions:
            raise ValueError("allocation action space is not canonical")
        if (
            self.base_round_trip_cost_percent != 0.23
            or self.stress_round_trip_cost_percent != 0.46
            or self.reward_read_splits != ("TRAIN", "VALIDATION")
        ):
            raise ValueError("allocation cost or reward-read contract is invalid")
        expected_keys = tuple(
            (algorithm, seed)
            for algorithm in AllocationAlgorithm
            for seed in ALLOCATION_MODEL_SEEDS
        )
        observed_keys = tuple((row.algorithm, row.seed) for row in self.model_runs)
        if observed_keys != expected_keys:
            raise ValueError("allocation receipt requires DQN/CQL seeds 0 through 4")
        dqn = tuple(
            AllocationSeedOutcome(
                algorithm=row.algorithm,
                seed=row.seed,
                validation_base=row.validation_base,
                validation_stress=row.validation_stress,
            )
            for row in self.model_runs
            if row.algorithm is AllocationAlgorithm.DQN
        )
        cql = tuple(
            AllocationSeedOutcome(
                algorithm=row.algorithm,
                seed=row.seed,
                validation_base=row.validation_base,
                validation_stress=row.validation_stress,
            )
            for row in self.model_runs
            if row.algorithm is AllocationAlgorithm.CQL
        )
        expected_gate = evaluate_allocation_validation_gate(dqn, cql)
        if self.validation_gate != expected_gate:
            raise ValueError("allocation validation gate does not match model evidence")
        is_reproduction = self.research_id.endswith("_002")
        expected_historical_state = (
            "FEATURES_PARSED_REWARDS_NOT_READ_CONTAMINATED"
            if is_reproduction
            else "NOT_RUN_NO_READ"
        )
        if self.historical_test_state != expected_historical_state:
            raise ValueError("allocation historical TEST disclosure is invalid")
        expected_verdict = (
            (
                "REPRODUCTION_ONLY_VALIDATION_CONSUMED"
                if self.lineage is not None
                and self.lineage.reproduction is not None
                and self.lineage.reproduction.exact_match
                else "REPRODUCTION_MISMATCH_VALIDATION_CONSUMED"
            )
            if is_reproduction
            else expected_gate.verdict
        )
        if self.verdict != expected_verdict:
            raise ValueError(
                "allocation verdict does not match evidence classification"
            )
        reproduction_reason = (
            (
                "VALIDATION_REPRODUCTION_MATCHED_001"
                if self.lineage is not None
                and self.lineage.reproduction is not None
                and self.lineage.reproduction.exact_match
                else "VALIDATION_REPRODUCTION_MISMATCHED_001"
            )
            if is_reproduction
            else None
        )
        expected_reasons = (
            *expected_gate.failed_checks,
            *((reproduction_reason,) if reproduction_reason is not None else ()),
            *(("VALIDATION_ALREADY_CONSUMED_BY_001",) if is_reproduction else ()),
            *self.authority_blockers,
            (
                "HISTORICAL_TEST_FEATURES_ALREADY_CONSUMED_REWARDS_NOT_READ"
                if is_reproduction
                else "HISTORICAL_TEST_NOT_RUN_NO_READ"
            ),
            "FRESH_OOS_NOT_RUN_NO_READ",
        )
        if self.reasons != expected_reasons:
            raise ValueError("allocation reasons do not match gate and authority")
        if self.dataset_id != (
            f"{self.score_dataset_hash[:16]}-{self.state_dataset_hash[:16]}"
        ):
            raise ValueError("allocation dataset id is not content-bound")
        authority_verified = self.authority_status == "VERIFIED_RESEARCH_DATA_AUTHORITY"
        if authority_verified == bool(self.authority_blockers):
            raise ValueError("allocation authority status and blockers disagree")
        return self


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


__all__ = [
    "AllocationDashboardRow",
    "AllocationDashboardSummary",
    "AllocationExperimentExecution",
    "AllocationExperimentReceipt",
    "AllocationModelReceipt",
    "LabeledAllocationTrajectory",
]
