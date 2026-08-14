"""Content-addressed file custody for daily-market authority evidence."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from .daily_market_authority_contract import (
    AuthorityFileIdentity,
    AuthorityInputBinding,
    AuthorityInputRole,
    DailyMarketAuthorityError,
)
from .daily_market_path_custody import has_reparse_component


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _consume_stable_file(
    path: Path,
    consume: Callable[[bytes], None],
    *,
    max_bytes: int | None = None,
) -> AuthorityFileIdentity:
    if has_reparse_component(path) or not path.is_file():
        raise DailyMarketAuthorityError("AUTHORITY_FILE_IDENTITY_UNTRUSTED", str(path))
    digest = hashlib.sha256()
    observed_bytes = 0
    with path.open("rb") as handle:
        descriptor_before = os.fstat(handle.fileno())
        if max_bytes is not None and descriptor_before.st_size > max_bytes:
            raise DailyMarketAuthorityError(
                "AUTHORITY_FILE_TOO_LARGE",
                str(path),
            )
        path_before = path.stat()
        if _stat_identity(descriptor_before) != _stat_identity(path_before):
            raise DailyMarketAuthorityError(
                "AUTHORITY_FILE_CHANGED_DURING_HASH",
                str(path),
            )
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            observed_bytes += len(chunk)
            consume(chunk)
        descriptor_after = os.fstat(handle.fileno())
        path_after = path.stat()
    descriptor_key = _stat_identity(descriptor_before)
    if (
        descriptor_key != _stat_identity(descriptor_after)
        or descriptor_key != _stat_identity(path_after)
        or observed_bytes != descriptor_after.st_size
    ):
        raise DailyMarketAuthorityError("AUTHORITY_FILE_CHANGED_DURING_HASH", str(path))
    return AuthorityFileIdentity(
        path_suffix=path.name,
        size_bytes=descriptor_after.st_size,
        modified_at_utc=datetime.fromtimestamp(
            descriptor_after.st_mtime,
            tz=timezone.utc,
        ).isoformat(),
        sha256=digest.hexdigest(),
    )


def ensure_required_file(path: Path, code: str) -> Path:
    resolved = path.resolve()
    if has_reparse_component(path) or not resolved.is_file():
        raise DailyMarketAuthorityError(code, str(path))
    return resolved


def file_identity(path: Path) -> AuthorityFileIdentity:
    return _consume_stable_file(path, lambda _chunk: None)


def read_stable_file_bytes(
    path: Path,
    *,
    max_bytes: int | None = None,
) -> tuple[bytes, AuthorityFileIdentity]:
    chunks: list[bytes] = []
    identity = _consume_stable_file(path, chunks.append, max_bytes=max_bytes)
    return b"".join(chunks), identity


def copy_stable_file(source: Path, destination: Path) -> AuthorityFileIdentity:
    if destination.exists() or has_reparse_component(destination.parent):
        raise DailyMarketAuthorityError(
            "AUTHORITY_SNAPSHOT_DESTINATION_UNTRUSTED",
            str(destination),
        )
    try:
        with destination.open("xb") as target:

            def write_chunk(chunk: bytes) -> None:
                _ = target.write(chunk)

            identity = _consume_stable_file(source, write_chunk)
            target.flush()
            os.fsync(target.fileno())
    except Exception:
        if destination.is_file() and not has_reparse_component(destination):
            destination.unlink()
        raise
    return identity


def authority_input_binding(
    path: Path,
    role: AuthorityInputRole,
) -> AuthorityInputBinding:
    if not path.exists():
        return AuthorityInputBinding(role=role, state="MISSING", identity=None)
    if has_reparse_component(path) or not path.is_file():
        return AuthorityInputBinding(role=role, state="INVALID", identity=None)
    try:
        identity = file_identity(path)
    except (OSError, DailyMarketAuthorityError):
        return AuthorityInputBinding(role=role, state="INVALID", identity=None)
    return AuthorityInputBinding(role=role, state="PRESENT", identity=identity)


def resolve_source_artifacts(
    root: Path,
    declared_hashes: frozenset[str],
) -> tuple[bool, tuple[AuthorityFileIdentity, ...]]:
    if not declared_hashes:
        return False, ()
    if has_reparse_component(root) or not root.is_dir():
        return False, ()
    identities: list[AuthorityFileIdentity] = []
    for declared_hash in sorted(declared_hashes):
        path = root / f"{declared_hash}.source"
        if has_reparse_component(path) or not path.is_file():
            return False, tuple(identities)
        try:
            identity = file_identity(path)
        except (OSError, DailyMarketAuthorityError):
            return False, tuple(identities)
        if identity.sha256 != declared_hash:
            return False, tuple(identities)
        identities.append(identity)
    return True, tuple(identities)


__all__ = [
    "authority_input_binding",
    "copy_stable_file",
    "ensure_required_file",
    "file_identity",
    "read_stable_file_bytes",
    "resolve_source_artifacts",
]
