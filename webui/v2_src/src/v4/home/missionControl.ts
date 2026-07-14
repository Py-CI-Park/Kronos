import { adaptPromotionLocks, PROMOTION_LOCK_KEYS, type PromotionLocksResult } from '../evidence';

export { PROMOTION_LOCK_KEYS } from '../evidence';

export type MissionTone = 'danger' | 'warn' | 'ok' | 'idle' | 'accent';
export type MissionSource = 'LIVE' | 'DECLARED' | 'FALLBACK';

export interface WorkflowStep {
  readonly id: 'data' | 'split' | 'baseline' | 'policy' | 'test_oos' | 'verdict';
  readonly marker: string;
  readonly label: string;
  readonly status: string;
  readonly tone: MissionTone;
}

export interface MissionCard {
  readonly id: 'forecast' | 'daily-d0-d9' | 'close-slot' | 'rl-evidence' | 'training-system' | 'unresolved-blockers';
  readonly title: string;
  readonly eyebrow: string;
  readonly verdict: string;
  readonly metric: string;
  readonly detail: string;
  readonly source: MissionSource;
  readonly tone: MissionTone;
  readonly tab: string;
}

export interface MissionTopBlocker {
  readonly status: 'blocked' | 'checking';
  readonly text: string;
  readonly detail: string;
}

export interface MissionControlModel {
  readonly topBlocker: MissionTopBlocker;
  readonly locks: PromotionLocksResult;
  readonly workflow: readonly WorkflowStep[];
  readonly cards: readonly MissionCard[];
}

export interface MissionControlInputs {
  readonly dailyProgress?: Record<string, unknown> | null;
  readonly closeSlot?: Record<string, unknown> | null;
  readonly rlRuns?: readonly Record<string, unknown>[] | null;
  readonly rlQueue?: Record<string, unknown> | null;
  readonly rliableStats?: Record<string, unknown> | null;
  readonly trainingStatus?: Record<string, unknown> | null;
  readonly metricsLatest?: Record<string, unknown> | null;
}

const CHECKING = '확인 중';
const MISSING = 'MISSING';
const NOT_RECORDED = 'NOT_RECORDED';
const NO_GO = 'NO-GO';
const CARD_ORDER: readonly MissionCard['id'][] = [
  'forecast',
  'daily-d0-d9',
  'close-slot',
  'rl-evidence',
  'training-system',
  'unresolved-blockers',
];

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function own(source: Record<string, unknown> | null | undefined, key: string): boolean {
  return !!source && Object.prototype.hasOwnProperty.call(source, key);
}

function meaningfulText(value: unknown): string | null {
  const next = stringOrNumber(value);
  if (next === null) return null;
  const normalized = next.trim().toUpperCase().replace(/[^A-Z0-9]+/g, '_');
  const sentinels = ['NOT_RECORDED', 'MISSING', 'CHECKING', 'UNKNOWN', 'NA', 'N_A', 'NULL', 'NONE', 'NOT_AVAILABLE', 'API_UNAVAILABLE'];
  const hasSentinel = sentinels.some((sentinel) => normalized === sentinel
    || normalized.startsWith(`${sentinel}_`)
    || normalized.endsWith(`_${sentinel}`)
    || normalized.includes(`_${sentinel}_`));
  return hasSentinel ? null : next;
}

