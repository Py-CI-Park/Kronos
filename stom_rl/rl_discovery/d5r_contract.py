"""Typed preregistration boundary for the D5R study."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore", strict=True)


class _StrictFrozenModel(_FrozenModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)


class D5RSourceRun(_FrozenModel):
    run_name: Literal["type2-d5-primary-20260729-001"]
    artifact_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    summary_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    episode_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    episode_count: Literal[573]
    partition: Literal["TRAIN_ONLY"]


class D5RCapacityRule(_FrozenModel):
    median_native_near_optimal_25bp_below: float = Field(gt=0, lt=1)
    or_median_native_regret_bp_above: float = Field(gt=0)


class D5RDiagnosticContract(_FrozenModel):
    source_arms: tuple[Literal["NATIVE", "SHUFFLED"], Literal["NATIVE", "SHUFFLED"]]
    seeds: tuple[Literal[0], Literal[1], Literal[2], Literal[3], Literal[4]]
    cost_bp: Literal[23]
    near_optimal_tolerance_bp: tuple[Literal[5], Literal[10], Literal[25]]
    regret_definition: str
    capacity_required_when: D5RCapacityRule


class D5RClaims(_FrozenModel):
    research_only: Literal[True]
    profitability_claim_allowed: Literal[False]
    promotion_allowed: Literal[False]
    live_broker_order_allowed: Literal[False]
    reused_validation: Literal["NOT_RUN_NO_READ"]
    fresh_oos: Literal["NOT_RUN_NO_READ"]


class D5RAlgorithm(_StrictFrozenModel):
    id: Literal["C_DQN_DISCRETE"]
    family: Literal["DQN"]
    net_arch: tuple[Literal[256], Literal[128]]
    gamma: Annotated[float, Field(ge=1.0, le=1.0)]
    learning_rate: Annotated[float, Field(ge=0.001, le=0.001)]
    train_freq: Literal[4]
    gradient_steps: Literal[1]


class D5RGateContract(_StrictFrozenModel):
    minimum_800k_native_median_accuracy_lift_vs_200k: Annotated[
        float, Field(ge=0.03, le=0.03)
    ]
    minimum_800k_native_median_reward_ratio_lift_vs_200k: Annotated[
        float, Field(ge=0.02, le=0.02)
    ]
    minimum_800k_native_reward_delta_vs_shuffled: Annotated[
        float, Field(ge=0.2, le=0.2)
    ]
    minimum_native_improving_seed_fraction: Annotated[
        float, Field(ge=0.6666666666666666, le=0.6666666666666666)
    ]
    zero_invalid_actions: Literal[True]


class D5RCostContract(_StrictFrozenModel):
    training_round_trip_bp: Literal[23]
    primary_evaluation_round_trip_bp: Literal[23]
    diagnostic_zero_cost_bp: Literal[0]


class D5RSmokeContract(_StrictFrozenModel):
    reward_arms: tuple[Literal["NATIVE"], Literal["SHUFFLED"]]
    seeds: tuple[Literal[0]]
    additional_steps: Literal[2048]


class D5RCapacityContract(_StrictFrozenModel):
    reward_arms: tuple[Literal["NATIVE"], Literal["SHUFFLED"]]
    seeds: tuple[Literal[0], Literal[1], Literal[2]]
    continuation_source_steps: Literal[200000]
    checkpoint_total_steps: tuple[Literal[400000], Literal[800000]]
    additional_steps_per_lineage: tuple[Literal[200000], Literal[600000]]
    algorithm: D5RAlgorithm
    costs: D5RCostContract
    smoke: D5RSmokeContract
    execution_condition: Literal["D5R-1 capacity_required_when is true"]
    gate: D5RGateContract


class D5RFixedExecutionParameters(_StrictFrozenModel):
    batch_size: Literal[64]
    buffer_size: Literal[200000]
    learning_starts: Literal[128]
    gamma: Annotated[float, Field(ge=1.0, le=1.0)]
    learning_rate: Annotated[float, Field(ge=0.001, le=0.001)]
    train_freq: Literal[4]
    gradient_steps: Literal[1]
    net_arch: tuple[Literal[256], Literal[128]]
    device: Literal["cpu"]
    deterministic_algorithms: Literal[True]
    reset_num_timesteps_between_checkpoints: Literal[False]


class D5RReplacementExecution(_StrictFrozenModel):
    method: Literal["DETERMINISTIC_REPLAY_FROM_ZERO_WITH_IN_PROCESS_CHECKPOINTS"]
    d5_200k_role: Literal["CUSTODY_BOUND_COMPARISON_BASELINE_ONLY"]
    reward_arms: tuple[Literal["NATIVE"], Literal["SHUFFLED"]]
    seeds: tuple[Literal[0], Literal[1], Literal[2]]
    checkpoint_total_steps: tuple[Literal[400000], Literal[800000]]
    training_steps_per_lineage: Literal[800000]
    lineage_count: Literal[6]
    total_new_rl_steps: Literal[4800000]
    replay_buffer_continuity: Literal["PRESERVED_WITHIN_EACH_0_TO_800K_LINEAGE"]
    fixed_execution_parameters: D5RFixedExecutionParameters


class D5RSupersededExecution(_StrictFrozenModel):
    continuation_source_steps: Literal[200000]
    additional_steps_per_lineage: tuple[Literal[200000], Literal[600000]]


class D5RUnchangedBoundary(_StrictFrozenModel):
    gate: Literal["UNCHANGED"]
    training_round_trip_bp: Literal[23]
    primary_evaluation_round_trip_bp: Literal[23]
    diagnostic_zero_cost_bp: Literal[0]
    native_and_shuffled_controls: Literal[True]
    reused_validation: Literal["NOT_RUN_NO_READ"]
    fresh_oos: Literal["NOT_RUN_NO_READ"]
    profitability_claim_allowed: Literal[False]
    promotion_allowed: Literal[False]
    live_broker_order_allowed: Literal[False]


class D5RAmendment(_StrictFrozenModel):
    schema_version: Literal["kronos.rl-discovery.d5r.amendment.v1"]
    status: Literal["APPROVED_BEFORE_D5R2_CODE"]
    experiment_id: Literal["TYPE2-D5R-CAPACITY-OBJECTIVE"]
    parent_prereg_commit: Literal["bb0d97a"]
    reason: str = Field(min_length=1)
    supersedes: D5RSupersededExecution
    replacement_execution: D5RReplacementExecution
    unchanged: D5RUnchangedBoundary


class D5RPreregistration(_FrozenModel):
    schema_version: Literal["kronos.rl-discovery.d5r.prereg.v1"]
    status: Literal["APPROVED_EXECUTABLE"]
    experiment_id: Literal["TYPE2-D5R-CAPACITY-OBJECTIVE"]
    parent_release: Literal["fork-v1.15.0-kronos-rl-d5-full-train-cost"]
    source_run: D5RSourceRun
    d5r_1_diagnostic: D5RDiagnosticContract
    d5r_2_capacity: D5RCapacityContract
    claims_boundary: D5RClaims


def load_d5r_prereg_bytes(payload: bytes) -> D5RPreregistration:
    return D5RPreregistration.model_validate_json(payload)


def load_d5r_amendment_bytes(payload: bytes) -> D5RAmendment:
    return D5RAmendment.model_validate_json(payload)
