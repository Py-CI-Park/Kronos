import pytest

from stom_rl.rl_discovery.d6_evaluation import maximum_cumulative_reward_drawdown


def test_d6_drawdown_measures_peak_to_later_cumulative_trough() -> None:
    # Given
    rewards = (0.10, -0.04, -0.09, 0.08, -0.01)

    # When
    drawdown = maximum_cumulative_reward_drawdown(rewards)

    # Then
    assert drawdown == pytest.approx(0.13)


def test_d6_drawdown_is_zero_for_monotonic_positive_rewards() -> None:
    assert maximum_cumulative_reward_drawdown((0.01, 0.02, 0.03)) == 0.0
