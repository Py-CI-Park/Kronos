from __future__ import annotations

from pathlib import Path

from stom_rl.daily_market_rl_artifacts import write_experiment_artifacts
from stom_rl.daily_market_rl_contract import MarketAlgorithm
from stom_rl.daily_market_rl_evaluation import (
    MarketPolicyMetrics,
    MarketPolicyTrajectory,
    MarketTrajectoryStep,
)
from stom_rl.daily_market_rl_experiment_contract import (
    LabeledTrajectory,
    DashboardExperimentSummary,
    MarketExperimentExecution,
    MarketExperimentReceipt,
    ModelArmReceipt,
)
from stom_rl.daily_market_rl_gate import (
    EconomicGateCheck,
    EconomicGateResult,
    SeedBootstrapInterval,
)


def _metrics(policy: str) -> MarketPolicyMetrics:
    return MarketPolicyMetrics(
        policy=policy,
        policy_kind="RL",
        split="TEST",
        round_trip_cost_percent=0.23,
        date_count=1,
        initial_nav_krw=60_000_000.0,
        final_nav_krw=60_300_000.0,
        total_net_pnl_krw=300_000.0,
        net_return_percent=0.5,
        max_drawdown_percent=-1.0,
        invest_action_count=1,
        invest_action_rate=1.0,
        filled_slots=10,
        total_cost_krw=100_000.0,
        turnover=0.8,
        mean_reward=0.005,
        cumulative_reward=0.005,
    )


def _execution() -> MarketExperimentExecution:
    metrics = _metrics("CQL")
    gate = EconomicGateResult(
        schema_version="kronos_daily_market_economic_gate.v1",
        verdict="NO_GO_HISTORICAL_ECONOMIC_GATE",
        checks=(EconomicGateCheck(check_id="TEST_CHECK", passed=False, observed="failed"),),
        failed_checks=("TEST_CHECK",),
        best_control_return_percent=0.0,
        cql_base_median_return_percent=0.5,
        cql_stress_median_return_percent=-0.1,
        reward_shuffled_median_return_percent=0.2,
        action_shuffled_median_return_percent=0.3,
        cql_seed_bootstrap_95=SeedBootstrapInterval(
            estimate=0.5,
            low=-0.1,
            high=1.0,
            resamples=5000,
            bootstrap_seed=20260809,
        ),
        promotion_blockers=("D0_PRICE_BASIS_NOT_VERIFIED",),
        promotion_allowed=False,
        fresh_oos_read=False,
    )
    def arm(algorithm: MarketAlgorithm) -> ModelArmReceipt:
        algorithm_metrics = metrics.model_copy(update={"policy": algorithm.value})
        return ModelArmReceipt(
            algorithm=algorithm,
            seed=0,
            shuffle_seed=0,
            loss_first=1.0,
            loss_last=0.1,
            checkpoint_path=f"models/{algorithm.value}/seed-0.kq",
            checkpoint_sha256="a" * 64,
            validation_base=algorithm_metrics.model_copy(update={"split": "VALIDATION"}),
            validation_stress=algorithm_metrics.model_copy(update={"split": "VALIDATION"}),
            historical_test_base=algorithm_metrics,
            historical_test_stress=algorithm_metrics,
        )
    receipt = MarketExperimentReceipt(
        schema_version="kronos_daily_market_offline_rl_experiment.v1",
        research_id="DAILY_MARKET_CQL_2026_08_09_001",
        verdict=gate.verdict,
        status="COMPLETE_RESEARCH_ONLY",
        algorithm="CQL",
        dataset_id="state-dataset",
        primary_headline="historical TEST NO-GO",
        reasons=("TEST_CHECK",),
        score_dataset_hash="b" * 64,
        state_dataset_hash="c" * 64,
        training_reward_read_splits=("TRAIN", "VALIDATION"),
        final_reward_read_splits=("TEST",),
        available_train_validation_days=2,
        blocked_train_validation_days=0,
        available_test_days=1,
        blocked_test_days=1,
        non_overlapping_train_days=1,
        non_overlapping_validation_days=1,
        non_overlapping_test_days=1,
        behavior_transition_count=32,
        controls_validation_base=(metrics.model_copy(update={"split": "VALIDATION"}),),
        controls_validation_stress=(metrics.model_copy(update={"split": "VALIDATION"}),),
        controls_historical_test_base=(metrics.model_copy(update={"policy": "NO_TRADE", "policy_kind": "RULE"}),),
        controls_historical_test_stress=(metrics.model_copy(update={"policy": "NO_TRADE", "policy_kind": "RULE"}),),
        model_runs=tuple(arm(algorithm) for algorithm in MarketAlgorithm),
        economic_gate=gate,
        fresh_oos_state="NOT_RUN_NO_READ",
        promotion_allowed=False,
        live_ready=False,
    )
    trajectory = MarketPolicyTrajectory(
        metrics=metrics,
        steps=(
            MarketTrajectoryStep(
                decision_date="2026-01-02",
                action="INVEST_TOP10_EQUAL_SLOT",
                final_nav_krw=60_300_000.0,
                deployed_at_entry_krw=50_000_000.0,
                total_cost_krw=100_000.0,
                reward_log_nav=0.005,
                drawdown_percent=-1.0,
                filled_slots=10,
            ),
        ),
        research_scope="LOCAL_RETROSPECTIVE_RESEARCH",
        promotion_allowed=False,
        fresh_oos_read=False,
    )
    return MarketExperimentExecution(
        receipt,
        (LabeledTrajectory(algorithm="CQL", seed=0, scenario="BASE_0_230_PERCENT", trajectory=trajectory),),
    )


def test_artifacts_write_bounded_dashboard_summary_and_separate_action_ledger(tmp_path: Path) -> None:
    # Given: one complete research-only execution receipt.
    # When: immutable JSON evidence is written.
    paths = write_experiment_artifacts(_execution(), tmp_path)

    # Then: catalog summary is bounded while full receipt and actions remain separate.
    summary = DashboardExperimentSummary.model_validate_json(paths.summary.read_bytes())
    assert summary.verdict == "NO_GO_HISTORICAL_ECONOMIC_GATE"
    assert summary.algorithm == "CQL"
    assert summary.promotion_allowed is False
    assert len(summary.summary) <= 16
    assert [row.policy for row in summary.summary] == [
        "NO_TRADE",
        "DQN/seed-0",
        "CQL/seed-0",
    ]
    assert paths.receipt.is_file()
    assert paths.action_ledger.is_file()
    assert paths.action_ledger.read_text(encoding="utf-8").count("\n") == 1
