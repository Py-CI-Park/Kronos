"""Source-contract tests for the V4 Wave-2 evidence component preview."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "webui" / "v2_src" / "src"
_V4 = _SRC / "v4"

_LOCK_KEYS = [
    "promotion_allowed",
    "model_build_allowed",
    "paper_forward_allowed",
    "live_broker_order_allowed",
    "profitability_claim_allowed",
    "go_summary_allowed",
]

_UI_STATES = [
    "loading",
    "empty",
    "error",
    "stale",
    "live",
    "replay",
    "completed",
    "missing",
    "no-go",
]

_COMPONENT_MARKERS = [
    "data-v4-evidence-header",
    "data-v4-promotion-locks",
    "data-v4-lifecycle-pill",
    "data-v4-metric",
    "data-v4-evidence-disclosure",
    "data-v4-state-boundary",
    "data-v4-facet-bar",
    "data-v4-a11y-chart",
    "data-v4-evidence-system-preview",
]

_V4_SOURCES = [
    _V4 / "evidence.ts",
    _V4 / "evidenceState.ts",
    _V4 / "EvidenceSystemPreview.svelte",
    _V4 / "components" / "A11yChartFrame.svelte",
    _V4 / "components" / "EvidenceDisclosure.svelte",
    _V4 / "components" / "EvidenceHeader.svelte",
    _V4 / "components" / "FacetBar.svelte",
    _V4 / "components" / "LifecyclePill.svelte",
    _V4 / "components" / "MetricWithProvenance.svelte",
    _V4 / "components" / "PromotionLocksGrid.svelte",
    _V4 / "components" / "StateBoundary.svelte",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _source(relative: str) -> str:
    return _read(_SRC / relative)


def _style_blocks(source: str) -> list[str]:
    return re.findall(r"<style>(.*?)</style>", source, re.DOTALL)


def _const_array_values(source: str, name: str) -> list[str]:
    match = re.search(rf"export const {re.escape(name)}[^=]*= \[(?P<body>.*?)\]", source, re.DOTALL)
    assert match, f"missing exported const array {name}"
    return re.findall(r"'([^']+)'", match.group("body"))


def test_evidence_lock_keys_are_exact_and_fail_closed_reasons_are_typed() -> None:
    evidence = _source("v4/evidence.ts")

    assert _const_array_values(evidence, "PROMOTION_LOCK_KEYS") == _LOCK_KEYS
    assert "for (const key of PROMOTION_LOCK_KEYS)" in evidence
    assert "locks[key] = state.allowed" in evidence
    assert "states[key] = state" in evidence
    assert "return { key, allowed: false, sourceStatus: 'missing'" in evidence
    assert "return { key, allowed: false, sourceStatus: 'invalid'" in evidence
    assert "allLocked" in evidence
    assert "hasInvalidSource" in evidence
    assert "LOCK_SOURCE_MISSING" in evidence
    assert "LOCK_SOURCE_INVALID" in evidence
    assert "UNLOCKED_BY_SOURCE" in evidence
    assert "LOCKED_BY_SOURCE" in evidence
    assert not re.search(r"promotionAllowed|modelBuildAllowed|brokerOrderAllowed", evidence)


def test_evidence_adapters_normalize_nested_lifecycle_and_wrappers_conservatively() -> None:
    evidence = _source("v4/evidence.ts")
    state_source = _source("v4/evidenceState.ts")

    assert "lifecycleText" in evidence
    assert "lifecycleCandidate" in evidence
    assert "CONFLICT_BLOCKED" in evidence
    assert "collectWrapperRecords" in evidence
    assert "collectNestedRecords" in evidence
    assert "collectLockObjectRecords" in evidence
    assert "resolvePromotionLock" in evidence
    assert "adaptPromotionLocksWithProvenance" in evidence
    assert "mergeRecordsPreservingDeclared" not in evidence
    assert "firstBooleanFromRecords" in evidence
    assert "String(source)" not in evidence
    assert "stateText" in state_source
    assert "normalizeEvidenceStateText" in state_source
    assert "String(source)" not in state_source

def test_promotion_lock_precedence_regressions_cover_all_six_keys() -> None:
    evidence_test = _source("v4/evidence.test.ts")

    assert "assertAllLocks" in evidence_test
    assert "root false ahead of nested true for all six keys" in evidence_test
    assert "wrapper direct false ahead of container true for all six keys" in evidence_test
    assert "invalid root sources ahead of nested true for all six keys" in evidence_test
    assert "legitimate nested false when root authority is absent for all six keys" in evidence_test
    assert "PROMOTION_LOCK_KEYS.map" in evidence_test
    for key in _LOCK_KEYS:
        assert key in evidence_test


def test_evidence_states_are_exact_nine_shared_values_and_preview_renders_each() -> None:
    state_source = _source("v4/evidenceState.ts")
    preview = _source("v4/EvidenceSystemPreview.svelte")

    assert "export type EvidenceUiState" in state_source
    assert _const_array_values(state_source, "EVIDENCE_UI_STATES") == _UI_STATES
    for state in _UI_STATES:
        assert preview.count(f"state: '{state}'") == 1
    assert "stateRows" in preview
    assert "<LifecyclePill" in preview
    assert "<StateBoundary" in preview


def test_component_markers_and_shared_preview_imports_exist() -> None:
    combined = "\n".join(_read(path) for path in _V4_SOURCES)
    preview = _source("v4/EvidenceSystemPreview.svelte")

    for marker in _COMPONENT_MARKERS:
        assert marker in combined
    for adapter in [
        "adaptEvidenceIdentity",
        "adaptRunEvidence",
        "adaptMetricValue",
        "adaptPromotionLocks",
    ]:
        assert adapter in preview
    for component in [
        "PromotionLocksGrid",
        "LifecyclePill",
        "StateBoundary",
        "EvidenceHeader",
        "MetricWithProvenance",
        "EvidenceDisclosure",
        "FacetBar",
        "A11yChartFrame",
    ]:
        assert f"from './components/{component}.svelte'" in preview or f"from './components/{component}.svelte';" in preview


def test_missing_fixture_preview_cannot_render_go_or_true_for_locks() -> None:
    preview = _source("v4/EvidenceSystemPreview.svelte")

    assert "intentionallyMissingFixture" in preview
    assert "NOT_RECORDED" in preview
    assert "fail-closed" in preview
    assert "all six" not in preview.lower(), "Korean-first preview should not rely on English-only lock copy"
    assert "GO" not in preview.replace("no-go", "")
    assert "allowed: true" not in preview
    assert "promotion_allowed: true" not in preview
    assert "go_summary_allowed: true" not in preview


def test_a11y_chart_frame_exposes_all_rows_focusable_region_and_source_tokens() -> None:
    chart = _source("v4/components/A11yChartFrame.svelte")

    assert "aria-label={name}" in chart
    assert "aria-describedby={summaryId}" in chart
    assert "{@render children?.()}" in chart
    assert 'role="region"' in chart
    assert 'tabindex="0"' not in chart
    assert "bind:this={tableWrap}" in chart
    assert "class=\"table-scroll-control\"" in chart
    assert "aria-controls={tableRegionId}" in chart
    assert "onkeydown={handleTableScrollKey}" in chart
    assert "event.key === 'ArrowLeft'" in chart
    assert "event.key === 'ArrowRight'" in chart
    assert "event.key === 'Home'" in chart
    assert "event.key === 'End'" in chart
    assert ".table-scroll-control:focus-visible" in chart
    assert "const tableRowLimit" not in chart
    assert "rows.slice(" not in chart
    assert "{#each rows as row}" in chart
    assert "<table>" in chart
    assert "<caption>{summary}</caption>" in chart
    assert "<th scope=\"col\">" in chart
    assert "value === undefined" in chart and "return 'MISSING'" in chart
    assert "value === null" in chart and "return 'NOT_RECORDED'" in chart
    assert "value === ''" in chart and "return 'EMPTY_DECLARED'" in chart
    assert "표 대체는 모든 원자료 행을 숨김 없이 표시합니다." in chart
    assert "추세는 원자료에서 선언되지 않으면 만들지 않습니다." in chart


def test_a11y_chart_frame_uses_instance_safe_summary_and_table_ids() -> None:
    chart = _source("v4/components/A11yChartFrame.svelte")

    assert "idPrefix?: string" in chart
    assert "const componentId = $props.id()" in chart
    assert "idPrefix ?? name" in chart
    assert "toChartId(idPrefix ?? name)" in chart
    assert "const summaryId = $derived(`${idBase}-summary`)" in chart
    assert "const tableRegionId = $derived(`${idBase}-table`)" in chart
    assert 'aria-describedby={summaryId}' in chart
    assert "aria-controls={tableRegionId}" in chart
    assert "id={tableRegionId}" in chart
    assert "v4-a11y-chart-${chartId}" not in chart
    assert "v4-a11y-chart-table-${chartId}" not in chart


def test_promotion_locks_mobile_cells_keep_context_and_title_id_is_instance_safe() -> None:
    locks = _source("v4/components/PromotionLocksGrid.svelte")

    assert "const componentId = $props.id()" in locks
    assert "const titleId = $derived(`promotion-locks-title-${componentId}`)" in locks
    assert 'aria-labelledby={titleId}' in locks
    assert "<h2 id={titleId}>승격 잠금 6종</h2>" in locks
    for label in ["잠금", "허용", "출처", "사유"]:
        assert f'<span class="cell-label">{label}</span>' in locks
    assert ".cell-label" in locks
    assert "position: static;" in locks
    assert "clip: auto;" in locks
    assert "display: none" not in locks
    assert 'role="columnheader"' in locks
    assert "PROMOTION_LOCK_KEYS as key (key)" in locks
    for key in _LOCK_KEYS:
        assert key in locks


def test_facet_bar_disabled_facets_explain_and_guard_without_native_disabled() -> None:
    facet = _source("v4/components/FacetBar.svelte")

    assert "const componentId = $props.id()" in facet
    assert "fallbackDisabledReason = '비활성 사유: 현재 증거 상태에서 선택할 수 없습니다.'" in facet
    assert "const toIdPart = (value: string)" in facet
    assert ".replace(/[^a-z0-9가-힣]+/g, '-')" in facet
    assert "facet-reason-${componentId}-${toIdPart(facet.id)}" in facet
    assert "{@const explanation = reasonFor(facet)}" in facet
    assert "aria-disabled={facet.disabled ? 'true' : 'false'}" in facet
    assert "aria-describedby={explanation ? reasonIdFor(facet) : undefined}" in facet
    assert "onkeydown={(event) => suppressDisabledKey(facet, event)}" in facet
    assert "onclick={(event) => selectFacet(facet, event)}" in facet
    assert "event?.preventDefault()" in facet
    assert "event?.stopPropagation()" in facet
    assert "event.key !== 'Enter' && event.key !== ' '" in facet
    assert '<span class="reason" id={reasonIdFor(facet)}>{explanation}</span>' in facet
    assert "disabled={facet.disabled}" not in facet
    assert ":disabled" not in facet


def test_metric_with_provenance_fails_closed_without_masking_declared_source_values() -> None:
    metric = _source("v4/components/MetricWithProvenance.svelte")

    assert "해당 없음 · INAPPLICABLE" in metric
    assert "기록 없음 · NOT_RECORDED" in metric
    assert "값 누락 · MISSING_VALUE" in metric
    assert "값 무효 · INVALID_NONFINITE_VALUE" in metric
    assert "정밀도 무효 · INVALID_PRECISION" in metric
    assert "Math.max" not in metric
    assert "Math.min" not in metric
    assert "toFixed(metric.precision)" in metric
    assert "metric.precision <= 12" in metric
    assert "metric.availability === 'NOT_RECORDED'" in metric
    assert "metric.value === null" in metric
    assert "SOURCE_NOT_RECORDED" in metric
    assert "{#if metric.source}" not in metric


def test_v4_sources_use_semantic_tokens_and_do_not_fetch_or_touch_backend() -> None:
    combined = "\n".join(_read(path) for path in _V4_SOURCES)
    styles = "\n".join(block for path in _V4_SOURCES for block in _style_blocks(_read(path)))

    assert "fetch(" not in combined
    assert "axios" not in combined
    assert "webui/app.py" not in combined
    assert "daily_ohlcv_dashboard.py" not in combined
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", styles)
    assert not re.search(r"rgba?\(", styles)
    assert "var(--" in styles


def test_wave2_preview_is_not_global_after_wave3_domain_hosts_replace_it() -> None:
    shell = _source("layout/V4Shell.svelte")
    app = _source("App.svelte")
    home = _source("v4/home/V4MissionControl.svelte")
    rl_console = _source("v4/rl/V4RLEvidenceConsole.svelte")

    assert "EvidenceSystemPreview" not in shell
    assert "EvidenceSystemPreview" not in app
    assert "data-v4-evidence-system-preview" not in app
    assert "PromotionLocksGrid" in rl_console
    assert "MetricWithProvenance" in rl_console
    assert "data-v4-home-locks" in home


def test_wave2_contract_test_does_not_depend_on_generated_dist_or_package_changes() -> None:
    this_test = _read(Path(__file__))
    preview = _source("v4/EvidenceSystemPreview.svelte")

    assert "webui/static/v2/" + "dist" not in this_test
    assert "package.json" not in preview
    assert "package-lock" not in preview
    assert "from '$lib/api'" not in preview
    assert "from '../lib/api'" not in preview


def test_close_slot_api_exposes_exact_six_strict_false_locks(tmp_path, monkeypatch) -> None:
    from tests.test_daily_ohlcv_dashboard_api import _prepare_close_slot_dashboard_run
    from webui.app import app as flask_app

    _prepare_close_slot_dashboard_run(tmp_path, monkeypatch, with_d3=True)
    response = flask_app.test_client().get(
        "/api/daily-ohlcv/close-slot/selection?run=gate_for_dashboard&limit=5"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert set(payload["false_locks"]) == set(_LOCK_KEYS)
    for key in _LOCK_KEYS:
        assert payload[key] is False
        assert payload["false_locks"][key] is False
