import json
from pathlib import Path

import pytest

from stom_rl import daily_scenario_runner as runner
from stom_rl import daily_scenario_batch as batch
from stom_rl import daily_rl_train as daily_train


def test_daily_model_scenario_runner_writes_locked_manifest(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(runner, "DEFAULT_SCENARIO_ROOT", tmp_path / "scenarios")

    def fake_dataset(**kwargs):
        calls.append(("dataset", kwargs))
        out = tmp_path / "dataset" / kwargs["run_id"]
        out.mkdir(parents=True, exist_ok=True)
        return {
            "dataset": {"manifest": {"status": "PASS"}},
            "written": {"artifact_dir": str(out), "dataset_manifest_path": str(out / "dataset_manifest.json")},
        }

    def fake_prediction(**kwargs):
        calls.append(("prediction", kwargs))
        out = tmp_path / "prediction" / kwargs["run_id"]
        out.mkdir(parents=True, exist_ok=True)
        return {
            "result": {"manifest": {"status": "WATCH"}},
            "written": {"artifact_dir": str(out), "prediction_manifest_path": str(out / "prediction_manifest.json")},
        }

    def fake_rl(**kwargs):
        calls.append(("rl", kwargs))
        out = tmp_path / "portfolio" / kwargs["run_id"]
        out.mkdir(parents=True, exist_ok=True)
        return {
            "result": {"manifest": {"status": "RESEARCH_ONLY"}},
            "written": {"artifact_dir": str(out), "rl_manifest_path": str(out / "rl_manifest.json")},
        }

    def fake_walk_forward(**kwargs):
        calls.append(("walk_forward", kwargs))
        out = tmp_path / "walk_forward" / kwargs["run_id"]
        out.mkdir(parents=True, exist_ok=True)
        return {
            "result": {
                "gate_verdict": {
                    "status": "NO-GO",
                    "readiness_status": "D5_NO_GO_RESEARCH_ONLY_GATE",
                    "selected_strategy": "equal_weight_topk_momentum",
                    "n_folds": 5,
                    "purge_days": 5,
                    "embargo_days": 5,
                    "cost_sensitivity_bp": [0, 23, 46],
                    "reasons": ["RESEARCH_ONLY_NO_PROFIT_LIVE_BROKER_ORDER_CLAIM"],
                }
            },
            "written": {
                "artifact_dir": str(out),
                "walk_forward_manifest_path": str(out / "walk_forward_manifest.json"),
                "gate_verdict_path": str(out / "gate_verdict.json"),
            },
        }

    monkeypatch.setattr(runner, "build_and_write_daily_ohlcv_dataset", fake_dataset)
    monkeypatch.setattr(runner, "run_and_write_daily_prediction", fake_prediction)
    monkeypatch.setattr(runner, "run_and_write_daily_rl", fake_rl)
    monkeypatch.setattr(runner, "run_and_write_daily_walk_forward", fake_walk_forward)

    manifest = runner.run_daily_model_scenario(
        run_id="scenario_unit",
        overwrite=True,
        max_symbols=8,
        max_rows_per_symbol=120,
        candidate_limit=10,
        max_positions=3,
        episodes=3,
        action_filter_mode="confidence_abstain_v1",
    )

    assert [name for name, _ in calls] == ["dataset", "prediction", "rl", "walk_forward"]
    assert calls[0][1]["max_symbols"] == 8
    assert calls[2][1]["candidate_limit"] == 10
    assert calls[2][1]["action_filter_mode"] == "confidence_abstain_v1"
    assert calls[3][1]["purge_days"] == 5
    assert manifest["status"] == "NO-GO"
    assert manifest["readiness_status"] == "D5_NO_GO_RESEARCH_ONLY_GATE"
    assert manifest["model_build_allowed"] is False
    assert manifest["paper_forward_allowed"] is False
    assert manifest["live_broker_order_allowed"] is False
    assert manifest["gate_verdict_summary"]["cost_sensitivity_bp"] == [0, 23, 46]

    manifest_path = Path(manifest["artifact_paths"]["scenario_manifest"])
    assert manifest_path.is_file()
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert persisted["run_id"] == "scenario_unit"
    assert persisted["artifact_paths"]["candidate_generation_config"].endswith("candidate_generation_config.json")


def test_daily_model_scenario_runner_rejects_unsafe_run_id(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "DEFAULT_SCENARIO_ROOT", tmp_path / "scenarios")
    with pytest.raises(ValueError, match="run_id"):
        runner.run_daily_model_scenario(run_id="../bad")

def test_daily_scenario_batch_runs_multiple_locked_scenarios(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(batch, "DEFAULT_SCENARIO_BATCH_ROOT", tmp_path / "batches")

    def fake_run_daily_model_scenario(**kwargs):
        calls.append(kwargs)
        run_id = kwargs["run_id"]
        out = tmp_path / "scenarios" / run_id
        out.mkdir(parents=True, exist_ok=True)
        return {
            "run_id": run_id,
            "status": "NO-GO",
            "readiness_status": "D5_NO_GO_RESEARCH_ONLY_GATE",
            "artifact_paths": {"scenario_manifest": str(out / "scenario_manifest.json")},
            "gate_verdict_summary": {
                "status": "NO-GO",
                "readiness_status": "D5_NO_GO_RESEARCH_ONLY_GATE",
                "selected_strategy": "equal_weight_topk_momentum",
                "n_folds": kwargs["n_folds"],
                "purge_days": kwargs["purge_days"],
                "embargo_days": kwargs["embargo_days"],
                "cost_sensitivity_bp": [0, 23, 46],
                "reasons": ["RESEARCH_ONLY_NO_PROFIT_LIVE_BROKER_ORDER_CLAIM"],
            },
        }

    monkeypatch.setattr(batch, "run_daily_model_scenario", fake_run_daily_model_scenario)

    plan = {
        "batch_id": "batch_unit",
        "defaults": {
            "max_symbols": 8,
            "max_rows_per_symbol": 120,
            "quality_table_limit": 0,
            "episodes": 3,
            "candidate_limit": 10,
            "max_positions": 3,
            "n_folds": 5,
            "top_k": 10,
            "purge_days": 5,
            "embargo_days": 5,
        },
        "scenarios": [
            {"scenario_id": "seed7", "overrides": {"rl_seed": 7, "wf_seed": 17}},
            {"scenario_id": "seed11", "overrides": {"rl_seed": 11, "wf_seed": 31, "action_filter_mode": "margin_abstain_v1"}},
        ],
    }

    manifest = batch.run_daily_scenario_batch(plan=plan, overwrite=True)

    assert [call["run_id"] for call in calls] == ["batch_unit__seed7", "batch_unit__seed11"]
    assert calls[0]["max_symbols"] == 8
    assert calls[1]["rl_seed"] == 11
    assert calls[1]["action_filter_mode"] == "margin_abstain_v1"
    assert manifest["mode"] == "daily_ohlcv_model_scenario_batch"
    assert manifest["platform_stage"] == "SCENARIO_BATCH_RUNNER_MVP"
    assert manifest["scenario_count"] == 2
    assert manifest["failed_count"] == 0
    assert manifest["gate_status_counts"] == {"NO-GO": 2}
    assert manifest["model_build_allowed"] is False
    assert manifest["paper_forward_allowed"] is False
    assert manifest["live_broker_order_allowed"] is False
    assert all(row["cost_sensitivity_bp"] == [0, 23, 46] for row in manifest["comparison_rows"])

    manifest_path = Path(manifest["artifact_paths"]["scenario_batch_manifest"])
    assert manifest_path.is_file()
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert persisted["batch_id"] == "batch_unit"
    assert persisted["artifact_paths"]["scenario_batch_plan"].endswith("scenario_batch_plan.json")


def test_daily_scenario_batch_rejects_sub_gate_folds(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "DEFAULT_SCENARIO_BATCH_ROOT", tmp_path / "batches")
    plan = {
        "batch_id": "bad_batch",
        "defaults": {"n_folds": 4, "purge_days": 5, "embargo_days": 5},
        "scenarios": [{"scenario_id": "bad"}],
    }

    with pytest.raises(ValueError, match="n_folds"):
        batch.run_daily_scenario_batch(plan=plan, overwrite=True)


def _fake_stability_result(seed: int, episodes: int, *, test_return: float = 0.01, trade_count: int = 2):
    metrics = [
        {"split": "val", "total_net_return": test_return / 2, "max_drawdown": 0.01, "trade_count": trade_count, "never_trade": trade_count == 0},
        {"split": "test", "total_net_return": test_return, "max_drawdown": 0.02, "trade_count": trade_count, "never_trade": trade_count == 0},
        {"split": "val+test", "total_net_return": test_return * 1.5, "max_drawdown": 0.03, "trade_count": trade_count * 2, "never_trade": trade_count == 0},
    ]
    return {
        "result": {
            "manifest": {
                "readiness_status": "D4_RESEARCH_ONLY_DIAGNOSTICS",
                "checkpoint_readiness": True,
                "environment_readiness": True,
                "model_ready": False,
                "prediction_run_dir": "prediction_2026_06_14_g004_d3_baseline_hardened",
                "parent_training_run": {
                    "seed": seed,
                    "episodes": episodes,
                    "prediction_manifest_sha": "b1d4",
                    "source_hashes": {"daily_rl_train.py": "abc123"},
                },
            },
            "policy_metrics": {"metrics": metrics},
            "baseline_comparison": {
                "best_d3_total_net_return": 0.03,
                "equal_weight_topk_total_net_return": 0.02,
                "no_trade_cash_total_net_return": 0.0,
            },
            "source_hashes": {"daily_rl_train.py": "abc123"},
            "verdict": {"reasons": ["D5_WALK_FORWARD_NOT_RUN"]},
        },
        "written": {
            "artifact_dir": f"/tmp/daily_d4_stability_2026_07_12_seed{seed}_ep{episodes}",
            "artifact_hashes": {"rl_manifest": f"{seed:02x}" * 32},
        },
    }


def _write_sweep_prereqs(tmp_path, monkeypatch):
    prediction_dir = tmp_path / "prediction"
    prediction_dir.mkdir(exist_ok=True)
    prediction_manifest = prediction_dir / "prediction_manifest.json"
    prediction_manifest.write_text('{"run_id":"prediction_2026_06_14_g004_d3_baseline_hardened"}\n', encoding="utf-8")
    prereg_doc = tmp_path / "prereg.md"
    prereg_doc.write_text("# prereg\n", encoding="utf-8")
    source_sha = "f" * 40
    portfolio_root = tmp_path / "portfolio"
    monkeypatch.setattr(batch, "D4_STABILITY_PREREG_SHA256", batch._sha256_file(prereg_doc))
    monkeypatch.setattr(
        batch,
        "D4_STABILITY_PREDICTION_MANIFEST_SHA256",
        batch._sha256_file(prediction_manifest),
    )
    monkeypatch.setattr(batch, "_git_head_sha", lambda: source_sha)
    monkeypatch.setattr(batch, "DEFAULT_PORTFOLIO_ROOT", portfolio_root)
    return prediction_dir, prereg_doc, source_sha, portfolio_root




def test_d4_stability_fixed_grid_order_and_duplicate_drift_rejection():
    cells = batch.build_d4_stability_cells(seeds="7,17,29,41,53", episodes="8,32,128")

    assert len(cells) == 15
    assert [(cell["episodes"], cell["seed"]) for cell in cells] == [
        (episode_count, seed)
        for episode_count in (8, 32, 128)
        for seed in (7, 17, 29, 41, 53)
    ]
    assert cells[0]["run_id"] == "daily_d4_stability_2026_07_12_seed7_ep8"
    assert cells[-1]["stage"] == "full"
    assert all(cell["config"]["score_column"] == "score_supervised_linear_ranker" for cell in cells)
    assert all(cell["config"]["candidate_limit"] == 20 for cell in cells)
    assert all(cell["config"]["max_positions"] == 5 for cell in cells)
    assert all(cell["config"]["observation_mode"] == "v1" for cell in cells)

    with pytest.raises(ValueError, match="duplicate"):
        batch.build_d4_stability_cells(seeds="7,7,17,29,41", episodes="8,32,128")
    with pytest.raises(ValueError, match="exactly"):
        batch.build_d4_stability_cells(seeds="7,17,29,41,54", episodes="8,32,128")


def test_d4_stability_sweep_fails_before_cells_without_prereqs(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(batch, "run_and_write_daily_rl", lambda **kwargs: calls.append(kwargs))

    with pytest.raises(FileNotFoundError, match="missing_prereg_doc"):
        batch.run_d4_stability_sweep(
            sweep_seeds="7,17,29,41,53",
            sweep_episodes="8,32,128",
            prediction_run_dir=tmp_path / "prediction",
            stability_root=tmp_path / "stability",
            prereg_doc=tmp_path / "missing.md",
            source_git_sha="fb53fe5",
        )
    assert calls == []

    prereg_doc = tmp_path / "prereg.md"
    prereg_doc.write_text("# prereg\n", encoding="utf-8")
    monkeypatch.setattr(batch, "D4_STABILITY_PREREG_SHA256", batch._sha256_file(prereg_doc))
    with pytest.raises(FileNotFoundError, match="missing_prediction_manifest"):
        batch.run_d4_stability_sweep(
            sweep_seeds="7,17,29,41,53",
            sweep_episodes="8,32,128",
            prediction_run_dir=tmp_path / "prediction",
            stability_root=tmp_path / "stability",
            prereg_doc=prereg_doc,
            source_git_sha="f" * 40,
        )
    assert calls == []

    prediction_dir, prereg_doc, source_sha, portfolio_root = _write_sweep_prereqs(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="source_git_sha"):
        batch.run_d4_stability_sweep(
            sweep_seeds="7,17,29,41,53",
            sweep_episodes="8,32,128",
            prediction_run_dir=prediction_dir,
            stability_root=portfolio_root / "stability",
            prereg_doc=prereg_doc,
        )
    assert calls == []

    with pytest.raises(ValueError, match="source_git_sha_mismatch"):
        batch.run_d4_stability_sweep(
            sweep_seeds="7,17,29,41,53",
            sweep_episodes="8,32,128",
            prediction_run_dir=prediction_dir,
            stability_root=portfolio_root / "stability",
            prereg_doc=prereg_doc,
            source_git_sha="e" * 40,
        )
    assert calls == []

    with pytest.raises(ValueError, match="must stay under daily_ohlcv_portfolio"):
        batch.run_d4_stability_sweep(
            sweep_seeds="7,17,29,41,53",
            sweep_episodes="8,32,128",
            prediction_run_dir=prediction_dir,
            stability_root=tmp_path / "outside",
            prereg_doc=prereg_doc,
            source_git_sha=source_sha,
        )
    assert calls == []




def test_d4_stability_summary_keeps_all_metrics_failures_and_is_deterministic(tmp_path, monkeypatch):
    calls = []

    def fake_run_and_write_daily_rl(**kwargs):
        calls.append(kwargs)
        if kwargs["seed"] == 29 and kwargs["episodes"] == 32:
            raise RuntimeError("synthetic negative/high-mdd cell failure")
        return _fake_stability_result(
            kwargs["seed"],
            kwargs["episodes"],
            test_return=-0.04 if kwargs["seed"] == 41 else 0.01,
            trade_count=0 if kwargs["seed"] == 53 else 2,
        )

    monkeypatch.setattr(batch, "run_and_write_daily_rl", fake_run_and_write_daily_rl)
    prediction_dir, prereg_doc, source_sha, portfolio_root = _write_sweep_prereqs(tmp_path, monkeypatch)


    summary = batch.run_d4_stability_sweep(
        sweep_seeds="7,17,29,41,53",
        sweep_episodes="8,32,128",
        prediction_run_dir=prediction_dir,
        stability_root=portfolio_root / "stability",
        prereg_doc=prereg_doc,
        source_git_sha=source_sha,
        overwrite=True,
    )

    assert [call["run_id"] for call in calls][:5] == [
        "daily_d4_stability_2026_07_12_seed7_ep8",
        "daily_d4_stability_2026_07_12_seed17_ep8",
        "daily_d4_stability_2026_07_12_seed29_ep8",
        "daily_d4_stability_2026_07_12_seed41_ep8",
        "daily_d4_stability_2026_07_12_seed53_ep8",
    ]
    assert all(call["prediction_run_dir"] == (tmp_path / "prediction").resolve() for call in calls)
    assert summary["decision"] == "INCONCLUSIVE"
    assert summary["cell_count"] == 15
    assert len(summary["cells"]) == 15
    failed = [cell for cell in summary["cells"] if cell["status"] == "failed"]
    assert failed and failed[0]["run_id"] == "daily_d4_stability_2026_07_12_seed29_ep32"
    negative = next(cell for cell in summary["cells"] if cell["seed"] == 41 and cell["episodes"] == 8)
    assert negative["metrics"]["test"]["total_net_return"] < 0
    never_trade = next(cell for cell in summary["cells"] if cell["seed"] == 53 and cell["episodes"] == 8)
    assert never_trade["metrics"]["test"]["never_trade"] is True
    assert negative["test_oos_primary"] == negative["metrics"]["test"]
    assert negative["val_test_secondary"] == negative["metrics"]["val+test"]
    assert negative["baseline_deltas_23bp"]["test_oos_primary"] == {
        "vs_no_trade_cash": None,
        "vs_equal_weight_topk_momentum": None,
        "vs_best_frozen_rule": None,
        "reason": "UNAVAILABLE_BASELINE_SCOPE_IS_VAL_TEST_SECONDARY_NOT_TEST_OOS",
    }
    assert negative["baseline_deltas_23bp"]["source_val_test_secondary_reference"]["vs_no_trade_cash"] == negative["metrics"]["val+test"]["total_net_return"]
    assert negative["readiness"]["checkpoint_readiness"] is True
    assert negative["readiness"]["environment_readiness"] is True
    assert negative["readiness"]["model_ready"] is False
    with pytest.raises(ValueError, match="readiness"):
        batch._readiness_payload(
            {"prediction_run_dir": str(prediction_dir), "readiness_status": "D4_RESEARCH_ONLY_DIAGNOSTICS"}
        )
    assert summary["prereg_sha256"]
    assert summary["prediction_manifest_sha256"] == batch._sha256_file(prediction_dir / "prediction_manifest.json")

    persisted = json.loads(Path(summary["artifact_paths"]["stability_summary"]).read_text(encoding="utf-8"))
    assert persisted["deterministic_content_hash"] == summary["deterministic_content_hash"]

    rebuilt = batch.build_d4_stability_summary(
        summary_cells=summary["cells"],
        prereg_path=prereg_doc,
        prereg_hash=summary["prereg_sha256"],
        source_git_sha=source_sha,
        prediction_dir=prediction_dir.resolve(),
        prediction_manifest_hash=summary["prediction_manifest_sha256"],
        registry_events=summary["registry_events"],
        root=portfolio_root / "stability",
        dry_run=False,
        generated_at="fixed",
    )
    assert rebuilt["deterministic_content_hash"] == summary["deterministic_content_hash"]


def test_d4_stability_registry_transitions_and_metadata(tmp_path, monkeypatch):
    calls = []

    def fake_register(registry_path, **kwargs):
        calls.append(("register", registry_path, kwargs))
        assert kwargs["cost_bps"] == batch.ROUND_TRIP_COST_BP
        assert kwargs["split_hash"] == batch._sha256_file(prediction_dir / "prediction_manifest.json")
        assert kwargs["artifact_hashes"] is None
        assert kwargs["prereg_doc"].endswith("prereg.md")
        assert kwargs["source_git_sha"] == source_sha
        assert kwargs["stage"] in {"smoke", "full"}
        assert "daily_d4_stability_2026_07_12" in kwargs["run_dir"]
        return {"run_id": kwargs["run_id"], "status": "queued"}

    def fake_set_status(registry_path, run_id, status, **kwargs):
        calls.append(("set_status", registry_path, {"run_id": run_id, "status": status, **kwargs}))
        return {"run_id": run_id, "status": status}

    monkeypatch.setattr(batch.run_registry, "register_run", fake_register)
    monkeypatch.setattr(batch.run_registry, "set_status", fake_set_status)

    def fake_update_artifacts(registry_path, run_id, **kwargs):
        calls.append(("update_run_artifacts", registry_path, {"run_id": run_id, **kwargs}))
        assert kwargs["artifact_hashes"]["rl_manifest"]
        return {"run_id": run_id, "status": "running"}

    monkeypatch.setattr(batch.run_registry, "update_run_artifacts", fake_update_artifacts)
    monkeypatch.setattr(
        batch,
        "run_and_write_daily_rl",
        lambda **kwargs: _fake_stability_result(kwargs["seed"], kwargs["episodes"]),
    )
    prediction_dir, prereg_doc, source_sha, portfolio_root = _write_sweep_prereqs(tmp_path, monkeypatch)


    summary = batch.run_d4_stability_sweep(
        sweep_seeds="7,17,29,41,53",
        sweep_episodes="8,32,128",
        prediction_run_dir=prediction_dir,
        stability_root=portfolio_root / "stability",
        registry_path=tmp_path / "factory_registry.sqlite",
        prereg_doc=prereg_doc,
        source_git_sha=source_sha,
        overwrite=True,
    )

    register_calls = [call for call in calls if call[0] == "register"]
    status_calls = [call for call in calls if call[0] == "set_status"]
    assert len(register_calls) == 15
    assert [call[2]["status"] for call in status_calls[:2]] == ["running", "done"]
    assert len([call for call in status_calls if call[2]["status"] == "running"]) == 15
    assert len([call for call in status_calls if call[2]["status"] == "done"]) == 15
    assert len([call for call in calls if call[0] == "update_run_artifacts"]) == 15
    assert summary["decision"] == "STABLE_NO_GO"
    assert summary["research_locks"]["aliases_excluded"] is True


def test_actual_trade_count_uses_executed_turnover_not_invested_hold_rows():
    reward_rows = [
        {"no_trade_action": True, "turnover": 0.0},
        {"no_trade_action": False, "turnover": 0.2},
        {"no_trade_action": False, "turnover": 0.0},
        {"no_trade_action": False, "turnover": 0.4},
    ]

    assert daily_train._actual_trade_count(reward_rows) == 2

def test_daily_rl_artifact_manifests_include_parent_training_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_train, "DEFAULT_PORTFOLIO_ROOT", tmp_path / "portfolio")
    parent_identity = {
        "seed": 7,
        "episodes": 8,
        "prediction_manifest_sha": "b1d4",
        "prediction_artifact_hashes": {"prediction_manifest": "b1d4"},
        "source_hashes": {"daily_rl_train.py": "abc123"},
    }
    result = {
        "manifest": {
            "schema_version": 1,
            "guardrail": "research-only",
            "parent_training_run": parent_identity,
            "policy_type": "tabular_q",
            "observation_mode": "v1",
            "action_prior_mode": "none",
            "action_prior_strength": 0.0,
            "action_filter_mode": "none",
        },
        "observation_manifest": {"observation_fields": [{"name": "field"}]},
        "policy_metrics": {"metrics": []},
        "episode_metrics": [],
        "positions": [],
        "invalid_actions": [],
        "reward_breakdown": [],
        "state_observations": [],
        "learning_curve": [],
        "action_distribution": [],
        "turnover": [],
        "drawdown": [],
        "reward_component_summary": {},
        "reward_action_ablations": [],
        "reward_action_ablation_summary": {},
        "no_trade_opportunity_diagnostics": [],
        "no_trade_opportunity_summary": {},
        "abstention_reasons": [],
        "policy_baseline_comparison": [],
        "policy_nav": [],
        "baseline_comparison": {"missing_frozen_baselines": []},
        "source_hashes": parent_identity["source_hashes"],
        "verdict": {"status": "RESEARCH_ONLY", "readiness_status": "D4_RESEARCH_ONLY_DIAGNOSTICS"},
    }

    written = daily_train.write_rl_artifacts(result, run_id="parent_identity_unit", overwrite=True)

    rl_manifest = json.loads(Path(written["rl_manifest_path"]).read_text(encoding="utf-8"))
    training_manifest = json.loads(Path(written["training_manifest_path"]).read_text(encoding="utf-8"))
    policy_eval_manifest = json.loads(Path(written["policy_evaluation_manifest_path"]).read_text(encoding="utf-8"))
    assert rl_manifest["parent_training_run"] == parent_identity
    assert training_manifest["parent_training_run"] == parent_identity
    assert policy_eval_manifest["parent_training_run"] == parent_identity
