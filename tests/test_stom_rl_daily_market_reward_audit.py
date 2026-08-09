from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from stom_rl.daily_market_reward_audit import audit_daily_market_rewards
from stom_rl.daily_market_score_dataset import load_market_score_dataset


def _sources(root: Path) -> tuple[Path, Path]:
    manifest = root / "manifest.json"
    _ = manifest.write_text(
        json.dumps(
            {
                "fill_mode": "close_to_next_close_research_label",
                "price_basis": "unknown",
                "decision_grade_return_status": "BLOCKED_UNTIL_PRICE_BASIS_VERIFIED",
                "promotion_allowed": False,
            }
        ),
        encoding="utf-8",
    )
    scores = root / "scores.csv"
    with scores.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "table", "code", "score", "split", "eligible_for_selection"],
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "date": "20260102",
                    "table": "A000001",
                    "code": "000001",
                    "score": "1",
                    "split": "train",
                    "eligible_for_selection": "True",
                },
                {
                    "date": "20260105",
                    "table": "A000001",
                    "code": "000001",
                    "score": "2",
                    "split": "test",
                    "eligible_for_selection": "True",
                },
            ]
        )
    return scores, manifest


def _database(path: Path) -> Path:
    with sqlite3.connect(path) as connection:
        _ = connection.execute('CREATE TABLE "A000001" (date INTEGER, open REAL)')
        _ = connection.executemany(
            'INSERT INTO "A000001" VALUES (?, ?)',
            [(20260102, 100), (20260105, 110), (20260106, 120)],
        )
    return path


def test_reward_audit_preserves_pass_and_blocked_days_without_silent_filtering(tmp_path: Path) -> None:
    scores, manifest = _sources(tmp_path)
    dataset = load_market_score_dataset(
        scores,
        source_manifest_path=manifest,
        artifact_root=tmp_path,
    )

    audit = audit_daily_market_rewards(dataset, db_path=_database(tmp_path / "daily.db"))

    assert audit.total_days == 2
    assert audit.passed_days == 1
    assert audit.blocked_days == 1
    assert audit.split_pass_counts == {"TRAIN": 1}
    assert audit.reason_counts == {"MISSING_EXIT_OPEN": 1}
    assert audit.rows[0].status == "PASS"
    assert audit.rows[0].split_hash == dataset.days[0].day_hash
    assert audit.rows[1].status == "BLOCKED"
    assert audit.rows[1].reason == "000001:MISSING_EXIT_OPEN"
    assert audit.promotion_allowed is False
