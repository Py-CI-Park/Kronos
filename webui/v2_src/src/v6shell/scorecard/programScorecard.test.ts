import assert from 'node:assert/strict';
import test from 'node:test';
import {
  PROGRAM_CAPABILITIES,
  PROGRAM_LANES,
  PROGRAM_PAGE_MATRIX,
  PROGRAM_SCORE_RUBRIC,
  programOverallScore,
  programRubricScore,
} from './programScorecard';

test('program score is the rounded weighted sum of current evidence', () => {
  // Given
  const totalWeight = PROGRAM_LANES.reduce((total, lane) => total + lane.weight, 0);

  // When
  const score = programOverallScore(PROGRAM_LANES);

  // Then
  assert.equal(totalWeight, 100);
  assert.equal(score, 63);
});
test('every lane score is derived from a frozen 100-point evidence rubric', () => {
  for (const lane of PROGRAM_LANES) {
    const maximum = PROGRAM_SCORE_RUBRIC[lane.id].reduce((total, criterion) => total + criterion.points, 0);
    assert.equal(maximum, 100);
    assert.equal(lane.score, programRubricScore(lane.id));
    assert.ok(PROGRAM_SCORE_RUBRIC[lane.id].every((criterion) => criterion.evidence.length > 0));
  }
});

test('page matrix describes every completed V6 surface in navigation order', () => {
  // Given / When
  const pageIds = PROGRAM_PAGE_MATRIX.map((page) => page.id);

  // Then
  assert.deepEqual(pageIds, [
    'home', 'scorecard', 'rl-discovery', 'rl-data', 'rl-experiment', 'rl-training',
    'rl-evaluation', 'rl-compare', 'rl-report', 'insights', 'lanes', 'kronos', 'settings',
  ]);
  assert.ok(PROGRAM_PAGE_MATRIX.every((page) => page.delivery === 'BUILT'));
  assert.ok(PROGRAM_PAGE_MATRIX.every((page) => page.progress === 100));
  assert.ok(PROGRAM_PAGE_MATRIX.every((page) => page.eta.length > 0));
  assert.ok(PROGRAM_PAGE_MATRIX.every((page) => page.nextAction.length > 0));
  assert.ok(PROGRAM_PAGE_MATRIX.every((page) => page.mergeGate.length > 0));
  assert.equal(PROGRAM_PAGE_MATRIX.find((page) => page.id === 'home')?.evidenceState, 'DAILY_CLOSE_G2_LOCAL_AUTHORITY_AUDITED_78');
  assert.equal(PROGRAM_PAGE_MATRIX.find((page) => page.id === 'scorecard')?.evidenceState, 'PROGRAM_63_IMPLEMENTATION_78_ECONOMIC_20');
  assert.equal(PROGRAM_PAGE_MATRIX.find((page) => page.id === 'rl-data')?.evidenceState, 'G2_LOCAL_ANCHOR_19_STABLE_1_EXCLUDED_4_EXTERNAL_BLOCKERS');
  assert.equal(PROGRAM_PAGE_MATRIX.find((page) => page.id === 'rl-training')?.evidenceState, 'SYNTHETIC_CQL_CREATED_MARKET_MODEL_NOT_CREATED');
  assert.equal(PROGRAM_PAGE_MATRIX.find((page) => page.id === 'rl-evaluation')?.evidenceState, 'G3_DIAGNOSTIC_PASS_4_OF_4_UNVERIFIED_CUSTODY');
  assert.equal(PROGRAM_PAGE_MATRIX.find((page) => page.id === 'rl-compare')?.evidenceState, 'CQL_IQM_0_1195_SHUFFLED_NEG_0_00524');
  assert.equal(PROGRAM_PAGE_MATRIX.find((page) => page.id === 'lanes')?.nextAction, '레인 간 성과 전이를 금지하고 독립 증거를 유지한다');
  assert.equal(PROGRAM_PAGE_MATRIX.find((page) => page.id === 'kronos')?.evidenceState, 'AVAILABLE_NOT_LOADED_NOT_RL_POLICY');
  assert.match(PROGRAM_LANES.find((lane) => lane.id === 'live')?.nextAction ?? '', /G7/u);
});

test('capability inventory separates current research from blocked claims', () => {
  // Given / When
  const available = PROGRAM_CAPABILITIES.filter((capability) => capability.state === 'AVAILABLE');
  const partial = PROGRAM_CAPABILITIES.filter((capability) => capability.state === 'PARTIAL');
  const blocked = PROGRAM_CAPABILITIES.filter((capability) => capability.state === 'BLOCKED');

  // Then
  assert.ok(available.some((capability) => capability.id === 'history-evidence'));
  assert.ok(available.some((capability) => capability.id === 'daily-close-contracts'));
  assert.ok(available.some((capability) => capability.id === 'portfolio-environment'));
  assert.ok(available.some((capability) => capability.id === 'offline-cql-calibration'));
  assert.ok(partial.some((capability) => capability.id === 'daily-close-foundation'));
  assert.ok(partial.some((capability) => capability.id === 'diagnostic-signal'));
  assert.ok(blocked.some((capability) => capability.id === 'point-in-time-custody'));
  assert.ok(blocked.some((capability) => capability.id === 'economic-market-model'));
  assert.ok(blocked.some((capability) => capability.id === 'fresh-oos'));
  assert.ok(blocked.some((capability) => capability.id === 'live-trading'));
});
