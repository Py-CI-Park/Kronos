import type {
  ArtifactsRoot,
  D0Root,
  D1Root,
  Download,
  FixtureRoot,
  LedgerEntry,
  LedgerRoot,
  Locks,
  MatrixCell,
  MatrixRoot,
  Progress,
  Run,
  RunsRoot,
  V5DeepReadonly,
} from '../lib/generated/kronosRlApiV2';
import { V5LearningFetchError } from '../lib/rlApi';

export const LEARNING_NOW_ROUTE_PATHS = ['/learning-now', '/v5/learning-now'] as const;

export function isLearningNowRouteLocation(
  locationLike: Pick<Location, 'pathname' | 'search'> | null,
): boolean {
  if (!locationLike) return false;
  const normalizedPath = locationLike.pathname.replace(/\/+$/, '') || '/';
  const requestedTab = new URLSearchParams(locationLike.search).get('tab');
  return requestedTab === 'learning-now'
    || LEARNING_NOW_ROUTE_PATHS.includes(normalizedPath as (typeof LEARNING_NOW_ROUTE_PATHS)[number]);
}
export const LEARNING_NOW_UX_REVISION = 'kronos_dashboard_v5_usability_instrument.v1@2026-07-15';
export const LEARNING_NOW_STALE_AFTER_SECONDS = 120;
export const LEARNING_NOW_FOCUS_SEED = 'seed-01';
export const LEARNING_NOW_FOCUS_COLUMN = 'fold-01:cost-23bp';

export const V5_MATRIX_ROWS = ['seed-01', 'seed-02', 'seed-03', 'seed-04', 'seed-05'] as const;
export const V5_MATRIX_COLUMNS = [
  'fold-01:baseline',
  'fold-01:cost-00bp',
  'fold-01:cost-23bp',
  'fold-01:cost-46bp',
  'fold-01:no-trade',
  'fold-02:baseline',
  'fold-02:cost-00bp',
  'fold-02:cost-23bp',
  'fold-02:cost-46bp',
  'fold-02:no-trade',
] as const;

export const LOCK_KEYS = [
  'promotion_allowed',
  'model_build_allowed',
  'paper_forward_allowed',
  'live_broker_order_allowed',
  'profitability_claim_allowed',
  'go_summary_allowed',
] as const;

export const LEARNING_NOW_ACCOUNTING_LABELS = Object.freeze({
  economicNavName: 'economic_nav',
  economicNavFormula: 'economic_nav = cash + marked_positions - costs',
  economicNavUnit: 'net_cash_nav',
  shapedRewardName: 'shaped_reward',
  shapedRewardBoundary: 'shaped_reward is train-only reward and is not economic NAV',
  costBasis: 'five-component 23bp round trip research accounting',
  horizon: 'D0 price basis + D1 universe gate; fresh OOS is NOT_RUN custody, not a model result',
});
export const LEARNING_NOW_SOURCE_PROTOCOL_LABEL = 'kronos_rl_api_v2.source_sha256';

export const LEARNING_NOW_COST_COMPONENTS = Object.freeze([
  Object.freeze({ id: 'sell_tax_bp', basisPoints: 20 }),
  Object.freeze({ id: 'buy_commission_bp', basisPoints: 1.5 }),
  Object.freeze({ id: 'sell_commission_bp', basisPoints: 1.5 }),
  Object.freeze({ id: 'buy_slippage_bp', basisPoints: 0 }),
  Object.freeze({ id: 'sell_slippage_bp', basisPoints: 0 }),
] as const);

export const LEARNING_NOW_GOVERNANCE_LABELS = Object.freeze({
  notRunNonResult: 'FRESH_OOS_NOT_RUN is custody/status governance, not a fresh OOS model result',
  matrixControls: '5 seeds x 2 folds x baseline/0bp/23bp/46bp/no-trade controls; missing or stopped cells fail closed',
  retryFocus: 'Retry stays bound to the selected run_uid and safe run_revision; focus cell is seed-01/fold-01:cost-23bp',
  rollback: 'Late route completions are ignored unless sequence, UID, revision, and display run_id still match',
});

