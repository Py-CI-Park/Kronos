"""Immutable D4 Smoke/Primary algorithm matrix execution."""

from __future__ import annotations

from dataclasses import asdict
from enum import StrEnum
from pathlib import Path

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d3_contract import D3PolicyArmId
from stom_rl.rl_discovery.d3_env import D3Representation
from stom_rl.rl_discovery.d3_training import evaluate_d3_model, shuffled_d3_episodes
from stom_rl.rl_discovery.d4_approval import approve_d4_smoke, primary_custody_signature
from stom_rl.rl_discovery.d4_contract import D4AlgorithmArmId, D4RewardArmId
from stom_rl.rl_discovery.d4_gates import D4Outcome, evaluate_d4_gate
from stom_rl.rl_discovery.d4_inputs import D4InputBundle, load_d4_inputs
from stom_rl.rl_discovery.d4_training import D4TrainingConfig, train_d4_model
from stom_rl.rl_discovery.storage import artifact_manifest_sha256, atomic_write_bytes, contained_path


class D4RunProfile(StrEnum):
    SMOKE = "SMOKE"
    PRIMARY = "PRIMARY"


def execute_d4(
    repo_root: Path,
    run_dir: Path,
    *,
    profile: D4RunProfile,
    approved_smoke: Path | None,
    approval_key: bytes | None,
) -> Path:
    """Execute the preregistered D4 matrix into an immutable run directory."""

    bundle = load_d4_inputs(repo_root)
    if profile is D4RunProfile.PRIMARY and (approval_key is None or len(approval_key) < 32):
        raise PermissionError("D4 Primary requires KRONOS_D4_APPROVAL_KEY_HEX")
    approved_name = approve_d4_smoke(
        approved_smoke,
        run_root=run_dir.parent,
        prereg_sha=bundle.prereg_sha256,
        episode_sha=bundle.episode_sha256,
        approval_key=approval_key,
    ) if profile is D4RunProfile.PRIMARY else None
    atomic_write_bytes(contained_path(run_dir, "inputs", "prereg.json"), bundle.prereg_bytes)
    atomic_write_bytes(contained_path(run_dir, "inputs", "episodes.json"), bundle.episode_bytes)
    representation = D3Representation.for_arm(D3PolicyArmId.TOP5_CONTEXT_4X)
    seeds = bundle.prereg.seeds if profile is D4RunProfile.PRIMARY else bundle.prereg.smoke.seeds
    outcomes: list[D4Outcome] = []
    model_rows: list[dict[str, str | int | bool | dict[str, float | int]]] = []
    for algorithm in D4AlgorithmArmId:
        registered = next(item for item in bundle.prereg.algorithm_arms if item.id is algorithm)
        config = _training_config(bundle, algorithm, profile)
        for reward in D4RewardArmId:
            for seed in seeds:
                fit_episodes = bundle.episodes if reward is D4RewardArmId.NATIVE else shuffled_d3_episodes(bundle.episodes, seed=seed)
                trained = train_d4_model(
                    fit_episodes,
                    representation=representation,
                    config=D4TrainingConfig(algorithm, seed, config[0], config[1]),
                )
                model_arm = f"{algorithm.value}__{reward.value}"
                trained.save(run_dir, arm=model_arm, seed=seed)
                fit, fit_events = evaluate_d3_model(trained.policy, fit_episodes, representation=representation, seed=seed, cost_bp=0)
                native, native_events = evaluate_d3_model(trained.policy, bundle.episodes, representation=representation, seed=seed, cost_bp=0)
                cost, cost_events = evaluate_d3_model(trained.policy, bundle.episodes, representation=representation, seed=seed, cost_bp=23)
                outcome = D4Outcome(algorithm, reward, seed, fit, native, cost)
                outcomes.append(outcome)
                model_row = _outcome_payload(outcome, registered.family.value, registered.rl_claim_allowed, config)
                outcome_payload = {
                    **model_row,
                    "events": {"fit": fit_events, "native": native_events, "cost_23bp": cost_events},
                }
                model_rows.append(model_row)
                atomic_write_bytes(
                    contained_path(run_dir, "outcomes", algorithm.value, reward.value, f"seed-{seed}.json"),
                    canonical_json_bytes(outcome_payload),
                )
                print(f"[{profile.value}] {algorithm.value}/{reward.value}/seed-{seed} fit={fit.reward_ratio:.3f} native={native.reward_ratio:.3f}", flush=True)
    return _finish_run(run_dir, profile, bundle, tuple(outcomes), tuple(model_rows), approved_name, approval_key)


