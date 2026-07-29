"""Custody-bound D4 input loading over the frozen D3 episode universe."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d2_custody import assert_plain_path, held_bytes, verified_bytes, verified_text_stream
from stom_rl.rl_discovery.d2_data import iter_json_array, load_scales_bytes
from stom_rl.rl_discovery.d3_data import D3SourceRow, build_top_k_episodes
from stom_rl.rl_discovery.d3_env import D3Episode
from stom_rl.rl_discovery.d4_contract import D4Preregistration, load_d4_prereg_bytes


class D4InputError(ValueError):
    """A custody-bound D4 input does not match its registered identity."""


@dataclass(frozen=True, slots=True)
class D4InputBundle:
    prereg: D4Preregistration
    prereg_bytes: bytes
    prereg_sha256: str
    episodes: tuple[D3Episode, ...]
    episode_bytes: bytes
    episode_sha256: str
    input_hashes: dict[str, str]


def load_d4_inputs(repo_root: Path) -> D4InputBundle:
    """Verify D4 preregistration and rebuild the exact train-only episode snapshot."""

    root = repo_root.absolute()
    prereg_path = root / "docs" / "kronos_rl_discovery_type2_d4_prereg_2026-07-29.json"
    if not prereg_path.exists():
        raise FileNotFoundError(prereg_path)
    prereg_bytes = held_bytes(prereg_path, anchor=root)
    prereg = load_d4_prereg_bytes(prereg_bytes)
    rows = (root / prereg.dataset.rows_relative_path).absolute()
    normalizer = (root / prereg.dataset.normalizer_relative_path).absolute()
    manifest = rows.parent / "dataset_manifest.json"
    receipt = rows.parent / "materializer_complete_receipt.json"
    for path in (rows, normalizer, manifest, receipt):
        assert_plain_path(path, anchor=root, require_file=True)
    normalizer_bytes = verified_bytes(normalizer, expected_sha256=prereg.dataset.normalizer_file_sha256, anchor=root)
    if json.loads(normalizer_bytes).get("digest") != prereg.dataset.normalizer_digest:
        raise D4InputError("D4 normalizer digest mismatch")
    input_hashes = {
        "rows": prereg.dataset.rows_sha256,
        "manifest": _verified_hash(manifest, prereg.dataset.manifest_sha256, root),
        "materializer_receipt": _verified_hash(receipt, prereg.dataset.materializer_receipt_sha256, root),
        "normalizer": hashlib.sha256(normalizer_bytes).hexdigest(),
    }
    with verified_text_stream(rows, expected_sha256=prereg.dataset.rows_sha256, anchor=root) as stream:
        parsed_rows = (D3SourceRow.model_validate(row) for row in iter_json_array(stream))
        episodes = build_top_k_episodes(parsed_rows, scales=load_scales_bytes(normalizer_bytes), limit=128)
    episode_bytes = canonical_json_bytes([asdict(episode) for episode in episodes])
    return D4InputBundle(
        prereg=prereg,
        prereg_bytes=prereg_bytes,
        prereg_sha256=hashlib.sha256(prereg_bytes).hexdigest(),
        episodes=episodes,
        episode_bytes=episode_bytes,
        episode_sha256=hashlib.sha256(episode_bytes).hexdigest(),
        input_hashes=input_hashes,
    )


def _verified_hash(path: Path, expected: str, root: Path) -> str:
    payload = verified_bytes(path, expected_sha256=expected, anchor=root)
    return hashlib.sha256(payload).hexdigest()
