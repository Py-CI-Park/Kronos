"""Backend tests for the RL run-lifecycle snapshot (plan Todo 6, backend half).

The dashboard read is a snapshot and can never observe an advancing step, so it
must never return RUNNING / never be LIVE. It returns COMPLETED / REPLAY / IDLE /
MISSING plus the raw signals (last_step, event_mtime_age_sec) that the live
client uses to upgrade to RUNNING/STALE across polls.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

import webui.rl_dashboard_runs as runs
from stom_rl import rl_events as ev


def _write_events(run_dir: Path, rows, *, age_sec: float = 0.0, name="rl_live_events.jsonl"):
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / name
    path.write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""), encoding="utf-8")
    if age_sec:
        t = time.time() - age_sec
        os.utime(path, (t, t))
    return path


def test_missing_when_no_event_file(tmp_path):
    (tmp_path / "run").mkdir()
    lc = runs._run_lifecycle(tmp_path / "run")
    assert lc["status"] == ev.RUN_STATUS_MISSING
    assert lc["is_live"] is False
    assert lc["event_file"] is None and lc["last_step"] is None


def test_idle_when_event_file_empty(tmp_path):
    rd = tmp_path / "run_idle"
    _write_events(rd, [])
    lc = runs._run_lifecycle(rd)
    assert lc["status"] == ev.RUN_STATUS_IDLE
    assert lc["is_live"] is False
    assert lc["event_count"] == 0


def test_completed_for_old_train_stream(tmp_path):
    rd = tmp_path / "run_done"
    _write_events(
        rd,
        [{"global_step": i, "phase": "train", "source": "daily_rl_train"} for i in range(4)],
        age_sec=9999,
    )
    lc = runs._run_lifecycle(rd)
    assert lc["status"] == ev.RUN_STATUS_COMPLETED
    assert lc["is_live"] is False
    assert lc["last_step"] == 3
    assert lc["event_mtime_age_sec"] >= 9000
    assert lc["is_replay"] is False


def test_completed_snapshot_even_for_fresh_stream_never_live(tmp_path):
    # A fresh write cannot be confirmed RUNNING from a single read -> snapshot is
    # COMPLETED (non-LIVE); the live client upgrades to RUNNING via advancing.
    rd = tmp_path / "run_fresh"
    _write_events(rd, [{"global_step": 10, "phase": "eval_test", "source": "daily_rl_train"}], age_sec=0.0)
    lc = runs._run_lifecycle(rd)
    assert lc["is_live"] is False
    assert lc["status"] in (ev.RUN_STATUS_COMPLETED,)
    assert lc["last_step"] == 10


def test_replay_for_backtest_phase(tmp_path):
    rd = tmp_path / "run_replay"
    _write_events(rd, [{"global_step": 5, "phase": "backtest", "source": "gap_up_backtest"}])
    lc = runs._run_lifecycle(rd)
    assert lc["status"] == ev.RUN_STATUS_REPLAY
    assert lc["is_replay"] is True
    assert lc["is_live"] is False


def test_replay_detected_from_source_token(tmp_path):
    rd = tmp_path / "run_replay_src"
    _write_events(rd, [{"global_step": 2, "phase": "eval", "source": "gap_up_backtest_publish"}])
    assert runs._run_lifecycle(rd)["status"] == ev.RUN_STATUS_REPLAY


def test_snapshot_is_never_live_across_all_states(tmp_path):
    (tmp_path / "m").mkdir()
    _write_events(tmp_path / "i", [])
    _write_events(tmp_path / "c", [{"global_step": 1, "phase": "train"}], age_sec=9999)
    _write_events(tmp_path / "r", [{"global_step": 1, "phase": "backtest"}])
    for name in ("m", "i", "c", "r"):
        assert runs._run_lifecycle(tmp_path / name)["is_live"] is False


def test_lifecycle_exposes_poll_interval_for_client(tmp_path):
    rd = tmp_path / "run"
    _write_events(rd, [{"global_step": 1, "phase": "train"}], age_sec=1.0)
    lc = runs._run_lifecycle(rd)
    assert lc["poll_interval_seconds"] == runs.DEFAULT_POLL_INTERVAL_SECONDS
    # raw signals the client needs to derive RUNNING/STALE across polls
    assert set(["last_step", "event_mtime_age_sec", "event_count", "is_replay"]).issubset(lc)


def test_run_record_payload_carries_lifecycle(tmp_path, monkeypatch):
    rd = tmp_path / "stom_run"
    _write_events(rd, [{"global_step": 7, "phase": "train", "source": "daily_rl_train"}], age_sec=9999)
    record = runs._run_record(rd)
    assert "lifecycle" in record
    assert record["lifecycle"]["status"] == ev.RUN_STATUS_COMPLETED
    assert record["lifecycle"]["is_live"] is False


def test_corrupt_last_step_does_not_crash(tmp_path):
    rd = tmp_path / "run_bad_step"
    _write_events(rd, [{"global_step": "not-an-int", "phase": "train"}], age_sec=9999)
    lc = runs._run_lifecycle(rd)
    assert lc["last_step"] is None
    assert lc["status"] == ev.RUN_STATUS_COMPLETED
