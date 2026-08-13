from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from stom_rl.daily_market_allocation_contract import AllocationAction
from stom_rl.daily_market_allocation_evaluation import (
    ConstantAllocationPolicy,
    simulate_allocation_policy,
)
from stom_rl.daily_market_allocation_trajectory import (
    build_allocation_behavior_transitions,
)
from stom_rl.daily_market_rl_contract import base_cost_config
from stom_rl.daily_market_rl_dataset import MarketDay, TrainScoreScale
from stom_rl.daily_market_score_dataset import CausalMarketScoreDay
from stom_rl.daily_market_state_dataset import CausalMarketStateDay
from stom_rl.daily_market_transition_contract import (
    DailyMarketCandidate,
    DailyMarketScore,
    SplitName,
    market_score_hash,
)


def _market_day(decision: date, split: SplitName) -> MarketDay:
    scores = tuple(
        DailyMarketScore(
            decision_date=decision,
            code=f"{index:06d}",
            score=float(11 - index),
            split=split,
        )
        for index in range(1, 11)
    )
    day_hash = market_score_hash(scores)
    state = CausalMarketStateDay(
        decision_date=decision.isoformat(),
        split=split,
        score_day_hash=day_hash,
        feature_vector=(0.0,) * 160,
        missing_feature_count=0,
        feature_hash="7" * 64,
    )
    candidates = tuple(
        DailyMarketCandidate(
            decision_date=decision,
            code=score.code,
            score=score.score,
            split=split,
            entry_date=decision + timedelta(days=1),
            exit_date=decision + timedelta(days=2),
            entry_open_krw=Decimal("10000"),
            exit_open_krw=Decimal("10100"),
        )
        for score in scores
    )
    return MarketDay(
        CausalMarketScoreDay(
            decision_date=decision,
            split=split,
            scores=scores,
            day_hash=day_hash,
        ),
        state,
        candidates,
    )


def _scale() -> TrainScoreScale:
    return TrainScoreScale(5.5, 2.872281323, 2.872281323, 80)


def test_behavior_trajectories_cover_all_four_allocation_actions() -> None:
    # Given: eight non-overlapping TRAIN days and eight fixed behavior seeds.
    start = date(2025, 1, 2)
    days = tuple(
        _market_day(start + timedelta(days=index * 2), "TRAIN") for index in range(8)
    )

    # When: exploratory trajectories run through real cost accounting.
    transitions = build_allocation_behavior_transitions(
        days,
        _scale(),
        behavior_seeds=tuple(range(8)),
        cost_config=base_cost_config(),
    )

    # Then: every preregistered action is represented and inputs remain 172-D.
    assert {row.action for row in transitions} == {0, 1, 2, 3}
    assert all(
        len(row.state) == 172 and len(row.next_state) == 172 for row in transitions
    )


def test_top3_policy_reports_action_mix_costs_and_slots_on_validation() -> None:
    # Given: two non-overlapping validation days and a constant top-3 policy.
    days = (
        _market_day(date(2026, 1, 2), "VALIDATION"),
        _market_day(date(2026, 1, 4), "VALIDATION"),
    )
    policy = ConstantAllocationPolicy(
        "ALWAYS_TOP3",
        AllocationAction.INVEST_TOP3_EQUAL_SLOT,
    )

    # When: the policy is replayed under the registered 0.230% cost case.
    trajectory = simulate_allocation_policy(
        days,
        _scale(),
        policy,
        split="VALIDATION",
        cost_config=base_cost_config(),
    )

    # Then: action diversity and economic accounting are directly inspectable.
    assert trajectory.metrics.action_top3_count == 2
    assert trajectory.metrics.distinct_action_count == 1
    assert trajectory.metrics.filled_slots == 6
    assert trajectory.metrics.total_cost_krw > 0
    assert tuple(step.action for step in trajectory.steps) == (
        "INVEST_TOP3_EQUAL_SLOT",
        "INVEST_TOP3_EQUAL_SLOT",
    )
