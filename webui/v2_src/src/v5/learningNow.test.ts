import assert from 'node:assert/strict';
import { test } from 'node:test';
import type * as LearningNow from './learningNow';
import type { Locks } from '../lib/generated/kronosRlApiV2';
import { rlApi, V5LearningFetchError } from '../lib/rlApi';

const learningNowPath = ['.', 'learningNow.ts'].join('/');
const {
  V5_MATRIX_COLUMNS,
  V5_MATRIX_ROWS,
  LEARNING_NOW_COST_COMPONENTS,
  assessRunLiveness,
  auditProgress,
  buildDownloadPolicy,
  bindLearningNowIdentityRevision,
  buildEvidenceReceipt,
  findScorecardArtifactSha256,
  classifyLearningNowFailure,
  createLearningNowLoadStamp,
  extractRunIdentity,
  reconcileLedger,
  roundProgressPercentHalfUp,
  selectLearningNowCandidate,
  shouldApplyLearningNowResult,
  summarizeGovernance,
  summarizeMatrix,
}: typeof LearningNow = await import(learningNowPath);

const sha256 = 'a'.repeat(64);
const utc = '2026-07-15T00:00:00Z';
const source = { source_sha256: sha256, generated_at: utc };
const locks = {
  promotion_allowed: false,
  model_build_allowed: false,
  paper_forward_allowed: false,
  live_broker_order_allowed: false,
  profitability_claim_allowed: false,
  go_summary_allowed: false,
} as const satisfies Locks;
const run = {
  run_id: 'run-1',
  state: {
    status: 'RUNNING',
    progress: { step: 1, total_steps: 3, percent: 33.333333 },
    updated_at: utc,
    started_at: utc,
    finished_at: null,
  },
  source_sha256: sha256,
  created_at: utc,
} as const;
const futureRun = { ...run, run_uid: '018f0000-0000-7000-8000-000000000001', run_revision: 7 } as const;
const provenance = { provenance: { registry_epoch: 'epoch-1', snapshot_global_seq: 7 } };
const matrixCells = V5_MATRIX_ROWS.flatMap((row_id) =>
  V5_MATRIX_COLUMNS.map((column_id) => ({ row_id, column_id, state: 'PASS' as const })),
);

const expectedCostComponents = [
  'sell_tax_bp=20',
  'buy_commission_bp=1.5',
  'sell_commission_bp=1.5',
  'buy_slippage_bp=0',
  'sell_slippage_bp=0',
] as const;

function runsRoot(items = [run] as readonly unknown[]): any {
  return { route_id: 'RUNS', source, locks, list: { items, next_cursor: null } };
}

function matrixRoot(cells = matrixCells): any {
  return {
    route_id: 'MATRIX',
    source,
    locks,
    cells,
    summary: { total_cells: 50, pass_count: cells.filter((cell) => cell.state === 'PASS').length, fail_count: 0, blocked_count: 0, pending_count: 0 },
  };
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), { status, headers: { 'content-type': 'application/json' } });
}

async function withFetch(result: Response, run: (urls: string[]) => Promise<void>): Promise<void> {
  const previousFetch = globalThis.fetch;
  const urls: string[] = [];
  globalThis.fetch = (async (input: Parameters<typeof fetch>[0]) => {
    urls.push(String(input));
    return result;
  }) as typeof fetch;
  try {
    await run(urls);
  } finally {
    globalThis.fetch = previousFetch;
  }
}

test('V5 fetch helpers bind generated query params without breaking legacy null errors', async () => {
  await withFetch(jsonResponse(matrixRoot()), async (urls) => {
    assert.equal((await rlApi.v5Matrix())?.route_id, 'MATRIX');
    assert.deepEqual(urls, ['/api/v5/rl/matrix']);
  });

  await withFetch(jsonResponse({ route_id: 'MATRIX', error: { code: 'INTERNAL_ERROR', message: 'missing immutable query' } }, 400), async (urls) => {
    assert.equal(await rlApi.v5Matrix(), null);
    assert.deepEqual(urls, ['/api/v5/rl/matrix']);
  });

  await withFetch(jsonResponse(matrixRoot()), async (urls) => {
    const payload = await rlApi.v5LearningMatrix(futureRun.run_uid, futureRun.run_revision);
    assert.equal(payload.route_id, 'MATRIX');
    assert.deepEqual(urls, [`/api/v5/rl/matrix?run_id=${futureRun.run_uid}&revision=${futureRun.run_revision}`]);
  });

  await withFetch(jsonResponse({ route_id: 'MATRIX', error: { code: 'INTERNAL_ERROR', message: 'bounded failure' } }, 503), async (urls) => {
    await assert.rejects(
      rlApi.v5LearningMatrix(futureRun.run_uid, futureRun.run_revision),
      (caught) => caught instanceof V5LearningFetchError && caught.status === 503,
    );
    assert.deepEqual(urls, [`/api/v5/rl/matrix?run_id=${futureRun.run_uid}&revision=${futureRun.run_revision}`]);
  });
});

