"""Custody-bound D5R source loader for D5S stability research."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from stom_rl.rl_discovery.d2_custody import assert_plain_path, held_bytes, verified_bytes
from stom_rl.rl_discovery.d3_env import D3Episode
from stom_rl.rl_discovery.d5r_source import load_d5r_source
from stom_rl.rl_discovery.d5s_contract import D5SPreregistration, load_d5s_prereg_bytes
from stom_rl.rl_discovery.d5s_gate import D5SBaseline
from stom_rl.rl_discovery.storage import artifact_manifest_sha256


class D5SSourceError(ValueError):
    """D5S source artifacts do not match the frozen preregistration."""


@dataclass(frozen=True, slots=True)
class D5SSourceBundle:
    prereg: D5SPreregistration
    prereg_bytes: bytes
    prereg_sha256: str
    episodes: tuple[D3Episode, ...]
    baselines: tuple[D5SBaseline, ...]


def load_d5s_source(repo_root: Path) -> D5SSourceBundle:
    root = repo_root.absolute()
    prereg_path = root / "docs/kronos_rl_discovery_type2_d5s_prereg_2026-07-30.json"
    prereg_bytes = held_bytes(prereg_path, anchor=root)
    prereg = load_d5s_prereg_bytes(prereg_bytes)
    run_dir = root / "webui" / "rl_runs" / "rl_discovery" / prereg.source_run.run_name
    _ = assert_plain_path(run_dir, anchor=root, require_file=False)
    _ = verified_bytes(
        run_dir / "summary.json",
        expected_sha256=prereg.source_run.summary_sha256,
        anchor=root,
    )
    _ = verified_bytes(
        run_dir / "terminal_receipt.json",
        expected_sha256=prereg.source_run.terminal_receipt_sha256,
        anchor=root,
    )
    digest = artifact_manifest_sha256(
        run_dir,
        excluded_relative_paths=frozenset({"terminal_receipt.json"}),
    )
    if digest != prereg.source_run.artifact_manifest_sha256:
        raise D5SSourceError("D5S source artifact manifest is mismatched")
    models = tuple(run_dir.glob("models/*/seed-*/steps-*/model.zip"))
    outcomes = tuple(run_dir.glob("outcomes/*/seed-*/steps-*.json"))
    if len(models) != prereg.source_run.model_count or len(outcomes) != prereg.source_run.outcome_count:
        raise D5SSourceError("D5S source matrix is incomplete")
    d5r_source = load_d5r_source(root)
    if d5r_source.prereg.source_run.episode_snapshot_sha256 != prereg.source_run.episode_snapshot_sha256:
        raise D5SSourceError("D5S episode custody is mismatched")
    baselines = tuple(
        D5SBaseline(unit.seed, unit.baseline_accuracy, unit.baseline_reward_ratio)
        for unit in d5r_source.units
        if unit.reward_arm == "NATIVE" and unit.seed in {0, 1, 2}
    )
    return D5SSourceBundle(
        prereg,
        prereg_bytes,
        hashlib.sha256(prereg_bytes).hexdigest(),
        d5r_source.episodes,
        baselines,
    )
