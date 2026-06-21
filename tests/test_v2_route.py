"""Verify official dashboard canonical routes and legacy redirects."""
from urllib.parse import urlparse

from pathlib import Path
from webui.app import app


OFFICIAL_SHELL_MARKER = "kronos-dashboard-shell"
LEGACY_PUBLIC_MARKERS = (
    "kronos-v2-version",
    "p1-ssr",
    "p1-5-spa",
)

TRADING_OUT_INDEX = Path(__file__).resolve().parents[1] / "webui" / "trading_src" / "out" / "index.html"
TRADING_SHELL_MARKER = "data-kronos-trading-command-center"


def _location_path(location: str | None) -> str:
    assert location is not None
    parsed = urlparse(location)
    return parsed.path or "/"


def _location_path_and_query(location: str | None) -> str:
    assert location is not None
    parsed = urlparse(location)
    path = parsed.path or "/"
    return f"{path}?{parsed.query}" if parsed.query else path


def _assert_official_shell(body: str) -> None:
    assert OFFICIAL_SHELL_MARKER in body
    for marker in LEGACY_PUBLIC_MARKERS:
        assert marker not in body


def _assert_trading_shell(body: str) -> None:
    assert TRADING_OUT_INDEX.exists(), "Trading command center export must exist before /rl can pass"
    assert TRADING_SHELL_MARKER in body
    assert "NO-GO" in body
    assert "RESEARCH_ONLY" in body
    assert "ts_imb RULE baseline" in body
    assert "강화학습 연구 커맨드 센터" in body
    assert "모델/실험 선택" in body
    assert "API 미연결(안전 잠금)" in body
    assert "차트형 증거 상태" in body
    assert "실거래 없음" in body
    assert "실거래 꺼짐" in body


def test_root_returns_official_dashboard_shell():
    client = app.test_client()

    resp = client.get("/")

    assert resp.status_code == 200
    _assert_official_shell(resp.data.decode("utf-8"))


def test_training_bookmarks_return_official_shell():
    client = app.test_client()

    for path in ("/training", "/dashboard"):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} broke"
        _assert_official_shell(resp.data.decode("utf-8"))


def test_rl_canonical_route_returns_trading_command_center_when_built():
    client = app.test_client()

    resp = client.get("/rl")

    assert resp.status_code == 200
    _assert_trading_shell(resp.data.decode("utf-8"))


def test_daily_trading_bookmarks_redirect_to_rl_sections():
    client = app.test_client()

    expected = {
        "/daily-ohlcv": "/rl?section=daily-gates",
        "/daily": "/rl?section=daily-gates",
        "/daily-rl-guide": "/rl?section=workflow",
        "/daily-ohlcv/rl-guide": "/rl?section=workflow",
    }
    for path, target in expected.items():
        resp = client.get(path, follow_redirects=False)
        assert resp.status_code == 301, f"{path} should redirect"
        assert _location_path_and_query(resp.headers.get("Location")) == target


def test_legacy_v2_routes_redirect_to_canonical_routes():
    client = app.test_client()

    main_routes = ("/v2", "/v2/")
    for path in main_routes:
        resp = client.get(path, follow_redirects=False)
        assert resp.status_code == 301, f"{path} should redirect"
        assert _location_path(resp.headers.get("Location")) == "/"

    section_routes = {
        "/rl-lab": "/rl?section=evidence",
        "/v2/rl-lab": "/rl?section=evidence",
        "/v2/rl-trading": "/rl",
    }
    for path, target in section_routes.items():
        resp = client.get(path, follow_redirects=False)
        assert resp.status_code == 301, f"{path} should redirect"
        assert _location_path_and_query(resp.headers.get("Location")) == target


def test_unknown_v2_subpath_redirects_to_root_without_catchall():
    client = app.test_client()

    resp = client.get("/v2/unknown", follow_redirects=False)

    assert resp.status_code == 301
    assert _location_path(resp.headers.get("Location")) == "/"
