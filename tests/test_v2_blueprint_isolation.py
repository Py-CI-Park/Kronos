"""Verify official dashboard cutover preserves legacy archive and API routes."""
from contextlib import closing
from urllib.parse import urlparse

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


def _assert_official_shell(body: str) -> None:
    assert OFFICIAL_SHELL_MARKER in body
    for marker in LEGACY_PUBLIC_MARKERS:
        assert marker not in body


def test_root_serves_official_dashboard_after_cutover():
    with app.test_client() as client:
        with closing(client.get("/")) as resp:
            assert resp.status_code == 200, "/ broke after cutover"
            _assert_official_shell(resp.data.decode("utf-8"))


def test_training_bookmarks_serve_official_dashboard_shell():
    with app.test_client() as client:
        for path in ("/training", "/dashboard"):
            with closing(client.get(path)) as resp:
                assert resp.status_code == 200, f"{path} broke"
                _assert_official_shell(resp.data.decode("utf-8"))


def test_v1_legacy_routes_still_available():
    with app.test_client() as client:
        for path in ("/v1/", "/v1/training", "/v1/stom"):
            with closing(client.get(path)) as resp:
                assert resp.status_code == 200, f"{path} broke"


def test_versioned_dashboard_urls_redirect_to_canonical_routes():
    with app.test_client() as client:
        for path in ("/v2", "/v2/"):
            with closing(client.get(path, follow_redirects=False)) as resp:
                assert resp.status_code == 301
                assert _location_path(resp.headers.get("Location")) == "/"

        # Consolidation A: legacy RL bookmarks canonicalize to the Svelte RL tab.
        for path in ("/rl-lab", "/v2/rl-trading", "/v2/rl-lab"):
            with closing(client.get(path, follow_redirects=False)) as resp:
                assert resp.status_code == 301
                parsed = urlparse(resp.headers.get("Location"))
                assert f"{parsed.path or '/'}?{parsed.query}" == "/?tab=rl"


def test_api_routes_unchanged():
    with app.test_client() as client:
        for path in (
            "/api/training/status",
            "/api/training/history",
            "/api/training/artifacts",
            "/api/training/gpu",
            "/api/training/system",
            "/api/training/runs",
            "/api/rl/runs",
        ):
            with closing(client.get(path)) as resp:
                assert resp.status_code == 200, f"{path} broke"


def test_no_global_catchall():
    rules = [str(rule) for rule in app.url_map.iter_rules()]

    assert "/<path:subpath>" not in rules
    assert not any(rule == "/<path:p>" for rule in rules)
