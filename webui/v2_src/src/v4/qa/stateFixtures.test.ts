import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import type * as StateFixtures from './stateFixtures';

const stateFixturesPath = ['.', 'stateFixtures.ts'].join('/');
const {
  V4_QA_TAB_IDS,
  V4_QA_STATE_IDS,
  V4_QA_FALSE_LOCK_KEYS,
  V4_QA_STATE_FIXTURES,
  V4_QA_STATE_LEGEND,
  V4_QA_REQUIRED_TAB_COUNT,
  V4_QA_REQUIRED_STATE_COUNT,
  V4_QA_REQUIRED_FIXTURE_COUNT,
  V4_QA_LIVE_SAFETY_PHRASES,
  validateFixtureSet,
  assertValidFixtureSet,
  getFixture,
}: typeof StateFixtures = await import(stateFixturesPath);

const frameSource = readFileSync(new URL('./V4LegacyDomainFrame.svelte', import.meta.url), 'utf8');

test('declares exactly the canonical 12 tab ids and 9 lifecycle states with no duplicates', () => {
  assert.equal(V4_QA_TAB_IDS.length, 12);
  assert.equal(new Set(V4_QA_TAB_IDS).size, 12);
  assert.equal(V4_QA_STATE_IDS.length, 9);
  assert.equal(new Set(V4_QA_STATE_IDS).size, 9);
  assert.deepEqual(
    [...V4_QA_STATE_IDS],
    ['loading', 'empty', 'error', 'stale', 'live', 'replay', 'completed', 'missing', 'no_go'],
  );
  assert.equal(V4_QA_REQUIRED_TAB_COUNT, 12);
  assert.equal(V4_QA_REQUIRED_STATE_COUNT, 9);
  assert.equal(V4_QA_REQUIRED_FIXTURE_COUNT, 108);
});

test('the canonical fixture matrix is exactly 12 tabs x 9 states = 108 rows, one per pair', () => {
  assert.equal(V4_QA_STATE_FIXTURES.length, 108);
  const keys = new Set(V4_QA_STATE_FIXTURES.map((fixture) => `${fixture.tabId}::${fixture.stateId}`));
  assert.equal(keys.size, 108);
  for (const tabId of V4_QA_TAB_IDS) {
    for (const stateId of V4_QA_STATE_IDS) {
      assert.ok(keys.has(`${tabId}::${stateId}`), `missing ${tabId}::${stateId}`);
    }
  }
});

test('every fixture carries a non-empty, unique, Korean-first label and evidence label', () => {
  const evidenceLabels = new Set<string>();
  for (const fixture of V4_QA_STATE_FIXTURES) {
    assert.match(fixture.tabLabelKo, /[\u3131-\uD79D]/, `${fixture.tabId} tab label must contain Korean text`);
    assert.match(fixture.stateLabelKo, /[\u3131-\uD79D]|NO-GO/, `${fixture.stateId} state label must contain Korean text or NO-GO`);
    assert.match(fixture.detailKo, /[\u3131-\uD79D]/, `${fixture.tabId}/${fixture.stateId} detail must contain Korean text`);
    assert.ok(fixture.evidenceLabel.trim().length > 0, 'evidence label must not be empty');
    assert.ok(!evidenceLabels.has(fixture.evidenceLabel), `duplicate evidence label ${fixture.evidenceLabel}`);
    evidenceLabels.add(fixture.evidenceLabel);
    assert.equal(fixture.optimisticLock, false);
    assert.equal(fixture.claimsProfit, false);
    assert.equal(fixture.claimsOrder, false);
  }
});

test('the canonical fixture matrix passes fail-closed validation with zero issues', () => {
  const result = validateFixtureSet(V4_QA_STATE_FIXTURES);
  assert.equal(result.ok, true);
  assert.deepEqual(result.issues, []);
  assert.equal(result.fixtureCount, 108);
  assert.doesNotThrow(() => assertValidFixtureSet(V4_QA_STATE_FIXTURES));
});

