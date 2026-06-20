"""Tests for read-only forward/paper evidence ledger writer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stom_rl.factory.forward_ledger import (
    ForwardLedgerConfig,
    ForwardLedgerError,
    append_forward_records,
    build_forward_records,
    load_edge_rows,
    write_forward_ledger,
)


def _edge_ledger(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "symbol": "000250",
                        "session": "20260105",
                        "p_win": 0.61,
                        "edge_pct": 0.4,
                        "decision": "TAKE",
                        "net_pct_23bp": 1.2,
                    },
                    {
                        "symbol": "035720",
                        "session": "20260105",
                        "p_win": 0.31,
                        "edge_pct": -0.2,
                        "decision": "SKIP",
                        "net_pct_23bp": -0.5,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def test_load_edge_rows_validates_decision(tmp_path: Path) -> None:
    path = tmp_path / "edge.json"
    path.write_text(json.dumps({"rows": [{"symbol": "000250", "session": "20260105", "p_win": 0.1, "edge_pct": 0.0, "decision": "HOLD"}]}), encoding="utf-8")
    with pytest.raises(ForwardLedgerError, match="invalid decision"):
        load_edge_rows(path)


def test_build_forward_records_preserves_codes_and_resolved_outcomes(tmp_path: Path) -> None:
    edge = _edge_ledger(tmp_path / "edge.json")
    records = build_forward_records(
        ForwardLedgerConfig(
            edge_ledger_path=edge,
            output_path=tmp_path / "forward.jsonl",
            run_id="run_a",
            model_version="run_a@summary",
            fill_assumption="realized_full",
            recorded_at_utc="2026-06-11T00:00:00+00:00",
        )
    )

    assert records[0]["record_id"] == "run_a:20260105:000250"
    assert records[0]["code"] == "000250"
    assert records[0]["outcome_status"] == "resolved"
    assert records[0]["realized_outcome_pct"] == 1.2
    assert records[0]["baseline_outcome_pct"] == 1.2
    assert records[0]["cost_bps"] == 23.0
    assert records[0]["schema_version"] == 1


def test_build_forward_records_can_write_pending(tmp_path: Path) -> None:
    edge = _edge_ledger(tmp_path / "edge.json")
    records = build_forward_records(
        ForwardLedgerConfig(
            edge_ledger_path=edge,
            output_path=tmp_path / "forward.jsonl",
            run_id="run_a",
            model_version="run_a@summary",
            fill_assumption="realized_full",
            include_outcomes=False,
        )
    )
    assert {record["outcome_status"] for record in records} == {"pending"}
    assert all(record["realized_outcome_pct"] is None for record in records)


def test_append_forward_records_skips_duplicate_ids(tmp_path: Path) -> None:
    output = tmp_path / "forward.jsonl"
    records = [
        {"record_id": "a", "outcome_status": "pending", "schema_version": 1},
        {"record_id": "a", "outcome_status": "resolved", "schema_version": 1},
        {"record_id": "b", "outcome_status": "resolved", "schema_version": 1},
    ]
    first = append_forward_records(output, records)
    second = append_forward_records(output, records)

    assert first["appended_count"] == 2
    assert first["skipped_duplicate_count"] == 1
    assert second["appended_count"] == 0
    assert second["skipped_duplicate_count"] == 3
    assert len(output.read_text(encoding="utf-8").splitlines()) == 2


def test_write_forward_ledger_writes_jsonl_and_summary(tmp_path: Path) -> None:
    edge = _edge_ledger(tmp_path / "edge.json")
    output = tmp_path / "forward" / "ledger.jsonl"
    summary = write_forward_ledger(
        ForwardLedgerConfig(
            edge_ledger_path=edge,
            output_path=output,
            run_id="run_a",
            model_version="run_a@summary",
            fill_assumption="slgap_full",
            output_root=tmp_path / "forward",
        )
    )

    assert output.is_file()
    assert Path(summary["summary_path"]).is_file()
    assert summary["appended_count"] == 2
    assert summary["status_counts"] == {"resolved": 2}
    assert summary["duplicate_policy"] == "skip_existing_record_id"
    assert "no orders" in summary["guardrail"]
    assert summary["output_root"] == str(tmp_path / "forward")


def test_write_forward_ledger_rejects_output_outside_root(tmp_path: Path) -> None:
    edge = _edge_ledger(tmp_path / "edge.json")
    with pytest.raises(ForwardLedgerError, match="output path must be under"):
        write_forward_ledger(
            ForwardLedgerConfig(
                edge_ledger_path=edge,
                output_path=tmp_path / "outside" / "ledger.jsonl",
                run_id="run_a",
                model_version="run_a@summary",
                fill_assumption="realized_full",
                output_root=tmp_path / "forward",
            )
        )
