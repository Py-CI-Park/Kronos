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
  assert.match(PROGRAM_EXECUTION.deliveryLane, /codex\/rl-etf-q0-q2-foundation-v1/);
  assert.equal(PROGRAM_EXECUTION.baseRelease, 'fork-v1.20.0-kronos-rl-d6r2-mdp-falsification');
  assert.equal(PROGRAM_EXECUTION.stage, 'ETF_Q0_Q2_BLOCKED_Q1_Q2A');
  assert.equal(PROGRAM_EXECUTION.authority, 'REVIEWED_SNAPSHOT');
  assert.equal(PROGRAM_EXECUTION.reviewedRun, 'etf-stateful-q0-q2-canary-20260801');
  assert.match(PROGRAM_EXECUTION.reviewedEvidenceManifest, /^[0-9a-f]{64}$/);
  assert.match(PROGRAM_EXECUTION.nextAction, /point-in-time/i);
  assert.match(researchContext, /D6R2/);
  assert.match(researchContext, /70 \/ 70 EVALUATIONS/);
  assert.match(researchContext, /TOP-5 SIGNAL FLOOR · NO-GO/);
  assert.match(researchContext, /2 \/ 13 GATES/);
});
