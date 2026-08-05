"""Behavior coverage for bounded V6 run telemetry."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from webui import v6_run_telemetry
from webui.v6_run_telemetry import discover_telemetry_runs, read_telemetry


def _event(step: int, *, reward: float | None = None, equity: float | None = None) -> str:
    return json.dumps(
        {
            "global_step": step,
            "phase": "train" if step < 10 else "eval",
            "reward": reward,
            "equity": equity,
            "loss": 1 / step,
            "exploration": 1 - (step / 20),
            "action_name": "buy" if step % 2 else "hold",
            "timestamp_utc": f"2026-08-05T00:00:{step:02d}+00:00",
        }
    )


def test_read_telemetry_preserves_observed_metrics_and_utf8_bom(tmp_path: Path) -> None:
    # Given
    run = tmp_path / "daily_close_dqn"
    run.mkdir()
    events = "\n".join((_event(1, reward=0.1, equity=1.0), "{broken", _event(2, reward=-0.2, equity=0.98)))
    (run / "rl_live_events.jsonl").write_text(events, encoding="utf-8-sig")

    # When
    snapshot = read_telemetry(run, limit=10, now=datetime(2026, 8, 5, tzinfo=timezone.utc))

    # Then
    assert [point.step for point in snapshot.points] == [1, 2]
    assert snapshot.points[1].reward == -0.2
    assert snapshot.points[1].equity == 0.98
    assert snapshot.invalid_lines == 1
    assert snapshot.sampling == "FULL_FILE"
    assert snapshot.follow_mode == "HISTORICAL_SNAPSHOT"


def test_read_telemetry_samples_head_and_tail_without_loading_middle(monkeypatch, tmp_path: Path) -> None:
    # Given
    run = tmp_path / "large_dqn"
    run.mkdir()
    (run / "rl_live_events.jsonl").write_text(
        "\n".join(_event(step, reward=float(step), equity=1 + step / 100) for step in range(1, 21)),
        encoding="utf-8",
    )
    monkeypatch.setattr(v6_run_telemetry, "HALF_SCAN_BYTES", 220)

    # When
    snapshot = read_telemetry(run, limit=6)

    # Then
    assert snapshot.sampling == "HEAD_TAIL_SAMPLE"
    assert snapshot.points[0].step == 1
    assert snapshot.points[-1].step == 20
    assert len(snapshot.points) <= 6


def test_discover_telemetry_runs_lists_only_direct_recorded_event_files(tmp_path: Path) -> None:
    # Given
    for name in ("run_a", "run_b"):
        directory = tmp_path / name
        directory.mkdir()
        (directory / "rl_live_events.jsonl").write_text(_event(1), encoding="utf-8")
        (directory / "run_verdict.json").write_text(
            json.dumps({"verdict": "NO-GO", "algorithm": "DQN"}),
            encoding="utf-8",
        )
    missing = tmp_path / "run_without_events"
    missing.mkdir()

    # When
    rows = discover_telemetry_runs(tmp_path)

    # Then
    assert {row.run_id for row in rows} == {"run_a", "run_b"}
    assert all(row.event_bytes > 0 for row in rows)
    assert all(row.status == "NO-GO" and row.algorithm == "DQN" for row in rows)
    assert all(row.lane == "other" for row in rows)
