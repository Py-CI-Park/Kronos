import assert from 'node:assert/strict';
import { test } from 'node:test';
import type * as ArtifactEvidence from './artifactEvidence';

const evidencePath = ['./artifactEvidence.ts'].join('/');
const {
  NOT_RECORDED,
  normalizeArtifactsEvidence,
  adaptRunSnapshot,
}: typeof ArtifactEvidence = await import(evidencePath);

const { PROMOTION_LOCK_KEYS } = await import('../evidence');

const VALID_HASH = 'a'.repeat(64);

// ─────────────────────────── Artifacts ───────────────────────────

test('missing artifacts payload fails closed to not_recorded across every category', () => {
  const evidence = normalizeArtifactsEvidence(null);
  assert.equal(evidence.status, 'not_recorded');
  assert.equal(evidence.checkpoints.status, 'not_recorded');
  assert.equal(evidence.pretrainedWeights.status, 'not_recorded');
  assert.equal(evidence.predictorOutputs.status, 'not_recorded');
  assert.equal(evidence.checkpoints.declaredCount, null);
  assert.deepEqual(evidence.checkpoints.files, []);
  assert.equal(evidence.checkpointReady.sourceStatus, 'missing');
  assert.equal(evidence.checkpointReady.declared, false);
  assert.equal(evidence.label, NOT_RECORDED);
  assert.equal(evidence.message, NOT_RECORDED);
});

test('undefined and non-object payloads are treated the same as missing', () => {
  for (const malformed of [undefined, 'artifacts', 42, ['a', 'b'], true]) {
    const evidence = normalizeArtifactsEvidence(malformed as never);
    assert.equal(evidence.status, 'not_recorded');
  }
});

test('empty arrays render empty status without inventing files while payload is still recorded', () => {
  const evidence = normalizeArtifactsEvidence({
    checkpoint_file_count: 0,
    model_weight_file_count: 0,
    recent_checkpoint_files: [],
    recent_model_weight_files: [],
  });
  assert.equal(evidence.status, 'empty');
  assert.equal(evidence.checkpoints.status, 'empty');
  assert.equal(evidence.pretrainedWeights.status, 'empty');
  assert.equal(evidence.predictorOutputs.status, 'empty');
  assert.equal(evidence.checkpoints.declaredCount, 0);
});

test('checkpoints, pretrained weights, and predictor outputs are separated into distinct categories', () => {
  const evidence = normalizeArtifactsEvidence({
    checkpoint_file_count: 2,
    model_weight_file_count: 1,
    recent_checkpoint_files: [
      { path: 'outputs/run/tokenizer/checkpoint-100.pt' },
      { path: 'outputs/run/predictor/checkpoint-200.pt', stage: 'predictor' },
    ],
    recent_model_weight_files: [{ path: 'pretrained/base-weight.safetensors' }],
  });
  assert.equal(evidence.checkpoints.files.length, 1);
  assert.equal(evidence.checkpoints.files[0].category, 'checkpoint');
  assert.equal(evidence.checkpoints.files[0].name, 'checkpoint-100.pt');
  assert.equal(evidence.predictorOutputs.files.length, 1);
  assert.equal(evidence.predictorOutputs.files[0].category, 'predictor_output');
  assert.equal(evidence.predictorOutputs.files[0].name, 'checkpoint-200.pt');
  assert.equal(evidence.pretrainedWeights.files.length, 1);
  assert.equal(evidence.pretrainedWeights.files[0].category, 'pretrained_weight');
  assert.equal(evidence.pretrainedWeights.files[0].name, 'base-weight.safetensors');
});

test('predictor output files are also recognized from a declared predictor list without merging into checkpoints', () => {
  const evidence = normalizeArtifactsEvidence({
    recent_checkpoint_files: [{ path: 'outputs/run/tokenizer/checkpoint-1.pt' }],
    recent_predictor_output_files: [{ path: 'outputs/run/predictor/final.pt' }],
  });
  assert.equal(evidence.checkpoints.files.length, 1);
  assert.equal(evidence.predictorOutputs.files.length, 1);
  assert.equal(evidence.predictorOutputs.files[0].name, 'final.pt');
});

test('string-only file entries fall back to NOT_RECORDED hash, authority, size, and modified fields', () => {
  const evidence = normalizeArtifactsEvidence({
    recent_checkpoint_files: ['outputs/run/tokenizer/checkpoint-9.pt'],
  });
  const [file] = evidence.checkpoints.files;
  assert.equal(file.name, 'checkpoint-9.pt');
  assert.equal(file.hash, NOT_RECORDED);
  assert.equal(file.authority, NOT_RECORDED);
  assert.equal(file.sizeLabel, NOT_RECORDED);
  assert.equal(file.modifiedLabel, NOT_RECORDED);
});

