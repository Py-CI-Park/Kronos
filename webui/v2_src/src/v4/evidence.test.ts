import assert from 'node:assert/strict';
import { test } from 'node:test';

import type * as Evidence from './evidence';

const evidencePath = ['.', 'evidence.ts'].join('/');
const {
  PROMOTION_LOCK_KEYS,
  adaptEvidenceIdentity,
  adaptMetricValue,
  adaptPromotionLocks,
  adaptRunEvidence,
}: typeof Evidence = await import(evidencePath);

const ALL_FALSE = {
  promotion_allowed: false,
  model_build_allowed: false,
  paper_forward_allowed: false,
  live_broker_order_allowed: false,
  profitability_claim_allowed: false,
  go_summary_allowed: false,
};

const ALL_TRUE = {
  promotion_allowed: true,
  model_build_allowed: true,
  paper_forward_allowed: true,
  live_broker_order_allowed: true,
  profitability_claim_allowed: true,
  go_summary_allowed: true,
};

function assertAllLocks(
  result: Evidence.PromotionLocksResult,
  expected: boolean,
  sourceStatus: Evidence.LockSourceStatus,
): void {
  const expectedReason = expected ? 'UNLOCKED_BY_SOURCE' : 'LOCKED_BY_SOURCE';
  assert.deepEqual(result.locks, Object.fromEntries(PROMOTION_LOCK_KEYS.map((key) => [key, expected])));
  for (const key of PROMOTION_LOCK_KEYS) {
    assert.equal(result.states[key].allowed, expected);
    assert.equal(result.states[key].sourceStatus, sourceStatus);
    assert.equal(result.states[key].reason, sourceStatus === 'declared' ? expectedReason : 'LOCK_SOURCE_INVALID');
  }
}

test('promotion locks always expose the exact six keys and fail closed when missing', () => {
  const result = adaptPromotionLocks({});

  assert.deepEqual(PROMOTION_LOCK_KEYS, [
    'promotion_allowed',
    'model_build_allowed',
    'paper_forward_allowed',
    'live_broker_order_allowed',
    'profitability_claim_allowed',
    'go_summary_allowed',
  ]);
  assert.deepEqual(result.locks, ALL_FALSE);
  assert.deepEqual(Object.keys(result.states), [...PROMOTION_LOCK_KEYS]);
  assert.equal(result.allLocked, true);
  assert.equal(result.hasInvalidSource, false);
  for (const key of PROMOTION_LOCK_KEYS) {
    assert.deepEqual(result.states[key], {
      key,
      allowed: false,
      sourceStatus: 'missing',
      reason: 'LOCK_SOURCE_MISSING',
    });
  }
});

test('declared boolean promotion locks pass through without optimistic inference', () => {
  const result = adaptPromotionLocks(ALL_TRUE);

  assert.deepEqual(result.locks, ALL_TRUE);
  assert.equal(result.allLocked, false);
  assert.equal(result.hasInvalidSource, false);
  for (const key of PROMOTION_LOCK_KEYS) {
    assert.equal(result.states[key].sourceStatus, 'declared');
    assert.equal(result.states[key].reason, 'UNLOCKED_BY_SOURCE');
  }
});

test('null and non-boolean promotion locks stay locked with missing or invalid source reasons', () => {
  const result = adaptPromotionLocks({
    promotion_allowed: null,
    model_build_allowed: 'true',
    paper_forward_allowed: 1,
    live_broker_order_allowed: {},
    profitability_claim_allowed: [],
    go_summary_allowed: undefined,
  });

  assert.deepEqual(result.locks, ALL_FALSE);
  assert.equal(result.states.promotion_allowed.sourceStatus, 'missing');
  assert.equal(result.states.go_summary_allowed.reason, 'LOCK_SOURCE_MISSING');
  assert.equal(result.states.model_build_allowed.sourceStatus, 'invalid');
  assert.equal(result.states.paper_forward_allowed.reason, 'LOCK_SOURCE_INVALID');
  assert.equal(result.hasInvalidSource, true);
});