test('getFixture returns the exact fixture for a tab/state pair and throws for unknown pairs', () => {
  const fixture = getFixture('rl', 'no_go');
  assert.equal(fixture.tabId, 'rl');
  assert.equal(fixture.stateId, 'no_go');
  assert.throws(() => getFixture('rl' as never, 'not-a-state' as never));
});

test('rejects a fixture set with a missing required state', () => {
  const missingOne = V4_QA_STATE_FIXTURES.filter((fixture) => !(fixture.tabId === 'docs' && fixture.stateId === 'stale'));
  const result = validateFixtureSet(missingOne);
  assert.equal(result.ok, false);
  assert.ok(result.issues.some((issue) => issue.code === 'MISSING_STATE' && issue.tabId === 'docs' && issue.stateId === 'stale'));
  assert.throws(() => assertValidFixtureSet(missingOne), /MISSING_STATE/);
});

test('rejects a fixture set with a duplicate tab/state pair', () => {
  const duplicated = [...V4_QA_STATE_FIXTURES, V4_QA_STATE_FIXTURES[0]];
  const result = validateFixtureSet(duplicated);
  assert.equal(result.ok, false);
  assert.ok(result.issues.some((issue) => issue.code === 'DUPLICATE_FIXTURE'));
  assert.throws(() => assertValidFixtureSet(duplicated), /DUPLICATE_FIXTURE/);
});

test('rejects any fixture that declares an optimistic lock', () => {
  const withOptimisticLock = V4_QA_STATE_FIXTURES.map((fixture) =>
    fixture.tabId === 'settings' && fixture.stateId === 'completed' ? { ...fixture, optimisticLock: true } : fixture,
  );
  const result = validateFixtureSet(withOptimisticLock);
  assert.equal(result.ok, false);
  assert.ok(result.issues.some((issue) => issue.code === 'OPTIMISTIC_LOCK_REJECTED'));
});

test('rejects unlabelled evidence (empty or whitespace-only evidenceLabel)', () => {
  const unlabelled = V4_QA_STATE_FIXTURES.map((fixture) =>
    fixture.tabId === 'artifacts' && fixture.stateId === 'error' ? { ...fixture, evidenceLabel: '   ' } : fixture,
  );
  const result = validateFixtureSet(unlabelled);
  assert.equal(result.ok, false);
  assert.ok(result.issues.some((issue) => issue.code === 'UNLABELLED_EVIDENCE'));
});

test('rejects unsafe profitability claims regardless of state', () => {
  const unsafeProfit = V4_QA_STATE_FIXTURES.map((fixture) =>
    fixture.tabId === 'rl' && fixture.stateId === 'completed' ? { ...fixture, claimsProfit: true } : fixture,
  );
  const result = validateFixtureSet(unsafeProfit);
  assert.equal(result.ok, false);
  assert.ok(result.issues.some((issue) => issue.code === 'UNSAFE_PROFIT_CLAIM'));
});

test('rejects unsafe live broker/order claims regardless of state', () => {
  const unsafeOrder = V4_QA_STATE_FIXTURES.map((fixture) =>
    fixture.tabId === 'rl' && fixture.stateId === 'live' ? { ...fixture, claimsOrder: true } : fixture,
  );
  const result = validateFixtureSet(unsafeOrder);
  assert.equal(result.ok, false);
  assert.ok(result.issues.some((issue) => issue.code === 'UNSAFE_ORDER_CLAIM'));
});

