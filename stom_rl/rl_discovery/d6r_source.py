"""Custody-bound TRAIN_ONLY source for D6R."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from stom_rl.rl_discovery.d2_custody import held_bytes, verified_bytes
from stom_rl.rl_discovery.d3_env import D3Episode
from stom_rl.rl_discovery.d5s_source import load_d5s_source
from stom_rl.rl_discovery.d6r_contract import (
    D6RPreregistration,
    load_d6r_prereg_bytes,
)
from stom_rl.rl_discovery.storage import artifact_manifest_sha256


class D6RSourceError(ValueError):
    """D6R source evidence does not match the frozen preregistration."""


@dataclass(frozen=True, slots=True)
class D6RSourceBundle:
    prereg: D6RPreregistration
    prereg_bytes: bytes
    prereg_sha256: str
    episodes: tuple[D3Episode, ...]
    episode_sha256: str
    input_hashes: tuple[tuple[str, str], ...]


def load_d6r_source(repo_root: Path) -> D6RSourceBundle:
    root = repo_root.absolute()
    prereg_path = root / "docs/kronos_rl_discovery_type2_d6r_prereg_2026-07-31.json"
    prereg_bytes = held_bytes(prereg_path, anchor=root)
    prereg = load_d6r_prereg_bytes(prereg_bytes)
    d6_result = root / "docs/kronos_rl_discovery_type2_d6_result_2026-07-31.md"
    d6_custody = root / "docs/evidence/type2-d6-primary-20260731-002.custody.json"
    _ = verified_bytes(
        d6_result,
        expected_sha256=prereg.prior_d6.result_document_sha256,
        anchor=root,
    )
    _ = verified_bytes(
        d6_custody,
        expected_sha256=prereg.prior_d6.custody_document_sha256,
        anchor=root,
    )
    d5s_source = load_d5s_source(root)
    if (
        d5s_source.prereg_sha256 != prereg.source.d5s_prereg_sha256
        or d5s_source.prereg.source_run.episode_snapshot_sha256
        != prereg.source.episode_snapshot_sha256
        or len(d5s_source.episodes) != prereg.source.episode_count
    ):
        raise D6RSourceError("D6R TRAIN_ONLY episode custody is mismatched")
    d5s_run = root / "webui" / "rl_runs" / "rl_discovery" / prereg.source.d5s_run
    _ = verified_bytes(
        d5s_run / "summary.json",
        expected_sha256=prereg.source.d5s_summary_sha256,
        anchor=root,
    )
    _ = verified_bytes(
        d5s_run / "terminal_receipt.json",
        expected_sha256=prereg.source.d5s_terminal_receipt_sha256,
        anchor=root,
    )
    digest = artifact_manifest_sha256(
        d5s_run,
        excluded_relative_paths=frozenset({"terminal_receipt.json"}),
    )
    if digest != prereg.source.d5s_artifact_manifest_sha256:
        raise D6RSourceError("D6R D5S source artifact manifest is mismatched")
    episode_sha = d5s_source.prereg.source_run.episode_snapshot_sha256
    return D6RSourceBundle(
        prereg,
        prereg_bytes,
        hashlib.sha256(prereg_bytes).hexdigest(),
        d5s_source.episodes,
        episode_sha,
        (
            ("d5s_artifact_manifest", digest),
            ("d5s_prereg", d5s_source.prereg_sha256),
            ("d6_custody_document", prereg.prior_d6.custody_document_sha256),
            ("d6_result_document", prereg.prior_d6.result_document_sha256),
            ("episode_snapshot", episode_sha),
        ),
    )
