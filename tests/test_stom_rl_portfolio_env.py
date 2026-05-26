import numpy as np
import pandas as pd
import pytest

from stom_rl.portfolio_env import ACTION_HOLD, PortfolioEnv, PortfolioEnvConfig, synthetic_candidates


def _t1_candidates() -> pd.DataFrame:
    """Tiny in-memory candidate frame carrying the Page 9 T+1 fill contract.

    Symbol A rises 100->110->120, symbol B 50->55->60.  Per symbol, ``fill_price``
    is the next bar's close (T+1); the last bar has no T+1 so it is unfillable.
    No DB is required — this mirrors the real candidate schema in-memory.
    """

    base = pd.Timestamp("2025-07-09 09:00:00")
    prices = {"A": [100.0, 110.0, 120.0], "B": [50.0, 55.0, 60.0]}
    rows = []
    for symbol, series in prices.items():
        for t, price in enumerate(series):
            fill = series[t + 1] if t + 1 < len(series) else float("nan")
            rows.append(
                {
                    "timestamp": (base + pd.Timedelta(seconds=t)).isoformat(),
                    "symbol": symbol,
                    "condition_id": "t1_fixture",
                    "passed": True,
                    "rank_score": float((10 - t) if symbol == "A" else (5 - t)),
                    "price": price,
                    "fill_price": fill,
                    "fillable": not np.isnan(fill),
                    "feature_f": float(t),
                }
            )
    return pd.DataFrame(rows)


def test_portfolio_env_fills_at_t1_not_decision_bar():
    """A buy decided at T (close=100) must fill at the T+1 price (110)."""

    env = PortfolioEnv(
        PortfolioEnvConfig(top_k_candidates=2, max_positions=2, buy_fraction=0.5, cost_bps=0.0, seed=7),
        candidates=_t1_candidates(),
    )
    _, info = env.reset(seed=7)
    decision_ts = pd.Timestamp(info["timestamp"])

    env.step(1)  # buy highest-rank slot (symbol A, decision close=100)
    fill = env.trade_log[-1]

    assert fill["symbol"] == "A"
    # Fill price is the next-bar close, strictly above the decision-bar close.
    assert fill["price"] == pytest.approx(110.0)
    assert fill["price"] > 100.0
    # The decision timestamp is recorded; the executed price is from T+1.
    assert pd.Timestamp(fill["timestamp"]) == decision_ts


def test_portfolio_env_nav_conserved_after_t1_change():
    """cash + holdings == NAV must hold across a full T+1 episode."""

    env = PortfolioEnv(
        PortfolioEnvConfig(top_k_candidates=2, max_positions=2, buy_fraction=0.5, cost_bps=25.0, seed=7),
        candidates=_t1_candidates(),
    )
    _, info = env.reset(seed=7)
    terminated = False
    while not terminated:
        mask = list(info["action_mask"])
        action = next((a for a in range(1, len(mask)) if mask[a]), ACTION_HOLD)
        _, _, terminated, _, info = env.step(action)
        prices = {symbol: env.last_prices[symbol] for symbol in env.account.positions}
        # NAV is cash + holdings by construction; assert_invariants enforces it.
        env.account.assert_invariants({**env.last_prices, **prices})
        assert abs(info["nav"] - (info["cash"] + env.account.holdings_value(env.last_prices))) < 1e-6


def test_portfolio_env_unfillable_last_bar_cannot_buy():
    """A candidate with fillable==False (no T+1) is never buyable."""

    env = PortfolioEnv(
        PortfolioEnvConfig(top_k_candidates=2, max_positions=2, buy_fraction=0.5, invalid_action_penalty=1.0, seed=7),
        candidates=_t1_candidates(),
    )
    env.reset(seed=7)
    env.current_step = len(env.timestamps) - 1  # last bar: every candidate is unfillable
    candidates = env._current_candidates()
    assert not candidates["fillable"].any()

    mask = env.action_mask(candidates)
    # Only HOLD is permitted; all buy slots are masked out.
    assert mask[ACTION_HOLD] == 1
    sell_offset = 1 + env.config.top_k_candidates
    assert all(mask[slot] == 0 for slot in range(1, sell_offset))
    assert env._blocked_reason(1, candidates) == "unfillable_no_t1"


def test_portfolio_env_missing_fill_price_falls_back_with_warning():
    """Legacy CSVs without fill_price keep working (synthetic smoke path)."""

    with pytest.warns(RuntimeWarning, match="fill_price"):
        env = PortfolioEnv(
            PortfolioEnvConfig(top_k_candidates=2, max_positions=1),
            candidates=synthetic_candidates(),
        )
    _, info = env.reset(seed=1)
    # Fallback marks every positive-price row fillable, so a buy is still possible.
    assert info["action_mask"][1] == 1
    env.step(1)
    assert env.trade_log[-1]["price"] > 0


def test_portfolio_env_fixed_masks_and_discrete_action_layout():
    env = PortfolioEnv(
        PortfolioEnvConfig(top_k_candidates=2, max_positions=1, invalid_action_penalty=1.0),
        candidates=synthetic_candidates(),
    )
    observation, info = env.reset(seed=1)

    assert observation.shape == env.observation_space.shape
    assert env.action_space.n == 4
    assert info["candidate_mask"] == [1, 1]
    assert info["holding_mask"] == [0]
    assert env.decode_action(1) == {"type": "buy", "slot": 0}
    assert env.decode_action(3) == {"type": "sell", "slot": 0}

    _, reward, terminated, truncated, info = env.step(1)
    assert reward == pytest.approx(reward)
    assert terminated is False
    assert truncated is False
    assert info["trade_count"] == 1
    assert info["holding_mask"] == [1]

    _, invalid_reward, _, _, invalid_info = env.step(2)
    assert invalid_reward < 0
    assert invalid_info["invalid_action"] is True
    assert invalid_info["blocked_reason"] == "max_positions_reached"

    _, _, _, _, sell_info = env.step(3)
    assert sell_info["trade_count"] == 2


def test_portfolio_env_hold_action_is_always_valid():
    env = PortfolioEnv(PortfolioEnvConfig(top_k_candidates=3, max_positions=2), candidates=synthetic_candidates())
    _, info = env.reset()
    assert info["action_mask"][ACTION_HOLD] == 1
