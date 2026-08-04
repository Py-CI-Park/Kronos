import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { PROGRAM_EXECUTION } from './programExecution';
import { PROGRAM_LANES, PROGRAM_PAGE_MATRIX, programOverallScore } from './programScorecard';

const researchContext = readFileSync(new URL('../ResearchContext.svelte', import.meta.url), 'utf8');

test('execution banner preserves current daily-close research boundary and lineage', () => {
  assert.equal(PROGRAM_EXECUTION.overallScore, programOverallScore(PROGRAM_LANES));
  assert.equal(PROGRAM_EXECUTION.overallScore, 63);
  assert.equal(PROGRAM_EXECUTION.implementationScore, 75);
  assert.equal(PROGRAM_EXECUTION.economicModelScore, 20);
  assert.equal(PROGRAM_EXECUTION.pageCount, PROGRAM_PAGE_MATRIX.length);
  assert.equal(PROGRAM_EXECUTION.pageCount, 13);
  assert.equal(PROGRAM_EXECUTION.freshOos, 'NOT_RUN_NO_READ');
  assert.equal(PROGRAM_EXECUTION.liveTrading, 'BLOCKED');
  assert.match(PROGRAM_EXECUTION.deliveryLane, /codex\/rl-all-pages-v1-28/);
  assert.match(PROGRAM_EXECUTION.deliveryLane, /research\/daily-close-offline-rl-v2/);
  assert.equal(PROGRAM_EXECUTION.baseRelease, 'v1.27.0-dev');
  assert.equal(PROGRAM_EXECUTION.releaseCandidate, 'v1.28.0-rc.1');
  assert.equal(PROGRAM_EXECUTION.stage, 'IMPLEMENTED_CALIBRATED_NO_GO_DATA_CUSTODY');
  assert.equal(PROGRAM_EXECUTION.authority, 'REVIEWED_SNAPSHOT');
  assert.equal(PROGRAM_EXECUTION.reviewedRun, 'DAILY_CLOSE_OFFLINE_RL_G1_G6_V2');
  assert.match(PROGRAM_EXECUTION.nextAction, /PIT universe/);
  assert.ok(PROGRAM_PAGE_MATRIX.some((page) => page.id === 'kronos'));
  assert.match(researchContext, /G1–G6/);
  assert.match(researchContext, /20종목 · 131,838표본/);
  assert.match(researchContext, /3 \/ 3 SEEDS/);
  assert.match(researchContext, /NOT_RUN_NO_READ/);
});
