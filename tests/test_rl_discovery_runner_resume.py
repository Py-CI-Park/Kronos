from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from stom_rl.rl_discovery import runner
from stom_rl.rl_discovery.contract import ArmId, DiscoveryPreregistration
from stom_rl.rl_discovery.gates import RunProfile
from stom_rl.rl_discovery.training_bundle import TrainedArm


class _Model:
    def learn(self, *, total_timesteps: int, progress_bar: bool) -> object:
        _ = total_timesteps, progress_bar
        return self

    def save(self, path: str) -> None:
        _ = Path(path).write_bytes(b"model")


class _Normalizer:
    def save(self, path: str) -> None:
        _ = Path(path).write_bytes(b"normalizer")


@dataclass(frozen=True, slots=True)
class _IgnoredConfig:
    """Runtime placeholder; the fake trainer never reads training configuration."""

    synthetic_timesteps: int = 256


def _trained() -> TrainedArm:
    return TrainedArm(model=_Model(), normalizer=_Normalizer())


def _fixture_pairs(path: Path) -> Sequence[Mapping[str, object]]:
    return ({"path": str(path)},)


def _config(
    seed: int,
    profile: RunProfile,
    prereg: DiscoveryPreregistration,
) -> _IgnoredConfig:
    _ = seed, profile, prereg
    return _IgnoredConfig()


def _evaluation(
    model: _Model,
    pairs: Sequence[Mapping[str, object]],
    *,
    seed: int,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    _ = model, pairs, seed
    return (
        [{"call_index": 0, "action": 0}],
        {
            "achieved_reward_ratio": 0.5,
            "exact_basket_accuracy": 0.5,
            "invalid_action_count": 0,
            "block_count": 0,
            "no_fill_count": 0,
        },
    )


def test_runner_resume_skips_completed_arm_and_finishes_remaining_matrix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = replace(
        runner.DiscoveryPaths.default(Path(__file__).resolve().parents[1]),
        run_root=tmp_path,
    )
    attempted: list[ArmId] = []

    def interrupting_train(
        arm: ArmId,
        pairs: Sequence[Mapping[str, object]],
        config: _IgnoredConfig,
    ) -> TrainedArm:
        _ = pairs, config
        attempted.append(arm)
        if len(attempted) == 2:
            raise RuntimeError("simulated interruption")
        return _trained()

    monkeypatch.setattr(runner, "_train_arm", interrupting_train)
    monkeypatch.setattr(runner, "load_fixture_pairs", _fixture_pairs)
    monkeypatch.setattr(runner, "build_training_config", _config)
    monkeypatch.setattr(runner, "evaluate_discovery_model", _evaluation)

    with pytest.raises(RuntimeError, match="simulated interruption"):
        _ = runner.run_discovery(
            paths,
            profile=RunProfile.SMOKE,
            run_id="type2-d0-smoke-resume-e2e",
        )

    run_dir = tmp_path / "type2-d0-smoke-resume-e2e"
    assert (run_dir / "inputs" / "prereg.json").read_bytes() == paths.prereg.read_bytes()
    assert (run_dir / "inputs" / "fixture.json").read_bytes() == paths.fixture.read_bytes()
    resumed_arms: list[ArmId] = []

    def resumed_train(
        arm: ArmId,
        pairs: Sequence[Mapping[str, object]],
        config: _IgnoredConfig,
    ) -> TrainedArm:
        _ = pairs, config
        resumed_arms.append(arm)
        return _trained()

    monkeypatch.setattr(runner, "_train_arm", resumed_train)

    completed = runner.run_discovery(
        paths,
        profile=RunProfile.SMOKE,
        resume_dir=run_dir,
    )

    assert completed == run_dir.resolve()
    assert resumed_arms == [ArmId.BC_THEN_PPO, ArmId.BC_ONLY, ArmId.SHUFFLED_REWARD_PPO]
    assert (run_dir / "terminal_receipt.json").is_file()
    assert len(tuple((run_dir / "models").glob("*/seed-0/model.zip"))) == 4
