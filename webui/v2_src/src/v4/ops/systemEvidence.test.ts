import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';

import type * as SystemEvidence from './systemEvidence';

const evidencePath = ['./systemEvidence.ts'].join('/');
const {
  OPS_MISSING,
  OPS_NOT_RECORDED,
  adaptCpuMemorySnapshot,
  adaptGpuSnapshot,
  adaptModelHealth,
  adaptSystemOpsEvidence,
  adaptTrainingAuthority,
  adaptTrainingOpsEvidence,
  adaptTrainingRunSnapshot,
  deriveTrainingLifecycleState,
}: typeof SystemEvidence = await import(evidencePath);

const { PROMOTION_LOCK_KEYS } = await import('../evidence');

const trainingOpsSource = readFileSync(new URL('./V4TrainingOps.svelte', import.meta.url), 'utf8');
const systemOpsSource = readFileSync(new URL('./V4SystemOps.svelte', import.meta.url), 'utf8');

function loadState<T>(partial: Partial<{ data: T | null; loading: boolean; error: string | null; loaded: boolean }>) {
  return { data: null, loading: false, error: null, loaded: false, ...partial };
}

// --------------------------------------------------------------------------- #
// Training ops: loading / empty / error / missing / live / replay / completed / stale
// --------------------------------------------------------------------------- #

test('training lifecycle state reports loading while the status GET is in flight', () => {
  assert.equal(deriveTrainingLifecycleState(loadState({ loading: true })), 'loading');
  assert.equal(deriveTrainingLifecycleState(loadState({ loaded: false })), 'loading');
});

test('training lifecycle state reports error when the status GET failed', () => {
  assert.equal(deriveTrainingLifecycleState(loadState({ loaded: true, error: 'boom' })), 'error');
});

test('training lifecycle state reports missing when the GET completed without a recorded payload', () => {
  assert.equal(deriveTrainingLifecycleState(loadState({ loaded: true, data: null })), 'missing');
});

test('training lifecycle state reports empty for a structurally-empty declared payload', () => {
  const state = loadState({ loaded: true, data: { status: undefined, stages: [] } as any });
  assert.equal(deriveTrainingLifecycleState(state), 'empty');
});

test('training lifecycle state maps declared status tokens to live/replay/completed/stale', () => {
  assert.equal(deriveTrainingLifecycleState(loadState({ loaded: true, data: { status: 'running', stages: [] } as any })), 'live');
  assert.equal(deriveTrainingLifecycleState(loadState({ loaded: true, data: { status: 'replay', stages: [] } as any })), 'replay');
  assert.equal(deriveTrainingLifecycleState(loadState({ loaded: true, data: { status: 'completed', stages: [] } as any })), 'completed');
  assert.equal(deriveTrainingLifecycleState(loadState({ loaded: true, data: { status: 'idle', stages: [] } as any })), 'stale');
});

test('malformed training status tokens fail closed to missing rather than an optimistic state', () => {
  assert.equal(deriveTrainingLifecycleState(loadState({ loaded: true, data: { status: 42, stages: [] } as any })), 'missing');
  assert.equal(deriveTrainingLifecycleState(loadState({ loaded: true, data: { status: 'unrecognized_token', stages: [] } as any })), 'missing');
});

// --------------------------------------------------------------------------- #
// Training ops: authority / run snapshot / model health / blockers
// --------------------------------------------------------------------------- #

test('training authority prefers status run_name, then history, then fails closed to missing', () => {
  const fromStatus = adaptTrainingAuthority({ run_name: '000123', status: 'running', stages: [] } as any, null);
  assert.equal(fromStatus.level, 'declared');
  assert.equal(fromStatus.source, 'status');
  assert.equal(fromStatus.label, '000123');

  const fromHistory = adaptTrainingAuthority({ status: 'running', stages: [] } as any, { run_name: '000456', points: [] } as any);
  assert.equal(fromHistory.source, 'history');
  assert.equal(fromHistory.label, '000456');

  const missing = adaptTrainingAuthority(null, null);
  assert.equal(missing.level, 'missing');
  assert.equal(missing.label, OPS_MISSING);
});

