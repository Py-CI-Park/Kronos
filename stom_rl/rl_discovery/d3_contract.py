"""Validated Type2-D3 representation/action preregistration boundary."""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

from stom_rl.rl_discovery.d2_contract import D2ClaimsBoundary, D2DatasetContract


class D3PolicyArmId(StrEnum):
    """Frozen stepwise representation and budget arms."""

    TOP1_CONTEXT_1X = "A_TOP1_CONTEXT_1X"
    TOP5_PLAIN_1X = "B_TOP5_PLAIN_1X"
    TOP5_CONTEXT_1X = "C_TOP5_CONTEXT_1X"
    TOP5_CONTEXT_4X = "D_TOP5_CONTEXT_4X"


class D3RewardArmId(StrEnum):
    """Native and shuffled train-only controls."""

    NATIVE = "NATIVE"
    SHUFFLED = "SHUFFLED"


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")


class D3PolicyArmContract(_FrozenModel):
    id: D3PolicyArmId
    candidate_count: Literal[1, 5]
    market_context: bool
    timesteps: Literal[16384, 65536]


class D3SmokeContract(_FrozenModel):
    policy_arms: tuple[D3PolicyArmId, ...]
    reward_arms: tuple[D3RewardArmId, ...]
    seeds: tuple[int, ...]
    timesteps: Literal[1024]


class D3CostContract(_FrozenModel):
    training_round_trip_bp: Literal[0]
    diagnostic_round_trip_bp: Literal[23]


class D3GateContract(_FrozenModel):
    minimum_fit_accuracy: float = Field(ge=0, le=1)
    minimum_fit_reward_ratio: float = Field(ge=0, le=1)
    minimum_passing_seed_fraction: float = Field(gt=0, le=1)
    minimum_native_delta_vs_shuffled: float = Field(ge=0, le=1)
    zero_invalid_actions: Literal[True]


class D3Preregistration(_FrozenModel):
    """Executable, immutable 24-model D3 matrix."""

    schema_version: Literal["kronos.rl-discovery.d3.prereg.v1"]
    status: Literal["APPROVED_EXECUTABLE"]
    experiment_id: Literal["TYPE2-D3-REPRESENTATION-ACTION"]
    hypothesis: str = Field(min_length=80)
    dataset: D2DatasetContract
    policy_arms: tuple[D3PolicyArmContract, ...]
    reward_arms: tuple[D3RewardArmId, ...]
    episode_count: Literal[128]
    seeds: tuple[int, ...]
    smoke: D3SmokeContract
    costs: D3CostContract
    gate: D3GateContract
    claims_boundary: D2ClaimsBoundary

    @model_validator(mode="after")
    def enforce_matrix(self) -> D3Preregistration:
        expected = (
            (D3PolicyArmId.TOP1_CONTEXT_1X, 1, True, 16384),
            (D3PolicyArmId.TOP5_PLAIN_1X, 5, False, 16384),
            (D3PolicyArmId.TOP5_CONTEXT_1X, 5, True, 16384),
            (D3PolicyArmId.TOP5_CONTEXT_4X, 5, True, 65536),
        )
        observed = tuple((arm.id, arm.candidate_count, arm.market_context, arm.timesteps) for arm in self.policy_arms)
        if observed != expected:
            raise PydanticCustomError("d3_policy_arms", "D3 policy arms and budgets are frozen")
        if self.reward_arms != tuple(D3RewardArmId) or self.seeds != (0, 1, 2):
            raise PydanticCustomError("d3_primary", "D3 reward and seed matrix is frozen")
        if self.smoke.policy_arms != tuple(D3PolicyArmId)[:2]:
            raise PydanticCustomError("d3_smoke_policy", "D3 smoke policy arms are frozen")
        if self.smoke.reward_arms != tuple(D3RewardArmId) or self.smoke.seeds != (0,):
            raise PydanticCustomError("d3_smoke_matrix", "D3 smoke reward and seed matrix is frozen")
        return self


def load_d3_prereg_bytes(payload: bytes) -> D3Preregistration:
    """Parse exact D3 preregistration bytes once at the trust boundary."""

    return D3Preregistration.model_validate_json(payload)
