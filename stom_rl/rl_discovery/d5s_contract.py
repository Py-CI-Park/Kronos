"""Typed preregistration boundary for the D5S stability study."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)


class D5SSourceRun(_FrozenModel):
    run_name: Literal["type2-d5r-primary-20260730-001"]
    artifact_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    summary_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    episode_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    episode_count: Literal[573]
    partition: Literal["TRAIN_ONLY"]
    verdict: Literal["D5R_CAPACITY_NOT_CONFIRMED"]
    model_count: Literal[12]
    outcome_count: Literal[12]


class D5SHypothesis(_FrozenModel):
    primary: str = Field(min_length=1)
    null: str = Field(min_length=1)
    interpretation_boundary: str = Field(min_length=1)


class D5SAlgorithm(_FrozenModel):
    id: Literal["D_DQN_STABLE_LR"]
    family: Literal["DQN"]
    net_arch: tuple[Literal[256], Literal[128]]
    gamma: Annotated[float, Field(ge=1.0, le=1.0)]
    learning_rate: Annotated[float, Field(ge=0.0003, le=0.0003)]
    buffer_size: Literal[200000]
    learning_starts: Literal[128]
    batch_size: Literal[64]
    train_freq: Literal[4]
    gradient_steps: Literal[1]
    target_update_interval: Literal[10000]
    exploration_fraction: Annotated[float, Field(ge=0.2, le=0.2)]
    exploration_final_eps: Annotated[float, Field(ge=0.02, le=0.02)]
    device: Literal["cpu"]
    deterministic_algorithms: Literal[True]
    reset_num_timesteps_between_checkpoints: Literal[False]


class D5SExecution(_FrozenModel):
    method: Literal["DETERMINISTIC_REPLAY_FROM_ZERO_WITH_GLOBAL_EARLY_STOP_DIAGNOSTIC"]
    reward_arms: tuple[Literal["NATIVE"], Literal["SHUFFLED"]]
    seeds: tuple[Literal[0], Literal[1], Literal[2]]
    checkpoint_total_steps: tuple[
        Literal[50000],
        Literal[100000],
        Literal[150000],
        Literal[200000],
        Literal[300000],
        Literal[400000],
    ]
    training_steps_per_lineage: Literal[400000]
    lineage_count: Literal[6]
    total_new_rl_steps: Literal[2400000]
    replay_buffer_continuity: Literal["PRESERVED_WITHIN_EACH_0_TO_400K_LINEAGE"]
    algorithm: D5SAlgorithm


class D5SSelection(_FrozenModel):
    scope: Literal["TRAIN_ONLY_DIAGNOSTIC"]
    candidate_checkpoints: tuple[
        Literal[50000],
        Literal[100000],
        Literal[150000],
        Literal[200000],
        Literal[300000],
        Literal[400000],
    ]
    rule: str = Field(min_length=1)
    per_seed_or_per_arm_checkpoint_selection_allowed: Literal[False]
    post_selection_retraining_allowed: Literal[False]


class D5SSmoke(_FrozenModel):
    reward_arms: tuple[Literal["NATIVE"], Literal["SHUFFLED"]]
    seeds: tuple[Literal[0]]
    checkpoint_total_steps: tuple[Literal[4096]]
    approval_requires_hmac: Literal[True]


class D5SCosts(_FrozenModel):
    training_round_trip_bp: Literal[23]
    primary_evaluation_round_trip_bp: Literal[23]
    diagnostic_zero_cost_bp: Literal[0]


class D5SBaselineContract(_FrozenModel):
    native_median_accuracy: Annotated[
        float, Field(ge=0.7120418848167539, le=0.7120418848167539)
    ]
    native_median_reward_ratio: Annotated[
        float, Field(ge=0.8727793884825973, le=0.8727793884825973)
    ]


class D5SGateContract(_FrozenModel):
    minimum_selected_native_median_accuracy: Annotated[
        float, Field(ge=0.7120418848167539, le=0.7120418848167539)
    ]
    minimum_selected_native_median_reward_ratio: Annotated[
        float, Field(ge=0.8727793884825973, le=0.8727793884825973)
    ]
    minimum_selected_native_reward_delta_vs_shuffled: Annotated[
        float, Field(ge=0.2, le=0.2)
    ]
    maximum_400k_accuracy_degradation_from_selected: Annotated[
        float, Field(ge=0.05, le=0.05)
    ]
    maximum_400k_reward_ratio_degradation_from_selected: Annotated[
        float, Field(ge=0.05, le=0.05)
    ]
    minimum_preserved_native_seed_fraction: Annotated[
        float, Field(ge=0.6666666666666666, le=0.6666666666666666)
    ]
    zero_invalid_actions: Literal[True]
    confirmed_verdict: Literal["D5S_STABILITY_CONFIRMED"]
    failed_verdict: Literal["D5S_STABILITY_NOT_CONFIRMED"]


class D5SControls(_FrozenModel):
    negative_control: Literal["SHUFFLED"]
    comparison_runs: tuple[
        Literal["type2-d5-primary-20260729-001"],
        Literal["type2-d5r-primary-20260730-001"],
    ]
    no_trade_reward: Annotated[float, Field(ge=0.0, le=0.0)]
    oracle_reward_ratio: Annotated[float, Field(ge=1.0, le=1.0)]
    ts_imb_classification: Literal["RULE_BASELINE_NOT_DIRECTLY_COMPARABLE"]


class D5SClaims(_FrozenModel):
    research_only: Literal[True]
    profitability_claim_allowed: Literal[False]
    promotion_allowed: Literal[False]
    live_broker_order_allowed: Literal[False]
    reused_validation: Literal["NOT_RUN_NO_READ"]
    fresh_oos: Literal["NOT_RUN_NO_READ"]


class D5SPreregistration(_FrozenModel):
    schema_version: Literal["kronos.rl-discovery.d5s.prereg.v1"]
    status: Literal["FROZEN_BEFORE_D5S_CODE"]
    experiment_id: Literal["TYPE2-D5S-STABILITY-EARLYSTOP"]
    parent_release: Literal["fork-v1.16.0-kronos-rl-d5r-capacity-objective"]
    source_run: D5SSourceRun
    hypothesis: D5SHypothesis
    execution: D5SExecution
    selection: D5SSelection
    smoke: D5SSmoke
    costs: D5SCosts
    d5_200k_baseline: D5SBaselineContract
    gate: D5SGateContract
    controls: D5SControls
    claims_boundary: D5SClaims


def load_d5s_prereg_bytes(payload: bytes) -> D5SPreregistration:
    return D5SPreregistration.model_validate_json(payload)