test('canonical top-level lock keys win over nested legacy containers and profit alias', () => {
  const result = adaptPromotionLocks({
    promotion_allowed: true,
    profitability_claim_allowed: false,
    profit_claim_allowed: true,
    false_locks: { promotion_allowed: false, model_build_allowed: true },
    research_locks: { paper_forward_allowed: true },
    guardrail_flags: { live_broker_order_allowed: true, go_summary_allowed: false },
  });

  assert.equal(result.locks.promotion_allowed, true);
  assert.equal(result.locks.model_build_allowed, true);
  assert.equal(result.locks.paper_forward_allowed, true);
  assert.equal(result.locks.live_broker_order_allowed, true);
  assert.equal(result.locks.profitability_claim_allowed, false);
  assert.equal(result.locks.go_summary_allowed, false);
  assert.equal(result.states.profitability_claim_allowed.reason, 'LOCKED_BY_SOURCE');
});

test('known nested lock containers are consumed, but non-boolean nested values are invalid', () => {
  const result = adaptPromotionLocks({
    false_locks: ['promotion_allowed'],
    research_only_locks: { model_build_allowed: false },
    research_locks: { paper_forward_allowed: true, live_broker_order_allowed: 'no' },
    guardrail_flags: { profitability_claim_allowed: false, go_summary_allowed: true },
  });

  assert.equal(result.locks.promotion_allowed, false);
  assert.equal(result.states.promotion_allowed.sourceStatus, 'declared');
  assert.equal(result.states.promotion_allowed.reason, 'LOCKED_BY_SOURCE');
  assert.equal(result.locks.paper_forward_allowed, true);
  assert.equal(result.locks.live_broker_order_allowed, false);
  assert.equal(result.states.live_broker_order_allowed.sourceStatus, 'invalid');
  assert.equal(result.locks.go_summary_allowed, true);
});

test('positive metric-like values and names never unlock missing promotion locks', () => {
  const result = adaptPromotionLocks({
    chart: { profitability_claim_allowed: true },
    pnl: 99,
    sharpe: 3,
    name: 'GO profitable RL live broker order ready',
    value: 23,
  });

  assert.deepEqual(result.locks, ALL_FALSE);
  assert.equal(result.allLocked, true);
});

test('evidence identity preserves string ids, valid hashes, source paths, endpoints, and computes age', () => {
  const modifiedAt = new Date(Date.now() - 65_000).toISOString();
  const identity = adaptEvidenceIdentity(
    {
      id: '000123',
      artifact_type: 'checkpoint',
      label: 'Run 000123',
      file_path: '../unsafe/preserved.txt',
      sha256: 'a'.repeat(64),
      modified_at: modifiedAt,
      status: 'completed',
    },
    { source_endpoint: '/api/local/evidence' },
  );

  assert.equal(identity.id, '000123');
  assert.equal(identity.kind, 'checkpoint');
  assert.equal(identity.label, 'Run 000123');
  assert.equal(identity.source_endpoint, '/api/local/evidence');
  assert.equal(identity.source_path, '../unsafe/preserved.txt');
  assert.equal(identity.sha256, 'a'.repeat(64));
  assert.equal(identity.modified_at, modifiedAt);
  assert.equal(typeof identity.artifact_age_seconds, 'number');
  assert.ok((identity.artifact_age_seconds ?? 0) >= 60);
  assert.equal(identity.freshness_status, 'COMPLETED');
});

