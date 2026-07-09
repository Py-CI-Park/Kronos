// Shared display-label helpers for backend status/verdict enums.
//
// Vocabulary-reconciliation decision (G11):
// The dashboard has TWO distinct status vocabularies that were previously
// duplicated in-component. This file unifies both into one library while
// keeping them as SEPARATE exports (option i of the plan's sub-decision) —
// they are NOT merged into a single map, because merging would conflate two
// genuinely different domains:
//
//   1. humanizeVerdict()  — backend research verdict/status enums in SNAKE_CASE
//      (e.g. 'D5_NO_GO_RESEARCH_ONLY_GATE', 'NOT_STARTED'). Original vocabulary
//      lived in MissionControl.svelte (KNOWN_VERDICTS + humanize()).
//
//   2. humanizeLifecycle() — run-lifecycle states in lowercase
//      (e.g. 'completed' -> '완료', 'failed' -> '실패', 'running' -> '진행 중').
//      Original vocabulary lived in HistoryRunsTab.svelte (statusLabel()), which
//      now imports humanizeLifecycle() from here instead of keeping a duplicate.
//
// Both helpers only transform the DISPLAYED string. Callers must keep the raw
// backend value for tone/`data-*` decisions (the raw literal is preserved in the
// source, so hand-asserted contract tests are unaffected).
//
// NOT named `statusLabel.ts`: that would collide with the pre-existing,
// semantically-different HistoryRunsTab statusLabel() (lifecycle vocabulary).

// Backend research verdict/status enum -> human-readable Korean label.
// Mirrors MissionControl.svelte's KNOWN_VERDICTS map (kept in sync intentionally).
const KNOWN_VERDICTS: Record<string, string> = {
  D0_D9_EVIDENCE_VISIBLE_MODEL_BUILD_NO_GO: 'D0–D9 증거 확인 · NO-GO',
  D0_D2_DATASET_READY_WATCH_D3_LOCKED: 'D0–D2 준비 · WATCH (D3 잠금)',
  MODEL_BUILD_LOCKED_NO_GO: '모델 빌드 잠금 · NO-GO',
  REVIEW_REQUIRED: '검토 필요',
  WATCH_RESEARCH_ONLY: 'WATCH · 연구 전용',
  NOT_STARTED: '시작 전',
  BLOCKED_INVALID_LATEST_ARTIFACT: '아티팩트 무효 · 잠금',
  BLOCKED_INVALID_CLOSE_SLOT_ARTIFACT: 'close-slot 아티팩트 무효 · 잠금',
  D3_WATCH_RESEARCH_ONLY: 'D3 · WATCH (연구 전용)',
  D4_RESEARCH_ONLY_DIAGNOSTICS: 'D4 · 연구 전용 진단',
  D5_NO_GO_RESEARCH_ONLY_GATE: 'D5 · NO-GO 게이트',
  UNIVERSE_ARTIFACT_SELECTION_FAILED_CLOSED: 'universe 선정 실패 · fail-closed',
  DATASET_ARTIFACT_SELECTION_FAILED_CLOSED: '데이터셋 선정 실패 · fail-closed',
};

// Convert a raw backend verdict/status enum to a human-readable label.
// - Passes through empty/already-human strings unchanged.
// - Falls back to underscore->space for unknown SNAKE_CASE enums.
export function humanizeVerdict(raw: string | null | undefined): string {
  if (raw == null) return '';
  const value = String(raw);
  if (!value) return value;
  const known = KNOWN_VERDICTS[value];
  if (known) return known;
  if (!/^[A-Z0-9_.-]+$/.test(value)) return value; // already a human-written phrase
  return value.replace(/_/g, ' ');
}

// Run-lifecycle state -> human-readable Korean label.
// Reconciled from HistoryRunsTab.svelte's local statusLabel() (now removed).
export function humanizeLifecycle(s: string | null | undefined): string {
  const value = String(s ?? '');
  if (value === 'completed' || value === 'complete' || value === 'success') return '완료';
  if (value === 'failed' || value === 'error') return '실패';
  if (value === 'running' || value === 'active') return '진행 중';
  return value || '미상';
}
