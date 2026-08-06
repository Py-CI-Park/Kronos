import assert from 'node:assert/strict';
import { test } from 'bun:test';
import { actionDistribution, buildActionTimelineRows } from './actionTimelineModel';
import { TelemetryPointSchema } from '../../api/telemetryApi';

const points = [
  { step: 1, phase: 'eval', reward: 0, equity: 1, loss: null, exploration: null, action_name: 'buy', timestamp: '2026-08-06T09:00:00Z' },
  { step: 2, phase: 'eval', reward: 0, equity: 1, loss: null, exploration: null, action_name: 'hold', timestamp: '2026-08-06T09:01:00Z' },
  { step: 3, phase: 'eval', reward: 0, equity: 1, loss: null, exploration: null, action_name: 'BUY', timestamp: '2026-08-06T09:02:00Z' },
  { step: 4, phase: 'eval', reward: 0, equity: 1, loss: null, exploration: null, action_name: 'exit', timestamp: 'not-a-time' },
].map((point) => TelemetryPointSchema.parse(point));

test('action distribution normalizes names and reports observed shares only', () => {
  assert.deepEqual(actionDistribution(points), [
    { label: 'BUY', count: 2, sharePct: 50 },
    { label: 'HOLD', count: 1, sharePct: 25 },
    { label: 'EXIT', count: 1, sharePct: 25 },
  ]);
});

test('timeline keeps valid timestamps and falls back to deterministic step positions', () => {
  const rows = buildActionTimelineRows(points);
  assert.equal(rows.length, 4);
  assert.deepEqual(rows[0], ['2026-08-06T09:00:00Z', 'BUY', 1, 'eval']);
  assert.deepEqual(rows[3], [4, 'EXIT', 4, 'eval']);
});
