from __future__ import annotations

import json
from pathlib import Path

import pytest

from webui import rl_dashboard_identity as identity
from webui.rl_dashboard_runs import require_discovery_terminal_receipt


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


def test_discovery_terminal_summary_requires_matching_receipt(tmp_path: Path) -> None:
    summary: dict[str, object] = {
        "research_lane": "rl_discovery",
        "status": "PRIMARY_COMPLETE",
        "verdict": "NO_GO",
        "prereg_sha256": "a" * 64,
        "fresh_oos": "NOT_RUN_NO_READ",
    }

    uncommitted = require_discovery_terminal_receipt(tmp_path, summary)
    assert uncommitted["status"] == "RUNNING"
    assert uncommitted["verdict"] == "RUNNING_NOT_EVALUATED"

    receipt = {
        "status": "PRIMARY_COMPLETE",
        "verdict": "NO_GO",
        "prereg_sha256": "a" * 64,
        "fresh_oos": "NOT_RUN_NO_READ",
    }
    _ = (tmp_path / "terminal_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    assert require_discovery_terminal_receipt(tmp_path, summary) == summary
