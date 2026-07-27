from __future__ import annotations

from pathlib import Path

import pytest

from webui import rl_dashboard_identity as identity


def test_artifact_identity_reuses_content_hash_when_file_stat_is_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    artifact = run_dir / "model.zip"
    _ = artifact.write_bytes(b"model-bytes")
    calls = 0
    original = identity.hash_file_content

    def counted(path: Path) -> tuple[str, int]:
        nonlocal calls
        calls += 1
        return original(path)

    monkeypatch.setattr(identity, "hash_file_content", counted)
    identity.clear_identity_cache()

    first = identity.artifact_snapshot(run_dir)
    second = identity.artifact_snapshot(run_dir)

    assert first == second
    assert calls == 1
