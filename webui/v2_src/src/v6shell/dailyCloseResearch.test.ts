import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { DAILY_CLOSE_RESEARCH, dailyCloseProgress } from './dailyCloseResearch';

test('daily-close research snapshot keeps implementation and economic verdict separate', () => {
  assert.equal(DAILY_CLOSE_RESEARCH.overallVerdict, 'IMPLEMENTED_CALIBRATED_NO_GO_DATA_CUSTODY');
  assert.equal(DAILY_CLOSE_RESEARCH.modelScope, 'SYNTHETIC_CALIBRATION_ONLY');
  assert.equal(DAILY_CLOSE_RESEARCH.costs.stockKrxRoundTripPercent, 0.23);
  assert.equal(DAILY_CLOSE_RESEARCH.signalFloor.positiveFolds, 4);
  assert.equal(DAILY_CLOSE_RESEARCH.economicModelCreated, false);
  assert.equal(DAILY_CLOSE_RESEARCH.freshOosState, 'NOT_RUN_NO_READ');
  assert.equal(DAILY_CLOSE_RESEARCH.version, 'v1.28.0-dev');
  assert.equal(DAILY_CLOSE_RESEARCH.sourceCustody.databaseHashState, 'SHA256_BOUND');
  assert.equal(DAILY_CLOSE_RESEARCH.sourceCustody.passedGateCount, 1);
  assert.equal(DAILY_CLOSE_RESEARCH.sourceCustody.externalBlockerCount, 4);
  assert.equal(dailyCloseProgress(DAILY_CLOSE_RESEARCH.gates), 78);
  assert.deepEqual(DAILY_CLOSE_RESEARCH.blockers, [
    'POINT_IN_TIME_UNIVERSE',
    'AVAILABLE_AT_PROVEN',
    'OFFICIAL_PRICE_IDENTITY',
    'CORPORATE_ACTION_CONTRACT',
  ]);
});

test('RL workspace exposes the same status panel on every research step', async () => {
  const workspace = await readFile(new URL('./RLWorkspace.svelte', import.meta.url), 'utf8');
  const scorecard = await readFile(new URL('./pages/ProgramScorecardPage.svelte', import.meta.url), 'utf8');
  const command = await readFile(new URL('./pages/command/CommandCenterPage.svelte', import.meta.url), 'utf8');
  const panel = await readFile(new URL('./DailyCloseResearchStatus.svelte', import.meta.url), 'utf8');
  const dataPage = await readFile(new URL('./pages/DataPage.svelte', import.meta.url), 'utf8');

  assert.match(workspace, /DailyCloseResearchStatus/u);
  assert.match(panel, /일봉 종가매매 강화학습/u);
  assert.match(scorecard, /DailyCloseResearchStatus/u);
  assert.match(command, /경제 모델/u);
  assert.match(dataPage, /G2 로컬 권위성 감사/u);
  assert.match(dataPage, /19 \/ 20/u);
  assert.match(dataPage, /068270/u);
  assert.match(dataPage, /외부 KRX 증명은 아닙니다/u);
});
