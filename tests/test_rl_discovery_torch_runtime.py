from __future__ import annotations

from pathlib import Path
import sys

from stom_rl.rl_discovery.torch_runtime import prepare_torch_runtime


def test_windows_torch_runtime_preloads_system_msvc_not_pyqt_copy() -> None:
    selected = prepare_torch_runtime()

    if sys.platform == "win32":
        assert selected == Path("C:/Windows/System32/MSVCP140.dll")
    else:
        assert selected is None
