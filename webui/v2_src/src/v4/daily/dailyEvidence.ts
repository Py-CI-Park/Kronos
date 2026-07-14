import type {
  DailyCloseSlotLatestResponse,
  DailyProgressResponse,
  DailyRegistryResponse,
} from '$lib/dailyOhlcvApi';
import { adaptPromotionLocks, type PromotionLocksResult } from '../evidence';

export const DAILY_NOT_RECORDED = 'NOT_RECORDED';
export const DAILY_MISSING = 'MISSING';
export const DAILY_NO_GO = 'NO-GO';
export const DAILY_EXPECTED_ROUND_TRIP_BP = 23;

export type DailyAuthorityLevel = 'canonical' | 'declared' | 'smoke' | 'unknown' | 'missing';
export type DailySourceName = 'progress' | 'closeSlotLatest' | 'registryLatest';

export interface DailyAuthority {
  level: DailyAuthorityLevel;
  source: DailySourceName | 'none';
  label: string;
  reason: string;
}

export interface DailyCostEvidence {
  declared: boolean;
  valueBp: number | null;
  label: string;
  status: 'DECLARED_23BP' | 'MISSING' | 'UNEXPECTED';
}
export interface DailyCostControlEvidence {
  declared: boolean;
  valuesBp: number[];
  label: string;
  status: 'DECLARED_0_46' | 'MISSING' | 'INCOMPLETE';
}


export interface DailySlotControlEvidence {
  declared: boolean;
  selected: number | null;
  max: number | null;
  label: string;
  status: 'DECLARED' | 'MISSING' | 'INCOMPLETE';
}

export interface DailyResearchEvidence {
  authority: DailyAuthority;
  testOosStatus: string;
  latestSelection: string;
  sourceRunId: string;
  sourceCode: string;
  roundTripCost: DailyCostEvidence;
  costControls: DailyCostControlEvidence;
  split: string;
  splitHash: string;
  seed: string;
  slotControls: DailySlotControlEvidence;
  blockers: string[];
  freshness: string;
  promotionLocks: PromotionLocksResult;
  rawAudit: {
    progressStatus: string;
    closeSlotStatus: string;
    registryStatus: string;
    artifactStatus: string;
  };
}

type UnknownRecord = Record<string, unknown>;

function asRecord(value: unknown): UnknownRecord | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? (value as UnknownRecord) : null;
}

function stringValue(value: unknown): string | null {
  if (typeof value === 'string' && value.trim() !== '') return value;
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return null;
}

function finiteNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function finiteInteger(value: unknown): number | null {
  return typeof value === 'number' && Number.isInteger(value) && Number.isFinite(value) ? value : null;
}

function normalizeToken(value: unknown): string {
  return stringValue(value)?.trim().toLowerCase().replace(/[\s-]+/g, '_') ?? '';
}

function isSmoke(value: unknown): boolean {
  const token = normalizeToken(value);
  return token.includes('smoke') || token.includes('sample') || token.includes('demo');
}

function isUnknownish(value: unknown): boolean {
  const token = normalizeToken(value);
  return token === 'unknown' || token === 'missing' || token === 'invalid' || token === 'malformed';
}
function isPositiveValidation(value: unknown): boolean {
  return ['canonical', 'pass', 'valid', 'validated'].includes(normalizeToken(value));
}

function isNegativeEvidence(value: unknown): boolean {
  const token = normalizeToken(value);
  return token === ''
    || token === 'unknown'
    || token === 'missing'
    || token === 'invalid'
    || token === 'malformed'
    || token === 'fail'
    || token === 'failed'
    || token === 'rejected'
    || token === 'no_go'
    || token.startsWith('blocked');
}

function isDeclaredEvidence(value: unknown): boolean {
  return !isSmoke(value) && !isUnknownish(value) && normalizeToken(value) !== '';
}

function statusOr(value: unknown, fallback = DAILY_NOT_RECORDED): string {
  return stringValue(value) ?? fallback;
}

function dedupeStrings(values: readonly unknown[], fallback: string): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const raw = Array.isArray(value) ? value : [value];
    for (const item of raw) {
      const text = stringValue(item);
      if (!text || seen.has(text)) continue;
      seen.add(text);
      result.push(text);
    }
  }
  return result.length > 0 ? result : [fallback];
}

function progressBlockers(progress: DailyProgressResponse | null | undefined): string[] {
  if (!progress) return [];
  return [
    ...(progress.stages ?? [])
      .filter((stage) => ['no_go', 'blocked'].includes(normalizeToken(stage.status)))
      .map((stage) => `${stage.id}:${stage.status}`),
    ...(progress.provenance_matrix ?? []).flatMap((entry) => entry.lock_labels ?? []),
  ];
}

