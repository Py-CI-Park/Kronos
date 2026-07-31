import numpy as np

from stom_rl.rl_discovery.d3_contract import D3PolicyArmId
from stom_rl.rl_discovery.d3_env import D3Episode, D3Representation
from stom_rl.rl_discovery.d6r2_training import train_ridge_reward_policy


def _episode(index: int) -> D3Episode:
    winning_slot = index % 5
    candidates = tuple(
        (
            f"{slot + 1:06d}",
            tuple(float(slot == feature % 5) for feature in range(14)),
            0.02 if slot == winning_slot else -0.01,
        )
        for slot in range(5)
    )
    return D3Episode(str(index), candidates, (0.0,) * 14, index / 29)


def test_ridge_reward_ceiling_predicts_registered_action_space() -> None:
    episodes = tuple(_episode(index) for index in range(30))
    representation = D3Representation.for_arm(D3PolicyArmId.TOP5_CONTEXT_4X)

    policy = train_ridge_reward_policy(episodes, representation=representation, cost_bp=23, alpha=1.0)
    observation = np.asarray(representation.observation(episodes[0]), dtype=np.float32)
    action, state = policy.predict(observation, deterministic=True, action_masks=np.ones(6, dtype=np.bool_))

    assert 0 <= int(action.item()) < 6
    assert state is None

