from __future__ import annotations

from datetime import datetime, timezone

import pytest

from stom_rl.daily_close_research.contracts import (
    CloseExecutionMode,
    ExecutionEvidence,
    FutureDataLeakError,
    audit_execution_readiness,
    ensure_observation_available,
    registered_execution_contract,
    validate_stock_code,
)


def test_pre_close_proxy_contract_passes_only_with_all_point_in_time_evidence() -> None:
    contract = registered_execution_contract(CloseExecutionMode.PRE_CLOSE_PROXY)
    evidence = ExecutionEvidence.verified_for_tests()

    receipt = audit_execution_readiness(contract, evidence)

    assert receipt.verdict == "PASS_EXECUTION_READY"
    assert receipt.blockers == ()
    assert contract.fill_basis == "REGISTERED_CLOSE_PROXY"
    assert contract.uses_official_same_day_close is False


def test_unverified_contract_is_blocked_instead_of_soft_passed() -> None:
    contract = registered_execution_contract(CloseExecutionMode.POST_CLOSE_NEXT_OPEN)

    receipt = audit_execution_readiness(contract, ExecutionEvidence.unverified())

    assert receipt.verdict == "BLOCKED_EXECUTION_CUSTODY"
    assert "POINT_IN_TIME_UNIVERSE" in receipt.blockers
    assert "AVAILABLE_AT_PROVEN" in receipt.blockers
    assert contract.fill_basis == "NEXT_SESSION_OPEN"


def test_observation_after_cutoff_is_rejected_as_future_data() -> None:
    cutoff = datetime(2026, 8, 4, 6, 20, tzinfo=timezone.utc)
    observed = datetime(2026, 8, 4, 6, 21, tzinfo=timezone.utc)

    with pytest.raises(FutureDataLeakError, match="after decision cutoff"):
        ensure_observation_available(observed_at=observed, decision_cutoff=cutoff)


def test_stock_code_preserves_leading_zero_and_rejects_invalid_shape() -> None:
    assert validate_stock_code("000250") == "000250"
    with pytest.raises(ValueError, match="six-digit"):
        validate_stock_code("250")

