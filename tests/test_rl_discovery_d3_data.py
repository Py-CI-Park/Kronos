from __future__ import annotations

from stom_rl.rl_discovery.d3_data import D3SourceRow, build_top_k_episodes


def _row(day: int, symbol: str, score: float, gross: float) -> D3SourceRow:
    return D3SourceRow.model_validate({
        "decision_date": f"2020-01-{day:02d}",
        "symbol": symbol,
        "split": "train",
        "features": {
            "ret_1d_prev": score,
            "ret_5d_prev": 0.1,
            "ret_20d_prev": 0.2,
            "vol_z_20": 0.3,
            "foreign_ratio_prev": 0.4,
            "foreign_ratio_delta_5": 0.5,
            "inst_netbuy_norm_5": 0.6,
        },
        "gross_return": gross,
        "entry_available": True,
    })


def test_d3_data_builds_observable_top_five_without_losing_stock_codes() -> None:
    # Given: two chronological sessions with six observable candidates each.
    rows = [
        _row(day, f"{symbol:06d}", float(symbol), symbol / 1000)
        for day in (2, 3)
        for symbol in range(1, 7)
    ]

    # When: the D3 adapter builds two episodes from the frozen scales.
    episodes = build_top_k_episodes(rows, scales=tuple((0.0, 1.0) for _ in range(7)), limit=2)

    # Then: rank uses observable score only and retains five six-digit symbols.
    assert [candidate[0] for candidate in episodes[0].candidates] == ["000006", "000005", "000004", "000003", "000002"]
    assert all(len(candidate[1]) == 14 for candidate in episodes[0].candidates)
