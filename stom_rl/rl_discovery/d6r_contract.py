"""Typed preregistration boundary for D6R."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)


class D6RSource(_FrozenModel):
    episode_source_run: Literal["type2-d5r-primary-20260730-001"]
    episode_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    episode_count: Literal[573]
    partition: Literal["TRAIN_ONLY"]
    d5s_run: Literal["type2-d5s-primary-20260730-001"]
    d5s_artifact_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    d5s_summary_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    d5s_terminal_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    d5s_prereg_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class D6RPriorD6(_FrozenModel):
    run_name: Literal["type2-d6-primary-20260731-002"]
    verdict: Literal["D6_REUSED_VALIDATION_NOT_CONFIRMED"]
    artifact_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    summary_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_episode_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    custody_document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    use_in_d6r_training_or_selection: Literal[False]
    interpretation: str = Field(min_length=1)


class D6RHypothesis(_FrozenModel):
    primary: str = Field(min_length=1)
    null: str = Field(min_length=1)
    interpretation_boundary: str = Field(min_length=1)


class D6RRepresentation(_FrozenModel):
    id: Literal["D_TOP5_CONTEXT_4X"]
    candidate_count: Literal[5]
    action_count: Literal[6]
    hold_action: Literal[0]
    market_context: Literal[True]
    normalizer: Literal["EXISTING_FULL_TRAIN_ONLY_NORMALIZER_NO_REFIT"]
    normalizer_temporal_limitation: str = Field(min_length=1)


class D6RFoldContract(_FrozenModel):
    fold_id: Annotated[int, Field(ge=0, le=4)]
    train_start: Literal[0]
    train_end_exclusive: Annotated[int, Field(ge=323, le=523)]
    evaluation_start: Annotated[int, Field(ge=323, le=523)]
    evaluation_end_exclusive: Annotated[int, Field(ge=373, le=573)]


class D6RRewardProfileContract(_FrozenModel):
    id: Literal["COST_ONLY", "TURNOVER_10BP"]
    training_round_trip_cost_bp: Literal[23]
    additional_trade_penalty_bp: Literal[0, 10]


class D6RExecution(_FrozenModel):
    algorithm: Literal["SB3_DQN"]
    learning_rate: Annotated[float, Field(ge=0.0003, le=0.0003)]
    gamma: Annotated[float, Field(ge=1.0, le=1.0)]
    buffer_size: Literal[200000]
    learning_starts: Literal[128]
    batch_size: Literal[64]
    train_freq: Literal[4]
    gradient_steps: Literal[1]
    target_update_interval: Literal[10000]
    exploration_fraction: Annotated[float, Field(ge=0.2, le=0.2)]
    exploration_final_eps: Annotated[float, Field(ge=0.02, le=0.02)]
    net_arch: tuple[Literal[256], Literal[128]]
    device: Literal["cpu"]
    deterministic_algorithms: Literal[True]
    reward_profiles: tuple[D6RRewardProfileContract, D6RRewardProfileContract]
    primary_profile: Literal["TURNOVER_10BP"]
    reward_arms: tuple[Literal["NATIVE"], Literal["SHUFFLED"]]
    seeds: tuple[Literal[0], Literal[1], Literal[2]]
    training_steps_per_unit: Literal[50000]
    fold_count: Literal[5]
    primary_unit_count: Literal[60]
    total_primary_rl_steps: Literal[3000000]
    evaluation_round_trip_cost_bp: Literal[23]
    diagnostic_zero_cost_bp: Literal[0]
    per_fold_or_seed_model_selection_allowed: Literal[False]
    post_fold_retraining_allowed: Literal[False]
    d6_validation_read_allowed: Literal[False]
    fresh_oos_read_allowed: Literal[False]


class D6RSmoke(_FrozenModel):
    fold_ids: tuple[Literal[0]]
    reward_profiles: tuple[Literal["COST_ONLY"], Literal["TURNOVER_10BP"]]
    reward_arms: tuple[Literal["NATIVE"], Literal["SHUFFLED"]]
    seeds: tuple[Literal[0]]
    training_steps_per_unit: Literal[4096]
    unit_count: Literal[4]
    primary_requires_complete_smoke: Literal[True]


class D6RGate(_FrozenModel):
    primary_profile: Literal["TURNOVER_10BP"]
    minimum_native_median_accuracy: Annotated[float, Field(ge=0.2, le=0.2)]
    minimum_native_median_reward_ratio: Annotated[float, Field(ge=0.0, le=0.0)]
    minimum_native_median_total_reward: Annotated[float, Field(ge=0.0, le=0.0)]
    minimum_native_reward_delta_vs_shuffled: Annotated[float, Field(ge=0.1, le=0.1)]
    minimum_positive_fold_fraction: Annotated[float, Field(ge=0.8, le=0.8)]
    minimum_positive_seed_fraction: Annotated[float, Field(ge=2 / 3, le=2 / 3)]
    maximum_native_median_trade_rate: Annotated[float, Field(ge=0.65, le=0.65)]
    minimum_trade_rate_reduction_vs_cost_only: Annotated[float, Field(ge=0.15, le=0.15)]
    maximum_native_median_reward_drawdown: Annotated[float, Field(ge=0.25, le=0.25)]
    zero_invalid_actions: Literal[True]
    candidate_verdict: Literal["D6R_TRAIN_FALSIFICATION_CANDIDATE"]
    failed_verdict: Literal["D6R_TRAIN_FALSIFICATION_NOT_CONFIRMED"]


class D6RControls(_FrozenModel):
    no_trade_total_reward: Annotated[float, Field(ge=0.0, le=0.0)]
    negative_control: Literal["SHUFFLED"]
    cost_only_profile: Literal["COST_ONLY"]
    random_action_accuracy_reference: Annotated[float, Field(ge=1 / 6, le=1 / 6)]
    ts_imb_classification: Literal["RULE_BASELINE_NOT_DIRECTLY_COMPARABLE"]


class D6RStopRules(_FrozenModel):
    stop_primary_on_incomplete_smoke: Literal[True]
    stop_on_non_finite_metric: Literal[True]
    stop_on_invalid_action: Literal[True]
    stop_on_matrix_identity_mismatch: Literal[True]
    continue_after_research_gate_failure: Literal[False]


class D6RClaims(_FrozenModel):
    research_only: Literal[True]
    candidate_is_not_confirmation: Literal[True]
    profitability_claim_allowed: Literal[False]
    promotion_allowed: Literal[False]
    paper_forward_allowed: Literal[False]
    live_broker_order_allowed: Literal[False]
    reused_validation: Literal["NO_READ_ALREADY_CONSUMED_DIAGNOSTIC_ONLY"]
    fresh_oos: Literal["NOT_RUN_NO_READ"]
    d7: Literal["LOCKED"]


class D6RPreregistration(_FrozenModel):
    schema_version: Literal["kronos.rl-discovery.d6r.prereg.v1"]
    status: Literal["FROZEN_BEFORE_D6R_IMPLEMENTATION_AND_EXECUTION"]
    experiment_id: Literal["TYPE2-D6R-TRAIN-ONLY-FALSIFICATION"]
    parent_release: Literal["fork-v1.18.0-kronos-rl-d6-reused-validation"]
    base_commit: Literal["de2bfff567c63489f21f53c1dfca123b9816c1ee"]
    source: D6RSource
    prior_d6: D6RPriorD6
    hypothesis: D6RHypothesis
    representation: D6RRepresentation
    folds: tuple[D6RFoldContract, ...]
    execution: D6RExecution
    smoke: D6RSmoke
    gate: D6RGate
    controls: D6RControls
    stop_rules: D6RStopRules
    claims_boundary: D6RClaims


def load_d6r_prereg_bytes(payload: bytes) -> D6RPreregistration:
    return D6RPreregistration.model_validate_json(payload)
