from __future__ import annotations

from stom_rl.daily_close_research.features import RankSample
from stom_rl.daily_close_research.signal_floor import SignalFloorConfig, evaluate_rank_signal


def _predictable_cross_section() -> tuple[RankSample, ...]:
    rows: list[RankSample] = []
    for day in range(120):
        rows.extend(
            (
                RankSample(day, "000001", (1.0, 0.2, 0.1, 0.0), 0.012),
                RankSample(day, "000002", (0.0, 0.1, 0.1, 0.0), 0.001),
                RankSample(day, "000003", (-1.0, 0.0, 0.1, 0.0), -0.008),
            )
        )
    return tuple(rows)


def test_fold_local_ridge_signal_beats_cost_and_shuffle_control() -> None:
    receipt = evaluate_rank_signal(
        _predictable_cross_section(),
        SignalFloorConfig.registered(round_trip_cost_percent=0.230),
        shuffle_seeds=(0, 1, 2),
    )

    assert receipt.verdict == "PASS_SIGNAL_FLOOR"
    assert receipt.validation_fold_count == 4
    assert receipt.positive_fold_count == 4
    assert receipt.net_mean_percent > 0
    assert receipt.native_minus_shuffle_percent > 0


def test_signal_floor_fails_when_all_returns_are_below_cost() -> None:
    rows = tuple(
        RankSample(day, f"{code:06d}", (float(code), 0.0, 0.0, 0.0), 0.001)
        for day in range(80)
        for code in range(1, 4)
    )

    receipt = evaluate_rank_signal(
        rows,
        SignalFloorConfig.registered(round_trip_cost_percent=0.230),
        shuffle_seeds=(0, 1, 2),
    )

    assert receipt.verdict == "NO_GO_SIGNAL_FLOOR"
    assert receipt.net_mean_percent < 0

