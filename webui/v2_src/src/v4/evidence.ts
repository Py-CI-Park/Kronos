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

function normalizeFreshness(value: unknown): string {
  const text = exactString(value);
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
  return 'MISSING';
}

function normalizeLine(value: unknown): string {
  const text = exactString(value);
  if (text === null) {
    return 'research_only';
  }
  const normalized = text.trim().toLowerCase().replace(/[\s-]+/g, '_');
  if (normalized === 'rl' || normalized === 'reinforcement_learning') {
    return 'RL';
  }
  if (normalized === 'rule' || normalized === 'rules' || normalized === 'rule_based') {
    return 'RULE';
  }
  if (normalized === 'supervised' || normalized === 'supervised_learning') {
    return 'supervised';
  }
  if (normalized === 'evaluation' || normalized === 'eval') {
    return 'evaluation';
  }
  return text;
}
function resolveCostBps(
  record: JsonRecord | null,
  detail: JsonRecord | null,
  declaredDefaultCostBps: unknown,
): number | null {
  const topLevel = declaredFiniteNonNegativeNumber(record, ['cost_bps', 'costBps']);
  if (topLevel.found) {
    return topLevel.value;
  }
  const nested = declaredFiniteNonNegativeNumber(detail, ['cost_bps', 'daily_cost_bps']);
  if (nested.found) {
    return nested.value;
  }
  return finiteNonNegativeNumber(declaredDefaultCostBps);
}


function pickLifecycle(record: JsonRecord | null): string {
  return normalizeFreshness(
    firstString(record, ['lifecycle', 'freshness_status', 'status', 'run_status']) ?? null,
  );
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

function readLock(source: JsonRecord | null, key: PromotionLockKey): LockRead {
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

  for (const containerKey of LOCK_CONTAINER_KEYS) {
    const fromContainer = readContainerLock(source[containerKey], key);
    if (fromContainer) {
      return fromContainer;
    }
  }

  return { value: false, status: 'missing' };
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

function nestedRecord(record: JsonRecord | null, keys: readonly string[]): JsonRecord | null {
  if (!record) {
    return null;
  }
  for (const key of keys) {
    const next = asRecord(record[key]);
    if (next) {
      return next;
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
  const locks = {} as PromotionLocks;
  const states = {} as Record<PromotionLockKey, PromotionLockState>;

  for (const key of PROMOTION_LOCK_KEYS) {
    const state = stateFor(key, readLock(record, key));
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
  const strategy = nestedRecord(record, ['strategy_context', 'strategy', 'summary']);
  const detail = nestedRecord(record, ['detail', 'details', 'risk_policy']);
  const locksContainer = nestedRecord(record, ['promotion_locks', 'locks', 'safety_locks']);
  const locksSource = locksContainer && record ? { ...locksContainer, ...record } : record;
  const declaredCost = resolveCostBps(record, detail, options.declaredDefaultCostBps);
  const blockerValue = record?.blocking_reasons ?? record?.blockers ?? record?.reasons;

  return {
    run_id: firstFromRecords([record], ['run_id', 'id', 'name']) ?? STRING_FALLBACKS.run,
    artifact_type: firstFromRecords([record], ['artifact_type', 'kind', 'type']) ?? STRING_FALLBACKS.artifactType,
    line: normalizeLine(
      firstFromRecords([strategy, record], ['line', 'strategy_line', 'strategy_context', 'type']),
    ),
    is_reinforcement_learning: typeof strategy?.is_reinforcement_learning === 'boolean'
      ? strategy.is_reinforcement_learning
      : typeof record?.is_reinforcement_learning === 'boolean'
        ? record.is_reinforcement_learning
        : false,
    strategy_label: firstFromRecords([strategy, record], ['strategy_label', 'label', 'name']) ?? STRING_FALLBACKS.strategy,
    baseline_label: firstFromRecords([record, detail], ['baseline_label', 'primary_baseline', 'baseline']) ?? STRING_FALLBACKS.baseline,
    cost_bps: declaredCost,
    seed: firstFromRecords([record, detail], ['seed', 'random_seed']) ?? STRING_FALLBACKS.seed,
    split: firstFromRecords([record, detail], ['split', 'split_policy', 'train_test_split']) ?? STRING_FALLBACKS.split,
    split_hash: stableSha256(firstFromRecords([record, detail], ['split_hash', 'data_split_hash']), STRING_FALLBACKS.splitHash),
    prereg_doc: firstFromRecords([record, detail], ['prereg_doc', 'preregistration_doc', 'prereg_path']) ?? STRING_FALLBACKS.prereg,
    source_endpoint: options.source_endpoint ?? firstString(record, ['source_endpoint', 'endpoint']) ?? STRING_FALLBACKS.endpoint,
    lifecycle: pickLifecycle(record),
    verdict: firstConservativeVerdict([record, detail]) ?? 'NO-GO/UNKNOWN_BLOCKED',
    blocking_reasons: blockerStrings(blockerValue),
    promotion_locks: adaptPromotionLocks(locksSource),
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
