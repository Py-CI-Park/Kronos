import assert from 'node:assert/strict';
import test from 'node:test';

import type { RlTableRow } from './rlApi';
// Node's native TypeScript type-stripping runtime (used by
// `node --experimental-strip-types --test`) requires an explicit file
// extension on every relative import specifier, while this project's
// `tsconfig.json` (moduleResolution: "bundler", no
// `allowImportingTsExtensions`) rejects a literal `.ts` extension in a
// *static* import specifier. A dynamic `import()` is not subject to that
// static specifier check, so it satisfies both the runtime and svelte-check
// without touching tsconfig.json.
import type * as RunMetrics from './runMetrics';

const runMetricsPath = ['.', 'runMetrics.ts'].join('/');
const {
  actionAvailability,
  equityUnitLabel,
  formatEquity,
  formatReward,
  metricsOverlayCompatible,
  resolveMetricMetadata,
  rewardAxisIsPercent,
  rewardPlotValue,
  rewardUnitLabel,
} = (await import(runMetricsPath)) as typeof RunMetrics;

type MetricMeta = RunMetrics.MetricMeta;

function row(overrides: Record<string, unknown>): RlTableRow {
  return overrides as unknown as RlTableRow;
}

// --- formatReward -----------------------------------------------------

test('formatReward: null reward -> NOT_RECORDED', () => {
  const meta = resolveMetricMetadata(row({ reward: null, info: { reward_unit: 'score' } }));
  assert.equal(formatReward(row({ reward: null }), meta), 'NOT_RECORDED');
});

test('formatReward: reward_unit score -> raw (no x100)', () => {
  const r = row({ reward: 0.7, info: { reward_kind: 'raw_reward', reward_unit: 'score' } });
  const meta = resolveMetricMetadata(r);
  const out = formatReward(r, meta);
  assert.ok(!out.includes('%'), `expected no percent sign, got ${out}`);
  assert.ok(out.includes('0.70') || out.includes('0.7'), `expected raw 0.7-ish value, got ${out}`);
});

test('formatReward: reward_unit fraction -> percent (x100 via pct)', () => {
  const r = row({ reward: 0.012, info: { reward_kind: 'return_fraction', reward_unit: 'fraction' } });
  const meta = resolveMetricMetadata(r);
  const out = formatReward(r, meta);
  assert.ok(out.includes('%'), `expected percent sign, got ${out}`);
  assert.ok(out.includes('1.2'), `expected 1.2%-ish value (0.012*100), got ${out}`);
});

test('formatReward: reward_unit percent -> pct as-is (no further x100)', () => {
  const r = row({ reward: 4.5, info: { reward_kind: 'return_percent', reward_unit: 'percent' } });
  const meta = resolveMetricMetadata(r);
  const out = formatReward(r, meta);
  assert.ok(out.includes('%'));
  assert.ok(out.includes('4.5'), `expected 4.5%-ish value (not x100'd to 450), got ${out}`);
});

test('formatReward: unknown/null unit -> raw, no x100', () => {
  const r = row({ reward: 0.5 });
  const meta = resolveMetricMetadata(r);
  assert.equal(meta.reward_unit, null);
  const out = formatReward(r, meta);
  assert.ok(!out.includes('%'));
  assert.ok(out.includes('0.5'), `expected raw 0.5-ish value, got ${out}`);
});

// --- actionAvailability -------------------------------------------------

test('actionAvailability: null/absent action -> NOT_RECORDED', () => {
  assert.equal(actionAvailability(row({ action: null })), 'NOT_RECORDED');
  assert.equal(actionAvailability(row({})), 'NOT_RECORDED');
});

test('actionAvailability: action 0 (real HOLD action) -> RECORDED', () => {
  assert.equal(actionAvailability(row({ action: 0 })), 'RECORDED');
});

test('actionAvailability: info.action_recorded false with non-null action -> NOT_RECORDED', () => {
  assert.equal(
    actionAvailability(row({ action: 1, info: { action_recorded: false } })),
    'NOT_RECORDED',
  );
});