test('immutable UID/revision extraction fails closed until generated fields exist', () => {
  const current = extractRunIdentity(run);
  assert.equal(current.uid, null);
  assert.equal(current.revision, null);
  assert.equal(current.canRequestDetail, false);
  assert.equal(current.blockerCode, 'UID_REVISION_UNAVAILABLE');

  const selection = selectLearningNowCandidate({ ...runsRoot([futureRun]), ...provenance } as never, null, {
    uid: '018f0000-0000-7000-8000-000000000001',
  });
  assert.equal(selection.status, 'SELECTED');
  assert.equal(selection.selected?.identity.uid, '018f0000-0000-7000-8000-000000000001');
  assert.equal(selection.selected?.identity.revision, 7);
  assert.equal(selection.selected?.identity.provenance.registryEpoch, 'epoch-1');
  assert.equal(selection.selected?.identity.provenance.snapshotGlobalSeq, '7');
  assert.equal(selection.selected?.identity.canRequestDetail, true);
  assert.equal(selection.requestedRevision, null);
  const fixtureSelection = selectLearningNowCandidate(null, {
    route_id: 'FIXTURE',
    source,
    locks,
    fixture: { fixture_id: '018f0000-0000-7000-8000-000000000001', run, source_sha256: sha256, created_at: utc },
  } as never, { uid: '018f0000-0000-7000-8000-000000000001' });
  assert.equal(fixtureSelection.status, 'SELECTED');
  assert.equal(fixtureSelection.selected?.fixtureUid, '018f0000-0000-7000-8000-000000000001');
  assert.equal(fixtureSelection.selected?.identity.canRequestDetail, false);
  const boundFromQuery = bindLearningNowIdentityRevision(
    extractRunIdentity({ ...run, run_id: '018f0000-0000-7000-8000-000000000001' } as never),
    7,
  );
  assert.equal(boundFromQuery.canRequestDetail, true);
  assert.equal(boundFromQuery.revision, 7);

  const missing = selectLearningNowCandidate(runsRoot([futureRun]), null, { uid: 'other-uid' });
  assert.equal(missing.status, 'REQUESTED_UID_NOT_FOUND');
  assert.equal(missing.selected, null);
});

test('race stamps reject stale or cross-revision route completions', () => {
  const older = createLearningNowLoadStamp(1, extractRunIdentity(futureRun));
  const active = createLearningNowLoadStamp(2, extractRunIdentity(futureRun));
  assert.equal(shouldApplyLearningNowResult(active, older), false);
  assert.equal(shouldApplyLearningNowResult(active, active), true);

  const changedRevision = createLearningNowLoadStamp(2, extractRunIdentity({ ...futureRun, run_revision: 8 } as never));
  assert.equal(shouldApplyLearningNowResult(active, changedRevision), false);
});

test('409 conflict and stale revision failures are retry-safe and explicit', () => {
  assert.deepEqual(classifyLearningNowFailure({ status: 409 }), {
    code: 'CONFLICT_409',
    message: 'Registry revision conflict; reload the immutable selection.',
    retryable: true,
  });
  assert.equal(classifyLearningNowFailure({ code: 'INVALID_CURSOR' }).code, 'STALE_REVISION');
  assert.equal(classifyLearningNowFailure({ status: 410 }).code, 'STALE_REVISION');
  assert.equal(classifyLearningNowFailure({ status: 422 }).code, 'VALIDATION_ERROR');
  assert.equal(classifyLearningNowFailure({ status: 503 }).code, 'ROUTE_UNAVAILABLE');
  assert.equal(classifyLearningNowFailure(null).code, 'ROUTE_UNAVAILABLE');
});

test('liveness and canonical progress rounding fail closed on stale or invalid values', () => {
  assert.equal(roundProgressPercentHalfUp(1, 200000000), 0.000001);
  assert.equal(roundProgressPercentHalfUp(1, 200000003), 0);
  assert.equal(roundProgressPercentHalfUp(1, 199999997), 0.000001);
  assert.equal(roundProgressPercentHalfUp(9007199254740992, 9007199254740992), null);
  assert.equal(auditProgress(run.state.progress).matchesCanonicalRounding, true);
  assert.equal(auditProgress({ step: 1, total_steps: 3, percent: 33.333332 }).matchesCanonicalRounding, false);

  const fresh = assessRunLiveness({ ...run, state: { ...run.state, updated_at: '2026-07-15T00:01:31Z' } }, Date.parse('2026-07-15T00:02:01Z'));
  assert.equal(fresh.ageSeconds, 30);
  assert.equal(fresh.phase, 'RUNNING');
  assert.equal(fresh.isStale, false);

  const stale = assessRunLiveness(run, Date.parse('2026-07-15T00:02:01Z'));
  assert.equal(stale.ageSeconds, 121);
  assert.equal(stale.phase, 'STALE');
  assert.equal(stale.isStale, true);
});