test('rejects a live claim outside the live state, and a live claim without the required safety phrases', () => {
  const liveOnWrongState = V4_QA_STATE_FIXTURES.map((fixture) =>
    fixture.tabId === 'rl' && fixture.stateId === 'replay' ? { ...fixture, claimsLive: true } : fixture,
  );
  const resultWrongState = validateFixtureSet(liveOnWrongState);
  assert.equal(resultWrongState.ok, false);
  assert.ok(resultWrongState.issues.some((issue) => issue.code === 'UNSAFE_LIVE_CLAIM' && issue.stateId === 'replay'));

  const liveWithoutSafetyNote = V4_QA_STATE_FIXTURES.map((fixture) =>
    fixture.tabId === 'rl' && fixture.stateId === 'live' ? { ...fixture, safetyNoteKo: '실시간입니다.' } : fixture,
  );
  const resultNoNote = validateFixtureSet(liveWithoutSafetyNote);
  assert.equal(resultNoNote.ok, false);
  assert.ok(resultNoNote.issues.some((issue) => issue.code === 'UNSAFE_LIVE_CLAIM' && issue.tabId === 'rl' && issue.stateId === 'live'));

  for (const fixture of V4_QA_STATE_FIXTURES) {
    if (fixture.stateId === 'live') {
      for (const phrase of V4_QA_LIVE_SAFETY_PHRASES) {
        assert.ok(fixture.safetyNoteKo.includes(phrase), `${fixture.tabId} live fixture must include "${phrase}"`);
      }
    }
  }
});

test('exposes exactly six canonical false lock keys, matching the shared V4 promotion-lock vocabulary', () => {
  assert.equal(V4_QA_FALSE_LOCK_KEYS.length, 6);
  assert.equal(new Set(V4_QA_FALSE_LOCK_KEYS).size, 6);
  assert.deepEqual(
    [...V4_QA_FALSE_LOCK_KEYS].sort(),
    [
      'go_summary_allowed',
      'live_broker_order_allowed',
      'model_build_allowed',
      'paper_forward_allowed',
      'profitability_claim_allowed',
      'promotion_allowed',
    ].sort(),
  );
});

test('the tab-agnostic state legend has exactly 9 rows matching V4_QA_STATE_IDS', () => {
  assert.equal(V4_QA_STATE_LEGEND.length, 9);
  assert.deepEqual(
    V4_QA_STATE_LEGEND.map((row) => row.stateId),
    [...V4_QA_STATE_IDS],
  );
  for (const row of V4_QA_STATE_LEGEND) {
    assert.ok(row.labelKo.length > 0);
    assert.ok(row.safetyNoteKo.length > 0);
  }
});

