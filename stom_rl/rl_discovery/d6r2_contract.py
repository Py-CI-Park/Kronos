"""Typed frozen preregistration boundary for D6R2."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore", strict=True)


class D6R2SourceContract(_FrozenModel):
    dataset_id: Literal["type1-close-20260803-005"]
    rows_relative_path: str
    rows_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    materializer_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    partition: Literal["TRAIN_ONLY"]
    episode_identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    episode_count: Literal[573]
    d6r_prereg_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    d6r_result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    d6r_custody_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class D6R2ExecutionContract(_FrozenModel):
    reward_arms: tuple[Literal["NATIVE"], Literal["SHUFFLED"]]
    dqn_seeds: tuple[Literal[0], Literal[1], Literal[2]]
    ridge_seeds: tuple[Literal[0]]
    fold_count: Literal[5]
    primary_unit_count: Literal[70]
    total_primary_rl_steps: Literal[3000000]
    training_round_trip_cost_bp: Literal[23]
    evaluation_round_trip_cost_bp: Literal[23]
    diagnostic_zero_cost_bp: Literal[0]
    fresh_oos_read_allowed: Literal[False]


class D6R2SmokeContract(_FrozenModel):
    fold_ids: tuple[Literal[0]]
    algorithm_ids: tuple[str, ...]
    reward_arms: tuple[Literal["NATIVE"], Literal["SHUFFLED"]]
    seeds: tuple[Literal[0]]
    dqn_training_steps: Literal[4096]
    unit_count: Literal[6]


class D6R2ClaimsContract(_FrozenModel):
    research_only: Literal[True]
    gamma0_is_not_sequential_portfolio_control: Literal[True]
    ridge_is_not_reinforcement_learning: Literal[True]
    profitability_claim_allowed: Literal[False]
    promotion_allowed: Literal[False]
    paper_forward_allowed: Literal[False]
    live_broker_order_allowed: Literal[False]
    fresh_oos: Literal["NOT_RUN_NO_READ"]
    d7: Literal["LOCKED"]


class D6R2Preregistration(_FrozenModel):
    schema_version: Literal["kronos.rl-discovery.d6r2.prereg.v1"]
    status: Literal["FROZEN_BEFORE_D6R2_IMPLEMENTATION_AND_EXECUTION"]
    experiment_id: Literal["TYPE2-D6R2-MDP-MISSPECIFICATION-FALSIFICATION"]
    parent_release: Literal["fork-v1.19.0-kronos-rl-d6r-train-falsification"]
    base_commit: Literal["019a96a5dabc04ce306be2cd48852a9efff8eaed"]
    source: D6R2SourceContract
    execution: D6R2ExecutionContract
    smoke: D6R2SmokeContract
    claims_boundary: D6R2ClaimsContract


def load_d6r2_prereg_bytes(payload: bytes) -> D6R2Preregistration:
    return D6R2Preregistration.model_validate_json(payload)

