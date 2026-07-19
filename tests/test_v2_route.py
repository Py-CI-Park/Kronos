"""Verify official dashboard canonical routes and legacy redirects."""
from contextlib import closing
from urllib.parse import urlparse

from pathlib import Path
from webui.app import app


OFFICIAL_SHELL_MARKER = "kronos-dashboard-shell"
LEGACY_PUBLIC_MARKERS = (
    "kronos-v2-version",
    "p1-ssr",
    "p1-5-spa",
)

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


def test_root_returns_official_dashboard_shell():
    with app.test_client() as client:
        with closing(client.get("/")) as resp:
            assert resp.status_code == 200
            _assert_official_shell(resp.data.decode("utf-8"))


def test_training_bookmarks_return_official_shell():
    with app.test_client() as client:
        for path in ("/training", "/dashboard"):
            with closing(client.get(path)) as resp:
                assert resp.status_code == 200, f"{path} broke"
                _assert_official_shell(resp.data.decode("utf-8"))


def test_rl_bookmark_redirects_to_svelte_rl_tab():
    # Consolidation A: the RL command center is now the Svelte RLTradingTab.
    # The Next.js export is retired, so /rl canonicalizes to /?tab=rl.
    with app.test_client() as client:
        with closing(client.get("/rl", follow_redirects=False)) as resp:
            assert resp.status_code == 301
            assert _location_path_and_query(resp.headers.get("Location")) == "/?tab=rl"


def test_daily_trading_bookmarks_redirect_to_rl_sections():
    with app.test_client() as client:
        # Consolidation B1: daily-ohlcv/daily bookmarks now resolve to the single
        # Svelte Daily OHLCV tab. The RL-guide bookmarks still point at the Next.js
        # command-center workflow section (RL surface consolidation is a later phase).
        expected = {
            "/daily-ohlcv": "/?tab=daily-ohlcv",
            "/daily": "/?tab=daily-ohlcv",
            "/daily-rl-guide": "/?tab=daily-rl-guide",
            "/daily-ohlcv/rl-guide": "/?tab=daily-rl-guide",
        }
        for path, target in expected.items():
            with closing(client.get(path, follow_redirects=False)) as resp:
                assert resp.status_code == 301, f"{path} should redirect"
                assert _location_path_and_query(resp.headers.get("Location")) == target


def test_legacy_v2_routes_redirect_to_canonical_routes():
    with app.test_client() as client:
        main_routes = ("/v2", "/v2/")
        for path in main_routes:
            with closing(client.get(path, follow_redirects=False)) as resp:
                assert resp.status_code == 301, f"{path} should redirect"
                assert _location_path(resp.headers.get("Location")) == "/"

        section_routes = {
            "/rl-lab": "/?tab=rl",
            "/v2/rl-lab": "/?tab=rl",
            "/v2/rl-trading": "/?tab=rl",
        }
        for path, target in section_routes.items():
            with closing(client.get(path, follow_redirects=False)) as resp:
                assert resp.status_code == 301, f"{path} should redirect"
                assert _location_path_and_query(resp.headers.get("Location")) == target


def test_unknown_v2_subpath_redirects_to_root_without_catchall():
    with app.test_client() as client:
        with closing(client.get("/v2/unknown", follow_redirects=False)) as resp:
            assert resp.status_code == 301
            assert _location_path(resp.headers.get("Location")) == "/"