test('component source carries the fixed V4LegacyDomainFrame signature, root marker, and both surface markers', () => {
  assert.match(frameSource, /data-v4-legacy-domain-frame/);
  assert.match(frameSource, /data-surface=\{surface\}/);
  assert.match(frameSource, /surface:\s*['"]diagnostics['"]\s*\|\s*['"]daily-guide['"]/);
  assert.doesNotMatch(frameSource, /\{@html/);
  assert.doesNotMatch(frameSource, /\bfetch\s*\(/);
  assert.doesNotMatch(frameSource, /import\.meta\.env/);
  assert.doesNotMatch(frameSource, /process\.env/);
});

test('component source renders the legacy child snippet visibly, inside an open non-lazy disclosure', () => {
  const legacyIndex = frameSource.indexOf('data-v4-legacy-domain-legacy');
  assert.ok(legacyIndex > -1, 'legacy marker must be present');

  const renderChildrenIndex = frameSource.indexOf('{@render children');
  assert.ok(renderChildrenIndex > legacyIndex, 'children snippet must render after the legacy marker opens');

  const precedingWindow = frameSource.slice(Math.max(0, legacyIndex - 400), legacyIndex);
  assert.match(precedingWindow, /\bopen\b/, 'legacy disclosure must be open, not hidden by default');
  assert.doesNotMatch(precedingWindow, /\blazy\b/, 'legacy disclosure must not be lazy (must render immediately, not hidden)');
});

test('component source renders the exact six false locks (via the shared lock vocabulary) and a state legend', () => {
  assert.match(frameSource, /V4_QA_FALSE_LOCK_KEYS/);
  assert.match(frameSource, /PromotionLocksGrid/);
  assert.match(frameSource, /data-v4-legacy-domain-locks/);
  assert.match(frameSource, /data-v4-legacy-domain-legend/);
  assert.match(frameSource, /data-v4-legacy-domain-posture/);
  assert.equal(V4_QA_FALSE_LOCK_KEYS.length, 6);
});

test('component source declares a research-only, no-hidden-evidence posture', () => {
  assert.match(frameSource, /연구/);
  assert.match(frameSource, /숨겨진 증거/);
});
test('component source contains the always-visible legacy child in a local, keyboard-accessible horizontal scroll region, not document-widening or hidden', () => {
  const scrollIndex = frameSource.indexOf('data-v4-legacy-domain-legacy-scroll');
  assert.ok(scrollIndex > -1, 'legacy child must have a dedicated local-scroll containment marker');

  const legacyIndex = frameSource.indexOf('data-v4-legacy-domain-legacy');
  assert.ok(legacyIndex > -1 && legacyIndex < scrollIndex, 'scroll region must nest inside the legacy child marker');

  const renderChildrenIndex = frameSource.indexOf('{@render children');
  assert.ok(
    renderChildrenIndex > scrollIndex,
    'children snippet must render inside the local scroll region, not before it',
  );

  const scrollOpenTagWindow = frameSource.slice(scrollIndex, renderChildrenIndex);
  assert.match(scrollOpenTagWindow, /tabindex="0"/, 'scroll region must be keyboard-focusable when scrollable');
  assert.match(scrollOpenTagWindow, /role="tabpanel"/, 'scroll region must expose an accessible, focusable region role');
  assert.match(scrollOpenTagWindow, /aria-label="[^"]+"/, 'scroll region must be labeled for assistive tech');

  const styleIndex = frameSource.indexOf('<style>');
  assert.ok(styleIndex > -1, 'component must declare a style block');
  const styleSource = frameSource.slice(styleIndex);

  const scrollRuleMatch = styleSource.match(/\.legacy-child-scroll\s*\{[^}]*\}/);
  assert.ok(scrollRuleMatch, '.legacy-child-scroll containment rule must exist');
  const scrollRule = scrollRuleMatch[0];
  assert.match(scrollRule, /overflow-x:\s*auto/, 'wide legacy content must scroll locally, not widen the document');
  assert.match(scrollRule, /min-width:\s*0/, 'scroll region must not force intrinsic min-content width onto ancestors');
  assert.match(scrollRule, /max-width:\s*100%/, 'scroll region must stay within the available inline size');

  const legacyChildRuleMatch = styleSource.match(/\.legacy-child\s*\{[^}]*\}/);
  assert.ok(legacyChildRuleMatch, '.legacy-child containment rule must exist');
  const legacyChildRule = legacyChildRuleMatch[0];
  assert.match(legacyChildRule, /min-width:\s*0/, 'legacy child wrapper must not force intrinsic width onto ancestors');
  assert.match(legacyChildRule, /max-width:\s*100%/, 'legacy child wrapper must stay within the available inline size');

  assert.match(
    styleSource,
    /\.legacy-child-scroll:focus-visible\s*\{[^}]*outline:/,
    'scroll region must render a visible focus outline when focused',
  );

  // Evidence must remain reachable via local scroll, never clipped out of existence.
  assert.doesNotMatch(styleSource, /\.legacy-child(-scroll)?\s*\{[^}]*overflow:\s*hidden/);
  assert.doesNotMatch(styleSource, /\.legacy-child(-scroll)?\s*\{[^}]*overflow:\s*clip/);
});

test('positive fixture: the local-scroll containment guard fails on a document-widening, non-scrollable legacy wrapper', () => {
  const taintedSource = [
    '<div class="legacy-child" data-v4-legacy-domain-legacy>',
    '  {@render children()}',
    '</div>',
    '<style>',
    '  .legacy-child { min-width: 0; max-width: 100%; }',
    '</style>',
  ].join('\n');

  assert.equal(taintedSource.indexOf('data-v4-legacy-domain-legacy-scroll'), -1);
  const scrollRuleMatch = taintedSource.match(/\.legacy-child-scroll\s*\{[^}]*\}/);
  assert.equal(scrollRuleMatch, null);
});
