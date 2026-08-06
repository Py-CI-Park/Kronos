import assert from 'node:assert/strict';
import { test } from 'bun:test';
import { comparisonChartOptions, shortRunLabel } from './comparisonChartModel';

test('comparison chart reserves separate space for legend, zoom and x-axis labels', () => {
  const option = comparisonChartOptions([], 'equity');
  assert.equal(option.tooltip.confine, true);
  assert.equal(option.legend.top, 0);
  assert.ok(option.grid.bottom >= 82);
  assert.equal(option.xAxis.axisLabel.hideOverlap, true);
  assert.equal(option.dataZoom.length, 2);
});

test('long run names are shortened without losing their verdict', () => {
  const label = shortRunLabel('stom_orderbook_dqn_constrained_actions', 'NO-GO');
  assert.ok(label.length <= 32);
  assert.match(label, /NO-GO/u);
  assert.match(label, /constrained_actions/u);
});
