"""Finalize 002 validation evidence with contaminated TEST features disclosed."""

from __future__ import annotations

from .daily_market_allocation_experiment import TrainedAllocationArm
from .daily_market_allocation_experiment_contract import (
    AllocationExperimentExecution,
    AllocationExperimentReceipt,
    AllocationModelReceipt,
    LabeledAllocationTrajectory,
)
from .daily_market_allocation_gate import (
    AllocationSeedOutcome,
    evaluate_allocation_validation_gate,
)
from .daily_market_allocation_lineage_contract import AllocationLineageEvidence
from .daily_market_allocation_reproduction import (
    AllocationReproductionProjection,
    compare_allocation_reproduction,
)
from .daily_market_allocation_rl_contract import AllocationAlgorithm
from .daily_market_authority_contract import MarketAuthorityReceipt
from .daily_market_rl_contract import DailyMarketRlContractError
from .daily_market_rl_dataset import PreparedMarketData
from .daily_market_rl_trajectory import select_non_overlapping_days


def _model_receipt(arm: TrainedAllocationArm) -> AllocationModelReceipt:
    checkpoint = arm.training.checkpoint_path
    checkpoint_hash = arm.training.checkpoint_sha256
    if checkpoint is None or checkpoint_hash is None or not arm.training.losses:
        raise DailyMarketRlContractError("ALLOCATION_MODEL_EVIDENCE_INCOMPLETE")
    return AllocationModelReceipt(
        algorithm=arm.plan.algorithm,
        seed=arm.plan.seed,
        loss_first=arm.training.losses[0],
        loss_last=arm.training.losses[-1],
        checkpoint_path=(f"models/{arm.plan.algorithm.value}/seed-{arm.plan.seed}.kq"),
        checkpoint_sha256=checkpoint_hash,
        validation_base=arm.validation_base.metrics,
        validation_stress=arm.validation_stress.metrics,
    )


def _outcomes(
    trained: tuple[TrainedAllocationArm, ...],
    algorithm: AllocationAlgorithm,
) -> tuple[AllocationSeedOutcome, ...]:
    return tuple(
        AllocationSeedOutcome(
            algorithm=arm.plan.algorithm,
            seed=arm.plan.seed,
            validation_base=arm.validation_base.metrics,
            validation_stress=arm.validation_stress.metrics,
        )
        for arm in trained
        if arm.plan.algorithm is algorithm
    )