type MatrixRowId = (typeof V5_MATRIX_ROWS)[number];
type MatrixColumnId = (typeof V5_MATRIX_COLUMNS)[number];
type MatrixState = MatrixCell['state'];
type ReadonlyRun = V5DeepReadonly<Run>;
type ReadonlyRunsRoot = V5DeepReadonly<RunsRoot>;
type ReadonlyFixtureRoot = V5DeepReadonly<FixtureRoot>;
type ReadonlyMatrixRoot = V5DeepReadonly<MatrixRoot>;
type ReadonlyLedgerRoot = V5DeepReadonly<LedgerRoot>;
type ReadonlyD0Root = V5DeepReadonly<D0Root>;
type ReadonlyD1Root = V5DeepReadonly<D1Root>;
type ReadonlyArtifactsRoot = V5DeepReadonly<ArtifactsRoot>;
type ReadonlyLocks = V5DeepReadonly<Locks>;
type ReadonlyDownload = V5DeepReadonly<Download>;
type ReadonlyLedgerEntry = V5DeepReadonly<LedgerEntry>;
type ReadonlyProgress = V5DeepReadonly<Progress>;
const sha256Pattern = /^[0-9a-f]{64}$/u;
const runUidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const revisionPattern = /^[1-9][0-9]{0,15}$/u;
const maxSafeRevision = Number.MAX_SAFE_INTEGER;

export type LearningNowBlockerCode =
  | 'OK'
  | 'UID_UNAVAILABLE'
  | 'REVISION_UNAVAILABLE'
  | 'UID_REVISION_UNAVAILABLE';

export type LearningNowRouteCode =
  | 'READY'
  | 'LOADING'
  | 'ROUTE_UNAVAILABLE'
  | 'CONFLICT_409'
  | 'STALE_REVISION'
  | 'VALIDATION_ERROR'
  | 'BLOCKED_BY_REVISION'
  | 'UNKNOWN_ERROR';

export interface LearningNowProvenance {
  readonly registryEpoch: string | null;
  readonly snapshotGlobalSeq: string | null;
}

export interface LearningNowRunIdentity {
  readonly uid: string | null;
  readonly revision: number | null;
  readonly displayRunId: string;
  readonly provenance: LearningNowProvenance;
  readonly canRequestDetail: boolean;
  readonly canRequestDownloads: boolean;
  readonly blockerCode: LearningNowBlockerCode;
}

export interface LearningNowRunCandidate {
  readonly run: ReadonlyRun;
  readonly identity: LearningNowRunIdentity;
  readonly sourceSha256: string;
  readonly fromFixture: boolean;
  readonly fixtureUid: string | null;
}

export interface LearningNowSelection {
  readonly candidates: readonly LearningNowRunCandidate[];
  readonly selected: LearningNowRunCandidate | null;
  readonly requestedUid: string | null;
  readonly requestedRunId: string | null;
  readonly requestedRevision: number | null;
  readonly status: 'SELECTED' | 'EMPTY' | 'REQUESTED_UID_NOT_FOUND';
}

export interface LearningNowLoadStamp {
  readonly sequence: number;
  readonly uid: string | null;
  readonly revision: number | null;
  readonly displayRunId: string | null;
}

export interface LearningNowFailure {
  readonly code: LearningNowRouteCode;
  readonly message: string;
  readonly retryable: boolean;
}

export interface ProgressAudit {
  readonly step: number | null;
  readonly totalSteps: number | null;
  readonly reportedPercent: number | null;
  readonly expectedPercent: number | null;
  readonly matchesCanonicalRounding: boolean;
  readonly label: string;
}

export interface LearningNowLiveness {
  readonly status: ReadonlyRun['state']['status'] | 'UNKNOWN';
  readonly phase: 'QUEUED' | 'RUNNING' | 'STALE' | 'STOPPED' | 'SUCCEEDED' | 'UNKNOWN';
  readonly updatedAt: string | null;
  readonly ageSeconds: number | null;
  readonly isStale: boolean;
  readonly label: string;
}