function numberValue(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function stringOrNumber(value: unknown): string | null {
  if (typeof value === 'string' && value.trim() !== '') return value;
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return null;
}

function firstText(source: Record<string, unknown> | null | undefined, keys: readonly string[]): string | null {
  for (const key of keys) {
    const next = stringOrNumber(source?.[key]);
    if (next !== null) return next;
  }
  return null;
}

function firstMeaningfulText(source: Record<string, unknown> | null | undefined, keys: readonly string[]): string | null {
  for (const key of keys) {
    const next = meaningfulText(source?.[key]);
    if (next !== null) return next;
  }
  return null;
}

function hasMeaningfulText(source: Record<string, unknown> | null | undefined, keys: readonly string[]): boolean {
  return firstMeaningfulText(source, keys) !== null;
}

function hasMeaningfulNumber(source: Record<string, unknown> | null | undefined, keys: readonly string[]): boolean {
  return keys.some((key) => numberValue(source?.[key]) !== null);
}

function sourceFromEvidence(hasEvidence: boolean, declared: boolean = false): MissionSource {
  if (hasEvidence) return declared ? 'DECLARED' : 'LIVE';
  return 'FALLBACK';
}

function firstArray(source: Record<string, unknown> | null | undefined, keys: readonly string[]): readonly unknown[] {
  for (const key of keys) {
    const value = source?.[key];
    if (Array.isArray(value)) return value;
  }
  return [];
}

function conservativeStatus(value: unknown, fallback: string = CHECKING): string {
  const next = stringOrNumber(value);
  if (next === null) return fallback;
  const normalized = next.toUpperCase().replace(/[^A-Z0-9]+/g, '_');
  const tokens = normalized.split('_').filter(Boolean);
  const optimistic = tokens.some((token, index) => token === 'GO' && tokens[index - 1] !== 'NO')
    || tokens.some((token) => ['READY', 'LIVE', 'ACTIVE', 'PROFIT', 'PROFITABLE', 'ALLOWED', 'APPROVED', 'PROMOTED', 'MODEL'].includes(token));
  if (optimistic || normalized.includes('BROKER') || normalized.includes('ORDER')) return NO_GO;
  return next;
}

function toneFor(value: string): MissionTone {
  const normalized = value.toUpperCase();
  if (normalized.includes('NO-GO') || normalized.includes('BLOCK') || normalized.includes('FAIL') || normalized.includes('MISSING')) return 'danger';
  if (normalized.includes('WATCH') || normalized.includes('확인') || normalized.includes('TUNING') || normalized.includes('NOT_RECORDED')) return 'warn';
  if (normalized.includes('PASS') || normalized.includes('RECORDED')) return 'ok';
  return 'idle';
}

function declaredCostBps(...sources: readonly (Record<string, unknown> | null | undefined)[]): string {
  for (const source of sources) {
    if (!source) continue;
    for (const key of ['round_trip_cost_bp', 'cost_bps', 'costBps']) {
      if (own(source, key)) {
        const value = numberValue(source[key]);
        return value === null ? NOT_RECORDED : `${value}bp`;
      }
    }
  }
  return NOT_RECORDED;
}

function latestRlRun(inputs: MissionControlInputs): Record<string, unknown> | null {
  return record(inputs.rlRuns?.[0]);
}

function rlRunContext(run: Record<string, unknown> | null): Record<string, unknown> | null {
  return record(run?.strategy_context) ?? record(run?.summary);
}

function strictLineLabel(run: Record<string, unknown> | null): string {
  const context = rlRunContext(run);
  const raw = firstText(context, ['line', 'strategy_line']) ?? firstText(run, ['line']);
  const normalized = raw?.toLowerCase().replace(/[\s-]+/g, '_') ?? '';
  const ruleText = ['rule', 'rules', 'rule_based', 'rule_mainline'].includes(normalized);
  const rlText = ['rl', 'rl_experiment', 'reinforcement_learning'].includes(normalized);
  const explicitRl = context?.is_reinforcement_learning ?? run?.is_reinforcement_learning;
  if ((explicitRl === false && rlText) || (explicitRl === true && ruleText)) return 'RULE/RL 충돌';
  if (ruleText && explicitRl !== true) return 'RULE baseline';
  if (rlText || explicitRl === true) return 'RL experiment';
  return 'RULE/RL 미선언';
}

function baselineLabel(run: Record<string, unknown> | null): string {
  const context = rlRunContext(run);
  const raw = firstText(context, ['primary_baseline', 'baseline_label', 'baseline']) ?? firstText(run, ['baseline_label', 'primary_baseline', 'baseline']);
  if (!raw) return NOT_RECORDED;
  const line = strictLineLabel(run);
  return line.startsWith('RULE') ? `${raw} · RULE` : raw;
}

function uniqueTexts(items: readonly unknown[]): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const item of items) {
    const next = stringOrNumber(item);
    if (next && !seen.has(next)) {
      seen.add(next);
      out.push(next);
    }
  }
  return out;
}

function deriveBlockers(inputs: MissionControlInputs): string[] {
  const daily = record(inputs.dailyProgress);
  const closeSlot = record(inputs.closeSlot);
  const run = latestRlRun(inputs);
  return uniqueTexts([
    ...firstArray(daily, ['blockers', 'blocking_reasons', 'upstream_gate_blockers']),
    ...firstArray(closeSlot, ['close_slot_blockers', 'current_required_blockers', 'upstream_gate_blockers', 'artifact_selection_errors']),
    ...firstArray(run, ['blocking_reasons', 'blockers']),
  ]);
}

export function deriveTopBlocker(inputs: MissionControlInputs): MissionTopBlocker {
  const blockers = deriveBlockers(inputs);
  if (blockers.length > 0) {
    return {
      status: 'blocked',
      text: `최상위 blocker ${blockers.length}건`,
      detail: blockers.slice(0, 3).join(' · '),
    };
  }
  return {
    status: 'checking',
    text: '최상위 blocker 확인 중',
    detail: 'API 미응답/미선언 값은 안전하게 MISSING 또는 NO-GO로 표시합니다.',
  };
}

