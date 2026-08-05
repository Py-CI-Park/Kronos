import assert from 'node:assert/strict';
import { test } from 'bun:test';
import { summarizeSnapshot } from './evaluationModel';
import { TelemetrySnapshotSchema } from '../../api/telemetryApi';

test('evaluation summary derives only sampled metrics and keeps the sampling label', () => {
  const snapshot = TelemetrySnapshotSchema.parse({
    schema_version: 'kronos_v6_run_telemetry.v1', status: 'OK', run_id: 'a', follow_mode: 'HISTORICAL_SNAPSHOT', sampling: 'HEAD_TAIL_SAMPLE', event_bytes: 1_000, invalid_lines: 0, updated_at: '2026-08-05T00:00:00Z', claims: { live_stream: false, profitability: false },
    points: [
      { step: 1, phase: 'eval', reward: 0.1, equity: 1, loss: null, exploration: null, action_name: 'hold', timestamp: 'a' },
      { step: 2, phase: 'eval', reward: -0.2, equity: 0.9, loss: null, exploration: null, action_name: 'sell', timestamp: 'b' },
      { step: 3, phase: 'eval', reward: 0.05, equity: 0.99, loss: null, exploration: null, action_name: 'buy', timestamp: 'c' },
    ],
  });

  const summary = summarizeSnapshot(snapshot);

  assert.equal(summary.sampleReward, -0.05);
  assert.equal(summary.latestEquity, 0.99);
  assert.ok(summary.sampleDrawdownPct !== null && Math.abs(summary.sampleDrawdownPct + 10) < 1e-9);
  assert.equal(summary.sampling, 'HEAD_TAIL_SAMPLE');
  assert.equal(summary.pointCount, 3);
});
