from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from stom_rl.daily_market_transition_contract import DailyMarketScore, build_market_state
from stom_rl.daily_market_transition_db import load_daily_market_candidates


def _database(
    path: Path,
    *,
    omit_exit_for_second: bool = False,
    zero_entry_for_first: bool = False,
) -> Path:
    with sqlite3.connect(path) as connection:
        for table, base in (("A000020", 100), ("A000040", 200)):
            _ = connection.execute(
                f'CREATE TABLE "{table}" (date INTEGER, open REAL, high REAL, low REAL, close REAL, volume REAL)'
            )
            rows = [
                (20260102, base, base, base, base, 1_000),
                (20260105, base + 10, base + 10, base + 10, base + 10, 1_100),
                (20260106, base + 20, base + 20, base + 20, base + 20, 1_200),
            ]
            if omit_exit_for_second and table == "A000040":
                _ = rows.pop()
            if zero_entry_for_first and table == "A000020":
                rows[1] = (20260105, 0, base + 10, base + 10, base + 10, 1_100)
            _ = connection.executemany(f'INSERT INTO "{table}" VALUES (?, ?, ?, ?, ?, ?)', rows)
    return path


def _scores() -> list[DailyMarketScore]:
    return [
        DailyMarketScore(decision_date=date(2026, 1, 2), code="000020", score=0.9, split="TRAIN"),
        DailyMarketScore(decision_date=date(2026, 1, 2), code="000040", score=0.8, split="TRAIN"),
    ]


def test_db_adapter_loads_exact_next_two_opens_without_changing_state_identity(tmp_path: Path) -> None:
    scores = _scores()
    before = build_market_state(
        scores,
        feature_vector=(0.1, 0.2),
        previous_exposure_ratio=Decimal("0"),
        previous_drawdown=Decimal("0"),
    )

    batch = load_daily_market_candidates(scores, db_path=_database(tmp_path / "daily.db"))
    after = build_market_state(
        batch.candidates,
        feature_vector=(0.1, 0.2),
        previous_exposure_ratio=Decimal("0"),
        previous_drawdown=Decimal("0"),
    )

    assert before.state_hash == after.state_hash
    assert batch.candidates[0].entry_date.isoformat() == "2026-01-05"
    assert batch.candidates[0].exit_date.isoformat() == "2026-01-06"
    assert batch.candidates[0].entry_open_krw == Decimal("110")
    assert batch.candidates[0].exit_open_krw == Decimal("120")
    assert batch.price_basis == "unknown"
    assert batch.decision_grade_status == "BLOCKED_UNTIL_PRICE_BASIS_VERIFIED"
    assert "D0_PRICE_BASIS_NOT_VERIFIED" in batch.blockers
    assert len(batch.source_identity) == 64
    assert len(batch.split_hash) == 64


def test_db_adapter_fails_the_whole_transition_instead_of_future_filtering(tmp_path: Path) -> None:
    db_path = _database(tmp_path / "missing.db", omit_exit_for_second=True)

    with pytest.raises(ValueError, match="000040.*MISSING_EXIT_OPEN"):
        _ = load_daily_market_candidates(_scores(), db_path=db_path)


def test_db_adapter_does_not_skip_an_invalid_exact_entry_open(tmp_path: Path) -> None:
    db_path = _database(tmp_path / "zero-entry.db", zero_entry_for_first=True)

    with pytest.raises(ValueError, match="000020.*INVALID_ENTRY_OPEN"):
        _ = load_daily_market_candidates(_scores(), db_path=db_path)


def test_future_price_change_does_not_change_state_hash(tmp_path: Path) -> None:
    scores = _scores()
    first_db = _database(tmp_path / "first.db")
    second_db = _database(tmp_path / "second.db")
    with sqlite3.connect(second_db) as connection:
        _ = connection.execute('UPDATE "A000020" SET open = 999 WHERE date = 20260106')
    first = load_daily_market_candidates(scores, db_path=first_db)
    second = load_daily_market_candidates(scores, db_path=second_db)

    first_state = build_market_state(
        first.candidates,
        feature_vector=(0.1,),
        previous_exposure_ratio=Decimal("0"),
        previous_drawdown=Decimal("0"),
    )
    second_state = build_market_state(
        second.candidates,
        feature_vector=(0.1,),
        previous_exposure_ratio=Decimal("0"),
        previous_drawdown=Decimal("0"),
    )

    assert first_state.state_hash == second_state.state_hash
    assert first.candidates[0].exit_open_krw != second.candidates[0].exit_open_krw
