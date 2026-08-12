import { test } from 'node:test';
import assert from 'node:assert/strict';
// Node's --experimental-strip-types runtime requires an explicit `.ts`
// extension on relative imports, while this project's tsconfig (bundler
// resolution, no allowImportingTsExtensions) rejects a literal `.ts` in a
// *static* specifier. A dynamic import() satisfies both (see requestGate.test.ts).
import type * as ChartA11y from './chartA11y';

const chartA11yPath = ['.', 'chartA11y.ts'].join('/');
const { chartAccessibleName, deriveChartSummary, deriveChartTable }: typeof ChartA11y = await import(chartA11yPath);
test('chartAccessibleName: explicit caption wins', () => {
  assert.equal(chartAccessibleName({ title: { text: 'ignored' } }, 'Equity curve'), 'Equity curve');
});

test('chartAccessibleName: falls back to title text + subtext', () => {
  assert.equal(chartAccessibleName({ title: { text: 'Loss', subtext: 'per step' } }), 'Loss — per step');
});

test('chartAccessibleName: generic fallback when nothing usable', () => {
  assert.equal(chartAccessibleName({}), '데이터 차트');
  assert.equal(chartAccessibleName(null), '데이터 차트');
  assert.equal(chartAccessibleName({ title: { text: '   ' } }), '데이터 차트');
});

test('deriveChartSummary: count, first→last direction, min, max per series', () => {
  const s = deriveChartSummary(
    { series: [{ name: 'nav', data: [1, 3, 2, 5] }] },
    'NAV',
  );
  assert.match(s, /NAV\./);
  assert.match(s, /nav: 4개 지점/);
  assert.match(s, /처음 1 → 마지막 5 \(상승\)/);
  assert.match(s, /최소 1, 최대 5/);
});

test('deriveChartSummary: downward and flat directions', () => {
  assert.match(deriveChartSummary({ series: [{ name: 'a', data: [5, 1] }] }), /하락/);
  assert.match(deriveChartSummary({ series: [{ name: 'a', data: [2, 2] }] }), /변화 없음/);
});

test('deriveChartSummary: ignores null/non-numeric points (no fabricated 0)', () => {
  // A single real value of 4 with holes must NOT report min 0.
  const s = deriveChartSummary({ series: [{ name: 'a', data: [null, 4, undefined, NaN] }] });
  assert.match(s, /1개 지점/);
  assert.match(s, /최소 4, 최대 4/);
});

test('deriveChartSummary: empty/absent series', () => {
  assert.match(deriveChartSummary({ series: [] }), /표시할 데이터 없음/);
  assert.match(deriveChartSummary({ series: [{ name: 'a', data: [] }] }), /수치 데이터 없음/);
});

test('deriveChartSummary: multiple series joined', () => {
  const s = deriveChartSummary({ series: [{ name: 'a', data: [1, 2] }, { name: 'b', data: [9, 3] }] });
  assert.match(s, /a: 2개 지점/);
  assert.match(s, /b: 2개 지점/);
});

test('deriveChartTable: columns from series names, rows from xAxis categories', () => {
  const t = deriveChartTable({
    xAxis: { data: ['d1', 'd2'] },
    series: [{ name: 'net', data: [1, 2] }, { name: 'mdd', data: [-1, -2] }],
  });
  assert.ok(t);
  assert.deepEqual(t.columns, ['항목', 'net', 'mdd']);
  assert.deepEqual(t.rows[0], ['d1', 1, -1]);
  assert.deepEqual(t.rows[1], ['d2', 2, -2]);
});

test('deriveChartTable: missing points become em dash, not 0', () => {
  const t = deriveChartTable({ series: [{ name: 'a', data: [null, 3] }] });
  assert.ok(t);
  assert.deepEqual(t.rows[0], ['1', '—']);
  assert.deepEqual(t.rows[1], ['2', 3]);
});

test('deriveChartTable: scatter [x,y] tuples tabulate the plotted y', () => {
  const t = deriveChartTable({ series: [{ name: 'pts', data: [[0.1, 4], [0.2, 5]] }] });
  assert.ok(t);
  assert.deepEqual(t.rows[0], ['1', 4]);
  assert.deepEqual(t.rows[1], ['2', 5]);
});

test('deriveChartTable: scatter metadata after [x,y] does not hide the plotted y', () => {
  const t = deriveChartTable({
    series: [{
      name: 'observed action',
      data: [['15:30 · step 1', 2, 1, 'VALIDATION_REPLAY']],
    }],
  });

  assert.ok(t);
  assert.deepEqual(t.rows[0], ['1', 2]);
});

test('deriveChartTable: caps at 80 rows for large series', () => {
  const data = Array.from({ length: 500 }, (_, i) => i);
  const t = deriveChartTable({ series: [{ name: 'loss', data }] });
  assert.ok(t);
  assert.equal(t.rows.length, 80);
});

test('deriveChartTable: null when no series or no data', () => {
  assert.equal(deriveChartTable({}), null);
  assert.equal(deriveChartTable({ series: [{ name: 'a', data: [] }] }), null);
});
