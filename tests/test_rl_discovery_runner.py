from __future__ import annotations

from pathlib import Path

from stom_rl.rl_discovery import runner


def test_shuffle_reward_pairs_is_deterministic_and_does_not_mutate_source() -> None:
    # Given
    pairs = tuple(
        {
            "decision_date": f"2020-01-0{index + 1}",
            "gross_returns": [f"{index}.01", f"-{index}.01"],
        }
        for index in range(4)
    )
    original = tuple(tuple(pair["gross_returns"]) for pair in pairs)

    # When
    first = runner.shuffle_reward_pairs(pairs, seed=7)
    second = runner.shuffle_reward_pairs(pairs, seed=7)

    # Then
    assert tuple(tuple(pair["gross_returns"]) for pair in first) == tuple(
        tuple(pair["gross_returns"]) for pair in second
    )
    assert tuple(tuple(pair["gross_returns"]) for pair in pairs) == original
    assert tuple(tuple(pair["gross_returns"]) for pair in first) != original


def test_outcome_from_evaluation_uses_initial_decisions_for_collapse_rate() -> None:
    # Given
    events = [
        {"call_index": 0, "action": 1},
        {"call_index": 1, "action": 0},
        {"call_index": 0, "action": 1},
        {"call_index": 1, "action": 0},
    ]
    metrics = {
        "achieved_reward_ratio": "0.750000000000",
        "exact_basket_accuracy": "0.500000000000",
        "invalid_action_count": 0,
        "block_count": 0,
        "no_fill_count": 0,
    }

    # When
    outcome = runner.outcome_from_evaluation(
        arm="A_PPO_ONLY",
        seed=0,
        training_timesteps=256,
        shuffled_reward=False,
        events=events,
        metrics=metrics,
    )

    # Then
    assert outcome.oracle_reward_ratio == 0.75
    assert outcome.exact_basket_accuracy == 0.5
    assert outcome.dominant_action_rate == 1.0


def test_default_paths_keep_fresh_oos_outside_the_runner() -> None:
    paths = runner.DiscoveryPaths.default(Path("D:/repo"))

    assert paths.fixture == Path("D:/repo/tests/fixtures/type1_synthetic_fixture.json")
    assert "fresh" not in str(paths.fixture).lower()
    assert paths.run_root == Path("D:/repo/webui/rl_runs/rl_discovery")
