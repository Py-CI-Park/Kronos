from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest
from pydantic import ValidationError

from stom_rl.daily_market_allocation_fresh_oos import (
    FRESH_OOS_ACTIONS,
    FreshOosPolicyKind,
    FreshOosPolicyCommitment,
    FreshOosWindowDescriptor,
    canonical_authority_receipt_bytes,
    canonical_descriptor_bytes,
    register_fresh_oos_window,
)
from stom_rl.daily_market_authority_contract import MarketAuthorityReceipt
from stom_rl.daily_market_rl_contract import DailyMarketRlContractError


def _policy(
    kind: FreshOosPolicyKind,
    policy_id: str,
    *,
    seed: int | None = None,
) -> FreshOosPolicyCommitment:
    return FreshOosPolicyCommitment(
        kind=kind,
        seed=seed,
        policy_id=policy_id,
        implementation_sha256=hashlib.sha256(f"impl:{policy_id}".encode()).hexdigest(),
        configuration_sha256=hashlib.sha256(f"config:{policy_id}".encode()).hexdigest(),
        checkpoint_sha256=(
            hashlib.sha256(f"checkpoint:{policy_id}".encode()).hexdigest()
            if kind == "CQL"
            else None
        ),
        paired_model_seed=seed if kind == "SHUFFLE" else None,
    )


def _policies() -> tuple[FreshOosPolicyCommitment, ...]:
    return (
        *(_policy("CQL", f"CQL_SEED_{seed}", seed=seed) for seed in range(5)),
        _policy("NO_TRADE", "NO_TRADE_CASH"),
        _policy("RULE", "RULE_ALWAYS_TOP5"),
        *(_policy("RANDOM", f"RANDOM_SEED_{seed}", seed=seed) for seed in range(5)),
        *(_policy("SHUFFLE", f"SHUFFLE_SEED_{seed}", seed=seed) for seed in range(5)),
    )


def _authority() -> MarketAuthorityReceipt:
    return MarketAuthorityReceipt.model_construct(status="BLOCKED_DATA_AUTHORITY")


def _descriptor() -> FreshOosWindowDescriptor:
    authority_sha256 = hashlib.sha256(
        canonical_authority_receipt_bytes(_authority())
    ).hexdigest()
    return FreshOosWindowDescriptor(
        schema="kronos_daily_market_fresh_oos_registration.v1",
        research_id="DAILY_MARKET_ALLOCATION_FRESH_OOS_2026_08_14_001",
        state="REGISTERED_SEALED_NO_READ",
        registered_at_utc="2026-08-14T00:00:00Z",
        first_eligible_trading_day="20260817",
        required_trading_days=60,
        source_git_sha="a" * 40,
        preregistration_sha256="b" * 64,
        evaluator_contract_sha256="c" * 64,
        authority_receipt_sha256=authority_sha256,
        approval_trust_store_sha256="e" * 64,
        custodian_principal="custodian://kronos/fresh-oos",
        actions=FRESH_OOS_ACTIONS,
        base_cost_bps=23,
        stress_cost_bps=46,
        policies=_policies(),
        historical_test_state="CONTAMINATED_FORBIDDEN",
        fresh_oos_state_features_read=False,
        fresh_oos_actions_read=False,
        fresh_oos_rewards_read=False,
        retuning_after_registration_allowed=False,
        retry_after_read_allowed=False,
        promotion_allowed=False,
        live_ready=False,
    )


def test_fresh_oos_descriptor_commits_exact_no_read_matrix() -> None:
    descriptor = _descriptor()

    first = canonical_descriptor_bytes(descriptor)
    second = canonical_descriptor_bytes(descriptor)

    assert first == second
    assert b"fresh_path" not in first
    assert descriptor.required_trading_days == 60
    assert tuple(
        policy.seed for policy in descriptor.policies if policy.kind == "CQL"
    ) == tuple(range(5))


def test_fresh_oos_descriptor_rejects_optional_window_and_matrix_drift() -> None:
    descriptor = _descriptor().model_dump(mode="json")
    descriptor["required_trading_days"] = 19
    with pytest.raises(ValidationError):
        _ = FreshOosWindowDescriptor.model_validate(descriptor)

    descriptor = _descriptor().model_dump(mode="json")
    descriptor["policies"] = descriptor["policies"][:-1]
    with pytest.raises(ValidationError, match="matrix is incomplete"):
        _ = FreshOosWindowDescriptor.model_validate(descriptor)

    descriptor = _descriptor().model_dump(mode="json")
    descriptor["fresh_path"] = "forbidden.csv"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        _ = FreshOosWindowDescriptor.model_validate(descriptor)


def test_fresh_oos_registration_writes_metadata_only_and_remains_blocked(
    tmp_path: Path,
) -> None:
    authority = _authority()
    output = tmp_path / "registration"

    receipt = register_fresh_oos_window(_descriptor(), output, authority)

    assert sorted(path.name for path in output.iterdir()) == [
        "fresh_oos_descriptor.json",
        "fresh_oos_registration_receipt.json",
    ]
    assert receipt.blockers == (
        "D0_D1_AUTHORITY_NOT_VERIFIED",
        "SEALED_WINDOW_ATTESTATION_MISSING",
        "HUMAN_ONE_READ_APPROVAL_MISSING",
    )
    assert receipt.fresh_oos_read is False
    assert receipt.one_read_authorized is False
    assert "fresh" not in inspect.signature(register_fresh_oos_window).parameters

    with pytest.raises(
        DailyMarketRlContractError,
        match="FRESH_OOS_REGISTRATION_OUTPUT_UNTRUSTED",
    ):
        _ = register_fresh_oos_window(_descriptor(), output, authority)


def test_fresh_oos_registration_rejects_authority_receipt_identity_drift(
    tmp_path: Path,
) -> None:
    authority = _authority().model_copy(
        update={"status": "VERIFIED_RESEARCH_DATA_AUTHORITY"}
    )

    with pytest.raises(
        DailyMarketRlContractError,
        match="FRESH_OOS_AUTHORITY_RECEIPT_IDENTITY_MISMATCH",
    ):
        _ = register_fresh_oos_window(
            _descriptor(),
            tmp_path / "registration",
            authority,
        )
