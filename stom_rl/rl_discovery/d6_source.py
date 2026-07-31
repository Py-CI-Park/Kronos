"""Custody-bound source loader for D6 reused validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, JsonValue, TypeAdapter

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d2_custody import (
    assert_plain_path,
    held_bytes,
    verified_bytes,
    verified_text_stream,
)
from stom_rl.rl_discovery.d2_data import iter_json_array, load_scales_bytes
from stom_rl.rl_discovery.d3_data import D3SourceRow
from stom_rl.rl_discovery.d3_env import D3Episode
from stom_rl.rl_discovery.d6_contract import D6Preregistration, load_d6_prereg_bytes
from stom_rl.rl_discovery.d6_data import build_reused_validation_episodes
from stom_rl.rl_discovery.storage import artifact_manifest_sha256

_JSON_OBJECT = TypeAdapter(dict[str, JsonValue])
_EPISODES = TypeAdapter(tuple[D3Episode, ...])


class D6SourceError(ValueError):
    """D6 source artifacts do not match the frozen preregistration."""


class _FailedReceipt(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_version: Literal["kronos.rl-discovery.d6.receipt.v1"]
    profile: Literal["PRIMARY"]
    status: Literal["FAILED"]
    verdict: Literal["NO_GO"]
    error_type: str
    reused_validation: Literal["FAILED"]
    fresh_oos: Literal["NOT_RUN_NO_READ"]
    live_broker_order_allowed: Literal[False]


@dataclass(frozen=True, slots=True)
class D6ModelArtifact:
    reward_arm: Literal["NATIVE", "SHUFFLED"]
    seed: int
    path: Path
    sha256: str


@dataclass(frozen=True, slots=True)
class D6SourceBundle:
    prereg: D6Preregistration
    prereg_bytes: bytes
    prereg_sha256: str
    validation_episodes: tuple[D3Episode, ...]
    validation_bytes: bytes
    validation_sha256: str
    models: tuple[D6ModelArtifact, ...]
    input_hashes: tuple[tuple[str, str], ...]
    validation_origin: Literal["FROZEN_DATASET", "FAILED_RUN_SNAPSHOT"]
    recovery_run: str | None


def load_d6_source(
    repo_root: Path,
    *,
    recovery_run: Path | None = None,
) -> D6SourceBundle:
    """Verify D5S models and materialize the preregistered validation prefix once."""

    root = repo_root.absolute()
    prereg_path = root / "docs/kronos_rl_discovery_type2_d6_prereg_2026-07-31.json"
    prereg_bytes = held_bytes(prereg_path, anchor=root)
    prereg = load_d6_prereg_bytes(prereg_bytes)
    run_dir = root / "webui/rl_runs/rl_discovery" / prereg.source_run.run_name
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
    manifest = artifact_manifest_sha256(
        run_dir,
        excluded_relative_paths=frozenset({"terminal_receipt.json"}),
    )
    if manifest != prereg.source_run.artifact_manifest_sha256:
        raise D6SourceError("D6 source run manifest is mismatched")
    expected_models = {
        (arm, seed)
        for arm in prereg.source_run.reward_arms
        for seed in prereg.source_run.seeds
    }
    observed_models = {(model.reward_arm, model.seed) for model in prereg.source_run.models}
    if len(prereg.source_run.models) != prereg.source_run.model_count or observed_models != expected_models:
        raise D6SourceError("D6 source model matrix is incomplete")
    models = tuple(
        _verified_model(root, run_dir, model.reward_arm, model.seed, model.relative_path, model.sha256)
        for model in prereg.source_run.models
    )
    if recovery_run is None:
        episodes, validation_bytes, hashes = _load_validation(root, prereg)
        validation_origin: Literal["FROZEN_DATASET", "FAILED_RUN_SNAPSHOT"] = "FROZEN_DATASET"
        recovery_name = None
    else:
        episodes, validation_bytes = load_d6_recovery_validation(
            root,
            recovery_run,
            prereg_bytes=prereg_bytes,
            episode_count=prereg.dataset.episode_count,
        )
        hashes = _registered_input_hashes(prereg)
        validation_origin = "FAILED_RUN_SNAPSHOT"
        recovery_name = recovery_run.name
    return D6SourceBundle(
        prereg,
        prereg_bytes,
        hashlib.sha256(prereg_bytes).hexdigest(),
        episodes,
        validation_bytes,
        hashlib.sha256(validation_bytes).hexdigest(),
        models,
        hashes,
        validation_origin,
        recovery_name,
    )


def _verified_model(
    root: Path,
    run_dir: Path,
    reward_arm: Literal["NATIVE", "SHUFFLED"],
    seed: int,
    relative_path: str,
    sha256: str,
) -> D6ModelArtifact:
    path = run_dir.joinpath(*relative_path.split("/"))
    _ = verified_bytes(path, expected_sha256=sha256, anchor=root)
    return D6ModelArtifact(reward_arm, seed, path, sha256)


def _load_validation(
    root: Path,
    prereg: D6Preregistration,
) -> tuple[tuple[D3Episode, ...], bytes, tuple[tuple[str, str], ...]]:
    rows = root / prereg.dataset.rows_relative_path
    normalizer = root / prereg.dataset.normalizer_relative_path
    manifest = rows.parent / "dataset_manifest.json"
    receipt = rows.parent / "materializer_complete_receipt.json"
    for path in (rows, normalizer, manifest, receipt):
        _ = assert_plain_path(path, anchor=root, require_file=True)
    normalizer_bytes = verified_bytes(
        normalizer,
        expected_sha256=prereg.dataset.normalizer_file_sha256,
        anchor=root,
    )
    normalizer_payload = _JSON_OBJECT.validate_json(normalizer_bytes)
    if normalizer_payload.get("digest") != prereg.dataset.normalizer_digest:
        raise D6SourceError("D6 train-only normalizer digest is mismatched")
    with verified_text_stream(
        rows,
        expected_sha256=prereg.dataset.rows_sha256,
        anchor=root,
    ) as stream:
        parsed = (D3SourceRow.model_validate(row) for row in iter_json_array(stream))
        episodes = build_reused_validation_episodes(
            parsed,
            scales=load_scales_bytes(normalizer_bytes),
            limit=prereg.dataset.episode_count,
        )
    validation_bytes = canonical_json_bytes([asdict(episode) for episode in episodes])
    hashes = (
        ("rows", prereg.dataset.rows_sha256),
        ("manifest", _verified_hash(manifest, prereg.dataset.manifest_sha256, root)),
        (
            "materializer_receipt",
            _verified_hash(receipt, prereg.dataset.materializer_receipt_sha256, root),
        ),
        ("normalizer", hashlib.sha256(normalizer_bytes).hexdigest()),
    )
    return episodes, validation_bytes, hashes


def _verified_hash(path: Path, expected: str, root: Path) -> str:
    return hashlib.sha256(verified_bytes(path, expected_sha256=expected, anchor=root)).hexdigest()


def _registered_input_hashes(prereg: D6Preregistration) -> tuple[tuple[str, str], ...]:
    return (
        ("rows", prereg.dataset.rows_sha256),
        ("manifest", prereg.dataset.manifest_sha256),
        ("materializer_receipt", prereg.dataset.materializer_receipt_sha256),
        ("normalizer", prereg.dataset.normalizer_file_sha256),
    )


def load_d6_recovery_validation(
    repo_root: Path,
    recovery_run: Path,
    *,
    prereg_bytes: bytes,
    episode_count: int,
) -> tuple[tuple[D3Episode, ...], bytes]:
    root = repo_root.absolute()
    run = assert_plain_path(recovery_run, anchor=root, require_file=False)
    receipt = _FailedReceipt.model_validate_json(
        held_bytes(run / "terminal_receipt.json", anchor=root)
    )
    if not receipt.error_type:
        raise D6SourceError("D6 recovery receipt lacks an error type")
    recovered_prereg = held_bytes(run / "inputs/prereg.json", anchor=root)
    if recovered_prereg != prereg_bytes:
        raise D6SourceError("D6 recovery preregistration is mismatched")
    snapshot = held_bytes(run / "inputs/validation_episodes.json", anchor=root)
    episodes = _EPISODES.validate_json(snapshot)
    if len(episodes) != episode_count:
        raise D6SourceError("D6 recovery validation snapshot is incomplete")
    return episodes, snapshot
