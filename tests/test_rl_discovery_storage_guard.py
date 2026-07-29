from __future__ import annotations

import pytest

from stom_rl.rl_discovery.storage import (
    RunDirectoryGuard,
    UnsafeArtifactPathError,
    contained_path,
)


def test_run_directory_guard_rejects_same_name_replacement(tmp_path) -> None:
    run_root = tmp_path / "runs"
    run_dir = run_root / "primary"
    run_dir.mkdir(parents=True)
    guard = RunDirectoryGuard.capture(run_root, run_dir)

    run_dir.rename(run_root / "original-primary")
    run_dir.mkdir()

    with pytest.raises(UnsafeArtifactPathError, match="identity changed"):
        guard.verify()


def test_contained_path_rejects_redirected_run_root(tmp_path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    redirected = tmp_path / "redirected"
    try:
        redirected.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is unavailable")

    with pytest.raises(UnsafeArtifactPathError, match="reparse"):
        contained_path(redirected, "summary.json")
