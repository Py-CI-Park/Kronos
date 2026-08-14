"""Content-free registration for the sole future Fresh OOS window."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .daily_market_allocation_contract import AllocationAction, allocation_action_name
from .daily_market_authority_contract import MarketAuthorityReceipt
from .daily_market_rl_contract import DailyMarketRlContractError
from .daily_market_path_custody import has_reparse_component

FRESH_OOS_MODEL_SEEDS = (0, 1, 2, 3, 4)
FRESH_OOS_BASE_COST_BPS = 23
FRESH_OOS_STRESS_COST_BPS = 46
FRESH_OOS_ACTIONS = tuple(allocation_action_name(action) for action in AllocationAction)

FreshOosPolicyKind = Literal["CQL", "NO_TRADE", "RULE", "RANDOM", "SHUFFLE"]


class FreshOosPolicyCommitment(BaseModel):
    """One policy/control frozen before any Fresh OOS observation."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    kind: FreshOosPolicyKind
    seed: int | None
    policy_id: str = Field(pattern=r"^[A-Z0-9_]+$")
    implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    checkpoint_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    paired_model_seed: int | None = None

    @model_validator(mode="after")
    def _kind_contract(self) -> Self:
        if self.kind in {"CQL", "RANDOM", "SHUFFLE"}:
            if self.seed not in FRESH_OOS_MODEL_SEEDS:
                raise ValueError("seeded Fresh OOS policy requires seed 0..4")
        elif self.seed is not None:
            raise ValueError("seedless Fresh OOS control cannot declare a seed")
        if (self.kind == "CQL") != (self.checkpoint_sha256 is not None):
            raise ValueError("only CQL policies bind checkpoints")
        if self.kind == "SHUFFLE":
            if self.paired_model_seed != self.seed:
                raise ValueError("shuffle control must pair with the same CQL seed")
        elif self.paired_model_seed is not None:
            raise ValueError("only shuffle controls declare paired model seeds")
        return self


class FreshOosWindowDescriptor(BaseModel):
    """Metadata-only window contract; it cannot contain Fresh payload locators."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", populate_by_name=True
    )

    schema_version: Literal["kronos_daily_market_fresh_oos_registration.v1"] = Field(
        alias="schema"
    )
    research_id: str = Field(pattern=r"^DAILY_MARKET_ALLOCATION_FRESH_OOS_[0-9_]+$")
    state: Literal["REGISTERED_SEALED_NO_READ"]
    registered_at_utc: str = Field(
        pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
    )
    first_eligible_trading_day: str = Field(pattern=r"^[0-9]{8}$")
    required_trading_days: int = Field(ge=20, le=60)
    source_git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    preregistration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluator_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_trust_store_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    custodian_principal: str = Field(pattern=r"^custodian://[A-Za-z0-9._/-]+$")
    actions: tuple[str, ...]
    base_cost_bps: Literal[23]
    stress_cost_bps: Literal[46]
    policies: tuple[FreshOosPolicyCommitment, ...]
    historical_test_state: Literal["CONTAMINATED_FORBIDDEN"]
    fresh_oos_state_features_read: Literal[False]
    fresh_oos_actions_read: Literal[False]
    fresh_oos_rewards_read: Literal[False]
    retuning_after_registration_allowed: Literal[False]
    retry_after_read_allowed: Literal[False]
    promotion_allowed: Literal[False]
    live_ready: Literal[False]

    @model_validator(mode="after")
    def _evaluation_matrix_is_exact(self) -> Self:
        if self.actions != FRESH_OOS_ACTIONS:
            raise ValueError("Fresh OOS action space drifted")
        by_kind: dict[str, list[FreshOosPolicyCommitment]] = {}
        for policy in self.policies:
            by_kind.setdefault(policy.kind, []).append(policy)
        expected_counts = {
            "CQL": 5,
            "NO_TRADE": 1,
            "RULE": 1,
            "RANDOM": 5,
            "SHUFFLE": 5,
        }
        if {kind: len(values) for kind, values in by_kind.items()} != expected_counts:
            raise ValueError("Fresh OOS policy/control matrix is incomplete")
        for kind in ("CQL", "RANDOM", "SHUFFLE"):
            seeds = tuple(
                policy.seed for policy in by_kind[kind] if policy.seed is not None
            )
            if tuple(sorted(seeds)) != FRESH_OOS_MODEL_SEEDS:
                raise ValueError(f"Fresh OOS {kind} seed set drifted")
        if by_kind["NO_TRADE"][0].policy_id != "NO_TRADE_CASH":
            raise ValueError("Fresh OOS no-trade control must remain CASH")
        identities = tuple(policy.policy_id for policy in self.policies)
        if len(set(identities)) != len(identities):
            raise ValueError("Fresh OOS policy IDs must be unique")
        return self


class FreshOosRegistrationReceipt(BaseModel):
    """Immutable proof that metadata was registered without reading Fresh data."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", populate_by_name=True
    )

    schema_version: Literal["kronos_daily_market_fresh_oos_registration_receipt.v1"] = (
        Field(alias="schema")
    )
    descriptor_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    descriptor_size_bytes: int = Field(gt=0)
    state: Literal["REGISTERED_SEALED_NO_READ"]
    blockers: tuple[
        Literal[
            "D0_D1_AUTHORITY_NOT_VERIFIED",
            "SEALED_WINDOW_ATTESTATION_MISSING",
            "HUMAN_ONE_READ_APPROVAL_MISSING",
        ],
        ...,
    ]
    fresh_oos_read: Literal[False]
    one_read_authorized: Literal[False]
    promotion_allowed: Literal[False]
    live_ready: Literal[False]


