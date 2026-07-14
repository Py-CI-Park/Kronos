import type {
  JsonObject,
  RlProgressResponse,
  RlRliableStatsResponse,
  RlRunDetail,
  RlRunRecord,
  RlTableRow,
} from '$lib/rlApi';
import { adaptMetricValue, adaptRunEvidence, type MetricValue, type RunEvidence } from '../evidence';

export type RlEvidenceLaneKind = 'RULE' | 'RL' | 'SUPERVISED_GATE' | 'EVIDENCE';

export interface RlEvidenceLane {
  kind: RlEvidenceLaneKind;
  label: string;
  isRl: boolean;
  posture: 'baseline_not_rl' | 'research_only_rl' | 'supervised_gate_not_rl' | 'audit_evidence';
  reason: string;
}

export interface CockpitMetric {
  key: string;
  label: string;
  metric: MetricValue;
  display: string;
  behavior: 'recorded' | 'not_recorded' | 'incompatible_unit' | 'inapplicable';
}

export interface CockpitMetadata {
  key: string;
  label: string;
  value: string;
  source: string;
  behavior: 'recorded' | 'not_recorded';
}

export interface RlCockpitEvidence {
  run: RunEvidence;
  lane: RlEvidenceLane;
  metrics: readonly CockpitMetric[];
  metadata: readonly CockpitMetadata[];
  neverTradeStatus: 'NEVER_TRADE' | 'TRADED' | 'NOT_RECORDED';
}

export interface DocumentedRlFact {
  key: string;
  status: 'COMPLETE' | 'NOT_PROMOTED' | 'NO-GO' | 'TUNING_HARMFUL' | 'SEED_NOISE_NO_GO' | 'DOCUMENTED_RESEARCH_POSTURE';
  label: string;
  detail: string;
  staticResearchPosture: boolean;
}

export const DOCUMENTED_RL_FACTS: readonly DocumentedRlFact[] = [
  {
    key: 'smoke_plumbing_complete',
    status: 'COMPLETE',
    label: 'Smoke plumbing complete',
    detail: 'SB3 smoke/plumbing evidence can be complete without promoting a full model.',
    staticResearchPosture: true,
  },
  {
    key: 'full_model_not_promoted',
    status: 'NOT_PROMOTED',
    label: 'Full model not promoted',
    detail: 'No full RL model promotion, live trading, broker order, or profitability claim is declared.',
    staticResearchPosture: true,
  },
  {
    key: 'r5_tuning_harmful',
    status: 'TUNING_HARMFUL',
    label: 'R5 TUNING_HARMFUL',
    detail: 'Documented R5 posture remains harmful tuning, not a GO signal.',
    staticResearchPosture: true,
  },
  {
    key: 'close_slot_no_go',
    status: 'NO-GO',
    label: 'Close-slot NO-GO',
    detail: 'Close-slot research remains explicitly blocked from promotion.',
    staticResearchPosture: true,
  },
  {
    key: 'd4_seed_noise_no_go',
    status: 'SEED_NOISE_NO_GO',
    label: 'D4 SEED_NOISE_NO_GO',
    detail: 'D4 seed noise is documented as NO-GO rather than robust model evidence.',
    staticResearchPosture: true,
  },
  {
    key: 'documented_research_posture',
    status: 'DOCUMENTED_RESEARCH_POSTURE',
    label: 'Documented research posture',
    detail: 'Static facts are labeled as documented posture, not live market data.',
    staticResearchPosture: true,
  },
] as const;


const NOT_RECORDED = 'NOT_RECORDED';
const INCOMPATIBLE_UNIT = 'INCOMPATIBLE_UNIT';

type UnknownRecord = Record<string, unknown>;

function asRecord(value: unknown): UnknownRecord | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? (value as UnknownRecord) : null;
}

function stringValue(value: unknown): string | null {
  if (typeof value === 'string' && value.trim() !== '') return value;
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return null;
}

function numberValue(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function validNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim() !== '';
}

function metadataString(value: unknown): string | null {
  return validNonEmptyString(value) ? value : null;
}

function metadataSeed(value: unknown): string | null {
  if (validNonEmptyString(value)) return value;
  return numberValue(value) === null ? null : String(value);
}

function lower(value: unknown): string {
  return stringValue(value)?.trim().toLowerCase().replace(/[\s-]+/g, '_') ?? '';
}

function first(records: readonly (UnknownRecord | null)[], keys: readonly string[]): unknown {
  for (const record of records) {
    if (!record) continue;
    for (const key of keys) {
      if (Object.prototype.hasOwnProperty.call(record, key)) return record[key];
    }
  }
  return undefined;
}

