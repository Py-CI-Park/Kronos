"""Typed preregistration boundary for the D5R study."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore", strict=True)


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


class D5RPreregistration(_FrozenModel):
    schema_version: Literal["kronos.rl-discovery.d5r.prereg.v1"]
    status: Literal["APPROVED_EXECUTABLE"]
    experiment_id: Literal["TYPE2-D5R-CAPACITY-OBJECTIVE"]
    parent_release: Literal["fork-v1.15.0-kronos-rl-d5-full-train-cost"]
    source_run: D5RSourceRun
    d5r_1_diagnostic: D5RDiagnosticContract
    claims_boundary: D5RClaims


def load_d5r_prereg_bytes(payload: bytes) -> D5RPreregistration:
    return D5RPreregistration.model_validate_json(payload)
