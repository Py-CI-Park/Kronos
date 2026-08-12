"""Canonical 001-to-002 evidence comparison for custody reproduction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, ValidationError

from .daily_market_allocation_contract import AllocationActionName
from .daily_market_allocation_experiment_contract import (
    AllocationExperimentReceipt,
    AllocationModelReceipt,
)
from .daily_market_allocation_gate import AllocationValidationGate
from .daily_market_allocation_lineage_contract import (
    AllocationReproductionEvidence,
)
from .daily_market_authority_contract import DailyMarketAuthorityError
from .daily_market_authority_file_custody import read_stable_file_bytes
from .daily_market_rl_contract import DailyMarketRlContractError
from .daily_market_transition_contract import SplitName


class AllocationReproductionProjection(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    score_dataset_hash: str
    state_dataset_hash: str
    authority_status: str
    authority_blockers: tuple[str, ...]
    daily_database_sha256: str
    action_space: tuple[AllocationActionName, ...]
    initial_capital_krw: int
    cash_reserve_floor_krw: int
    slot_notional_krw: int
    base_round_trip_cost_percent: float
    stress_round_trip_cost_percent: float
    reward_read_splits: tuple[SplitName, ...]
    available_train_days: int
    available_validation_days: int
    blocked_train_validation_days: int
    non_overlapping_train_days: int
    non_overlapping_validation_days: int
    behavior_transition_count: int
    model_runs: tuple[AllocationModelReceipt, ...]
    validation_gate: AllocationValidationGate


def allocation_reproduction_projection(
    receipt: AllocationExperimentReceipt,
) -> AllocationReproductionProjection:
    return AllocationReproductionProjection(
        score_dataset_hash=receipt.score_dataset_hash,
        state_dataset_hash=receipt.state_dataset_hash,
        authority_status=receipt.authority_status,
        authority_blockers=receipt.authority_blockers,
        daily_database_sha256=receipt.daily_database_sha256,
        action_space=receipt.action_space,
        initial_capital_krw=receipt.initial_capital_krw,
        cash_reserve_floor_krw=receipt.cash_reserve_floor_krw,
        slot_notional_krw=receipt.slot_notional_krw,
        base_round_trip_cost_percent=receipt.base_round_trip_cost_percent,
        stress_round_trip_cost_percent=receipt.stress_round_trip_cost_percent,
        reward_read_splits=receipt.reward_read_splits,
        available_train_days=receipt.available_train_days,
        available_validation_days=receipt.available_validation_days,
        blocked_train_validation_days=receipt.blocked_train_validation_days,
        non_overlapping_train_days=receipt.non_overlapping_train_days,
        non_overlapping_validation_days=receipt.non_overlapping_validation_days,
        behavior_transition_count=receipt.behavior_transition_count,
        model_runs=receipt.model_runs,
        validation_gate=receipt.validation_gate,
    )


def allocation_reproduction_projection_sha256(
    projection: AllocationReproductionProjection,
) -> str:
    payload = json.dumps(
        projection.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def compare_allocation_reproduction(
    reference_receipt: AllocationExperimentReceipt,
    observed: AllocationReproductionProjection,
    *,
    reference_receipt_sha256: str,
) -> AllocationReproductionEvidence:
    if reference_receipt.research_id != (
        "DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_001"
    ):
        raise DailyMarketRlContractError("ALLOCATION_REPRODUCTION_REFERENCE_INVALID")
    reference_sha256 = allocation_reproduction_projection_sha256(
        allocation_reproduction_projection(reference_receipt)
    )
    observed_sha256 = allocation_reproduction_projection_sha256(observed)
    return AllocationReproductionEvidence(
        reference_research_id=reference_receipt.research_id,
        reference_receipt_sha256=reference_receipt_sha256,
        reference_evidence_sha256=reference_sha256,
        observed_evidence_sha256=observed_sha256,
        exact_match=reference_sha256 == observed_sha256,
    )


def load_allocation_reproduction_reference(
    path: Path,
    *,
    expected_sha256: str,
) -> AllocationExperimentReceipt:
    try:
        payload, identity = read_stable_file_bytes(path)
        receipt = AllocationExperimentReceipt.model_validate_json(payload)
    except (OSError, ValidationError, DailyMarketAuthorityError) as exc:
        raise DailyMarketRlContractError(
            "ALLOCATION_REPRODUCTION_REFERENCE_INVALID"
        ) from exc
    if identity.sha256 != expected_sha256 or receipt.research_id != (
        "DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_001"
    ):
        raise DailyMarketRlContractError("ALLOCATION_REPRODUCTION_REFERENCE_INVALID")
    return receipt


__all__ = [
    "AllocationReproductionProjection",
    "allocation_reproduction_projection",
    "allocation_reproduction_projection_sha256",
    "compare_allocation_reproduction",
    "load_allocation_reproduction_reference",
]