def finalize_allocation_screen(
    prepared: PreparedMarketData,
    authority: MarketAuthorityReceipt,
    trained: tuple[TrainedAllocationArm, ...],
    *,
    behavior_transition_count: int,
    lineage: AllocationLineageEvidence,
    reference_receipt: AllocationExperimentReceipt,
) -> AllocationExperimentExecution:
    """Freeze evidence while disclosing contaminated TEST features and unread Fresh OOS."""
    gate = evaluate_allocation_validation_gate(
        _outcomes(trained, AllocationAlgorithm.DQN),
        _outcomes(trained, AllocationAlgorithm.CQL),
    )
    model_runs = tuple(_model_receipt(arm) for arm in trained)
    train_days = tuple(row for row in prepared.days if row.split == "TRAIN")
    validation_days = tuple(row for row in prepared.days if row.split == "VALIDATION")
    if not train_days or not validation_days:
        raise DailyMarketRlContractError("ALLOCATION_SPLIT_DAYS_MISSING")
    non_overlapping_train_days = len(
        select_non_overlapping_days(prepared.days, split="TRAIN")
    )
    non_overlapping_validation_days = len(
        select_non_overlapping_days(prepared.days, split="VALIDATION")
    )
    reproduction = compare_allocation_reproduction(
        reference_receipt,
        AllocationReproductionProjection(
            score_dataset_hash=prepared.score_dataset_hash,
            state_dataset_hash=prepared.state_dataset_hash,
            authority_status=authority.status,
            authority_blockers=authority.blockers,
            daily_database_sha256=authority.daily_database.sha256,
            action_space=(
                "CASH",
                "INVEST_TOP3_EQUAL_SLOT",
                "INVEST_TOP5_EQUAL_SLOT",
                "INVEST_TOP10_EQUAL_SLOT",
            ),
            initial_capital_krw=60_000_000,
            cash_reserve_floor_krw=10_000_000,
            slot_notional_krw=5_000_000,
            base_round_trip_cost_percent=0.23,
            stress_round_trip_cost_percent=0.46,
            reward_read_splits=("TRAIN", "VALIDATION"),
            available_train_days=len(train_days),
            available_validation_days=len(validation_days),
            blocked_train_validation_days=len(prepared.blocked_days),
            non_overlapping_train_days=non_overlapping_train_days,
            non_overlapping_validation_days=non_overlapping_validation_days,
            behavior_transition_count=behavior_transition_count,
            model_runs=model_runs,
            validation_gate=gate,
        ),
        reference_receipt_sha256=next(
            row.sha256
            for row in lineage.input_hashes
            if row.role == "SOURCE_ALLOCATION_RECEIPT_001"
        ),
    )
    bound_lineage = lineage.model_copy(update={"reproduction": reproduction})
    reproduction_reason = (
        "VALIDATION_REPRODUCTION_MATCHED_001"
        if reproduction.exact_match
        else "VALIDATION_REPRODUCTION_MISMATCHED_001"
    )
    reasons = (
        *gate.failed_checks,
        reproduction_reason,
        "VALIDATION_ALREADY_CONSUMED_BY_001",
        *authority.blockers,
        "HISTORICAL_TEST_FEATURES_ALREADY_CONSUMED_REWARDS_NOT_READ",
        "FRESH_OOS_NOT_RUN_NO_READ",
    )
    receipt = AllocationExperimentReceipt(
        schema_version="kronos_daily_market_allocation_screen.v1",
        research_id="DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_002",
        verdict=(
            "REPRODUCTION_ONLY_VALIDATION_CONSUMED"
            if reproduction.exact_match
            else "REPRODUCTION_MISMATCH_VALIDATION_CONSUMED"
        ),
        status="COMPLETE_RESEARCH_ONLY",
        algorithm="CQL",
        dataset_id=(
            f"{prepared.score_dataset_hash[:16]}-{prepared.state_dataset_hash[:16]}"
        ),
        primary_headline=(
            "4행동 일봉 CQL 계보 재현 일치: 기존 VALIDATION 소비됨"
            if reproduction.exact_match
            else "4행동 일봉 CQL 계보 재현 불일치: 연구 실패"
        ),
        reasons=reasons,
        score_dataset_hash=prepared.score_dataset_hash,
        state_dataset_hash=prepared.state_dataset_hash,
        authority_research_id=authority.research_id,
        authority_status=authority.status,
        authority_blockers=authority.blockers,
        daily_database_sha256=authority.daily_database.sha256,
        action_space=(
            "CASH",
            "INVEST_TOP3_EQUAL_SLOT",
            "INVEST_TOP5_EQUAL_SLOT",
            "INVEST_TOP10_EQUAL_SLOT",
        ),
        initial_capital_krw=60_000_000,
        cash_reserve_floor_krw=10_000_000,
        slot_notional_krw=5_000_000,
        base_round_trip_cost_percent=0.23,
        stress_round_trip_cost_percent=0.46,
        reward_read_splits=("TRAIN", "VALIDATION"),
        available_train_days=len(train_days),
        available_validation_days=len(validation_days),
        blocked_train_validation_days=len(prepared.blocked_days),
        non_overlapping_train_days=non_overlapping_train_days,
        non_overlapping_validation_days=non_overlapping_validation_days,
        behavior_transition_count=behavior_transition_count,
        model_runs=model_runs,
        validation_gate=gate,
        historical_test_state="FEATURES_PARSED_REWARDS_NOT_READ_CONTAMINATED",
        fresh_oos_state="NOT_RUN_NO_READ",
        promotion_allowed=False,
        live_ready=False,
        lineage=bound_lineage,
    )
    trajectories = tuple(
        trajectory
        for arm in trained
        for trajectory in (
            LabeledAllocationTrajectory(
                algorithm=arm.plan.algorithm,
                seed=arm.plan.seed,
                scenario="BASE_0_230_PERCENT",
                trajectory=arm.validation_base,
            ),
            LabeledAllocationTrajectory(
                algorithm=arm.plan.algorithm,
                seed=arm.plan.seed,
                scenario="STRESS_0_460_PERCENT",
                trajectory=arm.validation_stress,
            ),
        )
    )
    return AllocationExperimentExecution(receipt, trajectories)


__all__ = ["finalize_allocation_screen"]
