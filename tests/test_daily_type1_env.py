from __future__ import annotations

import numpy as np
import pytest
from gymnasium.utils.env_checker import check_env

from stom_rl.daily_type1_env import ACTION_COUNT, EXTRACTOR_WIDTH, Type1ClosingEnv, Type1DictExtractor, validate_type1_pairs


def _pair(*, pair_index=0, returns=None, availability=None, entry_available=None,
          post_decision_fill_available=None, symbols=None, **metadata):
    decision_day = 6 + pair_index * 3
    availability = np.ones(500, dtype=np.int8) if availability is None else availability
    entry_available = availability if entry_available is None else entry_available
    post_decision_fill_available = (
        np.ones(500, dtype=np.int8)
        if post_decision_fill_available is None
        else post_decision_fill_available
    )
    return {
        "decision_date": f"2026-01-{decision_day:02d}",
        "settlement_date": f"2026-01-{decision_day + 1:02d}",
        "observation_cutoff_d1": f"2026-01-{decision_day - 1:02d}",
        "observation_cutoff_d2": f"2026-01-{decision_day - 2:02d}",
        "split_label": "RESEARCH_ONLY_HISTORICAL_SECONDARY",
        "partition_label": "historical_secondary_only",
        "fresh_oos_access_allowed": False,
        "execution_proxy": "15:20_bar_close_proxy",
        "proxy_time": "15:20:00",
        "proxy_timezone": "Asia/Seoul",
        "official_close": False,
        "missing_entry_policy": "NO_FILL",
        "candidate_values": np.zeros((500, 7), dtype=np.float32),
        "candidate_missing": np.zeros((500, 7), dtype=np.int8),
        "availability_mask": availability,
        "symbols": tuple(f"{slot:06d}" for slot in range(1, 501)) if symbols is None else symbols,
        "gross_returns": ["0"] * 500 if returns is None else returns,
        "entry_available": entry_available,
        "post_decision_fill_available": post_decision_fill_available,
        **metadata,
    }


def _finish(env: Type1ClosingEnv, first: int = 0):
    result = None
    for call in range(10):
        result = env.step(first if call == 0 else 0)
    assert result is not None
    return result


def test_dict_observation_width_stable_slots_and_gym_checker():
    env = Type1ClosingEnv([_pair()])
    observation, _ = env.reset(seed=0)
    assert env.extractor_width == EXTRACTOR_WIDTH == 8514
    assert observation["candidate_values"].shape == (500, 7)
    assert observation["candidate_missing"].dtype == np.int8
    assert observation["availability_mask"].dtype == np.int8
    assert env.action_space.n == ACTION_COUNT == 501
    assert Type1DictExtractor().features_dim == EXTRACTOR_WIDTH
    assert observation["candidate_values"].dtype == np.float32
    assert env.observation_space.contains(observation)
    check_env(env, skip_render_check=True)


