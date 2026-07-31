from pathlib import Path

# This test intentionally verifies the private artifact classifier boundary.
# pyright: reportPrivateUsage=false

from webui.rl_dashboard_discovery_meta import discovery_type1_outcome, expected_discovery_schema
from webui.rl_dashboard_runs import _detect_artifact_type


def test_d6r2_schema_is_detected_and_keeps_no_go_verdict(tmp_path: Path) -> None:
    run = tmp_path / "d6r2"
    run.mkdir()
    _ = (run / "summary.json").write_text(
        '{"schema_version":"kronos.rl-discovery.d6r2.falsification.v1"}',
        encoding="utf-8",
    )

    assert _detect_artifact_type(run) == "rl_discovery_d6r2"
    assert expected_discovery_schema("rl_discovery_d6r2") == "kronos.rl-discovery.d6r2.falsification.v1"
    assert discovery_type1_outcome("rl_discovery_d6r2", {"verdict": "D6R2_TOP5_SIGNAL_FLOOR_NOT_CONFIRMED"}) == "D6R2_TOP5_SIGNAL_FLOOR_NOT_CONFIRMED"
