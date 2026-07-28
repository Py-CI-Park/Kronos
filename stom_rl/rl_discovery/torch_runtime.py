"""Windows native-runtime preparation for Torch entry points."""

from __future__ import annotations

import ctypes
from pathlib import Path
import sys


class TorchRuntimePreparationError(RuntimeError):
    """Raised when Windows cannot provide a trusted native runtime path."""


def _trusted_system_directory() -> Path:
    """Read the Windows system directory from Kernel32, not the environment."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    buffer = ctypes.create_unicode_buffer(32_768)
    length = int(kernel32.GetSystemDirectoryW(buffer, len(buffer)))
    if length == 0 or length >= len(buffer):
        raise TorchRuntimePreparationError("GetSystemDirectoryW failed")
    return Path(buffer.value).resolve(strict=True)


def prepare_torch_runtime() -> Path | None:
    """Preload the supported Windows MSVC runtime before Torch native DLLs."""

    if sys.platform != "win32":
        return None
    system_directory = _trusted_system_directory()
    runtime = (system_directory / "MSVCP140.dll").resolve(strict=True)
    if runtime.parent != system_directory or runtime.name.casefold() != "msvcp140.dll":
        raise TorchRuntimePreparationError("MSVC runtime escaped the trusted system directory")
    _ = ctypes.WinDLL(str(runtime), winmode=0x00000800)
    return runtime
