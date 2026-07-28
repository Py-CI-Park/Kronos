"""Windows native-runtime preparation for Torch entry points."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import sys


def prepare_torch_runtime() -> Path | None:
    """Preload the supported Windows MSVC runtime before Torch native DLLs."""

    if sys.platform != "win32":
        return None
    system_root = Path(os.environ.get("SystemRoot", "C:/Windows"))
    runtime = system_root / "System32" / "MSVCP140.dll"
    _ = ctypes.CDLL(str(runtime))
    return runtime
