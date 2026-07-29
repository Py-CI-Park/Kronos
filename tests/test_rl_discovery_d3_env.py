from __future__ import annotations

import pytest

from stom_rl.rl_discovery.d3_env import D3Episode, D3PolicyArmId, D3Representation, HistoricalTopKEnv


def _episode() -> D3Episode:
    candidates = tuple(
        (f"{index:06d}", tuple(float(index) for _ in range(14)), gross)
        for index, gross in enumerate((0.01, -0.02, 0.03, 0.005, -0.01), start=1)
    )
    return D3Episode("2020-01-02", candidates, tuple(0.5 for _ in range(14)), 0.0)


@pytest.mark.parametrize(
    ("arm", "width", "actions"),
    [
        (D3PolicyArmId.TOP1_CONTEXT_1X, 29, 2),
        (D3PolicyArmId.TOP5_PLAIN_1X, 71, 6),
        (D3PolicyArmId.TOP5_CONTEXT_1X, 85, 6),
        (D3PolicyArmId.TOP5_CONTEXT_4X, 85, 6),
    ],
)
def test_d3_representation_has_registered_width_and_action_count(arm: D3PolicyArmId, width: int, actions: int) -> None:
    # Given/When: one frozen policy arm renders the same observable episode.
    representation = D3Representation.for_arm(arm)
    observation = representation.observation(_episode())

    # Then: its tensor and action-space widths match the preregistered factor.
    assert len(observation) == width
    assert representation.action_count == actions


def test_top5_environment_rewards_the_selected_observable_candidate() -> None:
    # Given: a top-five action environment with 23bp diagnostic cost.
    env = HistoricalTopKEnv((_episode(),), representation=D3Representation.for_arm(D3PolicyArmId.TOP5_CONTEXT_1X), cost_bp=23)
    env.reset(seed=0)

    # When: action 3 selects the third ranked observable candidate.
    _, reward, terminated, _, info = env.step(3)

    # Then: reward and evidence bind to candidate three, not the top-one row.
    assert reward == pytest.approx(0.03 - 0.0023)
    assert info["symbol"] == "000003"
    assert terminated is True
