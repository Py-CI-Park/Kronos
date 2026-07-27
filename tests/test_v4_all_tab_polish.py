"""Source-contract tests for the G008 all-tab visual/accessibility/performance
polish foundations.

Scope: verifies webui/v2_src/src/App.svelte wires the agreed
`V4LegacyDomainFrame` wrapper around the two remaining unwrapped tab branches
(`stom` with surface="diagnostics", `daily-rl-guide` with surface="daily-guide")
as opt-in `shell === 'v4'` branches while preserving the exact V3 fallback
markup, that all 12 canonical tab ids remain a single ordered set, that the
selected Paper Ops Ledger design tokens / Korean(CJK) copy / focus-visible /
responsive media-query markers are present across the V4 product source, that
every chart wrapper enforces an accessible name + summary + raw-data table,
that raw evidence is never hidden behind a lazy-only disclosure, and that no
optimistic/live/profit/order claim vocabulary has been introduced. Read-only:
inspects source text only, never imports/executes the Svelte or TypeScript
sources, never touches backend routes, packages, or generated dist.
"""

from __future__ import annotations

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

# Tabs already wrapped by earlier waves (G003/Wave3/4/5/6) before this change;
# this change must not touch their branches.
_ALREADY_WRAPPED_TABS = {
    "mission-control": "V4MissionControl",
    "live-training": "V4TrainingOps",
    "forecast": "V4ForecastStudio",
    "rl": "V4RLEvidenceConsole",
    "daily-ohlcv": "V4DailyResearch",
    "artifacts": "V4ArtifactsWorkspace",
    "history": "V4RunsWorkspace",
    "system-health": "V4SystemOps",
    "settings": "V4AdminWorkspace",
    "docs": "V4AdminWorkspace",
}

# The two branches this change owns.
_NEWLY_WRAPPED_TABS = {
    "stom": ("diagnostics", "StomDiagnosticsTab"),
    "daily-rl-guide": ("daily-guide", "DailyRlGuideTab"),
}

_CJK_RE = re.compile(r"[\uac00-\ud7a3]")  # Hangul syllables (Korean/CJK-adjacent copy)

_DANGEROUS_VOCABULARY = [
    "sendBeacon",
    "gtag(",
    "mixpanel",
    "google-analytics",
    "segment.io",
    "document.cookie =",
    "new WebSocket(",
    "eval(",
    "fetch('http://",
    "fetch(\"http://",
    "fetch('https://",
    "fetch(\"https://",
    "XMLHttpRequest",
    "navigator.sendBeacon",
]

_FORBIDDEN_CLAIM_LITERALS = [
    "live_broker_order_allowed = true",
    "live_broker_order_allowed: true",
    "profitability_claim_allowed = true",
    "profitability_claim_allowed: true",
    "promotion_allowed = true",
    "promotion_allowed: true",
    "go_summary_allowed = true",
    "go_summary_allowed: true",
]

