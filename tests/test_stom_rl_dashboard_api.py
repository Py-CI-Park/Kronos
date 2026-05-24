import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from webui import rl_dashboard  # noqa: E402
from webui.app import app as flask_app  # noqa: E402


def _write_csv(path: Path, header: str, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8-sig")


def _write_rl_fixture(root: Path) -> None:
    bandit = root / "bandit_run"
    bandit.mkdir()
    (bandit / "eval_summary.json").write_text(
        json.dumps(
            {
                "mode": "stom_rl_contextual_bandit",
                "eval_summary": {
                    "policy": "contextual_bandit",
                    "episode_count": 1,
                    "trade_count": 1,
                    "avg_episode_net_return_pct": 1.5,
                    "passes_cost_gate": True,
                },
                "artifacts": {},
            }
        ),
        encoding="utf-8-sig",
    )
    (bandit / "model.json").write_text(
        json.dumps(
            {
                "model": {
                    "model_type": "stom_fixed_horizon_contextual_bandit_ridge",
                    "feature_columns": ["ret_1s"],
                    "train_summary": {"train_sample_count": 10},
                }
            }
        ),
        encoding="utf-8-sig",
    )
    _write_csv(
        bandit / "trades.csv",
        "episode_id,symbol,net_return_pct",
        ["000001_20250103,000001,1.5"],
    )
    _write_csv(
        bandit / "equity_curve.csv",
        "episode_id,timestamp,equity",
        ["000001_20250103,2025-01-03T09:05:00,1.015"],
    )
    _write_csv(
        bandit / "actions.csv",
        "episode_id,action,predicted_net_return_pct",
        ["000001_20250103,buy,1.7"],
    )
    _write_csv(
        bandit / "episodes.csv",
        "episode_id,episode_return_pct",
        ["000001_20250103,1.5"],
    )

    cost = root / "cost_gate_run"
    cost.mkdir()
    (cost / "cost_gate_report.json").write_text(
        json.dumps(
            {
                "mode": "stom_rl_cost_gate",
                "summary": {
                    "passing_policy_count": 1,
                    "passing_policies": ["buy_and_hold"],
                    "best_policy_at_target_cost": "buy_and_hold",
                },
            }
        ),
        encoding="utf-8-sig",
    )
    _write_csv(
        cost / "gate_summary.csv",
        "policy,passes_cost_gate,avg_episode_net_return_pct",
        ["buy_and_hold,True,1.2"],
    )
    _write_csv(
        cost / "scenario_summary.csv",
        "policy,cost_bps,avg_episode_net_return_pct",
        ["buy_and_hold,25,1.2"],
    )
    _write_csv(
        cost / "rolling_folds.csv",
        "fold,policy,positive_fold",
        ["1,buy_and_hold,True"],
    )

    baseline = root / "baseline_run"
    baseline.mkdir()
    (baseline / "baseline_summary.json").write_text(
        json.dumps({"mode": "stom_rl_baseline_run", "summary": {"policy_count": 1}}),
        encoding="utf-8-sig",
    )
    _write_csv(
        baseline / "buy_and_hold" / "trades.csv",
        "policy,episode_id,net_return_pct",
        ["buy_and_hold,000001_20250103,1.1"],
    )

    leaderboard = root / "leaderboard_run"
    leaderboard.mkdir()
    (leaderboard / "performance_leaderboard.json").write_text(
        json.dumps(
            {
                "mode": "stom_rl_performance_leaderboard",
                "summary": {
                    "row_count": 2,
                    "best_policy": "buy_and_hold",
                    "best_rl_model": "contextual_bandit",
                    "best_rl_usability": "watch",
                    "target_cost_bps": 25,
                },
                "leaderboard": [
                    {
                        "rank": 1,
                        "source": "baseline",
                        "model": "buy_and_hold",
                        "avg_episode_net_return_pct": 1.2,
                        "passes_cost_gate": False,
                    },
                    {
                        "rank": 2,
                        "source": "rl_model",
                        "model": "contextual_bandit",
                        "avg_episode_net_return_pct": 0.4,
                        "passes_cost_gate": False,
                    },
                ],
            }
        ),
        encoding="utf-8-sig",
    )
    _write_csv(
        leaderboard / "performance_leaderboard.csv",
        "rank,source,model,avg_episode_net_return_pct,passes_cost_gate",
        ["1,baseline,buy_and_hold,1.2,False", "2,rl_model,contextual_bandit,0.4,False"],
    )

    sb3 = root / "sb3_smoke_run"
    sb3.mkdir()
    (sb3 / "sb3_smoke_summary.json").write_text(
        json.dumps(
            {
                "mode": "stom_rl_sb3_smoke",
                "summary": {
                    "algorithm_count": 2,
                    "best_model": "dqn_smoke",
                    "best_algorithm_by_avg_episode_net": "dqn",
                    "feature_columns": ["open", "close", "position"],
                },
                "models": [
                    {
                        "algorithm": "dqn",
                        "model": "dqn_smoke",
                        "policy": "stable_baselines3_dqn",
                        "avg_episode_net_return_pct": 0.3,
                        "trade_count": 1,
                        "passes_cost_gate": False,
                        "is_smoke": True,
                    }
                ],
            }
        ),
        encoding="utf-8-sig",
    )
    _write_csv(
        sb3 / "sb3_smoke_summary.csv",
        "algorithm,model,avg_episode_net_return_pct,is_smoke",
        ["dqn,dqn_smoke,0.3,True"],
    )
    _write_csv(
        sb3 / "trades.csv",
        "model,algorithm,episode_id,net_return_pct",
        ["dqn_smoke,dqn,000001_20250103,0.3"],
    )
    (sb3 / "rl_live_events.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": "stom_rl_live_event.v1",
                        "run_id": "sb3_smoke_run",
                        "algorithm": "dqn",
                        "phase": "eval",
                        "global_step": 1,
                        "action": 1,
                        "action_name": "buy",
                        "reward": 0.1,
                        "position": 1,
                        "equity": 1.003,
                    }
                )
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (sb3 / "rl_live_summary.json").write_text(
        json.dumps({"schema_version": "stom_rl_live_event.v1", "event_count": 1, "phases": {"eval": 1}}),
        encoding="utf-8-sig",
    )


