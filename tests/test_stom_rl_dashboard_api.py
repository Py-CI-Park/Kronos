import json
import os
import sys
import time
import uuid
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from webui import rl_dashboard, rl_dashboard_runs  # noqa: E402
from webui.app import app as flask_app  # noqa: E402
from stom_rl.rl_discovery.storage import artifact_manifest_sha256  # noqa: E402


IDENTITY_FIELDS = ("run_uid", "revision", "source_sha256", "source_protocol")


def _identity_fields(record: dict) -> dict:
    return {key: record[key] for key in IDENTITY_FIELDS}


def _assert_identity_contract(record: dict) -> None:
    run_uid = record["run_uid"]
    assert isinstance(run_uid, str)
    assert str(uuid.UUID(run_uid)) == run_uid

    revision = record["revision"]
    assert isinstance(revision, int) and not isinstance(revision, bool)
    assert revision > 0

    source_sha256 = record["source_sha256"]
    assert isinstance(source_sha256, str)
    assert len(source_sha256) == 64
    assert source_sha256 == source_sha256.lower()
    int(source_sha256, 16)

    assert record["source_protocol"] == rl_dashboard_runs.RUN_IDENTITY_PROTOCOL


def _write_minimal_baseline_run(run_dir: Path) -> None:
    run_dir.mkdir(parents=True)
    (run_dir / "baseline_summary.json").write_text(
        json.dumps({"mode": "stom_rl_baseline_run", "summary": {"policy_count": 1}}),
        encoding="utf-8-sig",
    )


