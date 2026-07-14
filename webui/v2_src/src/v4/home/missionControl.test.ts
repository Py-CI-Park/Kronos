import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';

import type * as MissionControl from './missionControl';

const missionPath = ['.', 'missionControl.ts'].join('/');
const {
  PROMOTION_LOCK_KEYS,
  deriveMissionCards,
  deriveMissionControlModel,
  deriveStatusLocks,
  deriveWorkflowSteps,
  settleMissionControlSources,
}: typeof MissionControl = await import(missionPath);

const missionControlSvelte = readFileSync(new URL('./V4MissionControl.svelte', import.meta.url), 'utf8');

test('mission cards expose exactly six cards in approved visible order', () => {
  const cards = deriveMissionCards({
    dailyProgress: { overall_status: 'WATCH', guardrail: 'RESEARCH_ONLY' },
    closeSlot: { readiness_status: 'NO-GO', run_id: '000045', round_trip_cost_bp: 23 },
    rlRuns: [{ name: '000123', strategy_context: { line: 'rule_mainline', primary_baseline: 'ts_imb', is_reinforcement_learning: false }, verdict: 'NO-GO' }],
    trainingStatus: { status: 'idle' },
    metricsLatest: { runName: 'run-007' },
  });

  assert.deepEqual(cards.map((card) => card.id), [
    'forecast',
    'daily-d0-d9',
    'close-slot',
    'rl-evidence',
    'training-system',
    'unresolved-blockers',
  ]);
  assert.equal(cards.length, 6);
  assert.equal(cards[2].metric, '23bp');
  assert.equal(cards[2].detail, 'source_run_id 000045');
  assert.match(cards[3].metric, /RULE/);
  assert.doesNotMatch(cards[3].metric, /RL experiment/);
});

