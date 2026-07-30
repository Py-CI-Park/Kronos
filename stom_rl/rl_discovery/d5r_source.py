"""Custody-bound D5 source loader for D5R diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

from stom_rl.rl_discovery.d2_custody import assert_plain_path, held_bytes, verified_bytes
from stom_rl.rl_discovery.d3_env import D3Episode
from stom_rl.rl_discovery.d5_inputs import load_d5_inputs
from stom_rl.rl_discovery.d5r_contract import D5RPreregistration, load_d5r_prereg_bytes
from stom_rl.rl_discovery.d5r_diagnostic import D5REvent
from stom_rl.rl_discovery.storage import artifact_manifest_sha256


class D5RSourceError(ValueError):
    """D5 source artifacts do not match the D5R preregistration."""


class _FrozenBoundary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore", strict=True)


class _SourceEvent(_FrozenBoundary):
    decision_date: str
    action: int
    expected_action: int
    reward: float


class _SourceEvents(_FrozenBoundary):
    native_23bp: tuple[_SourceEvent, ...]


class _SourceMetric(_FrozenBoundary):
    accuracy: float
    reward_ratio: float


class _SourceOutcome(_FrozenBoundary):
    algorithm_arm: Literal["C_DQN_DISCRETE"]
    algorithm_family: Literal["DQN"]
    reward_arm: Literal["NATIVE", "SHUFFLED"]
    seed: int
    rl_timesteps: Literal[200000]
    training_round_trip_cost_bp: Literal[23]
    native_23bp: _SourceMetric
    events: _SourceEvents


@dataclass(frozen=True, slots=True)
class D5RSourceUnit:
    reward_arm: str
    seed: int
    baseline_accuracy: float
    baseline_reward_ratio: float
    events: tuple[D5REvent, ...]


@dataclass(frozen=True, slots=True)
class D5RSourceBundle:
    prereg: D5RPreregistration
    prereg_bytes: bytes
    prereg_sha256: str
    episodes: tuple[D3Episode, ...]
    units: tuple[D5RSourceUnit, ...]


def load_d5r_source(repo_root: Path) -> D5RSourceBundle:
    root = repo_root.absolute()
    prereg_path = root / "docs/kronos_rl_discovery_type2_d5r_prereg_2026-07-30.json"
    prereg_bytes = held_bytes(prereg_path, anchor=root)
    prereg = load_d5r_prereg_bytes(prereg_bytes)
    run_dir = root / "webui" / "rl_runs" / "rl_discovery" / prereg.source_run.run_name
    _ = assert_plain_path(run_dir, anchor=root, require_file=False)
    _ = verified_bytes(run_dir / "summary.json", expected_sha256=prereg.source_run.summary_sha256, anchor=root)
    episode_bytes = verified_bytes(
        run_dir / "inputs" / "episodes.json",
        expected_sha256=prereg.source_run.episode_snapshot_sha256,
        anchor=root,
    )
    digest = artifact_manifest_sha256(
        run_dir,
        excluded_relative_paths=frozenset({"terminal_receipt.json"}),
    )
    if digest != prereg.source_run.artifact_manifest_sha256:
        raise D5RSourceError("D5R source artifact manifest is mismatched")
    d5_inputs = load_d5_inputs(root)
    if d5_inputs.episode_bytes != episode_bytes:
        raise D5RSourceError("D5R source episodes are not reproducible")
    units = tuple(
        _load_unit(run_dir, root, reward_arm, seed)
        for reward_arm in prereg.d5r_1_diagnostic.source_arms
        for seed in prereg.d5r_1_diagnostic.seeds
    )
    return D5RSourceBundle(
        prereg,
        prereg_bytes,
        hashlib.sha256(prereg_bytes).hexdigest(),
        d5_inputs.episodes,
        units,
    )


def _load_unit(run_dir: Path, root: Path, reward_arm: str, seed: int) -> D5RSourceUnit:
    outcome_path = run_dir / "outcomes" / reward_arm / f"seed-{seed}.json"
    outcome = _SourceOutcome.model_validate_json(held_bytes(outcome_path, anchor=root))
    if outcome.reward_arm != reward_arm or outcome.seed != seed:
        raise D5RSourceError("D5R source outcome identity is mismatched")
    events = tuple(
        D5REvent(event.decision_date, event.action, event.expected_action, event.reward)
        for event in outcome.events.native_23bp
    )
    return D5RSourceUnit(
        reward_arm,
        seed,
        outcome.native_23bp.accuracy,
        outcome.native_23bp.reward_ratio,
        events,
    )
