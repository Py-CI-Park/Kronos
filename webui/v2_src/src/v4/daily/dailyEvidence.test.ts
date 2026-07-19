import assert from 'node:assert/strict';
import { test } from 'node:test';
import type * as DailyEvidence from './dailyEvidence';

const evidencePath = ['./dailyEvidence.ts'].join('/');
const {
  DAILY_MISSING,
  DAILY_NO_GO,
  DAILY_NOT_RECORDED,
  adaptDailyResearchEvidence,
}: typeof DailyEvidence = await import(evidencePath);

test('canonical close-slot authority wins before smoke artifacts', () => {
  const evidence = adaptDailyResearchEvidence(
    { mode: 'daily', overall_status: 'smoke-ready', guardrail: 'read-only', stages: [] },
    {
      status: 'PASS',
      artifact_status: 'validated',
      lineage_validation_status: 'validated',
      dashboard_validation_status: 'validated',
      run_id: '000123',
      latest_selection: { split: 'test', source_run_id: '000123' },
      false_locks: {
        promotion_allowed: false,
        model_build_allowed: false,
        paper_forward_allowed: false,
        live_broker_order_allowed: false,
        profitability_claim_allowed: false,
        go_summary_allowed: false,
      },
    },
    { status: 'smoke', run_id: 'smoke-1' },
  );

  assert.equal(evidence.authority.level, 'canonical');
  assert.equal(evidence.authority.source, 'closeSlotLatest');
  assert.equal(evidence.sourceRunId, '000123');
});

test('missing latest_selection fails closed without optimistic TEST OOS', () => {
  const evidence = adaptDailyResearchEvidence(null, { status: 'PASS', artifact_status: 'validated' }, null);

  assert.equal(evidence.latestSelection, DAILY_MISSING);
  assert.equal(evidence.sourceRunId, DAILY_MISSING);
  assert.equal(evidence.testOosStatus, DAILY_NO_GO);
});
test('partial validation and registered-only registry never become canonical', () => {
  const artifactOnly = adaptDailyResearchEvidence(null, {
    status: 'PASS',
    artifact_status: 'validated',
  }, null);
  const registeredOnly = adaptDailyResearchEvidence(null, null, {
    status: 'registered',
    run_id: 'registry-1',
  });

  assert.notEqual(artifactOnly.authority.level, 'canonical');
  assert.notEqual(registeredOnly.authority.level, 'canonical');
  assert.equal(registeredOnly.authority.level, 'declared');
});

test('zero TEST/OOS split counts remain NO-GO', () => {
  const evidence = adaptDailyResearchEvidence(null, {
    replay_summary: { split_counts: { test: 0, oos: 0 } },
  }, null);

  assert.equal(evidence.testOosStatus, DAILY_NO_GO);
});


test('close-slot malformed or missing evidence renders NO-GO blockers and missing authority', () => {
  const evidence = adaptDailyResearchEvidence(null, { status: 'malformed', artifact_status: 'unknown' }, null);

  assert.notEqual(evidence.authority.level, 'canonical');
  assert.equal(evidence.testOosStatus, DAILY_NO_GO);
  assert.deepEqual(evidence.blockers, [DAILY_NO_GO]);
});

test('exact six false locks fail closed through the shared V4 promotion-lock adapter', () => {
  const evidence = adaptDailyResearchEvidence(null, {
    false_locks: {
      promotion_allowed: false,
      model_build_allowed: false,
      paper_forward_allowed: false,
      live_broker_order_allowed: false,
      profitability_claim_allowed: false,
      go_summary_allowed: false,
    },
  }, null);

  assert.equal(Object.keys(evidence.promotionLocks.locks).length, 6);
  assert.equal(evidence.promotionLocks.allLocked, true);
  assert.deepEqual(Object.values(evidence.promotionLocks.locks), [false, false, false, false, false, false]);
  assert.equal(evidence.promotionLocks.states.promotion_allowed.sourceStatus, 'declared');
});

test('declared 23bp is exact while missing cost stays missing', () => {
  const declared = adaptDailyResearchEvidence(null, { round_trip_cost_bp: 23 }, null);
  const missing = adaptDailyResearchEvidence(null, {}, null);

  assert.equal(declared.roundTripCost.status, 'DECLARED_23BP');
  assert.equal(declared.roundTripCost.valueBp, 23);
  assert.equal(missing.roundTripCost.status, 'MISSING');
  assert.equal(missing.roundTripCost.valueBp, null);
});

test('0bp and 46bp cost controls render only when declared', () => {
  const declared = adaptDailyResearchEvidence(null, { cost_sensitivity_bp: [0, 23, 46] }, null);
  const incomplete = adaptDailyResearchEvidence(null, { cost_sensitivity_bp: [23] }, null);
  const missing = adaptDailyResearchEvidence(null, {}, null);

  assert.equal(declared.costControls.status, 'DECLARED_0_46');
  assert.equal(declared.costControls.label, '0/23/46bp');
  assert.equal(incomplete.costControls.status, 'INCOMPLETE');
  assert.equal(missing.costControls.status, 'MISSING');
});
test('max-only slot controls remain incomplete without synthesizing zero', () => {
  const evidence = adaptDailyResearchEvidence(null, { max_slot_count: 10 }, null);

  assert.equal(evidence.slotControls.declared, false);
  assert.equal(evidence.slotControls.status, 'INCOMPLETE');
  assert.equal(evidence.slotControls.selected, null);
  assert.equal(evidence.slotControls.max, 10);
  assert.equal(evidence.slotControls.label, `${DAILY_NOT_RECORDED}/10`);
  assert.equal(evidence.slotControls.label.startsWith('0/'), false);
});

test('leading-zero source run and code/hash strings are preserved without numeric coercion', () => {
  const evidence = adaptDailyResearchEvidence(null, {
    run_id: '000777',
    latest_selection: { split: 'test', source_run_id: '000001', seed: 7 },
    dataset_lineage: { split_hash: '000abc', code: '005930' },
  }, { run_id: '000999', data_hash: '000hash' });

  assert.equal(evidence.sourceRunId, '000001');
  assert.equal(evidence.splitHash, '000abc');
  assert.equal(evidence.sourceCode, '005930');
  assert.equal(evidence.seed, '7');
});

test('stale and malformed inputs render stale/not-recorded instead of READY or GO', () => {
  const evidence = adaptDailyResearchEvidence(
    { mode: 'daily', overall_status: 'RUNNING', guardrail: 'read-only', stages: [] },
    { data_recency: { is_today: false }, latest_selection: { split: 'train' }, promotion_allowed: 'yes' as unknown as boolean },
    null,
  );

  assert.equal(evidence.freshness, 'STALE');
  assert.equal(evidence.testOosStatus, DAILY_NO_GO);
  assert.equal(evidence.promotionLocks.states.promotion_allowed.sourceStatus, 'invalid');
  assert.equal(evidence.roundTripCost.label, DAILY_MISSING);
});

test('blockers are deduped across all close-slot and registry blocker sources', () => {
  const evidence = adaptDailyResearchEvidence(null, {
    current_required_blockers: ['A', 'B', 'A'],
    upstream_gate_blockers: ['B', 'C'],
    close_slot_blockers: ['C', 'D'],
    artifact_selection_errors: ['D', 'E'],
  }, {
    effective_gate_blockers: ['E', 'F'],
    invariant_errors: ['F', 'A'],
  });

  assert.deepEqual(evidence.blockers, ['A', 'B', 'C', 'D', 'E', 'F']);
  assert.notEqual(evidence.split, 'GO');
  assert.equal(evidence.split, DAILY_NOT_RECORDED);
});