test('actionAvailability: info.action_recorded true -> RECORDED', () => {
  assert.equal(
    actionAvailability(row({ action: null, info: { action_recorded: true } })),
    'RECORDED',
  );
});

// --- metricsOverlayCompatible --------------------------------------------

test('metricsOverlayCompatible: normalized_nav vs krw_nav -> false', () => {
  const a: MetricMeta = resolveMetricMetadata(
    row({ info: { equity_kind: 'normalized_nav', equity_unit: 'normalized' } }),
  );
  const b: MetricMeta = resolveMetricMetadata(
    row({ info: { equity_kind: 'krw_nav', equity_unit: 'krw' } }),
  );
  assert.equal(metricsOverlayCompatible(a, b, 'equity'), false);
});

test('metricsOverlayCompatible: same kind + unit -> true', () => {
  const a: MetricMeta = resolveMetricMetadata(
    row({ info: { equity_kind: 'normalized_nav', equity_unit: 'normalized' } }),
  );
  const b: MetricMeta = resolveMetricMetadata(
    row({ info: { equity_kind: 'normalized_nav', equity_unit: 'normalized' } }),
  );
  assert.equal(metricsOverlayCompatible(a, b, 'equity'), true);
});

test('metricsOverlayCompatible: null kind -> false', () => {
  const a: MetricMeta = resolveMetricMetadata(row({}));
  const b: MetricMeta = resolveMetricMetadata(
    row({ info: { equity_kind: 'normalized_nav', equity_unit: 'normalized' } }),
  );
  assert.equal(metricsOverlayCompatible(a, b, 'equity'), false);
  assert.equal(metricsOverlayCompatible(b, a, 'equity'), false);
});

test('metricsOverlayCompatible: identical explicit normalization -> true', () => {
  const a: MetricMeta = resolveMetricMetadata(
    row({ info: { equity_kind: 'raw_equity', equity_unit: 'krw', normalization: 'nav_v1' } }),
  );
  const b: MetricMeta = resolveMetricMetadata(
    row({ info: { equity_kind: 'cumulative_pnl', equity_unit: 'krw', normalization: 'nav_v1' } }),
  );
  assert.equal(metricsOverlayCompatible(a, b, 'equity'), true);
});

// --- resolveMetricMetadata precedence ------------------------------------

test('resolveMetricMetadata: info > runDefaults > null, no cross-fill', () => {
  const runDefaults: Partial<MetricMeta> = {
    reward_kind: 'raw_reward',
    reward_unit: 'score',
    equity_kind: 'normalized_nav',
    equity_unit: 'normalized',
  };
  const r = row({ info: { reward_unit: 'fraction', action_recorded: true } });
  const meta = resolveMetricMetadata(r, runDefaults);
  // info wins where declared
  assert.equal(meta.reward_unit, 'fraction');
  assert.equal(meta.action_recorded, true);
  // runDefaults fills where info is silent
  assert.equal(meta.reward_kind, 'raw_reward');
  assert.equal(meta.equity_kind, 'normalized_nav');
  assert.equal(meta.equity_unit, 'normalized');
});

test('resolveMetricMetadata: no info/runDefaults -> everything stays null (no cross-fill)', () => {
  const meta = resolveMetricMetadata(row({}));
  assert.equal(meta.reward_kind, null);
  assert.equal(meta.reward_unit, null);
  assert.equal(meta.equity_kind, null);
  assert.equal(meta.equity_unit, null);
  assert.equal(meta.action_recorded, null);
});

test('resolveMetricMetadata: row.info absent falls back to runDefaults only', () => {
  const runDefaults: Partial<MetricMeta> = { equity_kind: 'cumulative_pnl', equity_unit: 'krw' };
  const meta = resolveMetricMetadata(row({}), runDefaults);
  assert.equal(meta.equity_kind, 'cumulative_pnl');
  assert.equal(meta.equity_unit, 'krw');
  assert.equal(meta.reward_kind, null);
});

