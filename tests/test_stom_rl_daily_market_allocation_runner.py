from __future__ import annotations

from pathlib import Path

from stom_rl.daily_market_allocation_experiment import planned_allocation_arms
from stom_rl.daily_market_allocation_rl_contract import (
    ALLOCATION_MODEL_SEEDS,
    AllocationAlgorithm,
)
from stom_rl.daily_market_allocation_runner import DailyMarketAllocationPaths


def test_allocation_plan_contains_dqn_and_cql_five_seed_arms() -> None:
    # Given/When: the preregistered multi-action model plan is expanded.
    arms = planned_allocation_arms()

    # Then: exactly ten models are fixed before any validation execution.
    assert len(arms) == 10
    assert {
        algorithm: tuple(row.seed for row in arms if row.algorithm is algorithm)
        for algorithm in AllocationAlgorithm
    } == {algorithm: ALLOCATION_MODEL_SEEDS for algorithm in AllocationAlgorithm}


def test_registered_allocation_paths_never_point_at_test_or_fresh_data(
    tmp_path: Path,
) -> None:
    # Given/When: one repository root is registered.
    paths = DailyMarketAllocationPaths.registered(tmp_path)

    # Then: sources, authority receipt, and generated screen have fixed locations.
    dataset = (
        tmp_path
        / "webui"
        / "rl_runs"
        / "daily_close_slot_dataset"
        / "daily_close_slot_research_dataset_2026_07_03"
    )
    assert paths.candidate_scores == dataset / "candidate_score_rows.csv"
    assert paths.causal_panel == dataset / "close_slot_panel.csv"
    assert paths.authority_receipt.name == "authority_receipt.json"
    assert (
        paths.output_directory.name == "DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_001"
    )
