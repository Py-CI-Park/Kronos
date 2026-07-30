"""Typed Type2-D5 full-train and cost preregistration boundary."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

from stom_rl.rl_discovery.d4_contract import D4RewardArmId, D4RepresentationContract


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")


class D5DatasetContract(_FrozenModel):
    dataset_id: Literal["type1-close-20260803-005"]
    rows_relative_path: str
    rows_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    materializer_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalizer_relative_path: str
    normalizer_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalizer_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    partition: Literal["TRAIN_ONLY"]
    selection: Literal["ALL_573_CHRONOLOGICAL_ELIGIBLE_TRAIN_SESSIONS"]


class D5AlgorithmContract(_FrozenModel):
    id: Literal["C_DQN_DISCRETE"]
    family: Literal["DQN"]
    training_steps: Literal[200000]
    net_arch: tuple[Literal[256], Literal[128]]
    gamma: float
    learning_rate: float
    train_freq: Literal[4]
    gradient_steps: Literal[1]


class D5SmokeContract(_FrozenModel):
    reward_arms: tuple[D4RewardArmId, ...]
    seeds: tuple[Literal[0], ...]
    rl_timesteps: Literal[2048]


class D5CostContract(_FrozenModel):
    training_round_trip_bp: Literal[23]
    primary_evaluation_round_trip_bp: Literal[23]
    diagnostic_zero_cost_bp: Literal[0]


class D5GateContract(_FrozenModel):
    minimum_fit_accuracy: float = Field(ge=0, le=1)
    minimum_fit_reward_ratio: float = Field(ge=0, le=1)
    minimum_passing_seed_fraction: float = Field(gt=0, le=1)
    minimum_native_delta_vs_shuffled: float = Field(ge=0, le=1)
    zero_invalid_actions: Literal[True]


class D5ClaimsBoundary(_FrozenModel):
    research_only: Literal[True]
    train_only_confirmation: Literal[True]
    profitability_claim_allowed: Literal[False]
    promotion_allowed: Literal[False]
    live_broker_order_allowed: Literal[False]
    reused_validation: Literal["NOT_RUN_NO_READ"]
    fresh_oos: Literal["NOT_RUN_NO_READ"]


class D5Preregistration(_FrozenModel):
    """Immutable ten-model D5 research contract."""

    schema_version: Literal["kronos.rl-discovery.d5.prereg.v1"]
    status: Literal["APPROVED_EXECUTABLE"]
    experiment_id: Literal["TYPE2-D5-FULL-TRAIN-COST"]
    parent_release: Literal["fork-v1.14.0-kronos-rl-d4-algorithm-objective"]
    hypothesis: str = Field(min_length=160)
    dataset: D5DatasetContract
    representation: D4RepresentationContract
    algorithm: D5AlgorithmContract
    reward_arms: tuple[D4RewardArmId, ...]
    episode_count: Literal[573]
    seeds: tuple[int, ...]
    smoke: D5SmokeContract
    costs: D5CostContract
    gate: D5GateContract
    claims_boundary: D5ClaimsBoundary

    @model_validator(mode="after")
    def enforce_matrix(self) -> D5Preregistration:
        if self.reward_arms != tuple(D4RewardArmId) or self.seeds != (0, 1, 2, 3, 4):
            raise PydanticCustomError("d5_matrix", "D5 requires native/shuffled and seeds zero through four")
        if self.smoke.reward_arms != tuple(D4RewardArmId) or self.smoke.seeds != (0,):
            raise PydanticCustomError("d5_smoke", "D5 Smoke requires both rewards and seed zero")
        if self.algorithm.gamma != 1.0 or self.algorithm.learning_rate != 0.001:
            raise PydanticCustomError("d5_algorithm", "D5 gamma and learning rate are frozen")
        return self


def load_d5_prereg_bytes(payload: bytes) -> D5Preregistration:
    """Parse D5 preregistration bytes at the trust boundary."""

    return D5Preregistration.model_validate_json(payload)
