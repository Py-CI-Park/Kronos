"""Typed evidence contract for the contaminated existing-DB 60-day simulation."""

from __future__ import annotations

from datetime import date
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .daily_market_authority_contract import AuthorityFileIdentity

SimulationScenario = Literal["BASE_23BP", "STRESS_46BP"]
SimulationPolicyKind = Literal["RL", "CONTROL", "RULE", "RANDOM", "SHUFFLE"]
SimulationArtifactName = Literal[
    "summary.json", "simulation_receipt.json", "action_ledger.jsonl"
]
SimulationAction = Literal[
    "CASH",
    "INVEST_TOP3_EQUAL_SLOT",
    "INVEST_TOP5_EQUAL_SLOT",
    "INVEST_TOP10_EQUAL_SLOT",
]


class ExistingDbSimulationWindow(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    selection_rule: Literal["LAST_60_REGISTERED_SCORE_DAYS"]
    requested_score_days: Literal[60]
    start_decision_date: date
    end_decision_date: date
    validation_score_days: Literal[14]
    test_score_days: Literal[46]
    available_reward_days: int = Field(ge=0, le=60)
    blocked_reward_days: int = Field(ge=0, le=60)
    non_overlapping_decisions: int = Field(gt=0, le=60)

    @model_validator(mode="after")
    def _exact_registered_window(self) -> "ExistingDbSimulationWindow":
        if (
            self.start_decision_date != date(2026, 3, 9)
            or self.end_decision_date != date(2026, 6, 11)
            or self.available_reward_days + self.blocked_reward_days != 60
        ):
            raise ValueError("existing-DB historical simulation window drifted")
        return self


class ExistingDbSimulationStep(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    policy: str
    policy_kind: SimulationPolicyKind
    seed: int | None
    scenario: SimulationScenario
    decision_date: date
    entry_date: date
    exit_date: date
    action: SimulationAction
    final_nav_krw: float = Field(gt=0)
    deployed_at_entry_krw: float = Field(ge=0)
    total_cost_krw: float = Field(ge=0)
    reward_log_nav: float
    drawdown_percent: float = Field(le=0)
    filled_slots: int = Field(ge=0, le=10)


class ExistingDbSimulationMetrics(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    policy: str
    policy_kind: SimulationPolicyKind
    seed: int | None
    scenario: SimulationScenario
    round_trip_cost_bps: Literal[23, 46]
    decision_count: int = Field(gt=0)
    initial_nav_krw: float = Field(gt=0)
    final_nav_krw: float = Field(gt=0)
    net_return_percent: float
    max_drawdown_percent: float = Field(le=0)
    total_cost_krw: float = Field(ge=0)
    turnover: float = Field(ge=0)
    action_counts: tuple[int, int, int, int]
    distinct_action_count: int = Field(ge=1, le=4)
    cumulative_reward: float


class ExistingDbSimulationGateCheck(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    passed: bool
    observed: str


class ExistingDbSimulationGate(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    technical_gate_passed: bool
    checks: tuple[ExistingDbSimulationGateCheck, ...]
    failed_checks: tuple[str, ...]
    cql_base_median_return_percent: float
    cql_stress_median_return_percent: float
    best_base_control_return_percent: float
    paired_shuffle_base_median_return_percent: float


class ExistingDbSimulationSummary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos_existing_db_60_historical_summary.v1"]
    research_id: Literal["DAILY_MARKET_EXISTING_DB_60_SIM_2026_08_14_001"]
    verdict: Literal["HISTORICAL_SIMULATION_ONLY_NO_PROMOTION"]
    status: Literal["COMPLETE_LOCAL_RESEARCH_ONLY"]
    research_scope: Literal["POST_HOC_EXISTING_DB_HISTORICAL_SIMULATION"]
    window_start: Literal["2026-03-09"]
    window_end: Literal["2026-06-11"]
    requested_score_days: Literal[60]
    available_reward_days: int = Field(ge=0, le=60)
    non_overlapping_decisions: int = Field(gt=0, le=60)
    technical_gate_passed: bool
    cql_base_median_return_percent: float
    cql_stress_median_return_percent: float
    best_base_control_return_percent: float
    failed_checks: tuple[str, ...]
    future_data_used: Literal[False]
    independent_oos_claim_allowed: Literal[False]
    promotion_allowed: Literal[False]
    paper_live_allowed: Literal[False]


class ExistingDbSimulationArtifactRecord(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    path: SimulationArtifactName
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExistingDbSimulationBundleManifest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos_existing_db_60_historical_bundle.v1"]
    research_id: Literal["DAILY_MARKET_EXISTING_DB_60_SIM_2026_08_14_001"]
    artifacts: tuple[ExistingDbSimulationArtifactRecord, ...]
    artifact_count: Literal[3]
    ledger_row_count: int = Field(gt=0)
    complete: Literal[True]

    @model_validator(mode="after")
    def _exact_artifact_set(self) -> "ExistingDbSimulationBundleManifest":
        if {artifact.path for artifact in self.artifacts} != {
            "summary.json",
            "simulation_receipt.json",
            "action_ledger.jsonl",
        } or len(self.artifacts) != 3:
            raise ValueError("historical simulation artifact set drifted")
        return self


class ExistingDbSimulationReceipt(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos_existing_db_60_historical_simulation.v1"]
    research_id: Literal["DAILY_MARKET_EXISTING_DB_60_SIM_2026_08_14_001"]
    verdict: Literal["HISTORICAL_SIMULATION_ONLY_NO_PROMOTION"]
    status: Literal["COMPLETE_LOCAL_RESEARCH_ONLY"]
    source_git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    daily_database: AuthorityFileIdentity
    score_dataset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    state_dataset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    allocation_receipt: AuthorityFileIdentity
    checkpoint_identities: tuple[AuthorityFileIdentity, ...]
    window: ExistingDbSimulationWindow
    blocked_days: tuple[str, ...]
    metrics: tuple[ExistingDbSimulationMetrics, ...]
    gate: ExistingDbSimulationGate
    historical_state: Literal["VALIDATION_AND_TEST_ALREADY_CONSUMED_CONTAMINATED"]
    future_data_used: Literal[False]
    local_db_fresh_holdout_read: Literal[False]
    independent_oos_claim_allowed: Literal[False]
    profitability_claim_allowed: Literal[False]
    promotion_allowed: Literal[False]
    paper_live_allowed: Literal[False]


__all__ = [
    "ExistingDbSimulationArtifactRecord",
    "ExistingDbSimulationBundleManifest",
    "ExistingDbSimulationGate",
    "ExistingDbSimulationGateCheck",
    "ExistingDbSimulationMetrics",
    "ExistingDbSimulationReceipt",
    "ExistingDbSimulationStep",
    "ExistingDbSimulationSummary",
    "ExistingDbSimulationWindow",
    "SimulationAction",
    "SimulationArtifactName",
    "SimulationPolicyKind",
    "SimulationScenario",
]