def test_d2_summary_and_receipt_are_discoverable_as_read_only_rl_evidence(tmp_path, monkeypatch):
    run = tmp_path / "type2-d2-primary"
    run.mkdir()
    summary = {
        "schema_version": "kronos.rl-discovery.d2.result.v1",
        "status": "COMPLETE",
        "verdict": "D2_PARTIAL_CAPACITY_CONFIRMED",
        "profile": "PRIMARY",
        "fresh_oos": "NOT_RUN_NO_READ",
        "prereg_sha256": "a" * 64,
        "episode_snapshot_sha256": "b" * 64,
        "models": [],
    }
    (run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    receipt = {
        "status": "COMPLETE",
        "profile": "PRIMARY",
        "verdict": summary["verdict"],
        "prereg_sha256": summary["prereg_sha256"],
        "episode_snapshot_sha256": summary["episode_snapshot_sha256"],
        "fresh_oos": "NOT_RUN_NO_READ",
        "artifact_manifest_sha256": artifact_manifest_sha256(run),
    }
    (run / "terminal_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])

    record = next(item for item in rl_dashboard.list_rl_runs() if item["name"] == run.name)
    detail = rl_dashboard.load_rl_run(run.name)

    assert record["artifact_type"] == "rl_discovery_d2"
    assert record["summary"]["research_lane"] == "rl_discovery"
    assert record["summary"]["fresh_oos"] == "NOT_RUN_NO_READ"
    assert detail["detail"]["verdict"] == "D2_PARTIAL_CAPACITY_CONFIRMED"

    summary["models"] = [{"tampered": True}]
    (run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    blocked = rl_dashboard.load_rl_run(run.name)
    assert blocked["summary"]["status"] == "BLOCK"
    assert blocked["detail"] == {}

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
    daily_sb3 = root / "daily_ohlcv_portfolio_sb3" / "daily_sb3_run"
    daily_sb3.mkdir(parents=True)
    (daily_sb3 / "sb3_smoke_summary.json").write_text(
        json.dumps(
            {
                "mode": "stom_rl_sb3_smoke",
                "schema_version": "daily_portfolio_sb3_as_sb3_smoke.v1",
                "summary": {
                    "algorithm_count": 1,
                    "best_model": "fold_00_dqn",
                    "best_algorithm_by_avg_episode_net": "dqn",
                    "feature_columns": ["feature_score"],
                    "live_event_count": 2,
                    "live_event_phases": {"fold_completed": 1, "completed": 1},
                    "primary_cost_label": "base_23bp",
                    "primary_cost_bps": 23.0,
                    "oos_rows_used_for_fit": 0,
                    "model_build_allowed": False,
                    "paper_forward_allowed": False,
                    "live_broker_order_allowed": False,
                    "profit_claim_allowed": False,
                },
                "models": [
                    {
                        "algorithm": "dqn",
                        "model": "fold_00_dqn",
                        "policy": "stable_baselines3_dqn",
                        "model_path": "models/fold_00/portfolio_dqn_model.zip",
                        "model_sha256": "a" * 64,
                        "training_timesteps": 512,
                        "avg_episode_net_return_pct": 0.0,
                        "trade_count": 0,
                        "cost_bps": 23.0,
                        "passes_cost_gate": False,
                        "is_smoke": False,
                        "research_only": True,
                    }
                ],
                "live_events": {"schema_version": "stom_rl_live_event.v1", "event_count": 2, "phases": {"fold_completed": 1, "completed": 1}},
            }
        ),
        encoding="utf-8-sig",
    )
    (daily_sb3 / "rl_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "daily_portfolio_sb3_rl_manifest.v1",
                "artifact_type": "sb3_smoke",
                "stage": "G016_SLICE3_DAILY_PORTFOLIO_SB3_RESEARCH",
                "status": "COMPLETED_RESEARCH_ONLY",
                "authority": "D3_D2_DB_LINEAGE_APPROVED_RESEARCH_ONLY",
                "oos_rows_used_for_fit": 0,
                "false_locks": {
                    "model_build_allowed": False,
                    "paper_forward_allowed": False,
                    "live_broker_order_allowed": False,
                    "profit_claim_allowed": False,
                },
            }
        ),
        encoding="utf-8-sig",
    )
    (daily_sb3 / "rl_live_events.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "schema_version": "stom_rl_live_event.v1",
                    "run_id": "daily_sb3_run",
                    "algorithm": "portfolio_dqn",
                    "phase": phase,
                    "global_step": step,
                    "action": None,
                    "action_name": None,
                    "reward": 0.0,
                    "equity": 1000000.0,
                    "source": "daily_portfolio_sb3",
                    "info": {
                        "fold": 0 if phase == "fold_completed" else None,
                        "cost_scenario": "base_23bp",
                        "reward_kind": "raw_reward",
                        "reward_unit": "score",
                        "equity_kind": "krw_nav",
                        "equity_unit": "krw",
                        "action_recorded": False,
                        "device": {"requested": "cpu", "used": "cpu", "eval": "cpu"},
                        "source_lineage": {"d2_daily_db_sha256": "b" * 64},
                    },
                }
            )
            for step, phase in [(1, "fold_completed"), (2, "completed")]
        )
        + "\n",
        encoding="utf-8",
    )
    (daily_sb3 / "rl_live_summary.json").write_text(
        json.dumps({"schema_version": "stom_rl_live_event.v1", "event_count": 2, "phases": {"fold_completed": 1, "completed": 1}}),
        encoding="utf-8-sig",
    )
    (daily_sb3 / "source_hashes.json").write_text(
        json.dumps({"schema_version": "daily_portfolio_sb3_source_hashes.v1", "config_sha256": "c" * 64, "model_hashes": {"fold_00": "a" * 64}}),
        encoding="utf-8-sig",
    )
    (daily_sb3 / "training_manifest.json").write_text(
        json.dumps({"schema_version": "daily_portfolio_sb3_training_manifest.v1", "oos_rows_used_for_fit": 0, "primary_cost_label": "base_23bp"}),
        encoding="utf-8-sig",
    )

    readiness = root / "orderbook_readiness_run"
    readiness.mkdir()
    (readiness / "orderbook_rl_readiness_summary.json").write_text(
        json.dumps(
            {
                "mode": "stom_orderbook_rl_readiness",
                "artifact_type": "orderbook_rl_readiness",
                "summary": {
                    "readiness_status": "INCONCLUSIVE",
                    "verdict": "INCONCLUSIVE",
                    "is_live_ready": False,
                    "environment": "StomOrderbookRlEnv",
                    "eligible_episode_count": 12,
                    "quote_coverage": 0.98,
                    "valid_spread_coverage": 0.96,
                    "sample_env_smoke_passed": True,
                },
                "observation_features": ["ret_open", "spread_rel", "position"],
            }
        ),
        encoding="utf-8-sig",
    )
    _write_csv(
        readiness / "orderbook_rl_readiness.csv",
        "readiness_status,eligible_episode_count,quote_coverage,valid_spread_coverage",
        ["INCONCLUSIVE,12,0.98,0.96"],
    )


