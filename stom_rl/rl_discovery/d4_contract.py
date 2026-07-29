"""Validated Type2-D4 algorithm/objective preregistration boundary."""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

from stom_rl.rl_discovery.d2_contract import D2DatasetContract


class D4AlgorithmArmId(StrEnum):
    """Frozen diagnostic and reinforcement-learning comparison arms."""

    SUPERVISED_CEILING = "A_SUPERVISED_CEILING"
    PPO_BASELINE = "B_PPO_BASELINE"
    DQN_DISCRETE = "C_DQN_DISCRETE"
    AUXILIARY_PPO = "D_AUXILIARY_PPO"


class D4RewardArmId(StrEnum):
    """Native and shuffled objective identities."""

    NATIVE = "NATIVE"
    SHUFFLED = "SHUFFLED"


class D4AlgorithmFamily(StrEnum):
    """Executable family bound to each D4 arm."""

    SUPERVISED_DIAGNOSTIC = "SUPERVISED_DIAGNOSTIC"
    MASKABLE_PPO = "MASKABLE_PPO"
    DQN = "DQN"
    AUXILIARY_PPO = "AUXILIARY_PPO"


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")


class D4RepresentationContract(_FrozenModel):
    candidate_count: Literal[5]
    market_context: Literal[True]
    source_arm: Literal["D_TOP5_CONTEXT_4X"]


class D4AlgorithmArmContract(_FrozenModel):
    id: D4AlgorithmArmId
    family: D4AlgorithmFamily
    training_steps: Literal[256, 65536]
    pretraining_epochs: Literal[0, 256]
    rl_claim_allowed: bool


class D4SmokeContract(_FrozenModel):
    algorithm_arms: tuple[D4AlgorithmArmId, ...]
    reward_arms: tuple[D4RewardArmId, ...]
    seeds: tuple[int, ...]
    supervised_epochs: Literal[8]
    rl_timesteps: Literal[1024]


class D4CostContract(_FrozenModel):
    training_round_trip_bp: Literal[0]
    diagnostic_round_trip_bp: Literal[23]


class D4GateContract(_FrozenModel):
    minimum_fit_accuracy: float = Field(ge=0, le=1)
    minimum_fit_reward_ratio: float = Field(ge=0, le=1)
    minimum_passing_seed_fraction: float = Field(gt=0, le=1)
    minimum_native_delta_vs_shuffled: float = Field(ge=0, le=1)
    maximum_rl_gap_to_supervised_ceiling: float = Field(ge=0, le=1)
    zero_invalid_actions: Literal[True]


class D4ClaimsBoundary(_FrozenModel):
    research_only: Literal[True]
    supervised_is_not_rl: Literal[True]
    profitability_claim_allowed: Literal[False]
    promotion_allowed: Literal[False]
    live_broker_order_allowed: Literal[False]
    fresh_oos: Literal["NOT_RUN_NO_READ"]


class D4Preregistration(_FrozenModel):
    """Executable immutable 24-unit D4 comparison."""

    schema_version: Literal["kronos.rl-discovery.d4.prereg.v1"]
    status: Literal["APPROVED_EXECUTABLE"]
    experiment_id: Literal["TYPE2-D4-ALGORITHM-OBJECTIVE"]
    parent_release: Literal["fork-v1.13.0-kronos-rl-d3-representation-action"]
    hypothesis: str = Field(min_length=120)
    dataset: D2DatasetContract
    representation: D4RepresentationContract
    algorithm_arms: tuple[D4AlgorithmArmContract, ...]
    reward_arms: tuple[D4RewardArmId, ...]
    episode_count: Literal[128]
    seeds: tuple[int, ...]
    smoke: D4SmokeContract
    costs: D4CostContract
    gate: D4GateContract
    claims_boundary: D4ClaimsBoundary

    @model_validator(mode="after")
    def enforce_matrix(self) -> D4Preregistration:
        expected = (
            (D4AlgorithmArmId.SUPERVISED_CEILING, D4AlgorithmFamily.SUPERVISED_DIAGNOSTIC, 256, 256, False),
            (D4AlgorithmArmId.PPO_BASELINE, D4AlgorithmFamily.MASKABLE_PPO, 65536, 0, True),
            (D4AlgorithmArmId.DQN_DISCRETE, D4AlgorithmFamily.DQN, 65536, 0, True),
            (D4AlgorithmArmId.AUXILIARY_PPO, D4AlgorithmFamily.AUXILIARY_PPO, 65536, 256, True),
        )
        observed = tuple(
            (arm.id, arm.family, arm.training_steps, arm.pretraining_epochs, arm.rl_claim_allowed)
            for arm in self.algorithm_arms
        )
        if observed != expected:
            raise PydanticCustomError("d4_algorithm_arms", "D4 algorithm identities and claim boundaries are frozen")
        if self.reward_arms != tuple(D4RewardArmId) or self.seeds != (0, 1, 2):
            raise PydanticCustomError("d4_primary", "D4 reward and seed matrix is frozen")
        if self.smoke.algorithm_arms != tuple(D4AlgorithmArmId):
            raise PydanticCustomError("d4_smoke_arms", "D4 Smoke must cover every algorithm arm")
        if self.smoke.reward_arms != tuple(D4RewardArmId) or self.smoke.seeds != (0,):
            raise PydanticCustomError("d4_smoke_matrix", "D4 Smoke reward and seed matrix is frozen")
        return self


def load_d4_prereg_bytes(payload: bytes) -> D4Preregistration:
    """Parse exact D4 preregistration bytes at the trust boundary."""

    return D4Preregistration.model_validate_json(payload)
