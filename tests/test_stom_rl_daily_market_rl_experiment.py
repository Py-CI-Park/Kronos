from __future__ import annotations

from pathlib import Path

from stom_rl.daily_market_rl_contract import MODEL_SEEDS, MarketAlgorithm
from stom_rl.daily_market_rl_experiment import planned_model_arms
from stom_rl.daily_market_rl_runner import DailyMarketExperimentPaths


def test_experiment_plan_contains_all_four_five_seed_arms_before_test_read() -> None:
    # Given: the committed algorithm set and fixed model seeds.
    # When: the immutable training plan is expanded.
    arms = planned_model_arms()

    # Then: DQN, CQL, and both falsification controls each have exactly five seeds.
    assert len(arms) == 20
    assert {
        algorithm: tuple(row.seed for row in arms if row.algorithm is algorithm)
        for algorithm in MarketAlgorithm
    } == {algorithm: MODEL_SEEDS for algorithm in MarketAlgorithm}
    assert tuple(
        row.shuffle_seed
        for row in arms
        if row.algorithm is MarketAlgorithm.CQL_REWARD_SHUFFLED
    ) == tuple(100_000 + seed for seed in MODEL_SEEDS)
    assert tuple(
        row.shuffle_seed
        for row in arms
        if row.algorithm is MarketAlgorithm.CQL_ACTION_SHUFFLED
    ) == tuple(200_000 + seed for seed in MODEL_SEEDS)


def test_registered_runner_paths_keep_generated_models_under_one_research_run(tmp_path: Path) -> None:
    # Given: a repository root.
    # When: the registered actual-market experiment paths are resolved.
    paths = DailyMarketExperimentPaths.registered(tmp_path)

    # Then: source DB/dataset and generated output have fixed auditable locations.
    dataset = tmp_path / "webui/rl_runs/daily_close_slot_dataset/daily_close_slot_research_dataset_2026_07_03"
    assert paths.candidate_scores == dataset / "candidate_score_rows.csv"
    assert paths.source_manifest == dataset / "close_slot_dataset_manifest.json"
    assert paths.causal_panel == dataset / "close_slot_panel.csv"
    assert paths.daily_database == tmp_path / "_database/Stock_Database_ohlcv_1day.db"
    assert paths.output_directory == (
        tmp_path
        / "webui/rl_runs/daily_market_offline_rl/DAILY_MARKET_CQL_2026_08_09_001"
    )