function closeSlotIsCanonical(closeSlot: DailyCloseSlotLatestResponse | null | undefined): boolean {
  if (!closeSlot) return false;
  if (isSmoke(closeSlot.surface) || isSmoke(closeSlot.artifact_status) || isSmoke(closeSlot.run_id)) return false;
  return isPositiveValidation(closeSlot.dashboard_validation_status)
    && isPositiveValidation(closeSlot.lineage_validation_status)
    && !isNegativeEvidence(closeSlot.artifact_status);
}

function registryIsCanonical(registry: DailyRegistryResponse | null | undefined): boolean {
  if (!registry) return false;
  if (isSmoke(registry.status) || isSmoke(registry.run_id)) return false;
  return ['canonical', 'pass', 'valid', 'validated'].includes(normalizeToken(registry.status));
}

function authorityFrom(
  progress: DailyProgressResponse | null | undefined,
  closeSlot: DailyCloseSlotLatestResponse | null | undefined,
  registry: DailyRegistryResponse | null | undefined,
): DailyAuthority {
  if (closeSlotIsCanonical(closeSlot)) {
    return { level: 'canonical', source: 'closeSlotLatest', label: 'CANONICAL_CLOSE_SLOT', reason: statusOr(closeSlot?.lineage_validation_status, 'validated') };
  }
  if (registryIsCanonical(registry)) {
    return { level: 'canonical', source: 'registryLatest', label: 'CANONICAL_REGISTRY', reason: statusOr(registry?.status, 'validated') };
  }
  if (closeSlot && (isDeclaredEvidence(closeSlot.status) || isDeclaredEvidence(closeSlot.artifact_status))) {
    return { level: 'declared', source: 'closeSlotLatest', label: 'DECLARED_CLOSE_SLOT', reason: statusOr(closeSlot.status) };
  }
  if (registry && isDeclaredEvidence(registry.status)) {
    return { level: 'declared', source: 'registryLatest', label: 'DECLARED_REGISTRY', reason: statusOr(registry.status) };
  }
  if (progress && isDeclaredEvidence(progress.overall_status)) {
    return { level: 'declared', source: 'progress', label: 'DECLARED_PROGRESS', reason: statusOr(progress.overall_status) };
  }
  return { level: progress || closeSlot || registry ? 'unknown' : 'missing', source: 'none', label: DAILY_MISSING, reason: DAILY_NO_GO };
}

function deriveTestOosStatus(closeSlot: DailyCloseSlotLatestResponse | null | undefined): string {
  if (!closeSlot) return DAILY_MISSING;
  if (closeSlot.latest_selection?.missing_test_split_evidence === true) return DAILY_NO_GO;
  const latestSplit = normalizeToken(closeSlot.latest_selection?.split);
  const thresholdSplit = normalizeToken(closeSlot.threshold_selection?.split);
  const replaySplitCounts = asRecord(closeSlot.replay_summary?.split_counts);
  if (latestSplit === 'test' || latestSplit === 'oos' || latestSplit === 'test_oos') return 'TEST_OOS_DECLARED';
  if (thresholdSplit === 'test' || thresholdSplit === 'oos' || thresholdSplit === 'test_oos') return 'TEST_OOS_DECLARED';
  if ((finiteNumber(replaySplitCounts?.test) ?? 0) > 0 || (finiteNumber(replaySplitCounts?.oos) ?? 0) > 0) return 'TEST_OOS_DECLARED';
  return DAILY_NO_GO;
}

function deriveCost(closeSlot: DailyCloseSlotLatestResponse | null | undefined): DailyCostEvidence {
  const values = [
    closeSlot?.round_trip_cost_bp,
    closeSlot?.primary_cost_scenario_id ? closeSlot.cost_scenarios?.[closeSlot.primary_cost_scenario_id]?.total_bp : undefined,
    closeSlot?.latest_selection?.cost_scenario_id ? closeSlot.cost_scenarios?.[closeSlot.latest_selection.cost_scenario_id]?.total_bp : undefined,
  ];
  const declared = values.map(finiteNumber).find((value): value is number => value !== null);
  if (declared === undefined) return { declared: false, valueBp: null, label: DAILY_MISSING, status: 'MISSING' };
  if (declared === DAILY_EXPECTED_ROUND_TRIP_BP) return { declared: true, valueBp: declared, label: '23bp', status: 'DECLARED_23BP' };
  return { declared: true, valueBp: declared, label: `${declared}bp`, status: 'UNEXPECTED' };
}
function deriveCostControls(closeSlot: DailyCloseSlotLatestResponse | null | undefined): DailyCostControlEvidence {
  const valuesBp = (closeSlot?.cost_sensitivity_bp ?? [])
    .map(finiteNumber)
    .filter((value): value is number => value !== null);
  if (valuesBp.length === 0) return { declared: false, valuesBp: [], label: DAILY_MISSING, status: 'MISSING' };
  const hasRequiredControls = valuesBp.includes(0) && valuesBp.includes(46);
  return {
    declared: true,
    valuesBp,
    label: `${valuesBp.join('/')}bp`,
    status: hasRequiredControls ? 'DECLARED_0_46' : 'INCOMPLETE',
  };
}


