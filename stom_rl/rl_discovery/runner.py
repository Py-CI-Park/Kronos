"""Executable Type2-D0 PPO/behavior-cloning attribution runner."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
import random
import time
from typing import TYPE_CHECKING, ClassVar, Protocol, cast

from pydantic import BaseModel, ConfigDict

from stom_rl.rl_discovery.contract import ArmId, DiscoveryPreregistration, load_prereg
from stom_rl.rl_discovery.gates import ArmOutcome, RunProfile, evaluate_discovery_gate
from stom_rl.rl_discovery.lifecycle import DiscoveryLifecycle

if TYPE_CHECKING:
    from stom_rl.daily_type1_train import TrainingConfig


class EvaluationMetrics(BaseModel):
    """Typed boundary around the legacy Type1 evaluator payload."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", frozen=True)

    achieved_reward_ratio: float
    exact_basket_accuracy: float
    invalid_action_count: int
    block_count: int
    no_fill_count: int


@dataclass(frozen=True, slots=True)
class DiscoveryPaths:
    """All permitted inputs and outputs for the discovery runner."""

    repo_root: Path
    fixture: Path
    prereg: Path
    run_root: Path

    @classmethod
    def default(cls, repo_root: Path) -> DiscoveryPaths:
        return cls(
            repo_root=repo_root,
            fixture=repo_root / "tests" / "fixtures" / "type1_synthetic_fixture.json",
            prereg=repo_root / "docs" / "kronos_rl_discovery_type2_d0_prereg_2026-07-26.json",
            run_root=repo_root / "webui" / "rl_runs" / "rl_discovery",
        )


class DiscoveryModel(Protocol):
    """Minimal model surface required by the attribution runner."""

    def learn(self, *, total_timesteps: int, progress_bar: bool) -> object: ...

    def save(self, path: str) -> None: ...


class DiscoveryNormalizer(Protocol):
    """Persisted observation/reward normalization contract."""

    def save(self, path: str) -> None: ...


@dataclass(frozen=True, slots=True)
class TrainedArm:
    """Model bundle that must remain loadable after a run is interrupted."""

    model: DiscoveryModel
    normalizer: DiscoveryNormalizer

    def save(self, run_dir: Path, *, arm: str, seed: int) -> None:
        model_dir = run_dir / "models" / arm / f"seed-{seed}"
        model_dir.mkdir(parents=True, exist_ok=True)
        self.model.save(str(model_dir / "model.zip"))
        self.normalizer.save(str(model_dir / "normalizer.pkl"))


def shuffle_reward_pairs(
    pairs: Sequence[Mapping[str, object]],
    *,
    seed: int,
) -> tuple[dict[str, object], ...]:
    """Permute complete return vectors while leaving observations unchanged."""

    if len(pairs) < 2:
        raise ValueError("shuffled-reward control requires at least two pairs")
    order = list(range(len(pairs)))
    random.Random(seed).shuffle(order)
    if order == list(range(len(pairs))):
        order = order[1:] + order[:1]
    reward_vectors = [deepcopy(pairs[index]["gross_returns"]) for index in order]
    shuffled: list[dict[str, object]] = []
    for pair, rewards in zip(pairs, reward_vectors, strict=True):
        clone = deepcopy(dict(pair))
        clone["gross_returns"] = rewards
        shuffled.append(clone)
    return tuple(shuffled)


def outcome_from_evaluation(
    *,
    arm: str,
    seed: int,
    training_timesteps: int,
    shuffled_reward: bool,
    events: Sequence[Mapping[str, object]],
    metrics: Mapping[str, object],
) -> ArmOutcome:
    """Normalize evaluator output and calculate initial-decision collapse."""

    parsed = EvaluationMetrics.model_validate(metrics)
    initial_actions = [_required_int(event, "action") for event in events if event.get("call_index") == 0]
    if not initial_actions:
        raise ValueError("evaluation contains no initial decisions")
    dominant_count = Counter(initial_actions).most_common(1)[0][1]
    return ArmOutcome(
        arm=arm,
        seed=seed,
        training_timesteps=training_timesteps,
        oracle_reward_ratio=parsed.achieved_reward_ratio,
        exact_basket_accuracy=parsed.exact_basket_accuracy,
        invalid_action_count=parsed.invalid_action_count,
        block_count=parsed.block_count,
        no_fill_count=parsed.no_fill_count,
        dominant_action_rate=dominant_count / len(initial_actions),
        shuffled_reward=shuffled_reward,
    )


