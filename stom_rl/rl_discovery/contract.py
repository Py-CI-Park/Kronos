"""Type2 discovery preregistration boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import override


class ArmId(StrEnum):
    """Stable identifiers for the four attribution arms."""

    PPO_ONLY = "A_PPO_ONLY"
    BC_THEN_PPO = "B_BC_THEN_PPO"
    BC_ONLY = "C_BC_ONLY"
    SHUFFLED_REWARD_PPO = "D_SHUFFLED_REWARD_PPO"


class RewardKind(StrEnum):
    """Reward source used while training an arm."""

    NATIVE = "NATIVE"
    SHUFFLED = "SHUFFLED"


class PreregStatus(StrEnum):
    """Execution status recorded in the immutable preregistration."""

    APPROVED_EXECUTABLE = "APPROVED_EXECUTABLE"
    DRAFT_NOT_EXECUTABLE = "DRAFT_NOT_EXECUTABLE"


class ClaimsBoundary(BaseModel):
    """Claims that the discovery lane is explicitly forbidden to make."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    research_only: bool
    profitability_claim_allowed: bool
    fresh_oos: str


class ArmContract(BaseModel):
    """One attribution arm declared before execution."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    id: ArmId
    oracle_bc_before_ppo: bool
    ppo: bool
    reward: RewardKind


class TrainingContract(BaseModel):
    """Permitted smoke and primary budgets."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    smoke_timesteps: int = Field(gt=0)
    primary_timesteps: int = Field(gt=0)
    smoke_seeds: tuple[int, ...]


class DiscoveryPreregistration(BaseModel):
    """Validated executable boundary for Type2-D0."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    status: PreregStatus
    experiment_id: str = Field(min_length=1)
    claims_boundary: ClaimsBoundary
    arms: tuple[ArmContract, ...]
    seeds: tuple[int, ...]
    training: TrainingContract

    @model_validator(mode="after")
    def enforce_discovery_boundary(self) -> DiscoveryPreregistration:
        expected_arms = tuple(ArmId)
        if tuple(arm.id for arm in self.arms) != expected_arms:
            raise ValueError("the four Type2-D0 arms must be declared in canonical order")
        if self.schema_version != "kronos.rl-discovery.prereg.v1":
            raise ValueError("unsupported discovery preregistration schema")
        if not self.claims_boundary.research_only:
            raise ValueError("discovery runs must remain research-only")
        if self.claims_boundary.profitability_claim_allowed:
            raise ValueError("profitability claims are forbidden")
        if self.claims_boundary.fresh_oos != "NOT_RUN_NO_READ":
            raise ValueError("Fresh OOS must remain sealed")
        if self.seeds != (0, 1, 2):
            raise ValueError("primary attribution seeds must be exactly 0, 1, 2")
        if any(seed not in self.seeds for seed in self.training.smoke_seeds):
            raise ValueError("smoke seeds must be a subset of primary seeds")
        return self


@dataclass(frozen=True, slots=True)
class DraftPreregistrationError(ValueError):
    """Raised when a draft preregistration is passed to an executor."""

    path: Path

    @override
    def __str__(self) -> str:
        return f"preregistration is not executable: {self.path}"


def load_prereg(path: Path) -> DiscoveryPreregistration:
    """Load and validate an executable Type2-D0 preregistration."""

    return load_prereg_bytes(path.read_bytes(), source=path)


def load_prereg_bytes(payload: bytes, *, source: Path) -> DiscoveryPreregistration:
    """Validate the exact preregistration bytes used for hashing."""

    prereg = DiscoveryPreregistration.model_validate_json(payload)
    if prereg.status is not PreregStatus.APPROVED_EXECUTABLE:
        raise DraftPreregistrationError(source)
    return prereg
