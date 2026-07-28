export const PROMOTION_LOCK_KEYS = [
  'promotion_allowed',
  'model_build_allowed',
  'paper_forward_allowed',
  'live_broker_order_allowed',
  'profitability_claim_allowed',
  'go_summary_allowed',
] as const;

export type PromotionLockKey = (typeof PROMOTION_LOCK_KEYS)[number];

export type PromotionLocks = Record<PromotionLockKey, boolean>;

export type LockSourceStatus = 'declared' | 'missing' | 'invalid';

export type PromotionLockReason =
  | 'UNLOCKED_BY_SOURCE'
  | 'LOCKED_BY_SOURCE'
  | 'LOCK_SOURCE_MISSING'
  | 'LOCK_SOURCE_INVALID';

export interface PromotionLockState {
  key: PromotionLockKey;
  allowed: boolean;
  sourceStatus: LockSourceStatus;
  reason: PromotionLockReason;
}

export interface PromotionLocksResult {
  locks: PromotionLocks;
  states: Record<PromotionLockKey, PromotionLockState>;
  allLocked: boolean;
  hasInvalidSource: boolean;
}

export interface EvidenceIdentity {
  id: string;
  kind: string;
  label: string;
  source_endpoint: string;
  source_path: string;
  sha256: string;
  modified_at: string;
  artifact_age_seconds: number | null;
  freshness_status: string;
}

export interface RunEvidence {
  run_id: string;
  artifact_type: string;
  line: string;
  is_reinforcement_learning: boolean;
  strategy_label: string;
  baseline_label: string;
  cost_bps: number | null;
  seed: string;
  split: string;
  split_hash: string;
  prereg_doc: string;
  source_endpoint: string;
  lifecycle: string;
  verdict: string;
  blocking_reasons: string[];
  promotion_locks: PromotionLocksResult;
}

export interface MetricValue {
  value: number | null;
  kind: string;
  unit: string;
  availability: 'RECORDED' | 'NOT_RECORDED' | 'INAPPLICABLE';
  source: string;
  precision: number | null;
}

type JsonRecord = Record<string, unknown>;

type LockRead = {
  value: boolean;
  status: LockSourceStatus;
};

const LOCK_CONTAINER_KEYS = [
  'false_locks',
  'research_only_locks',
  'research_locks',
  'guardrail_flags',
] as const;

const LOCK_OBJECT_KEYS = [
  'promotion_locks',
  'locks',
  'safety_locks',
] as const;

const LIFECYCLE_SOURCE_KEYS = [
  'lifecycle',
  'freshness_status',
  'status',
  'run_status',
] as const;

const LIFECYCLE_OBJECT_TEXT_KEYS = [
  'status',
  'state',
  'value',
  'freshness_status',
  'run_status',
  'lifecycle',
] as const;

const LIFECYCLE_WRAPPER_KEYS = [
  'run',
  'record',
  'payload',
  'data',
  'evidence',
  'summary',
  'detail',
  'details',
] as const;

const EXACT_LIFECYCLE_STATES = new Set([
  'ADVANCING',
  'STALLED',
  'RESUMED',
  'RESTARTED_NON_EXACT',
  'STOPPED',
  'FAILED',
  'COMPLETED',
  'CONFLICT_BLOCKED',
  'NOT_RUN',
]);

const STRING_FALLBACKS = {
  id: 'MISSING_ID',
  kind: 'unknown_evidence',
  label: '이름 없음',
  endpoint: 'endpoint_unknown',
  path: 'PATH_NOT_RECORDED',
  hash: 'HASH_NOT_RECORDED',
  time: 'TIME_NOT_RECORDED',
  run: 'MISSING_RUN',
  artifactType: 'unknown',
  strategy: 'UNLABELED_STRATEGY',
  baseline: 'BASELINE_NOT_RECORDED',
  seed: 'SEED_NOT_RECORDED',
  split: 'SPLIT_NOT_RECORDED',
  splitHash: 'SPLIT_HASH_NOT_RECORDED',
  prereg: 'PREREG_DOC_NOT_RECORDED',
  blockers: 'BLOCKERS_NOT_RECORDED',
  metricKind: 'KIND_NOT_RECORDED',
} as const;

function asRecord(value: unknown): JsonRecord | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as JsonRecord)
    : null;
}

function finiteNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function finiteNonNegativeNumber(value: unknown): number | null {
  const next = finiteNumber(value);
  return next !== null && next >= 0 ? next : null;
}

function finiteInteger(value: unknown): number | null {
  const next = finiteNumber(value);
  return next !== null && Number.isInteger(next) ? next : null;
}
function normalizeMetricAvailability(value: unknown): MetricValue['availability'] | null {
  return value === 'RECORDED' || value === 'NOT_RECORDED' || value === 'INAPPLICABLE' ? value : null;
}


function exactString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() !== '' ? value : null;
}

function exactStringOrNumber(value: unknown): string | null {
  if (typeof value === 'string' && value.trim() !== '') {
    return value;
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }
  return null;
}

function exactDeclaredStringOrNumber(value: unknown): string | null {
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }
  return null;
}


function firstString(record: JsonRecord | null, keys: readonly string[]): string | null {
  if (!record) {
    return null;
  }
  for (const key of keys) {
    const value = exactString(record[key]);
    if (value !== null) {
      return value;
    }
  }
  return null;
}

function firstStringOrNumber(record: JsonRecord | null, keys: readonly string[]): string | null {
  if (!record) {
    return null;
  }
  for (const key of keys) {
    const value = exactStringOrNumber(record[key]);
    if (value !== null) {
      return value;
    }
  }
  return null;
}

function firstDeclaredStringOrNumber(record: JsonRecord | null, keys: readonly string[]): string | null {
  if (!record) {
    return null;
  }
  for (const key of keys) {
    if (!hasOwn(record, key)) {
      continue;
    }
    const value = exactDeclaredStringOrNumber(record[key]);
    if (value !== null) {
      return value;
    }
  }
  return null;
}

function firstDeclaredValue(
  records: readonly (JsonRecord | null)[],
  keys: readonly string[],
): { found: boolean; value: unknown } {
  for (const record of records) {
    if (!record) {
      continue;
    }
    for (const key of keys) {
      if (hasOwn(record, key)) {
        return { found: true, value: record[key] };
      }
    }
  }
  return { found: false, value: undefined };
}

function firstBooleanFromRecords(
  records: readonly (JsonRecord | null)[],
  keys: readonly string[],
): boolean | null {
  for (const record of records) {
    if (!record) {
      continue;
    }
    for (const key of keys) {
      if (hasOwn(record, key) && typeof record[key] === 'boolean') {
        return record[key];
      }
    }
  }
  return null;
}

function firstFiniteNumber(record: JsonRecord | null, keys: readonly string[]): number | null {
  if (!record) {
    return null;
  }
  for (const key of keys) {
    const value = finiteNumber(record[key]);
    if (value !== null) {
      return value;
    }
  }
  return null;
}
function declaredFiniteNonNegativeNumber(
  record: JsonRecord | null,
  keys: readonly string[],
): { found: boolean; value: number | null } {
  if (!record) {
    return { found: false, value: null };
  }
  for (const key of keys) {
    if (hasOwn(record, key)) {
      return { found: true, value: finiteNonNegativeNumber(record[key]) };
    }
  }
  return { found: false, value: null };
}


function hasOwn(record: JsonRecord, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(record, key);
}

function stableSha256(value: unknown, fallback: string = STRING_FALLBACKS.hash): string {
  const text = exactString(value);
  return text !== null && /^[a-f0-9]{64}$/i.test(text) ? text : fallback;
}

function parseTime(value: unknown): { text: string; epochMs: number | null } {
  const text = exactStringOrNumber(value);
  if (text === null) {
    return { text: STRING_FALLBACKS.time, epochMs: null };
  }
  const epochMs = Date.parse(text);
  if (!Number.isFinite(epochMs)) {
    return { text: STRING_FALLBACKS.time, epochMs: null };
  }
  return { text, epochMs };
}

function artifactAgeSeconds(record: JsonRecord | null, modifiedEpochMs: number | null): number | null {
  const declaredAge = firstFiniteNumber(record, [
    'artifact_age_seconds',
    'age_seconds',
    'mtime_age_seconds',
    'modified_age_seconds',
  ]);
  if (declaredAge !== null && declaredAge >= 0) {
    return declaredAge;
  }
  if (modifiedEpochMs !== null) {
    return Math.max(0, Math.floor((Date.now() - modifiedEpochMs) / 1000));
  }
  return null;
}

