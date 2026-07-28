from __future__ import annotations

import numpy as np
import pytest

from stom_rl.rl_discovery.d2_env import D2Action, HistoricalCloseEnv, HistoricalEpisode


def _episode(index: int, value: float, reward: float) -> HistoricalEpisode:
    return HistoricalEpisode(
        decision_date=f"2020-01-{index + 2:02d}",
        symbol=f"{index + 1:06d}",
        observation=tuple([value] * 29),
        gross_return=reward,
    )


def test_historical_env_never_exposes_future_reward_in_observation() -> None:
    first = HistoricalCloseEnv((_episode(0, 0.25, 0.20),), cost_bp=0)
    changed = HistoricalCloseEnv((_episode(0, 0.25, -0.90),), cost_bp=0)

    first_obs, _ = first.reset(seed=0)
    changed_obs, _ = changed.reset(seed=0)
    _, reward, terminated, _, info = first.step(D2Action.BUY)

    assert np.array_equal(first_obs, changed_obs)
    assert reward == pytest.approx(0.20)
    assert terminated
    assert info["symbol"] == "000001"


def test_historical_env_applies_cost_and_rejects_step_after_terminal() -> None:
    env = HistoricalCloseEnv((_episode(0, 0.1, 0.01),), cost_bp=23)
    _ = env.reset(seed=0)

    _, reward, terminated, _, _ = env.step(D2Action.BUY)

    assert reward == pytest.approx(0.0077)
    assert terminated
    with pytest.raises(RuntimeError, match="terminal"):
        env.step(D2Action.STOP)