def test_stop_padding_masks_duplicates_cap_and_terminal_vector():
    env = Type1ClosingEnv([_pair()])
    env.reset()
    assert env.action_masks()[0]
    env.step(1)
    assert not env.action_masks()[1]
    blocked = env.step(1)
    assert blocked[1:4] == (-1.0, True, False)

    observation, _ = env.reset()
    assert observation["portfolio_state"].tolist() == [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    env.step(0)
    assert env.action_masks().tolist() == [True] + [False] * 500
    result = None
    for _ in range(9):
        result = env.step(0)
    assert result is not None
    observation, reward, terminated, truncated, _ = result
    assert reward == 0.0 and terminated and not truncated
    assert observation["portfolio_state"].tolist() == [1.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0]


def test_two_session_chronology_no_fill_block_and_reward_accounting():
    returns = ["0"] * 500
    returns[0] = "0.01"
    second = ["0"] * 500
    second[1] = "-0.005"
    env = Type1ClosingEnv([_pair(returns=returns), _pair(pair_index=1, returns=second)])
    env.reset()
    observation, reward, terminated, _, _ = _finish(env, 1)
    assert not terminated
    assert abs(reward - 0.000641666667) < 1e-12
    assert observation["prior_selection_mask"][0] == 1
    assert observation["portfolio_state"][0] == 0
    assert np.allclose(observation["portfolio_state"][5:8], [0.1, 0.1, 0.0])
    observation, reward, terminated, _, _ = _finish(env, 2)
    assert terminated
    assert abs(reward + 0.000608333333) < 1e-12
    assert np.allclose(observation["portfolio_state"][8:11], [0.1, 0.1, 0.0])


    missing_exit = ["0"] * 500
    missing_exit[0] = None
    env = Type1ClosingEnv([_pair(returns=missing_exit)])
    env.reset()
    observation, reward, terminated, truncated, info = _finish(env, 1)
    assert reward == -1.0 and terminated and not truncated
    assert info["reason"] == "missing_settlement"
    assert observation["portfolio_state"][8:11].tolist() == [0.0, 0.0, 0.0]


def test_zero_one_ten_and_five_hundred_candidate_masks_preserve_leading_zeroes():
    for count in (0, 1, 10, 500):
        availability = np.zeros(500, dtype=np.int8)
        availability[:count] = 1
        env = Type1ClosingEnv([_pair(availability=availability)])
        observation, _ = env.reset(seed=123)
        assert observation["availability_mask"].sum() == count
        assert env._pairs[0]["symbols"][0] == "000001"
        assert env.action_masks().tolist() == [True] + [slot < count for slot in range(500)]

def test_pair_validation_rejects_overlap_slot_reorder_fresh_oos_and_future_features():
    first = _pair(pair_index=0)
    overlap = _pair(pair_index=0)
    with pytest.raises(ValueError, match="overlap"):
        validate_type1_pairs([first, overlap])

    reordered = list(_pair(pair_index=1)["symbols"])
    reordered[:2] = reversed(reordered[:2])
    with pytest.raises(ValueError, match="symbol mapping"):
        Type1ClosingEnv([first, _pair(pair_index=1, symbols=tuple(reordered))])

    with pytest.raises(ValueError, match="fresh OOS"):
        Type1ClosingEnv([_pair(fresh_oos_access_allowed=True)])
    with pytest.raises(ValueError, match="fresh OOS window"):
        Type1ClosingEnv([_pair(decision_date="2026-08-03", settlement_date="2026-08-04",
                               observation_cutoff_d1="2026-08-02", observation_cutoff_d2="2026-08-01")])
    with pytest.raises(ValueError, match="D-2"):
        Type1ClosingEnv([_pair(observation_cutoff_d1="2026-01-06", observation_cutoff_d2="2026-01-07")])


def test_explicit_all_available_fill_settles_and_outage_is_no_fill():
    returns = ["0"] * 500
    returns[0] = "0.01"
    all_available = np.ones(500, dtype=np.int8)
    env = Type1ClosingEnv([_pair(returns=returns, post_decision_fill_available=all_available)])
    env.reset()
    observation, reward, terminated, _, _ = _finish(env, 1)
    assert terminated and reward == pytest.approx(0.000641666667)
    assert np.allclose(observation["portfolio_state"][8:11], [0.1, 0.1, 0.0])

    all_available[0] = 0
    env = Type1ClosingEnv([_pair(returns=returns, post_decision_fill_available=all_available)])
    env.reset()
    observation, reward, terminated, _, _ = _finish(env, 1)
    assert terminated and reward == 0.0
    assert np.allclose(observation["portfolio_state"][8:11], [0.1, 0.0, 0.1])

def test_invalid_middle_pair_preserves_progress():

    env = Type1ClosingEnv([_pair(pair_index=0), _pair(pair_index=1), _pair(pair_index=2)])
    env.reset()
    _finish(env)
    before = env._observation()
    observation, reward, terminated, truncated, info = env.step(999)
    assert (reward, terminated, truncated, info["reason"]) == (-1.0, True, False, "action must be STOP (0) or a stable slot (1..500)")
    assert observation["portfolio_state"][0] == 0.1
    assert observation["portfolio_state"][11] == 0.5
    assert observation["portfolio_state"][1] == before["portfolio_state"][1] == 0.0
    assert observation["prior_selection_mask"].tolist() == before["prior_selection_mask"].tolist()
    assert not observation["current_selection_mask"].any()
def test_pair_input_boundaries_fail_closed():
    omitted_fill_evidence = _pair()
    omitted_fill_evidence.pop("post_decision_fill_available")
    with pytest.raises(ValueError, match="frozen-schema"):
        Type1ClosingEnv([omitted_fill_evidence])
    with pytest.raises(ValueError, match="frozen-schema"):
        Type1ClosingEnv([_pair(undocumented_metadata=True)])

    for field, value, match in (
        ("split_label", "OTHER", "research-only"),
        ("partition_label", "OTHER", "research-only"),
        ("execution_proxy", "official_close", "15:20"),
        ("proxy_time", "15:21:00", "15:20"),
        ("proxy_timezone", "UTC", "15:20"),
        ("official_close", True, "official-close"),
        ("missing_entry_policy", "FILL", "NO_FILL"),
    ):
        with pytest.raises(ValueError, match=match):
            Type1ClosingEnv([_pair(**{field: value})])

    for values, match in (
        (np.zeros((499, 7), dtype=np.float32), "candidate_values"),
        (np.full((500, 7), np.nan, dtype=np.float32), "candidate_values"),
        (np.full((500, 7), 10.1, dtype=np.float32), "clipped"),
    ):
        with pytest.raises(ValueError, match=match):
            Type1ClosingEnv([_pair(candidate_values=values)])

    for symbols, match in (
        (tuple(f"{slot:06d}" for slot in range(1, 500)), "exactly 500"),
        (("000001",) * 500, "unique"),
        (tuple(["BAD001"] + [f"{slot:06d}" for slot in range(2, 501)]), "six-digit"),
    ):
        with pytest.raises(ValueError, match=match):
            Type1ClosingEnv([_pair(symbols=symbols)])

    for returns, match in (
        (["0"] * 499, "exactly 500"),
        (["NaN"] + ["0"] * 499, r"gross_returns\[0\]"),
        ([True] + ["0"] * 499, r"gross_returns\[0\]"),
    ):
        with pytest.raises(ValueError, match=match):
            Type1ClosingEnv([_pair(returns=returns)])

    for invalid in ("1", -1, 2, 257, 0.5, np.nan, np.inf, object()):
        mask = np.zeros(500, dtype=object)
        mask[0] = invalid
        with pytest.raises(ValueError, match="binary"):
            Type1ClosingEnv([_pair(availability=mask, entry_available=mask)])

    contradictory_entry = np.ones(500, dtype=np.int8)
    contradictory_entry[0] = 0
    with pytest.raises(ValueError, match="15:20"):
        Type1ClosingEnv([_pair(entry_available=contradictory_entry)])

    with pytest.raises(ValueError, match="at least one"):
        validate_type1_pairs([])
    env = Type1ClosingEnv([_pair()])
    env.reset()
    for action in (True, 0.0, "0"):
        observation, reward, terminated, truncated, info = env.step(action)
        assert (reward, terminated, truncated, info["reason"]) == (-1.0, True, False, "action must be an integer")
        env.reset()


def test_max_slot_reserve_boundary_missing_settlement_and_terminal_immutability():
    env = Type1ClosingEnv([_pair()])
    env.reset()
    for action in range(1, 10):
        observation, reward, terminated, truncated, _ = env.step(action)
        assert reward == 0.0 and not terminated and not truncated
    assert env.action_masks()[10]
    settled = env.step(10)
    observation, reward, terminated, truncated, _ = settled
    assert terminated and not truncated
    assert not env.action_masks().any()
    snapshot = {name: value.copy() for name, value in observation.items()}
    repeated = env.step(1)
    assert repeated[1:4] == (-1.0, True, False)
    for name, value in snapshot.items():
        np.testing.assert_array_equal(repeated[0][name], value)
    assert env._call_index == 10 and len(env._selected) == 10

