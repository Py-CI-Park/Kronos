"""Validated schemas and typed errors for discovery lifecycle evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import override

from stom_rl.rl_discovery.contract import ArmId
from stom_rl.rl_discovery.gates import ArmOutcome, RunProfile
from stom_rl.rl_discovery.storage import JsonValue


class LifecycleStatus(StrEnum):
    """Persisted execution states; terminal states are immutable once receipted."""

    RUNNING = "RUNNING"
    SMOKE_COMPLETE = "SMOKE_COMPLETE"
    PRIMARY_COMPLETE = "PRIMARY_COMPLETE"


@dataclass(slots=True)  # Exception owns mutable traceback state.
class LifecycleIntegrityError(ValueError):
    """Raised when persisted evidence violates its cross-field contract."""

    field: str
    reason: str

    @override
    def __str__(self) -> str:
        return f"invalid lifecycle {self.field}: {self.reason}"


@dataclass(slots=True)  # Exception owns mutable traceback state.
class ResumeMismatchError(ValueError):
    """Raised when resumption would cross an immutable experiment boundary."""

    field: str

    @override
    def __str__(self) -> str:
        return f"cannot resume: {self.field} does not match the persisted lifecycle"


@dataclass(slots=True)  # Exception owns mutable traceback state.
class TerminalRunError(ValueError):
    """Raised when a terminal receipt makes further mutation forbidden."""

    run_dir: Path

    @override
    def __str__(self) -> str:
        return f"terminal discovery run is immutable: {self.run_dir}"


@dataclass(frozen=True, slots=True)
class RunKey:
    """Parsed arm/seed identity used for safe paths and equality checks."""

    arm: ArmId
    seed: int

    @classmethod
    def parse(cls, value: str) -> RunKey:
        parts = value.split(":")
        if len(parts) != 2 or not parts[1].isdigit():
            raise LifecycleIntegrityError("run_key", value)
        arm = ArmId(parts[0])
        seed = int(parts[1])
        if seed < 0:
            raise LifecycleIntegrityError("run_key", value)
        return cls(arm=arm, seed=seed)

    @property
    def value(self) -> str:
        return f"{self.arm.value}:{self.seed}"


class LifecycleState(BaseModel):
    """Strict boundary persisted before any expensive training starts."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos.rl-discovery.lifecycle.v2"]
    experiment_id: str = Field(min_length=1)
    profile: RunProfile
    prereg_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fixture_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: LifecycleStatus
    expected_runs: tuple[str, ...]
    completed_runs: tuple[str, ...]

    @model_validator(mode="after")
    def validate_cross_fields(self) -> Self:
        expected = tuple(RunKey.parse(value).value for value in self.expected_runs)
        completed = tuple(RunKey.parse(value).value for value in self.completed_runs)
        if len(expected) != len(set(expected)):
            raise LifecycleIntegrityError("expected_runs", "duplicates are forbidden")
        if len(completed) != len(set(completed)):
            raise LifecycleIntegrityError("completed_runs", "duplicates are forbidden")
        if not set(completed).issubset(expected):
            raise LifecycleIntegrityError("completed_runs", "must be a subset of expected_runs")
        if self.status is not LifecycleStatus.RUNNING and completed != expected:
            raise LifecycleIntegrityError("status", "terminal state requires every expected run")
        return self


class OutcomePayload(BaseModel):
    """Typed JSON boundary for one persisted arm/seed result."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    arm: ArmId
    seed: int = Field(ge=0)
    training_timesteps: int = Field(ge=0)
    oracle_reward_ratio: float = Field(allow_inf_nan=False)
    exact_basket_accuracy: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    invalid_action_count: int = Field(ge=0)
    block_count: int = Field(ge=0)
    no_fill_count: int = Field(ge=0)
    dominant_action_rate: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    shuffled_reward: bool
    model: str
    algorithm: ArmId


def outcome_payload(outcome: ArmOutcome) -> dict[str, JsonValue]:
    """Serialize one validated outcome without untyped model dumps."""

    return {
        "arm": outcome.arm,
        "seed": outcome.seed,
        "training_timesteps": outcome.training_timesteps,
        "oracle_reward_ratio": outcome.oracle_reward_ratio,
        "exact_basket_accuracy": outcome.exact_basket_accuracy,
        "invalid_action_count": outcome.invalid_action_count,
        "block_count": outcome.block_count,
        "no_fill_count": outcome.no_fill_count,
        "dominant_action_rate": outcome.dominant_action_rate,
        "shuffled_reward": outcome.shuffled_reward,
        "model": f"{outcome.arm}/seed-{outcome.seed}",
        "algorithm": outcome.arm,
    }