test('training run snapshot stage/status/percent fail closed and never coerce leading-zero run ids', () => {
  const authority = adaptTrainingAuthority({ run_name: '000007', status: 'running', stages: [] } as any, null);
  const snapshot = adaptTrainingRunSnapshot(
    {
      run_name: '000007',
      status: 'running',
      stages: [],
      latest_stage: { train_stage: 'stage_2', status: 'running' },
      overall_percent: 47,
    } as any,
    authority,
  );

  assert.equal(snapshot.runName, '000007');
  assert.equal(snapshot.stage, 'stage_2');
  assert.equal(snapshot.status, 'running');
  assert.equal(snapshot.overallPercent, 47);
});

test('malformed overall_percent values become null rather than a fabricated number', () => {
  const authority = adaptTrainingAuthority({ run_name: 'r', status: 'running', stages: [] } as any, null);
  for (const malformed of [-5, 150, NaN, Infinity, '50' as unknown as number, null]) {
    const snapshot = adaptTrainingRunSnapshot({ run_name: 'r', status: 'running', stages: [], overall_percent: malformed } as any, authority);
    assert.equal(snapshot.overallPercent, null);
  }
});

test('model health posture stays read-only and fails closed without a recorded artifacts payload', () => {
  const missing = adaptModelHealth(null);
  assert.equal(missing.status, 'NOT_RECORDED');
  assert.equal(missing.checkpointReady, false);
  assert.equal(missing.predictorStarted, false);
  assert.equal(missing.disclosure, 'READ_ONLY_POSTURE_NOT_A_PROMOTION_CLAIM');

  const declared = adaptModelHealth({
    checkpoint_file_count: 4,
    model_weight_file_count: 2,
    checkpoint_ready: true,
    predictor_started: true,
    label: 'stage_2',
    message: 'checkpoint ready',
    recent_checkpoint_files: [],
    recent_model_weight_files: [],
  } as any);
  assert.equal(declared.status, 'RECORDED');
  assert.equal(declared.checkpointReady, true);
  assert.equal(declared.predictorStarted, true);
  assert.equal(declared.disclosure, 'READ_ONLY_POSTURE_NOT_A_PROMOTION_CLAIM');
});

test('non-boolean checkpoint/predictor flags fail closed to false instead of truthy coercion', () => {
  const malformed = adaptModelHealth({ checkpoint_ready: 'yes', predictor_started: 1 } as any);
  assert.equal(malformed.checkpointReady, false);
  assert.equal(malformed.predictorStarted, false);
});

test('adaptTrainingOpsEvidence composes authority/run/modelHealth/locks/blockers behind a single call', () => {
  const evidence = adaptTrainingOpsEvidence(
    { run_name: '000123', status: 'running', stages: [], latest_stage: { train_stage: 'stage_1', status: 'running' }, readiness: { level: 'training' } } as any,
    null,
    { checkpoint_ready: false, predictor_started: true, label: 'stage_1', message: 'training' } as any,
    loadState({ loaded: true, data: { run_name: '000123', status: 'running', stages: [] } as any }),
  );

  assert.equal(evidence.authority.level, 'declared');
  assert.equal(evidence.run.runName, '000123');
  assert.equal(evidence.modelHealth.status, 'RECORDED');
  assert.equal(evidence.lifecycleState, 'live');
  assert.equal(Object.keys(evidence.promotionLocks.locks).length, 6);
  assert.equal(evidence.promotionLocks.allLocked, true);
  assert.ok(evidence.blockers.includes('CHECKPOINT_NOT_READY'));
  assert.ok(evidence.blockers.includes('READINESS_TRAINING'));
});

// --------------------------------------------------------------------------- #
// System ops: per-source isolation, malformed metrics, freshness
// --------------------------------------------------------------------------- #

