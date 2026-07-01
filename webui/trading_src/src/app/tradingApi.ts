import type {
  ApiState,
  AuditPayload,
  EvidencePayload,
  DrilldownPayload,
  StatusLock,
  StatusPayload,
  WorkflowPayload,
} from './tradingTypes';
import {
  D9_RESEARCH_GATE_LABEL,
  hasString,
  isRecord,
  isStringArray,
} from './tradingFormat';

const blockedLock = (label: string, reason: string): StatusLock => ({
  locked: true,
  allowed: false,
  enabled: false,
  capability_state: 'BLOCKED',
  status: 'API_UNAVAILABLE',
  label,
  reason,
});

export const FALLBACK_STATUS: StatusPayload = {
  api_status: 'API_UNAVAILABLE',
  mode: 'RESEARCH_ONLY',
  labels: ['NO-GO', 'RESEARCH_ONLY', '23bp', 'ts_imb RULE baseline'],
  cost_assumption_bps: 23,
  claim_locks: {
    live: false,
    broker: false,
    order: false,
    account: false,
    paper: false,
    model: false,
    profit: false,
  },
  status_locks: {
    live: blockedLock('NO-GO · 실거래 경로 잠금', '실거래 기능은 연구 전용 대시보드에서 차단됩니다.'),
    broker: blockedLock('NO-GO · 브로커 연결 잠금', '브로커 연결 기능은 연구 전용 대시보드에서 차단됩니다.'),
    order: blockedLock('NO-GO · 주문 전송 경로 잠금', '주문 전송 기능은 연구 전용 대시보드에서 차단됩니다.'),
    account: blockedLock('NO-GO · 계좌 접근 잠금', '계좌 접근 기능은 연구 전용 대시보드에서 차단됩니다.'),
    paper: blockedLock('NO-GO · 페이퍼 트레이딩 잠금', '페이퍼 트레이딩 기능은 연구 전용 대시보드에서 차단됩니다.'),
    model: blockedLock('NO-GO · 모델 빌드 잠금', '모델 빌드 기능은 연구 전용 대시보드에서 차단됩니다.'),
    profit: blockedLock('NO-GO · 수익 주장 경로 잠금', '수익 주장은 연구 전용 대시보드에서 차단됩니다.'),
  },
  controls: {
    research_intent_record_allowed: false,
    unsafe_trading_controls_allowed: false,
    job_post_endpoint: '/api/trading-command/jobs',
    allowed_workflows: ['record_research_intent'],
  },
  first_viewport: {
    sections: ['status_locks', 'workflow_process_map', 'kpi_cards'],
    cards: [
      { id: 'selected_run_verdict', title: '선택 산출물 판정', value: 'NO-GO', status: 'NO_GO', label: 'NO-GO / 연구 전용' },
      { id: 'cost_baseline_delta_23bp', title: '23bp 비용·기준선 차이', value: null, status: 'API_UNAVAILABLE', label: '23bp vs ts_imb 룰 기준선' },
      { id: 'drawdown', title: '최대 낙폭', value: null, status: 'API_UNAVAILABLE', label: '증거 없으면 차단' },
      { id: 'trade_count_turnover', title: '거래 수·회전율', value: { trade_count: 0, turnover: null }, status: 'API_UNAVAILABLE', label: '회전율 증거 없으면 차단' },
      { id: 'job_progress', title: '연구 의도 진행', value: { active_job_count: 0, recorded_intent_count: 0, latest_status: 'NOT_STARTED' }, status: 'NOT_STARTED', label: '연구 의도 기록만' },
      { id: 'd0_d9_gate_status', title: 'D0-D9 증거 게이트', value: 'NO-GO', status: 'NO_GO', label: 'D0-D9 게이트 NO-GO 유지' },
    ],
  },
  evidence_health: {
    missing: { present: true, status: 'MISSING', fields: ['backend_status'] },
    stale: { present: true, status: 'STALE', fields: [] },
    malformed: { present: true, status: 'MALFORMED', fields: [] },
    no_go: { present: true, status: 'NO_GO', fields: ['selected_run_verdict'] },
  },
  queue_summary: {
    mode: 'RESEARCH_ONLY_QUEUE',
    active_job_count: 0,
    recorded_intent_count: 0,
    latest_status: 'NOT_STARTED',
    latest_job_id: null,
    status_counts: {},
    allowed_workflows: ['record_research_intent'],
    unsafe_controls_allowed: false,
  },
};

