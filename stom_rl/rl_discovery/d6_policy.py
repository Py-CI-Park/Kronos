"""Frozen D5S policy loading for D6 evaluation."""

from __future__ import annotations

from pathlib import Path

from stom_rl.rl_discovery.d2_custody import verified_bytes
from stom_rl.rl_discovery.d4_training import D4PlainPolicy
from stom_rl.rl_discovery.d6_source import D6ModelArtifact
from stom_rl.rl_discovery.torch_runtime import prepare_torch_runtime


def load_d6_policy(model: D6ModelArtifact, *, repo_root: Path) -> D4PlainPolicy:
    """Load one preregistered 100K DQN without attaching a training environment."""

    _ = verified_bytes(model.path, expected_sha256=model.sha256, anchor=repo_root.absolute())
    _ = prepare_torch_runtime()
    from stable_baselines3.dqn.dqn import DQN

    return D4PlainPolicy(DQN.load(model.path, device="cpu"))