export function deriveStatusLocks(...sources: readonly unknown[]): PromotionLocksResult {
  for (const source of sources) {
    const sourceRecord = record(source);
    if (!sourceRecord) continue;
    const nestedLocks = record(sourceRecord.promotion_locks);
    const hasAnyLock = PROMOTION_LOCK_KEYS.some((key) => own(sourceRecord, key));
    if (hasAnyLock || nestedLocks || record(sourceRecord.false_locks)) {
      return adaptPromotionLocks(nestedLocks ? { ...nestedLocks, ...sourceRecord } : sourceRecord);
    }
  }
  return adaptPromotionLocks({});
}

export function deriveWorkflowSteps(inputs: MissionControlInputs): readonly WorkflowStep[] {
  const daily = record(inputs.dailyProgress);
  const closeSlot = record(inputs.closeSlot);
  const run = latestRlRun(inputs);
  const queue = record(inputs.rlQueue);
  const rliable = record(inputs.rliableStats);
  const steps: readonly [WorkflowStep['id'], string, string][] = [
    ['data', 'data', firstText(daily, ['overall_status', 'status']) ?? firstText(closeSlot, ['artifact_status', 'status']) ?? MISSING],
    ['split', 'split', firstText(run, ['split', 'split_hash']) ?? firstText(closeSlot, ['lineage_validation_status']) ?? MISSING],
    ['baseline', 'baseline', baselineLabel(run)],
    ['policy', 'policy', firstText(queue, ['guardrail', 'reason', 'status']) ?? firstText(closeSlot, ['readiness_status']) ?? MISSING],
    ['test_oos', 'TEST OOS', firstText(run, ['test_oos_status', 'test_oos_score', 'oos_return', 'oos_metric']) ?? NOT_RECORDED],
    ['verdict', 'verdict', conservativeStatus(firstText(run, ['verdict']) ?? firstText(closeSlot, ['readiness_status', 'status']), NO_GO)],
  ];
  return steps.map(([id, marker, status]) => ({ id, marker, label: marker, status, tone: toneFor(status) }));
}

export interface MissionControlSettledResult {
  readonly inputs: MissionControlInputs;
  readonly errors: readonly string[];
}

export interface MissionControlSourceRequests {
  readonly dailyProgress: Promise<unknown>;
  readonly closeSlot: Promise<unknown>;
  readonly rlRuns: Promise<unknown>;
  readonly rlQueue: Promise<unknown>;
  readonly rliableStats: Promise<unknown>;
}

const LOAD_SOURCE_KEYS = ['dailyProgress', 'closeSlot', 'rlRuns', 'rlQueue', 'rliableStats'] as const;

function apiUnavailable(key: string, reason: unknown): string {
  const message = reason instanceof Error ? reason.message.trim() : '';
  return message ? `${key}: API_UNAVAILABLE (${message})` : `${key}: API_UNAVAILABLE`;
}

export async function settleMissionControlSources(
  requests: MissionControlSourceRequests,
  preserved: Pick<MissionControlInputs, 'trainingStatus' | 'metricsLatest'> = {}
): Promise<MissionControlSettledResult> {
  const settled = await Promise.allSettled(LOAD_SOURCE_KEYS.map((key) => requests[key]));
  let next: MissionControlInputs = { ...preserved };
  const errors: string[] = [];

  settled.forEach((result, index) => {
    const key = LOAD_SOURCE_KEYS[index];
    if (result.status === 'rejected') {
      errors.push(apiUnavailable(key, result.reason));
      return;
    }
    switch (key) {
      case 'dailyProgress':
        next = { ...next, dailyProgress: result.value as Record<string, unknown> };
        break;
      case 'closeSlot':
        next = { ...next, closeSlot: result.value as Record<string, unknown> };
        break;
      case 'rlRuns':
        next = { ...next, rlRuns: (record(result.value)?.runs ?? []) as readonly Record<string, unknown>[] };
        break;
      case 'rlQueue':
        next = { ...next, rlQueue: result.value as Record<string, unknown> };
        break;
      case 'rliableStats':
        next = { ...next, rliableStats: result.value as Record<string, unknown> };
        break;
    }
  });

  return { inputs: next, errors };
}