test('GPU and system telemetry are read independently: one endpoint error never hides the other', () => {
  const evidence = adaptSystemOpsEvidence(
    null,
    loadState({ loaded: true, error: 'gpu GET timed out' }),
    { available: true, cpu: { utilization_percent: 12 }, memory: { used_percent: 40 }, generated_at: new Date().toISOString() } as any,
    loadState({ loaded: true, data: { available: true } as any }),
  );

  const gpuSource = evidence.sources.find((source) => source.key === 'gpu');
  const systemSource = evidence.sources.find((source) => source.key === 'cpuMemory');

  assert.equal(gpuSource?.availability, 'ERROR');
  assert.equal(gpuSource?.detail, 'gpu GET timed out');
  assert.equal(systemSource?.availability, 'RECORDED');
  assert.equal(systemSource?.detail, 'GET /api/training/system');
  assert.notEqual(systemSource?.availability, gpuSource?.availability);
});

test('system endpoint failure does not degrade an independently healthy GPU source', () => {
  const evidence = adaptSystemOpsEvidence(
    { available: true, gpus: [{ utilization_gpu_percent: 55, memory_used_percent: 61, temperature_c: 70 }], generated_at: new Date().toISOString() } as any,
    loadState({ loaded: true, data: { available: true } as any }),
    null,
    loadState({ loaded: true, error: 'system GET failed' }),
  );

  const gpuSource = evidence.sources.find((source) => source.key === 'gpu');
  const systemSource = evidence.sources.find((source) => source.key === 'cpuMemory');

  assert.equal(gpuSource?.availability, 'RECORDED');
  assert.equal(gpuSource?.lifecycleState, 'live');
  assert.equal(systemSource?.availability, 'ERROR');
  assert.equal(systemSource?.lifecycleState, 'error');
});

test('malformed GPU/CPU percentages become null instead of fabricated numeric values', () => {
  const gpu = adaptGpuSnapshot({
    available: true,
    gpus: [{ utilization_gpu_percent: -5, memory_used_percent: 140, temperature_c: 'hot' as unknown as number }],
    generated_at: 'not-a-date',
  } as any);
  assert.equal(gpu.utilizationPercent, null);
  assert.equal(gpu.memoryUsedPercent, null);
  assert.equal(gpu.temperatureC, null);
  assert.equal(gpu.generatedAt, 'not-a-date');

  const cpuMemory = adaptCpuMemorySnapshot({
    available: 'true' as unknown as boolean,
    cpu: { utilization_percent: NaN },
    memory: { used_percent: Infinity },
  } as any);
  assert.equal(cpuMemory.available, false);
  assert.equal(cpuMemory.cpuUtilizationPercent, null);
  assert.equal(cpuMemory.memoryUsedPercent, null);
});

test('missing GPU/system payloads render NOT_RECORDED availability and MISSING generatedAt', () => {
  const evidence = adaptSystemOpsEvidence(
    null,
    loadState({ loaded: true, data: null }),
    null,
    loadState({ loaded: true, data: null }),
  );

  for (const source of evidence.sources) {
    assert.equal(source.availability, 'NOT_RECORDED');
    assert.equal(source.freshness, OPS_MISSING);
  }
  assert.equal(evidence.gpu.generatedAt, OPS_MISSING);
  assert.equal(evidence.cpuMemory.generatedAt, OPS_MISSING);
});

test('stale generated_at timestamps are labeled STALE while recent timestamps stay FRESH', () => {
  const staleTs = new Date(Date.now() - 10 * 60 * 1000).toISOString();
  const freshTs = new Date().toISOString();

  const staleEvidence = adaptSystemOpsEvidence(
    { available: true, gpus: [], generated_at: staleTs } as any,
    loadState({ loaded: true, data: { available: true } as any }),
    null,
    loadState({ loaded: true, data: null }),
  );
  const freshEvidence = adaptSystemOpsEvidence(
    { available: true, gpus: [], generated_at: freshTs } as any,
    loadState({ loaded: true, data: { available: true } as any }),
    null,
    loadState({ loaded: true, data: null }),
  );

  const staleGpu = staleEvidence.sources.find((source) => source.key === 'gpu');
  const freshGpu = freshEvidence.sources.find((source) => source.key === 'gpu');

  assert.equal(staleGpu?.freshness, 'STALE');
  assert.equal(staleGpu?.lifecycleState, 'stale');
  assert.equal(freshGpu?.freshness, 'FRESH');
  assert.equal(freshGpu?.lifecycleState, 'live');
});

