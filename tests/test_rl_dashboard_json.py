from pathlib import Path

from webui.rl_dashboard_json import read_run_json


def test_read_run_json_fails_closed_for_non_object_root(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    payload = run / "summary.json"
    _ = payload.write_text("[]", encoding="utf-8")

    assert read_run_json(run, payload) == {}


def test_read_run_json_preserves_object_root(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    payload = run / "summary.json"
    _ = payload.write_text('{"schema_version":"test.v1"}', encoding="utf-8")

    assert read_run_json(run, payload) == {"schema_version": "test.v1"}
