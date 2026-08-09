"""Single-read historical TEST finalization for actual-market offline RL."""

from __future__ import annotations

from typing import Literal, TypeAlias

from .daily_market_rl_contract import (
    DailyMarketRlContractError,
    MarketAlgorithm,
    base_cost_config,
    stress_cost_config,
)
from .daily_market_rl_dataset import PreparedMarketData
from .daily_market_rl_evaluation import MarketPolicyTrajectory, simulate_policy
from .daily_market_rl_experiment import TrainedModelArm, registered_control_policies
from .daily_market_rl_experiment_contract import (
    LabeledTrajectory,
    MarketExperimentExecution,
    MarketExperimentReceipt,
    ModelArmReceipt,
)
from .daily_market_rl_gate import SeedOutcome, evaluate_economic_gate
from .daily_market_rl_trajectory import select_non_overlapping_days
from .daily_market_state_dataset import DailyMarketStateDataset
from .daily_market_transition_contract import MarketTransitionConfig, SplitName

EvaluationSplit: TypeAlias = Literal["VALIDATION", "TEST"]
ScenarioName: TypeAlias = Literal["BASE_0_230_PERCENT", "STRESS_0_460_PERCENT"]


def _control_replays(
    data: PreparedMarketData,
    state_dataset: DailyMarketStateDataset,
    split: EvaluationSplit,
    cost_config: MarketTransitionConfig,
) -> tuple[MarketPolicyTrajectory, ...]:
    return tuple(
        simulate_policy(
            data.days,
            data.score_scale,
            policy,
            split=split,
            cost_config=cost_config,
        )
        for policy in registered_control_policies(state_dataset)
    )


def _model_receipt(
    arm: TrainedModelArm,
    test_base: MarketPolicyTrajectory,
    test_stress: MarketPolicyTrajectory,
) -> ModelArmReceipt:
    checkpoint = arm.training.checkpoint_path
    checkpoint_hash = arm.training.checkpoint_sha256
    if checkpoint is None or checkpoint_hash is None:
        raise DailyMarketRlContractError("MODEL_CHECKPOINT_RECEIPT_MISSING")
    return ModelArmReceipt(
        algorithm=arm.plan.algorithm,
        seed=arm.plan.seed,
        shuffle_seed=arm.plan.shuffle_seed,
        loss_first=arm.training.losses[0],
        loss_last=arm.training.losses[-1],
        checkpoint_path=str(checkpoint.resolve()),
        checkpoint_sha256=checkpoint_hash,
        validation_base=arm.validation_base.metrics,
        validation_stress=arm.validation_stress.metrics,
        historical_test_base=test_base.metrics,
        historical_test_stress=test_stress.metrics,
    )


def _seed_outcomes(
    receipts: tuple[ModelArmReceipt, ...],
    algorithm: MarketAlgorithm,
) -> tuple[SeedOutcome, ...]:
    return tuple(
        SeedOutcome(
            algorithm=row.algorithm,
            seed=row.seed,
            historical_test_base=row.historical_test_base,
            historical_test_stress=row.historical_test_stress,
        )
        for row in receipts
        if row.algorithm is algorithm
    )