test('evidence identity uses approved fallbacks for missing or invalid hash/time/age', () => {
  const identity = adaptEvidenceIdentity({ id: '', sha256: 'not-a-hash', modified_at: 'tomorrowish' });

  assert.equal(identity.id, 'MISSING_ID');
  assert.equal(identity.kind, 'unknown_evidence');
  assert.equal(identity.label, '이름 없음');
  assert.equal(identity.source_endpoint, 'endpoint_unknown');
  assert.equal(identity.source_path, 'PATH_NOT_RECORDED');
  assert.equal(identity.sha256, 'HASH_NOT_RECORDED');
  assert.equal(identity.modified_at, 'TIME_NOT_RECORDED');
  assert.equal(identity.artifact_age_seconds, null);
  assert.equal(identity.freshness_status, 'MISSING');
});
test('freshness normalization allows only approved non-optimistic states', () => {
  assert.equal(adaptEvidenceIdentity({ status: 'running', artifact_age_seconds: 1 }).freshness_status, 'RUNNING');
  assert.equal(adaptEvidenceIdentity({ status: 'complete' }).freshness_status, 'COMPLETED');
  assert.equal(adaptEvidenceIdentity({ status: 'stale' }).freshness_status, 'STALE');
  assert.equal(adaptEvidenceIdentity({ status: 'replayed' }).freshness_status, 'REPLAY');
  assert.equal(adaptEvidenceIdentity({ status: 'idle' }).freshness_status, 'IDLE');

  assert.equal(adaptEvidenceIdentity({ status: 'ACTIVE' }).freshness_status, 'MISSING');
  assert.equal(adaptEvidenceIdentity({ status: 'READY' }).freshness_status, 'MISSING');
  assert.equal(adaptEvidenceIdentity({ status: 'LIVE' }).freshness_status, 'MISSING');
  assert.equal(adaptEvidenceIdentity({ status: 'surprisingly_good' }).freshness_status, 'MISSING');
});
test('running identity freshness requires known artifact age', () => {
  const unknownAge = adaptEvidenceIdentity({ status: 'RUNNING' });
  const knownAge = adaptEvidenceIdentity({ status: 'RUNNING', artifact_age_seconds: 0 });

  assert.equal(unknownAge.artifact_age_seconds, null);
  assert.equal(unknownAge.freshness_status, 'MISSING');
  assert.equal(knownAge.artifact_age_seconds, 0);
  assert.equal(knownAge.freshness_status, 'RUNNING');
});


test('run evidence preserves RULE versus RL strictly without deriving RL from names', () => {
  const ruleRun = adaptRunEvidence({
    run_id: '000045',
    strategy_context: { line: 'RULE', is_reinforcement_learning: false, strategy_label: 'RL-looking label' },
    name: 'rl_experiment_named_rule',
    status: 'completed',
  });

  assert.equal(ruleRun.run_id, '000045');
  assert.equal(ruleRun.line, 'RULE');
  assert.equal(ruleRun.is_reinforcement_learning, false);
  assert.equal(ruleRun.strategy_label, 'RL-looking label');
  assert.equal(ruleRun.lifecycle, 'COMPLETED');
  assert.equal(ruleRun.verdict, 'NO-GO/UNKNOWN_BLOCKED');
});

test('missing run lifecycle never becomes LIVE and blockers are deduped with fallback only when absent', () => {
  const missing = adaptRunEvidence({ blocking_reasons: ['NO_OOS', 'NO_OOS', 7, '7'] });

  assert.equal(missing.lifecycle, 'MISSING');
  assert.notEqual(missing.lifecycle, 'LIVE');
  assert.deepEqual(missing.blocking_reasons, ['NO_OOS', '7']);
  assert.deepEqual(missing.promotion_locks.locks, ALL_FALSE);

  const absent = adaptRunEvidence({});
  assert.deepEqual(absent.blocking_reasons, ['BLOCKERS_NOT_RECORDED']);
});
test('raw LIVE, ACTIVE, READY, and profitable run statuses fail closed for lifecycle and verdict', () => {
  for (const status of ['LIVE', 'ACTIVE', 'READY', 'profitable']) {
    const run = adaptRunEvidence({ status });

    assert.equal(run.lifecycle, 'MISSING');
    assert.equal(run.verdict, 'NO-GO/UNKNOWN_BLOCKED');
  }
});
test('run lifecycle accepts primitive and nested object variants without object-string artifacts', () => {
  assert.equal(adaptRunEvidence({ lifecycle: 'completed' }).lifecycle, 'COMPLETED');
  assert.equal(adaptRunEvidence({ lifecycle: { status: 'replayed' } }).lifecycle, 'REPLAY');
  assert.equal(adaptRunEvidence({ summary: { status: 'stale' } }).lifecycle, 'STALE');
  assert.equal(
    adaptEvidenceIdentity({ lifecycle: { status: 'completed' } }).freshness_status,
    'COMPLETED',
  );
  assert.equal(
    adaptRunEvidence({ lifecycle: { state: 'CONFLICT_BLOCKED' }, summary: { status: 'completed' } }).lifecycle,
    'CONFLICT_BLOCKED',
  );

  const malformed = adaptRunEvidence({
    lifecycle: { status: { unexpected: 'completed' } },
    status: 'completed',
  });

  assert.equal(malformed.lifecycle, 'MISSING');
  assert.notEqual(malformed.lifecycle, '[object Object]');
});

