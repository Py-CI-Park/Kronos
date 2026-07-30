from __future__ import annotations

import json
from pathlib import Path

from stom_rl.rl_discovery.d5r_runner import run_d5r_diagnostic

ROOT = Path(__file__).resolve().parents[1]


def test_d5r_diagnostic_run_terminalizes_the_exact_source_matrix(tmp_path: Path) -> None:
    run_dir = run_d5r_diagnostic(ROOT, run_root=tmp_path, run_id="d5r-diagnostic")

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    receipt = json.loads((run_dir / "terminal_receipt.json").read_text(encoding="utf-8"))
    assert summary["status"] == "COMPLETE"
    assert summary["source_unit_count"] == 10
    assert summary["episode_count"] == 573
    assert len(summary["units"]) == 10
    assert summary["d5_verdict_unchanged"] == "D5_FULL_TRAIN_COST_NOT_CONFIRMED"
    assert summary["fresh_oos"] == "NOT_RUN_NO_READ"
    assert receipt["artifact_manifest_sha256"]
    assert receipt["verdict"] == summary["verdict"]