test('malformed file entries (null, number, array) never crash and remain NOT_RECORDED', () => {
  const evidence = normalizeArtifactsEvidence({
    recent_checkpoint_files: [null, 42, ['nested'], { path: null }],
  });
  assert.equal(evidence.checkpoints.files.length, 4);
  for (const file of evidence.checkpoints.files) {
    assert.equal(file.path, NOT_RECORDED);
    assert.equal(file.name, NOT_RECORDED);
    assert.equal(file.hash, NOT_RECORDED);
  }
});

test('recorded sha256 hash is exposed exactly when it matches the strict 64-hex format', () => {
  const evidence = normalizeArtifactsEvidence({
    recent_checkpoint_files: [{ path: 'ckpt.pt', sha256: VALID_HASH }],
  });
  assert.equal(evidence.checkpoints.files[0].hash, VALID_HASH);
});

test('invalid hash formats (short, non-hex, whitespace) fail closed to NOT_RECORDED', () => {
  const invalidHashes = ['deadbeef', 'z'.repeat(64), '', '  ', 'a'.repeat(63), `${VALID_HASH}x`];
  for (const hash of invalidHashes) {
    const evidence = normalizeArtifactsEvidence({
      recent_checkpoint_files: [{ path: 'ckpt.pt', sha256: hash }],
    });
    assert.equal(evidence.checkpoints.files[0].hash, NOT_RECORDED, `expected NOT_RECORDED for ${JSON.stringify(hash)}`);
  }
});

test('authority is exposed only when declared as a non-empty string, otherwise NOT_RECORDED', () => {
  const declared = normalizeArtifactsEvidence({
    recent_checkpoint_files: [{ path: 'ckpt.pt', authority: 'signed_manifest' }],
  });
  assert.equal(declared.checkpoints.files[0].authority, 'signed_manifest');

  const missing = normalizeArtifactsEvidence({
    recent_checkpoint_files: [{ path: 'ckpt.pt', authority: 42 }],
  });
  assert.equal(missing.checkpoints.files[0].authority, NOT_RECORDED);
});

test('checkpoint_ready, predictor_started, and predictor stage completeness only trust strict booleans', () => {
  const evidence = normalizeArtifactsEvidence({
    checkpoint_ready: true,
    predictor_started: 'yes',
    stages: { predictor: { checkpoint_ready: false } },
  });
  assert.equal(evidence.checkpointReady.declared, true);
  assert.equal(evidence.checkpointReady.sourceStatus, 'declared');
  assert.equal(evidence.predictorStarted.declared, false);
  assert.equal(evidence.predictorStarted.sourceStatus, 'invalid');
  assert.equal(evidence.predictorComplete.declared, false);
  assert.equal(evidence.predictorComplete.sourceStatus, 'declared');
});

test('artifacts payload exposes exactly six fail-closed promotion locks when no lock source is declared', () => {
  const evidence = normalizeArtifactsEvidence({ recent_checkpoint_files: [] });
  assert.equal(Object.keys(evidence.promotionLocks.locks).length, 6);
  assert.deepEqual(Object.keys(evidence.promotionLocks.locks).sort(), [...PROMOTION_LOCK_KEYS].sort());
  for (const key of PROMOTION_LOCK_KEYS) {
    assert.equal(evidence.promotionLocks.locks[key], false);
  }
  assert.equal(evidence.promotionLocks.allLocked, true);
});

test('artifacts payload never promotes a declared true lock unless every strict boolean is true', () => {
  const evidence = normalizeArtifactsEvidence({
    recent_checkpoint_files: [],
    promotion_allowed: true,
    model_build_allowed: 'true',
  });
  assert.equal(evidence.promotionLocks.locks.promotion_allowed, true);
  assert.equal(evidence.promotionLocks.locks.model_build_allowed, false);
  assert.equal(evidence.promotionLocks.states.model_build_allowed.sourceStatus, 'invalid');
  assert.equal(evidence.promotionLocks.allLocked, false);
});

// ─────────────────────────── Runs ───────────────────────────

test('missing status and history fail closed to MISSING authority and NOT_RECORDED-style evidence', () => {
  const snapshot = adaptRunSnapshot(null, null);
  assert.equal(snapshot.authority.level, 'missing');
  assert.equal(snapshot.authority.source, 'missing');
  assert.equal(snapshot.stage, 'STAGE_NOT_RECORDED');
  assert.equal(snapshot.run.promotion_locks.allLocked, true);
});

test('malformed status/history objects (arrays, strings, numbers) are treated as absent sources', () => {
  const snapshot = adaptRunSnapshot('bad-status' as never, 42 as never);
  assert.equal(snapshot.authority.level, 'missing');
  assert.equal(snapshot.stage, 'STAGE_NOT_RECORDED');
});

test('a canonical status run_name outranks a declared history run_name', () => {
  const snapshot = adaptRunSnapshot({ run_name: 'run-canonical', status: 'running' }, { run_name: 'run-history' });
  assert.equal(snapshot.authority.level, 'canonical');
  assert.equal(snapshot.authority.source, 'status');
  assert.equal(snapshot.run.run_id, 'run-canonical');
});

