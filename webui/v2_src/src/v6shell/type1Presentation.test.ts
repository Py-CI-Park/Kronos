import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { initialReportSelection, v6ExactReportHtmlUrl, v6ReportHtmlUrl } from './v6Api';
import {
  TYPE1_FACTS,
  classifyType1State,
  isType1Identity,
  type1StateLabel,
} from './type1Presentation';

test('Type1 facts preserve the frozen research and no-claim contract', () => {
  assert.equal(Object.isFrozen(TYPE1_FACTS), true);
  assert.equal(Object.isFrozen(TYPE1_FACTS.execution), true);
  assert.equal(TYPE1_FACTS.identity.algorithm, 'Sequential MaskablePPO');
  assert.equal(TYPE1_FACTS.execution.priceBasis, 'Exact 15:20 close proxy');
  assert.equal(TYPE1_FACTS.execution.officialClose, false);
  assert.equal(TYPE1_FACTS.execution.roundTripCost, '23bp');
  assert.equal(TYPE1_FACTS.accounting.initialNav, '60M fixed-notional NAV');
  assert.equal(TYPE1_FACTS.accounting.slotNotional, '5M');
  assert.equal(TYPE1_FACTS.accounting.maxSlots, 10);
  assert.equal(TYPE1_FACTS.accounting.maxExposure, '50M');
  assert.equal(TYPE1_FACTS.accounting.reserve, '10M');
  assert.equal(TYPE1_FACTS.evaluation.fixedSeeds, 5);
  assert.equal(TYPE1_FACTS.evaluation.freshOos, 'NOT_RUN');
  assert.equal(TYPE1_FACTS.evaluation.freshOosLifecycle, 'ACCUMULATING_NOT_RUN');
  assert.equal(TYPE1_FACTS.claims.liveOrProfitabilityClaim, false);
});

test('Type1 identity excludes the M3E LinUCB contextual-bandit family', () => {
  assert.equal(isType1Identity({ family: 'TYPE1', algorithm: 'Sequential MaskablePPO' }), true);
  assert.equal(isType1Identity('sequential MaskablePPO'), true);
  assert.equal(isType1Identity({ family: 'M3E', algorithm: 'LinUCB contextual-bandit' }), false);
  assert.equal(isType1Identity({ family: 'TYPE1', algorithm: 'LinUCB' }), false);
});

test('Type1 lifecycle state remains fail-closed for adverse and missing evidence', () => {
  assert.equal(classifyType1State({ integrity: 'HASH_MISMATCH', verdict: 'NO_GO' }), 'TAMPERED');
  assert.equal(classifyType1State({ status: 'BLOCKED_MISSING_LINEAGE' }), 'BLOCKED');
  assert.equal(classifyType1State({ verdict: 'INCONCLUSIVE_NO_GO' }), 'NO_GO');
  assert.equal(classifyType1State({ state: 'COMPLETE', verdict_candidate: { value: 'NO_GO' } }), 'NO_GO');
  assert.equal(classifyType1State({ test_state: 'ACCUMULATING_NOT_RUN' }), 'NOT_RUN');
  assert.equal(classifyType1State(undefined, true), 'LOADING');
  assert.equal(classifyType1State({ status: 'COMPLETE' }), 'EMPTY');
  assert.equal(type1StateLabel('NOT_RUN'), 'NOT RUN');
});

test('report URLs require an explicit SHA for report-page viewing', () => {
  assert.equal(
    v6ExactReportHtmlUrl('dataset 1', 'train/1', 'sha 256/한글', true),
    '/api/v6/report-html?dataset=dataset%201&train=train%2F1&report_sha256=sha%20256%2F%ED%95%9C%EA%B8%80&download=1',
  );
  assert.equal(v6ExactReportHtmlUrl('dataset 1', 'train/1', undefined), null);
  assert.equal(
    v6ReportHtmlUrl('dataset 1', 'train/1', true),
    '/api/v6/report-html?dataset=dataset%201&train=train%2F1&download=1',
  );
});

test('report page begins without an implicit report selection', () => {
  assert.equal(initialReportSelection(), null);
  const source = readFileSync(new URL('./pages/ReportPage.svelte', import.meta.url), 'utf8');
  assert.match(source, /const revisionsFor = \(entry: V6ReportEntry\): readonly V6ReportRevision\[\] => entry\.revisions \?\? entry\.reports \?\? \[\]/);
  assert.match(source, /v6ExactReportHtmlUrl/);
  assert.doesNotMatch(source, /await selectReport\(/);
});