def _required_int(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def _training_config(seed: int, profile: RunProfile, prereg: DiscoveryPreregistration) -> TrainingConfig:
    from stom_rl.daily_type1_train import TrainingConfig

    timesteps = (
        prereg.training.smoke_timesteps
        if profile is RunProfile.SMOKE
        else prereg.training.primary_timesteps
    )
    return TrainingConfig(
        seed=seed,
        synthetic_timesteps=timesteps,
        n_steps=64 if profile is RunProfile.SMOKE else 1000,
        batch_size=64 if profile is RunProfile.SMOKE else 250,
        n_epochs=2 if profile is RunProfile.SMOKE else 10,
        oracle_calibration_epochs=20 if profile is RunProfile.SMOKE else 200,
    )


def _train_arm(
    arm: ArmId,
    pairs: Sequence[Mapping[str, object]],
    config: TrainingConfig,
) -> TrainedArm:
    from stom_rl.daily_type1_train import calibrate_synthetic_oracle, create_model, train_model

    if arm is ArmId.PPO_ONLY:
        model, normalizer = cast(
            tuple[object, object],
            train_model(pairs, config, timesteps=config.synthetic_timesteps),
        )
        return TrainedArm(cast(DiscoveryModel, model), cast(DiscoveryNormalizer, normalizer))
    if arm is ArmId.BC_THEN_PPO:
        raw_model, raw_normalizer = cast(tuple[object, object], create_model(pairs, config))
        model = cast(DiscoveryModel, raw_model)
        _ = calibrate_synthetic_oracle(model, pairs, epochs=config.oracle_calibration_epochs)
        _ = model.learn(total_timesteps=config.synthetic_timesteps, progress_bar=False)
        return TrainedArm(model, cast(DiscoveryNormalizer, raw_normalizer))
    if arm is ArmId.BC_ONLY:
        raw_model, raw_normalizer = cast(tuple[object, object], create_model(pairs, config))
        model = cast(DiscoveryModel, raw_model)
        _ = calibrate_synthetic_oracle(model, pairs, epochs=config.oracle_calibration_epochs)
        return TrainedArm(model, cast(DiscoveryNormalizer, raw_normalizer))
    shuffled_pairs = shuffle_reward_pairs(pairs, seed=config.seed)
    raw_model, raw_normalizer = cast(
        tuple[object, object],
        train_model(shuffled_pairs, config, timesteps=config.synthetic_timesteps),
    )
    return TrainedArm(
        cast(DiscoveryModel, raw_model), cast(DiscoveryNormalizer, raw_normalizer)
    )


def run_discovery(
    paths: DiscoveryPaths,
    *,
    profile: RunProfile,
    run_id: str | None = None,
    resume_dir: Path | None = None,
) -> Path:
    """Execute or resume every preregistered arm with durable partial evidence."""

    from stom_rl.daily_type1_train import evaluate_model, load_synthetic_fixture

    prereg_bytes = paths.prereg.read_bytes()
    prereg = load_prereg(paths.prereg)
    pairs = load_synthetic_fixture(paths.fixture)
    seeds = prereg.training.smoke_seeds if profile is RunProfile.SMOKE else prereg.seeds
    prereg_sha256 = hashlib.sha256(prereg_bytes).hexdigest()
    expected_runs = tuple(f"{arm.id.value}:{seed}" for arm in prereg.arms for seed in seeds)
    if resume_dir is None:
        timestamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
        lifecycle = DiscoveryLifecycle.start(
            paths.run_root,
            run_id=run_id or f"type2-d0-{profile.value.lower()}-{timestamp}",
            experiment_id=prereg.experiment_id,
            profile=profile,
            prereg_sha256=prereg_sha256,
            expected_runs=expected_runs,
        )
    else:
        lifecycle = DiscoveryLifecycle.resume(
            resume_dir,
            experiment_id=prereg.experiment_id,
            profile=profile,
            prereg_sha256=prereg_sha256,
        )
    started_at = time.monotonic()
    for arm in prereg.arms:
        for seed in seeds:
            key = f"{arm.id.value}:{seed}"
            if key in lifecycle.completed_keys:
                print(f"[{profile.value}] resume skip arm={arm.id.value} seed={seed}", flush=True)
                continue
            config = _training_config(seed, profile, prereg)
            print(
                f"[{profile.value}] start arm={arm.id.value} seed={seed} timesteps={config.synthetic_timesteps if arm.ppo else 0}",
                flush=True,
            )
            trained = _train_arm(arm.id, pairs, config)
            trained.save(lifecycle.run_dir, arm=arm.id.value, seed=seed)
            events, metrics = cast(
                tuple[list[dict[str, object]], dict[str, object]],
                evaluate_model(trained.model, pairs, seed=seed),
            )
            outcome = outcome_from_evaluation(
                arm=arm.id.value,
                seed=seed,
                training_timesteps=config.synthetic_timesteps if arm.ppo else 0,
                shuffled_reward=arm.reward.value == "SHUFFLED",
                events=events,
                metrics=metrics,
            )
            lifecycle.record(outcome)
            elapsed = time.monotonic() - started_at
            print(
                f"[{profile.value}] done arm={arm.id.value} seed={seed} ratio={outcome.oracle_reward_ratio:.6f} elapsed_sec={elapsed:.1f}",
                flush=True,
            )
    gate = evaluate_discovery_gate(lifecycle.outcomes, profile=profile)
    lifecycle.complete(gate)
    return lifecycle.run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--profile", choices=[profile.value for profile in RunProfile], default="SMOKE")
    _ = parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    _ = parser.add_argument("--run-id", help="stable direct-child run name for a new run")
    _ = parser.add_argument("--resume", type=Path, help="existing discovery run directory")
    args = parser.parse_args()
    repo_root = cast(Path, args.repo_root)
    profile = RunProfile(cast(str, args.profile))
    run_dir = run_discovery(
        DiscoveryPaths.default(repo_root.resolve()),
        profile=profile,
        run_id=cast(str | None, args.run_id),
        resume_dir=cast(Path | None, args.resume),
    )
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