export interface LearningNowMatrixSummary {
  readonly rows: readonly MatrixRowId[];
  readonly columns: readonly MatrixColumnId[];
  readonly ordered: boolean;
  readonly missingCount: number;
  readonly extraCount: number;
  readonly stoppedCount: number;
  readonly counts: Readonly<Record<MatrixState | 'MISSING', number>>;
  readonly focusCell: { readonly rowId: MatrixRowId; readonly columnId: MatrixColumnId; readonly state: MatrixState | 'MISSING' };
  readonly failClosedStatus: 'READY' | 'BLOCKED';
  readonly tableRows: readonly (readonly string[])[];
}

export interface LedgerReconciliation {
  readonly status: 'READY' | 'BLOCKED';
  readonly debit: number;
  readonly credit: number;
  readonly adjustment: number;
  readonly net: number;
  readonly entryCount: number;
  readonly currency: 'KRONOS_CREDIT' | 'MIXED_OR_MISSING';
  readonly labels: typeof LEARNING_NOW_ACCOUNTING_LABELS;
  readonly rows: readonly (readonly string[])[];
}

export interface LockSummary {
  readonly key: (typeof LOCK_KEYS)[number];
  readonly value: boolean | null;
  readonly status: 'FALSE_LOCKED' | 'BLOCKED';
}

export interface GovernanceSummary {
  readonly d0Code: 'D0_PRICE_BASIS_VERIFIED' | 'D0_PRICE_BASIS_NOT_VERIFIED';
  readonly d1Code: 'D1_UNIVERSE_VERIFIED' | 'D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED';
  readonly freshOosCode: 'FRESH_OOS_NOT_RUN';
  readonly modelVerdict: 'INCONCLUSIVE_NO_GO';
  readonly failClosed: boolean;
  readonly locks: readonly LockSummary[];
}

export interface LearningNowBoundDownload {
  readonly download: ReadonlyDownload;
  readonly href: string;
  readonly runUid: string;
  readonly revision: number;
}

export interface DownloadPolicy {
  readonly allowed: readonly LearningNowBoundDownload[];
  readonly denied: readonly { readonly id: string; readonly reason: string }[];
}

