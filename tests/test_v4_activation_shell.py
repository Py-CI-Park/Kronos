"""Source-contract regression tests for the G003 V4 activation shell.

These tests intentionally inspect Svelte/TypeScript source instead of generated
``dist`` output. The contract is that V3 remains the default shell, V4 is local
opt-in only, all existing dashboard tab routes survive unchanged, and the V4
command palette stays read-only/local.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "webui" / "v2_src" / "src"
_EXPECTED_TABS = [
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
_DANGEROUS_VERBS = [
    "train",
    "execute",
    "order",
    "broker",
    "account",
    "paper trade",
    "promote",
    "model build",
    "publish GO",
    "delete artifact",
    "mutate DB",
    "run job",
    "push",
    "merge",
    "tag",
]
_FROZEN_FRONTEND_BOUNDARY_CANDIDATES = {
    "webui/v2_src/src/App.svelte",
    "webui/v2_src/src/layout/V4Shell.svelte",
    "webui/v2_src/src/layout/Sidebar.svelte",
    "webui/v2_src/src/layout/Header.svelte",
    "webui/v2_src/src/layout/OpsStrip.svelte",
    "webui/v2_src/src/layout/CommandPalette.svelte",
    "webui/v2_src/src/lib/commandPalette.ts",
    "webui/v2_src/src/lib/shellMode.ts",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _source(relative: str) -> str:
    return _read(_SRC / relative)


def _const_block(source: str, name: str) -> str:
    match = re.search(rf"const {re.escape(name)}[^=]*= \[", source)
    assert match, f"missing const array {name}"
    start = match.end() - 1
    depth = 0
    for index in range(start, len(source)):
        char = source[index]
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unterminated const array {name}")


def _style_block(source: str) -> str:
    match = re.search(r"<style>(?P<style>.*?)</style>", source, re.DOTALL)
    assert match, "missing style block"
    return match.group("style")


def _assert_in_order(source: str, needles: list[str]) -> None:
    cursor = -1
    for needle in needles:
        position = source.find(needle, cursor + 1)
        assert position > cursor, f"{needle!r} was missing or out of order"
        cursor = position


# --------------------------------------------------------------------------- #
# App shell activation and tab preservation
# --------------------------------------------------------------------------- #
def test_app_preserves_all_tab_branches_popstate_and_polling() -> None:
    app = _source("App.svelte")

    assert "data-kronos-shell={shell}" in app
    assert "data-v3-tab-host" in app
    assert "<V4Shell>" in app
    assert "shell === 'v4'" in app
    assert "initializeDashboardShell()" in app
    assert "syncTabFromLocation({ replaceAlias: true })" in app
    assert "window.addEventListener('popstate', handlePopstate)" in app
    assert "window.removeEventListener('popstate', handlePopstate)" in app
    assert "installPollingWatcher()" in app
    assert "startPolling()" in app

    branches = re.findall(r"tab === '([^']+)'", app)
    assert len(branches) == len(set(branches)) == len(_EXPECTED_TABS)
    assert set(branches) == set(_EXPECTED_TABS)


# --------------------------------------------------------------------------- #
# V4 shell composition
# --------------------------------------------------------------------------- #
def test_v4_shell_reuses_existing_chrome_and_exposes_opt_in_markers() -> None:
    shell = _source("layout/V4Shell.svelte")

    _assert_in_order(shell, ["import Sidebar", "import Header", "import OpsStrip", "import CommandPalette"])
    _assert_in_order(shell, ["<Sidebar />", "<Header />", "<OpsStrip />", "{@render children()}", "<CommandPalette />"])
    assert "data-kronos-shell={shell}" in shell
    assert "data-v4-shell" in shell
    assert "data-v4-opt-in-badge" in shell
    assert "V4 opt-in · read-only" in shell


# --------------------------------------------------------------------------- #
# Shell-mode guards: V3 default, V4 opt-in, fail closed
# --------------------------------------------------------------------------- #
def test_shell_mode_keeps_v3_default_query_storage_persist_and_fail_closed_guards() -> None:
    mode = _source("lib/shellMode.ts")

    assert "export type DashboardShell = 'v3' | 'v4'" in mode
    assert "export const SHELL_STORAGE_KEY = 'kronos-dashboard-shell'" in mode
    assert "const DEFAULT_SHELL: DashboardShell = 'v3'" in mode
    assert "params.get('ui')" in mode
    assert "params.get('ui_persist') === '1'" in mode
    assert "source: 'query'" in mode
    assert "source: 'storage'" in mode
    assert "source: 'default'" in mode
    assert "return value === 'v3' || value === 'v4'" in mode
    assert "localStorage.getItem(SHELL_STORAGE_KEY)" in mode
    assert "localStorage.setItem(SHELL_STORAGE_KEY, shell)" in mode
    assert "history.pushState" in mode and "history.replaceState" in mode
    assert "params.set('ui', shell)" in mode
    assert "export function preserveShellQuery(targetUrl: string, currentSearch: string)" in mode
    assert "targetParams.set('ui', shell)" in mode
    assert "targetParams.set('ui_persist', '1')" in mode
    assert "return targetUrl" in mode
    assert mode.count("catch {") >= 4, "storage/document/history parsing must fail closed"

def test_routes_preserve_shell_query_during_canonicalization_and_navigation() -> None:
    routes = _source("lib/routes.ts")

    assert "import { preserveShellQuery } from './shellMode'" in routes
    assert "routeUrl(route.id, { currentSearch: locationLike.search })" in routes
    assert "return preserveShellQuery(`/rl?section=${encodeURIComponent(section)}`, locationLike.search)" in routes
    assert "export function routeUrl(tabId: string, options: { currentSearch?: string } = {})" in routes
    assert "window.location.search" in routes
    assert "return preserveShellQuery(baseUrl, currentSearch)" in routes
    assert "const nextUrl = routeUrl(tabId)" in routes
    assert "replaceAlias" in routes
    assert "window.history.replaceState({ tab: route.id }, '', canonical)" in routes
    for alias in ["/rl", "/daily-ohlcv", "/daily-rl-guide", "/daily-ohlcv/rl-guide"]:
        assert f"'{alias}'" in routes, f"{alias} must be executable route data"

# --------------------------------------------------------------------------- #
# Sidebar navigation contracts
# --------------------------------------------------------------------------- #
def test_sidebar_v4_groups_contain_all_twelve_tab_ids_once_and_v3_markers_remain() -> None:
    sidebar = _source("layout/Sidebar.svelte")
    v4_groups = _const_block(sidebar, "v4Groups")
    v3_groups = _const_block(sidebar, "v3Groups")

    v4_ids = re.findall(r"id: '([^']+)'", v4_groups)
    assert len(v4_ids) == len(set(v4_ids)) == len(_EXPECTED_TABS)
    assert set(v4_ids) == set(_EXPECTED_TABS)

    assert "data-v4-shell={shell === 'v4' ? 'sidebar' : undefined}" in sidebar
    assert "data-v4-command-trigger" in sidebar
    assert "onclick={requestCommandPalette}" in sidebar
    assert "let navGroups = $derived(shell === 'v4' ? v4Groups : v3Groups)" in sidebar

    for marker in [
        "커맨드",
        "Kronos 예측",
        "트레이딩 리서치",
        "라이브 · 시스템",
        "일봉 RL 설명서",
        "Trading Command Center",
        "data-nav-child=\"true\"",
    ]:
        assert marker in v3_groups or marker in sidebar


# --------------------------------------------------------------------------- #
# Header/ops strip V4 affordances
# --------------------------------------------------------------------------- #
def test_header_sidebar_command_triggers_exist_without_removing_existing_controls() -> None:
    header = _source("layout/Header.svelte")
    sidebar = _source("layout/Sidebar.svelte")

    assert "data-v4-command-trigger" in header
    assert "onclick={requestCommandPalette}" in header
    assert "Ctrl/Cmd+K" in header
    assert "data-theme-toggle" in header
    assert "toggleSidebar" in header
    assert "data-v4-command-trigger" in sidebar
    assert "onclick={requestCommandPalette}" in sidebar


def test_ops_strip_order_keeps_existing_readouts_and_places_v4_marker_after_posture() -> None:
    ops = _source("layout/OpsStrip.svelte")

    _assert_in_order(
        ops,
        [
            "<span class=\"ops-lead-text\">LIVE</span>",
            "<span class=\"ops-key\">DATA</span>",
            "<span class=\"ops-key\">GPU</span>",
            "<span class=\"ops-key\">RAM</span>",
            "<span class=\"ops-key\">POLL</span>",
            "<span class=\"ops-key\">자세</span>",
            "data-v4-status-marker",
            "<span class=\"ops-key\">V4</span>",
        ],
    )
    assert "data-ops-strip" in ops
    assert "data-v4-shell={shell === 'v4' ? 'ops-strip' : undefined}" in ops


# --------------------------------------------------------------------------- #
# Command palette shell and behavior hooks
# --------------------------------------------------------------------------- #
def test_command_palette_has_local_dialog_combobox_listbox_keyboard_focus_and_marker() -> None:
    palette = _source("layout/CommandPalette.svelte")

    for marker in [
        "data-v4-command-palette",
        "role=\"dialog\"",
        "aria-modal=\"true\"",
        "role=\"combobox\"",
        "aria-controls={LISTBOX_ID}",
        "role=\"listbox\"",
        "role=\"option\"",
        "OPEN_PALETTE_EVENT",
        "window.addEventListener('keydown', handleGlobalKeydown)",
        "event.ctrlKey || event.metaKey",
        "event.key.toLowerCase() === 'k'",
        "event.key === 'ArrowDown'",
        "event.key === 'ArrowUp'",
        "event.key === 'Enter'",
        "event.key === 'Escape'",
        "event.key === 'Tab'",
        "trapFocus(event)",
        "previousFocus = document.activeElement instanceof HTMLElement",
        "previousFocus?.focus()",
        "inputEl?.focus()",
        "setDashboardShell(shell, { persist: true, replace: true })",
    ]:
        assert marker in palette

    assert "fetch(" not in palette


def test_command_model_blocks_all_dangerous_verbs_and_has_no_backend_mutation_action() -> None:
    model = _source("lib/commandPalette.ts")
    blocked_block = _const_block(model, "BLOCKED_VERBS")

    for verb in _DANGEROUS_VERBS:
        assert f"['{verb}'," in blocked_block, f"missing blocked dangerous verb: {verb}"
    assert blocked_block.count("['") == len(_DANGEROUS_VERBS)
    assert "kind: 'blocked'" in model
    assert "action: { type: 'blocked' }" in model
    assert "disabledReason: reason" in model
    assert "if (command.disabledReason) return { status: 'blocked'" in model

    action_types = set(re.findall(r"type: '([^']+)'", model))
    assert action_types == {"navigateToTab", "inspect", "filter", "setDashboardShell", "blocked"}
    for forbidden in ["fetch(", ".post(", ".put(", ".patch(", ".delete(", "method: 'POST'", "method: 'PUT'", "method: 'PATCH'", "method: 'DELETE'"]:
        assert forbidden not in model


# --------------------------------------------------------------------------- #
# Command palette styling: semantic tokens, no raw color surfaces
# --------------------------------------------------------------------------- #
def test_command_palette_css_uses_semantic_tokens_without_raw_hex_or_rgba_surfaces() -> None:
    style = _style_block(_source("layout/CommandPalette.svelte"))

    assert "var(--surface" in style
    assert "var(--bg" in style
    assert "var(--fg" in style
    assert "var(--border" in style
    assert "var(--accent" in style
    assert "color-mix(in oklab" in style
    assert "rgba(" not in style.lower()
    assert "hsla(" not in style.lower()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", style)


# --------------------------------------------------------------------------- #
# G003 frontend boundary should not expand frozen-file ownership
# --------------------------------------------------------------------------- #
def test_g003_frontend_sources_are_not_named_by_frozen_file_boundary_helper() -> None:
    script = _REPO_ROOT / "scripts" / "verify_dashboard_v3_execution_boundaries.py"
    spec = importlib.util.spec_from_file_location("verify_dashboard_v3_execution_boundaries", script)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)

    frozen_files = set(mod.FROZEN_FILES)
    assert frozen_files.isdisjoint(_FROZEN_FRONTEND_BOUNDARY_CANDIDATES)