function lifecycleText(value: unknown, depth: number = 0, seen: Set<JsonRecord> = new Set()): string | null {
  const text = exactStringOrNumber(value);
  if (text !== null) {
    return text;
  }

  const record = asRecord(value);
  if (!record || depth >= 5 || seen.has(record)) {
    return null;
  }
  seen.add(record);

  for (const key of LIFECYCLE_OBJECT_TEXT_KEYS) {
    if (!hasOwn(record, key)) {
      continue;
    }
    const child = record[key];
    if (child === null || child === undefined) {
      continue;
    }
    return lifecycleText(child, depth + 1, seen);
  }

  for (const key of LIFECYCLE_WRAPPER_KEYS) {
    const child = asRecord(record[key]);
    if (!child) {
      continue;
    }
    const nested = lifecycleCandidate(child, depth + 1, seen);
    if (nested.found) {
      return lifecycleText(nested.value, depth + 1, seen);
    }
  }

  return null;
}

function normalizeFreshness(value: unknown): string {
  const text = lifecycleText(value);
  if (text === null) {
    return 'MISSING';
  }
  const normalized = text.trim().toUpperCase().replace(/[\s-]+/g, '_');
  if (normalized === 'RUNNING') {
    return 'RUNNING';
  }
  if (normalized === 'COMPLETED' || normalized === 'COMPLETE' || normalized === 'DONE') {
    return 'COMPLETED';
  }
  if (normalized === 'STALE' || normalized === 'EXPIRED') {
    return 'STALE';
  }
  if (normalized === 'REPLAY' || normalized === 'REPLAYED') {
    return 'REPLAY';
  }
  if (normalized === 'IDLE') {
    return 'IDLE';
  }
  if (EXACT_LIFECYCLE_STATES.has(normalized)) {
    return normalized;
  }
  return 'MISSING';
}

function normalizeLine(value: unknown): string {
  const text = exactString(value);
  if (text === null) {
    return 'research_only';
  }
  const normalized = text.trim().toLowerCase().replace(/[\s-]+/g, '_');
  if (
    normalized === 'rl' ||
    normalized === 'reinforcement_learning' ||
    normalized === 'rl_experiment'
  ) {
    return 'RL';
  }
  if (
    normalized === 'rule' ||
    normalized === 'rules' ||
    normalized === 'rule_based' ||
    normalized === 'rule_mainline'
  ) {
    return 'RULE';
  }
  if (
    normalized === 'supervised' ||
    normalized === 'supervised_learning' ||
    normalized === 'supervised_gate'
  ) {
    return 'supervised';
  }
  if (normalized === 'evaluation' || normalized === 'eval') {
    return 'evaluation';
  }
  return text;
}

function resolveCostBps(
  records: readonly (JsonRecord | null)[],
  declaredDefaultCostBps: unknown,
): number | null {
  for (const record of records) {
    const declared = declaredFiniteNonNegativeNumber(record, [
      'cost_bps',
      'costBps',
      'round_trip_cost_bp',
    ]);
    if (declared.found) {
      return declared.value;
    }
    const nested = declaredFiniteNonNegativeNumber(record, ['daily_cost_bps']);
    if (nested.found) {
      return nested.value;
    }
  }
  return finiteNonNegativeNumber(declaredDefaultCostBps);
}


function lifecycleCandidate(
  record: JsonRecord | null,
  depth: number = 0,
  seen: Set<JsonRecord> = new Set(),
): { found: boolean; value: unknown } {
  if (!record || depth >= 5 || seen.has(record)) {
    return { found: false, value: undefined };
  }
  seen.add(record);

  for (const key of LIFECYCLE_SOURCE_KEYS) {
    if (!hasOwn(record, key)) {
      continue;
    }
    const value = record[key];
    if (value !== null && value !== undefined) {
      return { found: true, value };
    }
  }

  for (const key of LIFECYCLE_WRAPPER_KEYS) {
    const child = asRecord(record[key]);
    if (!child) {
      continue;
    }
    const nested = lifecycleCandidate(child, depth + 1, seen);
    if (nested.found) {
      return nested;
    }
  }

  return { found: false, value: undefined };
}