export interface EvidenceReceiptInput {
  readonly identity: LearningNowRunIdentity;
  readonly sourceSha256?: string | null;
  readonly generatedAt?: string | null;
  readonly governance: GovernanceSummary;
  readonly matrix: LearningNowMatrixSummary;
  readonly ledger: LedgerReconciliation;
  readonly scorecardArtifactSha256?: string | null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function optionalString(source: unknown, key: string): string | null {
  if (!isRecord(source)) return null;
  const value = source[key];
  return typeof value === 'string' && value.trim().length > 0 ? value : null;
}
export function isLearningNowRunUid(value: string | null | undefined): value is string {
  return typeof value === 'string' && runUidPattern.test(value);
}

export function parseLearningNowRevision(value: number | string | null | undefined): number | null {
  if (typeof value === 'number') {
    return Number.isSafeInteger(value) && value >= 1 && value <= maxSafeRevision ? value : null;
  }
  if (typeof value !== 'string' || !revisionPattern.test(value)) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= 1 && parsed <= maxSafeRevision ? parsed : null;
}

function optionalRunUid(source: unknown, key: string): string | null {
  const value = optionalString(source, key);
  return isLearningNowRunUid(value) ? value : null;
}

function optionalRevision(source: unknown, key: string): number | null {
  if (!isRecord(source)) return null;
  return parseLearningNowRevision(source[key] as number | string | null | undefined);
}

function optionalSeq(source: unknown, key: string): string | null {
  if (!isRecord(source)) return null;
  const value = source[key];
  if (typeof value === 'string' && value.trim().length > 0) return value;
  if (typeof value === 'number' && Number.isSafeInteger(value)) return String(value);
  if (typeof value === 'bigint') return value.toString();
  return null;
}

function cleanSelection(value?: string | null): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function rootProvenance(root?: unknown): LearningNowProvenance {
  const provenance = isRecord(root) ? root.provenance : undefined;
  return {
    registryEpoch: optionalSeq(provenance, 'registry_epoch'),
    snapshotGlobalSeq: optionalSeq(provenance, 'snapshot_global_seq'),
  };
}
function identityBlocker(uid: string | null, revision: number | null): LearningNowBlockerCode {
  return uid && revision !== null
    ? 'OK'
    : uid
      ? 'REVISION_UNAVAILABLE'
      : revision !== null
        ? 'UID_UNAVAILABLE'
        : 'UID_REVISION_UNAVAILABLE';
}


export function extractRunIdentity(run: ReadonlyRun | null | undefined, root?: unknown): LearningNowRunIdentity {
  const displayRunId = run?.run_id ?? 'RUN_UNAVAILABLE';
  const uid = optionalRunUid(run, 'run_uid')
    ?? optionalRunUid(root, 'run_uid')
    ?? optionalRunUid(run, 'run_id')
    ?? optionalRunUid(root, 'run_id');
  const revision = optionalRevision(run, 'run_revision')
    ?? optionalRevision(root, 'run_revision')
    ?? optionalRevision(run, 'revision')
    ?? optionalRevision(root, 'revision');
  const blockerCode = identityBlocker(uid, revision);
  const canRequest = blockerCode === 'OK';
  return {
    uid,
    revision,
    displayRunId,
    provenance: rootProvenance(root),
    canRequestDetail: canRequest,
    canRequestDownloads: canRequest,
    blockerCode,
  };
}

export function bindLearningNowIdentityRevision(identity: LearningNowRunIdentity, revision?: number | null): LearningNowRunIdentity {
  const fallbackRevision = parseLearningNowRevision(revision);
  if (identity.revision !== null || fallbackRevision === null) return identity;
  const blockerCode = identityBlocker(identity.uid, fallbackRevision);
  const canRequest = blockerCode === 'OK';
  return {
    ...identity,
    revision: fallbackRevision,
    canRequestDetail: canRequest,
    canRequestDownloads: canRequest,
    blockerCode,
  };
}

export function buildLearningNowCandidates(runsRoot: ReadonlyRunsRoot | null | undefined, fixtureRoot?: ReadonlyFixtureRoot | null): readonly LearningNowRunCandidate[] {
  const candidates: LearningNowRunCandidate[] = [];
  const seen = new Set<string>();
  const addCandidate = (run: ReadonlyRun, root: ReadonlyRunsRoot | ReadonlyFixtureRoot, fromFixture: boolean) => {
    const identity = extractRunIdentity(run, root);
    const seenKey = identity.uid ?? run.run_id;
    if (seen.has(seenKey)) return;
    seen.add(seenKey);
    const fixtureUid = fromFixture && 'fixture' in root ? root.fixture.fixture_id : null;
    candidates.push({
      run,
      identity,
      sourceSha256: root.source.source_sha256,
      fromFixture,
      fixtureUid,
    });
  };

  if (fixtureRoot?.fixture.run) addCandidate(fixtureRoot.fixture.run, fixtureRoot, true);
  for (const run of runsRoot?.list.items ?? []) addCandidate(run, runsRoot, false);
  return candidates;
}

export function selectLearningNowCandidate(
  runsRoot: ReadonlyRunsRoot | null | undefined,
  fixtureRoot: ReadonlyFixtureRoot | null | undefined,
  request: { readonly uid?: string | null; readonly runId?: string | null; readonly revision?: number | string | null } = {},
): LearningNowSelection {
  const requestedUid = cleanSelection(request.uid);
  const requestedRunId = cleanSelection(request.runId);
  const requestedRevision = parseLearningNowRevision(request.revision);
  const candidates = buildLearningNowCandidates(runsRoot, fixtureRoot);
  if (candidates.length === 0) return { candidates, selected: null, requestedUid, requestedRunId, requestedRevision, status: 'EMPTY' };

  if (requestedUid) {
    const selected = candidates.find((candidate) => candidate.identity.uid === requestedUid || candidate.fixtureUid === requestedUid) ?? null;
    return {
      candidates,
      selected,
      requestedUid,
      requestedRunId,
      requestedRevision,
      status: selected ? 'SELECTED' : 'REQUESTED_UID_NOT_FOUND',
    };
  }

  const selected = requestedRunId
    ? candidates.find((candidate) => candidate.run.run_id === requestedRunId) ?? candidates[0]
    : candidates.find((candidate) => candidate.identity.canRequestDetail) ?? candidates[0];
  return { candidates, selected, requestedUid, requestedRunId, requestedRevision, status: 'SELECTED' };
}

export function createLearningNowLoadStamp(sequence: number, identity?: LearningNowRunIdentity | null): LearningNowLoadStamp {
  return {
    sequence,
    uid: identity?.uid ?? null,
    revision: identity?.revision ?? null,
    displayRunId: identity?.displayRunId ?? null,
  };
}

export function shouldApplyLearningNowResult(active: LearningNowLoadStamp | null | undefined, incoming: LearningNowLoadStamp): boolean {
  return Boolean(active)
    && active?.sequence === incoming.sequence
    && active.uid === incoming.uid
    && active.revision === incoming.revision
    && active.displayRunId === incoming.displayRunId;
}

export function classifyLearningNowFailure(error: unknown): LearningNowFailure {
  if (error === null || error === undefined) {
    return { code: 'ROUTE_UNAVAILABLE', message: 'V5 route returned no payload.', retryable: true };
  }
  if (typeof error === 'number' && error === 409) {
    return { code: 'CONFLICT_409', message: 'Registry revision conflict; reload the immutable selection.', retryable: true };
  }
  if (error instanceof V5LearningFetchError) {
    const detail = `${error.payload.error.code}: ${error.payload.error.message}`;
    if (error.status === 409) {
      return { code: 'CONFLICT_409', message: `Registry revision conflict; reload the immutable selection. ${detail}`, retryable: true };
    }
    if (error.status === 410 || error.code === 'INVALID_CURSOR') {
      return { code: 'STALE_REVISION', message: `Cursor or revision is stale for the current snapshot. ${detail}`, retryable: true };
    }
    if (error.status === 422) {
      return { code: 'VALIDATION_ERROR', message: `Validated V5 payload failed closed. ${detail}`, retryable: false };
    }
    if (error.status === 503) {
      return { code: 'ROUTE_UNAVAILABLE', message: `V5 route is unavailable. ${detail}`, retryable: true };
    }
  }
  if (isRecord(error)) {
    const status = error.status ?? error.httpStatus ?? error.responseStatus;
    const code = error.code;
    if (status === 409 || code === 'CONFLICT' || code === 'CONFLICT_409') {
      return { code: 'CONFLICT_409', message: 'Registry revision conflict; reload the immutable selection.', retryable: true };
    }
    if (status === 410 || code === 'STALE_REVISION' || code === 'INVALID_CURSOR') {
      return { code: 'STALE_REVISION', message: 'Cursor or revision is stale for the current snapshot.', retryable: true };
    }
    if (status === 422 || code === 'V5_SCHEMA_VALIDATION_ERROR' || code === 'VALIDATION_ERROR') {
      return { code: 'VALIDATION_ERROR', message: 'Validated V5 payload failed closed.', retryable: false };
    }
    if (status === 503) {
      return { code: 'ROUTE_UNAVAILABLE', message: 'V5 route is unavailable.', retryable: true };
    }
  }
  return { code: 'UNKNOWN_ERROR', message: 'Unexpected V5 route error.', retryable: true };
}

export function roundProgressPercentHalfUp(step: number, totalSteps: number): number | null {
  if (!Number.isSafeInteger(step) || !Number.isSafeInteger(totalSteps) || step < 0 || totalSteps < 1 || step > totalSteps) {
    return null;
  }
  const numerator = BigInt(step) * 100000000n;
  const denominator = BigInt(totalSteps);
  const quotient = numerator / denominator;
  const remainder = numerator % denominator;
  return Number(quotient + (remainder * 2n >= denominator ? 1n : 0n)) / 1000000;
}

export function auditProgress(progress?: ReadonlyProgress | null): ProgressAudit {
  if (!progress) {
    return {
      step: null,
      totalSteps: null,
      reportedPercent: null,
      expectedPercent: null,
      matchesCanonicalRounding: false,
      label: 'PROGRESS_UNAVAILABLE',
    };
  }
  const expectedPercent = roundProgressPercentHalfUp(progress.step, progress.total_steps);
  const matchesCanonicalRounding = expectedPercent !== null && progress.percent === expectedPercent;
  return {
    step: progress.step,
    totalSteps: progress.total_steps,
    reportedPercent: progress.percent,
    expectedPercent,
    matchesCanonicalRounding,
    label: `step=${progress.step}/${progress.total_steps} percent=${formatPercent(progress.percent)}`,
  };
}

export function formatPercent(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'UNAVAILABLE';
  return value.toFixed(6).replace(/\.0+$/u, '.000000');
}

function parseUtcMillis(value: string | null | undefined): number | null {
  if (!value) return null;
  const millis = Date.parse(value);
  return Number.isFinite(millis) ? millis : null;
}

export function assessRunLiveness(
  run: ReadonlyRun | null | undefined,
  nowMs: number = Date.now(),
  staleAfterSeconds: number = LEARNING_NOW_STALE_AFTER_SECONDS,
): LearningNowLiveness {
  if (!run) {
    return { status: 'UNKNOWN', phase: 'UNKNOWN', updatedAt: null, ageSeconds: null, isStale: true, label: 'RUN_UNAVAILABLE' };
  }
  const updatedAt = run.state.updated_at;
  const updatedMillis = parseUtcMillis(updatedAt);
  const ageSeconds = updatedMillis === null ? null : Math.max(0, Math.floor((nowMs - updatedMillis) / 1000));
  const stale = ageSeconds === null || (run.state.status === 'RUNNING' && ageSeconds > staleAfterSeconds);
  const phase = stale
    ? 'STALE'
    : run.state.status === 'SUCCEEDED'
      ? 'SUCCEEDED'
      : run.state.status === 'FAILED' || run.state.status === 'CANCELLED'
        ? 'STOPPED'
        : run.state.status;
  const progress = auditProgress(run.state.progress);
  return {
    status: run.state.status,
    phase,
    updatedAt,
    ageSeconds,
    isStale: stale,
    label: `Learning Now: ${run.state.status} ${progress.label}`,
  };
}

function matrixKey(rowId: string, columnId: string): string {
  return `${rowId}\u0000${columnId}`;
}

function expectedMatrixKeys(): readonly (readonly [MatrixRowId, MatrixColumnId])[] {
  return V5_MATRIX_ROWS.flatMap((row) => V5_MATRIX_COLUMNS.map((column) => [row, column] as const));
}

export function summarizeMatrix(matrixRoot?: ReadonlyMatrixRoot | null): LearningNowMatrixSummary {
  const cells = matrixRoot?.cells ?? [];
  const actual = new Map(cells.map((cell) => [matrixKey(cell.row_id, cell.column_id), cell]));
  const expected = expectedMatrixKeys();
  const expectedSet = new Set(expected.map(([row, column]) => matrixKey(row, column)));
  const missing = expected.filter(([row, column]) => !actual.has(matrixKey(row, column)));
  const ordered = cells.length === expected.length && expected.every(([row, column], index) => {
    const cell = cells[index];
    return cell?.row_id === row && cell?.column_id === column;
  });
  const extraCount = cells.filter((cell) => !expectedSet.has(matrixKey(cell.row_id, cell.column_id))).length;
  const counts: Record<MatrixState | 'MISSING', number> = { PASS: 0, FAIL: 0, BLOCKED: 0, PENDING: 0, MISSING: missing.length };
  for (const cell of cells) counts[cell.state] += 1;
  const focus = actual.get(matrixKey(LEARNING_NOW_FOCUS_SEED, LEARNING_NOW_FOCUS_COLUMN));
  const tableRows = V5_MATRIX_ROWS.map((row) => [
    row,
    ...V5_MATRIX_COLUMNS.map((column) => actual.get(matrixKey(row, column))?.state ?? 'MISSING'),
  ]);
  return {
    rows: V5_MATRIX_ROWS,
    columns: V5_MATRIX_COLUMNS,
    ordered,
    missingCount: missing.length,
    extraCount,
    stoppedCount: counts.FAIL + counts.BLOCKED,
    counts,
    focusCell: { rowId: LEARNING_NOW_FOCUS_SEED, columnId: LEARNING_NOW_FOCUS_COLUMN, state: focus?.state ?? 'MISSING' },
    failClosedStatus: ordered && missing.length === 0 && extraCount === 0 ? 'READY' : 'BLOCKED',
    tableRows,
  };
}

function sumLedger(entries: readonly ReadonlyLedgerEntry[], kind: ReadonlyLedgerEntry['kind']): number {
  return entries.filter((entry) => entry.kind === kind).reduce((total, entry) => total + entry.amount, 0);
}

export function reconcileLedger(ledgerRoot?: ReadonlyLedgerRoot | null): LedgerReconciliation {
  const entries = ledgerRoot?.list.items ?? [];
  const debit = sumLedger(entries, 'DEBIT');
  const credit = sumLedger(entries, 'CREDIT');
  const adjustment = sumLedger(entries, 'ADJUSTMENT');
  const currencies = new Set(entries.map((entry) => entry.currency));
  const currency = currencies.size <= 1 && (currencies.size === 0 || currencies.has('KRONOS_CREDIT'))
    ? 'KRONOS_CREDIT'
    : 'MIXED_OR_MISSING';
  const rows = entries.map((entry) => [entry.entry_id, entry.occurred_at, entry.kind, String(entry.amount), entry.currency]);
  return {
    status: ledgerRoot && currency === 'KRONOS_CREDIT' ? 'READY' : 'BLOCKED',
    debit,
    credit,
    adjustment,
    net: credit + adjustment - debit,
    entryCount: entries.length,
    currency,
    labels: LEARNING_NOW_ACCOUNTING_LABELS,
    rows,
  };
}

export function summarizeLocks(locks?: ReadonlyLocks | null): readonly LockSummary[] {
  return LOCK_KEYS.map((key) => {
    const value = locks?.[key] ?? null;
    return { key, value, status: value === false ? 'FALSE_LOCKED' : 'BLOCKED' };
  });
}

export function summarizeGovernance(d0Root?: ReadonlyD0Root | null, d1Root?: ReadonlyD1Root | null, locks?: ReadonlyLocks | null): GovernanceSummary {
  const d0 = d0Root?.d0;
  const d1 = d1Root?.d1;
  const d0Verified = d0?.status === 'PASS' && (d0.price_basis === 'RAW' || d0.price_basis === 'ADJUSTED');
  const d1Verified = d1?.status === 'PASS' && (d1.universe === 'OFFICIAL' || d1.universe === 'MANUAL_REVIEWED');
  const lockSummary = summarizeLocks(locks);
  const failClosed = !d0Verified || !d1Verified || lockSummary.some((lock) => lock.status !== 'FALSE_LOCKED');
  return {
    d0Code: d0Verified ? 'D0_PRICE_BASIS_VERIFIED' : 'D0_PRICE_BASIS_NOT_VERIFIED',
    d1Code: d1Verified ? 'D1_UNIVERSE_VERIFIED' : 'D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED',
    freshOosCode: 'FRESH_OOS_NOT_RUN',
    modelVerdict: 'INCONCLUSIVE_NO_GO',
    failClosed,
    locks: lockSummary,
  };
}

function extensionForMedia(mediaType: ReadonlyDownload['artifact']['media_type']): string {
  if (mediaType === 'application/json') return 'json';
  if (mediaType === 'text/csv') return 'csv';
  if (mediaType === 'application/jsonl') return 'jsonl';
  if (mediaType === 'text/markdown') return 'md';
  return 'png';
}

export function isBoundSecureDownload(download: ReadonlyDownload): boolean {
  const extension = download.artifact.filename.split('.').at(-1);
  let parsed: URL;
  try {
    parsed = new URL(download.download_url, 'https://kronos.invalid');
  } catch {
    return false;
  }
  return download.download_url.startsWith('/api/v5/rl/artifacts/')
    && parsed.origin === 'https://kronos.invalid'
    && parsed.pathname === `/api/v5/rl/artifacts/${download.artifact.artifact_id}/download`
    && parsed.search === ''
    && parsed.hash === ''
    && download.portable_filename === download.artifact.filename
    && extension === extensionForMedia(download.artifact.media_type)
    && sha256Pattern.test(download.artifact.sha256);
}

export function bindSecureDownload(download: ReadonlyDownload, identity: LearningNowRunIdentity): LearningNowBoundDownload | null {
  if (!identity.uid || identity.revision === null || !isBoundSecureDownload(download)) return null;
  const params = new URLSearchParams();
  params.set('run_id', identity.uid);
  params.set('revision', String(identity.revision));
  return {
    download,
    href: `${download.download_url}?${params.toString()}`,
    runUid: identity.uid,
    revision: identity.revision,
  };
}

export function findScorecardArtifactSha256(artifactsRoot: ReadonlyArtifactsRoot | null | undefined): string | null {
  const match = (artifactsRoot?.list.items ?? []).find((item) => /scorecard/iu.test(item.artifact.filename));
  return match?.artifact.sha256 ?? null;
}

export function formatBasisPoints(value: number): string {
  return Number.isInteger(value) ? `${value}bp` : `${value.toFixed(1)}bp`;
}

export function buildDownloadPolicy(artifactsRoot: ReadonlyArtifactsRoot | null | undefined, identity: LearningNowRunIdentity): DownloadPolicy {
  const denied = [{ id: 'raw_oos_download', reason: 'FRESH_OOS_NOT_RUN' }];
  if (!identity.canRequestDownloads) {
    return { allowed: [], denied: [{ id: 'artifact_downloads', reason: identity.blockerCode }, ...denied] };
  }
  const bound = (artifactsRoot?.list.items ?? [])
    .map((download) => bindSecureDownload(download, identity))
    .filter((download): download is LearningNowBoundDownload => download !== null);
  return {
    allowed: bound,
    denied,
  };
}

export function buildEvidenceReceipt(input: EvidenceReceiptInput): Readonly<Record<string, unknown>> {
  return Object.freeze({
    schema: 'kronos_learning_now_evidence.v1',
    ux_revision: LEARNING_NOW_UX_REVISION,
    selected_uid: input.identity.uid ?? 'UID_UNAVAILABLE',
    selected_revision: input.identity.revision ?? 'REVISION_UNAVAILABLE',
    display_run_id: input.identity.displayRunId,
    registry_epoch: input.identity.provenance.registryEpoch ?? 'PROVENANCE_UNAVAILABLE',
    snapshot_global_seq: input.identity.provenance.snapshotGlobalSeq ?? 'PROVENANCE_UNAVAILABLE',
    source_sha256: input.sourceSha256 ?? 'SOURCE_UNAVAILABLE',
    source_protocol: LEARNING_NOW_SOURCE_PROTOCOL_LABEL,
    generated_at: input.generatedAt ?? 'GENERATED_AT_UNAVAILABLE',
    d0: input.governance.d0Code,
    d1: input.governance.d1Code,
    fresh_oos: input.governance.freshOosCode,
    verdict: input.governance.modelVerdict,
    locks: input.governance.locks.map((lock) => `${lock.key}=${String(lock.value)}`),
    cost_23bp_components: LEARNING_NOW_COST_COMPONENTS.map((component) => `${component.id}=${component.basisPoints}`),
    scorecard_artifact_sha256: input.scorecardArtifactSha256 ?? 'SCORECARD_ARTIFACT_NOT_IN_API_METADATA',
    matrix: {
      ordered: input.matrix.ordered,
      missing_count: input.matrix.missingCount,
      focus: `${input.matrix.focusCell.rowId};${input.matrix.focusCell.columnId};${input.matrix.focusCell.state}`,
    },
    ledger: {
      status: input.ledger.status,
      debit: input.ledger.debit,
      credit: input.ledger.credit,
      adjustment: input.ledger.adjustment,
      net: input.ledger.net,
      label: input.ledger.labels.economicNavFormula,
    },
  });
}
