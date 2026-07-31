from stom_rl.rl_discovery.d3_contract import D3PolicyArmId
from stom_rl.rl_discovery.d3_env import D3Episode, D3Representation
from stom_rl.rl_discovery.d6r_folds import registered_d6r_folds, split_d6r_fold


def _episodes() -> tuple[D3Episode, ...]:
    candidates = tuple(
        (f"{index:06d}", (float(index),) + (0.0,) * 13, 0.01)
        for index in range(1, 6)
    )
    return tuple(
        D3Episode(f"2025-{index:03d}", candidates, (0.0,) * 14, index / 572)
        for index in range(573)
    )


def test_registered_d6r_folds_are_five_expanding_windows() -> None:
    # Given / When
    folds = registered_d6r_folds()

    # Then
    assert [(fold.train_end_exclusive, fold.evaluation_start, fold.evaluation_end_exclusive) for fold in folds] == [
        (323, 323, 373),
        (373, 373, 423),
        (423, 423, 473),
        (473, 473, 523),
        (523, 523, 573),
    ]


def test_split_d6r_fold_preserves_chronology_without_overlap() -> None:
    # Given
    episodes = _episodes()
    fold = registered_d6r_folds()[4]

    # When
    training, evaluation = split_d6r_fold(episodes, fold)

    # Then
    assert len(training) == 523
    assert len(evaluation) == 50
    assert training[-1].decision_date == "2025-522"
    assert evaluation[0].decision_date == "2025-523"
    assert evaluation[-1].decision_date == "2025-572"
    assert D3Representation.for_arm(D3PolicyArmId.TOP5_CONTEXT_4X).action_count == 6