def test_rl_dashboard_helpers_list_detail_and_tables(tmp_path, monkeypatch):
    _write_rl_fixture(tmp_path)
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])

    runs = rl_dashboard.list_rl_runs(limit=10)
    names = {run["name"] for run in runs}
    run_by_name = {run["name"]: run for run in runs}
    detail = rl_dashboard.load_rl_run("bandit_run")
    trades = rl_dashboard.load_rl_table("bandit_run", "trades", limit=5)
    baseline_trades = rl_dashboard.load_rl_table("baseline_run", "trades", policy="buy_and_hold", limit=5)
    leaderboard_detail = rl_dashboard.load_rl_run("leaderboard_run")
    leaderboard_rows = rl_dashboard.load_rl_table("leaderboard_run", "leaderboard", limit=5)
    sb3_detail = rl_dashboard.load_rl_run("sb3_smoke_run")
    sb3_summary = rl_dashboard.load_rl_table("sb3_smoke_run", "summary", limit=5)
    sb3_events = rl_dashboard.load_rl_events("sb3_smoke_run", limit=5)
    cost_gate = rl_dashboard.load_rl_cost_gate("cost_gate_run", limit=5)
    readiness_detail = rl_dashboard.load_rl_run("orderbook_readiness_run")
    readiness_rows = rl_dashboard.load_rl_table("orderbook_readiness_run", "orderbook-readiness", limit=5)

    assert {
        "bandit_run",
        "cost_gate_run",
        "baseline_run",
        "leaderboard_run",
        "sb3_smoke_run",
        "orderbook_readiness_run",
    }.issubset(names)
    assert detail["artifact_type"] == "contextual_bandit"
    assert detail["model"]["model_type"] == "stom_fixed_horizon_contextual_bandit_ridge"
    assert trades["rows"][0]["net_return_pct"] == 1.5
    assert baseline_trades["rows"][0]["policy"] == "buy_and_hold"
    baseline_context = run_by_name["baseline_run"]["strategy_context"]
    baseline_risk = baseline_context["risk_policy_summary"]
    assert baseline_context["line"] == "rule_mainline"
    assert baseline_context["label"] == "RULE MAINLINE"
    assert baseline_context["primary_baseline"] == "ts_imb"
    assert baseline_context["is_reinforcement_learning"] is False
    assert baseline_context["is_live_ready"] is False
    assert baseline_context["is_profit_model"] is False
    assert baseline_risk["per_trade_fraction_pct"] == 10.0
    assert baseline_risk["max_concurrent"] == 3
    assert baseline_risk["daily_loss_limit_pct"] == 3.0
    assert baseline_risk["cost_bps"] == 23.0
    assert baseline_risk["tp_pct"] == 5.0
    assert baseline_risk["sl_pct"] == 1.0
    assert baseline_risk["risk_unit_account_pct"] == pytest.approx(0.123)
    assert leaderboard_detail["artifact_type"] == "performance_leaderboard"
    assert leaderboard_detail["summary"]["best_policy"] == "buy_and_hold"
    assert leaderboard_detail["strategy_context"]["line"] == "evaluation"
    assert leaderboard_detail["strategy_context"]["is_profit_model"] is False
    assert leaderboard_rows["rows"][1]["model"] == "contextual_bandit"
    assert detail["strategy_context"]["line"] == "rl_experiment"
    assert detail["strategy_context"]["label"] == "RL EXPERIMENT"
    assert detail["strategy_context"]["is_reinforcement_learning"] is True
    assert detail["strategy_context"]["is_live_ready"] is False
    assert detail["strategy_context"]["is_profit_model"] is False
    assert sb3_detail["artifact_type"] == "sb3_smoke"
    assert sb3_detail["model"]["model_type"] == "stable_baselines3_dqn"
    assert sb3_detail["summary"]["live_event_count"] == 1
    assert sb3_detail["strategy_context"]["line"] == "rl_experiment"
    assert sb3_detail["strategy_context"]["is_live_ready"] is False
    assert sb3_detail["strategy_context"]["is_profit_model"] is False
    assert sb3_summary["rows"][0]["model"] == "dqn_smoke"
    assert sb3_events["rows"][0]["action_name"] == "buy"
    assert cost_gate["summary"]["passing_policies"] == ["buy_and_hold"]
    assert cost_gate["gate"]["rows"][0]["passes_cost_gate"] is True
    assert readiness_detail["artifact_type"] == "orderbook_rl_readiness"
    assert readiness_detail["summary"]["readiness_status"] == "INCONCLUSIVE"
    assert readiness_detail["model"]["model_type"] == "marketable_only_orderbook_rl_environment"
    assert readiness_detail["strategy_context"]["line"] == "rl_experiment"
    assert readiness_detail["strategy_context"]["is_live_ready"] is False
    assert readiness_detail["strategy_context"]["is_profit_model"] is False
    assert readiness_rows["rows"][0]["quote_coverage"] == 0.98


