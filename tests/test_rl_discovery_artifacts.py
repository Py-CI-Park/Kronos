from __future__ import annotations

import json
from pathlib import Path

from stom_rl.rl_discovery import artifacts, gates
from webui import rl_dashboard


def test_dashboard_artifact_is_visible_as_research_only_sb3_evidence(tmp_path: Path, monkeypatch) -> None:
    # Given
    result = gates.GateResult(
        status="SMOKE_COMPLETE",
        verdict="SMOKE_INCOMPLETE",
        reasons=("smoke profile cannot promote",),
        promotion_allowed=False,
        profitability_claim_allowed=False,
        fresh_oos="NOT_RUN_NO_READ",
    )
    outcomes = (
        gates.ArmOutcome(
            arm="A_PPO_ONLY",
            seed=0,
            training_timesteps=256,
            oracle_reward_ratio=0.25,
            exact_basket_accuracy=0.1,
            invalid_action_count=0,
            block_count=0,
            no_fill_count=0,
            dominant_action_rate=0.7,
            shuffled_reward=False,
        ),
    )
    run_dir = tmp_path / "type2-d0-smoke"

    # When
    artifacts.write_dashboard_artifact(
        run_dir,
        experiment_id="type2-d0-ppo-attribution-v0",
        profile="SMOKE",
        outcomes=outcomes,
        gate=result,
        prereg_sha256="a" * 64,
    )
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])
    runs = rl_dashboard.list_rl_runs(limit=10)

    # Then
    assert runs[0]["artifact_type"] == "sb3_smoke"
    assert runs[0]["summary"]["research_lane"] == "rl_discovery"
    assert runs[0]["summary"]["fresh_oos"] == "NOT_RUN_NO_READ"
    receipt = json.loads((run_dir / "terminal_receipt.json").read_text(encoding="utf-8"))
    assert receipt["promotion_allowed"] is False
