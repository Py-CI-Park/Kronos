"""Immutable D3 Smoke/Primary matrix execution and approval."""

from __future__ import annotations

from dataclasses import asdict
from enum import StrEnum
import json
from pathlib import Path

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d2_custody import assert_plain_path, held_bytes
from stom_rl.rl_discovery.d3_contract import D3PolicyArmId, D3RewardArmId
from stom_rl.rl_discovery.d3_env import D3Representation
from stom_rl.rl_discovery.d3_gates import D3Outcome, evaluate_d3_gate
from stom_rl.rl_discovery.d3_inputs import D3InputBundle, load_d3_inputs
from stom_rl.rl_discovery.d3_training import D3Metrics, D3TrainingConfig, evaluate_d3_model, shuffled_d3_episodes, train_d3_model
from stom_rl.rl_discovery.storage import artifact_manifest_sha256, atomic_write_bytes, contained_path


class D3RunProfile(StrEnum):
    SMOKE = "SMOKE"
    PRIMARY = "PRIMARY"


def approve_d3_smoke(path: Path | None, *, run_root: Path, prereg_sha: str, episode_sha: str) -> str:
    """Approve only a direct-child, held-read, exact four-unit D3 Smoke."""

    if path is None:
        raise PermissionError("D3 Primary requires an approved Smoke")
    configured_root = run_root.absolute()
    root = path.absolute()
    if root.parent != configured_root:
        raise PermissionError("approved D3 Smoke must be a direct child of the run root")
    assert_plain_path(root, anchor=configured_root, require_file=False)
    for artifact in root.rglob("*"):
        assert_plain_path(artifact, anchor=configured_root, require_file=artifact.is_file())
    summary = json.loads(held_bytes(root / "summary.json", anchor=configured_root))
    receipt = json.loads(held_bytes(root / "terminal_receipt.json", anchor=configured_root))
    digest = artifact_manifest_sha256(root, excluded_relative_paths=frozenset({"terminal_receipt.json"}))
    required = {
        "profile": "SMOKE",
        "status": "COMPLETE",
        "verdict": "SMOKE_COMPLETE",
        "prereg_sha256": prereg_sha,
        "episode_snapshot_sha256": episode_sha,
        "fresh_oos": "NOT_RUN_NO_READ",
        "artifact_manifest_sha256": digest,
    }
    if any(receipt.get(key) != value for key, value in required.items()):
        raise PermissionError("approved D3 Smoke receipt is missing or mismatched")
    models = summary.get("models")
    expected_units = {(policy.value, reward.value, 0) for policy in tuple(D3PolicyArmId)[:2] for reward in D3RewardArmId}
    observed_units = {
        (item.get("policy_arm"), item.get("reward_arm"), item.get("seed"))
        for item in models
        if isinstance(item, dict)
    } if isinstance(models, list) else set()
    if (
        summary.get("schema_version") != "kronos.rl-discovery.d3.result.v1"
        or summary.get("profile") != "SMOKE"
        or summary.get("status") != "COMPLETE"
        or summary.get("verdict") != "SMOKE_COMPLETE"
        or summary.get("prereg_sha256") != prereg_sha
        or summary.get("episode_snapshot_sha256") != episode_sha
        or summary.get("fresh_oos") != "NOT_RUN_NO_READ"
        or not isinstance(models, list)
        or len(models) != 4
        or observed_units != expected_units
    ):
        raise PermissionError("approved D3 Smoke does not match the frozen four-unit matrix")
    return root.name


