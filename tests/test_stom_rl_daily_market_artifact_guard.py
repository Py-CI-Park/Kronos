from __future__ import annotations

from pathlib import Path

import pytest

from stom_rl.daily_market_artifact_guard import resolve_trusted_artifact


def test_artifact_guard_rejects_outside_root_and_oversized_file(tmp_path: Path) -> None:
    trusted = tmp_path / "trusted"
    trusted.mkdir()
    inside = trusted / "inside.csv"
    _ = inside.write_text("12", encoding="utf-8")
    outside = tmp_path / "outside.csv"
    _ = outside.write_text("1", encoding="utf-8")

    with pytest.raises(ValueError, match="OUTSIDE_TRUSTED_ARTIFACT_ROOT"):
        _ = resolve_trusted_artifact(
            outside,
            artifact_root=trusted,
            max_bytes=10,
            label="TEST",
        )
    with pytest.raises(ValueError, match="ARTIFACT_SIZE_OUT_OF_BOUNDS"):
        _ = resolve_trusted_artifact(
            inside,
            artifact_root=trusted,
            max_bytes=1,
            label="TEST",
        )


def test_artifact_guard_rejects_a_symlinked_file_when_supported(tmp_path: Path) -> None:
    trusted = tmp_path / "trusted"
    trusted.mkdir()
    target = trusted / "target.csv"
    _ = target.write_text("safe", encoding="utf-8")
    link = trusted / "link.csv"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is unavailable on this Windows host")

    with pytest.raises(ValueError, match="SYMLINK_NOT_ALLOWED"):
        _ = resolve_trusted_artifact(
            link,
            artifact_root=trusted,
            max_bytes=10,
            label="TEST",
        )
