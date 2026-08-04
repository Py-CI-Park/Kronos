from __future__ import annotations

from stom_rl.daily_close_research.offline_data import chronological_splits, synthetic_market_dataset


def test_synthetic_dataset_contains_both_actions_and_terminal_episodes() -> None:
    transitions = synthetic_market_dataset(seed=7, episode_count=8, episode_length=20)

    assert len(transitions) == 160
    assert {transition.action for transition in transitions} == {0, 1}
    assert sum(transition.done for transition in transitions) == 8
    assert all(len(transition.state) == 2 for transition in transitions)


def test_chronological_splits_never_mix_future_transitions_into_training() -> None:
    transitions = synthetic_market_dataset(seed=3, episode_count=10, episode_length=10)

    splits = chronological_splits(transitions, validation_fold_count=4)

    assert len(splits) == 4
    assert all(max(item.sequence for item in split.train) < min(item.sequence for item in split.validation) for split in splits)

