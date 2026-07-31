"""Typed preregistration boundary for D6 reused validation."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)


class D6SourceModel(_FrozenModel):
    reward_arm: Literal["NATIVE", "SHUFFLED"]
    seed: Literal[0, 1, 2]
    relative_path: str = Field(pattern=r"^models/(NATIVE|SHUFFLED)/seed-[0-2]/steps-100000/model\.zip$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class D6SourceRun(_FrozenModel):
    run_name: Literal["type2-d5s-primary-20260730-001"]
    artifact_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    summary_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verdict: Literal["D5S_STABILITY_CONFIRMED"]
    selected_steps: Literal[100000]
    reward_arms: tuple[Literal["NATIVE"], Literal["SHUFFLED"]]
    seeds: tuple[Literal[0], Literal[1], Literal[2]]
    model_count: Literal[6]
    models: tuple[D6SourceModel, ...]


class D6Dataset(_FrozenModel):
    dataset_id: Literal["type1-close-20260803-005"]
    rows_relative_path: str = Field(min_length=1)
    rows_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    materializer_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalizer_relative_path: str = Field(min_length=1)
    normalizer_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalizer_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    partition: Literal["REUSED_VALIDATION"]
    selection: Literal["FIRST_128_CHRONOLOGICAL_ELIGIBLE_VALIDATION_SESSIONS"]
    episode_count: Literal[128]
    normalizer_policy: Literal["TRAIN_ONLY_NORMALIZER_NO_REFIT"]


class D6Hypothesis(_FrozenModel):
    primary: str = Field(min_length=1)
    null: str = Field(min_length=1)
    interpretation_boundary: str = Field(min_length=1)


class D6Execution(_FrozenModel):
    method: Literal["LOAD_FROZEN_100K_MODELS_AND_EVALUATE_ON_REUSED_VALIDATION_WITHOUT_TRAINING"]
    representation: Literal["D_TOP5_CONTEXT_4X"]
    candidate_count: Literal[5]
    market_context: Literal[True]
    round_trip_cost_bp: Literal[23]
    diagnostic_zero_cost_bp: Literal[0]
    retraining_allowed: Literal[False]
    model_mutation_allowed: Literal[False]
    per_seed_selection_allowed: Literal[False]
    threshold_amendment_after_read_allowed: Literal[False]
    validation_read_once: Literal[True]


class D6GateContract(_FrozenModel):
    minimum_native_median_accuracy: Annotated[float, Field(ge=0.2, le=0.2)]
    minimum_native_median_reward_ratio: Annotated[float, Field(ge=0.0, le=0.0)]
    minimum_native_median_total_reward: Annotated[float, Field(ge=0.0, le=0.0)]
    minimum_native_reward_delta_vs_shuffled: Annotated[float, Field(ge=0.1, le=0.1)]
    minimum_passing_native_seed_fraction: Annotated[
        float, Field(ge=0.6666666666666666, le=0.6666666666666666)
    ]
    maximum_native_median_reward_drawdown: Annotated[float, Field(ge=0.25, le=0.25)]
    zero_invalid_actions: Literal[True]
    confirmed_verdict: Literal["D6_REUSED_VALIDATION_CONFIRMED"]
    failed_verdict: Literal["D6_REUSED_VALIDATION_NOT_CONFIRMED"]


class D6Controls(_FrozenModel):
    negative_control: Literal["SHUFFLED"]
    no_trade_total_reward: Annotated[float, Field(ge=0.0, le=0.0)]
    random_action_accuracy_reference: Annotated[
        float, Field(ge=0.16666666666666666, le=0.16666666666666666)
    ]
    ts_imb_classification: Literal["RULE_BASELINE_NOT_DIRECTLY_COMPARABLE"]


class D6Claims(_FrozenModel):
    research_only: Literal[True]
    profitability_claim_allowed: Literal[False]
    promotion_allowed: Literal[False]
    live_broker_order_allowed: Literal[False]
    reused_validation: Literal["AUTHORIZED_AFTER_PREREG_COMMIT"]
    fresh_oos: Literal["NOT_RUN_NO_READ"]


class D6Preregistration(_FrozenModel):
    schema_version: Literal["kronos.rl-discovery.d6.prereg.v1"]
    status: Literal["FROZEN_BEFORE_REUSED_VALIDATION_READ"]
    experiment_id: Literal["TYPE2-D6-REUSED-VALIDATION"]
    parent_release: Literal["fork-v1.17.0-kronos-rl-d5s-stability-earlystop"]
    source_run: D6SourceRun
    dataset: D6Dataset
    hypothesis: D6Hypothesis
    execution: D6Execution
    gate: D6GateContract
    controls: D6Controls
    claims_boundary: D6Claims


def load_d6_prereg_bytes(payload: bytes) -> D6Preregistration:
    return D6Preregistration.model_validate_json(payload)
