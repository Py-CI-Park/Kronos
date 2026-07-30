"""Descriptor-bound lease for safe research-artifact publication."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
import os
from pathlib import Path
import stat


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
        with _locked_windows_directory(
            path,
            expected_device=expected_device,
            expected_inode=expected_inode,
        ) as anchor:
            yield anchor
        return
    with _locked_descriptor_directory(
        path,
        expected_device=expected_device,
        expected_inode=expected_inode,
    ) as anchor:
        yield anchor


@contextmanager
def locked_artifact_parent(
    run_dir: Path,
    parent_segments: tuple[str, ...],
    *,
    expected_device: int,
    expected_inode: int,
    exclusive_leaf: bool = False,
) -> Iterator[Path]:
    """Hold the run directory and every artifact parent until publication ends."""

    with ExitStack() as stack:
        current = stack.enter_context(
            locked_directory(
                run_dir,
                expected_device=expected_device,
                expected_inode=expected_inode,
            )
        )
        for index, raw_segment in enumerate(parent_segments):
            segment = _safe_segment(raw_segment)
            child = current / segment
            is_leaf = index == len(parent_segments) - 1
            if is_leaf and exclusive_leaf:
                child.mkdir(exist_ok=False)
            else:
                child.mkdir(exist_ok=True)
            identity = _plain_directory_identity(child)
            current = stack.enter_context(
                locked_directory(
                    child,
                    expected_device=identity[0],
                    expected_inode=identity[1],
                )
            )
        yield current


@contextmanager
def _locked_windows_directory(
    path: Path,
    *,
    expected_device: int,
    expected_inode: int,
) -> Iterator[Path]:
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
        _assert_identity(
            path,
            expected_device=expected_device,
            expected_inode=expected_inode,
        )
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


def _safe_segment(value: str) -> str:
    if value in {"", ".", ".."} or Path(value).name != value:
        raise DirectoryLeaseError("artifact parent must be a direct child name")
    return value


def _plain_directory_identity(path: Path) -> tuple[int, int]:
    identity = os.stat(path, follow_symlinks=False)
    attributes = getattr(identity, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if not path.is_dir() or path.is_symlink() or attributes & reparse_flag:
        raise DirectoryLeaseError("artifact parent must be a plain directory")
    return identity.st_dev, identity.st_ino


def _assert_identity(
    path: Path,
    *,
    expected_device: int | None,
    expected_inode: int | None,
) -> None:
    if expected_device is None or expected_inode is None:
        return
    if _plain_directory_identity(path) != (expected_device, expected_inode):
        raise DirectoryLeaseError("locked directory identity changed")
