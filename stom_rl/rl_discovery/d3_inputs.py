"""Custody-bound D3 input loading and episode snapshot construction."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d2_custody import assert_plain_path, held_bytes, verified_bytes, verified_text_stream
from stom_rl.rl_discovery.d2_data import iter_json_array, load_scales_bytes
from stom_rl.rl_discovery.d3_contract import D3Preregistration, load_d3_prereg_bytes
from stom_rl.rl_discovery.d3_data import D3SourceRow, build_top_k_episodes
from stom_rl.rl_discovery.d3_env import D3Episode


class D3InputError(ValueError):
    """A custody-bound D3 input does not match its registered identity."""


@dataclass(frozen=True, slots=True)
class D3InputBundle:
    """Verified preregistration, data identities, and frozen episode snapshot."""

    prereg: D3Preregistration
    prereg_bytes: bytes
    prereg_sha256: str
    episodes: tuple[D3Episode, ...]
    episode_bytes: bytes
    episode_sha256: str
    input_hashes: dict[str, str]


def load_d3_inputs(repo_root: Path) -> D3InputBundle:
    """Verify every registered input before consuming the train-only rows."""

    root = repo_root.absolute()
    prereg_path = root / "docs" / "kronos_rl_discovery_type2_d3_prereg_2026-07-29.json"
    if not prereg_path.exists():
        raise FileNotFoundError(prereg_path)
    assert_plain_path(prereg_path, anchor=root, require_file=True)
    prereg_bytes = held_bytes(prereg_path, anchor=root)
    prereg = load_d3_prereg_bytes(prereg_bytes)
    rows = (root / prereg.dataset.rows_relative_path).absolute()
    normalizer = (root / prereg.dataset.normalizer_relative_path).absolute()
    manifest = rows.parent / "dataset_manifest.json"
    materializer_receipt = rows.parent / "materializer_complete_receipt.json"
    for path in (rows, normalizer, manifest, materializer_receipt):
        assert_plain_path(path, anchor=root, require_file=True)
    normalizer_bytes = verified_bytes(normalizer, expected_sha256=prereg.dataset.normalizer_file_sha256, anchor=root)
    normalizer_payload = json.loads(normalizer_bytes)
    if normalizer_payload.get("digest") != prereg.dataset.normalizer_digest:
        raise D3InputError("D3 normalizer digest mismatch")
    input_hashes = {
        "rows": prereg.dataset.rows_sha256,
        "manifest": _verified_small_hash(manifest, prereg.dataset.manifest_sha256, root),
        "materializer_receipt": _verified_small_hash(materializer_receipt, prereg.dataset.materializer_receipt_sha256, root),
        "normalizer": hashlib.sha256(normalizer_bytes).hexdigest(),
    }
    with verified_text_stream(rows, expected_sha256=prereg.dataset.rows_sha256, anchor=root) as stream:
        parsed_rows = (D3SourceRow.model_validate(row) for row in iter_json_array(stream))
        episodes = build_top_k_episodes(parsed_rows, scales=load_scales_bytes(normalizer_bytes), limit=128)
    episode_bytes = canonical_json_bytes([asdict(episode) for episode in episodes])
    return D3InputBundle(
        prereg=prereg,
        prereg_bytes=prereg_bytes,
        prereg_sha256=hashlib.sha256(prereg_bytes).hexdigest(),
        episodes=episodes,
        episode_bytes=episode_bytes,
        episode_sha256=hashlib.sha256(episode_bytes).hexdigest(),
        input_hashes=input_hashes,
    )


def _verified_small_hash(path: Path, expected: str, root: Path) -> str:
    payload = verified_bytes(path, expected_sha256=expected, anchor=root)
    return hashlib.sha256(payload).hexdigest()
