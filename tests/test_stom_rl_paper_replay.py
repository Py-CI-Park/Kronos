import json

import pytest

from stom_rl.paper_replay import PaperReplayConfig, run_paper_replay


def test_paper_replay_is_read_only_and_logs_decisions(tmp_path):
    payload = run_paper_replay(PaperReplayConfig(output_dir=str(tmp_path), max_steps=5, max_daily_trades=1))

    assert payload["summary"]["read_only"] is True
    assert payload["summary"]["order_write_path"] is False
    assert payload["summary"]["steps"] == 5
    assert (tmp_path / "paper_replay_summary.json").is_file()
    assert (tmp_path / "decisions.csv").is_file()
    assert (tmp_path / "risk_triggers.json").is_file()
    triggers = json.loads((tmp_path / "risk_triggers.json").read_text(encoding="utf-8-sig"))
    assert "risk_triggers" in triggers


def test_paper_replay_refuses_non_read_only_mode():
    with pytest.raises(ValueError, match="read_only"):
        run_paper_replay(PaperReplayConfig(read_only=False, write_artifacts=False))
