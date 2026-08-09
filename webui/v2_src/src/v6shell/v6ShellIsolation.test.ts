import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

test('V6 shell isolates navigation and shows current evidence boundaries', async () => {
  const source = await readFile(new URL('./V6Shell.svelte', import.meta.url), 'utf8');
  const context = await readFile(new URL('./ResearchContext.svelte', import.meta.url), 'utf8');
  const kronos = await readFile(new URL('./pages/KronosPage.svelte', import.meta.url), 'utf8');
  const stepper = await readFile(new URL('./ProcessStepper.svelte', import.meta.url), 'utf8');
  const workspace = await readFile(new URL('./RLWorkspace.svelte', import.meta.url), 'utf8');

  assert.match(source, /<UnifiedSidebar/u);
  assert.match(source, /<SystemStatusRail/u);
  assert.match(source, /class="unified-v6-main"/u);
  assert.doesNotMatch(source, /class="sidebar"/u);
  assert.doesNotMatch(source, /<ResearchContext \/>/u);
  assert.doesNotMatch(source, /style:zoom/u);
  assert.match(context, /<strong>G1–G6<\/strong>/u);
  assert.match(context, /TRAIN 76 · VAL 24 · TEST 23/u);
  assert.match(context, /2,432 TRANSITIONS/u);
  assert.match(context, /DQN\/CQL 20개/u);
  assert.match(context, /CQL TEST 중앙값 -10\.19%/u);
  assert.match(context, /IMPLEMENTED · NO-GO/u);
  assert.match(context, /NOT_RUN_NO_READ/u);
  assert.match(kronos, /Kronos 예측 모델 ≠ 강화학습 정책/u);
  assert.match(kronos, /classifyV6ModelStatus/u);
  assert.match(stepper, /max-width: 1180px/u);
  assert.doesNotMatch(stepper, /white-space: nowrap/u);
  assert.match(workspace, /statusLoading \? 'LOADING'/u);
  assert.doesNotMatch(workspace, /await Promise\.all\(\[getV6Status/u);
});
