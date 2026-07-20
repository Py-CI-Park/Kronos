"""Contract coverage for the V7 self-contained HTML report builder."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from stom_rl.v7_report_builder import ReportBuildError, build_project_report, build_report

from tests.test_v6_platform_api import _write_index_artifacts


def _run_manifest() -> dict:
    def seed(nav: float, curve: list[float], trades: int) -> dict:
        return {
            "best_episode": 1,
            "episodes_ran": len(curve),
            "final_val_metrics": {
                "cost_scenario_navs": {"0.0000": nav + 1000000.0, "0.0023": nav, "0.0046": nav - 1000000.0},
                "max_drawdown": 0.1,
                "max_invested_krw": 50000000.0,
                "max_positions_per_session": 10,
                "nav": nav,
                "total_net_return_pct": (nav / 60000000.0 - 1.0) * 100.0,
                "trade_count": trades,
                "turnover_days": trades // 2,
            },
            "val_nav_curve": curve,
        }

    control = dict(seed(59000000.0, [60000000.0, 59000000.0], 10))
    control.update({
        "shuffled_train_labels_sha256": "b" * 64,
        "train_labels_changed": True,
        "train_labels_sha256": "c" * 64,
    })
    return {
        "baselines": {
            "no_trade": {"cost_scenario_navs": {"0.0023": 60000000.0}, "nav": 60000000.0},
            "random_topk": {"cost_scenario_navs": {"0.0023": 58000000.0}, "nav": 58000000.0},
            "rule_topk_ret5": {"cost_scenario_navs": {"0.0023": 37000000.0}, "nav": 37000000.0},
        },
        "bucket_boundaries": {"ret_5d_prev": [-0.04, 0.04]},
        "dataset_csv_sha256": "a" * 64,
        "dataset_run_id": "v7_dataset_test_001",
        "false_research_locks": {
            "go_summary_allowed": False,
            "live_broker_order_allowed": False,
            "model_build_allowed": False,
            "paper_forward_allowed": False,
            "profitability_claim_allowed": False,
            "promotion_allowed": False,
        },
        "generated_utc": "2026-07-20T00:00:00Z",
        "hyperparams": {
            "alpha": 0.1,
            "capital_krw": 60000000.0,
            "max_invested_krw": 50000000.0,
            "nav_formula": "NAV = 60000000 + ...",
            "primary_cost_rate": 0.0023,
            "slot_budget_krw": 5000000.0,
            "slots": 10,
        },
        "missing_h1_label_excluded": {"train": 5, "val": 1},
        "per_seed": {
            "0": seed(64000000.0, [55000000.0, 64000000.0], 100),
            "1": seed(55000000.0, [60000000.0, 55000000.0], 80),
        },
        "prereg": {"id": "KRONOS-V7-PREREG-TEST", "sha256": "d" * 64},
        "schema_version": "kronos_v6_train_run.v1",
        "seeds": [0, 1],
        "shuffled_label_control": {"0": control},
        "test": {"state": "NOT_RUN"},
        "verdict_candidate": {"reasons": ["only one seed satisfies validation criterion"], "value": "INCONCLUSIVE"},
    }


@pytest.fixture()
def run_dir(tmp_path) -> Path:
    dataset_dir = tmp_path / "v7_dataset_test_001"
    run_dir = dataset_dir / "train_test"
    run_dir.mkdir(parents=True)
    (run_dir / "run_manifest.json").write_text(json.dumps(_run_manifest(), ensure_ascii=False), encoding="utf-8")
    (dataset_dir / "dataset_manifest.json").write_text(json.dumps({
        "schema_version": "kronos_v6_joined_dataset.v1",
        "dataset_sha256": "a" * 64,
        "generated_utc": "2026-07-19T00:00:00Z",
        "split_row_counts": {"train": 100, "val": 50, "test": 30, "embargo_dropped": 5},
        "universe": {"size": 50},
    }, ensure_ascii=False), encoding="utf-8")
    return run_dir


@pytest.fixture()
def prereg_path(tmp_path) -> Path:
    path = tmp_path / "prereg.json"
    path.write_text(json.dumps({
        "prereg_id": "KRONOS-V7-PREREG-TEST",
        "hypothesis": {"primary": "hypothesis text", "null": "null text", "negative_controls": ["shuffled-label control must NOT beat no-trade net of cost"]},
        "dataset": {"splits": {"val": "20240101-20250630"}},
    }, ensure_ascii=False), encoding="utf-8")
    return path


def test_report_renders_verdict_and_all_sections_offline(run_dir, prereg_path, tmp_path) -> None:
    summary = build_report(run_dir, prereg_path=prereg_path, index_artifact_dir=tmp_path / "no-index", now_utc="2026-07-20T01:00:00Z")
    html = (run_dir / "report.html").read_text(encoding="utf-8")

    assert summary["verdict"] == "INCONCLUSIVE"
    assert summary["test_state"] == "NOT_RUN"
    assert summary["index_overlay_state"] == "BLOCKED_INDEX_SERIES_SOURCE"
    assert ">INCONCLUSIVE<" in html
    assert "only one seed satisfies validation criterion" in html
    for section_id in range(1, 17):
        assert f'id="s{section_id}"' in html
    # no external resources and no scripts
    assert "http://" not in html and "https://" not in html
    assert "<script" not in html
    assert "src=" not in html and "url(" not in html
    # honesty tokens preserved
    assert "BLOCKED_INDEX_SERIES_SOURCE" in html
    assert "shuffled control seed 0" in html
    assert "면책" in html and "수익성" in html
    assert "NOT_RUN" in html


def test_report_manifest_hashes_match_written_files(run_dir, prereg_path, tmp_path) -> None:
    summary = build_report(run_dir, prereg_path=prereg_path, index_artifact_dir=tmp_path / "no-index", now_utc="2026-07-20T01:00:00Z")
    manifest = json.loads((run_dir / "report_manifest.json").read_text(encoding="utf-8"))

    assert manifest == summary
    assert manifest["schema_version"] == "kronos_v7_report.v1"
    report_sha = hashlib.sha256((run_dir / "report.html").read_bytes()).hexdigest()
    assert manifest["report_sha256"] == report_sha
    run_sha = hashlib.sha256((run_dir / "run_manifest.json").read_bytes()).hexdigest()
    assert manifest["source_sha256"]["run_manifest"] == run_sha
    # prereg file differs from manifest-recorded sha ("d"*64) → mismatch is reported, not hidden
    assert manifest["prereg_match"] == "MISMATCH_OR_MISSING"
    assert manifest["false_research_locks"] == _run_manifest()["false_research_locks"]

    # deterministic rebuild with same timestamp
    rebuilt = build_report(run_dir, prereg_path=prereg_path, index_artifact_dir=tmp_path / "no-index", now_utc="2026-07-20T01:00:00Z")
    assert rebuilt["report_sha256"] == report_sha


def test_report_includes_index_overlay_when_artifacts_valid(run_dir, prereg_path, tmp_path) -> None:
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    _write_index_artifacts(index_dir)

    summary = build_report(run_dir, prereg_path=prereg_path, index_artifact_dir=index_dir, now_utc="2026-07-20T01:00:00Z")
    html = (run_dir / "report.html").read_text(encoding="utf-8")

    assert summary["index_overlay_state"] == "PRESENT"
    assert "KOSPI (기준=100)" in html and "KOSDAQ (기준=100)" in html
    assert "결측일 비보간" in html
    assert "http://" not in html and "https://" not in html


def test_report_rejects_missing_manifest(tmp_path) -> None:
    with pytest.raises(ReportBuildError, match="run_manifest.json not found"):
        build_report(tmp_path)

def test_project_report_v2_validates_sidecar_and_preserves_run_contracts(tmp_path) -> None:
    prereg_a = tmp_path / "prereg_a.json"
    prereg_b = tmp_path / "prereg_b.json"
    prereg_a.write_text('{"hypothesis":"A"}', encoding="utf-8")
    prereg_b.write_text('{"hypothesis":"B"}', encoding="utf-8")
    sha_a = hashlib.sha256(prereg_a.read_bytes()).hexdigest()
    sha_b = hashlib.sha256(prereg_b.read_bytes()).hexdigest()

    def write_run(name: str, prereg_sha: str, verdict: str, capital: float = 60000000.0) -> None:
        run_dir = tmp_path / "dataset" / name
        run_dir.mkdir(parents=True)
        manifest = _run_manifest()
        manifest["prereg"]["sha256"] = prereg_sha
        manifest["verdict_candidate"]["value"] = verdict
        manifest["hyperparams"]["capital_krw"] = capital
        (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    write_run("cycle_1_a", sha_a, "NO_GO")
    write_run("cycle_1_b", sha_a, "INCONCLUSIVE")
    write_run("cycle_2_a", sha_b, "NOT_RUN", capital=61000000.0)
    sidecar = {
        "schema_version": "kronos_v7_project_report_sidecar.v2",
        "project_id": "KRONOS-PROJECT-TEST",
        "title": "Project report fixture",
        "cycles": [
            {"cycle_id": "C1", "order": 1, "title": "First", "hypothesis_delta": "Initial hypothesis",
             "prereg": {"path": "prereg_a.json", "sha256": sha_a},
             "run_dirs": ["dataset/cycle_1_a", "dataset/cycle_1_b"]},
            {"cycle_id": "C2", "order": 2, "title": "Second", "hypothesis_delta": "Changed feature",
             "prereg": {"path": "prereg_b.json", "sha256": sha_b},
             "run_dirs": ["dataset/cycle_2_a"]},
        ],
    }
    sidecar_path = tmp_path / "project_sidecar.json"
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    output_dir = tmp_path / "export"
    summary = build_project_report(sidecar_path, output_dir, now_utc="2026-07-20T01:00:00Z")
    report = (output_dir / "project_report.html").read_text(encoding="utf-8")

    assert summary["project_id"] == "KRONOS-PROJECT-TEST"
    assert len(summary["source_sha256"]) == 6
    assert summary["false_research_locks"] == _run_manifest()["false_research_locks"]
    assert report.index("C1") < report.index("C2")
    for tab in ("Summary", "Cycles", "Comparison", "Traceability", "Integrity"):
        assert f">{tab}<" in report
    for verdict in ("NO_GO", "INCONCLUSIVE", "NOT_RUN"):
        assert verdict in report
    assert "OOS remains closed" in report
    assert "COMPATIBLE" in report and "INCOMPATIBLE" in report
    assert "<script" not in report and " on" not in report
    assert "http://" not in report and "https://" not in report and "src=" not in report and "url(" not in report
    assert build_project_report(sidecar_path, output_dir, now_utc="2026-07-20T01:00:00Z")["report_sha256"] == summary["report_sha256"]

    sidecar["cycles"][1]["order"] = 1
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    with pytest.raises(ReportBuildError, match="unique"):
        build_project_report(sidecar_path, output_dir, now_utc="2026-07-20T01:00:00Z")
    sidecar["cycles"][1]["order"] = 2
    sidecar["cycles"][0]["prereg"]["sha256"] = "0" * 64
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    with pytest.raises(ReportBuildError, match="SHA-256 mismatch"):
        build_project_report(sidecar_path, output_dir, now_utc="2026-07-20T01:00:00Z")