def finalize_experiment(
    train_validation: PreparedMarketData,
    historical_test: PreparedMarketData,
    state_dataset: DailyMarketStateDataset,
    trained: tuple[TrainedModelArm, ...],
    *,
    behavior_transition_count: int,
) -> MarketExperimentExecution:
    """Evaluate frozen policies after the one authorized historical TEST read."""
    validation_controls = _control_replays(
        train_validation,
        state_dataset,
        "VALIDATION",
        base_cost_config(),
    )
    validation_controls_stress = _control_replays(
        train_validation,
        state_dataset,
        "VALIDATION",
        stress_cost_config(),
    )
    test_controls = _control_replays(
        historical_test,
        state_dataset,
        "TEST",
        base_cost_config(),
    )
    test_controls_stress = _control_replays(
        historical_test,
        state_dataset,
        "TEST",
        stress_cost_config(),
    )
    receipts: list[ModelArmReceipt] = []
    trajectories: list[LabeledTrajectory] = []
    for arm in trained:
        test_base = simulate_policy(
            historical_test.days,
            historical_test.score_scale,
            arm.training.policy,
            split="TEST",
            cost_config=base_cost_config(),
        )
        test_stress = simulate_policy(
            historical_test.days,
            historical_test.score_scale,
            arm.training.policy,
            split="TEST",
            cost_config=stress_cost_config(),
        )
        receipts.append(_model_receipt(arm, test_base, test_stress))
        trajectories.extend((
            LabeledTrajectory(
                algorithm=arm.plan.algorithm.value,
                seed=arm.plan.seed,
                scenario="BASE_0_230_PERCENT",
                trajectory=test_base,
            ),
            LabeledTrajectory(
                algorithm=arm.plan.algorithm.value,
                seed=arm.plan.seed,
                scenario="STRESS_0_460_PERCENT",
                trajectory=test_stress,
            ),
        ))
    receipt_rows = tuple(receipts)
    gate = evaluate_economic_gate(
        _seed_outcomes(receipt_rows, MarketAlgorithm.CQL),
        _seed_outcomes(receipt_rows, MarketAlgorithm.CQL_REWARD_SHUFFLED),
        _seed_outcomes(receipt_rows, MarketAlgorithm.CQL_ACTION_SHUFFLED),
        tuple(row.metrics for row in test_controls),
    )
    control_scenarios: tuple[
        tuple[ScenarioName, tuple[MarketPolicyTrajectory, ...]],
        ...,
    ] = (
        ("BASE_0_230_PERCENT", test_controls),
        ("STRESS_0_460_PERCENT", test_controls_stress),
    )
    for scenario, control_rows in control_scenarios:
        trajectories.extend(
            LabeledTrajectory(
                algorithm=row.metrics.policy,
                scenario=scenario,
                trajectory=row,
            )
            for row in control_rows
        )
    receipt = MarketExperimentReceipt(
        schema_version="kronos_daily_market_offline_rl_experiment.v1",
        research_id="DAILY_MARKET_CQL_2026_08_09_001",
        verdict=gate.verdict,
        status="COMPLETE_RESEARCH_ONLY",
        algorithm="CQL",
        dataset_id=state_dataset.state_dataset_hash,
        primary_headline=f"실제 일봉 CQL historical TEST: {gate.verdict}",
        reasons=(*gate.failed_checks, *gate.promotion_blockers),
        score_dataset_hash=train_validation.score_dataset_hash,
        state_dataset_hash=train_validation.state_dataset_hash,
        training_reward_read_splits=("TRAIN", "VALIDATION"),
        final_reward_read_splits=("TEST",),
        available_train_validation_days=len(train_validation.days),
        blocked_train_validation_days=len(train_validation.blocked_days),
        available_test_days=len(historical_test.days),
        blocked_test_days=len(historical_test.blocked_days),
        non_overlapping_train_days=_day_count(train_validation, "TRAIN"),
        non_overlapping_validation_days=_day_count(train_validation, "VALIDATION"),
        non_overlapping_test_days=_day_count(historical_test, "TEST"),
        behavior_transition_count=behavior_transition_count,
        controls_validation_base=tuple(row.metrics for row in validation_controls),
        controls_validation_stress=tuple(row.metrics for row in validation_controls_stress),
        controls_historical_test_base=tuple(row.metrics for row in test_controls),
        controls_historical_test_stress=tuple(row.metrics for row in test_controls_stress),
        model_runs=receipt_rows,
        economic_gate=gate,
        fresh_oos_state="NOT_RUN_NO_READ",
        promotion_allowed=False,
        live_ready=False,
    )
    return MarketExperimentExecution(receipt, tuple(trajectories))


def _day_count(data: PreparedMarketData, split: SplitName) -> int:
    return len(select_non_overlapping_days(data.days, split=split))


__all__ = ["finalize_experiment"]
