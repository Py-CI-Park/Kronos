import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import type * as AdminEvidence from './adminEvidence';

const adminEvidencePath = ['.', 'adminEvidence.ts'].join('/');
const {
  PROMOTION_LOCK_KEYS,
  MUTATION_VERBS,
  READ_ONLY_NO_EGRESS_POSTURE,
  DOCS_SANITIZATION_FACTS,
  assertExactSixLocksFalse,
  deriveAdminWorkspaceModel,
  evaluateTrackingEvidence,
  evaluateTrackingUri,
  sanitizeAdminLabel,
}: typeof AdminEvidence = await import(adminEvidencePath);

const workspaceSource = readFileSync(new URL('./V4AdminWorkspace.svelte', import.meta.url), 'utf8');

test('rejects http/https tracking URIs and never marks tracking as detected', () => {
  const http = evaluateTrackingUri('http://mlflow.internal:5000');
  const https = evaluateTrackingUri('https://mlflow.internal:5000/api');

  assert.equal(http.status, 'rejected_remote_uri');
  assert.equal(http.sanitizedUri, null);
  assert.equal(https.status, 'rejected_remote_uri');
  assert.equal(https.sanitizedUri, null);
});

test('rejects credentials and tokens embedded anywhere in a candidate tracking URI', () => {
  const userinfo = evaluateTrackingUri('file://user:pass@localhost/mlruns');
  const tokenQuery = evaluateTrackingUri('file:///mlruns?token=abc123');
  const apiKey = evaluateTrackingUri('file:///mlruns?api_key=xyz');
  const bearer = evaluateTrackingUri('file:///mlruns Authorization: Bearer abcdef123456');

  for (const evaluation of [userinfo, tokenQuery, apiKey, bearer]) {
    assert.equal(evaluation.status, 'rejected_credentials');
    assert.equal(evaluation.sanitizedUri, null);
  }
});

test('rejects mutation/action verbs in labels and never redacts them into displayable text', () => {
  for (const verb of MUTATION_VERBS) {
    const label = sanitizeAdminLabel(`please ${verb} the mlflow server now`);
    assert.equal(label.rejected, true);
    assert.equal(label.reason, 'MUTATION_ACTION_VERB_REJECTED');
    assert.equal(label.text, 'REDACTED');
  }

  const safe = sanitizeAdminLabel('Local research tracking notes');
  assert.equal(safe.rejected, false);
  assert.equal(safe.text, 'Local research tracking notes');
});

test('rejects declared capabilities that imply mutation and never enables tracking from them', () => {
  const evidence = evaluateTrackingEvidence({
    trackingUri: 'file:///C:/mlruns',
    capabilities: ['create_experiment', 'delete_run', 'read_only'],
  });

  assert.equal(evidence.enabled, false);
  assert.deepEqual(evidence.rejectedCapabilities.sort(), ['create_experiment', 'delete_run'].sort());
  assert.equal(evidence.posture, 'REJECTED_UNSAFE_SOURCE');
});

test('never applies an optimistic enabled default; claimed enabled flags are ignored without file evidence', () => {
  const claimedTrue = evaluateTrackingEvidence({ enabled: true });
  const claimedTrueNoUri = evaluateTrackingEvidence({ enabled: true, trackingUri: '' });
  const missing = evaluateTrackingEvidence(undefined);
  const nullSource = evaluateTrackingEvidence(null);

  for (const evidence of [claimedTrue, claimedTrueNoUri, missing, nullSource]) {
    assert.equal(evidence.enabled, false);
    assert.equal(evidence.detectionStatus, 'disabled');
    assert.equal(evidence.posture, 'DISABLED');
    assert.equal(evidence.sanitizedUri, null);
  }
});

test('accepts only a safe, credential-free local file: URI as read-only detected tracking', () => {
  const evidence = evaluateTrackingEvidence({ trackingUri: 'file:///C:/kronos/mlruns' });

  assert.equal(evidence.enabled, true);
  assert.equal(evidence.detectionStatus, 'file_uri_detected');
  assert.equal(evidence.posture, 'READ_ONLY_LOCAL_FILE');
  assert.equal(evidence.sanitizedUri, 'file:///C:/kronos/mlruns');
  assert.equal(evidence.backend, 'mlflow');
});

test('rejects unsupported non-file, non-http schemes instead of guessing safety', () => {
  const s3 = evaluateTrackingUri('s3://bucket/mlruns');
  const postgres = evaluateTrackingUri('postgresql://db/mlflow');

  assert.equal(s3.status, 'rejected_remote_uri');
  assert.equal(postgres.status, 'rejected_unsupported_scheme');
  assert.equal(postgres.sanitizedUri, null);
});

