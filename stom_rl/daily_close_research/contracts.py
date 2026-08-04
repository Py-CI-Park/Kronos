"""Fail-closed point-in-time and close-execution contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

_CODE_PATTERN = re.compile(r"^[0-9]{6}$")


class CloseExecutionMode(str, Enum):
    PRE_CLOSE_PROXY = "PRE_CLOSE_PROXY"
    POST_CLOSE_NEXT_OPEN = "POST_CLOSE_NEXT_OPEN"


@dataclass(frozen=True, slots=True)
class FutureDataLeakError(Exception):
    observed_at: datetime
    decision_cutoff: datetime

    def __str__(self) -> str:
        return (
            f"observation {self.observed_at.isoformat()} is after decision cutoff "
            f"{self.decision_cutoff.isoformat()}"
        )


@dataclass(frozen=True, slots=True)
class ExecutionContract:
    mode: CloseExecutionMode
    decision_basis: str
    fill_basis: str
    uses_official_same_day_close: bool


@dataclass(frozen=True, slots=True)
class ExecutionEvidence:
    point_in_time_universe: bool
    available_at_proven: bool
    official_price_identity: bool
    corporate_action_contract: bool
    immutable_source_hash: bool
    fold_local_transform: bool

    @classmethod
    def unverified(cls) -> ExecutionEvidence:
        return cls(False, False, False, False, False, True)

    @classmethod
    def verified_for_tests(cls) -> ExecutionEvidence:
        return cls(True, True, True, True, True, True)


@dataclass(frozen=True, slots=True)
class ExecutionGate:
    name: str
    passed: bool
    evidence: str


@dataclass(frozen=True, slots=True)
class ExecutionAuditReceipt:
    verdict: str
    mode: CloseExecutionMode
    gates: tuple[ExecutionGate, ...]
    blockers: tuple[str, ...]


def registered_execution_contract(mode: CloseExecutionMode) -> ExecutionContract:
    if mode is CloseExecutionMode.PRE_CLOSE_PROXY:
        return ExecutionContract(mode, "FEATURES_AVAILABLE_BY_15_20_KST", "REGISTERED_CLOSE_PROXY", False)
    return ExecutionContract(mode, "OFFICIAL_CLOSE_AFTER_SESSION", "NEXT_SESSION_OPEN", False)


def audit_execution_readiness(
    contract: ExecutionContract,
    evidence: ExecutionEvidence,
) -> ExecutionAuditReceipt:
    gates = (
        ExecutionGate("POINT_IN_TIME_UNIVERSE", evidence.point_in_time_universe, "dated membership snapshot"),
        ExecutionGate("AVAILABLE_AT_PROVEN", evidence.available_at_proven, "source timestamp <= decision cutoff"),
        ExecutionGate("OFFICIAL_PRICE_IDENTITY", evidence.official_price_identity, contract.fill_basis),
        ExecutionGate("CORPORATE_ACTION_CONTRACT", evidence.corporate_action_contract, "adjustment policy fixed"),
        ExecutionGate("IMMUTABLE_SOURCE_HASH", evidence.immutable_source_hash, "source fingerprint"),
        ExecutionGate("FOLD_LOCAL_TRANSFORM", evidence.fold_local_transform, "train-only fit"),
        ExecutionGate("NO_IMPOSSIBLE_SAME_CLOSE_FILL", not contract.uses_official_same_day_close, contract.mode.value),
    )
    blockers = tuple(gate.name for gate in gates if not gate.passed)
    verdict = "PASS_EXECUTION_READY" if not blockers else "BLOCKED_EXECUTION_CUSTODY"
    return ExecutionAuditReceipt(verdict, contract.mode, gates, blockers)


def ensure_observation_available(*, observed_at: datetime, decision_cutoff: datetime) -> None:
    if observed_at.tzinfo is None or decision_cutoff.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    if observed_at > decision_cutoff:
        raise FutureDataLeakError(observed_at, decision_cutoff)


def validate_stock_code(code: str) -> str:
    if _CODE_PATTERN.fullmatch(code) is None:
        raise ValueError(f"stock code must be a six-digit string: {code!r}")
    return code

