import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { PROGRAM_EXECUTION } from './programExecution';
import { PROGRAM_LANES, PROGRAM_PAGE_MATRIX, programOverallScore } from './programScorecard';

const researchContext = readFileSync(new URL('../ResearchContext.svelte', import.meta.url), 'utf8');
const executionStrip = readFileSync(new URL('../ProgramExecutionStrip.svelte', import.meta.url), 'utf8');
const scorecardPage = readFileSync(new URL('../pages/ProgramScorecardPage.svelte', import.meta.url), 'utf8');

test('execution banner preserves current daily-close research boundary and lineage', () => {
  assert.equal(PROGRAM_EXECUTION.overallScore, programOverallScore(PROGRAM_LANES));
  assert.equal(PROGRAM_EXECUTION.overallScore, 63);
  assert.equal(PROGRAM_EXECUTION.implementationScore, 78);
  assert.equal(PROGRAM_EXECUTION.economicModelScore, 20);
  assert.equal(PROGRAM_EXECUTION.pageCount, PROGRAM_PAGE_MATRIX.length);
  assert.equal(PROGRAM_EXECUTION.pageCount, 13);
  assert.equal(PROGRAM_EXECUTION.freshOos, 'NOT_RUN_NO_READ');
  assert.equal(PROGRAM_EXECUTION.liveTrading, 'BLOCKED');
  assert.match(PROGRAM_EXECUTION.deliveryLane, /codex\/v1.28.0-dev-<task>/);
  assert.match(PROGRAM_EXECUTION.deliveryLane, /develop\/v1.28.0-dev/);
  assert.equal(PROGRAM_EXECUTION.developmentVersion, 'v1.28.0-dev');
  assert.equal(PROGRAM_EXECUTION.releaseCandidate, 'NOT_CREATED');
  assert.equal(PROGRAM_EXECUTION.versionPolicy, 'FREEZE_DEV_VERSION_UNTIL_RELEASE_GATE');
  assert.equal(PROGRAM_EXECUTION.branchRetentionPolicy, 'KEEP_MERGED_BRANCHES');
  assert.match(PROGRAM_EXECUTION.deliveryLane, /MERGED 보존/);
  assert.equal(PROGRAM_EXECUTION.stage, 'AUDITED_LOCAL_ANCHOR_NO_GO_EXTERNAL_AUTHORITY');
  assert.equal(PROGRAM_EXECUTION.authority, 'REVIEWED_SNAPSHOT');
  assert.equal(PROGRAM_EXECUTION.reviewedRun, 'DAILY_CLOSE_OFFLINE_RL_G2_PIT_AUTHORITY_AUDIT_V1');
  assert.match(PROGRAM_EXECUTION.nextAction, /날짜별 PIT/);
  assert.ok(PROGRAM_PAGE_MATRIX.some((page) => page.id === 'kronos'));
  assert.match(researchContext, /G1–G6/);
  assert.match(researchContext, /20종목 · 131,838표본/);
  assert.match(researchContext, /3 \/ 3 SEEDS/);
  assert.match(researchContext, /NOT_RUN_NO_READ/);
  assert.match(executionStrip, /PROGRAM_EXECUTION\.developmentVersion/);
  assert.match(scorecardPage, /병합된 작업 브랜치는 MERGED 이력으로 보존합니다/);
  assert.doesNotMatch(scorecardPage, /작업 브랜치는 삭제합니다/);
});
