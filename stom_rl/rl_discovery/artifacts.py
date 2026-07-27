"""Type2 discovery dashboard artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from stom_rl.rl_discovery.gates import ArmOutcome, GateResult, RunProfile


def _write_json(path: Path, payload: object) -> None:
    _ = path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_dashboard_artifact(
    run_dir: Path,
    *,
    experiment_id: str,
    profile: RunProfile | str,
    outcomes: tuple[ArmOutcome, ...],
    gate: GateResult,
    prereg_sha256: str,
) -> None:
    """Write an immutable dashboard-compatible discovery evidence bundle."""

    if run_dir.exists():
        raise FileExistsError(f"discovery run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    selected_profile = RunProfile(profile)
    models = [
        {
            "model": f"{outcome.arm}/seed-{outcome.seed}",
            "algorithm": outcome.arm,
            "training_timesteps": outcome.training_timesteps,
            "oracle_reward_ratio": outcome.oracle_reward_ratio,
            "exact_basket_accuracy": outcome.exact_basket_accuracy,
            "invalid_action_count": outcome.invalid_action_count,
            "block_count": outcome.block_count,
            "no_fill_count": outcome.no_fill_count,
            "dominant_action_rate": outcome.dominant_action_rate,
            "shuffled_reward": outcome.shuffled_reward,
        }
        for outcome in outcomes
    ]
    summary = {
        "research_lane": "rl_discovery",
        "experiment_id": experiment_id,
        "profile": selected_profile.value,
        "status": gate.status,
        "verdict": gate.verdict,
        "reasons": list(gate.reasons),
        "fresh_oos": gate.fresh_oos,
        "type1_outcome": "COMPLETE_NO_GO",
        "promotion_allowed": gate.promotion_allowed,
        "profitability_claim_allowed": gate.profitability_claim_allowed,
        "prereg_sha256": prereg_sha256,
        "arm_count": len({outcome.arm for outcome in outcomes}),
        "seed_count": len({outcome.seed for outcome in outcomes}),
    }
    _write_json(run_dir / "sb3_smoke_summary.json", {"summary": summary, "models": models})
    _write_json(run_dir / "outcomes.json", models)
    _write_json(
        run_dir / "terminal_receipt.json",
        {
            "experiment_id": experiment_id,
            "profile": selected_profile.value,
            "status": gate.status,
            "verdict": gate.verdict,
            "promotion_allowed": gate.promotion_allowed,
            "profitability_claim_allowed": gate.profitability_claim_allowed,
            "fresh_oos": gate.fresh_oos,
            "prereg_sha256": prereg_sha256,
        },
    )