def test_rl_dashboard_identity_fields_match_list_detail_and_api(tmp_path, monkeypatch):
    _write_rl_fixture(tmp_path)
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])

    list_record = next(run for run in rl_dashboard.list_rl_runs(limit=10) if run["name"] == "bandit_run")
    detail = rl_dashboard.load_rl_run("bandit_run")
    _assert_identity_contract(list_record)
    _assert_identity_contract(detail)
    assert _identity_fields(detail) == _identity_fields(list_record)

    client = flask_app.test_client()
    api_runs = client.get("/api/rl/runs")
    assert api_runs.status_code == 200
    api_list_record = next(run for run in api_runs.get_json()["runs"] if run["name"] == "bandit_run")
    api_detail = client.get("/api/rl/runs/bandit_run")
    assert api_detail.status_code == 200
    api_detail_payload = api_detail.get_json()
    _assert_identity_contract(api_list_record)
    _assert_identity_contract(api_detail_payload)
    assert _identity_fields(api_list_record) == _identity_fields(api_detail_payload) == _identity_fields(list_record)


def test_rl_dashboard_identity_changes_when_artifact_file_mutates(tmp_path, monkeypatch):
    _write_rl_fixture(tmp_path)
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])
    run_dir = tmp_path / "bandit_run"

    before = rl_dashboard.load_rl_run("bandit_run")
    summary_path = run_dir / "eval_summary.json"
    payload = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    payload["eval_summary"]["trade_count"] = 2
    summary_path.write_text(json.dumps(payload), encoding="utf-8-sig")
    latest_mtime = max(path.stat().st_mtime for path in run_dir.rglob("*") if path.is_file())
    future_mtime = max(time.time(), latest_mtime) + 2.0
    os.utime(summary_path, (future_mtime, future_mtime))

    after = rl_dashboard.load_rl_run("bandit_run")
    after_list = next(run for run in rl_dashboard.list_rl_runs(limit=10) if run["name"] == "bandit_run")
    assert after["run_uid"] == before["run_uid"]
    assert after["revision"] > before["revision"]
    assert after["source_sha256"] != before["source_sha256"]
    assert _identity_fields(after_list) == _identity_fields(after)


def test_rl_dashboard_run_uid_disambiguates_same_named_runs_under_different_roots(tmp_path, monkeypatch):
    left_root = tmp_path / "left"
    right_root = tmp_path / "right"
    run_name = "same_run"
    _write_minimal_baseline_run(left_root / run_name)
    _write_minimal_baseline_run(right_root / run_name)
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [left_root, right_root])

    records = [run for run in rl_dashboard.list_rl_runs(limit=10) if run["name"] == run_name]

    assert len(records) == 2
    for record in records:
        _assert_identity_contract(record)
    assert len({record["run_uid"] for record in records}) == 2
    assert len({record["source_sha256"] for record in records}) == 1