function pickLifecycle(record: JsonRecord | null): string {
  const candidate = lifecycleCandidate(record);
  return candidate.found ? normalizeFreshness(candidate.value) : 'MISSING';
}
function conservativeVerdictCandidate(value: unknown): string | null {
  const text = exactStringOrNumber(value);
  if (text === null) {
    return null;
  }
  const normalized = text.trim().toUpperCase().replace(/[^A-Z0-9]+/g, '_');
  const tokens = normalized.split('_').filter(Boolean);
  const hasOptimisticToken = tokens.some((token, index) => {
    if (token === 'GO' && tokens[index - 1] === 'NO') {
      return false;
    }
    return [
      'GO',
      'PASS',
      'PASSED',
      'READY',
      'LIVE',
      'ACTIVE',
      'PROFIT',
      'PROFITABLE',
      'ALLOWED',
      'APPROVED',
      'PROMOTED',
      'COMPLETED',
      'COMPLETE',
      'DONE',
    ].includes(token);
  });
  if (hasOptimisticToken) {
    return null;
  }
  return text;
}

function firstConservativeVerdict(records: readonly (JsonRecord | null)[]): string | null {
  for (const record of records) {
    if (!record) {
      continue;
    }
    for (const key of ['verdict', 'readiness', 'readiness_status'] as const) {
      const value = conservativeVerdictCandidate(record[key]);
      if (value !== null) {
        return value;
      }
    }
  }
  return null;
}


function readContainerLock(container: unknown, key: PromotionLockKey): LockRead | null {
  const record = asRecord(container);
  if (record) {
    if (!hasOwn(record, key)) {
      return null;
    }
    const value = record[key];
    if (value === null || value === undefined) {
      return { value: false, status: 'missing' };
    }
    if (typeof value === 'boolean') {
      return { value, status: 'declared' };
    }
    return { value: false, status: 'invalid' };
  }

  if (Array.isArray(container)) {
    return container.includes(key) ? { value: false, status: 'declared' } : null;
  }

  return null;
}

function readDirectLock(source: JsonRecord | null, key: PromotionLockKey): LockRead {
  if (!source) {
    return { value: false, status: 'missing' };
  }

  if (hasOwn(source, key)) {
    const value = source[key];
    if (value === null || value === undefined) {
      return { value: false, status: 'missing' };
    }
    if (typeof value === 'boolean') {
      return { value, status: 'declared' };
    }
    return { value: false, status: 'invalid' };
  }

  if (key === 'profitability_claim_allowed' && hasOwn(source, 'profit_claim_allowed')) {
    const value = source.profit_claim_allowed;
    if (value === null || value === undefined) {
      return { value: false, status: 'missing' };
    }
    if (typeof value === 'boolean') {
      return { value, status: 'declared' };
    }
    return { value: false, status: 'invalid' };
  }

  return { value: false, status: 'missing' };
}

function readRecordContainerLock(source: JsonRecord | null, key: PromotionLockKey): LockRead {
  if (!source) {
    return { value: false, status: 'missing' };
  }

  for (const containerKey of LOCK_CONTAINER_KEYS) {
    const fromContainer = readContainerLock(source[containerKey], key);
    if (fromContainer) {
      return fromContainer;
    }
  }

  return { value: false, status: 'missing' };
}

function readLock(source: JsonRecord | null, key: PromotionLockKey): LockRead {
  const direct = readDirectLock(source, key);
  return direct.status === 'missing' ? readRecordContainerLock(source, key) : direct;
}

function stateFor(key: PromotionLockKey, read: LockRead): PromotionLockState {
  if (read.status === 'missing') {
    return { key, allowed: false, sourceStatus: 'missing', reason: 'LOCK_SOURCE_MISSING' };
  }
  if (read.status === 'invalid') {
    return { key, allowed: false, sourceStatus: 'invalid', reason: 'LOCK_SOURCE_INVALID' };
  }
  return {
    key,
    allowed: read.value,
    sourceStatus: 'declared',
    reason: read.value ? 'UNLOCKED_BY_SOURCE' : 'LOCKED_BY_SOURCE',
  };
}

function blockerStrings(value: unknown): string[] {
  const raw = Array.isArray(value) ? value : value === null || value === undefined ? [] : [value];
  const seen = new Set<string>();
  const result: string[] = [];
  for (const item of raw) {
    const text = exactStringOrNumber(item);
    if (text === null || seen.has(text)) {
      continue;
    }
    seen.add(text);
    result.push(text);
  }
  return result.length > 0 ? result : [STRING_FALLBACKS.blockers];
}