def canonical_descriptor_bytes(descriptor: FreshOosWindowDescriptor) -> bytes:
    """Return deterministic UTF-8 bytes for descriptor commitment."""
    return json.dumps(
        descriptor.model_dump(mode="json", by_alias=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_authority_receipt_bytes(authority: MarketAuthorityReceipt) -> bytes:
    """Commit the complete typed authority receipt supplied to registration."""
    return json.dumps(
        authority.model_dump(mode="json", by_alias=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def register_fresh_oos_window(
    descriptor: FreshOosWindowDescriptor,
    output_directory: Path,
    authority: MarketAuthorityReceipt,
) -> FreshOosRegistrationReceipt:
    """Register metadata only; never accept or open a Fresh OOS source."""
    if has_reparse_component(output_directory) or output_directory.exists():
        raise DailyMarketRlContractError("FRESH_OOS_REGISTRATION_OUTPUT_UNTRUSTED")
    authority_receipt_sha256 = hashlib.sha256(
        canonical_authority_receipt_bytes(authority)
    ).hexdigest()
    if authority_receipt_sha256 != descriptor.authority_receipt_sha256:
        raise DailyMarketRlContractError(
            "FRESH_OOS_AUTHORITY_RECEIPT_IDENTITY_MISMATCH"
        )
    descriptor_bytes = canonical_descriptor_bytes(descriptor)
    descriptor_sha = hashlib.sha256(descriptor_bytes).hexdigest()
    blockers: tuple[
        Literal[
            "D0_D1_AUTHORITY_NOT_VERIFIED",
            "SEALED_WINDOW_ATTESTATION_MISSING",
            "HUMAN_ONE_READ_APPROVAL_MISSING",
        ],
        ...,
    ] = (
        *(
            ("D0_D1_AUTHORITY_NOT_VERIFIED",)
            if authority.status != "VERIFIED_RESEARCH_DATA_AUTHORITY"
            else ()
        ),
        "SEALED_WINDOW_ATTESTATION_MISSING",
        "HUMAN_ONE_READ_APPROVAL_MISSING",
    )
    receipt = FreshOosRegistrationReceipt(
        schema="kronos_daily_market_fresh_oos_registration_receipt.v1",
        descriptor_sha256=descriptor_sha,
        descriptor_size_bytes=len(descriptor_bytes),
        state="REGISTERED_SEALED_NO_READ",
        blockers=blockers,
        fresh_oos_read=False,
        one_read_authorized=False,
        promotion_allowed=False,
        live_ready=False,
    )
    try:
        output_directory.mkdir(parents=True, exist_ok=False)
        descriptor_path = output_directory / "fresh_oos_descriptor.json"
        receipt_path = output_directory / "fresh_oos_registration_receipt.json"
        with descriptor_path.open("xb") as handle:
            _ = handle.write(descriptor_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        receipt_bytes = json.dumps(
            receipt.model_dump(mode="json", by_alias=True),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        with receipt_path.open("xb") as handle:
            _ = handle.write(receipt_bytes)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        raise
    return receipt


__all__ = [
    "FRESH_OOS_ACTIONS",
    "FRESH_OOS_BASE_COST_BPS",
    "FRESH_OOS_MODEL_SEEDS",
    "FRESH_OOS_STRESS_COST_BPS",
    "FreshOosPolicyCommitment",
    "FreshOosPolicyKind",
    "FreshOosRegistrationReceipt",
    "FreshOosWindowDescriptor",
    "canonical_authority_receipt_bytes",
    "canonical_descriptor_bytes",
    "register_fresh_oos_window",
]