// --------------------------------------------------------------------------- #
// Exactly six promotion locks default false / fail closed
// --------------------------------------------------------------------------- #

test('system ops promotion locks are always exactly six and fail closed regardless of telemetry', () => {
  const evidence = adaptSystemOpsEvidence(
    { available: true, gpus: [{ utilization_gpu_percent: 90 }] } as any,
    loadState({ loaded: true, data: { available: true } as any }),
    { available: true, cpu: { utilization_percent: 90 } } as any,
    loadState({ loaded: true, data: { available: true } as any }),
  );

  assert.deepEqual(Object.keys(evidence.promotionLocks.locks), [...PROMOTION_LOCK_KEYS]);
  assert.equal(Object.keys(evidence.promotionLocks.locks).length, 6);
  assert.equal(evidence.promotionLocks.allLocked, true);
  for (const key of PROMOTION_LOCK_KEYS) {
    assert.equal(evidence.promotionLocks.locks[key], false);
  }
});

test('training ops promotion locks stay six and fail closed even when the source declares unrelated fields', () => {
  const evidence = adaptTrainingOpsEvidence(
    { run_name: 'r', status: 'running', stages: [], promotion_allowed: 'yes' as unknown as boolean } as any,
    null,
    null,
    loadState({ loaded: true, data: { run_name: 'r', status: 'running', stages: [] } as any }),
  );

  assert.equal(Object.keys(evidence.promotionLocks.locks).length, 6);
  assert.equal(evidence.promotionLocks.states.promotion_allowed.sourceStatus, 'invalid');
  assert.equal(evidence.promotionLocks.locks.promotion_allowed, false);
  assert.equal(evidence.promotionLocks.allLocked, true);
});

// --------------------------------------------------------------------------- #
// Component source contracts: markers, snippet children, no process control
// --------------------------------------------------------------------------- #

test('V4TrainingOps and V4SystemOps expose stable root markers and lazy-render legacy children last', () => {
  assert.match(trainingOpsSource, /data-v4-training-ops/);
  assert.match(systemOpsSource, /data-v4-system-ops/);
  assert.ok(trainingOpsSource.includes('children?: Snippet'));
  assert.ok(systemOpsSource.includes('children?: Snippet'));
  assert.ok(!trainingOpsSource.includes('<slot'));
  assert.ok(!systemOpsSource.includes('<slot'));


  const trainingMarkerIndex = trainingOpsSource.indexOf('data-v4-training-ops');
  const trainingRenderIndex = trainingOpsSource.lastIndexOf('{@render children()}');
  assert.ok(trainingRenderIndex > trainingMarkerIndex);

  const systemMarkerIndex = systemOpsSource.indexOf('data-v4-system-ops');
  const systemRenderIndex = systemOpsSource.lastIndexOf('{@render children()}');
  assert.ok(systemRenderIndex > systemMarkerIndex);
});

test('training/system ops components never declare process control, server start, or env-edit vocabulary', () => {
  for (const forbidden of ['child_process', 'spawn(', 'exec(', 'process.env[', 'os.environ', 'kill(', 'restart_server', 'start_server']) {
    assert.ok(!trainingOpsSource.includes(forbidden), `unexpected ${forbidden} in V4TrainingOps.svelte`);
    assert.ok(!systemOpsSource.includes(forbidden), `unexpected ${forbidden} in V4SystemOps.svelte`);
  }
});

test('promotion locks grid is rendered with the exact shared six-key adapter result', () => {
  assert.ok(trainingOpsSource.includes('<PromotionLocksGrid result={evidence.promotionLocks} compact />'));
  assert.ok(systemOpsSource.includes('<PromotionLocksGrid result={evidence.promotionLocks} compact />'));
});

test('not-recorded sentinel constants are exported and distinct', () => {
  assert.equal(OPS_NOT_RECORDED, 'NOT_RECORDED');
  assert.equal(OPS_MISSING, 'MISSING');
  assert.notEqual(OPS_NOT_RECORDED, OPS_MISSING);
});
