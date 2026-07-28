from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from stom_rl.rl_discovery.d1_contract import D1RewardKind
from stom_rl.rl_discovery.d1_env import BinaryAction, BinaryCandidateEnv
from stom_rl.rl_discovery.d1_fixture import load_d1_fixture

FIXTURE = Path(__file__).with_name("fixtures") / "type1_synthetic_fixture.json"


def test_binary_env_decodes_select_from_observation_without_future_returns() -> None:
    original = load_d1_fixture(FIXTURE)[1]
    changed = deepcopy(original)
    changed["gross_returns"] = ["-0.99"] * 500
    first = BinaryCandidateEnv((original,), reward_kind=D1RewardKind.NATIVE_ECONOMIC)
    second = BinaryCandidateEnv((changed,), reward_kind=D1RewardKind.NATIVE_ECONOMIC)

    first_observation, _ = first.reset(seed=0)
    second_observation, _ = second.reset(seed=0)
    _, _, _, _, info = first.step(BinaryAction.SELECT_TOP_OBSERVED)

    assert np.array_equal(first_observation, second_observation)
    assert info["decoded_action"] == 1
    assert first.action_space.n == 2


def test_diagnostic_reward_applies_only_to_first_decision() -> None:
    pair = load_d1_fixture(FIXTURE)[1]
    env = BinaryCandidateEnv((pair,), reward_kind=D1RewardKind.FIRST_DECISION_DIAGNOSTIC)
    _ = env.reset(seed=0)

    _, first_reward, first_terminated, _, _ = env.step(BinaryAction.SELECT_TOP_OBSERVED)
    _, second_reward, second_terminated, _, _ = env.step(BinaryAction.STOP)

    assert first_reward == pytest.approx(1.0)
    assert second_reward == pytest.approx(0.0)
    assert not first_terminated and not second_terminated


def test_binary_action_mask_keeps_stop_and_available_select() -> None:
    pair = load_d1_fixture(FIXTURE)[1]
    env = BinaryCandidateEnv((pair,), reward_kind=D1RewardKind.NATIVE_ECONOMIC)
    _ = env.reset(seed=0)

    assert env.action_masks().tolist() == [True, True]