export const FALLBACK_WORKFLOW: WorkflowPayload = {
  workflow_id: 'trading_command_research_only_fallback',
  status: 'NO-GO',
  labels: ['NO-GO', 'RESEARCH_ONLY', '23bp', 'ts_imb RULE baseline'],
  process_map: Array.from({ length: 10 }, (_, index) => ({
    step: `D${index}`,
    name: ['데이터·증거 발견', '룰 기준선 비교', '23bp 비용 게이트', '낙폭 검토', '거래 수·회전율', '음성/셔플 통제', 'OOS 분리 검토', '감사 증거 묶음', '사람 연구 검토', D9_RESEARCH_GATE_LABEL][index] ?? `증거 게이트 ${index}`,
    status: index === 9 ? 'NO_GO' : 'API_UNAVAILABLE',
    allowed: false,
    enabled: false,
    review_allowed: index < 9,
    capability_state: 'BLOCKED',
    blocker_reason: index === 9 ? '연구 검토 기준상 NO-GO 게이트가 유지됩니다.' : '백엔드 증거가 없으므로 안전 잠금 상태입니다.',
    source_run_id: 'research_ts_imb_rule_baseline_23bp',
    artifact_refs: [`research_ts_imb_rule_baseline_23bp:d${index}`],
    updated_at: null,
  })),
  forbidden_work: ['live', 'broker', 'order', 'account', 'paper', 'model_build', 'profit_claim'],
};

export const FALLBACK_AUDIT: AuditPayload = {
  status: 'RESEARCH_ONLY_AUDIT',
  labels: ['NO-GO', 'RESEARCH_ONLY', '23bp', 'ts_imb RULE baseline'],
  run_id: 'research_ts_imb_rule_baseline_23bp',
  events: [{ event: 'guardrails_loaded', status: 'NO_GO', details: 'fail-closed fallback audit' }],
};

export const FALLBACK_EVIDENCE: EvidencePayload = {
  run_id: 'research_ts_imb_rule_baseline_23bp',
  status: 'NO_GO',
  labels: ['NO-GO', 'RESEARCH_ONLY', '23bp', 'ts_imb RULE baseline'],
  symbols: ['000250', '005930', '035420'],
  artifacts: [
    {
      artifact_id: 'fallback-d9-gate',
      run_id: 'research_ts_imb_rule_baseline_23bp',
      kind: 'd0_d9_gate',
      series_source: 'BACKEND_OWNED',
      hash: null,
      path: null,
      timestamp: null,
      freshness: 'MISSING',
      schema_status: 'MISSING',
      status: 'MISSING',
      blocker_reason: '백엔드 증거가 없으므로 D0-D9 게이트 산출물이 없습니다.',
      source_stage: 'D9',
      source_run_id: 'research_ts_imb_rule_baseline_23bp',
      symbols: ['000250', '005930', '035420'],
    },
  ],
};
export const FALLBACK_DRILLDOWN: DrilldownPayload = {
  run_id: 'research_ts_imb_rule_baseline_23bp',
  status: 'NO_GO',
  labels: ['NO-GO', 'RESEARCH_ONLY', '23bp', 'ts_imb RULE baseline'],
  safe_preview_policy: {
    max_preview_chars: 1400,
    path_safe: true,
    hash_backed: true,
    allowed_roots: [],
    active_job_count: 0,
    unsafe_controls_allowed: false,
  },
  queue_summary: FALLBACK_STATUS.queue_summary,
  tabs: [
    {
      id: 'raw_json',
      title: '원본 JSON 일부',
      description: 'API 미연결 시 안전 잠금 fallback JSON입니다.',
      source: 'fallback:drilldown',
      preview_hash: 'fallback',
      path_safe: true,
      hash_backed: true,
      row_count: 1,
      rows: [{ status: 'API_UNAVAILABLE' }],
      raw_json: { status: 'API_UNAVAILABLE' },
    },
  ],
};

export function validateStatusPayload(value: unknown): value is StatusPayload {
  if (!isRecord(value)) return false;
  const firstViewport = value.first_viewport;
  const queueSummary = value.queue_summary;
  return hasString(value, 'api_status')
    && hasString(value, 'mode')
    && isStringArray(value.labels)
    && typeof value.cost_assumption_bps === 'number'
    && isRecord(value.claim_locks)
    && isRecord(value.status_locks)
    && isRecord(firstViewport)
    && Array.isArray(firstViewport.cards)
    && firstViewport.cards.length >= 6
    && isRecord(value.evidence_health)
    && (!queueSummary || (isRecord(queueSummary) && typeof queueSummary.active_job_count === 'number' && typeof queueSummary.recorded_intent_count === 'number'));
}

