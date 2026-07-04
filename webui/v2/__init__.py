from __future__ import annotations

import os
from typing import Final

from flask import Blueprint, current_app, redirect, render_template, send_from_directory

v2_bp = Blueprint("v2", __name__)

_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSY: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})


def _env_flag_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUTHY


def _official_ssr_fallback_requested() -> bool:
    mode = os.environ.get("KRONOS_DASHBOARD_MODE", "").strip().lower()
    if mode == "ssr":
        return True
    if _env_flag_enabled("KRONOS_DASHBOARD_SSR_FALLBACK"):
        return True

    # Backward compatibility only. The official default is the built dashboard
    # when dist exists; this old flag is retained only as an undocumented escape.
    legacy_dist = os.environ.get("KRONOS_V2_DIST", "").strip().lower()
    return legacy_dist in _FALSY


def _serve_dashboard_shell():
    """Serve the official Kronos dashboard shell."""
    dist_dir = os.path.join(current_app.static_folder or "", "v2", "dist")
    dist_index = os.path.join(dist_dir, "index.html")
    if os.path.exists(dist_index) and not _official_ssr_fallback_requested():
        return send_from_directory(dist_dir, "index.html")
    return render_template("v2_shell.html")

@v2_bp.route("/")
def dashboard_root():
    """Serve the official dashboard entry point."""
    return _serve_dashboard_shell()


@v2_bp.route("/training")
@v2_bp.route("/dashboard")
def dashboard_training_alias():
    """Serve the official dashboard for operator training bookmarks."""
    return _serve_dashboard_shell()


@v2_bp.route("/rl")
def dashboard_rl():
    """Redirect the RL command-center bookmark to the Svelte RL tab.

    Consolidation A: the RL trading/evidence surface now lives in the official
    Svelte dashboard (RLTradingTab). The Next.js command center is retired, so
    /rl canonicalizes to the single Svelte app.
    """
    return redirect("/?tab=rl", code=301)


@v2_bp.route("/daily-ohlcv")
@v2_bp.route("/daily")
def dashboard_daily_gates_redirect():
    """Redirect daily research bookmarks to the official Svelte Daily OHLCV tab.

    Consolidation B1: the daily research surface now lives in the Svelte
    dashboard (summary-first Daily OHLCV tab) instead of the Next.js command
    center, so both bookmarks resolve to a single daily view.
    """
    return redirect("/?tab=daily-ohlcv", code=301)


@v2_bp.route("/daily-rl-guide")
@v2_bp.route("/daily-ohlcv/rl-guide")
def dashboard_daily_workflow_redirect():
    """Redirect daily RL guide bookmarks to the Svelte daily RL guide tab."""
    return redirect("/?tab=daily-rl-guide", code=301)


@v2_bp.route("/rl-lab")
@v2_bp.route("/v2/rl-lab")
def dashboard_rl_evidence_redirect():
    """Redirect legacy RL lab bookmarks to the Svelte RL tab."""
    return redirect("/?tab=rl", code=301)


@v2_bp.route("/v2/rl-trading")
def dashboard_rl_trading_redirect():
    """Redirect legacy RL trading bookmarks to the Svelte RL tab."""
    return redirect("/?tab=rl", code=301)


@v2_bp.route("/v2")
@v2_bp.route("/v2/")
def dashboard_legacy_redirect():
    """Redirect legacy dashboard bookmarks to the canonical route."""
    return redirect("/", code=301)


@v2_bp.route("/v2/<path:subpath>")
def dashboard_legacy_subpath_redirect(subpath: str):
    """Redirect legacy versioned subpaths without adding a global catch-all."""
    return redirect("/", code=301)
