from stom_rl.rl_discovery.d3_data import D3FeatureRow, D3SourceRow
from stom_rl.rl_discovery.d6_data import build_reused_validation_episodes


def _rows(decision_date: str, split: str, base: float) -> tuple[D3SourceRow, ...]:
    return tuple(
        D3SourceRow(
            decision_date=decision_date,
            symbol=f"{index:06d}",
            split=split,
            features=D3FeatureRow(
                ret_1d_prev=base + index,
                ret_5d_prev=0.0,
                ret_20d_prev=0.0,
                vol_z_20=0.0,
                foreign_ratio_prev=0.0,
                foreign_ratio_delta_5=0.0,
                inst_netbuy_norm_5=0.0,
            ),
            gross_return=float(index) / 100,
            entry_available=True,
        )
        for index in range(6)
    )


def test_d6_data_uses_only_chronological_reused_validation_sessions() -> None:
    # Given
    rows = (
        *_rows("20260102", "train", 100.0),
        *_rows("20260103", "reused_validation", 0.0),
        *_rows("20260104", "reused_validation", 1.0),
        *_rows("20260105", "reused_validation", 2.0),
    )

    # When
    episodes = build_reused_validation_episodes(
        rows,
        scales=((0.0, 1.0),) * 7,
        limit=2,
    )

    # Then
    assert tuple(episode.decision_date for episode in episodes) == ("20260103", "20260104")
    assert episodes[0].candidates[0][0] == "000005"
