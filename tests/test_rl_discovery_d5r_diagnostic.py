from __future__ import annotations

import pytest

from stom_rl.rl_discovery.d3_env import D3Episode
from stom_rl.rl_discovery.d5r_diagnostic import D5REvent, diagnose_d5r_unit


def _episode(decision_date: str, returns: tuple[float, ...]) -> D3Episode:
    candidates = tuple(
        (f"{index:06d}", (0.0,) * 14, gross_return)
        for index, gross_return in enumerate(returns, start=1)
    )
    return D3Episode(decision_date, candidates, (0.0,) * 14, 0.0)


def test_d5r_diagnostic_separates_exact_and_near_optimal_actions() -> None:
    episodes = (
        _episode("2026-01-02", (0.0100, 0.0090, -0.01, -0.02, -0.03)),
        _episode("2026-01-03", (-0.01, -0.02, -0.03, -0.04, -0.05)),
    )
    events = (
        D5REvent("2026-01-02", 2, 1, 0.0067),
        D5REvent("2026-01-03", 0, 0, 0.0),
    )

    result = diagnose_d5r_unit(episodes, events, cost_bp=23)

    assert result.exact_accuracy == 0.5
    assert result.near_optimal_5bp == 0.5
    assert result.near_optimal_10bp == 1.0
    assert result.near_optimal_25bp == 1.0
    assert result.mean_regret_bp == pytest.approx(5.0)
    assert result.median_regret_bp == pytest.approx(5.0)
