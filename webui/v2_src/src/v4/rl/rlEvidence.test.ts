import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import type * as RlEvidence from './rlEvidence';

const evidencePath = ['./rlEvidence.ts'].join('/');
const {
  DOCUMENTED_RL_FACTS,
  CONFLICT_BLOCKED,
  choosePreferredRlRun,
  classifyRlEvidenceLane,
  deriveRlCockpitEvidence,
  normalizeRlRuns,
  normalizeRlRows,
  normalizeRliableCollections,
  normalizeRlProgress,
  normalizeRlRunDetail,
  reconcileRlRunIdentity,
  rlRunIdentityKey,
}: typeof RlEvidence = await import(evidencePath);
const consoleSource = readFileSync(new URL('./V4RLEvidenceConsole.svelte', import.meta.url), 'utf8');

const { PROMOTION_LOCK_KEYS } = await import('../evidence');

const SHA_A = 'a'.repeat(64);
const SHA_B = 'b'.repeat(64);
const PROTOCOL = 'rl-evidence-v4';

function optimisticPromotionLocks(): Record<string, boolean> {
  const locks: Record<string, boolean> = {};
  for (const key of PROMOTION_LOCK_KEYS) {
    locks[key] = true;
  }
  return locks;
}


function identityRun(overrides: Record<string, unknown> = {}): any {
  return {
    name: '000031',
    run_uid: 'run-uid-full-000031-20260715T000000Z',
    artifact_type: 'opening_30m_rl_workflow',
    revision: 7,
    source_sha256: SHA_A,
    source_protocol: PROTOCOL,
    strategy_context: { line: 'rl', label: 'identity candidate', is_reinforcement_learning: true },
    ...overrides,
  };
}

function conflictCodes(result: ReturnType<typeof reconcileRlRunIdentity>): string[] {
  return result.conflicts.map((item) => item.code);
}

test('run identity reconciliation keeps matching full run_uid revision and provenance usable', () => {
  const list = identityRun();
  const detail = identityRun({
    detail: { trade_count: 0 },
    artifacts: [{ name: 'model.zip' }],
  });
  const reconciled = reconcileRlRunIdentity(list, detail, {
    selectedRunUid: rlRunIdentityKey(list),
    selectedName: '000031',
    listRecords: [list],
  });
  const cockpit = deriveRlCockpitEvidence(reconciled.source);

  assert.equal(reconciled.status, 'MATCHED');
  assert.equal(reconciled.usable, true);
  assert.equal(reconciled.source, detail);
  assert.deepEqual(conflictCodes(reconciled), []);
  assert.equal(cockpit.run.run_id, '000031');
  assert.equal(cockpit.neverTradeStatus, 'NEVER_TRADE');
});

test('matched source true promotion locks remain provenance attempts with effective false locks', () => {
  const sourceLocks = optimisticPromotionLocks();
  const list = identityRun({ promotion_locks: sourceLocks });
  const detail = identityRun({ promotion_locks: sourceLocks, detail: { trade_count: 0 } });
  const reconciled = reconcileRlRunIdentity(list, detail, {
    selectedRunUid: rlRunIdentityKey(list),
    selectedName: '000031',
    listRecords: [list],
  });
  const cockpit = deriveRlCockpitEvidence(reconciled.source);

  assert.equal(reconciled.status, 'MATCHED');
  assert.equal(reconciled.usable, true);
  assert.equal(cockpit.run.promotion_locks.allLocked, true);
  for (const key of PROMOTION_LOCK_KEYS) {
    const state = cockpit.run.promotion_locks.states[key];
    assert.equal(cockpit.run.promotion_locks.locks[key], false);
    assert.equal(state.allowed, false);
    assert.equal(state.sourceStatus, 'declared');
    assert.equal(state.reason, 'UNLOCKED_BY_SOURCE');
  }
  assert.ok(cockpit.run.blocking_reasons.some((reason) => reason.includes('SOURCE_TRUE_UNLOCK_PROVENANCE_ATTEMPT_BLOCKED')));
});


