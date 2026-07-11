import importlib
from pathlib import Path

import pandas as pd


webui_app = importlib.import_module("webui.app")


def _frame():
    return pd.DataFrame({
        "timestamps": pd.date_range("2024-01-01", periods=2, freq="h"),
        "open": [1.0, 2.0],
        "high": [2.0, 3.0],
        "low": [0.5, 1.5],
        "close": [1.5, 2.5],
    })


def test_cors_only_allows_loopback_origins():
    client = webui_app.app.test_client()

    denied = client.get("/api/data-files", headers={"Origin": "https://example.com"})
    allowed = client.get("/api/data-files", headers={"Origin": "http://localhost:7070"})

    assert "Access-Control-Allow-Origin" not in denied.headers
    assert allowed.headers["Access-Control-Allow-Origin"] == "http://localhost:7070"
    assert "Access-Control-Allow-Credentials" not in allowed.headers


def test_load_data_rejects_outside_path(tmp_path, monkeypatch):
    root = tmp_path / "allowed"
    root.mkdir()
    outside = tmp_path / "outside.csv"
    outside.write_text("ignored", encoding="utf-8")
    monkeypatch.setenv("KRONOS_WEBUI_DATA_ROOTS", str(root))
    monkeypatch.setattr(webui_app, "load_data_file", lambda _: (_ for _ in ()).throw(AssertionError("must not load")))

    response = webui_app.app.test_client().post("/api/load-data", json={"file_path": str(outside)})

    assert response.status_code == 400


def test_load_data_rejects_resolved_symlink_escape_without_os_privileges(tmp_path, monkeypatch):
    root = tmp_path / "allowed"
    root.mkdir()
    outside = tmp_path / "outside.csv"
    outside.write_text("ignored", encoding="utf-8")
    escape = root / "escape.csv"
    escape.write_text("lexically inside, resolves outside", encoding="utf-8")
    resolved_outside = outside.resolve()
    original_resolve = Path.resolve

    def resolve_escape(path, *args, **kwargs):
        if path == escape:
            return resolved_outside
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setenv("KRONOS_WEBUI_DATA_ROOTS", str(root))
    monkeypatch.setattr(Path, "resolve", resolve_escape)
    monkeypatch.setattr(webui_app, "load_data_file", lambda _: (_ for _ in ()).throw(AssertionError("must not load")))

    response = webui_app.app.test_client().post("/api/load-data", json={"file_path": str(escape)})

    assert response.status_code == 400


def test_load_data_accepts_csv_under_configured_root(tmp_path, monkeypatch):
    root = tmp_path / "allowed"
    root.mkdir()
    data_file = root / "prices.csv"
    data_file.write_text("ignored", encoding="utf-8")
    monkeypatch.setenv("KRONOS_WEBUI_DATA_ROOTS", str(root))
    loaded = []

    def fake_load(path):
        loaded.append(path)
        return _frame(), None

    monkeypatch.setattr(webui_app, "load_data_file", fake_load)
    response = webui_app.app.test_client().post("/api/load-data", json={"file_path": str(data_file)})

    assert response.status_code == 200
    assert loaded == [str(data_file.resolve())]


def test_predict_rejects_invalid_bounds_before_data_load(tmp_path, monkeypatch):
    root = tmp_path / "allowed"
    root.mkdir()
    data_file = root / "prices.csv"
    data_file.write_text("ignored", encoding="utf-8")
    monkeypatch.setenv("KRONOS_WEBUI_DATA_ROOTS", str(root))
    monkeypatch.setattr(webui_app, "load_data_file", lambda _: (_ for _ in ()).throw(AssertionError("must not load")))
    client = webui_app.app.test_client()

    for params in (
        {"lookback": 4097},
        {"pred_len": 1025},
        {"sample_count": 17},
        {"pred_len": 0},
        {"sample_count": "1"},
    ):
        response = client.post("/api/predict", json={"file_path": str(data_file), **params})
        assert response.status_code == 400


def test_predict_accepts_exact_resource_caps(tmp_path, monkeypatch):
    root = tmp_path / "allowed"
    root.mkdir()
    data_file = root / "prices.csv"
    data_file.write_text("ignored", encoding="utf-8")
    monkeypatch.setenv("KRONOS_WEBUI_DATA_ROOTS", str(root))
    loaded = []

    def stop_after_bounds(path):
        loaded.append(path)
        return None, "bounded-test-stop"

    monkeypatch.setattr(webui_app, "load_data_file", stop_after_bounds)
    response = webui_app.app.test_client().post(
        "/api/predict",
        json={"file_path": str(data_file), "lookback": 4096, "pred_len": 1024, "sample_count": 16},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "bounded-test-stop"
    assert loaded == [str(data_file.resolve())]


def test_load_model_rejects_overrides_and_invalid_devices_before_import(monkeypatch):
    monkeypatch.setattr(webui_app, "ensure_kronos_imported", lambda: (_ for _ in ()).throw(AssertionError("must not import")))
    client = webui_app.app.test_client()

    for payload in ({"model_path": "/tmp/model"}, {"modelId": "remote/model"}, {"device": "cuda:bad"}):
        response = client.post("/api/load-model", json=payload)
        assert response.status_code == 400


def test_debug_default_remains_off_in_both_entrypoints():
    app_source = Path(webui_app.__file__).read_text(encoding="utf-8")
    run_source = Path(webui_app.__file__).with_name("run.py").read_text(encoding="utf-8")

    for source in (app_source, run_source):
        assert 'os.environ.get("KRONOS_WEBUI_DEBUG", "0")' in source
        assert "app.run(debug=debug_mode" in source
