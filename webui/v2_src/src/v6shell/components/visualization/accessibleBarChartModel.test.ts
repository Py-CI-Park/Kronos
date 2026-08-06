import assert from 'node:assert/strict';
import test from 'node:test';
import { buildBarChartRows } from './accessibleBarChartModel';

test('bar rows preserve labels and display values while scaling against observed maximum', () => {
  const rows = buildBarChartRows([
    { label: 'NO-GO', value: 5 },
    { label: 'COMPLETE', value: 10, displayValue: '10 runs' },
  ]);

  assert.deepEqual(rows.map((row) => ({ label: row.label, display: row.display, width: row.widthPercent })), [
    { label: 'NO-GO', display: '5', width: 50 },
    { label: 'COMPLETE', display: '10 runs', width: 100 },
  ]);
});

test('zero and negative observations render zero-width bars instead of fabricated pixels', () => {
  const rows = buildBarChartRows([{ label: 'SEALED', value: 0 }, { label: 'INVALID', value: -3 }]);
  assert.deepEqual(rows.map((row) => row.widthPercent), [0, 0]);
});
