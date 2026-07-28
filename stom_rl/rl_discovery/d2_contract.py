"""Validated Type2-D2 historical-scale preregistration boundary."""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError


class D2ArmId(StrEnum):
    """Canonical D2 arms."""

    NATIVE = "A_NATIVE"
    SHUFFLED = "B_SHUFFLED"


class D2RewardKind(StrEnum):
    """Reward binding for one arm."""

    NATIVE = "NATIVE_RETURN"
    SHUFFLED = "SHUFFLED_RETURN"


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")


class D2DatasetContract(_FrozenModel):
    dataset_id: Literal["type1-close-20260803-005"]
    rows_relative_path: str
    rows_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    materializer_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalizer_relative_path: str
    normalizer_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalizer_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    partition: Literal["TRAIN_ONLY"]
    selection: Literal["FIRST_128_CHRONOLOGICAL_ELIGIBLE_TRAIN_SESSIONS"]


class D2ActionContract(_FrozenModel):
    count: Literal[2]
    labels: tuple[Literal["STOP"], Literal["BUY_OBSERVABLE_TOP_RET_1D_PREV"]]
    candidate_rank_feature: Literal["ret_1d_prev"]


class D2ArmContract(_FrozenModel):
    id: D2ArmId
    reward: D2RewardKind


class D2TrainingContract(_FrozenModel):
    smoke_episode_counts: tuple[int, ...]
    smoke_seeds: tuple[int, ...]
    timesteps_by_episode_count: dict[str, int]


class D2CostContract(_FrozenModel):
    training_round_trip_bp: Literal[0]
    diagnostic_round_trip_bp: Literal[23]


class D2GateContract(_FrozenModel):
    minimum_fit_accuracy: float = Field(ge=0, le=1)
    minimum_fit_reward_ratio: float = Field(ge=0, le=1)
    minimum_primary_passing_seed_fraction: float = Field(gt=0, le=1)
    minimum_native_delta_vs_shuffled: float = Field(ge=0, le=1)
    zero_invalid_or_block: Literal[True]


class D2ClaimsBoundary(_FrozenModel):
    research_only: Literal[True]
    profitability_claim_allowed: Literal[False]
    promotion_allowed: Literal[False]
    live_broker_order_allowed: Literal[False]
    fresh_oos: Literal["NOT_RUN_NO_READ"]


class D2Preregistration(_FrozenModel):
    """Executable, fail-closed D2 matrix."""

    schema_version: Literal["kronos.rl-discovery.d2.prereg.v1"]
    status: Literal["APPROVED_EXECUTABLE"]
    experiment_id: Literal["TYPE2-D2-HISTORICAL-SCALE"]
    hypothesis: str = Field(min_length=40)
    dataset: D2DatasetContract
    action: D2ActionContract
    arms: tuple[D2ArmContract, ...]
    episode_counts: tuple[int, ...]
    seeds: tuple[int, ...]
    training: D2TrainingContract
    costs: D2CostContract
    gate: D2GateContract
    claims_boundary: D2ClaimsBoundary

    @model_validator(mode="after")
    def enforce_matrix(self) -> D2Preregistration:
        if self.episode_counts != (1, 8, 32, 128) or self.seeds != (0, 1, 2):
            raise PydanticCustomError("d2_matrix", "D2 scale and seed matrix is frozen")
        if tuple(arm.id for arm in self.arms) != tuple(D2ArmId):
            raise PydanticCustomError("d2_arms", "D2 arm order is frozen")
        if tuple(arm.reward for arm in self.arms) != tuple(D2RewardKind):
            raise PydanticCustomError("d2_rewards", "D2 reward order is frozen")
        if self.training.smoke_episode_counts != (1, 8) or self.training.smoke_seeds != (0,):
            raise PydanticCustomError("d2_smoke", "D2 smoke matrix is frozen")
        expected = {str(count) for count in self.episode_counts}
        if set(self.training.timesteps_by_episode_count) != expected:
            raise PydanticCustomError("d2_budgets", "D2 budgets must cover every scale")
        return self


def load_d2_prereg_bytes(payload: bytes) -> D2Preregistration:
    """Parse exact preregistration bytes at the trust boundary."""

    return D2Preregistration.model_validate_json(payload)
