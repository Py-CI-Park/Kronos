import json
from pathlib import Path

import pytest

from stom_rl.rl_discovery.d2_custody import D2CustodyError
from stom_rl.rl_discovery.d6_runner import run_d6


def test_d6_early_failure_writes_terminal_no_go_receipt(tmp_path: Path) -> None:
    # Given
    run_root = tmp_path / "runs"

    # When / Then
    with pytest.raises(D2CustodyError):
        _ = run_d6(tmp_path, run_root=run_root, run_id="early-failure")

    receipt = json.loads(
        (run_root / "early-failure" / "terminal_receipt.json").read_text(encoding="utf-8")
    )
    assert receipt["status"] == "FAILED"
    assert receipt["verdict"] == "NO_GO"
    assert receipt["fresh_oos"] == "NOT_RUN_NO_READ"
