from __future__ import annotations

from types import ModuleType
import sys

from stom_rl.rl_discovery.d3_contract import D3PolicyArmId
from stom_rl.rl_discovery.d3_env import D3Episode, D3Representation
from stom_rl.rl_discovery import d5r_training


def _episode() -> D3Episode:
    candidates = tuple(
        (f"{index:06d}", (0.0,) * 14, 0.01 * index)
        for index in range(1, 6)
    )
    return D3Episode("2026-01-02", candidates, (0.0,) * 14, 0.0)


def test_d5r_lineage_preserves_registered_buffer_across_checkpoints(monkeypatch) -> None:
    calls: list[tuple[int, bool]] = []
    constructor: dict[str, int | float | str] = {}

    class FakeDqn:
        def __init__(self, _policy, _vector, **kwargs) -> None:
            constructor.update(kwargs)

        def learn(
            self,
            *,
            total_timesteps: int,
            reset_num_timesteps: bool,
            progress_bar: bool,
        ) -> FakeDqn:
            assert progress_bar is False
            calls.append((total_timesteps, reset_num_timesteps))
            return self

        def predict(self, observation, *, deterministic: bool):
            return 0, None

        def save(self, path) -> None:
            return None

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
    monkeypatch.setattr(d5r_training, "prepare_torch_runtime", lambda: None, raising=False)

    lineage = d5r_training.start_d5r_lineage(
        (_episode(),),
        representation=D3Representation.for_arm(D3PolicyArmId.TOP5_CONTEXT_4X),
        seed=2,
        cost_bp=23,
    )
    checkpoint_400k = d5r_training.advance_d5r_lineage(lineage, target_steps=400_000)
    checkpoint_800k = d5r_training.advance_d5r_lineage(checkpoint_400k, target_steps=800_000)

    assert constructor["buffer_size"] == 200_000
    assert constructor["learning_starts"] == 128
    assert constructor["seed"] == 2
    assert calls == [(400_000, False), (400_000, False)]
    assert checkpoint_800k.trained_steps == 800_000
