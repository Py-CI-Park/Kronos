"""Deterministic, fail-closed manifests for supplied V5 QA trees."""
from __future__ import annotations

import gzip
import hashlib
import os
import stat
from pathlib import Path, PurePosixPath
import unicodedata
from typing import Any

import rfc8785


class ManifestError(ValueError):
    pass



_REPO_ROOT = Path(__file__).resolve().parents[1]
_TRACKED_DIST = (_REPO_ROOT / "webui" / "static" / "v2" / "dist").resolve(strict=False)
_FORBIDDEN_PATH_SEGMENTS = frozenset({"oos", "database", "db"})
_TRACKED_DIST_PARTS = ("webui", "static", "v2", "dist")
_REPARSE_FILE_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

def _canonical(value: Any) -> bytes:
    return rfc8785.dumps(value)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _casefold_parts(path: Path | PurePosixPath) -> tuple[str, ...]:
    return tuple(unicodedata.normalize("NFC", part).casefold() for part in path.parts)


def _contains_part_sequence(parts: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    if len(parts) < len(needle):
        return False
    return any(parts[index:index + len(needle)] == needle for index in range(len(parts) - len(needle) + 1))


def _is_forbidden_relative_path(path: str | Path | PurePosixPath) -> bool:
    relative = PurePosixPath(path) if isinstance(path, str) else path
    parts = _casefold_parts(relative)
    return _contains_part_sequence(parts, _TRACKED_DIST_PARTS) or any(part in _FORBIDDEN_PATH_SEGMENTS for part in parts)


def _is_forbidden_path(path: Path) -> bool:
    resolved = path.resolve(strict=False)
    return _is_forbidden_relative_path(path) or _is_forbidden_relative_path(resolved) or _is_relative_to(resolved, _TRACKED_DIST)


def _is_symlink_junction_or_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
    except OSError:
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None:
        try:
            if is_junction():
                return True
        except OSError:
            return True
    if os.name == "nt":
        try:
            return bool(os.lstat(path).st_file_attributes & _REPARSE_FILE_ATTRIBUTE)
        except FileNotFoundError:
            return False
        except (AttributeError, OSError):
            return True
    return False


def _has_symlink_junction_or_reparse_ancestor(path: Path) -> bool:
    return any(_is_symlink_junction_or_reparse(ancestor) for ancestor in (path, *path.parents))


def _reject_symlinked_ancestors(path: Path) -> None:
    if _has_symlink_junction_or_reparse_ancestor(path):
        raise ManifestError("symlinked/reparse manifest root ancestor is forbidden")


def _reject_forbidden_root(path: Path) -> None:
    if _is_forbidden_path(path):
        raise ManifestError("tracked dist/OOS/database/db manifest paths are forbidden")


def _manifest_relative_path(base: Path, item: Path) -> str:
    relative = item.relative_to(base).as_posix()
    canonical_name = unicodedata.normalize("NFC", relative)
    parts = PurePosixPath(canonical_name).parts
    if not canonical_name or canonical_name.startswith("/") or ".." in parts or "." in parts:
        raise ManifestError("path traversal is forbidden")
    if _is_forbidden_relative_path(PurePosixPath(canonical_name)):
        raise ManifestError("tracked dist/OOS/database/db manifest descendants are forbidden")
    return canonical_name


def _raise_walk_error(exc: OSError) -> None:
    raise ManifestError("manifest tree is not readable") from exc


def _validated_entry_files(base: Path) -> list[Path]:
    entry_files: list[Path] = []
    for current, directories, files in os.walk(base, followlinks=False, onerror=_raise_walk_error):
        current_path = Path(current)
        if _is_symlink_junction_or_reparse(current_path):
            raise ManifestError("symlinked/reparse directory is forbidden")
        if current_path != base:
            _manifest_relative_path(base, current_path)
        for directory in directories:
            directory_path = current_path / directory
            if _is_symlink_junction_or_reparse(directory_path):
                raise ManifestError("symlinked/reparse directory is forbidden")
            _manifest_relative_path(base, directory_path)
        for filename in files:
            item = current_path / filename
            if _is_symlink_junction_or_reparse(item) or not item.is_file():
                raise ManifestError("symlink/reparse or non-regular file is forbidden")
            _manifest_relative_path(base, item)
            entry_files.append(item)
    return entry_files


def _root(value: str | Path) -> Path:
    path = Path(value)
    if ".." in path.parts:
        raise ManifestError("path traversal is forbidden")
    candidate = path if path.is_absolute() else Path.cwd() / path
    _reject_symlinked_ancestors(candidate)
    if not candidate.exists() or not candidate.is_dir():
        raise ManifestError("manifest root must be an existing non-symlink/reparse directory")
    resolved = candidate.resolve(strict=True)
    _reject_forbidden_root(candidate)
    _reject_forbidden_root(resolved)
    return resolved


def _entries(root: str | Path) -> list[dict[str, Any]]:
    base = _root(root)
    rows: list[dict[str, Any]] = []
    names: set[str] = set()
    for item in _validated_entry_files(base):
        if _is_symlink_junction_or_reparse(item) or not item.is_file():
            raise ManifestError("symlink/reparse or non-regular file is forbidden")
        canonical_name = _manifest_relative_path(base, item)
        # Casefold makes output portable across the supported browser/build hosts.
        collision_key = canonical_name.casefold()
        if collision_key in names:
            raise ManifestError("portable output path collision")
        names.add(collision_key)
        raw = item.read_bytes()
        gz = gzip.compress(raw, compresslevel=9, mtime=0)
        rows.append({"path": canonical_name, "sha256": _sha(raw), "byte_length": len(raw),
                     "gzip9_byte_length": len(gz), "browser_transfer_byte_length": len(gz)})
    return sorted(rows, key=lambda row: row["path"].encode("utf-8"))


def _manifest(schema: str, root: str | Path) -> dict[str, Any]:
    entries = _entries(root)
    if not entries:
        raise ManifestError("manifest root must contain at least one regular file")
    raw_byte_length = sum(row["byte_length"] for row in entries)
    gzip9_byte_length = sum(row["gzip9_byte_length"] for row in entries)
    browser_transfer_byte_length = sum(row["browser_transfer_byte_length"] for row in entries)
    content = {
        "schema": schema,
        "entries": entries,
        "raw_byte_length": raw_byte_length,
        "gzip9_byte_length": gzip9_byte_length,
        "browser_transfer_byte_length": browser_transfer_byte_length,
    }
    raw = _canonical(content)
    return {**content, "manifest_sha256": _sha(raw)}


def build_source_manifest(source_root: str | Path) -> dict[str, Any]:
    return _manifest("kronos_source_manifest.v1", source_root)


def build_bundle_manifest(bundle_root: str | Path) -> dict[str, Any]:
    return _manifest("kronos_bundle_manifest.v1", bundle_root)


def build_dist_manifest(dist_root: str | Path) -> dict[str, Any]:
    return _manifest("kronos_dist_manifest.v1", dist_root)
