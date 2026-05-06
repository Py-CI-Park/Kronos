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
        "0,000001,20260102,2026-01-02T09:00:03,2026-01-02T09:00:04,1,100,101,-1,1,0.5,0.6,1\n"
        "0,000001,20260102,2026-01-02T09:00:03,2026-01-02T09:00:05,2,102,103,-1,1,0.5,0.6,1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(stom_dashboard, "PREDICTION_DIRS", [pred_dir])

    files = stom_dashboard.list_prediction_files()
    df = stom_dashboard.load_prediction_frame("sample.csv")
    metrics = stom_dashboard.prediction_metrics(df)
    chart = json.loads(stom_dashboard.prediction_chart_json(df))
    topk = stom_dashboard.topk_rows(df)

    assert files[0]["name"] == "sample.csv"
    assert df["symbol"].iloc[0] == "000001"
    assert metrics["rows"] == 2
    assert metrics["windows"] == 1
    assert chart["data"][0]["name"] == "실제 close"
    assert topk[0]["symbol"] == "000001"


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
        "0,000001,20260102,2026-01-02T09:00:03,2026-01-02T09:00:04,1,100,101,-1,1,0.5,0.6,1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(stom_dashboard, "PREDICTION_DIRS", [pred_dir])

    import app

    monkeypatch.setattr(app, "list_prediction_files", stom_dashboard.list_prediction_files)
    monkeypatch.setattr(app, "load_prediction_frame", stom_dashboard.load_prediction_frame)
    monkeypatch.setattr(app, "prediction_metrics", stom_dashboard.prediction_metrics)
    monkeypatch.setattr(app, "prediction_chart_json", stom_dashboard.prediction_chart_json)
    monkeypatch.setattr(app, "topk_rows", stom_dashboard.topk_rows)

    client = app.app.test_client()
    assert client.get("/stom").status_code == 200
    assert client.get("/api/stom/prediction-files").status_code == 200
    assert client.get("/api/stom/prediction?file=sample.csv").status_code == 200


def test_flask_stom_routes_work_when_imported_as_package():
    from webui.app import app as flask_app

    client = flask_app.test_client()
    assert client.get("/api/stom/prediction-files").status_code == 200
