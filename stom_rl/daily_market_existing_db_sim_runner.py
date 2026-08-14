"""One-shot runner for the preregistered existing-DB 60-day simulation."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from .daily_market_allocation_contract import AllocationAction
from .daily_market_existing_db_sim_artifacts import (
    ExistingDbSimulationArtifactPaths,
    write_existing_db_simulation_artifacts,
)
from .daily_market_existing_db_sim_contract import (
    ExistingDbSimulationMetrics,
    ExistingDbSimulationReceipt,
    ExistingDbSimulationStep,
    ExistingDbSimulationWindow,
    SimulationScenario,
)
from .daily_market_existing_db_sim_engine import (
    ConstantSimulationPolicy,
    NamedModelPolicy,
    RandomSimulationPolicy,
    paired_shuffle_policy,
    select_non_overlapping_window_days,
    simulate_existing_db_policy,
)
from .daily_market_existing_db_sim_gate import build_existing_db_simulation_gate
from .daily_market_existing_db_sim_inputs import (
    RESEARCH_ID,
    ExistingDbSimulationPaths,
    assert_simulation_database_unchanged,
    load_existing_db_simulation_inputs,
)
from .daily_market_rl_contract import (
    DailyMarketRlContractError,
    base_cost_config,
    stress_cost_config,
)
from .daily_market_rl_dataset import MarketDay, TrainScoreScale
from .daily_market_transition_contract import MarketTransitionConfig


def run_existing_db_policy_matrix(
    days: tuple[MarketDay, ...],
    scale: TrainScoreScale,
    policies: tuple[NamedModelPolicy, ...],
) -> tuple[
    tuple[ExistingDbSimulationMetrics, ...], tuple[ExistingDbSimulationStep, ...]
]:
    metrics: list[ExistingDbSimulationMetrics] = []
    steps: list[ExistingDbSimulationStep] = []
    scenarios: tuple[tuple[SimulationScenario, MarketTransitionConfig], ...] = (
        ("BASE_23BP", base_cost_config()),
        ("STRESS_46BP", stress_cost_config()),
    )
    model_steps: dict[
        tuple[int, SimulationScenario], tuple[ExistingDbSimulationStep, ...]
    ] = {}
    for policy in policies:
        for scenario, config in scenarios:
            result, trajectory = simulate_existing_db_policy(
                days, scale, policy, scenario=scenario, config=config
            )
            metrics.append(result)
            steps.extend(trajectory)
            model_steps[(policy.seed, scenario)] = trajectory
    controls = (
        ConstantSimulationPolicy("NO_TRADE", "CONTROL", AllocationAction.CASH),
        ConstantSimulationPolicy(
            "RULE_ALWAYS_TOP5", "RULE", AllocationAction.INVEST_TOP5_EQUAL_SLOT
        ),
        *(RandomSimulationPolicy(f"RANDOM_SEED_{seed}", seed) for seed in range(5)),
    )
    for policy in controls:
        for scenario, config in scenarios:
            result, trajectory = simulate_existing_db_policy(
                days, scale, policy, scenario=scenario, config=config
            )
            metrics.append(result)
            steps.extend(trajectory)
    for policy in policies:
        for scenario, config in scenarios:
            shuffled = paired_shuffle_policy(
                f"SHUFFLE_SEED_{policy.seed}",
                policy.seed,
                model_steps[(policy.seed, scenario)],
            )
            result, trajectory = simulate_existing_db_policy(
                days, scale, shuffled, scenario=scenario, config=config
            )
            metrics.append(result)
            steps.extend(trajectory)
    return tuple(metrics), tuple(steps)


def run_existing_db_60_simulation(
    paths: ExistingDbSimulationPaths,
) -> tuple[ExistingDbSimulationReceipt, ExistingDbSimulationArtifactPaths]:
    """Execute the fixed contaminated window once and publish immutable evidence."""
    if paths.output_directory.exists():
        raise DailyMarketRlContractError("HISTORICAL_SIMULATION_OUTPUT_UNTRUSTED")
    inputs = load_existing_db_simulation_inputs(paths)
    selected = select_non_overlapping_window_days(inputs.days)
    metrics, steps = run_existing_db_policy_matrix(
        inputs.days, inputs.scale, inputs.policies
    )
    gate = build_existing_db_simulation_gate(metrics)
    git_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    receipt = ExistingDbSimulationReceipt(
        schema_version="kronos_existing_db_60_historical_simulation.v1",
        research_id=RESEARCH_ID,
        verdict="HISTORICAL_SIMULATION_ONLY_NO_PROMOTION",
        status="COMPLETE_LOCAL_RESEARCH_ONLY",
        source_git_sha=git_sha,
        daily_database=inputs.database_identity,
        score_dataset_hash=inputs.score_dataset_hash,
        state_dataset_hash=inputs.state_dataset_hash,
        allocation_receipt=inputs.allocation_identity,
        checkpoint_identities=inputs.checkpoint_identities,
        window=ExistingDbSimulationWindow(
            selection_rule="LAST_60_REGISTERED_SCORE_DAYS",
            requested_score_days=60,
            start_decision_date=date(2026, 3, 9),
            end_decision_date=date(2026, 6, 11),
            validation_score_days=14,
            test_score_days=46,
            available_reward_days=len(inputs.days),
            blocked_reward_days=len(inputs.blocked_days),
            non_overlapping_decisions=len(selected),
        ),
        blocked_days=inputs.blocked_days,
        metrics=metrics,
        gate=gate,
        historical_state="VALIDATION_AND_TEST_ALREADY_CONSUMED_CONTAMINATED",
        future_data_used=False,
        local_db_fresh_holdout_read=False,
        independent_oos_claim_allowed=False,
        profitability_claim_allowed=False,
        promotion_allowed=False,
        paper_live_allowed=False,
    )
    artifacts = write_existing_db_simulation_artifacts(
        receipt, steps, paths.output_directory
    )
    assert_simulation_database_unchanged(paths, inputs.database_stat)
    return receipt, artifacts


def main(argv: Sequence[str] | None = None) -> int:
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        raise DailyMarketRlContractError("HISTORICAL_SIMULATION_REQUIRES_ROOT")
    receipt, artifacts = run_existing_db_60_simulation(
        ExistingDbSimulationPaths.registered(Path(arguments[0]))
    )
    print(
        json.dumps(
            {
                "research_id": receipt.research_id,
                "verdict": receipt.verdict,
                "technical_gate_passed": receipt.gate.technical_gate_passed,
                "receipt": str(artifacts.receipt.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
