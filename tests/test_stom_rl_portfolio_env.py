import pytest

from stom_rl.portfolio_env import ACTION_HOLD, PortfolioEnv, PortfolioEnvConfig, synthetic_candidates


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
