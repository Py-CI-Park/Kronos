import assert from 'node:assert/strict';
import test from 'node:test';

import type * as PerformanceBudget from './performanceBudget';

// Node's native TypeScript type-stripping runtime (used by
// `node --experimental-strip-types --test`) requires an explicit file
// extension on every relative import specifier, while this project's
// `tsconfig.json` (moduleResolution: "bundler", no
// `allowImportingTsExtensions`) rejects a literal `.ts` extension in a
// *static* specifier. A dynamic import() satisfies both.
const performanceBudgetPath = ['.', 'performanceBudget.ts'].join('/');
const {
  PERFORMANCE_BUDGET_LIMITS_MS,
  RETRY_VISIBLE_KEY,
  evaluatePerformanceBudget,
  percentile95,
}: typeof PerformanceBudget = await import(performanceBudgetPath);

const PASSING = Object.freeze({
  firstCriticalCardColdMs: 3_000,
  firstCriticalCardWarmMs: 1_500,
  fullCriticalHydrationColdMs: 10_000,
  fullCriticalHydrationWarmMs: 6_000,
  warmCriticalApiMs: 2_000,
  coldCriticalApiMs: 5_000,
  isolatedCardTimeoutMs: 20_500,
  isolatedCardRetryVisible: true,
  commandPaletteOpenMs: 100,
  thousandItemQueryFilterMs: 150,
});

test('budget limits match the exact contract values', () => {
  assert.deepEqual(PERFORMANCE_BUDGET_LIMITS_MS, {
    firstCriticalCardColdMs: 3_000,
    firstCriticalCardWarmMs: 1_500,
    fullCriticalHydrationColdMs: 10_000,
    fullCriticalHydrationWarmMs: 6_000,
    warmCriticalApiMs: 2_000,
    coldCriticalApiMs: 5_000,
    isolatedCardTimeoutMs: 20_500,
    commandPaletteOpenMs: 100,
    thousandItemQueryFilterMs: 150,
  });
  assert.equal(RETRY_VISIBLE_KEY, 'isolatedCardRetryVisible');
});

test('a capture sitting exactly on every limit passes with no failures', () => {
  assert.deepEqual(evaluatePerformanceBudget(PASSING), { pass: true, failures: [] });
});

test('one millisecond over any single duration budget fails that budget only', () => {
  const overBy1: [keyof typeof PASSING, number][] = [
    ['firstCriticalCardColdMs', 3_001],
    ['firstCriticalCardWarmMs', 1_501],
    ['fullCriticalHydrationColdMs', 10_001],
    ['fullCriticalHydrationWarmMs', 6_001],
    ['warmCriticalApiMs', 2_001],
    ['coldCriticalApiMs', 5_001],
    ['isolatedCardTimeoutMs', 20_501],
    ['commandPaletteOpenMs', 101],
    ['thousandItemQueryFilterMs', 151],
  ];
  for (const [key, value] of overBy1) {
    const result = evaluatePerformanceBudget({ ...PASSING, [key]: value });
    assert.equal(result.pass, false, `${key} should fail at ${value}`);
    assert.deepEqual(result.failures, [`${key}:${value}>${PASSING[key]}`]);
  }
});

test('missing metrics fail closed as invalid rather than passing by default', () => {
  const withoutColdApi = { ...PASSING } as Record<string, unknown>;
  delete withoutColdApi.coldCriticalApiMs;
  const result = evaluatePerformanceBudget(withoutColdApi as unknown as PerformanceBudget.PerformanceBudgetSample);
  assert.equal(result.pass, false);
  assert.deepEqual(result.failures, ['coldCriticalApiMs:invalid']);
});

test('non-finite and negative metrics fail closed as invalid', () => {
  for (const bad of [Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY, -1]) {
    const result = evaluatePerformanceBudget({ ...PASSING, warmCriticalApiMs: bad });
    assert.equal(result.pass, false, `warmCriticalApiMs=${bad} must fail`);
    assert.deepEqual(result.failures, ['warmCriticalApiMs:invalid']);
  }
});

test('multiple simultaneous breaches are all reported, not just the first', () => {
  const result = evaluatePerformanceBudget({
    ...PASSING,
    firstCriticalCardColdMs: 3_001,
    coldCriticalApiMs: 5_500,
    isolatedCardRetryVisible: false,
  });
  assert.equal(result.pass, false);
  assert.deepEqual(result.failures, [
    'firstCriticalCardColdMs:3001>3000',
    'coldCriticalApiMs:5500>5000',
    'isolatedCardRetryVisible:missing_or_false',
  ]);
});

// ─────────────────────── RETRY visibility requirement ───────────────────────

test('isolated card RETRY affordance must be explicitly true, not merely truthy or absent', () => {
  for (const bad of [false, undefined, null, 1, 'true', 0]) {
    const result = evaluatePerformanceBudget({
      ...PASSING,
      isolatedCardRetryVisible: bad as unknown as boolean,
    });
    assert.equal(result.pass, false, `retry visible=${String(bad)} must fail`);
    assert.deepEqual(result.failures, ['isolatedCardRetryVisible:missing_or_false']);
  }
});

test('isolated card timeout breach and missing RETRY are both reported together', () => {
  const result = evaluatePerformanceBudget({
    ...PASSING,
    isolatedCardTimeoutMs: 20_501,
    isolatedCardRetryVisible: false,
  });
  assert.deepEqual(result.failures, ['isolatedCardTimeoutMs:20501>20500', 'isolatedCardRetryVisible:missing_or_false']);
});

// ────────────────────────── percentile95 reduction ───────────────────────────

test('percentile95 uses nearest-rank and never the mean, so a slow tail is not averaged away', () => {
  const samples = [10, 12, 11, 13, 12, 900];
  const p95 = percentile95(samples);
  const mean = samples.reduce((sum, value) => sum + value, 0) / samples.length;
  assert.equal(p95, 900);
  assert.ok((p95 ?? 0) > mean, 'p95 must reflect the outlier tail, not the smoothed mean');
});

test('percentile95 rejects empty, missing, non-finite, and negative samples as invalid', () => {
  assert.equal(percentile95([]), null);
  assert.equal(percentile95([1, 2, Number.NaN]), null);
  assert.equal(percentile95([1, 2, -1]), null);
  assert.equal(percentile95([1, 2, Number.POSITIVE_INFINITY]), null);
});

test('a budget fed raw percentile samples fails when the reduced p95 breaches the limit', () => {
  const result = evaluatePerformanceBudget({
    ...PASSING,
    warmCriticalApiMs: [500, 600, 700, 2_500],
  });
  assert.equal(result.pass, false);
  assert.deepEqual(result.failures, ['warmCriticalApiMs:2500>2000']);
});

test('a budget fed raw percentile samples passes when the reduced p95 sits within the limit', () => {
  const result = evaluatePerformanceBudget({
    ...PASSING,
    commandPaletteOpenMs: [40, 50, 60, 70, 80, 90],
  });
  assert.deepEqual(result, { pass: true, failures: [] });
});

test('an unresolvable sample array for a metric fails closed as invalid, not as a pass', () => {
  const result = evaluatePerformanceBudget({
    ...PASSING,
    thousandItemQueryFilterMs: [] as unknown as number,
  });
  assert.equal(result.pass, false);
  assert.deepEqual(result.failures, ['thousandItemQueryFilterMs:invalid']);
});