test('a declared history run_name is used when status has none', () => {
  const snapshot = adaptRunSnapshot(null, { run_name: 'run-history-only' });
  assert.equal(snapshot.authority.level, 'declared');
  assert.equal(snapshot.authority.source, 'history');
  assert.equal(snapshot.run.run_id, 'run-history-only');
});

test('stage prefers latest_stage over the last stages entry over the history stage', () => {
  const snapshot = adaptRunSnapshot(
    {
      latest_stage: { train_stage: 'predictor' },
      stages: [{ train_stage: 'tokenizer' }],
    },
    { stage: 'legacy-tokenizer' },
  );
  assert.equal(snapshot.stage, 'predictor');
});

test('stage falls back to the last stages entry, then to history stage, then to NOT_RECORDED', () => {
  const withStages = adaptRunSnapshot({ stages: [{ train_stage: 'tokenizer' }, { train_stage: 'predictor' }] }, null);
  assert.equal(withStages.stage, 'predictor');

  const withHistoryOnly = adaptRunSnapshot(null, { stage: 'history-stage' });
  assert.equal(withHistoryOnly.stage, 'history-stage');

  const withNeither = adaptRunSnapshot({}, {});
  assert.equal(withNeither.stage, 'STAGE_NOT_RECORDED');
});

test('lifecycle/status text is derived from the strict status field and never invented', () => {
  const running = adaptRunSnapshot({ status: 'running' }, null);
  assert.equal(running.statusLabel, 'running');

  const missing = adaptRunSnapshot({}, {});
  assert.equal(missing.statusLabel, 'MISSING');
  assert.equal(missing.run.lifecycle, 'MISSING');
});

test('leading-zero seed strings are preserved exactly instead of being coerced to numbers', () => {
  const snapshot = adaptRunSnapshot({ seed: '007' }, null);
  assert.equal(snapshot.run.seed, '007');
});

test('leading-zero split_hash strings only pass through when they match the strict sha256 shape', () => {
  const valid = adaptRunSnapshot({ split_hash: VALID_HASH }, null);
  assert.equal(valid.run.split_hash, VALID_HASH);

  const invalid = adaptRunSnapshot({ split_hash: '007-not-a-hash' }, null);
  assert.equal(invalid.run.split_hash, 'SPLIT_HASH_NOT_RECORDED');
});

test('run artifact hash fails closed to a NOT_RECORDED-style fallback for invalid hash formats', () => {
  const invalid = adaptRunSnapshot({ sha256: 'not-a-real-hash' }, null);
  assert.equal(invalid.identity.sha256, 'HASH_NOT_RECORDED');

  const valid = adaptRunSnapshot({ sha256: VALID_HASH }, null);
  assert.equal(valid.identity.sha256, VALID_HASH);
});

test('prereg, cost, and split evidence pass through unmodified only when declared', () => {
  const snapshot = adaptRunSnapshot(
    { prereg_doc: 'docs/prereg.md', cost_bps: 12, split: 'train:val:test=70:15:15' },
    null,
  );
  assert.equal(snapshot.run.prereg_doc, 'docs/prereg.md');
  assert.equal(snapshot.run.cost_bps, 12);
  assert.equal(snapshot.run.split, 'train:val:test=70:15:15');

  const missing = adaptRunSnapshot({}, {});
  assert.equal(missing.run.prereg_doc, 'PREREG_DOC_NOT_RECORDED');
  assert.equal(missing.run.cost_bps, null);
  assert.equal(missing.run.split, 'SPLIT_NOT_RECORDED');
});

test('run evidence exposes exactly six fail-closed promotion locks regardless of source shape', () => {
  const snapshot = adaptRunSnapshot({ run_name: 'run-x' }, null);
  assert.equal(Object.keys(snapshot.run.promotion_locks.locks).length, 6);
  assert.deepEqual(Object.keys(snapshot.run.promotion_locks.locks).sort(), [...PROMOTION_LOCK_KEYS].sort());
  for (const key of PROMOTION_LOCK_KEYS) {
    assert.equal(snapshot.run.promotion_locks.locks[key], false);
  }
  assert.equal(snapshot.run.promotion_locks.allLocked, true);
});

test('run evidence never sets a lock true unless every source declares a strict boolean true', () => {
  const snapshot = adaptRunSnapshot({ promotion_locks: { promotion_allowed: true, model_build_allowed: 1 } }, null);
  assert.equal(snapshot.run.promotion_locks.locks.promotion_allowed, true);
  assert.equal(snapshot.run.promotion_locks.locks.model_build_allowed, false);
  assert.equal(snapshot.run.promotion_locks.states.model_build_allowed.sourceStatus, 'invalid');
});
