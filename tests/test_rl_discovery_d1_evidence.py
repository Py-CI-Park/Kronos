from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from stom_rl.rl_discovery.d1_contract import D1ArmId, load_d1_prereg_bytes
from stom_rl.rl_discovery.d1_evidence import write_d1_terminal
from stom_rl.rl_discovery.d1_gates import D1GateResult, D1Outcome
from stom_rl.rl_discovery.gates import RunProfile
from stom_rl.rl_discovery.storage import JsonValue


def test_d1_terminal_dashboard_rows_preserve_seed_and_safety_boundary(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    prereg = load_d1_prereg_bytes(
        (repo_root / "docs" / "kronos_rl_discovery_type2_d1_prereg_2026-07-28.json").read_bytes()
    )
    outcome = D1Outcome(
        arm=D1ArmId.BINARY_NATIVE,
        seed=2,
        training_timesteps=16_384,
        economic_reward_ratio=1.0,
        initial_decision_accuracy=1.0,
        invalid_action_count=0,
        block_count=0,
        no_fill_count=0,
        dominant_initial_action_rate=0.75,
    )
    gate = D1GateResult(
        status="PRIMARY_COMPLETE",
        verdict="D1_ACTION_REWARD_CONFIRMED",
        reasons=("test fixture",),
        smoke_pass=True,
        promotion_allowed=False,
        profitability_claim_allowed=False,
        fresh_oos="NOT_RUN_NO_READ",
    )

    write_d1_terminal(
        tmp_path,
        prereg=prereg,
        profile=RunProfile.PRIMARY,
        outcomes=(outcome,),
        gate=gate,
        prereg_sha="a" * 64,
        fixture_sha="b" * 64,
        smoke_reference="approved-smoke",
    )

    payload = cast(
        dict[str, JsonValue],
        json.loads((tmp_path / "sb3_smoke_summary.json").read_text(encoding="utf-8")),
    )
    models = cast(list[dict[str, JsonValue]], payload["models"])
    summary = cast(dict[str, JsonValue], payload["summary"])
    receipt = cast(
        dict[str, JsonValue],
        json.loads((tmp_path / "terminal_receipt.json").read_text(encoding="utf-8")),
    )

    assert models[0]["seed"] == 2
    assert summary["approved_smoke_run"] == "approved-smoke"
    assert receipt["fresh_oos"] == "NOT_RUN_NO_READ"
    assert receipt["promotion_allowed"] is False
    assert receipt["profitability_claim_allowed"] is False
