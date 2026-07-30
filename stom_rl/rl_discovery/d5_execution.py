"""Immutable D5 Smoke and Primary DQN matrix execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d3_contract import D3PolicyArmId
from stom_rl.rl_discovery.d3_env import D3Representation
from stom_rl.rl_discovery.d3_training import (
    D3Metrics,
    evaluate_d3_model,
    shuffled_d3_episodes,
)
from stom_rl.rl_discovery.d4_contract import D4AlgorithmArmId, D4RewardArmId
from stom_rl.rl_discovery.d4_training import D4TrainingConfig, train_d4_model
from stom_rl.rl_discovery.d5_approval import approve_d5_smoke, primary_custody_signature
from stom_rl.rl_discovery.d5_gates import D5Outcome, evaluate_d5_gate
from stom_rl.rl_discovery.d5_inputs import D5InputBundle, load_d5_inputs
from stom_rl.rl_discovery.storage import (
    RunDirectoryGuard,
    artifact_manifest_sha256,
)


class D5RunProfile(StrEnum):
    SMOKE = "SMOKE"
    PRIMARY = "PRIMARY"


@dataclass(frozen=True, slots=True)
class D5ModelRow:
    algorithm_arm: str
    algorithm_family: str
    rl_claim_allowed: bool
    reward_arm: str
    seed: int
    rl_timesteps: int
    training_round_trip_cost_bp: int
    fit_23bp: D3Metrics
    native_23bp: D3Metrics
    native_0bp: D3Metrics


def execute_d5(
    repo_root: Path,
    run_dir: Path,
    *,
    run_guard: RunDirectoryGuard,
    profile: D5RunProfile,
    approved_smoke: Path | None,
    approval_key: bytes | None,
) -> Path:
    """Execute preregistered D5 units into one immutable run directory."""

    bundle = load_d5_inputs(repo_root)
    run_dir = run_guard.verify()
    if profile is D5RunProfile.PRIMARY and (
        approval_key is None or len(approval_key) < 32
    ):
        raise PermissionError("D5 Primary requires KRONOS_D5_APPROVAL_KEY_HEX")
    approved_name = (
        approve_d5_smoke(
            approved_smoke,
            run_root=run_dir.parent,
            prereg_sha=bundle.prereg_sha256,
            episode_sha=bundle.episode_sha256,
            approval_key=approval_key,
        )
        if profile is D5RunProfile.PRIMARY
        else None
    )
    _ = run_guard.publish_bytes(bundle.prereg_bytes, "inputs", "prereg.json")
    _ = run_guard.publish_bytes(bundle.episode_bytes, "inputs", "episodes.json")
    representation = D3Representation.for_arm(D3PolicyArmId.TOP5_CONTEXT_4X)
    seeds = (
        bundle.prereg.seeds
        if profile is D5RunProfile.PRIMARY
        else bundle.prereg.smoke.seeds
    )
    timesteps = (
        bundle.prereg.algorithm.training_steps
        if profile is D5RunProfile.PRIMARY
        else bundle.prereg.smoke.rl_timesteps
    )
    outcomes: list[D5Outcome] = []
    rows: list[D5ModelRow] = []
    for reward in D4RewardArmId:
        for seed in seeds:
            fit_episodes = (
                bundle.episodes
                if reward is D4RewardArmId.NATIVE
                else shuffled_d3_episodes(bundle.episodes, seed=seed)
            )
            trained = train_d4_model(
                fit_episodes,
                representation=representation,
                config=D4TrainingConfig(
                    D4AlgorithmArmId.DQN_DISCRETE,
                    seed,
                    timesteps,
                    0,
                    cost_bp=bundle.prereg.costs.training_round_trip_bp,
                ),
            )
            model_arm = f"C_DQN_DISCRETE__{reward.value}"
            with run_guard.locked_parent(
                "models",
                model_arm,
                f"seed-{seed}",
                exclusive_leaf=True,
            ) as model_dir:
                trained.policy.save(model_dir / "model")
            fit, fit_events = evaluate_d3_model(
                trained.policy,
                fit_episodes,
                representation=representation,
                seed=seed,
                cost_bp=23,
            )
            native_cost, native_cost_events = evaluate_d3_model(
                trained.policy,
                bundle.episodes,
                representation=representation,
                seed=seed,
                cost_bp=23,
            )
            native_zero, native_zero_events = evaluate_d3_model(
                trained.policy,
                bundle.episodes,
                representation=representation,
                seed=seed,
                cost_bp=0,
            )
            outcome = D5Outcome(reward, seed, fit, native_cost, native_zero)
            row = D5ModelRow(
                "C_DQN_DISCRETE",
                "DQN",
                True,
                reward.value,
                seed,
                timesteps,
                23,
                fit,
                native_cost,
                native_zero,
            )
            outcomes.append(outcome)
            rows.append(row)
            _ = run_guard.publish_bytes(
                canonical_json_bytes(
                    {
                        **asdict(row),
                        "events": {
                            "fit_23bp": fit_events,
                            "native_23bp": native_cost_events,
                            "native_0bp": native_zero_events,
                        },
                    }
                ),
                "outcomes",
                reward.value,
                f"seed-{seed}.json",
            )
            print(
                (
                    f"[{profile.value}] C_DQN_DISCRETE/{reward.value}/seed-{seed} "
                    + f"fit23={fit.reward_ratio:.3f} native23={native_cost.reward_ratio:.3f}"
                ),
                flush=True,
            )
    return _finish_run(
        run_guard,
        profile,
        bundle,
        tuple(outcomes),
        tuple(rows),
        approved_name,
        approval_key,
    )


def _finish_run(
    run_guard: RunDirectoryGuard,
    profile: D5RunProfile,
    bundle: D5InputBundle,
    outcomes: tuple[D5Outcome, ...],
    rows: tuple[D5ModelRow, ...],
    approved_smoke: str | None,
    approval_key: bytes | None,
) -> Path:
    run_dir = run_guard.verify()
    gate = (
        evaluate_d5_gate(outcomes, thresholds=bundle.prereg.gate)
        if profile is D5RunProfile.PRIMARY
        else None
    )
    summary = {
        "schema_version": "kronos.rl-discovery.d5.result.v1",
        "research_lane": "rl_discovery",
        "experiment_id": bundle.prereg.experiment_id,
        "profile": profile.value,
        "status": "COMPLETE",
        "verdict": "SMOKE_COMPLETE" if gate is None else gate.verdict,
        "gate": None if gate is None else asdict(gate),
        "models": [asdict(row) for row in rows],
        "input_hashes": bundle.input_hashes,
        "prereg_sha256": bundle.prereg_sha256,
        "episode_snapshot_sha256": bundle.episode_sha256,
        "approved_smoke": approved_smoke,
        "reused_validation": "NOT_RUN_NO_READ",
        "fresh_oos": "NOT_RUN_NO_READ",
        "promotion_allowed": False,
        "profitability_claim_allowed": False,
        "live_broker_order_allowed": False,
        "primary_round_trip_cost_bp": 23,
        "diagnostic_round_trip_cost_bp": 0,
    }
    _ = run_guard.publish_bytes(canonical_json_bytes(summary), "summary.json")
    with run_guard.locked() as locked_dir:
        digest = artifact_manifest_sha256(
            locked_dir,
            excluded_relative_paths=frozenset({"terminal_receipt.json"}),
        )
    receipt = {
        "profile": profile.value,
        "status": "COMPLETE",
        "verdict": summary["verdict"],
        "prereg_sha256": bundle.prereg_sha256,
        "episode_snapshot_sha256": bundle.episode_sha256,
        "artifact_manifest_sha256": digest,
        "fresh_oos": "NOT_RUN_NO_READ",
        "live_broker_order_allowed": False,
    }
    if (
        profile is D5RunProfile.PRIMARY
        and approval_key is not None
        and approved_smoke is not None
    ):
        receipt["primary_custody_hmac_sha256"] = primary_custody_signature(
            approval_key,
            run_name=run_dir.name,
            prereg_sha=bundle.prereg_sha256,
            episode_sha=bundle.episode_sha256,
            manifest_sha=digest,
            approved_smoke=approved_smoke,
        )
    _ = run_guard.publish_bytes(canonical_json_bytes(receipt), "terminal_receipt.json")
    return run_guard.verify()