test('run evidence extracts nested summary and strategy wrappers with conservative provenance', () => {
  const run = adaptRunEvidence({
    data: {
      name: '000123',
      artifact_type: 'opening_30m_rl_workflow',
      lifecycle: { status: 'completed' },
      summary: {
        strategy_context: {
          line: 'supervised_gate',
          is_reinforcement_learning: false,
          label: '감독 게이트 000123',
          primary_baseline: 'rule_23bp',
        },
        cost_bps: 23,
        seed: '000007',
        split: 'train/test/oos',
        split_hash: 'c'.repeat(64),
        prereg_doc: 'docs/prereg.md',
        verdict: 'NO-GO_RESEARCH_ONLY',
      },
    },
  });

  assert.equal(run.run_id, '000123');
  assert.equal(run.line, 'supervised');
  assert.equal(run.is_reinforcement_learning, false);
  assert.equal(run.strategy_label, '감독 게이트 000123');
  assert.equal(run.baseline_label, 'rule_23bp');
  assert.equal(run.cost_bps, 23);
  assert.equal(run.seed, '000007');
  assert.equal(run.split, 'train/test/oos');
  assert.equal(run.split_hash, 'c'.repeat(64));
  assert.equal(run.prereg_doc, 'docs/prereg.md');
  assert.equal(run.lifecycle, 'COMPLETED');
  assert.equal(run.verdict, 'NO-GO_RESEARCH_ONLY');
});

test('explicit false zero and empty strategy values are not overwritten by wrapper fallbacks', () => {
  const run = adaptRunEvidence({
    run_id: '000000',
    cost_bps: 0,
    strategy_context: {
      line: 'rule_mainline',
      is_reinforcement_learning: false,
      label: '',
      primary_baseline: '',
    },
    summary: {
      strategy_context: {
        line: 'rl_experiment',
        is_reinforcement_learning: true,
        label: 'optimistic fallback',
        primary_baseline: 'optimistic baseline',
      },
      cost_bps: 23,
    },
    promotion_locks: ALL_FALSE,
  });

  assert.equal(run.run_id, '000000');
  assert.equal(run.line, 'RULE');
  assert.equal(run.is_reinforcement_learning, false);
  assert.equal(run.strategy_label, '');
  assert.equal(run.baseline_label, '');
  assert.equal(run.cost_bps, 0);
  assert.deepEqual(run.promotion_locks.locks, ALL_FALSE);
});

test('unknown optimistic lifecycle fails closed while verdict never uses optimistic fallback', () => {
  const run = adaptRunEvidence({
    lifecycle: { status: 'LIVE' },
    status: 'completed',
    verdict: 'READY_FOR_GO',
    summary: { verdict: 'NO-GO_RESEARCH_ONLY' },
    blocking_reasons: [],
  });

  assert.equal(run.lifecycle, 'MISSING');
  assert.equal(run.verdict, 'NO-GO_RESEARCH_ONLY');
  assert.deepEqual(run.blocking_reasons, ['BLOCKERS_NOT_RECORDED']);
});

