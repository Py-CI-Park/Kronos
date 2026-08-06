import assert from 'node:assert/strict';
import { test } from 'bun:test';
import { readFile } from 'node:fs/promises';

const root = new URL('./', import.meta.url);

test('evaluation compares only runs in the same evidence lane without ranking claims', async () => {
  const source = await readFile(new URL('pages/evaluation/EvaluationWorkspace.svelte', root), 'utf8');

  assert.match(source, /sameLaneRuns/u);
  assert.match(source, /같은 lane/u);
  assert.match(source, /순위가 아님/u);
  assert.match(source, /ComparisonCharts/u);
  assert.match(source, /NO-GO/u);
});

test('daily close process uses post-close next-open and reduced-motion safeguards', async () => {
  const source = await readFile(new URL('pages/evaluation/DailyCloseProcessFlow.svelte', root), 'utf8');

  for (const token of ['POST_CLOSE_NEXT_OPEN', 'D일 공식 종가', 'PIT·available-at', '6천만원', 'D+1 시가', '0.230%', 'reward·NAV', 'artifact']) assert.ok(source.includes(token));
  assert.match(source, /prefers-reduced-motion/u);
  assert.match(source, /aria-current/u);
  assert.match(source, /class="step-button"/u);
  assert.match(source, /단계 상세/u);
});

test('unified shell maps evaluation to the focused workspace', async () => {
  const shell = await readFile(new URL('V6Shell.svelte', root), 'utf8');

  assert.match(shell, /import EvaluationWorkspace/u);
  assert.match(shell, /page\.id === 'evaluation'\}<EvaluationWorkspace/u);
  assert.doesNotMatch(shell, /page\.id === 'evaluation'\}<RLWorkspace/u);
});
