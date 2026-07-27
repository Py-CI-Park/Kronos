"""Path-confined and crash-resistant storage for discovery evidence."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from typing import Protocol, TypeAlias

from typing_extensions import override

JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


class Saveable(Protocol):
    """Artifact that can persist itself to one explicit file path."""

    def save(self, path: str) -> None: ...


@dataclass(slots=True)  # Exception owns mutable traceback state.
class UnsafeArtifactPathError(ValueError):
    """Raised when an artifact path escapes or redirects its configured root."""

    path: Path
    reason: str

    @override
    def __str__(self) -> str:
        return f"unsafe artifact path {self.path}: {self.reason}"


def _is_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(attributes & reparse_flag)


def _safe_segment(value: str) -> str:
    if value in {"", ".", ".."} or Path(value).name != value:
        raise UnsafeArtifactPathError(Path(value), "segment must be a direct child name")
    return value


def create_run_directory(run_root: Path, run_id: str) -> Path:
    """Create one direct, non-reparse child beneath the canonical run root."""

    root = run_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    run_dir = root / _safe_segment(run_id)
    run_dir.mkdir(exist_ok=False)
    if _is_reparse_point(run_dir):
        raise UnsafeArtifactPathError(run_dir, "run directory cannot be a reparse point")
    return run_dir


def validate_run_directory(run_root: Path, candidate: Path) -> Path:
    """Return a canonical direct run child or fail closed."""

    root = run_root.resolve()
    supplied = candidate.absolute()
    if supplied.parent.resolve() != root or supplied.name in {"", ".", ".."}:
        raise UnsafeArtifactPathError(candidate, "run directory must be a direct child")
    if not supplied.is_dir() or _is_reparse_point(supplied):
        raise UnsafeArtifactPathError(candidate, "run directory is missing or redirected")
    resolved = supplied.resolve()
    if resolved.parent != root:
        raise UnsafeArtifactPathError(candidate, "resolved run directory escapes run root")
    return resolved


def contained_path(run_dir: Path, *segments: str) -> Path:
    """Resolve a path whose every segment remains inside a trusted run directory."""

    root = run_dir.resolve()
    candidate = root.joinpath(*(_safe_segment(segment) for segment in segments))
    cursor = root
    for segment in segments[:-1]:
        cursor /= segment
        if cursor.exists() and _is_reparse_point(cursor):
            raise UnsafeArtifactPathError(cursor, "artifact parent cannot be a reparse point")
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise UnsafeArtifactPathError(candidate, "resolved artifact escapes run directory")
    if candidate.exists() and _is_reparse_point(candidate):
        raise UnsafeArtifactPathError(candidate, "artifact cannot be a reparse point")
    return candidate


def atomic_write_json(path: Path, payload: JsonValue) -> None:
    """Write JSON through an exclusive random sibling and fsync before replace."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            _ = handle.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


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
    if final_dir.exists():
        shutil.rmtree(final_dir)
    temporary = Path(tempfile.mkdtemp(prefix=f".seed-{seed}.", dir=arm_dir))
    try:
        model_path = temporary / "model.zip"
        normalizer_path = temporary / "normalizer.pkl"
        model.save(str(model_path))
        normalizer.save(str(normalizer_path))
        if not model_path.is_file() or not normalizer_path.is_file():
            raise UnsafeArtifactPathError(temporary, "model bundle is incomplete")
        _fsync_file(model_path)
        _fsync_file(normalizer_path)
        os.replace(temporary, final_dir)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