test('run verdict ignores lifecycle status but preserves explicit conservative verdict and readiness fields', () => {
  const nestedNoGo = adaptRunEvidence({
    status: 'completed',
    detail: { verdict: 'NO-GO_RESEARCH_ONLY' },
  });
  const topLevelNoGo = adaptRunEvidence({
    lifecycle: 'READY',
    verdict: 'NO-GO_RESEARCH_ONLY',
    detail: { verdict: 'WATCH_RESEARCH_ONLY' },
  });
  const readinessNoGo = adaptRunEvidence({
    status: 'ACTIVE',
    detail: { readiness_status: 'D5_NO_GO_RESEARCH_ONLY_GATE' },
  });

  assert.equal(nestedNoGo.lifecycle, 'COMPLETED');
  assert.equal(nestedNoGo.verdict, 'NO-GO_RESEARCH_ONLY');
  assert.equal(topLevelNoGo.lifecycle, 'MISSING');
  assert.equal(topLevelNoGo.verdict, 'NO-GO_RESEARCH_ONLY');
  assert.equal(readinessNoGo.lifecycle, 'MISSING');
  assert.equal(readinessNoGo.verdict, 'D5_NO_GO_RESEARCH_ONLY_GATE');
});
test('punctuation-separated optimistic verdict and readiness values are denied while NO-GO is preserved', () => {
  assert.equal(adaptRunEvidence({ verdict: 'GO/LIVE' }).verdict, 'NO-GO/UNKNOWN_BLOCKED');
  assert.equal(adaptRunEvidence({ readiness: 'READY:LIVE' }).verdict, 'NO-GO/UNKNOWN_BLOCKED');
  assert.equal(adaptRunEvidence({ detail: { readiness_status: 'PASS.OK' } }).verdict, 'NO-GO/UNKNOWN_BLOCKED');
  assert.equal(adaptRunEvidence({ verdict: 'NO-GO/RESEARCH_ONLY' }).verdict, 'NO-GO/RESEARCH_ONLY');
});
test('domain-prefixed optimistic verdict tokens are denied while conservative NO-GO controls pass', () => {
  assert.equal(adaptRunEvidence({ verdict: 'D5_GO' }).verdict, 'NO-GO/UNKNOWN_BLOCKED');
  assert.equal(adaptRunEvidence({ readiness: 'MODEL_BUILD_READY' }).verdict, 'NO-GO/UNKNOWN_BLOCKED');
  assert.equal(adaptRunEvidence({ detail: { readiness_status: 'PAPER_FORWARD_GO' } }).verdict, 'NO-GO/UNKNOWN_BLOCKED');
  assert.equal(adaptRunEvidence({ detail: { verdict: 'D5_NO_GO_RESEARCH_ONLY_GATE' } }).verdict, 'D5_NO_GO_RESEARCH_ONLY_GATE');
  assert.equal(adaptRunEvidence({ verdict: 'NO-GO/RESEARCH_ONLY' }).verdict, 'NO-GO/RESEARCH_ONLY');
});


test('23bp cost fallback is used only when explicitly declared and nonnegative', () => {
  const undeclared = adaptRunEvidence({ run_id: 'costless' });
  const declared = adaptRunEvidence({ run_id: 'declared' }, { declaredDefaultCostBps: 23 });
  const explicitZero = adaptRunEvidence({ run_id: 'zero', cost_bps: 0 }, { declaredDefaultCostBps: 23 });
  const negativeExplicit = adaptRunEvidence({ run_id: 'negative', cost_bps: -1 });
  const negativeDefault = adaptRunEvidence({ run_id: 'negative-default' }, { declaredDefaultCostBps: -23 });
  const negativeExplicitWithDefault = adaptRunEvidence(
    { run_id: 'negative-with-default', cost_bps: -1 },
    { declaredDefaultCostBps: 23 },
  );

  assert.equal(undeclared.cost_bps, null);
  assert.equal(declared.cost_bps, 23);
  assert.equal(explicitZero.cost_bps, 0);
  assert.equal(negativeExplicit.cost_bps, null);
  assert.equal(negativeDefault.cost_bps, null);
  assert.equal(negativeExplicitWithDefault.cost_bps, null);
});


test('run evidence adapts nested locks and legacy profitability alias fail-closed', () => {
  const run = adaptRunEvidence({
    promotion_locks: {
      promotion_allowed: true,
      profit_claim_allowed: true,
      live_broker_order_allowed: null,
      guardrail_flags: { go_summary_allowed: true },
    },
  });

  assert.equal(run.promotion_locks.locks.promotion_allowed, true);
  assert.equal(run.promotion_locks.locks.profitability_claim_allowed, true);
  assert.equal(run.promotion_locks.states.live_broker_order_allowed.sourceStatus, 'missing');
  assert.equal(run.promotion_locks.locks.go_summary_allowed, true);
});

test('run promotion locks keep root false ahead of nested true for all six keys', () => {
  const run = adaptRunEvidence({
    promotion_locks: ALL_FALSE,
    payload: { promotion_locks: ALL_TRUE },
    summary: { promotion_locks: ALL_TRUE },
    detail: { locks: ALL_TRUE },
    risk_policy: { safety_locks: ALL_TRUE },
  });

  assertAllLocks(run.promotion_locks, false, 'declared');
  assert.equal(run.promotion_locks.allLocked, true);
  assert.equal(run.promotion_locks.hasInvalidSource, false);
});

