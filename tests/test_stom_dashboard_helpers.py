import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "webui"))

import stom_dashboard  # noqa: E402


def test_dashboard_prediction_helpers_load_metrics_and_chart(tmp_path, monkeypatch):
    pred_dir = tmp_path / "preds"
    pred_dir.mkdir()
    pred_file = pred_dir / "sample.csv"
    pred_file.write_text(
        "window_id,symbol,session,asof_timestamp,target_timestamp,horizon_step,pred_close,actual_close,error,abs_error,pred_return_window,actual_return_window,direction_hit_window\n"
        "0,000001,20260102,2026-01-02T09:00:03,2026-01-02T09:00:04,1,103,101,2,2,2.0,0.6,1\n"
        "0,000001,20260102,2026-01-02T09:00:03,2026-01-02T09:00:05,2,104,103,1,1,2.0,0.6,1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(stom_dashboard, "PREDICTION_DIRS", [pred_dir])

    files = stom_dashboard.list_prediction_files()
    df = stom_dashboard.load_prediction_frame("sample.csv")
    metrics = stom_dashboard.prediction_metrics(df)
    chart = json.loads(stom_dashboard.prediction_chart_json(df))
    topk = stom_dashboard.topk_rows(df)
    recommendations = stom_dashboard.ranked_recommendations(df)
    recommendation_summary = stom_dashboard.recommendation_summary(recommendations)
    backtest_report = stom_dashboard.score_backtest_report(df)
    export_payload = stom_dashboard.recommendation_export_payload(df, source_file="sample.csv")
    export_csv = stom_dashboard.recommendation_export_csv(export_payload["records"])

    assert files[0]["name"] == "sample.csv"
    assert df["symbol"].iloc[0] == "000001"
    assert metrics["rows"] == 2
    assert metrics["windows"] == 1
    assert chart["data"][0]["name"] == "실제 close"
    assert topk[0]["symbol"] == "000001"
    assert recommendations[0]["symbol"] == "000001"
    assert 0 <= recommendations[0]["kronos_score"] <= 100
    assert recommendation_summary["count"] == 1
    assert backtest_report["window_count"] == 1
    assert backtest_report["filters"][0]["label"] == "all_scored"
    assert export_payload["metadata"]["adapter_version"] == "stom-kronos-score-v1"
    assert export_payload["records"][0]["adapter_action"] == "BUY"
    assert export_csv.splitlines()[0].startswith("rank,source_file,window_id,symbol")


def test_ranked_recommendations_prefers_positive_consistent_prediction():
    df = stom_dashboard.pd.DataFrame(
        [
            {
                "window_id": 0,
                "symbol": "000001",
                "session": "20260102",
                "asof_timestamp": "2026-01-02T09:00:03",
                "target_timestamp": "2026-01-02T09:00:04",
                "actual_close_t0": 100,
                "pred_close": 102,
                "actual_close": 101,
                "abs_error": 1,
                "pred_return_window": 2.0,
                "actual_return_window": 1.0,
                "direction_hit_window": 1,
            },
            {
                "window_id": 1,
                "symbol": "000002",
                "session": "20260102",
                "asof_timestamp": "2026-01-02T09:00:03",
                "target_timestamp": "2026-01-02T09:00:04",
                "actual_close_t0": 100,
                "pred_close": 98,
                "actual_close": 101,
                "abs_error": 3,
                "pred_return_window": -2.0,
                "actual_return_window": 1.0,
                "direction_hit_window": 0,
            },
        ]
    )
    df["target_timestamp"] = stom_dashboard.pd.to_datetime(df["target_timestamp"])

    recommendations = stom_dashboard.ranked_recommendations(df, k=2)
    report = stom_dashboard.score_backtest_report(df)

    assert [row["symbol"] for row in recommendations] == ["000001", "000002"]
    assert recommendations[0]["signal"] == "BUY_CANDIDATE"
    assert recommendations[0]["kronos_score"] > recommendations[1]["kronos_score"]
    assert report["filters"][1]["label"] == "buy_candidate_score60"
    assert report["segments"]["score_band"][0]["count"] >= 1


def test_recommendation_export_filters_and_rejects_unknown_filter():
    df = stom_dashboard.pd.DataFrame(
        [
            {
                "window_id": 0,
                "symbol": "000001",
                "session": "20260102",
                "asof_timestamp": "2026-01-02T09:00:03",
                "target_timestamp": "2026-01-02T09:00:04",
                "actual_close_t0": 100,
                "pred_close": 102,
                "actual_close": 101,
                "abs_error": 1,
                "pred_return_window": 2.0,
                "actual_return_window": 1.0,
                "direction_hit_window": 1,
            },
            {
                "window_id": 1,
                "symbol": "000002",
                "session": "20260102",
                "asof_timestamp": "2026-01-02T09:00:03",
                "target_timestamp": "2026-01-02T09:00:04",
                "actual_close_t0": 100,
                "pred_close": 98,
                "actual_close": 101,
                "abs_error": 3,
                "pred_return_window": -2.0,
                "actual_return_window": 1.0,
                "direction_hit_window": 0,
            },
        ]
    )
    df["target_timestamp"] = stom_dashboard.pd.to_datetime(df["target_timestamp"])

    payload = stom_dashboard.recommendation_export_payload(
        df,
        source_file="sample.csv",
        selected_filter="buy_candidate_score60",
        limit=10,
    )

    assert payload["metadata"]["record_count"] == 1
    assert payload["records"][0]["symbol"] == "000001"
    assert "diagnostic_actual_return_pct" in payload["records"][0]
    try:
        stom_dashboard.recommendation_export_payload(df, selected_filter="unknown_filter")
    except ValueError as exc:
        assert "Unknown score filter" in str(exc)
    else:
        raise AssertionError("Expected unknown export filter to be rejected")


def test_score_backtest_report_tolerates_unknown_asof_timestamp():
    df = stom_dashboard.pd.DataFrame(
        [
            {
                "window_id": 0,
                "symbol": "000001",
                "session": "20260102",
                "asof_timestamp": "not-a-time",
                "target_timestamp": "2026-01-02T09:00:04",
                "actual_close_t0": 100,
                "pred_close": 102,
                "actual_close": 101,
                "abs_error": 1,
                "pred_return_window": 2.0,
                "actual_return_window": 1.0,
                "direction_hit_window": 1,
            }
        ]
    )
    df["target_timestamp"] = stom_dashboard.pd.to_datetime(df["target_timestamp"])

    report = stom_dashboard.score_backtest_report(df)

    assert report["segments"]["asof_minute_bucket"][0]["label"] == "unknown"
    early_filter = next(row for row in report["filters"] if row["label"] == "early_session_score60")
    assert early_filter["count"] == 0


def test_dashboard_rejects_path_traversal(tmp_path, monkeypatch):
    pred_dir = tmp_path / "preds"
    pred_dir.mkdir()
    monkeypatch.setattr(stom_dashboard, "PREDICTION_DIRS", [pred_dir])

    try:
        stom_dashboard.load_prediction_frame("../secret.csv")
    except ValueError as exc:
        assert "Invalid file path" in str(exc)
    else:
        raise AssertionError("Expected path traversal to be rejected")


def test_flask_stom_routes_smoke(tmp_path, monkeypatch):
    pred_dir = tmp_path / "preds"
    pred_dir.mkdir()
    pred_file = pred_dir / "sample.csv"
    pred_file.write_text(
        "window_id,symbol,session,asof_timestamp,target_timestamp,horizon_step,pred_close,actual_close,error,abs_error,pred_return_window,actual_return_window,direction_hit_window\n"
        "0,000001,20260102,2026-01-02T09:00:03,2026-01-02T09:00:04,1,103,101,2,2,2.0,0.6,1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(stom_dashboard, "PREDICTION_DIRS", [pred_dir])

    import app

    monkeypatch.setattr(app, "list_prediction_files", stom_dashboard.list_prediction_files)
    monkeypatch.setattr(app, "load_prediction_frame", stom_dashboard.load_prediction_frame)
    monkeypatch.setattr(app, "prediction_metrics", stom_dashboard.prediction_metrics)
    monkeypatch.setattr(app, "prediction_chart_json", stom_dashboard.prediction_chart_json)
    monkeypatch.setattr(app, "topk_rows", stom_dashboard.topk_rows)
    monkeypatch.setattr(app, "ranked_recommendations", stom_dashboard.ranked_recommendations)
    monkeypatch.setattr(app, "recommendation_summary", stom_dashboard.recommendation_summary)
    monkeypatch.setattr(app, "score_backtest_report", stom_dashboard.score_backtest_report)
    monkeypatch.setattr(app, "recommendation_export_payload", stom_dashboard.recommendation_export_payload)
    monkeypatch.setattr(app, "recommendation_export_csv", stom_dashboard.recommendation_export_csv)

    client = app.app.test_client()
    page = client.get("/stom")
    assert page.status_code == 200
    assert "STOM/Future_Trading Adapter Export" in page.get_data(as_text=True)
    assert client.get("/api/stom/prediction-files").status_code == 200
    assert client.get("/api/stom/prediction?file=sample.csv").status_code == 200
    rec = client.get("/api/stom/recommendations?file=sample.csv")
    assert rec.status_code == 200
    assert rec.get_json()["summary"]["count"] == 1
    report = client.get("/api/stom/backtest-report?file=sample.csv")
    assert report.status_code == 200
    assert report.get_json()["filters"][0]["count"] == 1
    export_json = client.get("/api/stom/recommendation-export?file=sample.csv&format=json")
    assert export_json.status_code == 200
    assert export_json.get_json()["metadata"]["record_count"] == 1
    export_csv = client.get("/api/stom/recommendation-export?file=sample.csv&format=csv")
    assert export_csv.status_code == 200
    assert export_csv.mimetype == "text/csv"
    assert export_csv.get_data(as_text=True).splitlines()[0].startswith("rank,source_file")


def test_flask_stom_routes_work_when_imported_as_package():
    from webui.app import app as flask_app

    client = flask_app.test_client()
    assert client.get("/api/stom/prediction-files").status_code == 200
