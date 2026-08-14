"""Typed no-read contract for the future local-DB holdout."""

from __future__ import annotations

from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .daily_market_allocation_contract import AllocationAction, allocation_action_name
from .daily_market_authority_contract import AuthorityFileIdentity

LOCAL_HOLDOUT_SEEDS = (0, 1, 2, 3, 4)
LOCAL_HOLDOUT_ACTIONS = tuple(
    allocation_action_name(action) for action in AllocationAction
)


class LocalHoldoutPolicy(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["CQL", "NO_TRADE", "RULE", "RANDOM", "SHUFFLE"]
    policy_id: str = Field(pattern=r"^[A-Z0-9_]+$")
    seed: int | None
    implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    checkpoint_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    paired_cql_seed: int | None = None

    @model_validator(mode="after")
    def _kind_contract(self) -> Self:
        if self.kind in {"CQL", "RANDOM", "SHUFFLE"}:
            if self.seed not in LOCAL_HOLDOUT_SEEDS:
                raise ValueError("seeded local holdout policy requires seed 0..4")
        elif self.seed is not None:
            raise ValueError("seedless local holdout control declared a seed")
        if (self.kind == "CQL") != (self.checkpoint_sha256 is not None):
            raise ValueError("only CQL policies bind checkpoints")
        if self.kind == "SHUFFLE":
            if self.paired_cql_seed != self.seed:
                raise ValueError("shuffle control must pair with the same CQL seed")
        elif self.paired_cql_seed is not None:
            raise ValueError("only shuffle controls declare paired CQL seeds")
        return self


class LocalDbHoldoutDescriptor(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos_daily_market_local_db_holdout.v1"]
    research_id: Literal["DAILY_MARKET_LOCAL_DB_HOLDOUT_2026_08_14_001"]
    state: Literal["REGISTERED_SEALED_NO_READ"]
    registered_at_utc: str
    source_git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    custody_receipt: AuthorityFileIdentity
    economic_gate_receipt: AuthorityFileIdentity
    allocation_receipt: AuthorityFileIdentity
    cutoff_date: Literal["20260814"]
    first_session_rule: Literal["FIRST_LOCAL_DB_SESSION_STRICTLY_AFTER_CUTOFF"]
    required_trading_days: Literal[60]
    price_basis: Literal["UNKNOWN_LOCAL_DB_BASIS"]
    universe_basis: Literal["CURRENT_SNAPSHOT_NOT_PIT"]
    actions: tuple[str, ...]
    base_cost_bps: Literal[23]
    stress_cost_bps: Literal[46]
    policies: tuple[LocalHoldoutPolicy, ...]
    historical_test_state: Literal["CONTAMINATED_FORBIDDEN"]
    local_holdout_features_read: Literal[False]
    local_holdout_actions_read: Literal[False]
    local_holdout_rewards_read: Literal[False]
    retuning_allowed: Literal[False]
    retry_allowed: Literal[False]
    independent_oos_claim_allowed: Literal[False]
    promotion_allowed: Literal[False]
    paper_live_allowed: Literal[False]

    @model_validator(mode="after")
    def _matrix_is_exact(self) -> Self:
        if self.actions != LOCAL_HOLDOUT_ACTIONS:
            raise ValueError("local holdout action space drifted")
        by_kind: dict[str, list[LocalHoldoutPolicy]] = {}
        for policy in self.policies:
            by_kind.setdefault(policy.kind, []).append(policy)
        if {key: len(value) for key, value in by_kind.items()} != {
            "CQL": 5,
            "NO_TRADE": 1,
            "RULE": 1,
            "RANDOM": 5,
            "SHUFFLE": 5,
        }:
            raise ValueError("local holdout policy matrix is incomplete")
        for kind in ("CQL", "RANDOM", "SHUFFLE"):
            seeds = tuple(
                sorted(
                    policy.seed for policy in by_kind[kind] if policy.seed is not None
                )
            )
            if seeds != LOCAL_HOLDOUT_SEEDS:
                raise ValueError(f"local holdout {kind} seed matrix drifted")
        return self


class LocalDbHoldoutRegistration(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos_daily_market_local_db_holdout_registration.v1"]
    descriptor_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    descriptor_size_bytes: int = Field(gt=0)
    state: Literal["REGISTERED_SEALED_NO_READ"]
    blockers: tuple[str, ...]
    accumulated_trading_days: Literal[0]
    required_trading_days: Literal[60]
    local_holdout_read: Literal[False]
    one_read_authorized: Literal[False]
    promotion_allowed: Literal[False]
    paper_live_allowed: Literal[False]


__all__ = [
    "LOCAL_HOLDOUT_ACTIONS",
    "LOCAL_HOLDOUT_SEEDS",
    "LocalDbHoldoutDescriptor",
    "LocalDbHoldoutRegistration",
    "LocalHoldoutPolicy",
]
