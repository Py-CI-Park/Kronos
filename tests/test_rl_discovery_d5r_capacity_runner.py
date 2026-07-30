import json
from pathlib import Path

import pytest

from stom_rl.rl_discovery.d2_custody import D2CustodyError
from stom_rl.rl_discovery.d5r_capacity_runner import (
    D5RCapacityProfile,
    _registered_schedule,
    run_d5r_capacity,
)


def test_d5r_capacity_profiles_freeze_smoke_and_primary_matrix() -> None:
    assert _registered_schedule(D5RCapacityProfile.SMOKE) == (
        ("NATIVE", "SHUFFLED"),
        (0,),
        (2048,),
    )
    assert _registered_schedule(D5RCapacityProfile.PRIMARY) == (
        ("NATIVE", "SHUFFLED"),
        (0, 1, 2),
        (400_000, 800_000),
    )


def test_d5r_capacity_early_failure_writes_terminal_no_go_receipt(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"

    with pytest.raises(D2CustodyError):
        _ = run_d5r_capacity(
            tmp_path,
            run_root=run_root,
            run_id="early-failure",
            profile=D5RCapacityProfile.SMOKE,
        )

    receipt = json.loads(
        (run_root / "early-failure" / "terminal_receipt.json").read_text(encoding="utf-8")
    )
    assert receipt["status"] == "FAILED"
    assert receipt["verdict"] == "NO_GO"
    assert receipt["fresh_oos"] == "NOT_RUN_NO_READ"