test('desktop Home card density stays scoped above tablet breakpoint', () => {
  assert.match(missionControlSvelte, /@media \(min-width: 1001px\) \{[\s\S]*?\.home-card \{[\s\S]*?min-height: 128px;[\s\S]*?padding: 10px 12px;[\s\S]*?gap: 4px;/);
  assert.match(missionControlSvelte, /@media \(max-width: 1000px\) \{[\s\S]*?\.cards \{[\s\S]*?grid-template-columns: repeat\(2, minmax\(0, 1fr\)\);/);
  assert.match(missionControlSvelte, /@media \(max-width: 640px\) \{[\s\S]*?\.cards \{[\s\S]*?grid-template-columns: 1fr;/);
});

test('promotion locks use the exact six canonical keys and fail closed when absent', () => {
  const result = deriveStatusLocks(null, { unrelated: 'GO profitable live order ready' });

  assert.deepEqual(PROMOTION_LOCK_KEYS, [
    'promotion_allowed',
    'model_build_allowed',
    'paper_forward_allowed',
    'live_broker_order_allowed',
    'profitability_claim_allowed',
    'go_summary_allowed',
  ]);
  assert.deepEqual(Object.keys(result.states), [...PROMOTION_LOCK_KEYS]);
  assert.equal(result.allLocked, true);
  for (const key of PROMOTION_LOCK_KEYS) {
    assert.equal(result.locks[key], false);
    assert.equal(result.states[key].sourceStatus, 'missing');
  }
});

test('workflow map keeps data to TEST OOS to verdict sequence before chart surfaces', () => {
  const workflow = deriveWorkflowSteps({
    dailyProgress: { overall_status: 'PASS' },
    rlRuns: [{ split_hash: '0000abc', strategy_context: { line: 'RULE', primary_baseline: 'ts_imb' }, verdict: 'NO-GO' }],
  });

  assert.deepEqual(workflow.map((step) => step.marker), ['data', 'split', 'baseline', 'policy', 'TEST OOS', 'verdict']);
  assert.deepEqual(workflow.map((step) => step.id), ['data', 'split', 'baseline', 'policy', 'test_oos', 'verdict']);
  assert.equal(workflow[4].status, 'NOT_RECORDED');
  assert.equal(workflow[5].status, 'NO-GO');
});

test('honesty fallbacks do not invent cost, model status, broker/order/profit, or GO unlocks', () => {
  const model = deriveMissionControlModel({
    closeSlot: { readiness_status: 'READY_FOR_GO', run_id: '000001' },
    rlRuns: [{ name: '000009', strategy_context: { label: 'RL-looking rule name', is_reinforcement_learning: false }, status: 'complete' }],
    rliableStats: { note: 'missing TEST OOS' },
  });

  assert.equal(model.cards.length, 6);
  assert.equal(model.cards.find((card) => card.id === 'close-slot')?.metric, 'NOT_RECORDED');
  assert.equal(model.cards.find((card) => card.id === 'close-slot')?.verdict, 'NO-GO');
  assert.equal(model.cards.find((card) => card.id === 'training-system')?.metric, 'NOT_RECORDED');
  assert.equal(model.cards.find((card) => card.id === 'unresolved-blockers')?.verdict, 'MISSING');
  assert.equal(model.locks.allLocked, true);
  for (const key of PROMOTION_LOCK_KEYS) {
    assert.equal(model.locks.locks[key], false);
  }
});

test('settled Home loading preserves fulfilled sources and source-specific failures', async () => {
  const { inputs, errors } = await settleMissionControlSources(
    {
      dailyProgress: Promise.resolve({ overall_status: 'WATCH', guardrail: 'RESEARCH_ONLY' }),
      closeSlot: Promise.reject(new Error('close down')),
      rlRuns: Promise.resolve({ runs: [{ verdict: 'NO-GO' }] }),
      rlQueue: Promise.reject(new Error('queue down')),
      rliableStats: Promise.resolve({ score_definition: 'IQM TEST OOS' }),
    },
    { trainingStatus: { status: 'idle' }, metricsLatest: { runName: 'run-007' } }
  );

  assert.deepEqual(errors, ['closeSlot: API_UNAVAILABLE (close down)', 'rlQueue: API_UNAVAILABLE (queue down)']);
  assert.deepEqual(inputs.dailyProgress, { overall_status: 'WATCH', guardrail: 'RESEARCH_ONLY' });
  assert.deepEqual(inputs.rlRuns, [{ verdict: 'NO-GO' }]);
  assert.deepEqual(inputs.rliableStats, { score_definition: 'IQM TEST OOS' });
  assert.deepEqual(inputs.trainingStatus, { status: 'idle' });
  assert.deepEqual(inputs.metricsLatest, { runName: 'run-007' });

  const model = deriveMissionControlModel(inputs);
  assert.equal(model.cards.find((card) => card.id === 'daily-d0-d9')?.source, 'LIVE');
  assert.equal(model.cards.find((card) => card.id === 'close-slot')?.source, 'FALLBACK');
  assert.equal(model.cards.find((card) => card.id === 'rl-evidence')?.source, 'LIVE');
  assert.equal(model.cards.find((card) => card.id === 'training-system')?.source, 'LIVE');
  assert.equal(model.locks.allLocked, true);
});

test('card source badges require meaningful rendered evidence instead of empty or sentinel fields', () => {
  const emptyCards = deriveMissionCards({
    dailyProgress: { overall_status: 'CHECKING', guardrail: 'MISSING' },
    closeSlot: { readiness_status: 'NOT_RECORDED', run_id: 'MISSING' },
    rlRuns: [{ verdict: 'NOT_RECORDED', strategy_context: { primary_baseline: 'MISSING', line: 'NOT_RECORDED' } }],
    rliableStats: { score_definition: 'NOT_RECORDED' },
    trainingStatus: { status: 'CHECKING' },
    metricsLatest: { runName: 'NOT_RECORDED' },
  });

  assert.equal(emptyCards.length, 6);
  assert.equal(emptyCards.find((card) => card.id === 'daily-d0-d9')?.source, 'FALLBACK');
  assert.equal(emptyCards.find((card) => card.id === 'close-slot')?.source, 'FALLBACK');
  assert.equal(emptyCards.find((card) => card.id === 'rl-evidence')?.source, 'FALLBACK');
  assert.equal(emptyCards.find((card) => card.id === 'training-system')?.source, 'FALLBACK');

  const variantCards = deriveMissionCards({
    dailyProgress: { overall_status: 'STATUS_UNKNOWN', guardrail: 'CHECKING_SOURCE' },
    closeSlot: { readiness_status: 'ARTIFACT_MISSING', run_id: 'SOURCE_NOT_RECORDED' },
    rlRuns: [{ verdict: 'STATUS_NOT_RECORDED', strategy_context: { primary_baseline: 'BASELINE_UNKNOWN', line: 'LINE_MISSING' } }],
    rliableStats: { score_definition: 'UNKNOWN_SCORE' },
    trainingStatus: { status: 'CHECKING_SOURCE' },
    metricsLatest: { runName: 'RUN_UNKNOWN' },
  });

  assert.equal(variantCards.find((card) => card.id === 'daily-d0-d9')?.source, 'FALLBACK');
  assert.equal(variantCards.find((card) => card.id === 'close-slot')?.source, 'FALLBACK');
  assert.equal(variantCards.find((card) => card.id === 'rl-evidence')?.source, 'FALLBACK');
  assert.equal(variantCards.find((card) => card.id === 'training-system')?.source, 'FALLBACK');

  const declaredCards = deriveMissionCards({
    dailyProgress: { overall_status: 'RECORDED' },
    closeSlot: { readiness_status: 'NO-GO', run_id: '000045' },
    rlRuns: [{ name: '000123', strategy_context: { line: 'rule_mainline', primary_baseline: 'ts_imb' }, verdict: 'NO-GO' }],
    trainingStatus: { readiness: { label: 'idle' } },
    metricsLatest: { runName: 'run-007' },
  });

  assert.equal(declaredCards.find((card) => card.id === 'daily-d0-d9')?.source, 'LIVE');
  assert.equal(declaredCards.find((card) => card.id === 'close-slot')?.source, 'LIVE');
  assert.equal(declaredCards.find((card) => card.id === 'rl-evidence')?.source, 'LIVE');
  assert.equal(declaredCards.find((card) => card.id === 'training-system')?.source, 'LIVE');
  assert.equal(declaredCards.find((card) => card.id === 'close-slot')?.detail, 'source_run_id 000045');
  assert.equal(declaredCards.find((card) => card.id === 'unresolved-blockers')?.source, 'FALLBACK');

  const blockerCards = deriveMissionCards({ dailyProgress: { blockers: ['split not recorded'] } });
  assert.equal(blockerCards.find((card) => card.id === 'unresolved-blockers')?.source, 'DECLARED');
});

test('Home card evidence stays source-grounded and contradiction-safe', () => {
  const splitOnly = deriveMissionCards({ rlRuns: [{ split_hash: '0000abc' }] });
  assert.equal(splitOnly.find((card) => card.id === 'rl-evidence')?.source, 'FALLBACK');

  const closeMissing = deriveMissionCards({
    closeSlot: null,
    rlRuns: [{ name: '000123', cost_bps: 23 }],
  });
  assert.equal(closeMissing.find((card) => card.id === 'close-slot')?.metric, 'NOT_RECORDED');
  assert.equal(closeMissing.find((card) => card.id === 'close-slot')?.detail, 'source_run_id NOT_RECORDED');
  assert.equal(closeMissing.find((card) => card.id === 'close-slot')?.source, 'FALLBACK');

  const conflict = deriveMissionCards({
    rlRuns: [{ strategy_context: { line: 'RULE', is_reinforcement_learning: true, primary_baseline: 'ts_imb' } }],
  });
  assert.match(conflict.find((card) => card.id === 'rl-evidence')?.metric ?? '', /RULE\/RL 충돌/);
  const reverseConflict = deriveMissionCards({
    rlRuns: [{ strategy_context: { line: 'RL', is_reinforcement_learning: false, primary_baseline: 'ts_imb' } }],
  });
  assert.match(reverseConflict.find((card) => card.id === 'rl-evidence')?.metric ?? '', /RULE\/RL 충돌/);

  const definitionOnly = deriveMissionControlModel({
    rlRuns: [{ verdict: 'NO-GO' }],
    rliableStats: { score_definition: 'IQM TEST OOS' },
  });
  assert.equal(definitionOnly.workflow.find((step) => step.id === 'test_oos')?.status, 'NOT_RECORDED');
  assert.equal(definitionOnly.cards.find((card) => card.id === 'rl-evidence')?.detail, 'TEST OOS NOT_RECORDED');
});
test('absence and API error sentinels never produce optimistic LIVE source badges', () => {
  const sentinelCards = deriveMissionCards({
    dailyProgress: { overall_status: 'N/A', guardrail: 'API_UNAVAILABLE' },
    closeSlot: { readiness_status: 'NULL', run_id: 'NONE' },
    rlRuns: [{ verdict: 'NOT_AVAILABLE', strategy_context: { line: 'UNKNOWN', primary_baseline: 'MISSING' } }],
    rliableStats: { error: 'API_UNAVAILABLE' },
  });

  assert.equal(sentinelCards.find((card) => card.id === 'daily-d0-d9')?.source, 'FALLBACK');
  assert.equal(sentinelCards.find((card) => card.id === 'close-slot')?.source, 'FALLBACK');
  assert.equal(sentinelCards.find((card) => card.id === 'rl-evidence')?.source, 'FALLBACK');

  const validCards = deriveMissionCards({
    dailyProgress: { overall_status: 'PASS' },
    closeSlot: { readiness_status: 'NO-GO', run_id: 'run-123' },
    rlRuns: [{ verdict: 'NO-GO', strategy_context: { line: 'RL', primary_baseline: 'ts_imb' } }],
    rliableStats: { error: 'API_UNAVAILABLE' },
  });

  assert.equal(validCards.find((card) => card.id === 'daily-d0-d9')?.source, 'LIVE');
  assert.equal(validCards.find((card) => card.id === 'close-slot')?.source, 'LIVE');
  assert.equal(validCards.find((card) => card.id === 'rl-evidence')?.source, 'LIVE');
});
