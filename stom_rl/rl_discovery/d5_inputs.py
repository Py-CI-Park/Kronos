"""Custody-bound D5 full train-only input materialization."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path

from pydantic import JsonValue, TypeAdapter

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d2_custody import assert_plain_path, held_bytes, verified_bytes, verified_text_stream
from stom_rl.rl_discovery.d2_data import iter_json_array, load_scales_bytes
from stom_rl.rl_discovery.d3_data import D3SourceRow, build_top_k_episodes
from stom_rl.rl_discovery.d3_env import D3Episode
from stom_rl.rl_discovery.d5_contract import D5Preregistration, load_d5_prereg_bytes

_JSON_OBJECT = TypeAdapter(dict[str, JsonValue])


class D5InputError(ValueError):
    """D5 input evidence does not match the registered identity."""


@dataclass(frozen=True, slots=True)
class D5InputBundle:
    prereg: D5Preregistration
    prereg_bytes: bytes
    prereg_sha256: str
    episodes: tuple[D3Episode, ...]
    episode_bytes: bytes
    episode_sha256: str
    input_hashes: dict[str, str]


def load_d5_inputs(repo_root: Path) -> D5InputBundle:
    """Verify source custody and materialize all 573 eligible train sessions."""

    root = repo_root.absolute()
    prereg_path = root / "docs/kronos_rl_discovery_type2_d5_prereg_2026-07-29.json"
    if not prereg_path.is_file():
        raise FileNotFoundError(prereg_path)
    prereg_bytes = held_bytes(prereg_path, anchor=root)
    prereg = load_d5_prereg_bytes(prereg_bytes)
    rows = (root / prereg.dataset.rows_relative_path).absolute()
    normalizer = (root / prereg.dataset.normalizer_relative_path).absolute()
    manifest = rows.parent / "dataset_manifest.json"
    receipt = rows.parent / "materializer_complete_receipt.json"
    for path in (rows, normalizer, manifest, receipt):
        _ = assert_plain_path(path, anchor=root, require_file=True)
    normalizer_bytes = verified_bytes(normalizer, expected_sha256=prereg.dataset.normalizer_file_sha256, anchor=root)
    if _JSON_OBJECT.validate_json(normalizer_bytes).get("digest") != prereg.dataset.normalizer_digest:
        raise D5InputError("D5 normalizer digest mismatch")
    with verified_text_stream(rows, expected_sha256=prereg.dataset.rows_sha256, anchor=root) as stream:
        parsed = (D3SourceRow.model_validate(row) for row in iter_json_array(stream))
        episodes = build_top_k_episodes(parsed, scales=load_scales_bytes(normalizer_bytes), limit=573)
    if len(episodes) != prereg.episode_count:
        raise D5InputError("D5 episode count mismatch")
    episode_bytes = canonical_json_bytes([asdict(episode) for episode in episodes])
    hashes = {
        "rows": prereg.dataset.rows_sha256,
        "manifest": _verified_hash(manifest, prereg.dataset.manifest_sha256, root),
        "materializer_receipt": _verified_hash(receipt, prereg.dataset.materializer_receipt_sha256, root),
        "normalizer": hashlib.sha256(normalizer_bytes).hexdigest(),
    }
    return D5InputBundle(prereg, prereg_bytes, hashlib.sha256(prereg_bytes).hexdigest(), episodes, episode_bytes, hashlib.sha256(episode_bytes).hexdigest(), hashes)


def _verified_hash(path: Path, expected: str, root: Path) -> str:
    return hashlib.sha256(verified_bytes(path, expected_sha256=expected, anchor=root)).hexdigest()