function pushUniqueRecord(records: JsonRecord[], seen: Set<JsonRecord>, value: unknown): void {
  const record = asRecord(value);
  if (!record || seen.has(record)) {
    return;
  }
  seen.add(record);
  records.push(record);
}

function collectWrapperRecords(record: JsonRecord | null, keys: readonly string[]): JsonRecord[] {
  const records: JsonRecord[] = [];
  const seen = new Set<JsonRecord>();

  const visit = (value: unknown, depth: number): void => {
    const next = asRecord(value);
    if (!next || seen.has(next) || depth >= 4) {
      return;
    }
    pushUniqueRecord(records, seen, next);
    for (const key of keys) {
      visit(next[key], depth + 1);
    }
  };

  visit(record, 0);
  return records;
}

function collectNestedRecords(records: readonly (JsonRecord | null)[], keys: readonly string[]): JsonRecord[] {
  const result: JsonRecord[] = [];
  const seen = new Set<JsonRecord>();
  for (const record of records) {
    if (!record) {
      continue;
    }
    for (const key of keys) {
      pushUniqueRecord(result, seen, record[key]);
    }
  }
  return result;
}

function collectLockObjectRecords(records: readonly (JsonRecord | null)[]): JsonRecord[] {
  const result: JsonRecord[] = [];
  const seen = new Set<JsonRecord>();
  for (const record of records) {
    if (!record) {
      continue;
    }
    for (const key of LOCK_OBJECT_KEYS) {
      pushUniqueRecord(result, seen, record[key]);
    }
  }
  return result;
}

type LockReader = (record: JsonRecord | null, key: PromotionLockKey) => LockRead;

type LockTier = {
  records: readonly (JsonRecord | null)[];
  read: LockReader;
};

function firstLockRead(
  records: readonly (JsonRecord | null)[],
  key: PromotionLockKey,
  readFromRecord: LockReader,
): LockRead | null {
  for (const record of records) {
    const read = readFromRecord(record, key);
    if (read.status !== 'missing') {
      return read;
    }
  }
  return null;
}

function resolvePromotionLock(
  key: PromotionLockKey,
  tiers: readonly LockTier[],
): LockRead {
  for (const tier of tiers) {
    const read = firstLockRead(tier.records, key, tier.read);
    if (read) {
      return read;
    }
  }
  return { value: false, status: 'missing' };
}

function promotionLocksFromReader(readForKey: (key: PromotionLockKey) => LockRead): PromotionLocksResult {
  const locks = {} as PromotionLocks;
  const states = {} as Record<PromotionLockKey, PromotionLockState>;

  for (const key of PROMOTION_LOCK_KEYS) {
    const state = stateFor(key, readForKey(key));
    locks[key] = state.allowed;
    states[key] = state;
  }

  return {
    locks,
    states,
    allLocked: PROMOTION_LOCK_KEYS.every((key) => locks[key] === false),
    hasInvalidSource: PROMOTION_LOCK_KEYS.some((key) => states[key].sourceStatus === 'invalid'),
  };
}

function adaptPromotionLocksWithProvenance(
  root: JsonRecord | null,
  wrapperRecords: readonly JsonRecord[],
  summaryRecords: readonly JsonRecord[],
  detailRecords: readonly JsonRecord[],
  riskPolicyRecords: readonly JsonRecord[],
): PromotionLocksResult {
  const rootRecords = root ? [root] : [];
  const rootLockObjects = collectLockObjectRecords(rootRecords);
  const wrapperLockObjects = collectLockObjectRecords(wrapperRecords);
  const summaryLockObjects = collectLockObjectRecords(summaryRecords);
  const detailLockObjects = collectLockObjectRecords(detailRecords);
  const riskPolicyLockObjects = collectLockObjectRecords(riskPolicyRecords);
  const tiers: readonly LockTier[] = [
    { records: rootRecords, read: readDirectLock },
    { records: rootLockObjects, read: readLock },
    { records: rootRecords, read: readRecordContainerLock },
    { records: wrapperRecords, read: readDirectLock },
    { records: wrapperLockObjects, read: readLock },
    { records: wrapperRecords, read: readRecordContainerLock },
    { records: summaryRecords, read: readDirectLock },
    { records: summaryLockObjects, read: readLock },
    { records: summaryRecords, read: readRecordContainerLock },
    { records: detailRecords, read: readDirectLock },
    { records: detailLockObjects, read: readLock },
    { records: detailRecords, read: readRecordContainerLock },
    { records: riskPolicyRecords, read: readDirectLock },
    { records: riskPolicyLockObjects, read: readLock },
    { records: riskPolicyRecords, read: readRecordContainerLock },
  ];

  return promotionLocksFromReader((key) => resolvePromotionLock(key, tiers));
}

