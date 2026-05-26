import json

from stom_rl.portfolio_train import PortfolioTrainConfig, run_portfolio_smoke


def test_portfolio_train_smoke_writes_core_artifacts(tmp_path):
    payload = run_portfolio_smoke(
        PortfolioTrainConfig(output_dir=str(tmp_path), max_steps=5, top_k_candidates=2, max_positions=1)
    )

    assert payload["summary"]["steps"] == 5
    assert payload["summary"]["action_space_n"] == 4
    assert (tmp_path / "portfolio_train_summary.json").is_file()
    assert (tmp_path / "actions.csv").is_file()
    assert (tmp_path / "trades.csv").is_file()
    summary = json.loads((tmp_path / "portfolio_train_summary.json").read_text(encoding="utf-8-sig"))
    assert summary["summary"]["final_nav"] > 0
