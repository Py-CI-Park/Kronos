from stom_rl.portfolio_walk_forward import PortfolioWalkForwardConfig, run_portfolio_walk_forward


def test_portfolio_walk_forward_generates_fold_report_and_baselines(tmp_path):
    payload = run_portfolio_walk_forward(
        PortfolioWalkForwardConfig(output_dir=str(tmp_path), n_folds=2, max_steps_per_fold=4)
    )

    assert payload["summary"]["smoke_success"] is True
    assert payload["summary"]["n_folds"] == 2
    assert {row["policy"] for row in payload["folds"]} >= {"no_trade", "equal_weight_candidate", "buy_and_hold"}
    assert (tmp_path / "portfolio_walk_forward_report.json").is_file()
    assert (tmp_path / "portfolio_walk_forward_folds.csv").is_file()
