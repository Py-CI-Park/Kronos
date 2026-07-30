"""Characterization tests for the RL dashboard summary facade."""

from pathlib import Path

from webui.rl_dashboard_summary import find_discovery_evidence, find_json_summary


def test_summary_facade_keeps_public_discovery_exports() -> None:
    assert find_json_summary(Path("."), "unknown") == {}
    assert callable(find_discovery_evidence)


def test_discovery_evidence_fails_closed_for_missing_artifacts(tmp_path: Path) -> None:
    compact, detail = find_discovery_evidence(tmp_path, "rl_discovery_d4")

    assert compact == {
        "research_lane": "rl_discovery",
        "status": "BLOCK",
        "verdict": "NO_GO",
    }
    assert detail == {}
