import json
from pathlib import Path

import pytest

from stom_rl.rl_discovery.d2_custody import D2CustodyError
from stom_rl.rl_discovery.d5s_execution import D5SProfile
from stom_rl.rl_discovery.d5s_runner import run_d5s


def test_d5s_early_failure_writes_terminal_no_go_receipt(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"

    with pytest.raises(D2CustodyError):
        _ = run_d5s(
            tmp_path,
            run_root=run_root,
            run_id="early-failure",
            profile=D5SProfile.SMOKE,
        )

    receipt = json.loads(
        (run_root / "early-failure" / "terminal_receipt.json").read_text(encoding="utf-8")
    )
    assert receipt["status"] == "FAILED"
    assert receipt["verdict"] == "NO_GO"
    assert receipt["fresh_oos"] == "NOT_RUN_NO_READ"