def _write_portfolio_fixture(root: Path) -> None:
    portfolio = root / "portfolio_paper_run"
    portfolio.mkdir()
    (portfolio / "portfolio_paper_summary.json").write_text(
        json.dumps(
            {
                "mode": "stom_rl_portfolio_paper_run",
                "run_name": "portfolio_paper_run",
                "config": {"cost_bps": 25.0, "max_positions": 2, "top_k_candidates": 3},
                "summary": {
                    "read_only": True,
                    "steps": 3,
                    "final_nav": 989504.0,
                    "trade_count": 2,
                    "risk_trigger_count": 1,
                    "order_write_path": False,
                },
                "walk_forward_summary": {"n_folds": 1, "best_policy_by_return": "no_trade"},
            }
        ),
        encoding="utf-8-sig",
    )
    (portfolio / "portfolio_walk_forward_report.json").write_text(
        json.dumps(
            {"mode": "stom_rl_portfolio_walk_forward", "summary": {"n_folds": 1, "best_policy_by_return": "no_trade"}}
        ),
        encoding="utf-8-sig",
    )
    (portfolio / "risk_triggers.json").write_text(
        json.dumps({"risk_triggers": [{"timestamp": "2025-07-09T09:01:22", "reason": "consecutive_losses"}]}),
        encoding="utf-8-sig",
    )
    _write_csv(
        portfolio / "nav.csv",
        "timestamp,step,nav,cash,position_count",
        ["2025-07-09T09:00:05,0,1000000.0,1000000.0,0", "2025-07-09T09:00:25,1,989504.0,498906.0,2"],
    )
    _write_csv(
        portfolio / "decisions.csv",
        "timestamp,proposed_action,executed_action,action_type,symbol,blocked,blocked_reason,nav_after",
        ["2025-07-09T09:00:05,1,1,buy,100,False,,999375.0"],
    )
    _write_csv(
        portfolio / "trades.csv",
        "timestamp,symbol,side,price,quantity,realized_pnl",
        ["2025-07-09T09:00:05,100,buy,106100.0,2.35,0.0"],
    )
    _write_csv(
        portfolio / "portfolio_walk_forward_folds.csv",
        "fold_index,policy,final_nav,return_pct,max_drawdown_pct,trade_count,test_start,test_end",
        ["0,no_trade,1000000.0,0.0,0.0,0,2025-07-09T09:10:30,2025-07-09T09:13:55"],
    )
    _write_csv(
        portfolio / "candidates.csv",
        "timestamp,symbol,passed,rank_score",
        ["2025-07-09T09:00:05,000100,True,96.1"],
    )
    # Live step events (portfolio NAV stream) published by Page 14 so the
    # dashboard's realtime follow/replay view streams the portfolio run.
    (portfolio / "rl_live_events.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "run_id": "portfolio_paper_run",
                    "algorithm": "portfolio",
                    "phase": "train",
                    "global_step": step,
                    "action": 1 if step == 1 else 0,
                    "action_name": "buy" if step == 1 else "hold",
                    "reward": 0.0019 if step == 1 else -0.0105,
                    "equity": 1000000.0 if step == 1 else 989504.0,
                    "position": float(step),
                    "timestamp": f"2025-07-09T09:00:0{step}",
                    "schema_version": "stom_rl_live_event.v1",
                    "info": {"nav": 1000000.0 if step == 1 else 989504.0, "cash": 500000.0},
                }
            )
            for step in (1, 2)
        )
        + "\n",
        encoding="utf-8",
    )


def test_rl_dashboard_serves_portfolio_paper_run(tmp_path, monkeypatch):
    _write_portfolio_fixture(tmp_path)
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])

    runs = rl_dashboard.list_rl_runs(limit=10)
    types = {run["name"]: run["artifact_type"] for run in runs}
    assert types.get("portfolio_paper_run") == "portfolio_paper"

    detail = rl_dashboard.load_rl_run("portfolio_paper_run")
    assert detail["artifact_type"] == "portfolio_paper"
    assert detail["summary"]["final_nav"] == 989504.0
    assert detail["detail"]["walk_forward_summary"]["n_folds"] == 1
    assert detail["detail"]["risk_trigger_reasons"]["consecutive_losses"] == 1

    nav = rl_dashboard.load_rl_table("portfolio_paper_run", "nav", limit=10)
    assert nav["rows"][-1]["nav"] == 989504.0
    decisions = rl_dashboard.load_rl_table("portfolio_paper_run", "decisions", limit=10)
    assert decisions["rows"][0]["action_type"] == "buy"
    folds = rl_dashboard.load_rl_table("portfolio_paper_run", "portfolio_folds", limit=10)
    assert folds["rows"][0]["policy"] == "no_trade"


def test_flask_serves_portfolio_paper_tables(tmp_path, monkeypatch):
    _write_portfolio_fixture(tmp_path)
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])

    client = flask_app.test_client()

    runs = client.get("/api/rl/runs")
    assert runs.status_code == 200
    assert any(
        run["name"] == "portfolio_paper_run" and run["artifact_type"] == "portfolio_paper"
        for run in runs.get_json()["runs"]
    )

    nav = client.get("/api/rl/runs/portfolio_paper_run/table/nav")
    assert nav.status_code == 200
    assert nav.get_json()["rows"][-1]["nav"] == 989504.0

    folds = client.get("/api/rl/runs/portfolio_paper_run/table/portfolio_folds")
    assert folds.status_code == 200
    assert folds.get_json()["rows"][0]["policy"] == "no_trade"


