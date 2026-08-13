"""Canonical daily-market allocation bundle fixtures for publication tests."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from stom_rl.daily_market_allocation_artifacts import (
    write_allocation_artifacts,
)
from stom_rl.daily_market_allocation_evaluation_contract import (
    AllocationPolicyMetrics,
    AllocationPolicyTrajectory,
)
from stom_rl.daily_market_allocation_experiment_contract import (
    AllocationExperimentExecution,
    AllocationExperimentReceipt,
    LabeledAllocationTrajectory,
)
from stom_rl.daily_market_allocation_gate import (
    AllocationSeedOutcome,
    evaluate_allocation_validation_gate,
)
from stom_rl.daily_market_allocation_lineage_contract import (
    AllocationInputHash,
    AllocationLineageEvidence,
    AllocationLineageInputRole,
    AllocationTrainingEvidence,
)
from stom_rl.daily_market_allocation_reproduction import (
    allocation_reproduction_projection,
    compare_allocation_reproduction,
)
from stom_rl.daily_market_allocation_rl_contract import AllocationAlgorithm
from stom_rl.daily_market_rl_contract import BEHAVIOR_SEEDS
from tests.daily_market_allocation_fixture_models import (
    allocation_models,
    allocation_steps,
)


def canonical_allocation_receipt(
    payloads: dict[str, bytes],
) -> AllocationExperimentReceipt:
    models = allocation_models(payloads)
    outcomes = {
        algorithm: tuple(
            AllocationSeedOutcome(
                algorithm=row.algorithm,
                seed=row.seed,
                validation_base=row.validation_base,
                validation_stress=row.validation_stress,
            )
            for row in models
            if row.algorithm is algorithm
        )
        for algorithm in AllocationAlgorithm
    }
    gate = evaluate_allocation_validation_gate(
        outcomes[AllocationAlgorithm.DQN],
        outcomes[AllocationAlgorithm.CQL],
    )
    blockers = (
        "D0_PRICE_BASIS_NOT_VERIFIED",
        "D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED",
    )
    score_hash = "b" * 64
    state_hash = "c" * 64
    return AllocationExperimentReceipt(
        schema_version="kronos_daily_market_allocation_screen.v1",
        research_id="DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_001",
        verdict=gate.verdict,
        status="COMPLETE_RESEARCH_ONLY",
        algorithm="CQL",
        dataset_id=f"{score_hash[:16]}-{state_hash[:16]}",
        primary_headline="4-action validation candidate; TEST sealed",
        reasons=(
            *blockers,
            "HISTORICAL_TEST_NOT_RUN_NO_READ",
            "FRESH_OOS_NOT_RUN_NO_READ",
        ),
        score_dataset_hash=score_hash,
        state_dataset_hash=state_hash,
        authority_research_id="DAILY_MARKET_AUTHORITY_2026_08_10_001",
        authority_status="BLOCKED_DATA_AUTHORITY",
        authority_blockers=blockers,
        daily_database_sha256="a" * 64,
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
        available_train_days=151,
        available_validation_days=47,
        blocked_train_validation_days=0,
        non_overlapping_train_days=76,
        non_overlapping_validation_days=24,
        behavior_transition_count=2_432,
        model_runs=models,
        validation_gate=gate,
        historical_test_state="NOT_RUN_NO_READ",
        fresh_oos_state="NOT_RUN_NO_READ",
        promotion_allowed=False,
        live_ready=False,
    )


def write_valid_allocation_bundle(directory: Path) -> None:
    directory.mkdir(parents=True)
    execution = canonical_allocation_execution(directory)
    _ = write_allocation_artifacts(execution, directory)


def write_valid_reproduction_bundle(
    directory: Path,
    *,
    reference_directory: Path,
) -> None:
    reference_payload = (reference_directory / "validation_receipt.json").read_bytes()
    reference = AllocationExperimentReceipt.model_validate_json(reference_payload)
    execution = canonical_allocation_execution(directory)
    reference_receipt_sha256 = hashlib.sha256(reference_payload).hexdigest()
    input_hash_rows: tuple[tuple[AllocationLineageInputRole, str], ...] = (
        ("CANDIDATE_SCORES", "1" * 64),
        ("SOURCE_MANIFEST", "2" * 64),
        ("CAUSAL_PANEL", "3" * 64),
        ("AUTHORITY_RECEIPT", "4" * 64),
        ("SOURCE_ALLOCATION_RECEIPT_001", reference_receipt_sha256),
    )
    lineage = AllocationLineageEvidence(
        evidence_classification="POST_HOC_CUSTODY_REPRODUCTION",
        preregistration_path=(
            "docs/kronos_v1_29_0_market_authority_allocation_prereg_002_2026-08-10.md"
        ),
        preregistration_sha256="d" * 64,
        source_git_sha="e" * 40,
        source_bundle_sha256="f" * 64,
        input_hashes=tuple(
            AllocationInputHash(role=role, sha256=value)
            for role, value in input_hash_rows
        ),
        training=AllocationTrainingEvidence(
            model_seeds=(0, 1, 2, 3, 4),
            behavior_seeds=BEHAVIOR_SEEDS,
            behavior_policy="UNIFORM_RANDOM_FOUR_ACTIONS_TRAIN_ONLY",
            input_dimension=172,
            action_count=4,
            hidden_dimensions=(128, 64),
            learning_rate=0.0003,
            discount=0.95,
            dqn_cql_alpha=0.0,
            cql_cql_alpha=1.0,
            reward_scale=100.0,
            batch_size=256,
            gradient_steps=600,
            target_update_interval=25,
        ),
    )
    reproduction = compare_allocation_reproduction(
        reference,
        allocation_reproduction_projection(execution.receipt),
        reference_receipt_sha256=reference_receipt_sha256,
    )
    lineage = lineage.model_copy(update={"reproduction": reproduction})
    receipt_payload = execution.receipt.model_dump(mode="json")
    receipt_payload.update(
        {
            "research_id": "DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_002",
            "authority_research_id": "DAILY_MARKET_AUTHORITY_2026_08_10_002",
            "verdict": "REPRODUCTION_ONLY_VALIDATION_CONSUMED",
            "primary_headline": "001 exact custody reproduction; validation consumed",
            "reasons": [
                "VALIDATION_REPRODUCTION_MATCHED_001",
                "VALIDATION_ALREADY_CONSUMED_BY_001",
                *execution.receipt.authority_blockers,
                "HISTORICAL_TEST_FEATURES_ALREADY_CONSUMED_REWARDS_NOT_READ",
                "FRESH_OOS_NOT_RUN_NO_READ",
            ],
            "historical_test_state": ("FEATURES_PARSED_REWARDS_NOT_READ_CONTAMINATED"),
            "lineage": lineage.model_dump(mode="json"),
        }
    )
    reproduction_receipt = AllocationExperimentReceipt.model_validate(receipt_payload)
    _ = write_allocation_artifacts(
        AllocationExperimentExecution(
            receipt=reproduction_receipt,
            trajectories=execution.trajectories,
        ),
        directory,
    )


def canonical_allocation_execution(
    output_directory: Path,
) -> AllocationExperimentExecution:
    payloads: dict[str, bytes] = {}
    receipt = canonical_allocation_receipt(payloads)
    for relative_path, payload in payloads.items():
        path = output_directory / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_bytes(payload)
    trajectories: list[LabeledAllocationTrajectory] = []
    for model in receipt.model_runs:
        scenarios: tuple[
            tuple[
                Literal["BASE_0_230_PERCENT", "STRESS_0_460_PERCENT"],
                AllocationPolicyMetrics,
            ],
            ...,
        ] = (
            ("BASE_0_230_PERCENT", model.validation_base),
            ("STRESS_0_460_PERCENT", model.validation_stress),
        )
        for scenario, metrics in scenarios:
            trajectory = AllocationPolicyTrajectory(
                metrics=metrics,
                steps=allocation_steps(
                    initial_nav_krw=metrics.initial_nav_krw,
                    final_nav_krw=metrics.final_nav_krw,
                    total_cost_krw=100_000.0 + model.seed,
                ),
                research_scope="LOCAL_RETROSPECTIVE_RESEARCH",
                historical_test_read=False,
                fresh_oos_read=False,
                promotion_allowed=False,
            )
            trajectories.append(
                LabeledAllocationTrajectory(
                    algorithm=model.algorithm,
                    seed=model.seed,
                    scenario=scenario,
                    trajectory=trajectory,
                )
            )
    return AllocationExperimentExecution(
        receipt=receipt,
        trajectories=tuple(trajectories),
    )


__all__ = [
    "canonical_allocation_execution",
    "canonical_allocation_receipt",
    "write_valid_allocation_bundle",
    "write_valid_reproduction_bundle",
]
