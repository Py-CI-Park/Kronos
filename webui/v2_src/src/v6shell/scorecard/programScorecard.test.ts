import assert from 'node:assert/strict';
import test from 'node:test';
import {
  PROGRAM_CAPABILITIES,
  PROGRAM_LANES,
  PROGRAM_PAGE_MATRIX,
  programOverallScore,
} from './programScorecard';

test('program score is the rounded weighted sum of every audited lane', () => {
  // Given
  const totalWeight = PROGRAM_LANES.reduce((total, lane) => total + lane.weight, 0);

  // When
  const score = programOverallScore(PROGRAM_LANES);

  // Then
  assert.equal(totalWeight, 100);
  assert.equal(score, 74);
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
  assert.equal(PROGRAM_PAGE_MATRIX.find((page) => page.id === 'rl-evaluation')?.evidenceState, 'NO_GO');
});

test('capability inventory separates available research from blocked claims', () => {
  // Given / When
  const available = PROGRAM_CAPABILITIES.filter((capability) => capability.state === 'AVAILABLE');
  const blocked = PROGRAM_CAPABILITIES.filter((capability) => capability.state === 'BLOCKED');

  // Then
  assert.ok(available.some((capability) => capability.id === 'd0-smoke'));
  assert.ok(blocked.some((capability) => capability.id === 'fresh-oos'));
  assert.ok(blocked.some((capability) => capability.id === 'live-trading'));
});
