from __future__ import annotations

import json
from pathlib import Path

import pytest

from stom_rl.daily_market_authority_contract import AuthorityFileIdentity
from stom_rl.daily_market_local_db_audit import LocalDbCustodyReceipt, LocalDbQuality
from stom_rl.daily_market_local_db_evaluation import LocalDbEconomicGateReceipt
from stom_rl.daily_market_local_holdout import (
    LocalDbHoldoutPaths,
    build_local_holdout_descriptor,
    main,
    register_local_holdout,
)
from stom_rl.daily_market_rl_contract import DailyMarketRlContractError


def _identity(name: str, value: str) -> AuthorityFileIdentity:
    return AuthorityFileIdentity(
        path_suffix=name,
        size_bytes=10,
        modified_at_utc="2026-08-14T00:00:00+00:00",
        sha256=value * 64,
    )


def _custody() -> LocalDbCustodyReceipt:
    return LocalDbCustodyReceipt(
        schema_version="kronos_daily_market_local_db_custody.v1",
        research_id="DAILY_MARKET_LOCAL_DB_CUSTODY_2026_08_14_001",
        status="COMPLETE_LOCAL_RESEARCH_ONLY",
        daily_database=_identity("daily.db", "a"),
        stockinfo_database=_identity("stockinfo.json", "b"),
        quality=LocalDbQuality(
            table_count=1,
            nonempty_table_count=1,
            required_schema_table_count=1,
            explicit_price_basis_table_count=0,
            duplicate_date_table_count=0,
            total_row_count=2,
            first_date="20260102",
            last_date="20260103",
            stockinfo_row_count=1,
            leading_zero_codes_preserved=True,
            quality_passed=True,
        ),
        price_basis="UNKNOWN_LOCAL_DB_BASIS",
        universe_basis="CURRENT_SNAPSHOT_NOT_PIT",
        historical_test_state="CONTAMINATED_LOCAL_RESEARCH_ONLY",
        blockers=("D0_PRICE_BASIS_UNKNOWN_LOCAL_DB", "D1_CURRENT_SNAPSHOT_NOT_PIT"),
        local_research_allowed=True,
        independent_oos_claim_allowed=False,
        profitability_claim_allowed=False,
        promotion_allowed=False,
        paper_live_allowed=False,
        fresh_holdout_read=False,
        read_only=True,
        query_only=True,
    )


def _gate() -> LocalDbEconomicGateReceipt:
    return LocalDbEconomicGateReceipt(
        schema_version="kronos_daily_market_local_db_economic_gate.v1",
        research_id="DAILY_MARKET_LOCAL_DB_BASELINE_2026_08_14_001",
        verdict="NO_GO_LOCAL_DB_BASELINE",
        status="COMPLETE_LOCAL_RESEARCH_ONLY",
        source_experiment=_identity("experiment.json", "c"),
        source_custody=_identity("custody.json", "d"),
        source_research_id="DAILY_MARKET_CQL_2026_08_09_001",
        source_verdict="NO_GO_HISTORICAL_ECONOMIC_GATE",
        model_seed_matrix={
            "DQN": (0, 1, 2, 3, 4),
            "CQL": (0, 1, 2, 3, 4),
            "CQL_REWARD_SHUFFLED": (0, 1, 2, 3, 4),
            "CQL_ACTION_SHUFFLED": (0, 1, 2, 3, 4),
        },
        base_cost_bps=23,
        stress_cost_bps=46,
        controls_observed=("COST_AWARE_MOMENTUM_RULE", "NO_TRADE"),
        controls_required_next=(
            "NO_TRADE",
            "RULE",
            "RANDOM_SEEDS_0_TO_4",
            "SHUFFLE_SEEDS_0_TO_4",
        ),
        failed_checks=("RANDOM_POLICY_CONTROL_NOT_EVALUATED",),
        best_control_return_percent=0.0,
        cql_base_median_return_percent=-10.19155,
        cql_stress_median_return_percent=-12.391138,
        random_control_evaluated=False,
        historical_test_state="CONTAMINATED_LOCAL_RESEARCH_ONLY",
        fresh_holdout_state="NOT_RUN_NO_READ",
        retuning_allowed=False,
        independent_oos_claim_allowed=False,
        promotion_allowed=False,
        paper_live_allowed=False,
    )


def _paths(tmp_path: Path, *, database_hash: str = "a" * 64) -> LocalDbHoldoutPaths:
    custody, gate, allocation = (
        tmp_path / "custody.json",
        tmp_path / "gate.json",
        tmp_path / "allocation.json",
    )
    _ = custody.write_text(_custody().model_dump_json(), encoding="utf-8")
    _ = gate.write_text(_gate().model_dump_json(), encoding="utf-8")
    source = {
        "research_id": "DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_002",
        "verdict": "REPRODUCTION_ONLY_VALIDATION_CONSUMED",
        "daily_database_sha256": database_hash,
        "action_space": [
            "CASH",
            "INVEST_TOP3_EQUAL_SLOT",
            "INVEST_TOP5_EQUAL_SLOT",
            "INVEST_TOP10_EQUAL_SLOT",
        ],
        "model_runs": [
            {"algorithm": "CQL", "seed": seed, "checkpoint_sha256": f"{seed + 1:064x}"}
            for seed in range(5)
        ],
    }
    _ = allocation.write_text(json.dumps(source), encoding="utf-8")
    return LocalDbHoldoutPaths(custody, gate, allocation, tmp_path / "output")


def test_local_holdout_registration_freezes_matrix_without_reading_future_rows(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)

    descriptor = build_local_holdout_descriptor(
        paths,
        source_git_sha="f" * 40,
        registered_at_utc="2026-08-14T00:00:00Z",
    )
    registration = register_local_holdout(descriptor, paths.output_directory)

    assert descriptor.required_trading_days == 60
    assert (
        descriptor.first_session_rule == "FIRST_LOCAL_DB_SESSION_STRICTLY_AFTER_CUTOFF"
    )
    assert len(descriptor.policies) == 17
    assert tuple(
        policy.seed for policy in descriptor.policies if policy.kind == "CQL"
    ) == (0, 1, 2, 3, 4)
    assert descriptor.local_holdout_features_read is False
    assert registration.accumulated_trading_days == 0
    assert registration.one_read_authorized is False
    assert "LOCAL_DB_NOT_OFFICIAL_PIT_AUTHORITY" in registration.blockers
    assert sorted(path.name for path in paths.output_directory.iterdir()) == [
        "local_holdout_descriptor.json",
        "local_holdout_registration.json",
    ]


def test_local_holdout_rejects_database_identity_mismatch(tmp_path: Path) -> None:
    with pytest.raises(
        DailyMarketRlContractError,
        match="LOCAL_HOLDOUT_ALLOCATION_IDENTITY_INVALID",
    ):
        _ = build_local_holdout_descriptor(
            _paths(tmp_path, database_hash="e" * 64),
            source_git_sha="f" * 40,
            registered_at_utc="2026-08-14T00:00:00Z",
        )


def test_local_holdout_cli_requires_explicit_root() -> None:
    with pytest.raises(
        DailyMarketRlContractError,
        match="LOCAL_HOLDOUT_REQUIRES_REPOSITORY_ROOT",
    ):
        _ = main(())