test('run identity reconciliation blocks stale detail races with false promotion locks', () => {
  const list = identityRun({ revision: 9 });
  const staleDetail = identityRun({ revision: 8 });
  const reconciled = reconcileRlRunIdentity(list, staleDetail, {
    selectedRunUid: rlRunIdentityKey(list),
    selectedName: '000031',
    listRecords: [list],
  });
  const cockpit = deriveRlCockpitEvidence(reconciled.source);

  assert.equal(reconciled.status, CONFLICT_BLOCKED);
  assert.equal(reconciled.usable, false);
  assert.ok(conflictCodes(reconciled).includes('REVISION_MISMATCH_STALE_DETAIL'));
  assert.equal(cockpit.run.verdict, CONFLICT_BLOCKED);
  assert.equal(cockpit.run.promotion_locks.allLocked, true);
  assert.equal(Object.values(cockpit.run.promotion_locks.locks).every((value) => value === false), true);
});

test('conflict source true promotion locks remain conflict-blocked effective false locks', () => {
  const sourceLocks = optimisticPromotionLocks();
  const list = identityRun({ revision: 9, promotion_locks: sourceLocks });
  const staleDetail = identityRun({ revision: 8, promotion_locks: sourceLocks });
  const reconciled = reconcileRlRunIdentity(list, staleDetail, {
    selectedRunUid: rlRunIdentityKey(list),
    selectedName: '000031',
    listRecords: [list],
  });
  const cockpit = deriveRlCockpitEvidence(reconciled.source);

  assert.equal(reconciled.status, CONFLICT_BLOCKED);
  assert.equal(reconciled.usable, false);
  assert.ok(conflictCodes(reconciled).includes('REVISION_MISMATCH_STALE_DETAIL'));
  assert.equal(cockpit.run.verdict, CONFLICT_BLOCKED);
  assert.equal(cockpit.run.promotion_locks.allLocked, true);
  for (const key of PROMOTION_LOCK_KEYS) {
    assert.equal(cockpit.run.promotion_locks.locks[key], false);
    assert.equal(cockpit.run.promotion_locks.states[key].allowed, false);
  }
});


test('run identity reconciliation blocks UID mismatch and list UID collisions', () => {
  const list = identityRun();
  const mismatch = reconcileRlRunIdentity(list, identityRun({ run_uid: 'run-uid-full-other-20260715T000000Z' }), {
    selectedRunUid: rlRunIdentityKey(list),
    selectedName: '000031',
    listRecords: [list],
  });
  const collision = reconcileRlRunIdentity(list, identityRun(), {
    selectedRunUid: rlRunIdentityKey(list),
    selectedName: '000031',
    listRecords: [list, identityRun({ name: '000032' })],
  });

  assert.equal(mismatch.status, CONFLICT_BLOCKED);
  assert.ok(conflictCodes(mismatch).includes('RUN_UID_MISMATCH'));
  assert.equal(collision.status, CONFLICT_BLOCKED);
  assert.ok(conflictCodes(collision).includes('LIST_UID_COLLISION'));
});

test('run identity reconciliation blocks newer detail, source hash, protocol, and malformed provenance', () => {
  const newerSourceConflict = reconcileRlRunIdentity(
    identityRun(),
    identityRun({ revision: 8, source_sha256: SHA_B, source_protocol: 'rl-evidence-v4-replay' }),
    { selectedRunUid: rlRunIdentityKey(identityRun()), selectedName: '000031', listRecords: [identityRun()] },
  );
  const malformed = reconcileRlRunIdentity(
    identityRun({ run_uid: '', source_sha256: 'not-a-sha', source_protocol: '' }),
    identityRun(),
    { selectedRunUid: 'RUN_UID_NOT_RECORDED:000031', selectedName: '000031', listRecords: [identityRun({ run_uid: '' })] },
  );
  const malformedDetail = reconcileRlRunIdentity(
    identityRun(),
    identityRun(),
    { selectedRunUid: rlRunIdentityKey(identityRun()), selectedName: '000031', listRecords: [identityRun()], detailRecorded: false },
  );

  assert.equal(newerSourceConflict.status, CONFLICT_BLOCKED);
  assert.ok(conflictCodes(newerSourceConflict).includes('REVISION_MISMATCH_NEWER_DETAIL'));
  assert.ok(conflictCodes(newerSourceConflict).includes('SOURCE_SHA_CONFLICT'));
  assert.ok(conflictCodes(newerSourceConflict).includes('PROTOCOL_CONFLICT'));
  assert.equal(malformed.status, CONFLICT_BLOCKED);
  assert.ok(conflictCodes(malformed).includes('LIST_RUN_UID_INVALID'));
  assert.ok(conflictCodes(malformed).includes('LIST_SOURCE_SHA_INVALID'));
  assert.ok(conflictCodes(malformed).includes('LIST_PROTOCOL_INVALID'));
  assert.equal(malformedDetail.status, CONFLICT_BLOCKED);
  assert.ok(conflictCodes(malformedDetail).includes('DETAIL_RECORD_MALFORMED'));
});

