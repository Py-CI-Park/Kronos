"""Execute the preregistered Type2-D2 historical-scale experiment."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d2_contract import D2ArmId, D2Preregistration, load_d2_prereg_bytes
from stom_rl.rl_discovery.d2_data import build_historical_episodes, iter_json_array, load_scales
from stom_rl.rl_discovery.d2_gates import D2GateResult, D2Outcome, evaluate_d2_gate
from stom_rl.rl_discovery.d2_training import (
    D2Metrics,
    D2TrainingConfig,
    evaluate_d2_model,
    shuffled_episodes,
    train_d2_model,
)
from stom_rl.rl_discovery.gates import RunProfile
from stom_rl.rl_discovery.storage import artifact_manifest_sha256, atomic_write_bytes, contained_path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_inputs(repo_root: Path, prereg: D2Preregistration) -> tuple[Path, Path, dict[str, str]]:
    rows = (repo_root / prereg.dataset.rows_relative_path).resolve()
    normalizer = (repo_root / prereg.dataset.normalizer_relative_path).resolve()
    manifest = rows.parent / "dataset_manifest.json"
    receipt = rows.parent / "materializer_complete_receipt.json"
    root = repo_root.resolve()
    for path in (rows, normalizer, manifest, receipt):
        if not path.is_file() or root not in path.parents:
            raise ValueError("D2 input must be a regular file inside the repository")
    hashes = {
        "rows": _sha256(rows),
        "manifest": _sha256(manifest),
        "materializer_receipt": _sha256(receipt),
        "normalizer": _sha256(normalizer),
    }
    expected = {
        "rows": prereg.dataset.rows_sha256,
        "manifest": prereg.dataset.manifest_sha256,
        "materializer_receipt": prereg.dataset.materializer_receipt_sha256,
        "normalizer": prereg.dataset.normalizer_file_sha256,
    }
    if hashes != expected:
        raise ValueError("D2 custody hash mismatch")
    value = json.loads(normalizer.read_text(encoding="utf-8"))
    if value.get("digest") != prereg.dataset.normalizer_digest:
        raise ValueError("D2 normalizer digest mismatch")
    return rows, normalizer, hashes


def _approved_smoke(path: Path | None, *, prereg_sha: str, data_sha: str) -> str:
    if path is None:
        raise PermissionError("Primary requires an approved D2 Smoke receipt")
    root = path.resolve()
    receipt_path = root / "terminal_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    digest = artifact_manifest_sha256(root, excluded_relative_paths=frozenset({"terminal_receipt.json"}))
    required = {
        "profile": "SMOKE",
        "status": "COMPLETE",
        "prereg_sha256": prereg_sha,
        "episode_snapshot_sha256": data_sha,
        "artifact_manifest_sha256": digest,
        "fresh_oos": "NOT_RUN_NO_READ",
    }
    if any(receipt.get(key) != value for key, value in required.items()):
        raise PermissionError("approved D2 Smoke receipt is missing or mismatched")
    return root.name


def _metrics(value: D2Metrics) -> dict[str, Any]:
    return asdict(value)


def _outcome_payload(outcome: D2Outcome, *, timesteps: int) -> dict[str, Any]:
    return {
        "arm": outcome.arm.value,
        "episode_count": outcome.episode_count,
        "seed": outcome.seed,
        "training_timesteps": timesteps,
        "fit": _metrics(outcome.fit),
        "native": _metrics(outcome.native),
        "cost_23bp": _metrics(outcome.cost_23bp),
    }


def _gate_payload(gate: D2GateResult) -> dict[str, Any]:
    return asdict(gate)


def run_d2(
    repo_root: Path,
    *,
    profile: RunProfile,
    run_id: str | None = None,
    approved_smoke: Path | None = None,
) -> Path:
    """Run Smoke or the full 24-member Primary matrix into an immutable directory."""

    prereg_path = repo_root / "docs" / "kronos_rl_discovery_type2_d2_prereg_2026-07-28.json"
    prereg_bytes = prereg_path.read_bytes()
    prereg = load_d2_prereg_bytes(prereg_bytes)
    prereg_sha = hashlib.sha256(prereg_bytes).hexdigest()
    rows_path, normalizer_path, input_hashes = _verify_inputs(repo_root, prereg)
    episodes = build_historical_episodes(
        iter_json_array(rows_path),
        scales=load_scales(normalizer_path),
        limit=128,
    )
    episode_bytes = canonical_json_bytes([asdict(episode) for episode in episodes])
    episode_sha = hashlib.sha256(episode_bytes).hexdigest()
    smoke_reference = None
    if profile is RunProfile.PRIMARY:
        smoke_reference = _approved_smoke(approved_smoke, prereg_sha=prereg_sha, data_sha=episode_sha)
    timestamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
    selected_id = run_id or f"type2-d2-{profile.value.lower()}-{timestamp}"
    run_root = repo_root / "webui" / "rl_runs" / "rl_discovery"
    run_dir = contained_path(run_root, selected_id)
    if run_dir.exists():
        raise FileExistsError("D2 run ID already exists")
    run_dir.mkdir(parents=True)
    atomic_write_bytes(contained_path(run_dir, "inputs", "prereg.json"), prereg_bytes)
    atomic_write_bytes(contained_path(run_dir, "inputs", "episodes.json"), episode_bytes)
    counts = prereg.training.smoke_episode_counts if profile is RunProfile.SMOKE else prereg.episode_counts
    seeds = prereg.training.smoke_seeds if profile is RunProfile.SMOKE else prereg.seeds
    outcomes: list[D2Outcome] = []
    for count in counts:
        native_episodes = episodes[:count]
        timesteps = prereg.training.timesteps_by_episode_count[str(count)]
        for arm in D2ArmId:
            for seed in seeds:
                fit_episodes = native_episodes if arm is D2ArmId.NATIVE else shuffled_episodes(native_episodes, seed=seed)
                trained = train_d2_model(fit_episodes, config=D2TrainingConfig(seed=seed, timesteps=timesteps))
                trained.save(run_dir, arm=f"count-{count}/{arm.value}", seed=seed)
                fit, fit_events = evaluate_d2_model(trained.model, fit_episodes, seed=seed, cost_bp=0)
                native, native_events = evaluate_d2_model(trained.model, native_episodes, seed=seed, cost_bp=0)
                cost, cost_events = evaluate_d2_model(trained.model, native_episodes, seed=seed, cost_bp=23)
                outcome = D2Outcome(arm, count, seed, fit, native, cost)
                outcomes.append(outcome)
                unit = contained_path(run_dir, "outcomes", f"count-{count}", arm.value, f"seed-{seed}.json")
                atomic_write_bytes(unit, canonical_json_bytes({
                    **_outcome_payload(outcome, timesteps=timesteps),
                    "events": {"fit": fit_events, "native": native_events, "cost_23bp": cost_events},
                }))
                print(
                    f"[{profile.value}] count={count} arm={arm.value} seed={seed} "
                    f"fit_acc={fit.accuracy:.3f} fit_ratio={fit.reward_ratio:.3f} "
                    f"native_ratio={native.reward_ratio:.3f} cost23={cost.reward_ratio:.3f}",
                    flush=True,
                )
    gate = evaluate_d2_gate(tuple(outcomes), thresholds=prereg.gate) if profile is RunProfile.PRIMARY else None
    summary = {
        "schema_version": "kronos.rl-discovery.d2.result.v1",
        "experiment_id": prereg.experiment_id,
        "profile": profile.value,
        "status": "COMPLETE",
        "verdict": "SMOKE_COMPLETE" if gate is None else gate.verdict,
        "gate": None if gate is None else _gate_payload(gate),
        "models": [_outcome_payload(item, timesteps=prereg.training.timesteps_by_episode_count[str(item.episode_count)]) for item in outcomes],
        "input_hashes": input_hashes,
        "prereg_sha256": prereg_sha,
        "episode_snapshot_sha256": episode_sha,
        "approved_smoke": smoke_reference,
        "fresh_oos": "NOT_RUN_NO_READ",
        "profitability_claim_allowed": False,
        "promotion_allowed": False,
    }
    atomic_write_bytes(contained_path(run_dir, "summary.json"), canonical_json_bytes(summary))
    digest = artifact_manifest_sha256(run_dir, excluded_relative_paths=frozenset({"terminal_receipt.json"}))
    receipt = {
        "profile": profile.value,
        "status": "COMPLETE",
        "verdict": summary["verdict"],
        "prereg_sha256": prereg_sha,
        "episode_snapshot_sha256": episode_sha,
        "artifact_manifest_sha256": digest,
        "fresh_oos": "NOT_RUN_NO_READ",
    }
    atomic_write_bytes(contained_path(run_dir, "terminal_receipt.json"), canonical_json_bytes(receipt))
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--profile", choices=[item.value for item in RunProfile], required=True)
    _ = parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    _ = parser.add_argument("--run-id")
    _ = parser.add_argument("--approved-smoke", type=Path)
    args = parser.parse_args()
    result = run_d2(
        args.repo_root.resolve(),
        profile=RunProfile(args.profile),
        run_id=args.run_id,
        approved_smoke=args.approved_smoke,
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
