"""Model and trajectory primitives for daily-market allocation test bundles."""

from __future__ import annotations

import hashlib
import math
from datetime import date, timedelta

from stom_rl.daily_market_allocation_contract import AllocationActionName
from stom_rl.daily_market_allocation_evaluation import summarize_allocation_steps
from stom_rl.daily_market_allocation_evaluation_contract import (
    AllocationPolicyMetrics,
    AllocationTrajectoryStep,
)
from stom_rl.daily_market_allocation_experiment_contract import AllocationModelReceipt
from stom_rl.daily_market_allocation_rl_contract import AllocationAlgorithm


def allocation_steps(
    *,
    initial_nav_krw: float,
    final_nav_krw: float,
    total_cost_krw: float,
) -> tuple[AllocationTrajectoryStep, ...]:
    rows: list[AllocationTrajectoryStep] = []
    actions: tuple[tuple[AllocationActionName, int], ...] = (
        ("CASH", 0),
        ("INVEST_TOP3_EQUAL_SLOT", 3),
        ("INVEST_TOP5_EQUAL_SLOT", 5),
        ("INVEST_TOP10_EQUAL_SLOT", 10),
    )
    previous_nav = initial_nav_krw
    ratio = math.exp(math.log(final_nav_krw / initial_nav_krw) / 24.0)
    first_day = date(2026, 1, 1)
    for index in range(24):
        action, slots = actions[index % len(actions)]
        final_nav = (
            final_nav_krw if index == 23 else initial_nav_krw * ratio ** (index + 1)
        )
        decision = first_day + timedelta(days=index * 3)
        rows.append(
            AllocationTrajectoryStep(
                decision_date=decision,
                entry_date=decision + timedelta(days=1),
                exit_date=decision + timedelta(days=2),
                action=action,
                final_nav_krw=final_nav,
                deployed_at_entry_krw=float(slots * 5_000_000),
                total_cost_krw=0.0 if action == "CASH" else total_cost_krw / 18.0,
                reward_log_nav=math.log(final_nav / previous_nav),
                drawdown_percent=0.0,
                filled_slots=slots,
            )
        )
        previous_nav = final_nav
    return tuple(rows)


def _metrics(
    algorithm: AllocationAlgorithm,
    seed: int,
    *,
    cost_percent: float,
    return_percent: float,
) -> AllocationPolicyMetrics:
    initial = 60_000_000.0
    pnl = initial * return_percent / 100.0
    return summarize_allocation_steps(
        policy=algorithm.value,
        policy_kind="RL",
        split="VALIDATION",
        round_trip_cost_percent=cost_percent,
        initial_nav_krw=initial,
        steps=allocation_steps(
            initial_nav_krw=initial,
            final_nav_krw=initial + pnl,
            total_cost_krw=100_000.0 + seed,
        ),
    )


def allocation_models(payloads: dict[str, bytes]) -> tuple[AllocationModelReceipt, ...]:
    rows: list[AllocationModelReceipt] = []
    for algorithm in AllocationAlgorithm:
        for seed in range(5):
            relative = f"models/{algorithm.value}/seed-{seed}.kq"
            payload = f"{algorithm.value}-{seed}".encode()
            payloads[relative] = payload
            base_return = (
                (0.1 + seed * 0.01)
                if algorithm is AllocationAlgorithm.DQN
                else (1.0 + seed * 0.1)
            )
            stress_return = (
                0.05 if algorithm is AllocationAlgorithm.DQN else (0.5 + seed * 0.05)
            )
            rows.append(
                AllocationModelReceipt(
                    algorithm=algorithm,
                    seed=seed,
                    loss_first=1.0,
                    loss_last=0.1,
                    checkpoint_path=relative,
                    checkpoint_sha256=hashlib.sha256(payload).hexdigest(),
                    validation_base=_metrics(
                        algorithm,
                        seed,
                        cost_percent=0.23,
                        return_percent=base_return,
                    ),
                    validation_stress=_metrics(
                        algorithm,
                        seed,
                        cost_percent=0.46,
                        return_percent=stress_return,
                    ),
                )
            )
    return tuple(rows)
