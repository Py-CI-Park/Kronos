from stom_rl.rl_discovery.d6r_folds import registered_d6r_folds
from stom_rl.rl_discovery.d6r2_data import RawFeatureRow, RawSession, build_fold_episodes


def _session(index: int, offset: float) -> RawSession:
    rows = tuple(
        RawFeatureRow(
            symbol=f"{slot + 1:06d}",
            values=tuple(offset + slot + feature / 10 for feature in range(7)),
            gross_return=(slot - 2) / 100.0,
        )
        for slot in range(5)
    )
    return RawSession(f"2020-01-{index + 1:02d}", rows)


def test_fold_local_normalizer_excludes_evaluation_rows() -> None:
    sessions = tuple(_session(index, 0.0) for index in range(573))
    shifted = sessions[:323] + tuple(_session(index, 10_000.0) for index in range(323, 573))

    base = build_fold_episodes(sessions, registered_d6r_folds()[0])
    changed = build_fold_episodes(shifted, registered_d6r_folds()[0])

    assert base.scales == changed.scales
    assert base.normalizer_fit_session_count == 323
    assert base.normalizer_evaluation_row_count == 0
    assert base.evaluation != changed.evaluation
