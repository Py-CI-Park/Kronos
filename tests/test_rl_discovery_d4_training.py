from __future__ import annotations

from types import ModuleType
import sys

import numpy as np

from stom_rl.rl_discovery import d4_training
from stom_rl.rl_discovery.d3_contract import D3PolicyArmId
from stom_rl.rl_discovery.d3_env import D3Episode, D3Representation
from stom_rl.rl_discovery.d4_contract import D4AlgorithmArmId
from stom_rl.rl_discovery.d4_training import D4TrainingConfig, supervised_examples


def _episode(gross: tuple[float, ...]) -> D3Episode:
    candidates = tuple(
        (f"{index:06d}", tuple(float(index) for _ in range(14)), reward)
        for index, reward in enumerate(gross, start=1)
    )
    return D3Episode("2020-01-02", candidates, tuple(0.5 for _ in range(14)), 0.0)


def test_d4_supervised_examples_keep_future_returns_out_of_observations() -> None:
    # Given: one positive candidate and one all-negative daily session.
    episodes = (
        _episode((-0.01, 0.02, 0.01, -0.03, 0.0)),
        _episode((-0.01, -0.02, -0.03, -0.04, -0.05)),
    )
    representation = D3Representation.for_arm(D3PolicyArmId.TOP5_CONTEXT_4X)

    # When: D4 builds supervised diagnostic examples.
    observations, actions = supervised_examples(episodes, representation=representation)

    # Then: labels identify candidate two and STOP, while tensors contain observable width only.
    assert observations.shape == (2, 85)
    assert actions.tolist() == [2, 0]
    assert 0.02 not in observations[0].tolist()


def test_d4_training_config_accepts_registered_environment_cost() -> None:
    config = D4TrainingConfig(D4AlgorithmArmId.DQN_DISCRETE, 0, 2048, 0, cost_bp=23)
    assert config.cost_bp == 23


def test_d4_dqn_training_does_not_evaluate_type_checking_only_names(monkeypatch) -> None:
    class FakeDqn:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def learn(self, *, total_timesteps: int, progress_bar: bool):
            assert total_timesteps == 1
            assert progress_bar is False
            return self

        def predict(self, observation, *, deterministic: bool):
            return np.asarray([0], dtype=np.int64), None

        def save(self, path) -> None:
            pass

    class FakeVec:
        def __init__(self, factories) -> None:
            self.factories = factories

    fake_torch = ModuleType("torch")
    fake_torch.manual_seed = lambda seed: seed
    fake_torch.set_num_threads = lambda count: None
    fake_torch.use_deterministic_algorithms = lambda enabled: None
    fake_sb3 = ModuleType("stable_baselines3")
    fake_sb3.DQN = FakeDqn
    fake_common = ModuleType("stable_baselines3.common")
    fake_vec = ModuleType("stable_baselines3.common.vec_env")
    fake_vec.DummyVecEnv = FakeVec
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "stable_baselines3", fake_sb3)
    monkeypatch.setitem(sys.modules, "stable_baselines3.common", fake_common)
    monkeypatch.setitem(sys.modules, "stable_baselines3.common.vec_env", fake_vec)
    monkeypatch.setattr(d4_training, "prepare_torch_runtime", lambda: None)

    trained = d4_training.train_d4_model(
        (_episode((0.01, 0.0, -0.01, -0.02, -0.03)),),
        representation=D3Representation.for_arm(D3PolicyArmId.TOP5_CONTEXT_4X),
        config=D4TrainingConfig(D4AlgorithmArmId.DQN_DISCRETE, 0, 1, 0, cost_bp=23),
    )

    assert isinstance(trained.policy, d4_training.D4PlainPolicy)