def test_rl_dashboard_helpers_list_detail_and_tables(tmp_path, monkeypatch):
    _write_rl_fixture(tmp_path)
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])

    runs = rl_dashboard.list_rl_runs(limit=10)
    names = {run["name"] for run in runs}
    detail = rl_dashboard.load_rl_run("bandit_run")
    trades = rl_dashboard.load_rl_table("bandit_run", "trades", limit=5)
    baseline_trades = rl_dashboard.load_rl_table("baseline_run", "trades", policy="buy_and_hold", limit=5)
    leaderboard_detail = rl_dashboard.load_rl_run("leaderboard_run")
    leaderboard_rows = rl_dashboard.load_rl_table("leaderboard_run", "leaderboard", limit=5)
    sb3_detail = rl_dashboard.load_rl_run("sb3_smoke_run")
    sb3_summary = rl_dashboard.load_rl_table("sb3_smoke_run", "summary", limit=5)
    sb3_events = rl_dashboard.load_rl_events("sb3_smoke_run", limit=5)
    cost_gate = rl_dashboard.load_rl_cost_gate("cost_gate_run", limit=5)

    assert {"bandit_run", "cost_gate_run", "baseline_run", "leaderboard_run", "sb3_smoke_run"}.issubset(names)
    assert detail["artifact_type"] == "contextual_bandit"
    assert detail["model"]["model_type"] == "stom_fixed_horizon_contextual_bandit_ridge"
    assert trades["rows"][0]["net_return_pct"] == 1.5
    assert baseline_trades["rows"][0]["policy"] == "buy_and_hold"
    assert leaderboard_detail["artifact_type"] == "performance_leaderboard"
    assert leaderboard_detail["summary"]["best_policy"] == "buy_and_hold"
    assert leaderboard_rows["rows"][1]["model"] == "contextual_bandit"
    assert sb3_detail["artifact_type"] == "sb3_smoke"
    assert sb3_detail["model"]["model_type"] == "stable_baselines3_dqn"
    assert sb3_detail["summary"]["live_event_count"] == 1
    assert sb3_summary["rows"][0]["model"] == "dqn_smoke"
    assert sb3_events["rows"][0]["action_name"] == "buy"
    assert cost_gate["summary"]["passing_policies"] == ["buy_and_hold"]
    assert cost_gate["gate"]["rows"][0]["passes_cost_gate"] is True


def test_rl_dashboard_rejects_path_traversal(tmp_path, monkeypatch):
    _write_rl_fixture(tmp_path)
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])

    try:
        rl_dashboard.load_rl_run("../secret")
    except ValueError as exc:
        assert "direct child" in str(exc) or "Invalid" in str(exc)
    else:
        raise AssertionError("path traversal was accepted")


def test_flask_rl_routes_smoke(tmp_path, monkeypatch):
    _write_rl_fixture(tmp_path)
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])

    client = flask_app.test_client()

    runs = client.get("/api/rl/runs")
    assert runs.status_code == 200
    assert any(run["name"] == "bandit_run" for run in runs.get_json()["runs"])

    detail = client.get("/api/rl/runs/bandit_run")
    assert detail.status_code == 200
    assert detail.get_json()["summary"]["passes_cost_gate"] is True

    trades = client.get("/api/rl/runs/bandit_run/trades")
    assert trades.status_code == 200
    assert trades.get_json()["rows"][0]["net_return_pct"] == 1.5

    baseline_trades = client.get("/api/rl/runs/baseline_run/trades?policy=buy_and_hold")
    assert baseline_trades.status_code == 200
    assert baseline_trades.get_json()["rows"][0]["policy"] == "buy_and_hold"

    cost_gate = client.get("/api/rl/runs/cost_gate_run/cost-gate")
    assert cost_gate.status_code == 200
    assert cost_gate.get_json()["summary"]["best_policy_at_target_cost"] == "buy_and_hold"

    leaderboard = client.get("/api/rl/runs/leaderboard_run/table/leaderboard")
    assert leaderboard.status_code == 200
    assert leaderboard.get_json()["rows"][0]["model"] == "buy_and_hold"

    sb3 = client.get("/api/rl/runs/sb3_smoke_run")
    assert sb3.status_code == 200
    assert sb3.get_json()["artifact_type"] == "sb3_smoke"

    events = client.get("/api/rl/runs/sb3_smoke_run/events")
    assert events.status_code == 200
    assert events.get_json()["rows"][0]["phase"] == "eval"

    progress = client.get("/api/rl/progress")
    assert progress.status_code == 200
    assert progress.get_json()["mode"] == "stom_rl_page_progress"

    bad = client.get("/api/rl/runs/..%5Csecret")
    assert bad.status_code in {400, 404}