test('matrix summary preserves canonical order and marks missing cells fail-closed', () => {
  const summary = summarizeMatrix(matrixRoot());
  assert.equal(summary.ordered, true);
  assert.equal(summary.missingCount, 0);
  assert.equal(summary.failClosedStatus, 'READY');
  assert.deepEqual(summary.focusCell, { rowId: 'seed-01', columnId: 'fold-01:cost-23bp', state: 'PASS' });

  const swapped = [matrixCells[1], matrixCells[0], ...matrixCells.slice(2)];
  const orderFailure = summarizeMatrix(matrixRoot(swapped));
  assert.equal(orderFailure.ordered, false);
  assert.equal(orderFailure.missingCount, 0);
  assert.equal(orderFailure.failClosedStatus, 'BLOCKED');

  const missing = summarizeMatrix(matrixRoot(matrixCells.slice(0, -1)));
  assert.equal(missing.missingCount, 1);
  assert.equal(missing.counts.MISSING, 1);
  assert.equal(missing.failClosedStatus, 'BLOCKED');
});

test('accounting labels, governance, locks, and download policy remain fail-closed', () => {
  const ledger = reconcileLedger({
    route_id: 'LEDGER',
    source,
    locks,
    list: {
      items: [
        { entry_id: 'entry-1', occurred_at: utc, kind: 'DEBIT', amount: 5, currency: 'KRONOS_CREDIT', source_sha256: sha256 },
        { entry_id: 'entry-2', occurred_at: utc, kind: 'CREDIT', amount: 8, currency: 'KRONOS_CREDIT', source_sha256: sha256 },
        { entry_id: 'entry-3', occurred_at: utc, kind: 'ADJUSTMENT', amount: -1, currency: 'KRONOS_CREDIT', source_sha256: sha256 },
      ],
      next_cursor: null,
    },
  });
  assert.equal(ledger.status, 'READY');
  assert.equal(ledger.net, 2);
  assert.equal(ledger.labels.economicNavFormula, 'economic_nav = cash + marked_positions - costs');
  assert.match(ledger.labels.shapedRewardBoundary, /not economic NAV/);
  assert.deepEqual(LEARNING_NOW_COST_COMPONENTS.map((component) => `${component.id}=${component.basisPoints}`), [...expectedCostComponents]);

  const d0Blocked = { route_id: 'D0', source, locks, d0: { status: 'PENDING', price_basis: 'UNKNOWN', source_sha256: sha256, updated_at: utc } } as never;
  const d1Pass = { route_id: 'D1', source, locks, d1: { status: 'PASS', universe: 'OFFICIAL', source_sha256: sha256, updated_at: utc } } as never;
  const governance = summarizeGovernance(d0Blocked, d1Pass, { ...locks, model_build_allowed: true } as never);
  assert.equal(governance.d0Code, 'D0_PRICE_BASIS_NOT_VERIFIED');
  assert.equal(governance.freshOosCode, 'FRESH_OOS_NOT_RUN');
  assert.equal(governance.modelVerdict, 'INCONCLUSIVE_NO_GO');
  assert.equal(governance.failClosed, true);
  assert.equal(governance.locks.find((lock) => lock.key === 'model_build_allowed')?.status, 'BLOCKED');

  const noRevisionPolicy = buildDownloadPolicy(null, extractRunIdentity(run));
  assert.equal(noRevisionPolicy.allowed.length, 0);
  assert.equal(noRevisionPolicy.denied[0].reason, 'UID_REVISION_UNAVAILABLE');

  const okIdentity = extractRunIdentity(futureRun);
  const artifactsRoot = {
    route_id: 'ARTIFACTS',
    source,
    locks,
    list: {
      items: [
        {
          artifact: { artifact_id: 'artifact-1', filename: 'report.json', media_type: 'application/json', byte_length: 2, sha256, created_at: utc },
          download_url: '/api/v5/rl/artifacts/artifact-1/download',
          portable_filename: 'report.json',
        },
        {
          artifact: { artifact_id: 'scorecard-v2', filename: 'scorecard.json', media_type: 'application/json', byte_length: 2, sha256, created_at: utc },
          download_url: '/api/v5/rl/artifacts/scorecard-v2/download',
          portable_filename: 'scorecard.json',
        },
      ],
      next_cursor: null,
    },
  } as never;
  const artifactPolicy = buildDownloadPolicy(artifactsRoot, okIdentity);
  assert.equal(artifactPolicy.allowed.length, 2);
  assert.equal(artifactPolicy.allowed[0]?.href, '/api/v5/rl/artifacts/artifact-1/download?run_id=018f0000-0000-7000-8000-000000000001&revision=7');
  assert.equal(findScorecardArtifactSha256(artifactsRoot), sha256);

  const receipt = buildEvidenceReceipt({
    identity: okIdentity,
    sourceSha256: sha256,
    generatedAt: utc,
    governance: summarizeGovernance(null, null, locks),
    matrix: summarizeMatrix(matrixRoot()),
    ledger,
    scorecardArtifactSha256: findScorecardArtifactSha256(artifactsRoot),
  });
  assert.equal(receipt.selected_revision, 7);
  assert.deepEqual((receipt.matrix as Record<string, unknown>).missing_count, 0);
  assert.equal(receipt.scorecard_artifact_sha256, sha256);
  assert.deepEqual(receipt.cost_23bp_components, [...expectedCostComponents]);
  assert.equal((receipt.cost_23bp_components as string[]).length, LEARNING_NOW_COST_COMPONENTS.length);
});