export function deriveMissionCards(inputs: MissionControlInputs): readonly MissionCard[] {
  const daily = record(inputs.dailyProgress);
  const closeSlot = record(inputs.closeSlot);
  const train = record(inputs.trainingStatus);
  const metrics = record(inputs.metricsLatest);
  const run = latestRlRun(inputs);
  const rliable = record(inputs.rliableStats);
  const blockers = deriveBlockers(inputs);
  const dailyStatus = conservativeStatus(firstText(daily, ['overall_status', 'status']), CHECKING);
  const closeStatus = conservativeStatus(firstText(closeSlot, ['readiness_status', 'status']), CHECKING);
  const rlVerdict = conservativeStatus(firstText(run, ['verdict', 'status']) ?? firstText(rliable, ['note', 'error']), NO_GO);
  const trainStatus = conservativeStatus(firstText(train, ['status']) ?? firstText(record(train?.readiness), ['label']), CHECKING);
  const cost = declaredCostBps(closeSlot);
  const baseline = baselineLabel(run);
  const sourceRun = firstText(closeSlot, ['run_id']) ?? NOT_RECORDED;
  const rlOos = firstMeaningfulText(run, ['test_oos_status', 'test_oos_score', 'oos_return', 'oos_metric']);
  const dailyHasEvidence = hasMeaningfulText(daily, ['overall_status', 'status', 'guardrail', 'mode']);
  const closeHasEvidence = hasMeaningfulText(closeSlot, ['readiness_status', 'status', 'run_id'])
    || hasMeaningfulNumber(closeSlot, ['round_trip_cost_bp', 'cost_bps', 'costBps']);
  const rlHasEvidence = hasMeaningfulText(run, ['verdict', 'status'])
    || hasMeaningfulText(rlRunContext(run), ['line', 'strategy_line', 'primary_baseline', 'baseline_label', 'baseline'])
    || hasMeaningfulText(rliable, ['note']);
  const trainingHasEvidence = hasMeaningfulText(train, ['status'])
    || hasMeaningfulText(record(train?.readiness), ['label'])
    || hasMeaningfulText(metrics, ['runName']);
  const cards: Record<MissionCard['id'], MissionCard> = {
    forecast: {
      id: 'forecast',
      title: 'Forecast',
      eyebrow: '예측 워크벤치',
      verdict: CHECKING,
      metric: '모델 사용 가능성 미선언',
      detail: '이 홈은 모델 빌드/수익 주장을 열지 않습니다.',
      source: 'FALLBACK',
      tone: 'warn',
      tab: 'forecast',
    },
    'daily-d0-d9': {
      id: 'daily-d0-d9',
      title: 'Daily D0–D9',
      eyebrow: '일봉 게이트',
      verdict: dailyStatus,
      metric: firstText(daily, ['guardrail', 'mode']) ?? MISSING,
      detail: 'TEST OOS와 blocker를 차트보다 먼저 확인합니다.',
      source: sourceFromEvidence(dailyHasEvidence),
      tone: toneFor(dailyStatus),
      tab: 'daily-ohlcv',
    },
    'close-slot': {
      id: 'close-slot',
      title: 'close-slot',
      eyebrow: '종가 연구',
      verdict: closeStatus,
      metric: cost,
      detail: `source_run_id ${sourceRun}`,
      source: sourceFromEvidence(closeHasEvidence),
      tone: toneFor(closeStatus),
      tab: 'daily-ohlcv',
    },
    'rl-evidence': {
      id: 'rl-evidence',
      title: 'RL Evidence',
      eyebrow: '증거 콘솔',
      verdict: rlVerdict,
      metric: `${baseline} · ${strictLineLabel(run)}`,
      detail: `TEST OOS ${rlOos ?? NOT_RECORDED}`,
      source: sourceFromEvidence(rlHasEvidence),
      tone: toneFor(rlVerdict),
      tab: 'rl',
    },
    'training-system': {
      id: 'training-system',
      title: 'Training/System',
      eyebrow: '학습/시스템',
      verdict: trainStatus,
      metric: firstText(metrics, ['runName']) ?? NOT_RECORDED,
      detail: '상태 관측만 표시하며 모델 사용 가능성을 선언하지 않습니다.',
      source: sourceFromEvidence(trainingHasEvidence),
      tone: toneFor(trainStatus),
      tab: 'system-health',
    },
    'unresolved-blockers': {
      id: 'unresolved-blockers',
      title: 'unresolved blockers',
      eyebrow: '미해결 blocker',
      verdict: blockers.length > 0 ? `${blockers.length} open` : MISSING,
      metric: blockers[0] ?? NOT_RECORDED,
      detail: blockers.slice(1, 3).join(' · ') || 'blocker가 선언되지 않으면 해제하지 않습니다.',
      source: sourceFromEvidence(blockers.length > 0, true),
      tone: blockers.length > 0 ? 'danger' : 'warn',
      tab: 'daily-ohlcv',
    },
  };
  return CARD_ORDER.map((id) => cards[id]);
}

export function deriveMissionControlModel(inputs: MissionControlInputs): MissionControlModel {
  return {
    topBlocker: deriveTopBlocker(inputs),
    locks: deriveStatusLocks(inputs.closeSlot, latestRlRun(inputs), inputs.dailyProgress),
    workflow: deriveWorkflowSteps(inputs),
    cards: deriveMissionCards(inputs),
  };
}
