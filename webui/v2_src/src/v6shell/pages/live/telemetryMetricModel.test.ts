import assert from 'node:assert/strict';
import { test } from 'bun:test';
import { TelemetryPointSchema } from '../../api/telemetryApi';
import {
  equityPresentation,
  metricIdentity,
  metricOverlayCompatible,
  rewardPresentation,
} from './telemetryMetricModel';

const point = (overrides: Record<string, unknown>) => TelemetryPointSchema.parse({
  step: 1,
  phase: 'eval',
  reward: 0.01,
  equity: 1.02,
  loss: null,
  exploration: null,
  action_name: 'hold',
  timestamp: '2026-08-09T00:00:00Z',
  ...overrides,
});

test('normalized NAV converts to percent and permits drawdown', () => {
  const points = [
    point({ step: 1, equity: 1, equity_kind: 'normalized_nav', equity_unit: 'normalized' }),
    point({ step: 2, equity: 0.9, equity_kind: 'normalized_nav', equity_unit: 'normalized' }),
  ];

  const presentation = equityPresentation(points);

  assert.equal(presentation.identity.state, 'declared');
  assert.deepEqual(presentation.rows, [[1, 0], [2, -10]]);
  assert.deepEqual(presentation.drawdownRows, [[1, 0], [2, -10]]);
  assert.equal(presentation.latestLabel, '-10.00%');
});

test('cumulative PnL stays in KRW and never manufactures drawdown', () => {
  const points = [
    point({ step: 1, equity: 392_062, equity_kind: 'cumulative_pnl', equity_unit: 'krw' }),
    point({ step: 2, equity: -848_545, equity_kind: 'cumulative_pnl', equity_unit: 'krw' }),
  ];

  const presentation = equityPresentation(points);

  assert.deepEqual(presentation.rows, [[1, 392_062], [2, -848_545]]);
  assert.deepEqual(presentation.drawdownRows, []);
  assert.match(presentation.latestLabel, /848,545/u);
  assert.match(presentation.axisLabel, /원/u);
});

test('legacy and mixed metadata remain explicit and fail comparison closed', () => {
  const legacy = [point({ equity: 1.1 })];
  const normalized = [point({ equity_kind: 'normalized_nav', equity_unit: 'normalized' })];
  const mixed = [
    ...normalized,
    point({ step: 2, equity_kind: 'cumulative_pnl', equity_unit: 'krw' }),
  ];

  assert.equal(metricIdentity(legacy, 'equity').state, 'missing');
  assert.equal(metricIdentity(mixed, 'equity').state, 'mixed');
  assert.equal(metricOverlayCompatible(legacy, normalized, 'equity'), false);
  assert.match(equityPresentation(legacy).notice, /MISSING/u);
});

test('reward labels declared fractions without claiming economic return', () => {
  const points = [
    point({ reward: 0.01, reward_kind: 'return_fraction', reward_unit: 'fraction' }),
    point({ step: 2, reward: -0.004, reward_kind: 'return_fraction', reward_unit: 'fraction' }),
  ];

  const presentation = rewardPresentation(points);

  assert.equal(presentation.identity.state, 'declared');
  assert.deepEqual(presentation.rows, [[1, 0.01], [2, 0.006]]);
  assert.match(presentation.latestLabel, /0\.006/u);
});
