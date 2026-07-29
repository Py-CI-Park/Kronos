import assert from 'node:assert/strict';
import test from 'node:test';
import { PROGRAM_EXECUTION } from './programExecution';
import { PROGRAM_LANES, PROGRAM_PAGE_MATRIX, programOverallScore } from './programScorecard';

test('execution banner preserves the research boundary and delivery lineage', () => {
  assert.equal(PROGRAM_EXECUTION.overallScore, programOverallScore(PROGRAM_LANES));
  assert.equal(PROGRAM_EXECUTION.pageCount, PROGRAM_PAGE_MATRIX.length);
  assert.equal(PROGRAM_EXECUTION.freshOos, 'NOT_RUN_NO_READ');
  assert.equal(PROGRAM_EXECUTION.liveTrading, 'BLOCKED');
  assert.match(PROGRAM_EXECUTION.deliveryLane, /codex\/\*/);
  assert.equal(PROGRAM_EXECUTION.baseRelease, 'fork-v1.11.0-kronos-rl-d2-historical-scale');
  assert.equal(PROGRAM_EXECUTION.stage, 'D3_REPRESENTATION_ACTION_NOT_CONFIRMED');
  assert.equal(PROGRAM_EXECUTION.authority, 'REVIEWED_SNAPSHOT');
  assert.equal(PROGRAM_EXECUTION.reviewedRun, 'type2-d3-primary-20260729-v1');
  assert.match(PROGRAM_EXECUTION.reviewedEvidenceManifest, /^[0-9a-f]{64}$/);
  assert.match(PROGRAM_EXECUTION.nextAction, /D4/i);
});
