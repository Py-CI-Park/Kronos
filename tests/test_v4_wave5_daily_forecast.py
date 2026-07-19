"""Source-contract tests for V4 Wave-5 daily/forecast workspaces."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "webui" / "v2_src" / "src"

_EXPECTED_TABS = [
    "mission-control",
    "live-training",
    "forecast",
    "stom",
    "rl",
    "daily-ohlcv",
    "daily-rl-guide",
    "artifacts",
    "history",
    "system-health",
    "settings",
    "docs",
]
_LOCK_KEYS = [
    "promotion_allowed",
    "model_build_allowed",
    "paper_forward_allowed",
    "live_broker_order_allowed",
    "profitability_claim_allowed",
    "go_summary_allowed",
]
_FROZEN_ROUTE_IDS = [
    "mission-control",
    "live-training",
    "forecast",
    "stom",
    "daily-ohlcv",
    "daily-rl-guide",
    "rl",
    "artifacts",
    "history",
    "system-health",
    "settings",
    "docs",
]
# V5 intentionally owns the shell, Flask route registration, and generated-client
# dependencies. Keep the historical V4 freeze on untouched V4 authorities.
_FROZEN_BOUNDARY_SHA256 = {
    "webui/rl_dashboard_tables.py": "b3cebec1bc4f698435f8fa42277a6de5aa495e07c1fd5c5f14dfc605ba8a60b6",
    "stom_rl/rl_events.py": "4764308da956babcbc3b9c385aff59a52f27dc41816971a1c9be08f0a740a701",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")
def _normalized_sha256(path: Path) -> str:
    payload = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(payload).hexdigest()


def _source(relative: str) -> str:
    return _read(_SRC / relative)


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def _tab_branch(source: str, tab_id: str) -> str:
    marker = f"tab === '{tab_id}'"
    start = source.index(marker)
    next_branch = source.find("{:else if tab ===", start + len(marker))
    end = next_branch if next_branch != -1 else source.index("{/if}", start)
    return source[start:end]


def _product_sources(*relative_roots: str) -> dict[str, str]:
    sources: dict[str, str] = {}
    for relative_root in relative_roots:
        root = _SRC / relative_root
        candidates = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in candidates:
            if path.suffix not in {".svelte", ".ts"}:
                continue
            if path.name.endswith(".test.ts"):
                continue
            sources[path.relative_to(_REPO_ROOT).as_posix()] = _read(path)
    return sources


def _assert_in_order(source: str, needles: list[str]) -> None:
    cursor = -1
    for needle in needles:
        position = source.find(needle, cursor + 1)
        assert position > cursor, f"{needle!r} missing or out of order"
        cursor = position


def test_app_keeps_single_twelve_branch_host_and_v3_v4_coexistence() -> None:
    app = _source("App.svelte")
    tab_host = _between(app, "{#snippet tabHost()}", "{/snippet}")

    assert "import V4ForecastStudio from '$lib/../v4/forecast/V4ForecastStudio.svelte';" in app
    assert "import V4DailyResearch from '$lib/../v4/daily/V4DailyResearch.svelte';" in app
    assert app.count("{#snippet tabHost()}") == 1
    assert app.count("{@render tabHost()}") == 2

    branches = re.findall(r"tab === '([^']+)'", tab_host)
    assert branches == _EXPECTED_TABS
    assert len(branches) == len(set(branches)) == 12
    assert "data-v3-tab-host={shell === 'v3' ? '' : undefined}" in tab_host
    assert "data-v4-domain-host={shell === 'v4' ? '' : undefined}" in tab_host


def test_app_wraps_only_forecast_and_daily_legacy_tabs_for_v4() -> None:
    app = _source("App.svelte")
    tab_host = _between(app, "{#snippet tabHost()}", "{/snippet}")
    forecast_branch = _tab_branch(tab_host, "forecast")
    daily_branch = _tab_branch(tab_host, "daily-ohlcv")

    _assert_in_order(
        forecast_branch,
        [
            "{#if shell === 'v4'}",
            "<V4ForecastStudio>",
            "<ForecastWorkbenchTab />",
            "</V4ForecastStudio>",
            "{:else}",
            "<ForecastWorkbenchTab />",
        ],
    )
    _assert_in_order(
        daily_branch,
        [
            "{#if shell === 'v4'}",
            "<V4DailyResearch>",
            "<DailyOhlcvTab />",
            "</V4DailyResearch>",
            "{:else}",
            "<DailyOhlcvTab />",
        ],
    )
    assert tab_host.count("<V4ForecastStudio>") == tab_host.count("</V4ForecastStudio>") == 1
    assert tab_host.count("<V4DailyResearch>") == tab_host.count("</V4DailyResearch>") == 1

    for tab_id in set(_EXPECTED_TABS) - {"forecast", "daily-ohlcv"}:
        branch = _tab_branch(tab_host, tab_id)
        assert "V4ForecastStudio" not in branch
        assert "V4DailyResearch" not in branch


def test_v4_forecast_contract_markers_lazy_child_and_payload_validation() -> None:
    sources = _product_sources("v4/forecast", "tabs/ForecastWorkbenchTab.svelte")
    combined = "\n".join(sources.values())
    studio = sources.get("webui/v2_src/src/v4/forecast/V4ForecastStudio.svelte", "")
    tab = sources["webui/v2_src/src/tabs/ForecastWorkbenchTab.svelte"]

    assert studio, "V4ForecastStudio source must exist at the agreed path"
    assert "data-v4-forecast-studio" in studio
    assert "children?: Snippet" in studio
    assert "Raw provenance/results · repaired Forecast workbench" in studio
    assert "data-v4-raw-audit" in studio
    assert studio.rfind("{@render children()}") > studio.index("data-v4-raw-audit")
    assert "<slot" not in studio

    for bound in ["4096", "1024", "16", "0.1", "topP"]:
        assert bound in sources["webui/v2_src/src/v4/forecast/forecastEvidence.ts"]
    assert "file_path" in combined
    assert "sample_count" in combined
    assert re.search(r"\bn_samples\s*:", combined) is None

    _assert_in_order(tab, ["buildForecastPredictPayload", "if (validation.ok === false)", "fetch('/api/predict'"])
    predict_body = _between(tab, "fetch('/api/predict'", "});")
    assert "JSON.stringify(validation.value)" in predict_body
    assert "file_path" not in predict_body and "sample_count" not in predict_body, "payload must come from the validator, not duplicated inline"
    assert "validateForecastPredictionResponse" in tab
    assert "predictionResult.prediction_results" in tab
    assert "predictionResult.actual_data" in tab
    for legacy_alias in ["predictionResult.historical", "predictionResult.history", "predictionResult.predicted", "predictionResult.prediction", "predictionResult.forecast", "predictionResult.actual", "predictionResult.truth"]:
        assert re.search(rf"{re.escape(legacy_alias)}(?![A-Za-z0-9_])", tab) is None
    assert "Model catalog HTTP" in tab
    assert "Data catalog HTTP" in tab
    assert "catch {}" not in tab
    assert tab.count("clearPredictionEvidence();") == 2


def test_v4_daily_contract_markers_authority_locks_and_critical_gets() -> None:
    sources = _product_sources("v4/daily", "tabs/DailyOhlcvTab.svelte", "lib/dailyOhlcvApi.ts", "v4/evidence.ts")
    combined = "\n".join(sources.values())
    daily = sources.get("webui/v2_src/src/v4/daily/V4DailyResearch.svelte", "")
    evidence = sources["webui/v2_src/src/v4/daily/dailyEvidence.ts"]
    tab = sources["webui/v2_src/src/tabs/DailyOhlcvTab.svelte"]
    api = sources["webui/v2_src/src/lib/dailyOhlcvApi.ts"]

    assert daily, "V4DailyResearch source must exist at the agreed path"
    for marker in ["data-v4-daily-research", "data-v4-daily-authority", "data-v4-daily-blockers", "data-v4-raw-audit"]:
        assert marker in daily
    assert "children?: Snippet" in daily
    assert daily.rfind("{@render children()}") > daily.rindex("data-v4-raw-audit")
    assert "<slot" not in daily

    assert "adaptPromotionLocks" in evidence
    lock_list = re.search(r"PROMOTION_LOCK_KEYS\s*=\s*\[(?P<body>.*?)\]", sources["webui/v2_src/src/v4/evidence.ts"], re.DOTALL)
    assert lock_list, "shared promotion lock adapter must expose ordered lock keys"
    assert re.findall(r"'([^']+)'", lock_list.group("body")) == _LOCK_KEYS
    for key in _LOCK_KEYS:
        assert key in combined

    _assert_in_order(tab, ["const progressRequest = loadProgressCard();", "const closeSlotRequest = loadCloseSlotCard();", "await loadSecondaryCards();"])
    assert "Promise.all([\n      withTimeout(dailyOhlcvApi.closeSlotLatest()" in tab
    assert "withTimeout(dailyOhlcvApi.closeSlotGate()" in tab
    for endpoint in ["/api/daily-ohlcv/progress", "/api/daily-ohlcv/close-slot/latest", "/api/daily-ohlcv/close-slot/gate/latest"]:
        assert endpoint in api
    assert "CRITICAL_TIMEOUT_MS = 5000" in daily
    assert "AbortController" in daily
    assert "return await Promise.race([request(controller.signal), timeout])" in daily
    assert "source.state.loaded && !source.state.data" in daily
    assert "GET unavailable" not in daily


def test_v4_daily_forecast_guardrails_test_oos_23bp_leading_zero_and_canonical_priority() -> None:
    sources = _product_sources("v4/daily", "tabs/DailyOhlcvTab.svelte")
    combined = "\n".join(sources.values())
    evidence = sources["webui/v2_src/src/v4/daily/dailyEvidence.ts"]

    for marker in ["TEST_OOS_DECLARED", "DAILY_EXPECTED_ROUND_TRIP_BP = 23", "23bp", "000250"]:
        assert marker in combined
    assert re.search(r"(?:sourceRunId|code|run_id|source_run_id)\s*[:=]\s*0\d+", combined) is None
    _assert_in_order(evidence, ["closeSlotIsCanonical(closeSlot)", "registryIsCanonical(registry)", "DECLARED_CLOSE_SLOT", "DECLARED_REGISTRY", "DECLARED_PROGRESS"])
    assert "isSmoke" in evidence
    assert "missing_test_split_evidence" in evidence


def test_wave5_frontend_sources_do_not_declare_backend_routes_or_duplicate_polling() -> None:
    product = _product_sources("App.svelte", "v4/forecast", "v4/daily", "lib/routes.ts")
    combined = "\n".join(product.values())
    app = product["webui/v2_src/src/App.svelte"]
    routes = product["webui/v2_src/src/lib/routes.ts"]

    assert all(not path.endswith(".test.ts") for path in product)
    for forbidden in ["@app.route", "Blueprint("]:
        assert forbidden not in combined
    assert app.count("installPollingWatcher();") == 1
    assert app.count("startPolling();") == 1
    assert "startPolling" not in "\n".join(value for path, value in product.items() if path != "webui/v2_src/src/App.svelte")
    assert "setInterval" not in combined

    route_ids = re.findall(r"id: '([^']+)'", _between(routes, "export const DASHBOARD_ROUTES", "] as const;"))
    assert route_ids == _FROZEN_ROUTE_IDS
    assert "/api/predict" not in routes
    assert "/api/daily-ohlcv" not in routes


def test_wave5_frozen_backend_and_dependency_files_match_wave0_baseline() -> None:
    actual = {
        relative: _normalized_sha256(_REPO_ROOT / relative)
        for relative in _FROZEN_BOUNDARY_SHA256
    }

    assert actual == _FROZEN_BOUNDARY_SHA256
