"""Descriptor-bound event sampling and cross-poll file advancement."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Final, Literal

from stom_rl.daily_market_path_custody import has_reparse_component

SamplingMode = Literal["FULL_FILE", "HEAD_TAIL_SAMPLE"]
MAX_FOLLOW_OBSERVATIONS: Final = 512


@dataclass(frozen=True, slots=True)
class _FileObservation:
    device: int
    inode: int
    size: int
    modified_ns: int
    last_step: int


_FOLLOW_LOCK = Lock()
_FOLLOW_OBSERVATIONS: dict[str, _FileObservation] = {}


def _stat_signature(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def sampled_lines(
    path: Path,
    *,
    half_scan_bytes: int,
) -> tuple[tuple[str, ...], SamplingMode, os.stat_result]:
    """Read one bounded snapshot from the same verified file descriptor."""
    if path.is_symlink() or has_reparse_component(path):
        raise FileNotFoundError(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise OSError("telemetry event path is not a regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            if before.st_size <= half_scan_bytes * 2:
                payload = stream.read(before.st_size + 1)
                if len(payload) != before.st_size:
                    raise OSError("telemetry changed during bounded read")
                lines = tuple(payload.decode("utf-8-sig").splitlines())
                sampling: SamplingMode = "FULL_FILE"
            else:
                head = stream.read(half_scan_bytes)
                _ = stream.seek(before.st_size - half_scan_bytes)
                tail = stream.read(half_scan_bytes + 1)
                if len(head) != half_scan_bytes or len(tail) != half_scan_bytes:
                    raise OSError("telemetry changed during bounded sample")
                head = head[: head.rfind(b"\n") + 1]
                first_break = tail.find(b"\n")
                tail = tail[first_break + 1 :] if first_break >= 0 else b""
                head_lines = head.decode("utf-8-sig").splitlines()
                tail_lines = tail.decode("utf-8").splitlines()
                lines = tuple(head_lines + tail_lines)
                sampling = "HEAD_TAIL_SAMPLE"
        after = os.fstat(descriptor)
        path_after = os.stat(path, follow_symlinks=False)
        if _stat_signature(before) != _stat_signature(after) or _stat_signature(
            after
        ) != _stat_signature(path_after):
            raise OSError("telemetry changed during descriptor-bound read")
        return lines, sampling, after
    finally:
        os.close(descriptor)


def advanced_since_previous_poll(
    event_path: Path,
    stat_result: os.stat_result,
    *,
    last_step: int | None,
) -> bool:
    if last_step is None:
        return False
    current = _FileObservation(
        stat_result.st_dev,
        stat_result.st_ino,
        stat_result.st_size,
        stat_result.st_mtime_ns,
        last_step,
    )
    key = str(event_path.resolve())
    with _FOLLOW_LOCK:
        previous = _FOLLOW_OBSERVATIONS.get(key)
        _FOLLOW_OBSERVATIONS[key] = current
        while len(_FOLLOW_OBSERVATIONS) > MAX_FOLLOW_OBSERVATIONS:
            _ = _FOLLOW_OBSERVATIONS.pop(next(iter(_FOLLOW_OBSERVATIONS)))
    return (
        previous is not None
        and previous.device == current.device
        and previous.inode == current.inode
        and current.size > previous.size
        and current.modified_ns > previous.modified_ns
        and current.last_step > previous.last_step
    )


__all__ = ["SamplingMode", "advanced_since_previous_poll", "sampled_lines"]