function nested(record: UnknownRecord | null, keys: readonly string[]): UnknownRecord | null {
  for (const key of keys) {
    const child = asRecord(record?.[key]);
    if (child) return child;
  }
  return null;
}

function unitOf(value: unknown): string | null {
  return stringValue(asRecord(value)?.unit ?? asRecord(value)?.units);
}

function valueOf(value: unknown): unknown {
  const record = asRecord(value);
  return record && Object.prototype.hasOwnProperty.call(record, 'value') ? record.value : value;
}

function sourceRecord(source: RlRunRecord | RlRunDetail | JsonObject | null | undefined): UnknownRecord | null {
  return asRecord(source);
}

export function classifyRlEvidenceLane(source: RlRunRecord | RlRunDetail | JsonObject | null | undefined): RlEvidenceLane {
  const record = sourceRecord(source);
  const strategy = nested(record, ['strategy_context', 'strategy', 'summary']);
  const artifact = lower(record?.artifact_type ?? record?.kind ?? record?.type);
  const line = lower(strategy?.line ?? record?.line ?? record?.strategy_line);
  const label = stringValue(strategy?.label ?? record?.name ?? record?.run_id ?? record?.id) ?? 'UNLABELED';
  const explicitRl = strategy?.is_reinforcement_learning === true || record?.is_reinforcement_learning === true;
  const explicitNonRl = strategy?.is_reinforcement_learning === false || record?.is_reinforcement_learning === false;

  if (line.includes('rule') || artifact === 'baseline' || artifact.includes('rule_filter')) {
    return {
      kind: 'RULE',
      label: `${label} · RULE baseline / NOT RL`,
      isRl: false,
      posture: 'baseline_not_rl',
      reason: 'RULE lane is a baseline/control surface and is never re-labeled as RL.',
    };
  }

  if (
    !explicitNonRl &&
    (explicitRl ||
      line === 'rl' ||
      line === 'reinforcement_learning' ||
      artifact.includes('rl_workflow') ||
      artifact.includes('sb3') ||
      artifact.includes('reinforcement'))
  ) {
    return {
      kind: 'RL',
      label: `${label} · RL experiment / research-only`,
      isRl: true,
      posture: 'research_only_rl',
      reason: 'RL evidence is research-only unless independent promotion locks explicitly unlock, which this console does not infer.',
    };
  }

  if (
    line.includes('supervised') ||
    artifact.includes('calibration') ||
    artifact.includes('lineage') ||
    artifact.includes('sizing') ||
    artifact.includes('risk_policy') ||
    artifact.includes('session') ||
    artifact.includes('factory')
  ) {
    return {
      kind: 'SUPERVISED_GATE',
      label: `${label} · supervised gate / NOT RL`,
      isRl: false,
      posture: 'supervised_gate_not_rl',
      reason: 'Supervised/factory gates can block or contextualize RL, but are not RL returns.',
    };
  }

  return {
    kind: 'EVIDENCE',
    label: `${label} · audit evidence / NOT RL unless declared`,
    isRl: false,
    posture: 'audit_evidence',
    reason: 'No explicit RL lane declaration was recorded.',
  };
}

function rowCount(rows: readonly RlTableRow[] | undefined): number | null {
  return rows && rows.length > 0 ? rows.length : null;
}
export type RlCollectionStatus = 'recorded' | 'empty' | 'not_recorded';
export interface NormalizedRlProgress {
  status: RlCollectionStatus;
  progress: RlProgressResponse | null;
}

function validProgressPage(value: unknown): boolean {
  const page = asRecord(value);
  return page !== null &&
    validNonEmptyString(page.page) &&
    numberValue(page.progress_pct) !== null &&
    validNonEmptyString(page.status) &&
    (page.criteria === undefined || Array.isArray(page.criteria));
}

export function normalizeRlProgress(payload: unknown): NormalizedRlProgress {
  const record = asRecord(payload);
  if (!record || numberValue(record.overall_progress_pct) === null || !validNonEmptyString(record.status) ||
      !Array.isArray(record.pages) || !record.pages.every(validProgressPage)) {
    return { status: 'not_recorded', progress: null };
  }
  const progress = record as unknown as RlProgressResponse;
  return { status: progress.pages.length === 0 ? 'empty' : 'recorded', progress };
}

export interface NormalizedRlRunDetail {
  status: RlCollectionStatus;
  detail: RlRunDetail | null;
}