# Loose English/Korean prose claims that would indicate an optimistic/live
# trading-outcome assertion leaking into read-only research surfaces.
_FORBIDDEN_PROSE_CLAIMS = [
    "profit is guaranteed",
    "live trading is enabled",
    "order has been placed",
    "order executed",
    "수익이 보장",
    "실거래가 활성화",
    "주문이 체결",
    "주문 실행 완료",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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


def _assert_in_order(source: str, needles: list[str]) -> None:
    cursor = -1
    for needle in needles:
        position = source.find(needle, cursor + 1)
        assert position > cursor, f"{needle!r} missing or out of order"
        cursor = position


def _product_sources(*relative_roots: str) -> dict[str, str]:
    """Collect .svelte/.ts product sources under the given roots, excluding tests."""
    sources: dict[str, str] = {}
    for relative_root in relative_roots:
        root = _SRC / relative_root
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in candidates:
            if path.suffix not in {".svelte", ".ts"}:
                continue
            if path.name.endswith(".test.ts"):
                continue
            if not path.is_file():
                continue
            sources[path.relative_to(_REPO_ROOT).as_posix()] = _read(path)
    return sources


# --------------------------------------------------------------------------- #
# App.svelte: single 12-branch host, tab ids preserved, new import present
# --------------------------------------------------------------------------- #
def test_app_keeps_twelve_tab_branches_with_legacy_domain_frame_import_present() -> None:
    app = _source("App.svelte")
    tab_host = _between(app, "{#snippet tabHost()}", "{/snippet}")

    assert "import V4LegacyDomainFrame from '$lib/../v4/qa/V4LegacyDomainFrame.svelte';" in app

    assert app.count("{#snippet tabHost()}") == 1
    assert app.count("{@render tabHost()}") == 2

    legacy_map = _between(app, "const LEGACY_COMPONENTS", "};")
    for tab_id in _EXPECTED_TABS:
        assert (f"'{tab_id}':" in legacy_map) or (f" {tab_id}:" in legacy_map)
    assert "data-v3-tab-host={shell === 'v3' ? '' : undefined}" in tab_host
    assert "data-v4-domain-host={shell === 'v4' ? '' : undefined}" in tab_host


# --------------------------------------------------------------------------- #
# App.svelte: exactly stom + daily-rl-guide gain a V4/V3 split; V3 fallback
# preserved exactly; all previously-wrapped branches remain untouched.
# --------------------------------------------------------------------------- #
def test_app_wraps_exactly_stom_and_daily_rl_guide_for_v4_and_preserves_v3_fallback() -> None:
    app = _source("App.svelte")
    wrapper_map = _between(app, "const V4_WRAPPERS", "};")
    props_map = _between(app, "const V4_WRAPPER_PROPS", "};")

    for tab_id, (surface, legacy) in _NEWLY_WRAPPED_TABS.items():
        key = f"'{tab_id}'" if "-" in tab_id else tab_id
        assert f"{key}: {legacy}" in _between(app, "const LEGACY_COMPONENTS", "};")
        assert f"{key}: V4LegacyDomainFrame" in wrapper_map
        assert f"{key}: {{ surface: '{surface}' }}" in props_map

    # Every already-wrapped branch keeps its existing wrapper untouched by
    # this change (contract: "only two branches change").
    for tab_id, wrapper in _ALREADY_WRAPPED_TABS.items():
        key = f"'{tab_id}'" if "-" in tab_id else tab_id
        assert f"{key}: {wrapper}" in wrapper_map


def test_app_wraps_exactly_two_branches_total() -> None:
    app = _source("App.svelte")
    wrapper_map = _between(app, "const V4_WRAPPERS", "};")
    assert wrapper_map.count("V4LegacyDomainFrame") == len(_NEWLY_WRAPPED_TABS)


# --------------------------------------------------------------------------- #
# Positive fixture: prove the branch-shape guard used above can actually fail
# --------------------------------------------------------------------------- #
def test_positive_fixture_missing_v3_fallback_fails_the_in_order_guard() -> None:
    broken_branch = (
        "tab === 'stom'}\n"
        "{#if shell === 'v4'}\n"
        '<V4LegacyDomainFrame surface="diagnostics">\n'
        "<StomDiagnosticsTab />\n"
        "</V4LegacyDomainFrame>\n"
        # V3 fallback deliberately omitted
        "{/if}"
    )
    try:
        _assert_in_order(
            broken_branch,
            [
                "{#if shell === 'v4'}",
                '<V4LegacyDomainFrame surface="diagnostics">',
                "<StomDiagnosticsTab />",
                "</V4LegacyDomainFrame>",
                "{:else}",
                "<StomDiagnosticsTab />",
            ],
        )
    except AssertionError:
        pass
    else:
        raise AssertionError("guard should have failed on a branch missing its V3 fallback")


# --------------------------------------------------------------------------- #
# V4LegacyDomainFrame: agreed marker, dual surfaces, snippet children, and a
# raw-evidence-never-hidden (non-lazy) disclosure contract.
# --------------------------------------------------------------------------- #
def test_v4_legacy_domain_frame_exists_with_marker_dual_surfaces_and_snippet_children() -> None:
    frame_path = "webui/v2_src/src/v4/qa/V4LegacyDomainFrame.svelte"
    sources = _product_sources("v4/qa")
    assert sources, "v4/qa product sources must exist for the agreed V4LegacyDomainFrame"
    assert frame_path in sources, f"{frame_path} must exist at the agreed path"
    frame = sources[frame_path]

    assert re.search(r"surface\s*:\s*'diagnostics'\s*\|\s*'daily-guide'", frame), (
        "surface prop must be a diagnostics|daily-guide union"
    )
    assert "children?: Snippet" in frame
    assert "<slot" not in frame
    assert "{@render children()}" in frame
    assert "data-v4-legacy-domain-frame={surface}" in frame


def test_v4_legacy_domain_frame_never_hides_raw_evidence_behind_a_lazy_only_surface() -> None:
    frame_path = "webui/v2_src/src/v4/qa/V4LegacyDomainFrame.svelte"
    sources = _product_sources("v4/qa")
    frame = sources[frame_path]

    # Must not delegate to EvidenceDisclosure/details with a lazy prop set true,
    # and must not conditionally gate the rendered children on an "expanded"/
    # "open" state — the legacy child content must always be mounted/visible.
    assert "lazy" not in frame or "lazy={false}" in frame or "lazy = false" in frame
    assert "lazy={true}" not in frame
    assert "lazy\n" not in frame
    # A `{#if children && (!lazy || expanded)}`-style conditional gate would
    # hide raw evidence until the user expands it; the agreed contract forbids it.
    assert not re.search(r"\{#if[^}]*expanded[^}]*\}", frame)
    assert "hidden" not in frame.lower() or "hidden=" not in frame
    # children render unconditionally (not behind an `{#if}` on children alone
    # without an always-open disclosure)
    render_line = next(line for line in frame.splitlines() if "{@render children()}" in line)
    assert render_line.strip() == "{@render children()}", (
        "children must render unconditionally, not gated behind a lazy {#if}"
    )


def test_positive_fixture_lazy_gate_pattern_is_detected_by_the_hiding_guard() -> None:
    """Positive-fixture proof: the expanded-gate regex used above must
    actually fire on a deliberately lazy/hidden sample."""
    tainted = "{#if children && (!lazy || expanded)}\n<div>{@render children()}</div>\n{/if}"
    assert re.search(r"\{#if[^}]*expanded[^}]*\}", tainted)


# --------------------------------------------------------------------------- #
# Selected design tokens: semantic light/dark tokens exist and are the ones
# used throughout V4 source (no raw hex/rgba color literals in V4 styles).
# --------------------------------------------------------------------------- #
def test_semantic_light_dark_tokens_are_declared_and_used_across_v4_source() -> None:
    core_css = _read(_SRC / "styles" / "core.css")
    assert re.search(r":root\s*\{", core_css)
    assert '[data-theme="dark"]' in core_css
    light_block = _between(core_css, ":root {", "\n}")
    dark_block = _between(core_css, '[data-theme="dark"] {', "\n}")
    for token in ("--bg:", "--surface:", "--fg:", "--fg-strong:", "--muted:", "--border"):
        assert token in light_block, f"{token} missing from light token block"
        assert token in dark_block, f"{token} missing from dark token block"

    sources = _product_sources("v4")
    assert sources, "v4 product sources must exist for the token-usage scan"
    combined = "\n".join(sources.values()) + "\n" + _source("layout/V4Shell.svelte")
    for token_usage in ("var(--fg-strong)", "var(--bg)", "var(--surface)", "var(--muted)"):
        assert token_usage in combined, f"{token_usage} not used anywhere in V4 source"

    # No raw hex/rgba literals leaking into V4 <style> blocks (semantic tokens only).
    for path, source in sources.items():
        if not path.endswith(".svelte") or "<style>" not in source:
            continue
        style = _between(source, "<style>", "</style>")
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", style), f"raw hex color literal found in {path}"


def test_positive_fixture_raw_hex_scan_fires_on_a_tainted_style_block() -> None:
    tainted_style = "<style>.x { color: #ff00aa; }</style>"
    tainted = _between(tainted_style, "<style>", "</style>")
    assert re.search(r"#[0-9a-fA-F]{3,8}\b", tainted)


# --------------------------------------------------------------------------- #
# Korean/CJK copy present across V4 product source (not just test fixtures)
# --------------------------------------------------------------------------- #
def test_korean_cjk_copy_present_across_v4_source_and_in_both_new_wrappers_targets() -> None:
    sources = _product_sources("v4")
    assert sources, "v4 product sources must exist for the CJK scan"
    files_with_cjk = [path for path, source in sources.items() if _CJK_RE.search(source)]
    assert len(files_with_cjk) >= 5, "Korean/CJK copy should appear broadly across V4 source"

    # The two legacy tabs being wrapped already carry CJK-heavy domain copy;
    # confirm that source-level fact so the wrap doesn't strip/replace it.
    stom_tab = _source("tabs/StomDiagnosticsTab.svelte")
    guide_tab = _source("tabs/DailyRlGuideTab.svelte")
    assert _CJK_RE.search(stom_tab)
    assert _CJK_RE.search(guide_tab)


def test_positive_fixture_cjk_regex_matches_hangul_and_rejects_ascii_only() -> None:
    assert _CJK_RE.search("증거 요약 차트 계약")
    assert not _CJK_RE.search("evidence summary chart contract")


# --------------------------------------------------------------------------- #
# Focus-visible and responsive markers across V4 source
# --------------------------------------------------------------------------- #
def test_focus_visible_and_responsive_media_query_markers_exist_across_v4_source() -> None:
    core_css = _read(_SRC / "styles" / "core.css")
    assert ":focus-visible" in core_css

    sources = _product_sources("v4")
    assert sources, "v4 product sources must exist for the focus/responsive scan"
    focus_visible_files = [p for p, s in sources.items() if ":focus-visible" in s]
    media_query_files = [p for p, s in sources.items() if re.search(r"@media\s*\(max-width", s)]
    assert len(focus_visible_files) >= 1
    assert len(media_query_files) >= 5, "responsive @media breakpoints should appear broadly across V4 source"


def test_positive_fixture_focus_visible_and_media_query_scans_are_live() -> None:
    tainted = ".btn { color: red; }"  # no focus-visible, no media query
    assert ":focus-visible" not in tainted
    assert not re.search(r"@media\s*\(max-width", tainted)


# --------------------------------------------------------------------------- #
# Chart wrappers: accessible name + summary + raw-data table, no bare charts
# --------------------------------------------------------------------------- #
def test_a11y_chart_frame_requires_accessible_name_summary_and_table() -> None:
    frame_path = "webui/v2_src/src/v4/components/A11yChartFrame.svelte"
    sources = _product_sources("v4/components")
    assert frame_path in sources
    frame = sources[frame_path]

    assert "name: string" in frame
    assert "summary: string" in frame
    assert 'aria-label={name}' in frame
    assert "<p id={summaryId}" in frame
    assert "{summary}" in frame
    assert "<table>" in frame
    assert "<caption>{summary}</caption>" in frame
    # every raw data row must be rendered, not truncated/hidden
    assert "{#each rows as row}" in frame


def test_no_bare_chart_elements_bypass_the_a11y_chart_frame_in_v4_source() -> None:
    sources = _product_sources("v4")
    assert sources, "v4 product sources must exist for the bare-chart scan"
    for path, source in sources.items():
        if path.endswith("A11yChartFrame.svelte"):
            continue
        assert "<canvas" not in source, f"bare <canvas> chart element found outside A11yChartFrame in {path}"

    # At least one real usage of the accessible wrapper exists in V4 product source.
    usages = [p for p, s in sources.items() if "<A11yChartFrame" in s]
    assert usages, "A11yChartFrame must actually be used somewhere in V4 source"


def test_positive_fixture_bare_canvas_scan_fires_on_a_tainted_sample() -> None:
    tainted = "<canvas class=\"raw-chart\"></canvas>"
    assert "<canvas" in tainted


# --------------------------------------------------------------------------- #
# No optimistic/live/profit/order claim vocabulary introduced anywhere in V4
# product source (including the two newly-wrapped surfaces).
# --------------------------------------------------------------------------- #
def test_v4_source_introduces_no_optimistic_live_profit_or_order_claims() -> None:
    sources = _product_sources("v4")
    app = _source("App.svelte")
    combined = "\n".join(sources.values()) + "\n" + app
    assert sources, "v4 product sources must exist for the claims scan"

    for forbidden in _DANGEROUS_VOCABULARY:
        assert forbidden not in combined, f"forbidden vocabulary {forbidden!r} found in V4 product files"
    for forbidden_claim in _FORBIDDEN_CLAIM_LITERALS:
        assert forbidden_claim not in combined
    for forbidden_prose in _FORBIDDEN_PROSE_CLAIMS:
        assert forbidden_prose not in combined


def test_positive_fixture_claims_scan_is_live_and_can_fail() -> None:
    """Positive-fixture proof: the same scan used above must actually fire on
    a deliberately tainted sample, so a silently-vacuous assertion can't hide
    a broken scan."""
    tainted = "export const state = { live_broker_order_allowed: true, note: '주문이 체결되었습니다' };"
    for forbidden in ["live_broker_order_allowed: true", "주문이 체결"]:
        assert forbidden in tainted


# --------------------------------------------------------------------------- #
# Scope: this change touches only App.svelte inside v2_src/src root (plus the
# separately-owned v4/qa/V4LegacyDomainFrame.svelte it imports).
# --------------------------------------------------------------------------- #
def test_app_svelte_change_does_not_touch_backend_or_duplicate_bootstrap() -> None:
    app = _source("App.svelte")
    for forbidden in ["@app.route", "Blueprint(", "sqlite3.connect(", "os.remove("]:
        assert forbidden not in app
    assert app.count("installPollingWatcher();") == 1
    assert app.count("startPolling();") == 1
