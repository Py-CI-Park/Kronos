import assert from 'node:assert/strict';
import { test } from 'bun:test';
import { TelemetrySnapshotSchema, type TelemetryRun } from '../../api/telemetryApi';
import { comparisonChartOptions, comparisonCompatibility, normalizedProgressSeries, shortRunLabel } from './comparisonChartModel';

test('comparison chart reserves separate space for legend, zoom and x-axis labels', () => {
  const option = comparisonChartOptions([], 'equity');
  assert.equal(option.tooltip.confine, true);
  assert.equal(option.legend.top, 0);
  assert.ok(option.grid.bottom >= 104);
  assert.equal(option.xAxis.axisLabel.hideOverlap, true);
  assert.equal(option.xAxis.name, '진행률 (%)');
  assert.equal(option.xAxis.max, 100);
  assert.equal(option.dataZoom.length, 2);
});

test('normalized progress gives short and long runs the same comparison width', () => {
  assert.deepEqual(normalizedProgressSeries([[10, 1], [20, 2], [40, 3]]), [[0, 1], [50, 2], [100, 3]]);
  assert.deepEqual(normalizedProgressSeries([[99, -1]]), [[100, -1]]);
});

test('long run names are shortened without losing their verdict', () => {
  const label = shortRunLabel('stom_orderbook_dqn_constrained_actions', 'NO-GO');
  assert.ok(label.length <= 32);
  assert.match(label, /NO-GO/u);
  assert.match(label, /constrained_actions/u);
});

test('comparison is blocked when run metric units are missing', () => {
  const run: TelemetryRun = { run_id: 'a', name: 'a', lane: 'orderbook', status: 'NO-GO', algorithm: 'DQN', event_bytes: 1, updated_at: 'now' };
  const snapshot = TelemetrySnapshotSchema.parse({
    schema_version: 'kronos_v6_run_telemetry.v1', status: 'OK', run_id: 'a', follow_mode: 'HISTORICAL_SNAPSHOT', sampling: 'FULL_FILE', event_bytes: 1, invalid_lines: 0, updated_at: 'now', claims: { live_stream: false, profitability: false },
    points: [{ step: 1, phase: 'eval', reward: 1, equity: 1.1, loss: null, exploration: null, action_name: 'hold', timestamp: 'now' }],
  });

  const status = comparisonCompatibility([{ run, snapshot }, { run: { ...run, run_id: 'b' }, snapshot }], 'equity');

  assert.equal(status.compatible, false);
  assert.match(status.message, /차단/u);
});
