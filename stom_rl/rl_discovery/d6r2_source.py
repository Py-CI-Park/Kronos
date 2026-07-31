"""Custody-bound preregistration and raw TRAIN_ONLY source for D6R2."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from stom_rl.rl_discovery.d2_custody import held_bytes, verified_bytes
from stom_rl.rl_discovery.d6r2_contract import D6R2Preregistration, load_d6r2_prereg_bytes
from stom_rl.rl_discovery.d6r2_data import D6R2RawSource, load_d6r2_raw_source


class D6R2SourceError(ValueError):
    """D6R2 source custody differs from the frozen preregistration."""


@dataclass(frozen=True, slots=True)
class D6R2SourceBundle:
    prereg: D6R2Preregistration
    prereg_bytes: bytes
    prereg_sha256: str
    raw: D6R2RawSource


def load_d6r2_source(repo_root: Path) -> D6R2SourceBundle:
    root = repo_root.absolute()
    prereg_bytes = held_bytes(root / "docs/kronos_rl_discovery_type2_d6r2_prereg_2026-07-31.json", anchor=root)
    prereg = load_d6r2_prereg_bytes(prereg_bytes)
    for relative, expected in (
        ("docs/kronos_rl_discovery_type2_d6r_prereg_2026-07-31.json", prereg.source.d6r_prereg_sha256),
        ("docs/kronos_rl_discovery_type2_d6r_result_2026-07-31.md", prereg.source.d6r_result_sha256),
        ("docs/evidence/type2-d6r-primary-20260731-001.custody.json", prereg.source.d6r_custody_sha256),
    ):
        _ = verified_bytes(root / relative, expected_sha256=expected, anchor=root)
    raw = load_d6r2_raw_source(root)
    if raw.rows_sha256 != prereg.source.rows_sha256 or raw.episode_identity_sha256 != prereg.source.episode_identity_sha256:
        raise D6R2SourceError("D6R2 raw source identity is mismatched")
    return D6R2SourceBundle(prereg, prereg_bytes, hashlib.sha256(prereg_bytes).hexdigest(), raw)