def execute_d3(repo_root: Path, run_dir: Path, *, profile: D3RunProfile, approved_smoke: Path | None) -> Path:
    """Execute the registered D3 matrix into an already-created immutable run."""

    bundle = load_d3_inputs(repo_root)
    run_root = run_dir.parent
    approved_name = approve_d3_smoke(
        approved_smoke,
        run_root=run_root,
        prereg_sha=bundle.prereg_sha256,
        episode_sha=bundle.episode_sha256,
    ) if profile is D3RunProfile.PRIMARY else None
    atomic_write_bytes(contained_path(run_dir, "inputs", "prereg.json"), bundle.prereg_bytes)
    atomic_write_bytes(contained_path(run_dir, "inputs", "episodes.json"), bundle.episode_bytes)
    policy_arms = tuple(D3PolicyArmId) if profile is D3RunProfile.PRIMARY else tuple(D3PolicyArmId)[:2]
    seeds = bundle.prereg.seeds if profile is D3RunProfile.PRIMARY else bundle.prereg.smoke.seeds
    outcomes: list[D3Outcome] = []
    for policy_arm in policy_arms:
        representation = D3Representation.for_arm(policy_arm)
        registered = next(item for item in bundle.prereg.policy_arms if item.id is policy_arm)
        timesteps = registered.timesteps if profile is D3RunProfile.PRIMARY else bundle.prereg.smoke.timesteps
        for reward_arm in D3RewardArmId:
            for seed in seeds:
                fit_episodes = bundle.episodes if reward_arm is D3RewardArmId.NATIVE else shuffled_d3_episodes(bundle.episodes, seed=seed)
                trained = train_d3_model(fit_episodes, representation=representation, config=D3TrainingConfig(seed=seed, timesteps=timesteps))
                model_arm = f"{policy_arm.value}__{reward_arm.value}"
                trained.save(run_dir, arm=model_arm, seed=seed)
                fit, fit_events = evaluate_d3_model(trained.model, fit_episodes, representation=representation, seed=seed, cost_bp=0)
                native, native_events = evaluate_d3_model(trained.model, bundle.episodes, representation=representation, seed=seed, cost_bp=0)
                cost, cost_events = evaluate_d3_model(trained.model, bundle.episodes, representation=representation, seed=seed, cost_bp=23)
                outcome = D3Outcome(policy_arm, reward_arm, seed, fit, native, cost)
                outcomes.append(outcome)
                payload = _outcome_payload(outcome, timesteps)
                payload["events"] = {"fit": fit_events, "native": native_events, "cost_23bp": cost_events}
                atomic_write_bytes(contained_path(run_dir, "outcomes", policy_arm.value, reward_arm.value, f"seed-{seed}.json"), canonical_json_bytes(payload))
                print(f"[{profile.value}] {policy_arm.value}/{reward_arm.value}/seed-{seed} fit={fit.reward_ratio:.3f} native={native.reward_ratio:.3f}", flush=True)
    return _finish_run(run_dir, profile=profile, bundle=bundle, outcomes=tuple(outcomes), approved_smoke=approved_name)


def _outcome_payload(outcome: D3Outcome, timesteps: int) -> dict[str, str | int | dict[str, float | int]]:
    return {
        "policy_arm": outcome.policy_arm.value,
        "reward_arm": outcome.reward_arm.value,
        "seed": outcome.seed,
        "training_timesteps": timesteps,
        "fit": asdict(outcome.fit),
        "native": asdict(outcome.native),
        "cost_23bp": asdict(outcome.cost_23bp),
    }


def _finish_run(run_dir: Path, *, profile: D3RunProfile, bundle: D3InputBundle, outcomes: tuple[D3Outcome, ...], approved_smoke: str | None) -> Path:
    gate = evaluate_d3_gate(outcomes, thresholds=bundle.prereg.gate) if profile is D3RunProfile.PRIMARY else None
    summary = {
        "schema_version": "kronos.rl-discovery.d3.result.v1",
        "research_lane": "rl_discovery",
        "experiment_id": bundle.prereg.experiment_id,
        "profile": profile.value,
        "status": "COMPLETE",
        "verdict": "SMOKE_COMPLETE" if gate is None else gate.verdict,
        "gate": None if gate is None else asdict(gate),
        "models": [_outcome_payload(item, next(arm.timesteps for arm in bundle.prereg.policy_arms if arm.id is item.policy_arm)) for item in outcomes],
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
    atomic_write_bytes(contained_path(run_dir, "terminal_receipt.json"), canonical_json_bytes(receipt))
    return run_dir
