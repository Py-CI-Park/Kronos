"""Immutable preregistration, optimizer, and input lineage for allocation 002."""

from __future__ import annotations

from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .daily_market_rl_contract import BEHAVIOR_SEEDS, MODEL_INPUT_DIMENSION

AllocationLineageInputRole = Literal[
    "CANDIDATE_SCORES",
    "SOURCE_MANIFEST",
    "CAUSAL_PANEL",
    "AUTHORITY_RECEIPT",
    "SOURCE_ALLOCATION_RECEIPT_001",
]


class AllocationInputHash(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    role: AllocationLineageInputRole
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AllocationTrainingEvidence(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    model_seeds: tuple[int, ...]
    behavior_seeds: tuple[int, ...]
    behavior_policy: Literal["UNIFORM_RANDOM_FOUR_ACTIONS_TRAIN_ONLY"]
    input_dimension: int
    action_count: int
    hidden_dimensions: tuple[int, int]
    learning_rate: float
    discount: float
    dqn_cql_alpha: float
    cql_cql_alpha: float
    reward_scale: float
    batch_size: int
    gradient_steps: int
    target_update_interval: int

    @model_validator(mode="after")
    def _training_contract_is_registered(self) -> Self:
        expected = {
            "model_seeds": (0, 1, 2, 3, 4),
            "behavior_seeds": BEHAVIOR_SEEDS,
            "input_dimension": MODEL_INPUT_DIMENSION,
            "action_count": 4,
            "hidden_dimensions": (128, 64),
            "learning_rate": 0.0003,
            "discount": 0.95,
            "dqn_cql_alpha": 0.0,
            "cql_cql_alpha": 1.0,
            "reward_scale": 100.0,
            "batch_size": 256,
            "gradient_steps": 600,
            "target_update_interval": 25,
        }
        for field, value in expected.items():
            if getattr(self, field) != value:
                raise ValueError(f"unregistered allocation training field: {field}")
        return self


class AllocationReproductionEvidence(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    reference_research_id: Literal["DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_001"]
    reference_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reference_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_match: bool

    @model_validator(mode="after")
    def _match_flag_agrees_with_hashes(self) -> Self:
        if self.exact_match != (
            self.reference_evidence_sha256 == self.observed_evidence_sha256
        ):
            raise ValueError("allocation reproduction match flag is inconsistent")
        return self


class AllocationLineageEvidence(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    evidence_classification: Literal["POST_HOC_CUSTODY_REPRODUCTION"]
    preregistration_path: Literal[
        "docs/kronos_v1_29_0_market_authority_allocation_prereg_002_2026-08-10.md"
    ]
    preregistration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_hashes: tuple[AllocationInputHash, ...]
    training: AllocationTrainingEvidence
    reproduction: AllocationReproductionEvidence | None = None

    @model_validator(mode="after")
    def _input_set_is_canonical(self) -> Self:
        expected = (
            "CANDIDATE_SCORES",
            "SOURCE_MANIFEST",
            "CAUSAL_PANEL",
            "AUTHORITY_RECEIPT",
            "SOURCE_ALLOCATION_RECEIPT_001",
        )
        if tuple(row.role for row in self.input_hashes) != expected:
            raise ValueError("allocation lineage input set or order is invalid")
        if self.reproduction is not None and (
            self.reproduction.reference_receipt_sha256 != self.input_hashes[-1].sha256
        ):
            raise ValueError("reference receipt hash is not bound to allocation input")
        return self


__all__ = [
    "AllocationInputHash",
    "AllocationLineageInputRole",
    "AllocationLineageEvidence",
    "AllocationReproductionEvidence",
    "AllocationTrainingEvidence",
]
