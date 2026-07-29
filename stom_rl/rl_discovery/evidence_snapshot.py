"""Consistent held-handle snapshots for coupled research evidence."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path

from stom_rl.rl_discovery.d2_custody import assert_plain_path, held_binary


@dataclass(frozen=True, slots=True)
class EvidenceSnapshot:
    """Selected bytes and the manifest digest computed from the same handles."""

    captured: dict[str, bytes]
    manifest_sha256: str
    relative_paths: frozenset[str]


def read_evidence_snapshot(
    run_dir: Path,
    *,
    capture_paths: frozenset[str],
    excluded_manifest_paths: frozenset[str] = frozenset(),
) -> EvidenceSnapshot:
    """Lock every artifact, verify stable identities, then parse/hash one snapshot."""

    root = run_dir.absolute()
    assert_plain_path(root, anchor=root.parent, require_file=False)
    paths = _regular_artifacts(root)
    relative_paths = frozenset(path.relative_to(root).as_posix() for path in paths)
    if not capture_paths <= relative_paths:
        raise FileNotFoundError("required evidence artifact is missing")

    entries: list[dict[str, int | str]] = []
    captured: dict[str, bytes] = {}
    with ExitStack() as stack:
        handles = {
            path: stack.enter_context(held_binary(path, anchor=root))
            for path in paths
        }
        if _artifact_names(root) != relative_paths:
            raise PermissionError("evidence inventory changed while acquiring snapshot")
        for path, handle in handles.items():
            relative = path.relative_to(root).as_posix()
            path_stat = os.stat(path, follow_symlinks=False)
            handle_stat = os.fstat(handle.fileno())
            if (path_stat.st_dev, path_stat.st_ino) != (handle_stat.st_dev, handle_stat.st_ino):
                raise PermissionError("evidence path identity changed during snapshot")
            payload = handle.read()
            if relative in capture_paths:
                captured[relative] = payload
            if relative not in excluded_manifest_paths:
                entries.append(
                    {
                        "path": relative,
                        "size_bytes": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }
                )
        if _artifact_names(root) != relative_paths:
            raise PermissionError("evidence inventory changed while reading snapshot")
    encoded = json.dumps(entries, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return EvidenceSnapshot(captured, hashlib.sha256(encoded).hexdigest(), relative_paths)


def _regular_artifacts(root: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        assert_plain_path(path, anchor=root, require_file=path.is_file())
        if path.is_dir():
            continue
        if not path.is_file():
            raise PermissionError("evidence inventory contains a non-regular artifact")
        paths.append(path)
    return tuple(paths)


def _artifact_names(root: Path) -> frozenset[str]:
    return frozenset(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    )
