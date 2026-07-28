"""Type2-D1 reward/action preregistration boundary."""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError


class D1ArmId(StrEnum):
    """Canonical D1 reward/action arms."""

    BINARY_NATIVE = "A_BINARY_NATIVE"
    BINARY_DIAGNOSTIC = "B_BINARY_DIAGNOSTIC"
    BINARY_SHUFFLED = "C_BINARY_SHUFFLED"


class D1RewardKind(StrEnum):
    """Training reward source for a D1 arm."""

    NATIVE_ECONOMIC = "NATIVE_ECONOMIC"
    FIRST_DECISION_DIAGNOSTIC = "FIRST_DECISION_DIAGNOSTIC"
    SHUFFLED_NATIVE = "SHUFFLED_NATIVE"


class D1ClaimsBoundary(BaseModel):
    """Claims forbidden throughout D1 discovery."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    research_only: Literal[True]
    profitability_claim_allowed: Literal[False]
    fresh_oos: Literal["NOT_RUN_NO_READ"]


class D1ArmContract(BaseModel):
    """One preregistered D1 training arm."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    id: D1ArmId
    reward: D1RewardKind


class D1TrainingContract(BaseModel):
    """Fixed D1 smoke and Primary budgets."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    smoke_timesteps: int = Field(gt=0)
    primary_timesteps: int = Field(gt=0)
    smoke_seeds: tuple[int, ...]


class D1GateThresholds(BaseModel):
    """Frozen D1 confirmation thresholds."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    native_min_reward_ratio: float = Field(ge=0.0, le=1.0)
    native_min_delta_vs_shuffled: float = Field(ge=0.0, le=1.0)
    diagnostic_min_initial_accuracy: float = Field(ge=0.0, le=1.0)
    max_dominant_initial_action_rate: float = Field(ge=0.5, lt=1.0)


class D1Preregistration(BaseModel):
    """Validated executable boundary for Type2-D1."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos.rl-discovery.d1.prereg.v1"]
    status: Literal["APPROVED_EXECUTABLE"]
    experiment_id: Literal["TYPE2-D1-REWARD-ACTION"]
    primary_round_trip_cost_bp: Literal[23]
    hypothesis: str = Field(min_length=20)
    claims_boundary: D1ClaimsBoundary
    arms: tuple[D1ArmContract, ...]
    seeds: tuple[int, ...]
    training: D1TrainingContract
    gate: D1GateThresholds

    @model_validator(mode="after")
    def enforce_canonical_matrix(self) -> D1Preregistration:
        if tuple(arm.id for arm in self.arms) != tuple(D1ArmId):
            raise PydanticCustomError("d1_arm_order", "D1 arms must use canonical order")
        expected_rewards = tuple(D1RewardKind)
        if tuple(arm.reward for arm in self.arms) != expected_rewards:
            raise PydanticCustomError("d1_reward_order", "D1 rewards must match canonical arms")
        if self.seeds != (0, 1, 2):
            raise PydanticCustomError("d1_seeds", "D1 Primary seeds must be 0, 1, 2")
        if self.training.smoke_seeds != (0,):
            raise PydanticCustomError("d1_smoke_seed", "D1 smoke must use seed 0 only")
        if self.training.smoke_timesteps >= self.training.primary_timesteps:
            raise PydanticCustomError("d1_budget", "D1 smoke budget must be below Primary")
        return self


def load_d1_prereg_bytes(payload: bytes) -> D1Preregistration:
    """Parse the exact D1 preregistration bytes."""

    return D1Preregistration.model_validate_json(payload)
