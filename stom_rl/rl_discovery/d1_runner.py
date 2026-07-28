"""Executable Type2-D1 reward/action research runner."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
from stom_rl.rl_discovery.d1_approval import approved_smoke_reference
from stom_rl.rl_discovery.d1_contract import load_d1_prereg_bytes
from stom_rl.rl_discovery.d1_evidence import write_d1_terminal, write_d1_unit
from stom_rl.rl_discovery.d1_fixture import load_d1_fixture
from stom_rl.rl_discovery.d1_gates import D1Outcome, evaluate_d1_gate
from stom_rl.rl_discovery.d1_lifecycle import D1Lifecycle, D1LifecycleError
from stom_rl.rl_discovery.d1_training import D1TrainingConfig, evaluate_d1_arm, train_d1_arm
from stom_rl.rl_discovery.gates import RunProfile
from stom_rl.rl_discovery.storage import atomic_write_bytes, contained_path


@dataclass(frozen=True, slots=True)
class D1Paths:
    """Confined D1 inputs and output root."""

    repo_root: Path
    fixture: Path
    prereg: Path
    run_root: Path

    @classmethod
    def default(cls, repo_root: Path) -> D1Paths:
        return cls(
            repo_root=repo_root,
            fixture=repo_root / "tests" / "fixtures" / "type1_synthetic_fixture.json",
            prereg=repo_root / "docs" / "kronos_rl_discovery_type2_d1_prereg_2026-07-28.json",
            run_root=repo_root / "webui" / "rl_runs" / "rl_discovery",
        )


def run_d1(
    paths: D1Paths,
    *,
    profile: RunProfile,
    run_id: str | None = None,
    approved_smoke: Path | None = None,
    resume: bool = False,
) -> Path:
    """Execute one immutable D1 Smoke or conditionally approved Primary matrix."""

    prereg_bytes = paths.prereg.read_bytes()
    fixture_bytes = paths.fixture.read_bytes()
    prereg = load_d1_prereg_bytes(prereg_bytes)
    prereg_sha = hashlib.sha256(prereg_bytes).hexdigest()
    fixture_sha = hashlib.sha256(fixture_bytes).hexdigest()
    smoke_reference = approved_smoke_reference(
        profile=profile,
        approved_smoke=approved_smoke,
        prereg_sha=prereg_sha,
        fixture_sha=fixture_sha,
        run_root=paths.run_root,
    )
    timestamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
    selected_id = run_id or f"type2-d1-{profile.value.lower()}-{timestamp}"
    seeds = prereg.training.smoke_seeds if profile is RunProfile.SMOKE else prereg.seeds
    timesteps = (
        prereg.training.smoke_timesteps
        if profile is RunProfile.SMOKE
        else prereg.training.primary_timesteps
    )
    if resume and run_id is None:
        raise D1LifecycleError("resume requires an explicit run ID")
    expected_runs = tuple(
        D1Lifecycle.key(arm_contract.id, seed)
        for arm_contract in prereg.arms
        for seed in seeds
    )
    lifecycle = D1Lifecycle.open(
        paths.run_root,
        run_id=selected_id,
        experiment_id=prereg.experiment_id,
        profile=profile,
        prereg_sha256=prereg_sha,
        fixture_sha256=fixture_sha,
        expected_runs=expected_runs,
        resume=resume,
    )
    run_dir = lifecycle.run_dir
    if not resume:
        atomic_write_bytes(contained_path(run_dir, "inputs", "prereg.json"), prereg_bytes)
        atomic_write_bytes(contained_path(run_dir, "inputs", "fixture.json"), fixture_bytes)
    pairs = load_d1_fixture(contained_path(run_dir, "inputs", "fixture.json"))
    outcomes: list[D1Outcome] = list(lifecycle.outcomes)
    for arm_contract in prereg.arms:
        for seed in seeds:
            if D1Lifecycle.key(arm_contract.id, seed) in lifecycle.completed_keys:
                continue
            trained = train_d1_arm(
                pairs,
                arm=arm_contract.id,
                reward_kind=arm_contract.reward,
                config=D1TrainingConfig(seed=seed, timesteps=timesteps),
            )
            trained.save(run_dir, arm=arm_contract.id.value, seed=seed)
            outcome, events = evaluate_d1_arm(
                trained.model,
                pairs,
                arm=arm_contract.id,
                seed=seed,
                training_timesteps=timesteps,
            )
            outcomes.append(outcome)
            write_d1_unit(run_dir, outcome=outcome, events=events)
            lifecycle.record(outcome)
            print(
                f"[{profile.value}] D1 arm={arm_contract.id.value} seed={seed} "
                f"ratio={outcome.economic_reward_ratio:.6f} "
                f"accuracy={outcome.initial_decision_accuracy:.6f}",
                flush=True,
            )
    gate = evaluate_d1_gate(tuple(outcomes), profile=profile, thresholds=prereg.gate)
    lifecycle.mark_complete_pending_receipt()
    write_d1_terminal(
        run_dir,
        prereg=prereg,
        profile=profile,
        outcomes=tuple(outcomes),
        gate=gate,
        prereg_sha=prereg_sha,
        fixture_sha=fixture_sha,
        smoke_reference=smoke_reference,
    )
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--profile", choices=[item.value for item in RunProfile], default="SMOKE")
    _ = parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    _ = parser.add_argument("--run-id")
    _ = parser.add_argument("--approved-smoke", type=Path)
    _ = parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    profile = RunProfile(args.profile)
    result = run_d1(
        D1Paths.default(args.repo_root.resolve()),
        profile=profile,
        run_id=args.run_id,
        approved_smoke=args.approved_smoke,
        resume=bool(args.resume),
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