function firstDeclaredFromRecords(records: readonly (JsonRecord | null)[], keys: readonly string[]): string | null {
  for (const record of records) {
    const value = firstDeclaredStringOrNumber(record, keys);
    if (value !== null) {
      return value;
    }
  }
  return null;
}

function firstFromRecords(records: readonly (JsonRecord | null)[], keys: readonly string[]): string | null {
  for (const record of records) {
    const value = firstStringOrNumber(record, keys);
    if (value !== null) {
      return value;
    }
  }
  return null;
}

export function adaptPromotionLocks(source: unknown): PromotionLocksResult {
  const record = asRecord(source);
  return promotionLocksFromReader((key) => readLock(record, key));
}

export function adaptEvidenceIdentity(
  source: unknown,
  meta: { source_endpoint?: string } = {},
): EvidenceIdentity {
  const record = asRecord(source);
  const modified = parseTime(
    firstFromRecords([record], ['modified_at', 'updated_at', 'mtime', 'timestamp', 'created_at']),
  );
  const id = firstStringOrNumber(record, ['id', 'run_id', 'name', 'slug', 'filename', 'file_name']);
  const label = firstStringOrNumber(record, ['label', 'title', 'display_name', 'name', 'filename', 'file_name']);
  const ageSeconds = artifactAgeSeconds(record, modified.epochMs);
  const freshnessStatus = pickLifecycle(record);
  const safeFreshnessStatus = freshnessStatus === 'RUNNING' && ageSeconds === null ? 'MISSING' : freshnessStatus;

  return {
    id: id ?? STRING_FALLBACKS.id,
    kind: firstString(record, ['kind', 'artifact_type', 'category', 'domain']) ?? STRING_FALLBACKS.kind,
    label: label ?? id ?? STRING_FALLBACKS.label,
    source_endpoint: meta.source_endpoint ?? firstString(record, ['source_endpoint', 'endpoint']) ?? STRING_FALLBACKS.endpoint,
    source_path: firstString(record, ['source_path', 'path', 'file_path', 'artifact_path']) ?? STRING_FALLBACKS.path,
    sha256: stableSha256(firstString(record, ['sha256', 'hash', 'digest'])),
    modified_at: modified.text,
    artifact_age_seconds: ageSeconds,
    freshness_status: safeFreshnessStatus,
  };
}

