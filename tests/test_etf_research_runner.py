import json
import sqlite3
from pathlib import Path

from stom_rl.etf_research.runner import FoundationRunConfig, run_foundation, write_foundation_receipt


def _write_canary_database(path: Path) -> None:
    codes = ("069500", "102110", "091160", "091170")
    with sqlite3.connect(path) as connection:
        for code_index, code in enumerate(codes):
            connection.execute(
                f'CREATE TABLE "A{code}" (date INTEGER, open REAL, high REAL, low REAL, close REAL, volume REAL)'
            )
            rows = []
            for day in range(180):
                base = 100.0 + code_index * 3.0 + day * (0.12 - code_index * 0.02)
                rows.append((20260000 + day, base, base + 1.0, base - 1.0, base + 0.4, 1000.0 + day))
            connection.executemany(f'INSERT INTO "A{code}" VALUES (?, ?, ?, ?, ?, ?)', rows)


def test_foundation_runner_executes_diagnostics_but_keeps_q3_locked(tmp_path: Path) -> None:
    # Given: local canary OHLCV without point-in-time custody metadata.
    database = tmp_path / "daily.db"
    _write_canary_database(database)
    config = FoundationRunConfig.registered(database)

    # When: Q1, Q2-A, and Q2-B foundation diagnostics execute.
    receipt = run_foundation(config)

    # Then: diagnostics are recorded but Q1 blocks PPO promotion.
    assert receipt.data_audit.verdict == "BLOCKED_DATA_CUSTODY"
    assert receipt.signal_floor.evidence_scope == "DIAGNOSTIC_ONLY"
    assert receipt.synthetic_gate.verdict == "PASS_SYNTHETIC_STATEFUL_MDP"
    assert receipt.overall_verdict == "BLOCKED_Q1_DATA_CUSTODY"
    assert receipt.q3_ppo_allowed is False


def test_foundation_receipt_is_written_as_stable_json(tmp_path: Path) -> None:
    # Given: a completed deterministic foundation run.
    database = tmp_path / "daily.db"
    output = tmp_path / "receipt.json"
    _write_canary_database(database)
    receipt = run_foundation(FoundationRunConfig.registered(database))

    # When: the artifact writer persists its receipt.
    write_foundation_receipt(receipt, output)

    # Then: the JSON exposes the fail-closed decision and preserves code strings.
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["overall_verdict"] == "BLOCKED_Q1_DATA_CUSTODY"
    assert payload["q3_ppo_allowed"] is False
    assert payload["data_audit"]["codes"][0] == "069500"

