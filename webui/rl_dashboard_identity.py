"""Stable run identity with stat-keyed content-hash caching."""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
from typing import TypedDict
import uuid

if __package__:
    from . import rl_dashboard_files as _files
    from .rl_dashboard_files import RlDashboardPathError
else:  # pragma: no cover - direct script-style import
    from webui import rl_dashboard_files as _files
    from webui.rl_dashboard_files import RlDashboardPathError

RUN_IDENTITY_PROTOCOL = "stom_rl_dashboard_run_identity.v1"
_RUN_UID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, RUN_IDENTITY_PROTOCOL)
_SOURCE_HASH_CHUNK_BYTES = 1024 * 1024
_REVISION_CONTENT_BUCKETS = 1_048_576


class ArtifactIdentityFile(TypedDict):
    """Content identity for one run artifact."""

    path: str
    size_bytes: int
    sha256: str


class RunIdentityFields(TypedDict):
    """Public stable identity fields added to one dashboard run."""

    run_uid: str
    revision: int
    source_sha256: str
    source_protocol: str


def canonical_path_id(path: Path) -> str:
    value = path.resolve().as_posix()
    return value.lower() if os.name == "nt" else value


def _canonical_run_locator(run_dir: Path) -> dict[str, str]:
    run_resolved = run_dir.resolve()
    for root in _files.RL_RUN_ROOTS:
        root_path = Path(root)
        root_resolved = root_path.resolve()
        if run_resolved == root_resolved or root_resolved in run_resolved.parents:
            relative_path = run_resolved.relative_to(root_resolved).as_posix()
            return {
                "root": canonical_path_id(root_path),
                "path": canonical_path_id(run_dir),
                "relative_path": relative_path or ".",
            }
    raise RlDashboardPathError(f"Invalid run: resolved path escapes RL root: {run_dir.name!r}")


def hash_file_content(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_length = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_SOURCE_HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
            byte_length += len(chunk)
    return digest.hexdigest(), byte_length


@lru_cache(maxsize=4096)
def _cached_content_hash(
    path_text: str,
    size_bytes: int,
    modified_ns: int,
    changed_ns: int,
) -> tuple[str, int]:
    _ = size_bytes, modified_ns, changed_ns
    return hash_file_content(Path(path_text))


def clear_identity_cache() -> None:
    """Clear stat-keyed hashes for tests and explicit cache invalidation."""

    _cached_content_hash.cache_clear()


def _artifact_paths(run_dir: Path) -> list[Path]:
    """Walk contained files without resolving every leaf on Windows."""

    root = run_dir.resolve()
    pending = [root]
    files: list[Path] = []
    while pending:
        current = pending.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                if entry.is_symlink():
                    continue
                path = Path(entry.path)
                if entry.is_dir(follow_symlinks=False):
                    if path.resolve().is_relative_to(root):
                        pending.append(path)
                elif entry.is_file(follow_symlinks=False):
                    files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def artifact_snapshot(run_dir: Path) -> tuple[list[ArtifactIdentityFile], int]:
    """Build a deterministic manifest while reusing unchanged content hashes."""

    root = run_dir.resolve()
    files: list[ArtifactIdentityFile] = []
    revision_ns = root.stat().st_mtime_ns
    for path in _artifact_paths(root):
        stat_result = path.stat()
        content_sha256, size_bytes = _cached_content_hash(
            str(path.resolve()),
            stat_result.st_size,
            stat_result.st_mtime_ns,
            stat_result.st_ctime_ns,
        )
        revision_ns = max(revision_ns, stat_result.st_mtime_ns)
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": size_bytes,
                "sha256": content_sha256,
            }
        )
    return files, revision_ns


def _revision_from_snapshot(max_mtime_ns: int, source_sha256: str) -> int:
    mtime_seconds = max(0, max_mtime_ns // 1_000_000_000)
    content_component = int(source_sha256[:5], 16)
    return max(1, (mtime_seconds * _REVISION_CONTENT_BUCKETS) + content_component + 1)


def run_identity_fields(run_dir: Path) -> RunIdentityFields:
    """Return stable run identity fields from a cached content manifest."""

    locator = _canonical_run_locator(run_dir)
    files, revision_ns = artifact_snapshot(run_dir)
    source_manifest = {"schema": RUN_IDENTITY_PROTOCOL, "files": files}
    source_bytes = json.dumps(
        source_manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    locator_text = json.dumps(locator, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return {
        "run_uid": str(uuid.uuid5(_RUN_UID_NAMESPACE, locator_text)),
        "revision": _revision_from_snapshot(revision_ns, source_sha256),
        "source_sha256": source_sha256,
        "source_protocol": RUN_IDENTITY_PROTOCOL,
    }
