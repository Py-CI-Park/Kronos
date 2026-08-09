"""Trusted-root and bounded-size guards for daily market artifacts."""

from __future__ import annotations

from pathlib import Path

MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_SCORE_CSV_BYTES = 64 * 1024 * 1024
MAX_PANEL_CSV_BYTES = 256 * 1024 * 1024
MAX_SCORE_ROWS = 5_000_000
MAX_PANEL_ROWS = 5_000_000


def resolve_trusted_artifact(
    path: Path | str,
    *,
    artifact_root: Path | str,
    max_bytes: int,
    label: str,
) -> Path:
    """Resolve one regular file inside an explicit non-symlink trust root."""
    raw_root = Path(artifact_root)
    raw_path = Path(path)
    if raw_root.is_symlink() or raw_path.is_symlink():
        raise ValueError(f"{label}:SYMLINK_NOT_ALLOWED")
    resolved_root = raw_root.resolve()
    resolved_path = raw_path.resolve()
    if not resolved_root.is_dir():
        raise FileNotFoundError(resolved_root)
    try:
        _ = resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"{label}:OUTSIDE_TRUSTED_ARTIFACT_ROOT") from exc
    if not resolved_path.is_file():
        raise FileNotFoundError(resolved_path)
    size = resolved_path.stat().st_size
    if size <= 0 or size > max_bytes:
        raise ValueError(f"{label}:ARTIFACT_SIZE_OUT_OF_BOUNDS")
    return resolved_path


__all__ = [
    "MAX_MANIFEST_BYTES",
    "MAX_PANEL_CSV_BYTES",
    "MAX_PANEL_ROWS",
    "MAX_SCORE_CSV_BYTES",
    "MAX_SCORE_ROWS",
    "resolve_trusted_artifact",
]
