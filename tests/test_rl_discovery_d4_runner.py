from __future__ import annotations

import json

import pytest

from stom_rl.rl_discovery import d4_runner
from stom_rl.rl_discovery.d4_execution import D4RunProfile
from stom_rl.rl_discovery.d4_runner import run_d4


def test_d4_direct_early_failure_writes_a_terminal_no_go_receipt(tmp_path) -> None:
    # Given/When: D4 starts in a repository without its committed preregistration.
    with pytest.raises(FileNotFoundError):
        run_d4(tmp_path, profile=D4RunProfile.SMOKE, run_id="early-failure")

    # Then: the run is terminalized and Fresh OOS remains sealed.
    receipt = json.loads(
        (tmp_path / "webui/rl_runs/rl_discovery/early-failure/terminal_receipt.json").read_text()
    )
    assert receipt["status"] == "FAILED"
    assert receipt["verdict"] == "NO_GO"
    assert receipt["fresh_oos"] == "NOT_RUN_NO_READ"


def test_d4_interrupt_terminalizes_the_run(tmp_path, monkeypatch) -> None:
    # Given: execution is interrupted after immutable directory creation.
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt("operator stop")

    monkeypatch.setattr(d4_runner, "execute_d4", interrupt)

    # When: the public runner receives the interrupt.
    with pytest.raises(KeyboardInterrupt):
        run_d4(tmp_path, profile=D4RunProfile.SMOKE, run_id="interrupted")

    # Then: interruption is explicit rather than an ambiguous partial run.
    receipt = json.loads(
        (tmp_path / "webui/rl_runs/rl_discovery/interrupted/terminal_receipt.json").read_text()
    )
    assert receipt["status"] == "FAILED"
    assert receipt["fresh_oos"] == "NOT_RUN_NO_READ"
