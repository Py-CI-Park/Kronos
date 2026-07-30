from __future__ import annotations

import os
from pathlib import Path

import pytest

from stom_rl.rl_discovery.storage import (
    RunDirectoryGuard,
    UnsafeArtifactPathError,
    atomic_write_bytes,
    contained_path,
)


def test_run_directory_guard_rejects_same_name_replacement(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"
    run_dir = run_root / "primary"
    run_dir.mkdir(parents=True)
    guard = RunDirectoryGuard.capture(run_root, run_dir)

    _ = run_dir.rename(run_root / "original-primary")
    run_dir.mkdir()

    with pytest.raises(UnsafeArtifactPathError, match="identity changed"):
        _ = guard.verify()


def test_run_directory_guard_rejects_same_name_root_replacement(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"
    run_dir = run_root / "primary"
    run_dir.mkdir(parents=True)
    guard = RunDirectoryGuard.capture(run_root, run_dir)

    moved_root = tmp_path / "moved-runs"
    _ = run_root.rename(moved_root)
    run_root.mkdir()
    _ = (moved_root / "primary").rename(run_dir)

    with pytest.raises(
        ValueError, match="root.*identity changed|locked directory identity changed"
    ):
        _ = guard.publish_bytes(b"blocked", "summary.json")
    assert not (run_dir / "summary.json").exists()


def test_contained_path_rejects_redirected_run_root(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    redirected = tmp_path / "redirected"
    try:
        redirected.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is unavailable")

    with pytest.raises(UnsafeArtifactPathError, match="reparse"):
        _ = contained_path(redirected, "summary.json")


@pytest.mark.skipif(os.name != "nt", reason="Windows directory-sharing contract")
def test_locked_guard_blocks_run_directory_replacement_during_publication(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "runs"
    run_dir = run_root / "primary"
    run_dir.mkdir(parents=True)
    guard = RunDirectoryGuard.capture(run_root, run_dir)

    with guard.locked() as locked_dir:
        with pytest.raises(PermissionError):
            _ = run_dir.rename(run_root / "moved-primary")
        atomic_write_bytes(contained_path(locked_dir, "summary.json"), b"safe")

    assert (run_dir / "summary.json").read_bytes() == b"safe"


@pytest.mark.skipif(os.name != "nt", reason="Windows directory-sharing contract")
def test_locked_parent_blocks_nested_directory_replacement(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"
    run_dir = run_root / "primary"
    inputs = run_dir / "inputs"
    inputs.mkdir(parents=True)
    guard = RunDirectoryGuard.capture(run_root, run_dir)

    with guard.locked_parent("inputs") as locked_inputs:
        with pytest.raises(PermissionError):
            _ = inputs.rename(run_dir / "moved-inputs")
        atomic_write_bytes(contained_path(locked_inputs, "prereg.json"), b"safe")

    assert (inputs / "prereg.json").read_bytes() == b"safe"


def test_guarded_publication_rejects_a_same_name_redirect(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"
    run_dir = run_root / "primary"
    outside = tmp_path / "outside"
    run_dir.mkdir(parents=True)
    outside.mkdir()
    guard = RunDirectoryGuard.capture(run_root, run_dir)
    _ = run_dir.rename(run_root / "original-primary")
    try:
        run_dir.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory redirect creation is unavailable")

    with pytest.raises(UnsafeArtifactPathError):
        _ = guard.publish_bytes(b"blocked", "summary.json")
    assert not (outside / "summary.json").exists()
