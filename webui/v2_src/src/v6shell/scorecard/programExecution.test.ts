import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { PROGRAM_EXECUTION } from './programExecution';
import { PROGRAM_LANES, PROGRAM_PAGE_MATRIX, programOverallScore } from './programScorecard';

const researchContext = readFileSync(new URL('../ResearchContext.svelte', import.meta.url), 'utf8');

test('execution banner preserves the research boundary and delivery lineage', () => {
  assert.equal(PROGRAM_EXECUTION.overallScore, programOverallScore(PROGRAM_LANES));
  assert.equal(PROGRAM_EXECUTION.pageCount, PROGRAM_PAGE_MATRIX.length);
  assert.equal(PROGRAM_EXECUTION.freshOos, 'NOT_RUN_NO_READ');
  assert.equal(PROGRAM_EXECUTION.liveTrading, 'BLOCKED');
  assert.match(PROGRAM_EXECUTION.deliveryLane, /codex\/D5S/);
  assert.equal(PROGRAM_EXECUTION.baseRelease, 'fork-v1.16.0-kronos-rl-d5r-capacity-objective');
  assert.equal(PROGRAM_EXECUTION.stage, 'D5S_STABILITY_CONFIRMED');
  assert.equal(PROGRAM_EXECUTION.authority, 'REVIEWED_SNAPSHOT');
  assert.equal(PROGRAM_EXECUTION.reviewedRun, 'type2-d5s-primary-20260730-001');
  assert.match(PROGRAM_EXECUTION.reviewedEvidenceManifest, /^[0-9a-f]{64}$/);
  assert.match(PROGRAM_EXECUTION.nextAction, /D6/i);
  assert.match(researchContext, /D5S/);
  assert.match(researchContext, /36 \/ 36 UNITS/);
  assert.match(researchContext, /TRAIN_ONLY · CONFIRMED/);
  assert.doesNotMatch(researchContext, /D5 DQN 10개/);
});
