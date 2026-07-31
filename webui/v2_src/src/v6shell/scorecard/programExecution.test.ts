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
  assert.match(PROGRAM_EXECUTION.deliveryLane, /codex\/rl-d6r/);
  assert.equal(PROGRAM_EXECUTION.baseRelease, 'fork-v1.18.0-kronos-rl-d6-reused-validation');
  assert.equal(PROGRAM_EXECUTION.stage, 'D6R_TRAIN_FALSIFICATION_NOT_CONFIRMED');
  assert.equal(PROGRAM_EXECUTION.authority, 'REVIEWED_SNAPSHOT');
  assert.equal(PROGRAM_EXECUTION.reviewedRun, 'type2-d6r-primary-20260731-001');
  assert.match(PROGRAM_EXECUTION.reviewedEvidenceManifest, /^[0-9a-f]{64}$/);
  assert.match(PROGRAM_EXECUTION.nextAction, /D6R2/i);
  assert.match(researchContext, /D6R/);
  assert.match(researchContext, /60 \/ 60 EVALUATIONS/);
  assert.match(researchContext, /TRAIN FALSIFICATION · NO-GO/);
  assert.match(researchContext, /1 \/ 10 GATES/);
});
