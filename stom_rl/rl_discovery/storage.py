"""Path-confined and crash-resistant storage for discovery evidence."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from typing import Protocol, TypeAlias, final

from typing_extensions import override

from stom_rl.rl_discovery.atomic_storage import atomic_write_bytes
from stom_rl.rl_discovery.atomic_storage import atomic_write_json as _atomic_write_json
from stom_rl.rl_discovery.directory_lease import (
    locked_artifact_parent,
    locked_directory,
)

atomic_write_json = _atomic_write_json

JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)


class Saveable(Protocol):
    """Artifact that can persist itself to one explicit file path."""

    def save(self, path: str) -> None: ...


@final
class UnsafeArtifactPathError(ValueError):
    """Raised when an artifact path escapes or redirects its configured root."""

    __slots__: tuple[str, str] = ("path", "reason")
    path: Path
    reason: str

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(path, reason)
        self.path = path
        self.reason = reason

    @override
    def __str__(self) -> str:
        return f"unsafe artifact path {self.path}: {self.reason}"


@dataclass(frozen=True, slots=True)
class RunDirectoryGuard:
    """Stable direct-child identity for a research run directory."""

    run_root: Path
    run_dir: Path
    device: int
    inode: int

    @classmethod
    def capture(cls, run_root: Path, run_dir: Path) -> RunDirectoryGuard:
        root = run_root.absolute()
        if not root.is_dir() or _is_reparse_point(root):
            raise UnsafeArtifactPathError(root, "run root must be a plain directory")
        candidate = validate_run_directory(root, run_dir)
        identity = os.stat(candidate, follow_symlinks=False)
        return cls(
            root.resolve(), candidate.absolute(), identity.st_dev, identity.st_ino
        )

    def verify(self) -> Path:
        """Return the original run directory only while its identity is stable."""

        if _is_reparse_point(self.run_root):
            raise UnsafeArtifactPathError(
                self.run_root, "run root became a reparse point"
            )
        candidate = validate_run_directory(self.run_root, self.run_dir)
        identity = os.stat(candidate, follow_symlinks=False)
        if (identity.st_dev, identity.st_ino) != (self.device, self.inode):
            raise UnsafeArtifactPathError(candidate, "run directory identity changed")
        return candidate

    def locked(self) -> AbstractContextManager[Path]:
        return locked_directory(
            self.run_dir,
            expected_device=self.device,
            expected_inode=self.inode,
        )

    def publish_bytes(self, payload: bytes, *segments: str) -> Path:
        if not segments:
            raise UnsafeArtifactPathError(self.run_dir, "artifact path is required")
        with self.locked_parent(*segments[:-1]) as locked_parent:
            target = contained_path(locked_parent, segments[-1])
            atomic_write_bytes(target, payload)
            return self.run_dir.joinpath(*segments)

    def locked_parent(
        self,
        *segments: str,
        exclusive_leaf: bool = False,
    ) -> AbstractContextManager[Path]:
        return locked_artifact_parent(
            self.run_dir,
            segments,
            expected_device=self.device,
            expected_inode=self.inode,
            exclusive_leaf=exclusive_leaf,
        )


def _is_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(attributes & reparse_flag)


def _safe_segment(value: str) -> str:
    if value in {"", ".", ".."} or Path(value).name != value:
        raise UnsafeArtifactPathError(
            Path(value), "segment must be a direct child name"
        )
    return value


def create_run_directory(run_root: Path, run_id: str) -> Path:
    """Create one direct, non-reparse child beneath the canonical run root."""

    root = run_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    run_dir = root / _safe_segment(run_id)
    run_dir.mkdir(exist_ok=False)
    if _is_reparse_point(run_dir):
        raise UnsafeArtifactPathError(
            run_dir, "run directory cannot be a reparse point"
        )
    return run_dir


def validate_run_directory(run_root: Path, candidate: Path) -> Path:
    """Return a canonical direct run child or fail closed."""

    root = run_root.resolve()
    supplied = candidate.absolute()
    if supplied.parent.resolve() != root or supplied.name in {"", ".", ".."}:
        raise UnsafeArtifactPathError(candidate, "run directory must be a direct child")
    if not supplied.is_dir() or _is_reparse_point(supplied):
        raise UnsafeArtifactPathError(
            candidate, "run directory is missing or redirected"
        )
    resolved = supplied.resolve()
    if resolved.parent != root:
        raise UnsafeArtifactPathError(
            candidate, "resolved run directory escapes run root"
        )
    return resolved


def contained_path(run_dir: Path, *segments: str) -> Path:
    """Resolve a path whose every segment remains inside a trusted run directory."""

    supplied = run_dir.absolute()
    if not supplied.is_dir() or _is_reparse_point(supplied):
        raise UnsafeArtifactPathError(
            supplied, "run directory cannot be a reparse point"
        )
    before = os.stat(supplied, follow_symlinks=False)
    root = supplied.resolve(strict=True)
    candidate = supplied.joinpath(*(_safe_segment(segment) for segment in segments))
    cursor = supplied
    for segment in segments[:-1]:
        cursor /= segment
        if cursor.exists() and _is_reparse_point(cursor):
            raise UnsafeArtifactPathError(
                cursor, "artifact parent cannot be a reparse point"
            )
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise UnsafeArtifactPathError(
            candidate, "resolved artifact escapes run directory"
        )
    if candidate.exists() and _is_reparse_point(candidate):
        raise UnsafeArtifactPathError(candidate, "artifact cannot be a reparse point")
    after = os.stat(supplied, follow_symlinks=False)
    if (before.st_dev, before.st_ino) != (
        after.st_dev,
        after.st_ino,
    ) or _is_reparse_point(supplied):
        raise UnsafeArtifactPathError(supplied, "run directory identity changed")
    return candidate


def file_digest(path: Path) -> tuple[str, int]:
    """Return a streaming SHA-256 and exact byte length."""

    digest = hashlib.sha256()
    size_bytes = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size_bytes += len(chunk)
    return digest.hexdigest(), size_bytes


def artifact_manifest_sha256(
    run_dir: Path,
    *,
    excluded_relative_paths: frozenset[str] | None = None,
) -> str:
    """Hash every regular, non-reparse artifact in a run with path and size."""

    exclusions = excluded_relative_paths or frozenset()
    walk_root = run_dir.absolute()
    _ = walk_root.resolve(strict=True)
    if _is_reparse_point(walk_root):
        raise UnsafeArtifactPathError(
            run_dir, "run directory cannot be a reparse point"
        )
    entries: list[dict[str, int | str]] = []
    for path in sorted(
        walk_root.rglob("*"), key=lambda item: item.relative_to(walk_root).as_posix()
    ):
        relative = path.relative_to(walk_root)
        if relative.as_posix() in exclusions:
            continue
        cursor = walk_root
        for segment in relative.parts:
            cursor /= segment
            if _is_reparse_point(cursor):
                raise UnsafeArtifactPathError(
                    cursor, "manifest cannot include a reparse point"
                )
        if path.is_dir():
            continue
        if not path.is_file():
            raise UnsafeArtifactPathError(path, "manifest entry must be a regular file")
        sha256, size_bytes = file_digest(path)
        entries.append(
            {"path": relative.as_posix(), "size_bytes": size_bytes, "sha256": sha256}
        )
    encoded = json.dumps(entries, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fsync_file(path: Path) -> None:
    with path.open("r+b") as handle:
        os.fsync(handle.fileno())


def write_model_bundle(
    run_dir: Path,
    *,
    arm: str,
    seed: int,
    model: Saveable,
    normalizer: Saveable,
) -> None:
    """Publish a complete model directory only after both files are durable."""

    arm_dir = contained_path(run_dir, "models", arm)
    arm_dir.mkdir(parents=True, exist_ok=True)
    final_dir = contained_path(run_dir, "models", arm, f"seed-{seed}")
    temporary = Path(tempfile.mkdtemp(prefix=f".seed-{seed}.", dir=arm_dir))
    backup = Path(tempfile.mkdtemp(prefix=f".seed-{seed}.backup.", dir=arm_dir))
    backup.rmdir()
    try:
        model_path = temporary / "model.zip"
        normalizer_path = temporary / "normalizer.pkl"
        model.save(str(model_path))
        normalizer.save(str(normalizer_path))
        if not model_path.is_file() or not normalizer_path.is_file():
            raise UnsafeArtifactPathError(temporary, "model bundle is incomplete")
        _fsync_file(model_path)
        _fsync_file(normalizer_path)
        if final_dir.exists():
            os.replace(final_dir, backup)
        try:
            os.replace(temporary, final_dir)
        except OSError:
            if backup.exists() and not final_dir.exists():
                os.replace(backup, final_dir)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup.exists() and final_dir.exists():
            shutil.rmtree(backup)
