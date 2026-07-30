import assert from 'node:assert/strict';
import test from 'node:test';
import { PROGRAM_EXECUTION } from './programExecution';
import { PROGRAM_LANES, PROGRAM_PAGE_MATRIX, programOverallScore } from './programScorecard';

test('execution banner preserves the research boundary and delivery lineage', () => {
  assert.equal(PROGRAM_EXECUTION.overallScore, programOverallScore(PROGRAM_LANES));
  assert.equal(PROGRAM_EXECUTION.pageCount, PROGRAM_PAGE_MATRIX.length);
  assert.equal(PROGRAM_EXECUTION.freshOos, 'NOT_RUN_NO_READ');
  assert.equal(PROGRAM_EXECUTION.liveTrading, 'BLOCKED');
  assert.match(PROGRAM_EXECUTION.deliveryLane, /codex\/D5R/);
  assert.equal(PROGRAM_EXECUTION.baseRelease, 'fork-v1.15.0-kronos-rl-d5-full-train-cost');
  assert.equal(PROGRAM_EXECUTION.stage, 'D5R_CAPACITY_NOT_CONFIRMED');
  assert.equal(PROGRAM_EXECUTION.authority, 'REVIEWED_SNAPSHOT');
  assert.equal(PROGRAM_EXECUTION.reviewedRun, 'type2-d5r-primary-20260730-001');
  assert.match(PROGRAM_EXECUTION.reviewedEvidenceManifest, /^[0-9a-f]{64}$/);
  assert.match(PROGRAM_EXECUTION.nextAction, /D5S/i);
});