export function adaptRunEvidence(
  source: unknown,
  options: { source_endpoint?: string; declaredDefaultCostBps?: number } = {},
): RunEvidence {
  const record = asRecord(source);
  const baseRecords = collectWrapperRecords(record, ['run', 'record', 'payload', 'data', 'evidence']);
  const summaryRecords = collectNestedRecords(baseRecords, ['summary', 'run_summary', 'evidence_summary']);
  const detailRecords = collectNestedRecords(baseRecords, ['detail', 'details']);
  const riskPolicyRecords = collectNestedRecords([...detailRecords, ...summaryRecords, ...baseRecords], [
    'risk_policy',
    'risk_policy_summary',
  ]);
  const baseStrategyRecords = collectNestedRecords(baseRecords, ['strategy_context', 'strategy']);
  const nestedStrategyRecords = collectNestedRecords([...summaryRecords, ...detailRecords], [
    'strategy_context',
    'strategy',
  ]);
  const strategyRecords = [...baseStrategyRecords, ...nestedStrategyRecords];
  const strategyEvidenceRecords = [
    ...baseStrategyRecords,
    ...baseRecords,
    ...nestedStrategyRecords,
    ...summaryRecords,
    ...detailRecords,
  ];
  const provenanceRecords = [
    ...baseRecords,
    ...summaryRecords,
    ...detailRecords,
    ...riskPolicyRecords,
    ...strategyRecords,
  ];
  const wrapperRecords = baseRecords.slice(1);
  const promotionLocks = adaptPromotionLocksWithProvenance(
    record,
    wrapperRecords,
    summaryRecords,
    detailRecords,
    riskPolicyRecords,
  );
  const costRecords = [
    ...baseRecords,
    ...detailRecords,
    ...riskPolicyRecords,
    ...summaryRecords,
    ...strategyRecords,
  ];
  const baselineRecords = [
    ...strategyRecords,
    ...baseRecords,
    ...summaryRecords,
    ...detailRecords,
    ...riskPolicyRecords,
  ];
  const declaredCost = resolveCostBps(
    costRecords,
    options.declaredDefaultCostBps,
  );
  const blockerCandidate = firstDeclaredValue(
    provenanceRecords,
    ['blocking_reasons', 'blockers', 'reasons'],
  );
  const explicitRl = firstBooleanFromRecords(
    strategyEvidenceRecords,
    ['is_reinforcement_learning'],
  );

  return {
    run_id: firstFromRecords(baseRecords, ['run_id', 'id', 'name']) ?? STRING_FALLBACKS.run,
    artifact_type: firstFromRecords(baseRecords, ['artifact_type', 'kind', 'type'])
      ?? STRING_FALLBACKS.artifactType,
    line: normalizeLine(
      firstFromRecords(
        strategyEvidenceRecords,
        ['line', 'strategy_line', 'strategy_context', 'type'],
      ),
    ),
    is_reinforcement_learning: explicitRl ?? false,
    strategy_label: firstDeclaredFromRecords(strategyEvidenceRecords, ['strategy_label', 'label'])
      ?? firstFromRecords(baseRecords, ['name', 'run_id', 'id'])
      ?? STRING_FALLBACKS.strategy,
    baseline_label: firstDeclaredFromRecords(
      baselineRecords,
      ['baseline_label', 'primary_baseline', 'baseline'],
    ) ?? STRING_FALLBACKS.baseline,
    cost_bps: declaredCost,
    seed: firstFromRecords(provenanceRecords, ['seed', 'random_seed']) ?? STRING_FALLBACKS.seed,
    split: firstFromRecords(provenanceRecords, ['split', 'split_policy', 'train_test_split'])
      ?? STRING_FALLBACKS.split,
    split_hash: stableSha256(
      firstFromRecords(provenanceRecords, ['split_hash', 'data_split_hash']),
      STRING_FALLBACKS.splitHash,
    ),
    prereg_doc: firstFromRecords(provenanceRecords, ['prereg_doc', 'preregistration_doc', 'prereg_path'])
      ?? STRING_FALLBACKS.prereg,
    source_endpoint: options.source_endpoint
      ?? firstFromRecords(baseRecords, ['source_endpoint', 'endpoint'])
      ?? STRING_FALLBACKS.endpoint,
    lifecycle: pickLifecycle(record),
    verdict: firstConservativeVerdict(provenanceRecords) ?? 'NO-GO/UNKNOWN_BLOCKED',
    blocking_reasons: blockerStrings(blockerCandidate.found ? blockerCandidate.value : undefined),
    promotion_locks: promotionLocks,
  };
}

export function adaptMetricValue(
  source: unknown,
  meta: {
    kind?: string;
    unit?: string;
    source?: string;
    precision?: number;
    availability?: 'RECORDED' | 'NOT_RECORDED' | 'INAPPLICABLE';
  } = {},
): MetricValue {
  const record = asRecord(source);
  const rawValue = record && hasOwn(record, 'value') ? record.value : source;
  const value = finiteNumber(rawValue);
  const precision = finiteInteger(meta.precision) ?? finiteInteger(record?.precision);
  const declaredAvailability = meta.availability ?? normalizeMetricAvailability(record?.availability);
  const availability = value === null
    ? declaredAvailability === 'INAPPLICABLE'
      ? 'INAPPLICABLE'
      : 'NOT_RECORDED'
    : declaredAvailability ?? 'RECORDED';

  return {
    value,
    kind: meta.kind ?? firstString(record, ['kind', 'metric_kind', 'name']) ?? STRING_FALLBACKS.metricKind,
    unit: meta.unit ?? firstString(record, ['unit', 'units']) ?? 'UNIT_NOT_RECORDED',
    availability,
    source: meta.source ?? firstString(record, ['source', 'source_endpoint', 'endpoint']) ?? STRING_FALLBACKS.endpoint,
    precision,
  };
}