// --- equity formatting sanity (never x100) --------------------------------

test('formatEquity: null equity -> NOT_RECORDED, never coerced to 0', () => {
  const meta = resolveMetricMetadata(row({ info: { equity_kind: 'krw_nav', equity_unit: 'krw' } }));
  assert.equal(formatEquity(row({ equity: null }), meta), 'NOT_RECORDED');
});

test('formatEquity: never multiplies by 100', () => {
  const r = row({ equity: 1.234, info: { equity_kind: 'normalized_nav', equity_unit: 'normalized' } });
  const meta = resolveMetricMetadata(r);
  const out = formatEquity(r, meta);
  assert.ok(!out.includes('%'));
  assert.ok(out.includes('1.23') || out.includes('1.2'), `expected raw ~1.23 value, got ${out}`);
});

test('rewardUnitLabel / equityUnitLabel: honest labels', () => {
  assert.equal(rewardUnitLabel(resolveMetricMetadata(row({ info: { reward_unit: 'score' } }))), 'score');
  assert.equal(rewardUnitLabel(resolveMetricMetadata(row({ info: { reward_unit: 'fraction' } }))), '%');
  assert.equal(rewardUnitLabel(resolveMetricMetadata(row({}))), 'raw');
  assert.equal(
    equityUnitLabel(resolveMetricMetadata(row({ info: { equity_kind: 'cumulative_pnl' } }))),
    'P&L',
  );
  assert.equal(
    equityUnitLabel(resolveMetricMetadata(row({ info: { equity_unit: 'krw' } }))),
    'KRW',
  );
  assert.equal(equityUnitLabel(resolveMetricMetadata(row({}))), 'raw');
});

// --- rewardPlotValue / rewardAxisIsPercent (chart contract) -----------
test('rewardPlotValue x100 ONLY for fraction; percent/score/unknown raw', () => {
  const frac: MetricMeta = { reward_kind: 'return_fraction', reward_unit: 'fraction', equity_kind: null, equity_unit: null, action_recorded: null };
  const pctm: MetricMeta = { reward_kind: 'return_percent', reward_unit: 'percent', equity_kind: null, equity_unit: null, action_recorded: null };
  const score: MetricMeta = { reward_kind: 'raw_reward', reward_unit: 'score', equity_kind: null, equity_unit: null, action_recorded: null };
  const unknown: MetricMeta = { reward_kind: null, reward_unit: null, equity_kind: null, equity_unit: null, action_recorded: null };
  assert.equal(rewardPlotValue(0.0123, frac), 1.23);   // fraction -> x100
  assert.equal(rewardPlotValue(12.3, pctm), 12.3);     // percent as-is
  assert.equal(rewardPlotValue(0.7, score), 0.7);      // score raw, NOT 70
  assert.equal(rewardPlotValue(0.7, unknown), 0.7);    // unknown raw, NOT 70
});

test('rewardPlotValue null/non-finite -> null (chart gap, not fake 0)', () => {
  const score: MetricMeta = { reward_kind: 'raw_reward', reward_unit: 'score', equity_kind: null, equity_unit: null, action_recorded: null };
  assert.equal(rewardPlotValue(null, score), null);
  assert.equal(rewardPlotValue(undefined, score), null);
  assert.equal(rewardPlotValue('nope', score), null);
});

test('rewardAxisIsPercent true only for fraction/percent', () => {
  const mk = (u: string | null): MetricMeta => ({ reward_kind: null, reward_unit: u, equity_kind: null, equity_unit: null, action_recorded: null });
  assert.equal(rewardAxisIsPercent(mk('fraction')), true);
  assert.equal(rewardAxisIsPercent(mk('percent')), true);
  assert.equal(rewardAxisIsPercent(mk('score')), false);
  assert.equal(rewardAxisIsPercent(mk(null)), false);
});
