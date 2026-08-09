"""Behavior coverage for the lightweight V6 research catalog."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from webui.v6_research_catalog import ResearchQuery, discover_runs, filter_runs


def _write_summary(directory: Path, payload: dict[str, str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "rl_live_summary.json").write_text(json.dumps(payload), encoding="utf-8")


def test_discover_runs_preserves_recorded_status_and_nested_v6_identity(tmp_path: Path) -> None:
    # Given
    _write_summary(
        tmp_path / "stom_orderbook_dqn_smoke",
        {"status": "NO_GO", "algorithm": "DQN", "dataset_id": "orderbook-2025"},
    )
    nested = tmp_path / "v6_daily_h1" / "type1-close-20260803-005"
    nested.mkdir(parents=True)
    (nested / "dataset_manifest.json").write_text(
        json.dumps({"state": "BLOCKED", "dataset_id": "type1-close-20260803-005"}),
        encoding="utf-8",
    )

    # When
    rows = discover_runs(tmp_path)

    # Then
    assert [row.run_id for row in rows] == [
        "v6_daily_h1/type1-close-20260803-005",
        "stom_orderbook_dqn_smoke",
    ]
    orderbook = rows[1]
    assert orderbook.status == "NO_GO"
    assert orderbook.algorithm == "DQN"
    assert orderbook.dataset_id == "orderbook-2025"
    assert orderbook.lane == "orderbook"
    assert orderbook.source_file == "rl_live_summary.json"


def test_discover_runs_keeps_corrupt_or_missing_summaries_visible(tmp_path: Path) -> None:
    # Given
    corrupt = tmp_path / "daily_ohlcv_broken"
    corrupt.mkdir()
    (corrupt / "summary.json").write_text("{broken", encoding="utf-8")
    recorded = tmp_path / "rl_discovery"
    recorded.mkdir()
    (recorded / "actions.csv").write_text("action\n0\n", encoding="utf-8")

    # When
    rows = discover_runs(tmp_path)

    # Then
    assert {row.status for row in rows} == {"CORRUPT_EVIDENCE", "RECORDED"}
    assert {row.run_id for row in rows} == {"daily_ohlcv_broken", "rl_discovery"}


def test_discover_runs_prefers_official_verdict_and_supplements_algorithm(tmp_path: Path) -> None:
    # Given
    run = tmp_path / "stom_orderbook_dqn_smoke"
    _write_summary(run, {"algorithms": {"orderbook_dqn": 4352}})
    (run / "orderbook_oos_verdict.json").write_text(
        json.dumps({"verdict": "NO-GO", "model_mean_pct": -4.12}),
        encoding="utf-8",
    )

    # When
    row = discover_runs(tmp_path)[0]

    # Then
    assert row.status == "NO-GO"
    assert row.algorithm == "orderbook_dqn"
    assert row.source_file == "orderbook_oos_verdict.json"


def test_discover_runs_uses_valid_verdict_when_another_evidence_file_is_corrupt(tmp_path: Path) -> None:
    # Given
    run = tmp_path / "daily_close_cql"
    run.mkdir()
    (run / "rl_live_summary.json").write_text("{broken", encoding="utf-8")
    (run / "daily_close_verdict.json").write_text(
        json.dumps({"verdict": "NO_GO", "algorithm": "CQL"}),
        encoding="utf-8",
    )

    # When
    row = discover_runs(tmp_path)[0]

    # Then
    assert row.status == "NO_GO"
    assert row.algorithm == "CQL"
    assert row.source_file == "daily_close_verdict.json"


def test_discover_runs_accepts_utf8_bom_from_windows_research_artifacts(tmp_path: Path) -> None:
    # Given
    run = tmp_path / "stom_orderbook_dqn_windows"
    run.mkdir()
    (run / "orderbook_oos_verdict.json").write_text(
        json.dumps({"verdict": "NO-GO", "algorithm": "orderbook_dqn"}),
        encoding="utf-8-sig",
    )

    # When
    row = discover_runs(tmp_path)[0]

    # Then
    assert row.status == "NO-GO"
    assert row.algorithm == "orderbook_dqn"


def test_discover_runs_expands_generic_group_into_direct_child_runs(tmp_path: Path) -> None:
    # Given
    grouped_run = tmp_path / "daily_close_slot_train" / "policy_2026_08_07"
    _write_summary(
        grouped_run,
        {"status": "NO_GO", "algorithm": "CQL", "dataset_id": "daily-close-v3"},
    )

    # When
    rows = discover_runs(tmp_path)

    # Then
    assert [row.run_id for row in rows] == ["daily_close_slot_train/policy_2026_08_07"]
    assert rows[0].artifact_count == 1


def test_discover_runs_keeps_child_runs_when_group_has_a_direct_index_file(tmp_path: Path) -> None:
    # Given
    group = tmp_path / "daily_ohlcv_scenario_batches"
    group.mkdir()
    (group / "index.json").write_text("{}", encoding="utf-8")
    _write_summary(group / "scenario_001", {"status": "RECORDED", "algorithm": "RULE"})

    # When
    rows = discover_runs(tmp_path)

    # Then
    assert {row.run_id for row in rows} == {
        "daily_ohlcv_scenario_batches",
        "daily_ohlcv_scenario_batches/scenario_001",
    }


def test_discover_runs_counts_bounded_nested_model_checkpoints(tmp_path: Path) -> None:
    # Given
    run = tmp_path / "daily_market_cql"
    _write_summary(run, {"status": "NO_GO", "algorithm": "CQL"})
    model_dir = run / "models" / "CQL"
    model_dir.mkdir(parents=True)
    (model_dir / "seed-0.kq").write_bytes(b"KQ01")

    # When
    row = discover_runs(tmp_path)[0]

    # Then
    assert row.artifact_count == 2


@pytest.mark.skipif(os.name != "nt", reason="Windows junction boundary")
def test_discover_runs_rejects_junction_outside_research_root(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    outside = tmp_path / "outside"
    root.mkdir()
    _write_summary(outside, {"status": "SECRET_STATUS", "algorithm": "LEAK"})
    junction = root / "daily_junction_escape"
    created = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(outside)],
        check=False,
        capture_output=True,
        text=True,
    )
    if created.returncode != 0:
        pytest.skip("junction creation unavailable")
    try:
        assert discover_runs(root) == ()
    finally:
        junction.rmdir()


def test_filter_runs_applies_lane_status_query_and_pagination(tmp_path: Path) -> None:
    # Given
    for index in range(4):
        _write_summary(
            tmp_path / f"daily_close_{index}",
            {"status": "NO_GO" if index < 3 else "COMPLETE", "algorithm": "CQL"},
        )
    rows = discover_runs(tmp_path)
    query = ResearchQuery(search="close", lane="daily_close", status="NO_GO", page=2, page_size=2)

    # When
    page = filter_runs(rows, query)

    # Then
    assert page.total == 3
    assert page.page == 2
    assert page.page_size == 2
    assert len(page.items) == 1


def test_filter_runs_matches_generic_no_go_status_family(tmp_path: Path) -> None:
    _write_summary(
        tmp_path / "daily_market_cql",
        {"status": "NO_GO_HISTORICAL_ECONOMIC_GATE", "algorithm": "CQL"},
    )

    page = filter_runs(discover_runs(tmp_path), ResearchQuery(status="NO_GO"))

    assert [row.run_id for row in page.items] == ["daily_market_cql"]