test('RL console exposes list/detail provenance markers and conflict-blocked source state', () => {
  assert.match(consoleSource, /data-v4-rl-identity-reconciliation/);
  assert.match(consoleSource, /data-v4-rl-list-provenance/);
  assert.match(consoleSource, /data-v4-rl-detail-provenance/);
  assert.match(consoleSource, /data-v4-rl-identity-conflicts/);
  assert.match(consoleSource, /data-identity-state=\{reconciliationState\}/);
  assert.match(consoleSource, /CONFLICT_BLOCKED/);
  assert.match(consoleSource, /rlRunIdentityKey\(preferred\)/);
  assert.match(consoleSource, /value=\{selectedRunUid\}/);
  assert.match(consoleSource, /reconcileRlRunIdentity\(selectedListRecord, selectedRun/);
  assert.match(consoleSource, /Unsafe actions and optimistic model\/GO copy are suppressed/);
});

test('RL console gates raw audit legacy child behind usable reconciliation markers', () => {
  const rawAudit = consoleSource.slice(consoleSource.indexOf('data-v4-raw-audit'));
  const gateIndex = rawAudit.indexOf('{#if reconciliation.usable}');
  const renderIndex = rawAudit.indexOf('{@render children()}');

  assert.match(consoleSource, /data-v4-effective-lock-boundary/);
  assert.match(consoleSource, /Source true unlock fields are provenance attempts only/);
  assert.match(consoleSource, /open=\{!reconciliation\.usable\}/);
  assert.match(rawAudit, /data-raw-audit-trust=\{reconciliation\.usable \? 'MATCHED' : 'UNTRUSTED'\}/);
  assert.match(rawAudit, /data-legacy-child-state=\{reconciliation\.usable \? 'MATCHED' : CONFLICT_BLOCKED\}/);
  assert.match(rawAudit, /data-v4-raw-audit-untrusted/);
  assert.match(rawAudit, /UNTRUSTED · \{CONFLICT_BLOCKED\}/);
  assert.match(rawAudit, /Independent child state is not trusted/);
  assert.ok(gateIndex >= 0 && renderIndex > gateIndex);
});

test('classifies RULE, RL, and supervised gate lanes without relabeling RULE as RL', () => {
  const rule = classifyRlEvidenceLane({
    name: '000007',
    artifact_type: 'baseline',
    strategy_context: { line: 'rule_mainline', label: 'ts_imb', is_reinforcement_learning: false },
  });
  const rl = classifyRlEvidenceLane({
    name: '000008',
    artifact_type: 'opening_30m_rl_workflow',
    strategy_context: { line: 'rl', label: 'candidate', is_reinforcement_learning: true },
  });
  const supervised = classifyRlEvidenceLane({
    name: '000009',
    artifact_type: 'factory_calibration',
    strategy_context: { line: 'supervised', label: 'calibration', is_reinforcement_learning: false },
  });

  assert.equal(rule.kind, 'RULE');
  assert.equal(rule.isRl, false);
  assert.equal(rl.kind, 'RL');
  assert.equal(rl.isRl, true);
  assert.equal(supervised.kind, 'SUPERVISED_GATE');
  assert.equal(supervised.isRl, false);
});
test('explicit non-RL declarations outrank RL artifact naming heuristics', () => {
  const supervisedArtifact = classifyRlEvidenceLane({
    name: '000017',
    artifact_type: 'supervised_sb3_rl_workflow',
    strategy_context: { line: 'supervised', is_reinforcement_learning: false },
  });
  const factoryArtifact = classifyRlEvidenceLane({
    name: '000018',
    artifact_type: 'factory_rl_workflow_sb3',
    is_reinforcement_learning: false,
  });

  assert.equal(supervisedArtifact.kind, 'SUPERVISED_GATE');
  assert.equal(supervisedArtifact.isRl, false);
  assert.equal(factoryArtifact.kind, 'SUPERVISED_GATE');
  assert.equal(factoryArtifact.isRl, false);
});

test('explicit true remains RL when no RULE baseline takes precedence', () => {
  const rl = classifyRlEvidenceLane({
    name: '000019',
    artifact_type: 'ordinary_artifact',
    strategy_context: { line: 'research', is_reinforcement_learning: true },
  });

  assert.equal(rl.kind, 'RL');
  assert.equal(rl.isRl, true);
});

test('ordinary supervised and factory records remain non-RL', () => {
  const supervised = classifyRlEvidenceLane({
    name: '000020',
    artifact_type: 'supervised_calibration',
    strategy_context: { line: 'supervised', is_reinforcement_learning: false },
  });
  const factory = classifyRlEvidenceLane({
    name: '000021',
    artifact_type: 'factory_sizing',
  });

  assert.equal(supervised.kind, 'SUPERVISED_GATE');
  assert.equal(factory.kind, 'SUPERVISED_GATE');
  assert.equal(supervised.isRl, false);
  assert.equal(factory.isRl, false);
});

test('RULE precedence remains authoritative over explicit RL declarations', () => {
  const rule = classifyRlEvidenceLane({
    name: '000022',
    artifact_type: 'sb3_rl_workflow',
    strategy_context: { line: 'rule_mainline', is_reinforcement_learning: true },
  });

  assert.equal(rule.kind, 'RULE');
  assert.equal(rule.isRl, false);
});

test('derive cockpit metrics fail closed for missing and null values with explicit NOT_RECORDED', () => {
  const cockpit = deriveRlCockpitEvidence({
    name: '000010',
    artifact_type: 'opening_30m_rl_workflow',
    strategy_context: { line: 'rl', is_reinforcement_learning: true, label: 'missing metrics' },
    detail: { test_oos: null, trade_count: null },
  });

  const testOos = cockpit.metrics.find((metric) => metric.key === 'test_oos');
  const cost = cockpit.metrics.find((metric) => metric.key === 'declared_cost_bps');
  const tradeCount = cockpit.metrics.find((metric) => metric.key === 'trade_count');

  assert.equal(testOos?.metric.availability, 'NOT_RECORDED');
  assert.equal(cost?.metric.availability, 'NOT_RECORDED');
  assert.equal(cost?.display, 'NOT_RECORDED');
  assert.equal(tradeCount?.metric.availability, 'NOT_RECORDED');
  assert.equal(cockpit.neverTradeStatus, 'NOT_RECORDED');
});

test('derive cockpit metadata exposes textual split hash seed and baseline before numeric metrics', () => {
  const splitHash = '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef';
  const cockpit = deriveRlCockpitEvidence({
    name: '000012',
    artifact_type: 'opening_30m_rl_workflow',
    split: 'walk-forward train=2024 test=2025',
    split_hash: splitHash,
    seed: '000123',
    baseline_label: 'ts_imb_rule_23bp',
    strategy_context: { line: 'rl', is_reinforcement_learning: true },
  });

  assert.deepEqual(
    cockpit.metadata.map((item) => [item.key, item.value, item.behavior]),
    [
      ['split', 'walk-forward train=2024 test=2025', 'recorded'],
      ['split_hash', splitHash, 'recorded'],
      ['seed', '000123', 'recorded'],
      ['baseline', 'ts_imb_rule_23bp', 'recorded'],
    ],
  );
  assert.equal(cockpit.metrics.some((metric) => metric.metric.unit === 'recorded_flag'), false);
});

test('derive cockpit metadata preserves NOT_RECORDED text for malformed or null textual fields', () => {
  const cockpit = deriveRlCockpitEvidence({
    name: '000013',
    artifact_type: 'opening_30m_rl_workflow',
    split: null,
    split_hash: 'not-a-sha256',
    seed: null,
    baseline_label: '',
    detail: { baseline: null },
    strategy_context: { line: 'rl', is_reinforcement_learning: true },
  });

  assert.deepEqual(
    cockpit.metadata.map((item) => [item.key, item.value, item.behavior]),
    [
      ['split', 'SPLIT_NOT_RECORDED', 'not_recorded'],
      ['split_hash', 'SPLIT_HASH_NOT_RECORDED', 'not_recorded'],
      ['seed', 'SEED_NOT_RECORDED', 'not_recorded'],
      ['baseline', 'BASELINE_NOT_RECORDED', 'not_recorded'],
    ],
  );
});

test('derive cockpit metrics marks incompatible declared units instead of coercing them', () => {
  const cockpit = deriveRlCockpitEvidence({
    name: '000011',
    artifact_type: 'opening_30m_rl_workflow',
    cost_bps: 23,
    detail: {
      trade_count: { value: 3, unit: 'pct' },
      max_drawdown_pct: { value: 12, unit: 'usd' },
    },
    strategy_context: { line: 'rl', is_reinforcement_learning: true },
  });

  const drawdown = cockpit.metrics.find((metric) => metric.key === 'max_drawdown');
  const tradeCount = cockpit.metrics.find((metric) => metric.key === 'trade_count');

  assert.equal(drawdown?.behavior, 'incompatible_unit');
  assert.match(drawdown?.display ?? '', /INCOMPATIBLE_UNIT/);
  assert.equal(tradeCount?.behavior, 'incompatible_unit');
  assert.equal(tradeCount?.metric.availability, 'INAPPLICABLE');
});
test('incompatible trade-count units fail closed for zero and nonzero values', () => {
  for (const value of [0, 3]) {
    const cockpit = deriveRlCockpitEvidence({
      name: `00001${value}`,
      artifact_type: 'opening_30m_rl_workflow',
      detail: { trade_count: { value, unit: 'pct' } },
      strategy_context: { line: 'rl', is_reinforcement_learning: true },
    });
    assert.equal(cockpit.neverTradeStatus, 'NOT_RECORDED');
    assert.equal(cockpit.metrics.find((metric) => metric.key === 'trade_count')?.behavior, 'incompatible_unit');
  }
});

test('collection normalizers distinguish malformed, empty, and recorded payloads', () => {
  assert.equal(normalizeRlRuns({}).status, 'not_recorded');
  assert.equal(normalizeRlRuns({ runs: null }).status, 'not_recorded');
  assert.equal(normalizeRlRuns({ runs: {} }).status, 'not_recorded');
  assert.equal(normalizeRlRuns({ runs: [null] }).status, 'not_recorded');
  assert.equal(normalizeRlRuns({ runs: [{}] }).status, 'not_recorded');
  assert.equal(normalizeRlRuns({ runs: [] }).status, 'empty');
  assert.equal(normalizeRlRuns({ runs: [{ name: '000001' }] }).status, 'recorded');
  assert.equal(normalizeRlRows({}).status, 'not_recorded');
  assert.equal(normalizeRlRows({ rows: null }).status, 'not_recorded');
  assert.equal(normalizeRlRows({ rows: [{}] }).status, 'recorded');
  assert.equal(normalizeRlRows({ rows: [] }).status, 'empty');

  assert.equal(normalizeRliableCollections({}).status, 'not_recorded');
  assert.equal(normalizeRliableCollections({ algorithms: null, aggregates: {} }).status, 'not_recorded');
  assert.equal(normalizeRliableCollections({ algorithms: [], aggregates: {} }).status, 'empty');
  assert.equal(normalizeRliableCollections({ algorithms: ['ppo'], aggregates: { ppo: {} } }).status, 'recorded');
});
test('malformed collection payloads stay not recorded while transport rejection labels remain fetch failed', () => {
  assert.equal(normalizeRlRuns({ runs: null }).status, 'not_recorded');
  assert.equal(normalizeRlProgress({ pages: [], status: 'bad' }).status, 'not_recorded');

  assert.match(consoleSource, /data-run-source-state=\{runsError \? 'error' : runCollectionState\}/);
  assert.match(consoleSource, /\{runsError \?\? \(runCollectionState === 'not_recorded' \? 'RUNS_NOT_RECORDED'/);
  assert.match(consoleSource, /data-progress-source-state=\{progressError \? 'error' : progressState\}/);
  assert.match(consoleSource, /progressState === 'not_recorded' \? 'PROGRESS_NOT_RECORDED'/);
  assert.match(consoleSource, /runsError = message\(runResult\.reason, 'RL runs evidence fetch failed'\)/);
  assert.match(consoleSource, /progressError = message\(progressResult\.reason, 'RL progress evidence fetch failed'\)/);
  assert.doesNotMatch(consoleSource, /normalizedRuns\.status === 'not_recorded'.*runsError =/);
  assert.doesNotMatch(consoleSource, /normalizedProgress\.status === 'not_recorded'.*progressError =/);
  assert.match(consoleSource, /'PROGRESS_FETCH_FAILED'/);
});
test('numeric metric strings remain NOT_RECORDED instead of appearing as recorded values', () => {
  const cockpit = deriveRlCockpitEvidence({
    name: '000023',
    artifact_type: 'opening_30m_rl_workflow',
    detail: { test_oos: '0.42', trade_count: '0' },
    strategy_context: { line: 'rl', is_reinforcement_learning: true },
  });
  const testOos = cockpit.metrics.find((metric) => metric.key === 'test_oos');
  const tradeCount = cockpit.metrics.find((metric) => metric.key === 'trade_count');
  assert.equal(testOos?.metric.availability, 'NOT_RECORDED');
  assert.equal(testOos?.display, 'NOT_RECORDED');
  assert.equal(tradeCount?.metric.availability, 'NOT_RECORDED');
  assert.equal(tradeCount?.display, 'NOT_RECORDED');
  assert.equal(cockpit.neverTradeStatus, 'NOT_RECORDED');
});

test('RL cockpit boundary exposes exactly six fail-closed promotion locks', () => {
  const cockpit = deriveRlCockpitEvidence({
    name: '000014',
    artifact_type: 'opening_30m_rl_workflow',
    promotion_locks: {
      promotion_allowed: false,
      model_build_allowed: false,
      paper_forward_allowed: false,
      live_broker_order_allowed: false,
      profitability_claim_allowed: false,
      go_summary_allowed: false,
    },
    strategy_context: { line: 'rl', is_reinforcement_learning: true },
  });

  assert.deepEqual(Object.keys(cockpit.run.promotion_locks.locks), [...PROMOTION_LOCK_KEYS]);
  assert.equal(PROMOTION_LOCK_KEYS.length, 6);
  assert.equal(cockpit.run.promotion_locks.allLocked, true);
  assert.equal(Object.values(cockpit.run.promotion_locks.locks).every((value) => value === false), true);
});

test('RL cockpit boundary fails closed for missing and invalid promotion lock sources', () => {
  const missing = deriveRlCockpitEvidence({
    name: '000015',
    artifact_type: 'opening_30m_rl_workflow',
    strategy_context: { line: 'rl', is_reinforcement_learning: true },
  });
  const invalid = deriveRlCockpitEvidence({
    name: '000016',
    artifact_type: 'opening_30m_rl_workflow',
    promotion_locks: {
      promotion_allowed: 'false',
      model_build_allowed: 1,
      paper_forward_allowed: 0,
      live_broker_order_allowed: 'no',
      profitability_claim_allowed: {},
      go_summary_allowed: [],
    },
    strategy_context: { line: 'rl', is_reinforcement_learning: true },
  });

  assert.equal(missing.run.promotion_locks.allLocked, true);
  assert.equal(PROMOTION_LOCK_KEYS.every((key) => missing.run.promotion_locks.states[key].sourceStatus === 'missing'), true);
  assert.equal(invalid.run.promotion_locks.allLocked, true);
  assert.equal(invalid.run.promotion_locks.hasInvalidSource, true);
  assert.equal(PROMOTION_LOCK_KEYS.every((key) => invalid.run.promotion_locks.states[key].sourceStatus === 'invalid'), true);
});

test('documented model-health facts expose mandatory non-live research posture blockers', () => {
  const keys = DOCUMENTED_RL_FACTS.map((fact) => fact.key);
  assert.deepEqual(keys, [
    'smoke_plumbing_complete',
    'full_model_not_promoted',
    'r5_tuning_harmful',
    'close_slot_no_go',
    'd4_seed_noise_no_go',
    'documented_research_posture',
  ]);
  assert.equal(DOCUMENTED_RL_FACTS.every((fact) => fact.staticResearchPosture), true);
  assert.equal(DOCUMENTED_RL_FACTS.some((fact) => fact.status === 'NO-GO'), true);
  assert.equal(DOCUMENTED_RL_FACTS.some((fact) => fact.status === 'NOT_PROMOTED'), true);
});

test('preferred run chooses completed RL before RULE while preserving leading-zero identifiers', () => {
  const preferred = choosePreferredRlRun([
    { name: '000001', artifact_type: 'baseline', strategy_context: { line: 'rule_mainline', is_reinforcement_learning: false } },
    { name: '000002', artifact_type: 'opening_30m_rl_workflow', summary: { status: 'running' }, strategy_context: { line: 'rl', is_reinforcement_learning: true } },
    { name: '000003', artifact_type: 'opening_30m_rl_workflow', summary: { status: 'completed' }, strategy_context: { line: 'rl', is_reinforcement_learning: true } },
  ]);

  assert.equal(preferred?.name, '000003');
  assert.equal(typeof preferred?.name, 'string');
});

test('progress and selected detail normalizers fail closed with explicit empty state and identity checks', () => {
  const page = { page: 'training', progress_pct: 50, status: 'in_progress' };
  assert.equal(normalizeRlProgress({ overall_progress_pct: 50, status: 'in_progress', pages: [page] }).status, 'recorded');
  assert.equal(normalizeRlProgress({ overall_progress_pct: 0, status: 'queued', pages: [] }).status, 'empty');
  assert.equal(normalizeRlProgress({ overall_progress_pct: 50, status: 'ok', pages: [{ ...page, progress_pct: '50' }] }).status, 'not_recorded');
  assert.equal(normalizeRlProgress({ overall_progress_pct: 50, status: 'ok', pages: [{ ...page, criteria: {} }] }).status, 'not_recorded');

  const detail = { name: '000001', artifact_type: 'opening_30m_rl_workflow', artifacts: [{ name: 'model.zip' }] };
  assert.equal(normalizeRlRunDetail(detail, '000001').status, 'recorded');
  assert.equal(normalizeRlRunDetail({}, '000001').status, 'not_recorded');
  assert.equal(normalizeRlRunDetail({ ...detail, name: '000002' }, '000001').status, 'not_recorded');
  assert.equal(normalizeRlRunDetail({ ...detail, artifacts: [{ name: '' }] }, '000001').status, 'not_recorded');
});

test('metadata and trade-count domains remain explicit', () => {
  const base = { name: '000002', artifact_type: 'opening_30m_rl_workflow', strategy_context: { line: 'rl', is_reinforcement_learning: true } };
  const numeric = deriveRlCockpitEvidence({ ...base, split: 2025, baseline_label: { value: 'x' }, seed: '000007' });
  assert.equal(numeric.metadata.find((item) => item.key === 'split')?.behavior, 'not_recorded');
  assert.equal(numeric.metadata.find((item) => item.key === 'baseline')?.behavior, 'not_recorded');
  assert.equal(numeric.metadata.find((item) => item.key === 'seed')?.value, '000007');

  for (const value of [-1, 1.5, NaN, Infinity, '2', {}]) {
    assert.equal(deriveRlCockpitEvidence({ ...base, detail: { trade_count: value } }).neverTradeStatus, 'NOT_RECORDED');
  }
  assert.equal(deriveRlCockpitEvidence({ ...base, detail: { trade_count: 0 } }).neverTradeStatus, 'NEVER_TRADE');
  assert.equal(deriveRlCockpitEvidence({ ...base, detail: { trade_count: 2 } }).neverTradeStatus, 'TRADED');
});

