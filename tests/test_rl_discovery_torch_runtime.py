from __future__ import annotations

from pathlib import Path
import sys

import pytest

from stom_rl.rl_discovery.torch_runtime import prepare_torch_runtime


def test_windows_torch_runtime_preloads_system_msvc_not_environment_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SystemRoot", "C:/attacker-controlled")
    selected = prepare_torch_runtime()

    if sys.platform == "win32":
        assert selected is not None
        assert selected.name.casefold() == "msvcp140.dll"
        assert selected.parent.name.casefold() == "system32"
        assert selected != Path("C:/attacker-controlled/System32/MSVCP140.dll")
    else:
        assert selected is None
