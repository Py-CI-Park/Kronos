"""Descriptor-bound lease for safe research-artifact publication."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path


class DirectoryLeaseError(ValueError):
    """Raised when publication cannot stay bound to one directory identity."""


@contextmanager
def locked_directory(
    path: Path,
    *,
    expected_device: int,
    expected_inode: int,
) -> Iterator[Path]:
    """Yield a stable publication anchor while preventing pathname replacement."""

    if os.name == "nt":
        with _locked_windows_directory(path) as anchor:
            yield anchor
        return
    with _locked_descriptor_directory(
        path,
        expected_device=expected_device,
        expected_inode=expected_inode,
    ) as anchor:
        yield anchor


@contextmanager
def _locked_windows_directory(path: Path) -> Iterator[Path]:
    import win32con
    import win32file

    handle = win32file.CreateFile(
        str(path),
        win32con.GENERIC_READ,
        win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
        None,
        win32con.OPEN_EXISTING,
        win32con.FILE_FLAG_BACKUP_SEMANTICS | 0x00200000,
        None,
    )
    try:
        yield path
    finally:
        handle.Close()


@contextmanager
def _locked_descriptor_directory(
    path: Path,
    *,
    expected_device: int,
    expected_inode: int,
) -> Iterator[Path]:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        identity = os.fstat(descriptor)
        if (identity.st_dev, identity.st_ino) != (expected_device, expected_inode):
            raise DirectoryLeaseError("locked directory identity changed")
        anchors = (Path(f"/proc/self/fd/{descriptor}"), Path(f"/dev/fd/{descriptor}"))
        anchor = next((candidate for candidate in anchors if candidate.is_dir()), None)
        if anchor is None:
            raise DirectoryLeaseError("descriptor-relative publication is unavailable")
        yield anchor
        final_identity = os.fstat(descriptor)
        if (final_identity.st_dev, final_identity.st_ino) != (
            expected_device,
            expected_inode,
        ):
            raise DirectoryLeaseError("locked directory identity changed")
    finally:
        os.close(descriptor)
