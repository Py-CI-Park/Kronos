import assert from 'node:assert/strict';
import test from 'node:test';

import type * as LatencyGate from './latencyGate';

const latencyGatePath = ['.', 'latencyGate.ts'].join('/');
const { evaluateDashboardLatency }: typeof LatencyGate = await import(latencyGatePath);

const passing = {
  firstMeaningfulCardMs: 3_000,
  fullCriticalHydrationMs: 10_000,
  warmCriticalApiMs: 2_000,
  coldCriticalApiMs: 5_000,
};

test('latency gate passes values exactly at every limit', () => {
  assert.deepEqual(evaluateDashboardLatency(passing), { pass: true, failures: [] });
});

test('warm critical API breach fails rather than passing silently', () => {
  const result = evaluateDashboardLatency({ ...passing, warmCriticalApiMs: 2_001 });
  assert.equal(result.pass, false);
  assert.deepEqual(result.failures, ['warmCriticalApiMs:2001>2000']);
});

test('cold critical API breach fails rather than passing silently', () => {
  const result = evaluateDashboardLatency({ ...passing, coldCriticalApiMs: 5_001 });
  assert.equal(result.pass, false);
  assert.deepEqual(result.failures, ['coldCriticalApiMs:5001>5000']);
});

test('invalid and multiple page timing breaches all fail closed', () => {
  const result = evaluateDashboardLatency({
    firstMeaningfulCardMs: Number.NaN,
    fullCriticalHydrationMs: 10_001,
    warmCriticalApiMs: -1,
    coldCriticalApiMs: 5_000,
  });
  assert.equal(result.pass, false);
  assert.deepEqual(result.failures, [
    'firstMeaningfulCardMs:invalid',
    'fullCriticalHydrationMs:10001>10000',
    'warmCriticalApiMs:invalid',
  ]);
});