test('run promotion locks keep wrapper direct false ahead of container true for all six keys', () => {
  const run = adaptRunEvidence({
    payload: {
      ...ALL_FALSE,
      promotion_locks: ALL_TRUE,
      locks: ALL_TRUE,
      safety_locks: ALL_TRUE,
    },
  });

  assertAllLocks(run.promotion_locks, false, 'declared');
  assert.equal(run.promotion_locks.allLocked, true);
  assert.equal(run.promotion_locks.hasInvalidSource, false);
});

test('run promotion locks keep invalid root sources ahead of nested true for all six keys', () => {
  const invalidRootLocks = Object.fromEntries(PROMOTION_LOCK_KEYS.map((key) => [key, 'true']));
  const run = adaptRunEvidence({
    ...invalidRootLocks,
    summary: { promotion_locks: ALL_TRUE },
  });

  assertAllLocks(run.promotion_locks, false, 'invalid');
  assert.equal(run.promotion_locks.allLocked, true);
  assert.equal(run.promotion_locks.hasInvalidSource, true);
});

test('run promotion locks accept legitimate nested false when root authority is absent for all six keys', () => {
  const run = adaptRunEvidence({
    summary: { promotion_locks: { promotion_allowed: false, model_build_allowed: false } },
    detail: { locks: { paper_forward_allowed: false, live_broker_order_allowed: false } },
    risk_policy: {
      safety_locks: { profitability_claim_allowed: false, go_summary_allowed: false },
    },
  });

  assertAllLocks(run.promotion_locks, false, 'declared');
  assert.equal(run.promotion_locks.allLocked, true);
  assert.equal(run.promotion_locks.hasInvalidSource, false);
});

test('invalid or missing split hashes use the split-specific fallback', () => {
  assert.equal(adaptRunEvidence({ split_hash: 'not-a-hash' }).split_hash, 'SPLIT_HASH_NOT_RECORDED');
  assert.equal(adaptRunEvidence({}).split_hash, 'SPLIT_HASH_NOT_RECORDED');
  assert.equal(adaptRunEvidence({ split_hash: 'b'.repeat(64) }).split_hash, 'b'.repeat(64));
});


test('metric values preserve units, source, precision, and do not coerce percent or zero', () => {
  const metric = adaptMetricValue(
    { value: 0, unit: 'bps', source: '/api/metrics', precision: 4, kind: 'cost' },
    { unit: 'raw ratio' },
  );

  assert.equal(metric.value, 0);
  assert.equal(metric.kind, 'cost');
  assert.equal(metric.unit, 'raw ratio');
  assert.equal(metric.source, '/api/metrics');
  assert.equal(metric.precision, 4);
  assert.equal(metric.availability, 'RECORDED');
});

test('null and nonfinite metric values render as null with NOT_RECORDED availability', () => {
  assert.deepEqual(adaptMetricValue({ value: null, unit: '%' }), {
    value: null,
    kind: 'KIND_NOT_RECORDED',
    unit: '%',
    availability: 'NOT_RECORDED',
    source: 'endpoint_unknown',
    precision: null,
  });

  assert.equal(adaptMetricValue({ value: Number.POSITIVE_INFINITY }).value, null);
  assert.equal(adaptMetricValue(Number.NaN).availability, 'NOT_RECORDED');
});

test('metric availability preserves explicit inapplicable null but never records null optimistically', () => {
  const inapplicable = adaptMetricValue(null, { availability: 'INAPPLICABLE', kind: 'turnover', unit: 'shares' });
  const forcedRecordedNull = adaptMetricValue({ value: undefined }, { availability: 'RECORDED' });
  const finiteInapplicable = adaptMetricValue(1, { availability: 'INAPPLICABLE' });

  assert.equal(inapplicable.value, null);
  assert.equal(inapplicable.availability, 'INAPPLICABLE');
  assert.equal(inapplicable.kind, 'turnover');
  assert.equal(inapplicable.unit, 'shares');
  assert.equal(forcedRecordedNull.availability, 'NOT_RECORDED');
  assert.equal(finiteInapplicable.availability, 'INAPPLICABLE');
});