function validArtifact(value: unknown): boolean {
  const artifact = asRecord(value);
  return artifact !== null && validNonEmptyString(artifact.name);
}

export function normalizeRlRunDetail(payload: unknown, requestedName: string): NormalizedRlRunDetail {
  const record = asRecord(payload);
  if (!record || !validNonEmptyString(record.name) || record.name !== requestedName ||
      !validNonEmptyString(record.artifact_type) ||
      (record.artifacts !== undefined && (!Array.isArray(record.artifacts) || !record.artifacts.every(validArtifact)))) {
    return { status: 'not_recorded', detail: null };
  }
  return { status: 'recorded', detail: record as unknown as RlRunDetail };
}

export interface NormalizedRlRuns {
  status: RlCollectionStatus;
  runs: readonly RlRunRecord[];
}

export function normalizeRlRuns(payload: unknown): NormalizedRlRuns {
  const record = asRecord(payload);
  const runs = record?.runs;
  if (!Array.isArray(runs) || !runs.every((run) => {
    const item = asRecord(run);
    return item !== null && typeof item.name === 'string' && item.name.trim() !== '';
  })) {
    return { status: 'not_recorded', runs: [] };
  }
  return { status: runs.length === 0 ? 'empty' : 'recorded', runs: runs as readonly RlRunRecord[] };
}

export interface NormalizedRlRows {
  status: RlCollectionStatus;
  rows: readonly RlTableRow[];
}

export function normalizeRlRows(payload: unknown): NormalizedRlRows {
  const record = asRecord(payload);
  if (!record || !Array.isArray(record.rows) || !record.rows.every((row) => asRecord(row) !== null)) {
    return { status: 'not_recorded', rows: [] };
  }
  return { status: record.rows.length === 0 ? 'empty' : 'recorded', rows: record.rows as readonly RlTableRow[] };
}

export interface NormalizedRliableCollections {
  status: RlCollectionStatus;
  algorithms: number;
  aggregates: number;
}

export function normalizeRliableCollections(payload: unknown): NormalizedRliableCollections {
  const record = asRecord(payload);
  if (!record || !Array.isArray(record.algorithms) || !record.algorithms.every((item) => typeof item === 'string') || !asRecord(record.aggregates)) {
    return { status: 'not_recorded', algorithms: 0, aggregates: 0 };
  }
  const algorithms = record.algorithms.length;
  const aggregates = Object.keys(record.aggregates).length;
  return { status: algorithms === 0 && aggregates === 0 ? 'empty' : 'recorded', algorithms, aggregates };
}

function makeMetric(
  key: string,
  label: string,
  raw: unknown,
  options: { unit: string; source: string; precision?: number; expectedUnits?: readonly string[] },
): CockpitMetric {
  const declaredUnit = unitOf(raw) ?? options.unit;
  const compatible = !options.expectedUnits || options.expectedUnits.includes(declaredUnit);
  const rawValue = valueOf(raw);
  const numeric = numberValue(rawValue);
  const metric = adaptMetricValue(compatible ? numeric : null, {
    kind: key,
    unit: compatible ? declaredUnit : `${declaredUnit}:${INCOMPATIBLE_UNIT}`,
    source: options.source,
    precision: options.precision,
    availability: compatible ? undefined : 'INAPPLICABLE',
  });
  const behavior = !compatible
    ? 'incompatible_unit'
    : metric.availability === 'INAPPLICABLE'
      ? 'inapplicable'
      : metric.availability === 'NOT_RECORDED'
        ? 'not_recorded'
        : 'recorded';
  const display = behavior === 'incompatible_unit'
    ? `${INCOMPATIBLE_UNIT} (${declaredUnit})`
    : metric.value === null
      ? NOT_RECORDED
      : `${metric.value}${declaredUnit === 'count' ? '' : ` ${declaredUnit}`}`;
  return { key, label, metric, display, behavior };
}

function makeMetadata(key: string, label: string, raw: unknown, notRecorded: string, source: string): CockpitMetadata {
  const value = stringValue(raw) ?? notRecorded;
  return {
    key,
    label,
    value,
    source,
    behavior: value === notRecorded ? 'not_recorded' : 'recorded',
  };
}

