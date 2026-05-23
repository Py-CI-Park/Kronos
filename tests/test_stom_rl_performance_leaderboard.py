import json
from pathlib import Path

from stom_rl.performance_leaderboard import PerformanceLeaderboardConfig, build_performance_leaderboard


def test_performance_leaderboard_combines_baseline_and_bandit(tmp_path: Path):
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir()
    baseline_report = baseline_dir / "leaderboard_report.json"
    baseline_report.write_text(
        json.dumps(
            {
                "summary": {
                    "target_rows": [
                        {
                            "policy": "buy_and_hold",
                            "cost_bps": 25.0,
                            "episode_count": 10,
                            "trade_count": 10,
                            "trades_per_episode": 1.0,
                            "avg_episode_net_return_pct": 0.5,
                            "max_drawdown_pct": -5.0,
                        },
                        {
                            "policy": "no_trade",
                            "cost_bps": 25.0,
                            "episode_count": 10,
                            "trade_count": 0,
                            "avg_episode_net_return_pct": 0.0,
                            "max_drawdown_pct": 0.0,
                        },
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    bandit_dir = tmp_path / "bandit"
    bandit_dir.mkdir()
    bandit_report = bandit_dir / "eval_summary.json"
    bandit_report.write_text(
        json.dumps(
            {
                "eval_summary": {
                    "summary": {
                        "policy": "contextual_bandit",
                        "eval_split": "test",
                        "episode_count": 10,
                        "trade_count": 4,
                        "trades_per_episode": 0.4,
                        "avg_episode_net_return_pct": 0.2,
                        "max_drawdown_pct": -4.0,
                        "passes_cost_gate": False,
                        "cost_bps": 25.0,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    payload = build_performance_leaderboard(
        PerformanceLeaderboardConfig(
            baseline_report=str(baseline_report),
            contextual_bandit_report=str(bandit_report),
            output_dir=str(tmp_path / "out"),
            sb3_smoke_reports=(),
        )
    )

    assert payload["summary"]["row_count"] == 3
    assert payload["summary"]["best_policy"] == "buy_and_hold"
    assert payload["summary"]["best_rl_usability"] == "watch"
    rows = {row["policy"]: row for row in payload["leaderboard"]}
    assert rows["contextual_bandit"]["beats_no_trade"] is True
    assert rows["contextual_bandit"]["beats_buy_and_hold"] is False
    assert (tmp_path / "out" / "performance_leaderboard.json").is_file()
    assert (tmp_path / "out" / "performance_leaderboard.csv").is_file()


def test_performance_leaderboard_includes_sb3_smoke_models(tmp_path: Path):
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir()
    baseline_report = baseline_dir / "leaderboard_report.json"
    baseline_report.write_text(
        json.dumps(
            {
                "summary": {
                    "target_rows": [
                        {"policy": "buy_and_hold", "avg_episode_net_return_pct": 0.5, "episode_count": 1},
                        {"policy": "no_trade", "avg_episode_net_return_pct": 0.0, "episode_count": 1},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    bandit_dir = tmp_path / "bandit"
    bandit_dir.mkdir()
    bandit_report = bandit_dir / "eval_summary.json"
    bandit_report.write_text(
        json.dumps({"eval_summary": {"summary": {"policy": "contextual_bandit", "avg_episode_net_return_pct": 0.1}}}),
        encoding="utf-8",
    )
    sb3_dir = tmp_path / "sb3"
    sb3_dir.mkdir()
    sb3_report = sb3_dir / "sb3_smoke_summary.json"
    sb3_report.write_text(
        json.dumps(
            {
                "models": [
                    {
                        "algorithm": "dqn",
                        "model": "dqn_smoke",
                        "policy": "stable_baselines3_dqn",
                        "avg_episode_net_return_pct": 0.2,
                        "episode_count": 1,
                        "trade_count": 1,
                        "passes_cost_gate": False,
                        "is_smoke": True,
                    },
                    {
                        "algorithm": "ppo",
                        "model": "ppo_smoke",
                        "policy": "stable_baselines3_ppo",
                        "avg_episode_net_return_pct": -0.1,
                        "episode_count": 1,
                        "trade_count": 0,
                        "passes_cost_gate": False,
                        "is_smoke": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = build_performance_leaderboard(
        PerformanceLeaderboardConfig(
            baseline_report=str(baseline_report),
            contextual_bandit_report=str(bandit_report),
            sb3_smoke_reports=(str(sb3_report),),
            output_dir=str(tmp_path / "out"),
        )
    )

    rows = {row["model"]: row for row in payload["leaderboard"]}
    assert payload["summary"]["row_count"] == 5
    assert payload["summary"]["rl_smoke_models"] == ["dqn_smoke", "ppo_smoke"]
    assert rows["dqn_smoke"]["is_smoke"] is True
    assert rows["dqn_smoke"]["run_name"] == "sb3"
