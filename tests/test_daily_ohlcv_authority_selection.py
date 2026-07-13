"""Authority-aware latest-run selection tests for webui/daily_ohlcv_dashboard.py.

Covers _run_authority_sort_key / _latest_run_dir / _latest_artifact_dir:
  - explicit authoritative manifest beats a newer non-authoritative one
  - a newer disposable smoke run with no authority fields never beats an
    explicitly authoritative older run
  - backward-compat: with no authority fields anywhere, pure mtime wins
  - among equally-authoritative runs, status and completed_at break ties
  - malformed manifest JSON is treated as no-authority, never crashes
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import webui.daily_ohlcv_dashboard as daily_dashboard

REQUIRED_FILE = "rl_manifest.json"


def _make_run(
    root: Path,
    run_id: str,
    manifest: dict | None,
    *,
    mtime_offset: float,
    required_file: str = REQUIRED_FILE,
) -> Path:
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / required_file
    if manifest is None:
        manifest_path.write_text("{not-valid-json", encoding="utf-8")
    else:
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    ts = time.time() + mtime_offset
    os.utime(manifest_path, (ts, ts))
    return run_dir


def test_older_authoritative_run_beats_newer_non_authoritative_run(tmp_path, monkeypatch):
    root = tmp_path / "portfolio"
    monkeypatch.setattr(daily_dashboard, "DEFAULT_PORTFOLIO_ROOT", root)

    older_authoritative = _make_run(
        root,
        "full_run",
        {"authoritative": True, "status": "done", "stage": "full"},
        mtime_offset=-1000.0,
    )
    _make_run(
        root,
        "smoke_run",
        {"authoritative": False, "status": "running", "stage": "smoke"},
        mtime_offset=0.0,
    )

    selected = daily_dashboard._latest_run_dir(root, required_file=REQUIRED_FILE)

    assert selected == older_authoritative


def test_newer_disposable_smoke_without_authority_never_beats_authoritative_run(tmp_path, monkeypatch):
    root = tmp_path / "portfolio"
    monkeypatch.setattr(daily_dashboard, "DEFAULT_PORTFOLIO_ROOT", root)

    older_authoritative = _make_run(
        root,
        "full_run",
        {"authoritative": True, "status": "done"},
        mtime_offset=-500.0,
    )
    _make_run(root, "smoke_run", {}, mtime_offset=100.0)

    selected = daily_dashboard._latest_run_dir(root, required_file=REQUIRED_FILE)

    assert selected == older_authoritative


def test_no_authority_fields_falls_back_to_pure_mtime(tmp_path, monkeypatch):
    root = tmp_path / "prediction"
    monkeypatch.setattr(daily_dashboard, "DEFAULT_PREDICTION_ROOT", root)

    _make_run(root, "older", {"stage": "full"}, mtime_offset=-200.0, required_file="prediction_manifest.json")
    newer = _make_run(root, "newer", {"stage": "full"}, mtime_offset=0.0, required_file="prediction_manifest.json")

    selected = daily_dashboard._latest_run_dir(
        root, required_file="prediction_manifest.json"
    )

    assert selected == newer


def test_no_authority_fields_falls_back_to_pure_mtime_for_artifact_dir(tmp_path, monkeypatch):
    root = tmp_path / "artifact_root"
    root.mkdir(parents=True, exist_ok=True)

    older = root / "older"
    older.mkdir()
    older_manifest = older / "db_summary.json"
    older_manifest.write_text(json.dumps({"stage": "full"}), encoding="utf-8")
    older_ts = time.time() - 200.0
    os.utime(older_manifest, (older_ts, older_ts))

    newer = root / "newer"
    newer.mkdir()
    newer_manifest = newer / "db_summary.json"
    newer_manifest.write_text(json.dumps({"stage": "full"}), encoding="utf-8")
    newer_ts = time.time()
    os.utime(newer_manifest, (newer_ts, newer_ts))

    selected = daily_dashboard._latest_artifact_dir(root, required_file="db_summary.json")

    assert selected == newer


def test_completed_at_breaks_ties_between_equally_authoritative_done_runs(tmp_path, monkeypatch):
    root = tmp_path / "portfolio"
    monkeypatch.setattr(daily_dashboard, "DEFAULT_PORTFOLIO_ROOT", root)

    earlier_completion = _make_run(
        root,
        "completed_earlier",
        {"authoritative": False, "status": "done", "completed_at": "2026-07-01T00:00:00Z"},
        mtime_offset=0.0,
    )
    later_completion = _make_run(
        root,
        "completed_later",
        {"authoritative": False, "status": "done", "completed_at": "2026-07-05T00:00:00Z"},
        mtime_offset=-500.0,
    )

    selected = daily_dashboard._latest_run_dir(root, required_file=REQUIRED_FILE)

    assert selected == later_completion
    assert selected != earlier_completion


def test_status_done_beats_status_running_when_authority_equal(tmp_path, monkeypatch):
    root = tmp_path / "portfolio"
    monkeypatch.setattr(daily_dashboard, "DEFAULT_PORTFOLIO_ROOT", root)

    done_run = _make_run(
        root,
        "done_run",
        {"authoritative": False, "status": "done"},
        mtime_offset=-500.0,
    )
    _make_run(
        root,
        "running_run",
        {"authoritative": False, "status": "running"},
        mtime_offset=0.0,
    )

    selected = daily_dashboard._latest_run_dir(root, required_file=REQUIRED_FILE)

    assert selected == done_run


def test_malformed_manifest_candidate_does_not_crash_and_is_treated_as_no_authority(tmp_path, monkeypatch):
    root = tmp_path / "portfolio"
    monkeypatch.setattr(daily_dashboard, "DEFAULT_PORTFOLIO_ROOT", root)

    authoritative_run = _make_run(
        root,
        "authoritative_run",
        {"authoritative": True, "status": "done"},
        mtime_offset=-100.0,
    )
    _make_run(root, "malformed_run", None, mtime_offset=1000.0)

    selected = daily_dashboard._latest_run_dir(root, required_file=REQUIRED_FILE)

    assert selected == authoritative_run


def test_nested_authority_block_is_honored(tmp_path, monkeypatch):
    root = tmp_path / "portfolio"
    monkeypatch.setattr(daily_dashboard, "DEFAULT_PORTFOLIO_ROOT", root)

    nested_authoritative = _make_run(
        root,
        "nested_authoritative",
        {"authority": {"authoritative": True, "status": "done"}},
        mtime_offset=-300.0,
    )
    _make_run(
        root,
        "smoke_run",
        {"authoritative": False, "status": "running"},
        mtime_offset=0.0,
    )

    selected = daily_dashboard._latest_run_dir(root, required_file=REQUIRED_FILE)

    assert selected == nested_authoritative
