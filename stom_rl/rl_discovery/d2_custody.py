"""Held-handle and reparse-safe custody primitives for D2 inputs."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import hashlib
import io
import os
from pathlib import Path
import stat
import sys


class D2CustodyError(ValueError):
    """A D2 path or held input failed its custody contract."""


_REPARSE_ATTRIBUTE = 0x400


def assert_plain_path(path: Path, *, anchor: Path, require_file: bool) -> Path:
    """Reject traversal, symlinks, junctions, and every existing reparse ancestor."""

    root = anchor.absolute()
    candidate = path.absolute()
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise D2CustodyError("D2 path must stay under its configured anchor") from exc
    current = root
    for segment in relative.parts:
        current /= segment
        if not current.exists() and not current.is_symlink():
            continue
        info = os.lstat(current)
        attributes = int(getattr(info, "st_file_attributes", 0))
        if stat.S_ISLNK(info.st_mode) or attributes & _REPARSE_ATTRIBUTE:
            raise D2CustodyError("D2 paths cannot contain symlinks or reparse points")
    if require_file and (not candidate.is_file() or candidate.is_symlink()):
        raise D2CustodyError("D2 input must be a regular file")
    return candidate


def verified_bytes(path: Path, *, expected_sha256: str, anchor: Path) -> bytes:
    """Read one small input through a deny-write held handle and verify those bytes."""

    checked = assert_plain_path(path, anchor=anchor, require_file=True)
    with _open_held_binary(checked) as handle:
        payload = handle.read()
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise D2CustodyError("D2 held input hash mismatch")
    return payload


def held_bytes(path: Path, *, anchor: Path) -> bytes:
    """Read a small custody artifact from a write-denied, no-reparse handle."""

    checked = assert_plain_path(path, anchor=anchor, require_file=True)
    with _open_held_binary(checked) as handle:
        return handle.read()


@contextmanager
def verified_text_stream(
    path: Path,
    *,
    expected_sha256: str,
    anchor: Path,
) -> Iterator[io.TextIOWrapper]:
    """Hash, parse, and rehash the same write-denied binary handle."""

    checked = assert_plain_path(path, anchor=anchor, require_file=True)
    with _open_held_binary(checked) as binary:
        if _hash_handle(binary) != expected_sha256:
            raise D2CustodyError("D2 held input hash mismatch")
        binary.seek(0)
        text = io.TextIOWrapper(binary, encoding="utf-8", newline="")
        detached = False
        try:
            yield text
            text.detach()
            detached = True
            if _hash_handle(binary) != expected_sha256:
                raise D2CustodyError("D2 input changed while it was consumed")
        finally:
            if not detached:
                text.detach()


def _hash_handle(handle: io.BufferedReader) -> str:
    handle.seek(0)
    digest = hashlib.sha256()
    for chunk in iter(lambda: handle.read(1 << 20), b""):
        digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def _open_held_binary(path: Path) -> Iterator[io.BufferedReader]:
    """Open without write/delete sharing on Windows; no-follow elsewhere."""

    if sys.platform == "win32":
        import ctypes
        import msvcrt
        from ctypes import wintypes

        create_file = ctypes.windll.kernel32.CreateFileW
        create_file.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        )
        create_file.restype = wintypes.HANDLE
        handle = create_file(str(path), 0x80000000, 0x00000001, None, 3, 0x00200000, None)
        if handle == wintypes.HANDLE(-1).value:
            raise OSError(ctypes.get_last_error(), "cannot hold D2 input", str(path))
        descriptor = msvcrt.open_osfhandle(int(handle), os.O_RDONLY)
    else:
        flags = os.O_RDONLY | int(getattr(os, "O_NOFOLLOW", 0))
        descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as binary:
        yield binary