function deriveSlotControls(closeSlot: DailyCloseSlotLatestResponse | null | undefined): DailySlotControlEvidence {
  const selected = finiteInteger(closeSlot?.slot_count)
    ?? finiteInteger(closeSlot?.selected_hold_summary?.rows?.[0]?.selected_count)
    ?? finiteInteger(closeSlot?.threshold_selection?.oos_rows_used_for_fit);
  const max = finiteInteger(closeSlot?.max_slot_count)
    ?? finiteInteger(closeSlot?.selected_hold_summary?.max_slot_count)
    ?? finiteInteger(closeSlot?.threshold_selection?.max_slot_count);
  if (selected === null && max === null) return { declared: false, selected: null, max: null, label: DAILY_MISSING, status: 'MISSING' };
  if (selected === null || max === null) {
    return {
      declared: false,
      selected,
      max,
      label: `${selected ?? DAILY_NOT_RECORDED}/${max ?? DAILY_NOT_RECORDED}`,
      status: 'INCOMPLETE',
    };
  }
  return {
    declared: true,
    selected,
    max,
    label: `${selected}/${max}`,
    status: 'DECLARED',
  };
}

function deriveSplitHash(closeSlot: DailyCloseSlotLatestResponse | null | undefined, registry: DailyRegistryResponse | null | undefined): string {
  return stringValue(closeSlot?.dataset_lineage?.split_hash)
    ?? stringValue(closeSlot?.dataset_lineage?.data_split_hash)
    ?? stringValue(registry?.data_hash)
    ?? DAILY_NOT_RECORDED;
}

function deriveSourceCode(closeSlot: DailyCloseSlotLatestResponse | null | undefined): string {
  return stringValue(closeSlot?.dataset_lineage?.code)
    ?? stringValue(closeSlot?.samples?.policy_scores?.[0]?.code)
    ?? DAILY_NOT_RECORDED;
}

function deriveFreshness(closeSlot: DailyCloseSlotLatestResponse | null | undefined): string {
  if (!closeSlot) return DAILY_MISSING;
  if (closeSlot.data_recency?.label) return closeSlot.data_recency.label;
  if (closeSlot.data_recency?.is_today === true) return 'FRESH_TODAY';
  if (closeSlot.data_recency?.is_today === false) return 'STALE';
  if (typeof closeSlot.artifact_age_seconds === 'number' && Number.isFinite(closeSlot.artifact_age_seconds)) return `${closeSlot.artifact_age_seconds}s`;
  return DAILY_NOT_RECORDED;
}

function closeSlotLockSource(closeSlot: DailyCloseSlotLatestResponse | null | undefined): unknown {
  return closeSlot ?? null;
}

export function adaptDailyResearchEvidence(
  progress: DailyProgressResponse | null | undefined,
  closeSlot: DailyCloseSlotLatestResponse | null | undefined,
  registry: DailyRegistryResponse | null | undefined,
): DailyResearchEvidence {
  const authority = authorityFrom(progress, closeSlot, registry);
  const latest = closeSlot?.latest_selection;
  const blockers = dedupeStrings([
    progressBlockers(progress),
    closeSlot?.current_required_blockers,
    closeSlot?.upstream_gate_blockers,
    closeSlot?.close_slot_blockers,
    closeSlot?.artifact_selection_errors,
    registry?.effective_gate_blockers,
    registry?.invariant_errors,
  ], DAILY_NO_GO);

  return {
    authority,
    testOosStatus: deriveTestOosStatus(closeSlot),
    latestSelection: latest ? statusOr(latest.label ?? latest.policy ?? latest.date, DAILY_NOT_RECORDED) : DAILY_MISSING,
    sourceRunId: stringValue(latest?.source_run_id) ?? stringValue(closeSlot?.run_id) ?? stringValue(registry?.run_id) ?? DAILY_MISSING,
    roundTripCost: deriveCost(closeSlot),
    costControls: deriveCostControls(closeSlot),
    split: stringValue(latest?.split) ?? stringValue(closeSlot?.threshold_selection?.split) ?? DAILY_NOT_RECORDED,
    splitHash: deriveSplitHash(closeSlot, registry),
    sourceCode: deriveSourceCode(closeSlot),
    seed: stringValue(latest?.seed) ?? DAILY_NOT_RECORDED,
    slotControls: deriveSlotControls(closeSlot),
    blockers,
    freshness: deriveFreshness(closeSlot),
    promotionLocks: adaptPromotionLocks(closeSlotLockSource(closeSlot)),
    rawAudit: {
      progressStatus: statusOr(progress?.overall_status),
      closeSlotStatus: statusOr(closeSlot?.status),
      registryStatus: statusOr(registry?.status),
      artifactStatus: statusOr(closeSlot?.artifact_status),
    },
  };
}
