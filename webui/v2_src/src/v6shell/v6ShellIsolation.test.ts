import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

test('V6 shell uses isolated navigation and main class names', async () => {
  const source = await readFile(new URL('./V6Shell.svelte', import.meta.url), 'utf8');
  const context = await readFile(new URL('./ResearchContext.svelte', import.meta.url), 'utf8');
  const experiment = await readFile(new URL('./pages/ExperimentPage.svelte', import.meta.url), 'utf8');
  const insight = await readFile(new URL('./pages/InsightSymbolPage.svelte', import.meta.url), 'utf8');
  const kronos = await readFile(new URL('./pages/KronosPage.svelte', import.meta.url), 'utf8');
  const stepper = await readFile(new URL('./ProcessStepper.svelte', import.meta.url), 'utf8');

  assert.match(source, /class="v6-sidebar"/u);
  assert.match(source, /class="v6-main"/u);
  assert.doesNotMatch(source, /class="sidebar"/u);
  assert.match(source, /ResearchContext/u);
  assert.match(source, /<ResearchContext \/>/u);
  assert.match(context, /<strong>D6R2<\/strong>/u);
  assert.match(context, /70 \/ 70 EVALUATIONS/u);
  assert.match(context, /TOP-5 SIGNAL FLOOR · NO-GO/u);
  assert.match(context, /NOT_RUN_NO_READ/u);
  assert.match(experiment, /새 사전등록 초안 없음/u);
  assert.match(experiment, /새 feature·horizon·비용·종료 조건/u);
  assert.match(insight, /다른 종목 빠르게 보기/u);
  assert.match(insight, /매수 추천이 아닙니다/u);
  assert.match(kronos, /Kronos 예측 모델 ≠ 강화학습 policy/u);
  assert.match(kronos, /classifyV6ModelStatus/u);
  assert.match(stepper, /max-width: 1180px/u);
  assert.doesNotMatch(stepper, /white-space: nowrap/u);
});