test('missing tracking source stays disabled, not merely empty', () => {
  const evidence = evaluateTrackingEvidence(undefined);

  assert.equal(evidence.detectionStatus, 'disabled');
  assert.equal(evidence.enabled, false);
  assert.equal(evidence.reasons[0], 'MLFLOW_TRACKING_URI_NOT_RECORDED');
});

test('admin workspace model always exposes exactly six false promotion locks regardless of input', () => {
  const attemptedUnlock = {
    promotion_allowed: true,
    model_build_allowed: true,
    paper_forward_allowed: true,
    live_broker_order_allowed: true,
    profitability_claim_allowed: true,
    go_summary_allowed: true,
  };

  const settingsModel = deriveAdminWorkspaceModel('settings', attemptedUnlock);
  const docsModel = deriveAdminWorkspaceModel('docs', attemptedUnlock);

  assert.equal(PROMOTION_LOCK_KEYS.length, 6);
  for (const model of [settingsModel, docsModel]) {
    assert.equal(assertExactSixLocksFalse(model.locks), true);
    assert.equal(model.locks.allLocked, true);
    for (const key of PROMOTION_LOCK_KEYS) {
      assert.equal(model.locks.locks[key], false);
      assert.equal(model.locks.states[key].sourceStatus, 'missing');
    }
  }
});

test('admin workspace model always declares the read-only, no-egress, no-mutation posture', () => {
  const model = deriveAdminWorkspaceModel('settings');

  assert.deepEqual(READ_ONLY_NO_EGRESS_POSTURE, {
    readOnly: true,
    noEgress: true,
    noServerControl: true,
    noMutation: true,
  });
  assert.deepEqual(model.posture, READ_ONLY_NO_EGRESS_POSTURE);
  assert.ok(DOCS_SANITIZATION_FACTS.length > 0);
  assert.deepEqual(model.docsSanitization, DOCS_SANITIZATION_FACTS);
});

test('docs and settings surfaces derive independent tracking evidence for identical input', () => {
  const source = { trackingUri: 'file:///C:/kronos/mlruns' };
  const settingsModel = deriveAdminWorkspaceModel('settings', source);
  const docsModel = deriveAdminWorkspaceModel('docs', source);

  assert.equal(settingsModel.surface, 'settings');
  assert.equal(docsModel.surface, 'docs');
  assert.notEqual(settingsModel.tracking, docsModel.tracking);
  assert.deepEqual(settingsModel.tracking, docsModel.tracking);
});

test('component markup carries stable V4 markers, supports both surfaces, and never uses unsanitized {@html}', () => {
  assert.match(workspaceSource, /data-v4-admin-workspace/);
  assert.match(workspaceSource, /data-v4-admin-locks/);
  assert.match(workspaceSource, /data-v4-admin-tracking/);
  assert.match(workspaceSource, /data-v4-admin-posture/);
  assert.match(workspaceSource, /data-v4-admin-docs-sanitization/);
  assert.match(workspaceSource, /data-v4-admin-legacy/);
  assert.match(workspaceSource, /surface:\s*['"]settings['"]\s*\|\s*['"]docs['"]/);
  assert.doesNotMatch(workspaceSource, /\{@html/);
});

test('component source renders the legacy child snippet last inside a lazy disclosure', () => {
  const legacyIndex = workspaceSource.indexOf('data-v4-admin-legacy');
  const lazyDisclosureIndex = workspaceSource.lastIndexOf('lazy', legacyIndex === -1 ? workspaceSource.length : legacyIndex + 400);
  const renderChildrenIndex = workspaceSource.indexOf('{@render children');

  assert.ok(legacyIndex > -1, 'legacy marker must be present');
  assert.ok(renderChildrenIndex > legacyIndex, 'children snippet must render after the legacy marker opens');
  assert.ok(lazyDisclosureIndex > -1, 'legacy child must sit inside a lazy disclosure');

  const trailingSource = workspaceSource.slice(legacyIndex);
  assert.doesNotMatch(trailingSource.slice(trailingSource.indexOf('{@render children') + 1), /data-v4-admin-(locks|tracking|posture|docs-sanitization)/);
});

test('component source never fetches external URLs or reads environment variables', () => {
  assert.doesNotMatch(workspaceSource, /\bfetch\s*\(/);
  assert.doesNotMatch(workspaceSource, /import\.meta\.env/);
  assert.doesNotMatch(workspaceSource, /process\.env/);
});
