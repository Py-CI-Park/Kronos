import pytest

from stom_rl.rl_discovery.d3_contract import D3PolicyArmId
from stom_rl.rl_discovery.d3_env import D3Episode, D3Representation
from stom_rl.rl_discovery.d6r_env import D6RTradePenaltyEnv


def _episode() -> D3Episode:
    candidates = tuple(
        (f"{index:06d}", (float(6 - index),) + (0.0,) * 13, 0.02)
        for index in range(1, 6)
    )
    return D3Episode("2025-01-01", candidates, (0.0,) * 14, 0.0)


def test_trade_penalty_applies_only_to_a_trade() -> None:
    # Given
    representation = D3Representation.for_arm(D3PolicyArmId.TOP5_CONTEXT_4X)
    trade_env = D6RTradePenaltyEnv(
        (_episode(),),
        representation=representation,
        cost_bp=23,
        additional_trade_penalty_bp=10,
    )
    hold_env = D6RTradePenaltyEnv(
        (_episode(),),
        representation=representation,
        cost_bp=23,
        additional_trade_penalty_bp=10,
    )
    _ = trade_env.reset(seed=0)
    _ = hold_env.reset(seed=0)

    # When
    _, trade_reward, *_ = trade_env.step(1)
    _, hold_reward, *_ = hold_env.step(0)

    # Then
    assert trade_reward == pytest.approx(0.0167)
    assert hold_reward == 0.0
