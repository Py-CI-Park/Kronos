import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

test('research workspace offers a catalog and permanent run detail route', async () => {
  // Given
  const workspace = await readFile(new URL('./pages/research/ResearchWorkspace.svelte', import.meta.url), 'utf8');
  const library = await readFile(new URL('./pages/research/ResearchLibraryPage.svelte', import.meta.url), 'utf8');
  const detail = await readFile(new URL('./pages/research/RunDetailPage.svelte', import.meta.url), 'utf8');

  // When / Then
  assert.match(workspace, /data-research-workspace/u);
  assert.match(workspace, /params\.get\('run'\)/u);
  assert.match(workspace, /params\.set\('run'/u);
  assert.match(library, /data-research-library/u);
  assert.match(library, /실패와 NO-GO도 숨기지 않습니다/u);
  assert.match(detail, /data-run-detail/u);
  assert.match(detail, /detail\.evidence_scope/u);
  assert.match(detail, /Artifacts/u);
  assert.match(detail, /TelemetryCharts/u);
  assert.match(detail, /관측 결과 시각화/u);
  assert.match(detail, /ObservedOutcomeCharts/u);
  assert.match(detail, /직접 관측 결과 요약/u);
  assert.match(detail, /REPRODUCTION_ONLY_VALIDATION_CONSUMED/u);
  assert.match(detail, /REPRODUCTION_MISMATCH_VALIDATION_CONSUMED/u);
  assert.match(detail, /HISTORICAL TEST CONTAMINATED/u);
  assert.match(detail, /Fresh OOS만 사용/u);
});

test('research library ignores stale overlapping refresh responses', async () => {
  const library = await readFile(new URL('./pages/research/ResearchLibraryPage.svelte', import.meta.url), 'utf8');

  assert.match(library, /requestGeneration/u);
  assert.match(library, /currentRequest !== requestGeneration/u);
});

test('unified shell renders the research workspace instead of the legacy stepper', async () => {
  // Given
  const shell = await readFile(new URL('./V6Shell.svelte', import.meta.url), 'utf8');

  // When / Then
  assert.match(shell, /<ResearchWorkspace/u);
  assert.equal(shell.includes("page.id === 'research'}<RLWorkspace"), false);
});
