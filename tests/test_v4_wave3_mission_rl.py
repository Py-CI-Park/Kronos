"""Source-contract tests for V4 Wave-3 mission-control and RL hosts."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "webui" / "v2_src" / "src"
_V4 = _SRC / "v4"

_LEGACY_TAB_COMPONENTS = [
    "MissionControl",
    "LiveTrainingTab",
    "ForecastWorkbenchTab",
    "StomDiagnosticsTab",
    "RLTradingTab",
    "DailyOhlcvTab",
    "DailyRlGuideTab",
    "ArtifactsModelsTab",
    "HistoryRunsTab",
    "SystemHealthTab",
    "SettingsTab",
    "DocsTab",
]

_V4_FALLBACK_COMPONENTS = [
    "LiveTrainingTab",
    "ForecastWorkbenchTab",
    "StomDiagnosticsTab",
    "DailyOhlcvTab",
    "DailyRlGuideTab",
    "ArtifactsModelsTab",
    "HistoryRunsTab",
    "SystemHealthTab",
    "SettingsTab",
    "DocsTab",
]

_LOCK_KEYS = [
    "promotion_allowed",
    "model_build_allowed",
    "paper_forward_allowed",
    "live_broker_order_allowed",
    "profitability_claim_allowed",
    "go_summary_allowed",
]

_HOME_MARKERS = [
    "data-v4-mission-control",
    "data-v4-top-blocker",
    "data-lock-key",
    "data-v4-workflow-map",
    "data-v4-home-card",
    "data-v4-workflow-step",
]

_RL_MARKERS = [
    "data-v4-rl-console",
    "data-v4-selected-run",
    "data-v4-rl-lane",
    "data-v4-rl-facts",
    "data-v4-raw-audit",
]

_RL_SHARED_COMPONENTS = [
    "EvidenceHeader",
    "PromotionLocksGrid",
    "MetricWithProvenance",
    "EvidenceDisclosure",
    "StateBoundary",
]

_OPTIMISTIC_BROKER_ORDER_CLAIMS = [
    re.compile(
        r"(?:live[\s-]*(?:broker|trading)[\s-]*(?:order)?|broker[\s-]*order|브로커[/\s·-]*주문|실거래[/\s·-]*주문)"
        r"[^_\"'`\n]{0,48}"
        r"(?:ready|enabled|allowed|approved|go|가능|허용|준비|해제)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:ready|enabled|allowed|approved|go|가능|허용|준비|해제)"
        r"[^_\"'`\n]{0,48}"
        r"(?:live[\s-]*(?:broker|trading)[\s-]*(?:order)?|broker[\s-]*order|브로커[/\s·-]*주문|실거래[/\s·-]*주문)",
        re.IGNORECASE,
    ),
]
_OPTIMISTIC_BROKER_ORDER_FIXTURES = [
    "live broker\norder ready",
    "브로커/\n주문 가능",
    "ready for live\nbroker order",
    "준비\n브로커/주문",
]


def _is_product_source_path(path: Path) -> bool:
    parts = {part.casefold() for part in path.parts}
    name = path.name.casefold()
    return (
        path.suffix.casefold() in {".svelte", ".ts"}
        and ".test." not in name
        and ".spec." not in name
        and "__tests__" not in parts
        and not parts.intersection({"test", "tests", "fixture", "fixtures"})
    )


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _source(relative: str) -> str:
    return _read(_SRC / relative)


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def _v4_source_paths(relative_dir: str) -> list[Path]:
    root = _V4 / relative_dir
    assert root.exists(), f"missing V4 source directory: {root}"
    paths = sorted([*root.rglob("*.svelte"), *root.rglob("*.ts")])
    product_paths = [path for path in paths if _is_product_source_path(path)]
    assert product_paths, f"missing V4 product sources under: {root}"
    assert all(_is_product_source_path(path) for path in product_paths), product_paths
    return product_paths


def _v4_sources(relative_dir: str) -> str:
    return "\n".join(_read(path) for path in _v4_source_paths(relative_dir))


def _count_ordered_ids(source: str, name: str) -> int:
    match = re.search(rf"const\s+{re.escape(name)}[^=]*=\s*\[(?P<body>.*?)\]\s*;", source, re.DOTALL)
    assert match, f"missing ordered id source for {name}"
    return len(re.findall(r"'[^']+'", match.group("body")))
def _optimistic_match(pattern: re.Pattern[str], source: str) -> re.Match[str] | None:
    normalized = re.sub(r"\s+", " ", source)
    for match in pattern.finditer(normalized):
        context = normalized[max(0, match.start() - 24) : match.end() + 24]
        if re.search(r"\b(?:not|no|never|blocked|false)\b|않|못|불가|금지|허용되지", context, re.IGNORECASE):
            continue
        return match
    return None


def _assert_no_optimistic_broker_order_claims(source: str) -> None:
    canonical_lock = "live_broker_order_allowed"
    assert canonical_lock in source
    scan_source = source.replace(canonical_lock, "")
    for fixture_index in (0, 1):
        assert _optimistic_match(_OPTIMISTIC_BROKER_ORDER_CLAIMS[0], _OPTIMISTIC_BROKER_ORDER_FIXTURES[fixture_index]) is not None
    for fixture_index in (2, 3):
        assert _optimistic_match(_OPTIMISTIC_BROKER_ORDER_CLAIMS[1], _OPTIMISTIC_BROKER_ORDER_FIXTURES[fixture_index]) is not None
    for pattern in _OPTIMISTIC_BROKER_ORDER_CLAIMS:
        assert _optimistic_match(pattern, scan_source) is None
    for honest_negative in [
        "live broker order is not ready",
        "브로커/주문은 허용되지 않습니다",
        "live_broker_order_allowed remains false",
    ]:
        assert all(_optimistic_match(pattern, honest_negative) is None for pattern in _OPTIMISTIC_BROKER_ORDER_CLAIMS)

def test_product_source_path_predicate_rejects_test_conventions() -> None:
    accepted = [Path("v4/home/missionControl.ts"), Path("v4/rl/V4RLEvidenceConsole.svelte")]
    rejected = [
        Path("v4/home/missionControl.test.ts"),
        Path("v4/home/missionControl.spec.ts"),
        Path("v4/home/__tests__/missionControl.ts"),
        Path("v4/home/test/fixture.ts"),
        Path("v4/home/fixtures/fixture.ts"),
    ]
    assert all(_is_product_source_path(path) for path in accepted)
    assert all(not _is_product_source_path(path) for path in rejected)



def test_app_routes_only_v4_mission_and_rl_to_wave3_hosts_and_preserves_v3() -> None:
    app = _source("App.svelte")
    tab_host = _between(app, "{#snippet tabHost()}", "{/snippet}")
    v4_shell_branch = _between(app, "{#if shell === 'v4'}\n  <V4Shell>", "{:else}")

    assert "import V4MissionControl from '$lib/../v4/home/V4MissionControl.svelte';" in app
    assert "import V4RLEvidenceConsole from '$lib/../v4/rl/V4RLEvidenceConsole.svelte';" in app

    assert "data-v3-tab-host={shell === 'v3' ? '' : undefined}" in tab_host
    assert "data-v4-domain-host={shell === 'v4' ? '' : undefined}" in tab_host
    assert "{@render tabHost()}" in v4_shell_branch

    branches = re.findall(r"tab === '([^']+)'", app)
    assert len(branches) == len(set(branches)) == 12, "V4 routing must not duplicate or remove tab branches"
    for component in _LEGACY_TAB_COMPONENTS:
        assert f"<{component}" in tab_host
    assert "tab === 'mission-control'" in tab_host
    assert "shell === 'v4'" in tab_host
    assert "<V4MissionControl />" in tab_host
    assert "tab === 'rl'" in tab_host
    assert "<V4RLEvidenceConsole>" in tab_host
    for component in _V4_FALLBACK_COMPONENTS:
        assert f"<{component}" in tab_host


def test_v4_rl_host_places_legacy_rl_as_final_raw_audit_child() -> None:
    app = _source("App.svelte")
    rl_branch = _between(app, "<V4RLEvidenceConsole>", "</V4RLEvidenceConsole>")
    rl_console = _source("v4/rl/V4RLEvidenceConsole.svelte")

    assert rl_branch.strip() == "<V4RLEvidenceConsole>\n          <RLTradingTab />"

    raw_audit_index = rl_console.index("data-v4-raw-audit")
    render_candidates = [rl_console.rfind("{@render children?.()}"), rl_console.rfind("{@render children()}")]
    render_index = max(render_candidates)
    assert render_index > raw_audit_index, "legacy RL children must render inside the final raw-audit slot"
    assert raw_audit_index > rl_console.index("data-v4-rl-facts")
    assert raw_audit_index > rl_console.index("data-v4-rl-lane")
    assert "<slot" not in rl_console, "Svelte 5 snippet children contract should not regress to slot syntax"


def test_v4_shell_removes_global_wave2_preview_but_keeps_foundation_and_coexistence() -> None:
    shell = _source("layout/V4Shell.svelte")

    assert "EvidenceSystemPreview" not in shell
    assert "data-v4-shell" in shell
    assert "data-v4-opt-in-badge" in shell
    assert "CommandPalette" in shell
    assert "<Header />" in shell
    assert "<OpsStrip />" in shell
    assert "{@render children()}" in shell
    assert shell.index("<section class=\"v4-foundation\"") < shell.index("{@render children()}") < shell.index("<CommandPalette />")


def test_wave3_sources_do_not_add_backend_package_route_alias_or_polling_contracts() -> None:
    app = _source("App.svelte")
    shell = _source("layout/V4Shell.svelte")
    home_and_rl = _v4_sources("home") + "\n" + _v4_sources("rl")
    wave3_sources = app + "\n" + shell + "\n" + home_and_rl

    for forbidden in ["webui/app.py", "package.json", "package-lock.json", "resolveRoute(", "startPolling("]:
        assert forbidden not in home_and_rl
    assert app.count("startPolling();") == 1
    assert "installPollingWatcher();" in app
    assert "from '$lib/routes'" in app
    assert "fetch(" not in shell
    _assert_no_optimistic_broker_order_claims(wave3_sources)


def test_v4_mission_control_declares_exact_six_fail_closed_home_evidence_markers() -> None:
    home = _v4_sources("home")

    for marker in _HOME_MARKERS:
        assert marker in home
    assert _count_ordered_ids(home, "CARD_ORDER") == 6
    for key in _LOCK_KEYS:
        assert key in home
    assert "deriveStatusLocks" in home
    assert "adaptPromotionLocks({})" in home
    assert "TEST OOS" in home
    assert home.index("TEST OOS") < home.index("data-v4-home-card")
    assert "all six" not in home.lower()
    assert re.search(r"(?:run_id|source_run_id|symbol|code)\s*:\s*0\d+", home) is None, "leading-zero identifiers must stay strings, not numeric literals"
    home_paths = _v4_source_paths("home")
    assert all(_is_product_source_path(path) for path in home_paths)


def test_v4_rl_console_declares_required_markers_components_and_research_boundaries() -> None:
    rl = _v4_sources("rl")
    console = _source("v4/rl/V4RLEvidenceConsole.svelte")

    for marker in _RL_MARKERS:
        assert marker in console
    for component in _RL_SHARED_COMPONENTS:
        assert component in console
    for adapter in ["adaptRunEvidence", "adaptEvidenceIdentity", "adaptMetricValue"]:
        assert adapter in rl
    assert "RULE" in rl
    assert "RL" in rl
    assert "rule" in rl.lower() and "rl" in rl.lower()
    for boundary in ["No full RL model promotion", "research-only", "Close-slot NO-GO", "D4 SEED_NOISE_NO_GO"]:
        assert boundary in rl
    assert "does not infer" in rl
    for stale_guard in [
        "createRequestGate",
        "runSelectGate.next()",
        "runSelectGate.isCurrent(token)",
        'data-request-gate="createRequestGate:isCurrent"',
        "stale response guarded",
    ]:
        assert stale_guard in rl
    for error_marker in [
        "RLIABLE_FETCH_FAILED",
        "EVENTS_FETCH_FAILED",
        "data-rliable-source-state",
        "data-events-source-state",
    ]:
        assert error_marker in console
    assert "Promise.allSettled" in console
    assert ".catch(() => null)" not in console
    assert ".catch(() => ({ rows: []" not in console
