from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from stom_rl.daily_market_rl_contract import base_cost_config, stress_cost_config
from stom_rl.daily_market_rl_dataset import MarketDay, TrainScoreScale
from stom_rl.daily_market_rl_evaluation import (
    ConstantMarketPolicy,
    CostAwareMomentumPolicy,
    simulate_policy,
)
from stom_rl.daily_market_score_dataset import CausalMarketScoreDay
from stom_rl.daily_market_state_dataset import CausalMarketStateDay
from stom_rl.daily_market_transition_contract import (
    BinaryAction,
    DailyMarketCandidate,
    DailyMarketScore,
    market_score_hash,
)


def _market_day(decision: date, *, five_day_return: float) -> MarketDay:
    scores = tuple(
        DailyMarketScore(
            decision_date=decision,
            code=f"{index:06d}",
            score=float(10 - index),
            split="TEST",
        )
        for index in range(1, 11)
    )
    day_hash = market_score_hash(scores)
    features = [0.0] * 160
    for slot in range(10):
        features[(slot * 16) + 2] = five_day_return
    state_day = CausalMarketStateDay(
        decision_date=decision.isoformat(),
        split="TEST",
        score_day_hash=day_hash,
        feature_vector=tuple(features),
        missing_feature_count=0,
        feature_hash="7" * 64,
    )
    candidates = tuple(
        DailyMarketCandidate(
            decision_date=score.decision_date,
            code=score.code,
            score=score.score,
            split=score.split,
            market_prefix=score.market_prefix,
            entry_date=decision + timedelta(days=1),
            exit_date=decision + timedelta(days=2),
            entry_open_krw=Decimal("10000"),
            exit_open_krw=Decimal("10100"),
        )
        for score in scores
    )
    return MarketDay(
        score_day=CausalMarketScoreDay(
            decision_date=decision,
            split="TEST",
            scores=scores,
            day_hash=day_hash,
        ),
        state_day=state_day,
        candidates=candidates,
    )


def _days() -> tuple[MarketDay, ...]:
    return (
        _market_day(date(2026, 1, 2), five_day_return=0.01),
        _market_day(date(2026, 1, 4), five_day_return=-0.01),
    )


def _scale() -> TrainScoreScale:
    return TrainScoreScale(mean=4.5, standard_deviation=2.872281323, scaling_denominator=2.872281323, observed_count=10)


def test_no_trade_control_preserves_sixty_million_nav() -> None:
    # Given: two non-overlapping TEST decisions and the no-trade policy.
    policy = ConstantMarketPolicy("NO_TRADE", BinaryAction.CASH)

    # When: the full real-accounting trajectory is replayed.
    result = simulate_policy(_days(), _scale(), policy, split="TEST", cost_config=base_cost_config())

    # Then: NAV, costs, and drawdown remain exactly neutral.
    assert result.metrics.final_nav_krw == 60_000_000.0
    assert result.metrics.net_return_percent == 0.0
    assert result.metrics.invest_action_count == 0
    assert result.metrics.total_cost_krw == 0.0
    assert result.metrics.max_drawdown_percent == 0.0


def test_always_invest_control_reports_costed_nav_and_stress_degradation() -> None:
    # Given: the same fixed investment policy under base and stress costs.
    policy = ConstantMarketPolicy("ALWAYS_INVEST", BinaryAction.INVEST_TOP10_EQUAL_SLOT)

    # When: both preregistered cost scenarios are replayed.
    base = simulate_policy(_days(), _scale(), policy, split="TEST", cost_config=base_cost_config())
    stress = simulate_policy(_days(), _scale(), policy, split="TEST", cost_config=stress_cost_config())

    # Then: the ledger is populated and higher costs reduce economic NAV.
    assert base.metrics.date_count == 2
    assert base.metrics.invest_action_count == 2
    assert base.metrics.filled_slots == 20
    assert base.metrics.total_cost_krw > 0.0
    assert base.metrics.net_return_percent > 0.0
    assert stress.metrics.final_nav_krw < base.metrics.final_nav_krw
    assert stress.metrics.total_cost_krw > base.metrics.total_cost_krw


def test_cost_aware_momentum_rule_uses_only_causal_five_day_return() -> None:
    # Given: positive then negative causal five-day momentum and a 0.230% threshold.
    policy = CostAwareMomentumPolicy(
        name="COST_AWARE_MOMENTUM_RULE",
        train_mean=0.0,
        train_scaling_denominator=1.0,
        threshold_fraction=0.0023,
    )

    # When: the interpretable rule is replayed.
    result = simulate_policy(_days(), _scale(), policy, split="TEST", cost_config=base_cost_config())

    # Then: only the positive-momentum day invests and the rule remains explicitly non-RL.
    assert tuple(step.action for step in result.steps) == (
        "INVEST_TOP10_EQUAL_SLOT",
        "CASH",
    )
    assert result.metrics.policy_kind == "RULE"
    assert result.metrics.invest_action_rate == 0.5
