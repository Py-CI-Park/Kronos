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

test('program score is the rounded weighted sum of every audited lane', () => {
  // Given
  const totalWeight = PROGRAM_LANES.reduce((total, lane) => total + lane.weight, 0);

  // When
  const score = programOverallScore(PROGRAM_LANES);

  // Then
  assert.equal(totalWeight, 100);
  assert.equal(score, 81);
});

test('every lane score is derived from a frozen 100-point evidence rubric', () => {
  for (const lane of PROGRAM_LANES) {
    const maximum = PROGRAM_SCORE_RUBRIC[lane.id].reduce((total, criterion) => total + criterion.points, 0);
    assert.equal(maximum, 100);
    assert.equal(lane.score, programRubricScore(lane.id));
    assert.ok(PROGRAM_SCORE_RUBRIC[lane.id].every((criterion) => criterion.evidence.length > 0));
  }
});

test('page matrix describes every V6 user surface in navigation order', () => {
  // Given / When
  const pageIds = PROGRAM_PAGE_MATRIX.map((page) => page.id);

  // Then
  assert.deepEqual(pageIds, [
    'home', 'scorecard', 'rl-discovery', 'rl-data', 'rl-experiment', 'rl-training',
    'rl-evaluation', 'rl-compare', 'rl-report', 'insights', 'lanes', 'settings',
  ]);
  assert.ok(PROGRAM_PAGE_MATRIX.every((page) => page.delivery === 'BUILT'));
  assert.ok(PROGRAM_PAGE_MATRIX.every((page) => page.progress >= 0 && page.progress <= 100));
  assert.ok(PROGRAM_PAGE_MATRIX.every((page) => page.eta.length > 0));
  assert.ok(PROGRAM_PAGE_MATRIX.every((page) => page.nextAction.length > 0));
  assert.ok(PROGRAM_PAGE_MATRIX.every((page) => page.mergeGate.length > 0));
  assert.equal(PROGRAM_PAGE_MATRIX.find((page) => page.id === 'rl-training')?.evidenceState, 'PRIMARY_COMPLETE');
  assert.equal(PROGRAM_PAGE_MATRIX.find((page) => page.id === 'rl-evaluation')?.evidenceState, 'D3_NO_GO_EXPLAINED');
});

test('capability inventory separates available research from blocked claims', () => {
  // Given / When
  const available = PROGRAM_CAPABILITIES.filter((capability) => capability.state === 'AVAILABLE');
  const blocked = PROGRAM_CAPABILITIES.filter((capability) => capability.state === 'BLOCKED');

  // Then
  assert.ok(available.some((capability) => capability.id === 'd0-smoke'));
  assert.ok(available.some((capability) => capability.id === 'd1-primary'));
  assert.ok(available.some((capability) => capability.id === 'd2-primary'));
  assert.ok(blocked.some((capability) => capability.id === 'fresh-oos'));
  assert.ok(blocked.some((capability) => capability.id === 'live-trading'));
});
