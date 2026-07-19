import { test } from 'node:test';
import assert from 'node:assert/strict';
import type * as RunLifecycleModule from './runLifecycle';

const runLifecyclePath = ['.', 'runLifecycle.ts'].join('/');
const { deriveDisplayStatus, isLive } = (await import(runLifecyclePath)) as typeof RunLifecycleModule;

type RunLifecycle = RunLifecycleModule.RunLifecycle;
type LiveObservation = RunLifecycleModule.LiveObservation;

function lc(overrides: Partial<RunLifecycle> = {}): RunLifecycle {
  return {
    status: 'COMPLETED',
    is_live: false,
    event_file: 'run/events.jsonl',
    event_count: 10,
    last_step: 100,
    event_mtime_age_sec: 1,
    last_phase: 'research',
    is_replay: false,
    poll_interval_seconds: 4,
    ...overrides,
  };
}

function obs(overrides: Partial<LiveObservation> = {}): LiveObservation {
  return {
    prevStep: null,
    currentStep: null,
    polling: false,
    wasRunning: false,
    ...overrides,
  };
}

test('null lifecycle -> MISSING', () => {
  const status = deriveDisplayStatus(null, obs());
  assert.equal(status, 'MISSING');
  assert.equal(isLive(status), false);
});

test('REPLAY/IDLE/MISSING pass through and are never live, regardless of observation', () => {
  for (const passthrough of ['REPLAY', 'IDLE', 'MISSING'] as const) {
    const status = deriveDisplayStatus(
      lc({ status: passthrough }),
      obs({ polling: true, wasRunning: true, prevStep: 1, currentStep: 5 })
    );
    assert.equal(status, passthrough);
    assert.equal(isLive(status), false);
  }
});

test('COMPLETED snapshot + polling + advancing + fresh -> RUNNING (isLive true)', () => {
  const status = deriveDisplayStatus(
    lc({ status: 'COMPLETED', event_mtime_age_sec: 1, poll_interval_seconds: 4 }),
    obs({ polling: true, prevStep: 10, currentStep: 12 })
  );
  assert.equal(status, 'RUNNING');
  assert.equal(isLive(status), true);
});

test('polling but not advancing (no wasRunning) -> COMPLETED', () => {
  const status = deriveDisplayStatus(
    lc({ status: 'COMPLETED', event_mtime_age_sec: 1 }),
    obs({ polling: true, prevStep: 10, currentStep: 10, wasRunning: false })
  );
  assert.equal(status, 'COMPLETED');
  assert.equal(isLive(status), false);
});

test('stale age (age > 2*poll_interval) even though step advanced -> not RUNNING', () => {
  const status = deriveDisplayStatus(
    lc({ status: 'COMPLETED', event_mtime_age_sec: 20, poll_interval_seconds: 4 }),
    obs({ polling: true, prevStep: 10, currentStep: 12 })
  );
  assert.notEqual(status, 'RUNNING');
  assert.equal(isLive(status), false);
});

test('wasRunning + polling + not-advancing -> STALE', () => {
  const status = deriveDisplayStatus(
    lc({ status: 'COMPLETED', event_mtime_age_sec: 1 }),
    obs({ polling: true, wasRunning: true, prevStep: 10, currentStep: 10 })
  );
  assert.equal(status, 'STALE');
  assert.equal(isLive(status), false);
});

test('polling=false never yields RUNNING even with advancing+fresh', () => {
  const status = deriveDisplayStatus(
    lc({ status: 'COMPLETED', event_mtime_age_sec: 1 }),
    obs({ polling: false, prevStep: 10, currentStep: 12 })
  );
  assert.notEqual(status, 'RUNNING');
  assert.equal(isLive(status), false);
});

test('isLive is true only for RUNNING across all statuses', () => {
  const all: RunLifecycle['status'][] = ['RUNNING', 'COMPLETED', 'STALE', 'REPLAY', 'IDLE', 'MISSING'];
  for (const status of all) {
    assert.equal(isLive(status), status === 'RUNNING');
  }
});