def _training_config(
    bundle: D4InputBundle,
    algorithm: D4AlgorithmArmId,
    profile: D4RunProfile,
) -> tuple[int, int]:
    registered = next(item for item in bundle.prereg.algorithm_arms if item.id is algorithm)
    if profile is D4RunProfile.SMOKE:
        rl_steps = 0 if algorithm is D4AlgorithmArmId.SUPERVISED_CEILING else bundle.prereg.smoke.rl_timesteps
        epochs = bundle.prereg.smoke.supervised_epochs if algorithm in {D4AlgorithmArmId.SUPERVISED_CEILING, D4AlgorithmArmId.AUXILIARY_PPO} else 0
        return rl_steps, epochs
    rl_steps = 0 if algorithm is D4AlgorithmArmId.SUPERVISED_CEILING else registered.training_steps
    return rl_steps, registered.pretraining_epochs


def _outcome_payload(
    outcome: D4Outcome,
    family: str,
    rl_claim_allowed: bool,
    config: tuple[int, int],
) -> dict[str, str | int | bool | dict[str, float | int]]:
    return {
        "algorithm_arm": outcome.algorithm_arm.value,
        "algorithm_family": family,
        "rl_claim_allowed": rl_claim_allowed,
        "reward_arm": outcome.reward_arm.value,
        "seed": outcome.seed,
        "rl_timesteps": config[0],
        "pretraining_epochs": config[1],
        "fit": asdict(outcome.fit),
        "native": asdict(outcome.native),
        "cost_23bp": asdict(outcome.cost_23bp),
    }


def _finish_run(
    run_dir: Path,
    profile: D4RunProfile,
    bundle: D4InputBundle,
    outcomes: tuple[D4Outcome, ...],
    model_rows: tuple[dict[str, str | int | bool | dict[str, float | int]], ...],
    approved_smoke: str | None,
    approval_key: bytes | None,
) -> Path:
    gate = evaluate_d4_gate(outcomes, thresholds=bundle.prereg.gate) if profile is D4RunProfile.PRIMARY else None
    summary = {
        "schema_version": "kronos.rl-discovery.d4.result.v1",
        "research_lane": "rl_discovery",
        "experiment_id": bundle.prereg.experiment_id,
        "profile": profile.value,
        "status": "COMPLETE",
        "verdict": "SMOKE_COMPLETE" if gate is None else gate.verdict,
        "gate": None if gate is None else asdict(gate),
        "models": model_rows,
        "input_hashes": bundle.input_hashes,
        "prereg_sha256": bundle.prereg_sha256,
        "episode_snapshot_sha256": bundle.episode_sha256,
        "approved_smoke": approved_smoke,
        "fresh_oos": "NOT_RUN_NO_READ",
        "promotion_allowed": False,
        "profitability_claim_allowed": False,
        "primary_round_trip_cost_bp": 0,
        "diagnostic_round_trip_cost_bp": 23,
    }
    atomic_write_bytes(contained_path(run_dir, "summary.json"), canonical_json_bytes(summary))
    digest = artifact_manifest_sha256(run_dir, excluded_relative_paths=frozenset({"terminal_receipt.json"}))
    receipt = {
        "profile": profile.value,
        "status": "COMPLETE",
        "verdict": summary["verdict"],
        "prereg_sha256": bundle.prereg_sha256,
        "episode_snapshot_sha256": bundle.episode_sha256,
        "artifact_manifest_sha256": digest,
        "fresh_oos": "NOT_RUN_NO_READ",
    }
    if profile is D4RunProfile.PRIMARY and approval_key is not None and approved_smoke is not None:
        receipt["primary_custody_hmac_sha256"] = primary_custody_signature(
            approval_key,
            run_name=run_dir.name,
            prereg_sha=bundle.prereg_sha256,
            episode_sha=bundle.episode_sha256,
            manifest_sha=digest,
            approved_smoke=approved_smoke,
        )
    atomic_write_bytes(contained_path(run_dir, "terminal_receipt.json"), canonical_json_bytes(receipt))
    return run_dir
