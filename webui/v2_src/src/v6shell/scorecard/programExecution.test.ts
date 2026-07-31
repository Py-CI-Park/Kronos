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
  assert.match(PROGRAM_EXECUTION.deliveryLane, /codex\/rl-d6/);
  assert.equal(PROGRAM_EXECUTION.baseRelease, 'fork-v1.17.0-kronos-rl-d5s-stability-earlystop');
  assert.equal(PROGRAM_EXECUTION.stage, 'D6_REUSED_VALIDATION_NOT_CONFIRMED');
  assert.equal(PROGRAM_EXECUTION.authority, 'REVIEWED_SNAPSHOT');
  assert.equal(PROGRAM_EXECUTION.reviewedRun, 'type2-d6-primary-20260731-002');
  assert.match(PROGRAM_EXECUTION.reviewedEvidenceManifest, /^[0-9a-f]{64}$/);
  assert.match(PROGRAM_EXECUTION.nextAction, /D6R/i);
  assert.match(researchContext, /D6/);
  assert.match(researchContext, /6 \/ 6 EVALUATIONS/);
  assert.match(researchContext, /VALIDATION · NO-GO/);
  assert.doesNotMatch(researchContext, /D5 DQN 10개/);
});