def test_portfolio_paper_run_serves_live_events(tmp_path, monkeypatch):
    """A published portfolio run exposes its NAV stream through the existing
    ``/table/events`` route so the dashboard's follow/replay view is non-empty."""

    _write_portfolio_fixture(tmp_path)
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])

    events = rl_dashboard.load_rl_table("portfolio_paper_run", "events", limit=50)
    assert len(events["rows"]) == 2
    last = events["rows"][-1]
    assert last["algorithm"] == "portfolio"
    assert last["phase"] == "train"
    assert last["equity"] == 989504.0  # NAV mapped to equity

    client = flask_app.test_client()
    response = client.get("/api/rl/runs/portfolio_paper_run/table/events")
    assert response.status_code == 200
    rows = response.get_json()["rows"]
    assert rows and all(row["algorithm"] == "portfolio" for row in rows)
    assert any(row.get("equity") for row in rows)


def test_rl_dashboard_rejects_path_traversal(tmp_path, monkeypatch):
    _write_rl_fixture(tmp_path)
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])

    try:
        rl_dashboard.load_rl_run("../secret")
    except ValueError as exc:
        assert "direct child" in str(exc) or "Invalid" in str(exc)
    else:
        raise AssertionError("path traversal was accepted")


def test_rl_dashboard_rejects_symlink_escape(tmp_path, monkeypatch):
    run_root = tmp_path / "runs"
    run_root.mkdir()
    outside = tmp_path / "outside_run"
    outside.mkdir()
    (outside / "baseline_summary.json").write_text(
        json.dumps({"mode": "stom_rl_baseline_run", "summary": {"policy_count": 1}}),
        encoding="utf-8-sig",
    )
    link = run_root / "linked_run"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [run_root])

    assert "linked_run" not in {run["name"] for run in rl_dashboard.list_rl_runs(limit=10)}

    with pytest.raises(ValueError, match="escapes RL root"):
        rl_dashboard.load_rl_run("linked_run")


def test_rl_dashboard_rejects_symlinked_artifact_file(tmp_path, monkeypatch):
    run_root = tmp_path / "runs"
    run_root.mkdir()
    run = run_root / "baseline_run"
    run.mkdir()
    (run / "baseline_summary.json").write_text(
        json.dumps({"mode": "stom_rl_baseline_run", "summary": {"policy_count": 1}}),
        encoding="utf-8-sig",
    )
    policy_dir = run / "buy_and_hold"
    policy_dir.mkdir()
    outside = tmp_path / "outside_trades.csv"
    outside.write_text("secret\nleaked\n", encoding="utf-8-sig")
    try:
        os.symlink(outside, policy_dir / "trades.csv")
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [run_root])

    with pytest.raises(FileNotFoundError):
        rl_dashboard.load_rl_table("baseline_run", "trades", policy="buy_and_hold", limit=5)


def test_webui_default_bind_is_localhost_only():
    run_launcher = (REPO_ROOT / "webui" / "run.py").read_text(encoding="utf-8")
    direct_app = (REPO_ROOT / "webui" / "app.py").read_text(encoding="utf-8")

    assert 'KRONOS_WEBUI_HOST", "127.0.0.1"' in run_launcher
    assert 'KRONOS_WEBUI_HOST", "127.0.0.1"' in direct_app
    assert "host='0.0.0.0'" not in direct_app


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
    assert detail.get_json()["strategy_context"]["line"] == "rl_experiment"
    assert detail.get_json()["strategy_context"]["is_live_ready"] is False

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

    readiness = client.get("/api/rl/runs/orderbook_readiness_run")
    assert readiness.status_code == 200
    assert readiness.get_json()["artifact_type"] == "orderbook_rl_readiness"
    assert readiness.get_json()["strategy_context"]["is_profit_model"] is False

    events = client.get("/api/rl/runs/sb3_smoke_run/events")
    assert events.status_code == 200
    assert events.get_json()["rows"][0]["phase"] == "eval"

    progress = client.get("/api/rl/progress")
    assert progress.status_code == 200
    assert progress.get_json()["mode"] == "stom_rl_page_progress"

    bad = client.get("/api/rl/runs/..%5Csecret")
    assert bad.status_code in {400, 404}