export function validateWorkflowPayload(value: unknown): value is WorkflowPayload {
  if (!isRecord(value) || !Array.isArray(value.process_map)) return false;
  return hasString(value, 'workflow_id')
    && hasString(value, 'status')
    && isStringArray(value.labels)
    && value.process_map.every((stage) => isRecord(stage)
      && hasString(stage, 'step')
      && hasString(stage, 'name')
      && hasString(stage, 'status')
      && typeof stage.allowed === 'boolean'
      && typeof stage.enabled === 'boolean'
      && typeof stage.review_allowed === 'boolean'
      && hasString(stage, 'capability_state')
      && hasString(stage, 'blocker_reason')
      && hasString(stage, 'source_run_id')
      && Array.isArray(stage.artifact_refs)
      && 'updated_at' in stage);
}
export function validateDrilldownPayload(value: unknown): value is DrilldownPayload {
  if (!isRecord(value) || !Array.isArray(value.tabs)) return false;
  const policy = value.safe_preview_policy;
  return hasString(value, 'run_id')
    && hasString(value, 'status')
    && isStringArray(value.labels)
    && isRecord(policy)
    && typeof policy.path_safe === 'boolean'
    && typeof policy.hash_backed === 'boolean'
    && typeof policy.active_job_count === 'number'
    && typeof policy.unsafe_controls_allowed === 'boolean'
    && value.tabs.every((tab) => isRecord(tab)
      && hasString(tab, 'id')
      && hasString(tab, 'title')
      && hasString(tab, 'source')
      && hasString(tab, 'preview_hash')
      && typeof tab.path_safe === 'boolean'
      && typeof tab.hash_backed === 'boolean'
      && typeof tab.row_count === 'number'
      && Array.isArray(tab.rows)
      && 'raw_json' in tab);
}

export function validateAuditPayload(value: unknown): value is AuditPayload {
  return isRecord(value)
    && hasString(value, 'status')
    && isStringArray(value.labels)
    && hasString(value, 'run_id')
    && Array.isArray(value.events);
}

export function validateEvidencePayload(value: unknown): value is EvidencePayload {
  if (!isRecord(value) || !Array.isArray(value.artifacts)) return false;
  return hasString(value, 'run_id')
    && hasString(value, 'status')
    && isStringArray(value.labels)
    && isStringArray(value.symbols)
    && value.artifacts.every((artifact) => isRecord(artifact)
      && hasString(artifact, 'artifact_id')
      && hasString(artifact, 'kind')
      && 'hash' in artifact
      && 'path' in artifact
      && 'timestamp' in artifact
      && hasString(artifact, 'freshness')
      && hasString(artifact, 'schema_status')
      && hasString(artifact, 'status')
      && hasString(artifact, 'blocker_reason')
      && hasString(artifact, 'source_stage')
      && hasString(artifact, 'source_run_id')
      && isStringArray(artifact.symbols));
}

async function fetchJson<T>(path: string, fallback: T, validate: (value: unknown) => value is T): Promise<ApiState<T>> {
  try {
    const response = await fetch(path, { cache: 'no-store' });
    if (!response.ok) throw new Error(`${path} returned ${response.status}`);
    const payload = await response.json();
    if (!validate(payload)) throw new Error(`${path} returned malformed research payload`);
    return { data: payload, failedClosed: false };
  } catch {
    return { data: fallback, failedClosed: true };
  }
}

export async function loadCommandSummaries(): Promise<[
  ApiState<StatusPayload>,
  ApiState<WorkflowPayload>,
  ApiState<AuditPayload>,
  ApiState<EvidencePayload>,
  ApiState<DrilldownPayload>,
]> {
  return Promise.all([
    fetchJson('/api/trading-command/status', FALLBACK_STATUS, validateStatusPayload),
    fetchJson('/api/trading-command/workflow', FALLBACK_WORKFLOW, validateWorkflowPayload),
    fetchJson('/api/trading-command/audit', FALLBACK_AUDIT, validateAuditPayload),
    fetchJson('/api/trading-command/runs/research_ts_imb_rule_baseline_23bp/evidence', FALLBACK_EVIDENCE, validateEvidencePayload),
    fetchJson('/api/trading-command/runs/research_ts_imb_rule_baseline_23bp/drilldown', FALLBACK_DRILLDOWN, validateDrilldownPayload),
  ]);
}
