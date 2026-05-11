import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "finetune"))

import preflight_stom_2025_full as preflight  # noqa: E402


def _create_minimal_stom_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            '''
            CREATE TABLE "000001" (
                "timestamp" INTEGER,
                "close" REAL,
                "volume" REAL,
                "amount" REAL
            )
            '''
        )
        start = datetime(2025, 1, 3, 9, 0, 0)
        for i in range(3):
            ts = int((start + timedelta(seconds=i)).strftime("%Y%m%d%H%M%S"))
            conn.execute(
                'INSERT INTO "000001" VALUES (?, ?, ?, ?)',
                (ts, 1000 + i, 3, 3000 + i),
            )
        conn.commit()
    finally:
        conn.close()


def test_preflight_builds_2025_export_and_training_commands(tmp_path, monkeypatch):
    db_path = tmp_path / "stock_tick_back.db"
    _create_minimal_stom_db(db_path)
    scan_report = tmp_path / "scan.json"
    scan_report.write_text(
        json.dumps(
            {
                "split_by_session_70_15_15": {
                    "train": {"possible_samples_pred60": 123},
                    "val": {"possible_samples_pred60": 45},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        preflight,
        "_cuda_report",
        lambda python_exe: {"python": python_exe, "cuda_available": True, "memory_total_gb": 16},
    )

    args = preflight.parse_args(
        [
            "--db",
            str(db_path),
            "--scan-report",
            str(scan_report),
            "--export-dir",
            str(tmp_path / "export_2025"),
            "--output-root",
            str(tmp_path / "outputs"),
            "--python-exe",
            "python",
        ]
    )

    report = preflight.build_preflight(args)

    assert report["blockers"] == []
    assert report["db"]["query_only"] == 1
    assert report["db"]["write_probe_blocked"] is True
    assert "--session-start 20250101" in report["commands"]["export_2025_dataset"]
    assert "--session-end 20251231" in report["commands"]["export_2025_dataset"]
    assert "--n-train-iter 123" in report["commands"]["train_2025_full_small"]
    assert "--n-val-iter 45" in report["commands"]["train_2025_full_small"]
