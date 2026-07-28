from __future__ import annotations

import json
from pathlib import Path

from stom_rl.rl_discovery.d2_data import build_historical_episodes, iter_json_array


def _row(day: int, symbol: str, score: str, gross: str | None) -> dict[str, object]:
    return {
        "decision_date": f"2020-01-{day:02d}",
        "symbol": symbol,
        "split": "train",
        "features": {
            "ret_1d_prev": score,
            "ret_5d_prev": "0.1",
            "ret_20d_prev": "0.2",
            "vol_z_20": "0.3",
            "foreign_ratio_prev": "0.4",
            "foreign_ratio_delta_5": "0.5",
            "inst_netbuy_norm_5": "0.6"
        },
        "gross_return": gross,
        "entry_available": gross is not None
    }


def test_stream_and_build_use_observable_rank_and_chronological_prefix(tmp_path: Path) -> None:
    rows = [
        _row(2, "000001", "0.1", "0.01"),
        _row(2, "000002", "0.9", "-0.02"),
        _row(3, "000001", "0.8", "0.03"),
        _row(3, "000002", "0.2", "0.04"),
    ]
    path = tmp_path / "rows.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    scales = tuple((0.0, 1.0) for _ in range(7))

    episodes = build_historical_episodes(iter_json_array(path), scales=scales, limit=2)

    assert [(item.decision_date, item.symbol) for item in episodes] == [
        ("2020-01-02", "000002"),
        ("2020-01-03", "000001"),
    ]
    assert episodes[0].gross_return == -0.02
    assert len(episodes[0].observation) == 29