export function deriveRlCockpitEvidence(
  source: RlRunRecord | RlRunDetail | JsonObject | null | undefined,
  rows: { trades?: readonly RlTableRow[]; events?: readonly RlTableRow[] } = {},
): RlCockpitEvidence {
  const record = sourceRecord(source);
  const detail = nested(record, ['detail', 'summary', 'risk_policy']);
  const strategy = nested(record, ['strategy_context', 'strategy']);
  const sourceName = stringValue(record?.name ?? record?.run_id ?? record?.id) ?? 'selected-run';
  const run = adaptRunEvidence(record, { source_endpoint: `/api/rl/runs/${encodeURIComponent(sourceName)}` });
  const lane = classifyRlEvidenceLane(source);
  const declaredTradeCount = first([record, detail], ['trade_count', 'trades', 'num_trades', 'executed_trades']);
  const tradeCountRaw = declaredTradeCount ?? rowCount(rows.trades);
  const validTradeCount = (() => {
    const value = valueOf(tradeCountRaw);
    return typeof value === 'number' && Number.isInteger(value) && value >= 0 ? tradeCountRaw : null;
  })();
  const tradeMetric = makeMetric('trade_count', 'Trade count', validTradeCount, {
    unit: 'count',
    source: sourceName,
    precision: 0,
    expectedUnits: ['count'],
  });
  const tradeCount = tradeMetric.behavior === 'recorded' ? numberValue(tradeMetric.metric.value) : null;
  const neverTradeStatus = tradeCount === 0 ? 'NEVER_TRADE' : tradeCount === null ? 'NOT_RECORDED' : 'TRADED';

  return {
    run,
    lane,
    neverTradeStatus,
    metadata: [
      makeMetadata('split', 'Split', metadataString(first([record, detail], ['split', 'split_policy', 'train_test_split'])), 'SPLIT_NOT_RECORDED', sourceName),
      makeMetadata('split_hash', 'Split hash', run.split_hash, 'SPLIT_HASH_NOT_RECORDED', sourceName),
      makeMetadata('seed', 'Seed', metadataSeed(first([record, detail], ['seed', 'random_seed'])), 'SEED_NOT_RECORDED', sourceName),
      makeMetadata('baseline', 'Baseline', metadataString(first([record, detail, strategy], ['baseline_label', 'primary_baseline', 'baseline'])), 'BASELINE_NOT_RECORDED', sourceName),
    ],
    metrics: [
      makeMetric('test_oos', 'TEST OOS', first([record, detail], ['test_oos', 'test_oos_score', 'oos_return', 'oos_metric']), {
        unit: 'score',
        source: sourceName,
        precision: 4,
        expectedUnits: ['score', 'ratio', 'pct', 'percent'],
      }),
      makeMetric('declared_cost_bps', 'Declared cost', run.cost_bps, {
        unit: 'bps',
        source: sourceName,
        precision: 2,
        expectedUnits: ['bps'],
      }),
      makeMetric('uncertainty', 'Uncertainty', first([record, detail], ['uncertainty', 'ci95', 'stderr', 'std_error']), {
        unit: 'score',
        source: sourceName,
        precision: 4,
        expectedUnits: ['score', 'ratio', 'pct', 'percent'],
      }),
      makeMetric('max_drawdown', 'MDD', first([record, detail], ['mdd', 'max_drawdown', 'max_drawdown_pct', 'max_dd_pct']), {
        unit: 'pct',
        source: sourceName,
        precision: 2,
        expectedUnits: ['pct', 'percent', 'ratio'],
      }),
      tradeMetric,
    ],
  };
}

export function choosePreferredRlRun(candidates: readonly RlRunRecord[]): RlRunRecord | null {
  return (
    candidates.find((run) => classifyRlEvidenceLane(run).kind === 'RL' && lower(run.lifecycle?.status ?? run.summary?.status) === 'completed') ??
    candidates.find((run) => classifyRlEvidenceLane(run).kind === 'RL') ??
    candidates.find((run) => classifyRlEvidenceLane(run).kind === 'RULE') ??
    candidates.find((run) => run.artifact_type === 'performance_leaderboard') ??
    candidates[0] ??
    null
  );
}

export function summarizeProgress(progress: RlProgressResponse | null): string {
  if (!progress) return 'progress NOT_RECORDED';
  return `${progress.status} · ${progress.overall_progress_pct}% · ${progress.pages.length} pages`;
}

export function summarizeRliable(stats: RlRliableStatsResponse | null): string {
  const normalized = normalizeRliableCollections(stats);
  if (normalized.status === 'not_recorded') return 'rliable NOT_RECORDED';
  return `${stats?.generated_utc ?? 'TIME_NOT_RECORDED'} · ${normalized.algorithms} algos · ${normalized.aggregates} aggregates`;
}
