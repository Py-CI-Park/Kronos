import assert from 'node:assert/strict';
import { test } from 'bun:test';
import { readFile } from 'node:fs/promises';

const root = new URL('./', import.meta.url);

test('live training page separates recorded history from a currently changing event file', async () => {
  const source = await readFile(new URL('pages/live/LiveTrainingPage.svelte', root), 'utf8');

  assert.match(source, /FOLLOWING_FILE/u);
  assert.match(source, /HISTORICAL_SNAPSHOT/u);
  assert.match(source, /실시간 스트림이 아님/u);
  assert.match(source, /실행 판정/u);
  assert.match(source, /setInterval/u);
  assert.match(source, /TelemetryCharts/u);
  assert.match(source, /ActionTimeline/u);
});

test('telemetry charts expose reward equity drawdown loss and exploration', async () => {
  const source = await readFile(new URL('pages/live/TelemetryCharts.svelte', root), 'utf8');

  for (const metric of ['누적 보상', '에쿼티', '낙폭', '손실', '탐색률']) assert.match(source, new RegExp(metric, 'u'));
  assert.match(source, /EChartsRenderer/u);
  assert.match(source, /caption=/u);
});

test('action timeline exposes the full observed event sequence as an accessible table', async () => {
  const source = await readFile(new URL('pages/live/ActionTimeline.svelte', root), 'utf8');

  assert.match(source, /전체 행동 event 표/u);
  assert.match(source, /<table/u);
  assert.match(source, /<th scope="col">기록 시각<\/th>/u);
  assert.match(source, /<th scope="col">행동<\/th>/u);
});

test('unified shell replaces the legacy training stepper with the focused live page', async () => {
  const shell = await readFile(new URL('V6Shell.svelte', root), 'utf8');

  assert.match(shell, /import LiveTrainingPage/u);
  assert.match(shell, /page\.id === 'live'\}<LiveTrainingPage/u);
  assert.doesNotMatch(shell, /page\.id === 'live'\}<RLWorkspace/u);
});
