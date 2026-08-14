from __future__ import annotations

import json
from pathlib import Path

import pytest

from stom_rl.daily_market_authority_contract import AuthorityFileIdentity
from stom_rl.daily_market_local_db_audit import LocalDbCustodyReceipt, LocalDbQuality
from stom_rl.daily_market_local_db_evaluation import (
    LocalDbEvaluationPaths,
    evaluate_local_db_baseline,
    main,
    write_local_db_evaluation,
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


def _experiment(
    *,
    omit_seed: bool = False,
    swapped_costs: bool = False,
    boolean_seed: bool = False,
    omit_stress_control: bool = False,
) -> dict[str, object]:
    models: list[dict[str, object]] = []
    for algorithm in ("DQN", "CQL", "CQL_REWARD_SHUFFLED", "CQL_ACTION_SHUFFLED"):
        for seed in range(5):
            if omit_seed and algorithm == "CQL" and seed == 4:
                continue
            encoded_seed: int | bool = (
                True if boolean_seed and algorithm == "CQL" and seed == 1 else seed
            )
            models.append(
                {
                    "algorithm": algorithm,
                    "seed": encoded_seed,
                    "historical_test_base": {
                        "round_trip_cost_percent": 0.46 if swapped_costs else 0.23
                    },
                    "historical_test_stress": {
                        "round_trip_cost_percent": 0.23 if swapped_costs else 0.46
                    },
                }
            )
    base_controls = [
        {"policy": "NO_TRADE", "round_trip_cost_percent": 0.23},
        {
            "policy": "COST_AWARE_MOMENTUM_RULE",
            "round_trip_cost_percent": 0.23,
        },
    ]
    stress_controls = [
        {"policy": "NO_TRADE", "round_trip_cost_percent": 0.46},
        {
            "policy": "COST_AWARE_MOMENTUM_RULE",
            "round_trip_cost_percent": 0.46,
        },
    ]
    if omit_stress_control:
        _ = stress_controls.pop()
    return {
        "schema_version": "kronos_daily_market_offline_rl_experiment.v1",
        "research_id": "DAILY_MARKET_CQL_2026_08_09_001",
        "verdict": "NO_GO_HISTORICAL_ECONOMIC_GATE",
        "model_runs": models,
        "controls_historical_test_base": base_controls,
        "controls_historical_test_stress": stress_controls,
        "economic_gate": {
            "failed_checks": ["CQL_MEDIAN_BEATS_ZERO_AND_BEST_CONTROL"],
            "best_control_return_percent": 0.0,
            "cql_base_median_return_percent": -10.191550,
            "cql_stress_median_return_percent": -12.391138,
        },
    }


def _paths(
    tmp_path: Path,
    *,
    omit_seed: bool = False,
    swapped_costs: bool = False,
    boolean_seed: bool = False,
    omit_stress_control: bool = False,
) -> LocalDbEvaluationPaths:
    experiment = tmp_path / "experiment.json"
    custody = tmp_path / "custody.json"
    _ = experiment.write_text(
        json.dumps(
            _experiment(
                omit_seed=omit_seed,
                swapped_costs=swapped_costs,
                boolean_seed=boolean_seed,
                omit_stress_control=omit_stress_control,
            )
        ),
        encoding="utf-8",
    )
    _ = custody.write_text(_custody().model_dump_json(), encoding="utf-8")
    return LocalDbEvaluationPaths(experiment, custody, tmp_path / "output")


def test_local_db_evaluation_keeps_historical_no_go_and_control_gap(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)

    receipt = evaluate_local_db_baseline(paths)

    assert receipt.verdict == "NO_GO_LOCAL_DB_BASELINE"
    assert receipt.model_seed_matrix["CQL"] == (0, 1, 2, 3, 4)
    assert receipt.base_cost_bps == 23
    assert receipt.stress_cost_bps == 46
    assert receipt.cql_base_median_return_percent == -10.19155
    assert receipt.random_control_evaluated is False
    assert "RANDOM_POLICY_CONTROL_NOT_EVALUATED" in receipt.failed_checks
    assert receipt.independent_oos_claim_allowed is False
    assert receipt.retuning_allowed is False

    output = write_local_db_evaluation(receipt, paths.output_directory)
    assert output.is_file()


def test_local_db_evaluation_rejects_incomplete_seed_matrix(tmp_path: Path) -> None:
    with pytest.raises(
        DailyMarketRlContractError,
        match="LOCAL_DB_MODEL_SEED_MATRIX_INVALID",
    ):
        _ = evaluate_local_db_baseline(_paths(tmp_path, omit_seed=True))


@pytest.mark.parametrize(
    "path_kwargs, error",
    [
        ({"swapped_costs": True}, "LOCAL_DB_COST_SCENARIOS_INVALID"),
        ({"boolean_seed": True}, "LOCAL_DB_MODEL_SEED_MATRIX_INVALID"),
        ({"omit_stress_control": True}, "LOCAL_DB_REQUIRED_CONTROL_MISSING"),
    ],
)
def test_local_db_evaluation_rejects_noncanonical_matrix_evidence(
    tmp_path: Path,
    path_kwargs: dict[str, bool],
    error: str,
) -> None:
    with pytest.raises(DailyMarketRlContractError, match=error):
        _ = evaluate_local_db_baseline(_paths(tmp_path, **path_kwargs))


def test_local_db_evaluation_cli_requires_explicit_root() -> None:
    with pytest.raises(
        DailyMarketRlContractError,
        match="LOCAL_DB_EVALUATION_REQUIRES_REPOSITORY_ROOT",
    ):
        _ = main(())
