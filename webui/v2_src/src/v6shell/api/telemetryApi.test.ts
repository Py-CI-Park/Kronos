import assert from 'node:assert/strict';
import { test } from 'bun:test';
import { TelemetryRunsSchema, TelemetrySnapshotSchema, buildTelemetryUrl } from './telemetryApi';

test('telemetry schemas preserve follow mode sampling and metric points', () => {
  const runs = TelemetryRunsSchema.parse({
    schema_version: 'kronos_v6_telemetry_runs.v1',
    status: 'OK',
    total: 1,
    items: [{ run_id: 'daily/seed-1', name: 'seed-1', status: 'NO-GO', algorithm: 'DQN', event_bytes: 2048, updated_at: '2026-08-05T00:00:00Z' }],
  });
  const snapshot = TelemetrySnapshotSchema.parse({
    schema_version: 'kronos_v6_run_telemetry.v1',
    status: 'OK',
    run_id: 'daily/seed-1',
    follow_mode: 'HISTORICAL_SNAPSHOT',
    sampling: 'HEAD_TAIL_SAMPLE',
    event_bytes: 2048,
    invalid_lines: 0,
    updated_at: '2026-08-05T00:00:00Z',
    points: [{ step: 7, phase: 'train', reward: 0.1, equity: 1.02, loss: null, exploration: 0.5, action_name: 'buy', timestamp: '2026-08-05T00:00:00Z' }],
    claims: { live_stream: false, profitability: false },
  });

  assert.equal(runs.items[0].run_id, 'daily/seed-1');
  assert.equal(runs.items[0].status, 'NO-GO');
  assert.equal(snapshot.points[0].equity, 1.02);
  assert.equal(snapshot.claims.profitability, false);
});

test('telemetry URL encodes each run path segment and fixes the point bound', () => {
  assert.equal(buildTelemetryUrl('daily close/seed 1', 240), '/api/v6/research-runs/daily%20close/seed%201/telemetry?limit=240');
});
