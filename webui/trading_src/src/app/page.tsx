'use client';

import { useEffect, useMemo, useState } from 'react';

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

type CommandCard = {
  id: string;
  title: string;
  value: JsonValue;
  status: string;
  label: string;
};

type StatusLock = {
  locked: boolean;
  status: string;
  label: string;
};

type StatusPayload = {
  api_status: string;
  mode: string;
  labels: string[];
  cost_assumption_bps: number;
  claim_locks: Record<string, boolean>;
  status_locks: Record<string, StatusLock>;
  controls: {
    research_intent_record_allowed: boolean;
    unsafe_trading_controls_allowed: boolean;
    job_post_endpoint: string;
    allowed_workflows: string[];
  };
  first_viewport: {
    sections: string[];
    cards: CommandCard[];
  };
  evidence_health: Record<string, { present: boolean; status: string; fields: string[] }>;
};

type WorkflowStep = {
  step: string;
  name: string;
  status: string;
  allowed: boolean;
};

type WorkflowPayload = {
  workflow_id: string;
  status: string;
  labels: string[];
  process_map: WorkflowStep[];
  forbidden_work: string[];
};

type AuditPayload = {
  status: string;
  labels: string[];
  run_id: string;
  events: Array<{ event: string; status: string; details?: string; workflow?: string; job_id?: string }>;
};

type ApiState<T> = {
  data: T;
  failedClosed: boolean;
};

type ExperimentPreset = {
  id: string;
  nameKo: string;
  nameEn: string;
  description: string;
  status: string;
  safeAction: string;
};

const FALLBACK_STATUS: StatusPayload = {
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
    live: { locked: false, status: 'API_UNAVAILABLE', label: 'NO-GO live trading disabled' },
    broker: { locked: false, status: 'API_UNAVAILABLE', label: 'NO-GO broker disabled' },
    order: { locked: false, status: 'API_UNAVAILABLE', label: 'NO-GO order routing disabled' },
    account: { locked: false, status: 'API_UNAVAILABLE', label: 'NO-GO account access disabled' },
    paper: { locked: false, status: 'API_UNAVAILABLE', label: 'NO-GO paper trading disabled' },
    model: { locked: false, status: 'API_UNAVAILABLE', label: 'NO-GO model build disabled' },
    profit: { locked: false, status: 'API_UNAVAILABLE', label: 'NO-GO profit readiness disabled' },
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
      { id: 'selected_run_verdict', title: 'Selected run verdict', value: 'NO-GO', status: 'NO_GO', label: 'NO-GO / RESEARCH_ONLY' },
      { id: 'cost_baseline_delta_23bp', title: '23bp cost/baseline delta', value: null, status: 'API_UNAVAILABLE', label: '23bp vs ts_imb RULE baseline' },
      { id: 'drawdown', title: 'Drawdown', value: null, status: 'API_UNAVAILABLE', label: 'Fail-closed drawdown' },
      { id: 'trade_count_turnover', title: 'Trade count/turnover', value: { trade_count: 0, turnover: null }, status: 'API_UNAVAILABLE', label: 'Fail-closed turnover' },
      { id: 'job_progress', title: 'Job progress', value: { active_job_count: 0, recorded_intent_count: 0, latest_status: 'NOT_STARTED' }, status: 'NOT_STARTED', label: 'Research intent only' },
      { id: 'd0_d9_gate_status', title: 'D0-D9 gate status', value: 'NO-GO', status: 'NO_GO', label: 'D0-D9 gate remains NO-GO' },
    ],
  },
  evidence_health: {
    missing: { present: true, status: 'MISSING', fields: ['backend_status'] },
    stale: { present: true, status: 'STALE', fields: [] },
    malformed: { present: true, status: 'MALFORMED', fields: [] },
    no_go: { present: true, status: 'NO_GO', fields: ['selected_run_verdict'] },
  },
};

const FALLBACK_WORKFLOW: WorkflowPayload = {
  workflow_id: 'trading_command_research_only_fallback',
  status: 'NO-GO',
  labels: ['NO-GO', 'RESEARCH_ONLY', '23bp', 'ts_imb RULE baseline'],
  process_map: [
    { step: 'D0', name: 'Backend unavailable', status: 'API_UNAVAILABLE', allowed: false },
    { step: 'D9', name: 'Trading readiness', status: 'NO_GO', allowed: false },
  ],
  forbidden_work: ['live', 'broker', 'order', 'account', 'paper', 'model_build', 'profit_claim'],
};

const FALLBACK_AUDIT: AuditPayload = {
  status: 'RESEARCH_ONLY_AUDIT',
  labels: ['NO-GO', 'RESEARCH_ONLY', '23bp', 'ts_imb RULE baseline'],
  run_id: 'unavailable',
  events: [{ event: 'fail_closed_fallback_rendered', status: 'NO_GO', details: 'Flask audit API unavailable.' }],
};

const REQUIRED_CARD_ORDER = [
  'selected_run_verdict',
  'cost_baseline_delta_23bp',
  'drawdown',
  'trade_count_turnover',
  'job_progress',
  'd0_d9_gate_status',
];

const STATUS_LOCK_ORDER = ['live', 'broker', 'order', 'account', 'paper', 'model', 'profit'];

const EXPERIMENT_PRESETS: ExperimentPreset[] = [
  {
    id: 'ts_imb_rule_baseline',
    nameKo: 'ts_imb 룰 기준선',
    nameEn: 'RULE baseline',
    description: '현재 메인 기준선입니다. 강화학습 모델이 아니라 비교 기준입니다.',
    status: 'MAINLINE_RULE',
    safeAction: '증거 비교만 가능',
  },
  {
    id: 'dqn_ppo_research_compare',
    nameKo: 'DQN/PPO 연구 비교',
    nameEn: 'RL experiment',
    description: '실패/반증 포함 연구 산출물만 검토합니다. 수익성·실거래 판정이 아닙니다.',
    status: 'RESEARCH_ONLY',
    safeAction: '연구 의도 기록',
  },
  {
    id: 'orderbook_falsification',
    nameKo: '호가창 RL 반증 실험',
    nameEn: 'Orderbook falsification',
    description: 'market_buy/market_exit 같은 행동 설계를 확인하는 격리 실험입니다.',
    status: 'NO_GO_REVIEW',
    safeAction: '결과 시각화 검토',
  },
];

const CARD_COPY: Record<string, { title: string; help: string }> = {
  selected_run_verdict: { title: '선택 산출물 판정', help: 'GO/NO-GO와 연구 전용 여부를 먼저 확인합니다.' },
  cost_baseline_delta_23bp: { title: '23bp 비용·기준선 차이', help: '23bp 비용과 ts_imb 룰 기준선 대비 차이를 봅니다.' },
  drawdown: { title: '최대 낙폭', help: '신선한 drawdown 증거가 없으면 통과하지 않습니다.' },
  trade_count_turnover: { title: '거래 수·회전율', help: '표본 수와 과도한 회전율을 같이 봅니다.' },
  job_progress: { title: '연구 의도 진행', help: '이 화면에서는 연구 의도만 기록하고 실제 주문/학습 실행은 열지 않습니다.' },
  d0_d9_gate_status: { title: 'D0-D9 증거 게이트', help: '데이터부터 최종 연구 검토까지 빠진 증거를 확인합니다.' },
};

const SECTION_COPY: Record<string, string> = {
  status: '상태 잠금',
  workflow: '연구 흐름',
  evidence: '증거 검토',
  'daily-gates': '일봉 게이트',
};

const LOCK_COPY: Record<string, string> = {
  live: '실거래',
  broker: '브로커 연결',
  order: '주문 전송',
  account: '계좌 접근',
  paper: '페이퍼 트레이딩',
  model: '모델 빌드',
  profit: '수익 준비 판정',
};

const STAGE_COPY: Record<string, string> = {
  D0: '데이터·증거 발견',
  D1: '룰 기준선 비교',
  D2: '23bp 비용 게이트',
  D3: '낙폭 검토',
  D4: '거래 수·회전율',
  D5: '음성/셔플 통제',
  D6: 'OOS 분리 검토',
  D7: '감사 증거 묶음',
  D8: '사람 연구 검토',
  D9: '거래 준비 판정',
};

async function fetchJson<T>(path: string, fallback: T): Promise<ApiState<T>> {
  try {
    const response = await fetch(path, { cache: 'no-store' });
    if (!response.ok) throw new Error(`${path} returned ${response.status}`);
    return { data: (await response.json()) as T, failedClosed: false };
  } catch {
    return { data: fallback, failedClosed: true };
  }
}

function stringifyValue(value: JsonValue): string {
  if (value == null || value === '') return '—';
  if (Array.isArray(value)) return value.map(stringifyValue).join(', ');
  if (typeof value === 'object') {
    return Object.entries(value)
      .map(([key, item]) => `${key}: ${stringifyValue(item)}`)
      .join(' · ');
  }
  return String(value);
}

function statusLabel(status: string): string {
  const normalized = status.toUpperCase();
  if (normalized === 'API_UNAVAILABLE') return 'API 미연결(안전 잠금)';
  if (normalized === 'NO_GO') return 'NO-GO';
  if (normalized === 'NOT_STARTED') return '대기';
  if (normalized === 'STALE') return '오래됨';
  if (normalized === 'MISSING') return '증거 없음';
  if (normalized === 'MALFORMED') return '형식 문제';
  if (normalized === 'RECORDED_RESEARCH_INTENT') return '연구 의도 기록됨';
  return status.replaceAll('_', ' ');
}

function compactCardValue(card: CommandCard): string {
  if (card.id === 'job_progress' && card.value && typeof card.value === 'object' && !Array.isArray(card.value)) {
    const value = card.value as Record<string, JsonValue>;
    return `진행 ${stringifyValue(value.active_job_count)} · 기록 ${stringifyValue(value.recorded_intent_count)} · ${statusLabel(stringifyValue(value.latest_status))}`;
  }
  if (card.id === 'trade_count_turnover' && card.value && typeof card.value === 'object' && !Array.isArray(card.value)) {
    const value = card.value as Record<string, JsonValue>;
    return `거래 ${stringifyValue(value.trade_count)} · 회전율 ${stringifyValue(value.turnover)}`;
  }
  return stringifyValue(card.value);
}

function statusTone(status: string): string {
  const normalized = status.toUpperCase();
  if (normalized.includes('NO') || normalized.includes('MISSING') || normalized.includes('MALFORMED') || normalized.includes('UNAVAILABLE')) return 'danger';
  if (normalized.includes('STALE') || normalized.includes('NOT_STARTED')) return 'warn';
  return 'research';
}

function evidenceScore(status: string): number {
  const normalized = status.toUpperCase();
  if (normalized.includes('NO')) return 18;
  if (normalized.includes('MISSING')) return 24;
  if (normalized.includes('MALFORMED')) return 30;
  if (normalized.includes('STALE')) return 42;
  return 68;
}

function splitSymbols(raw: string): string[] {
  return raw
    .split(',')
    .map((symbol) => symbol.trim())
    .filter(Boolean);
}

async function loadCommandSummaries(): Promise<[
  ApiState<StatusPayload>,
  ApiState<WorkflowPayload>,
  ApiState<AuditPayload>,
]> {
  return Promise.all([
    fetchJson('/api/trading-command/status', FALLBACK_STATUS),
    fetchJson('/api/trading-command/workflow', FALLBACK_WORKFLOW),
    fetchJson('/api/trading-command/audit', FALLBACK_AUDIT),
  ]);
}

export default function TradingCommandCenter() {
  const [statusState, setStatusState] = useState<ApiState<StatusPayload>>({ data: FALLBACK_STATUS, failedClosed: true });
  const [workflowState, setWorkflowState] = useState<ApiState<WorkflowPayload>>({ data: FALLBACK_WORKFLOW, failedClosed: true });
  const [auditState, setAuditState] = useState<ApiState<AuditPayload>>({ data: FALLBACK_AUDIT, failedClosed: true });
  const [jobMessage, setJobMessage] = useState('아직 이 화면에서 기록한 연구 의도가 없습니다.');
  const [requestedSection, setRequestedSection] = useState('status');
  const [selectedExperimentId, setSelectedExperimentId] = useState(EXPERIMENT_PRESETS[0].id);
  const [symbolInput, setSymbolInput] = useState('000250,005930,035420');

  useEffect(() => {
    let active = true;
    loadCommandSummaries().then(([status, workflow, audit]) => {
      if (typeof window !== 'undefined') {
        setRequestedSection(new URLSearchParams(window.location.search).get('section') ?? 'status');
      }
      if (!active) return;
      setStatusState(status);
      setWorkflowState(workflow);
      setAuditState(audit);
    });
    return () => {
      active = false;
    };
  }, []);

  const status = statusState.data;
  const workflow = workflowState.data;
  const audit = auditState.data;
  const selectedExperiment = EXPERIMENT_PRESETS.find((preset) => preset.id === selectedExperimentId) ?? EXPERIMENT_PRESETS[0];
  const selectedSymbols = splitSymbols(symbolInput);
  const cards = useMemo(() => {
    const byId = new Map(status.first_viewport.cards.map((card) => [card.id, card]));
    return REQUIRED_CARD_ORDER.map((id) => byId.get(id) ?? FALLBACK_STATUS.first_viewport.cards.find((card) => card.id === id)!);
  }, [status.first_viewport.cards]);
  const fetchBanner = statusState.failedClosed || workflowState.failedClosed || auditState.failedClosed
    ? '백엔드 요약 중 하나가 닫힘 우선(fail-closed)으로 표시되었습니다. API 미연결은 오류가 아니라 안전 잠금입니다.'
    : 'Flask 백엔드 상태·워크플로우·감사 요약을 불러왔습니다.';
  const canRecordResearchIntent = Boolean(status.controls?.research_intent_record_allowed);
  const controlsDisabled = !canRecordResearchIntent;
  const orderedLocks = STATUS_LOCK_ORDER
    .map((key) => [key, status.status_locks[key]] as const)
    .filter((entry): entry is readonly [string, StatusLock] => Boolean(entry[1]));
  const processProgress = Math.round((workflow.process_map.filter((stage) => stage.allowed).length / Math.max(workflow.process_map.length, 1)) * 100);

  async function refreshSummaries(): Promise<void> {
    const [nextStatus, nextWorkflow, nextAudit] = await loadCommandSummaries();
    setStatusState(nextStatus);
    setWorkflowState(nextWorkflow);
    setAuditState(nextAudit);
  }

  async function recordResearchIntent(): Promise<void> {
    if (!canRecordResearchIntent) return;
    setJobMessage('연구 의도를 기록하는 중입니다. 실제 학습·주문 실행은 열지 않습니다.');
    try {
      const response = await fetch(status.controls.job_post_endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow: 'record_research_intent',
          requested_by: 'kronos-command-center-ui',
          config: {
            run_id: 'research_ts_imb_rule_baseline_23bp',
            experiment_preset: selectedExperiment.id,
            symbols: selectedSymbols.length ? selectedSymbols : ['000250'],
            cost_assumption_bps: status.cost_assumption_bps,
            baseline: 'ts_imb RULE baseline',
          },
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.reason ?? `HTTP ${response.status}`);
      setJobMessage(`${statusLabel(payload.status ?? 'RECORDED_RESEARCH_INTENT')} · ${payload.job_id ?? 'job id 없음'}`);
      await refreshSummaries();
    } catch (error) {
      setJobMessage(`연구 의도 기록 거부: ${error instanceof Error ? error.message : '알 수 없는 오류'}`);
    }
  }

  return (
    <main className="command-shell" data-kronos-trading-command-center="true">
      <section className="hero" aria-labelledby="page-title">
        <div className="hero-copy">
          <p className="eyebrow">Kronos Trading Command Center · 강화학습 연구 화면</p>
          <h1 id="page-title">강화학습 연구 커맨드 센터</h1>
          <p className="lede">모델 선택·세팅·증거 확인을 한 화면에서 합니다. 단, 이 화면은 연구 전용이라 실거래, 브로커, 주문, 계좌, 페이퍼, 모델 빌드, 수익 준비 경로를 열지 않습니다.</p>
        </div>
        <div className="verdict-pill tone-danger" aria-label="Selected run verdict">
          <span>NO-GO</span>
          <small>{status.mode}</small>
        </div>
      </section>

      <section className="guardrail-strip" aria-label="Visible trading guardrails">
        {status.labels.map((label) => <span key={label}>{label}</span>)}
        <span>실거래 없음 · 브로커 없음 · 주문 없음 · 수익 주장 없음</span>
      </section>
      <section className="section-request" aria-label="Requested route section">
        현재 섹션: <strong>{SECTION_COPY[requestedSection] ?? requestedSection}</strong>
      </section>

      <section className="research-console panel" aria-label="Korean RL research setup and progress">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">RL research setup</p>
            <h2>1) 실험을 고르고 2) 안전 세팅을 확인하고 3) 결과 증거를 봅니다</h2>
          </div>
          <span className="safe-badge">실행 잠금 · 연구 의도만 기록</span>
        </div>
        <div className="setup-grid">
          <div className="setup-card setup-card-wide">
            <label htmlFor="experiment-preset">모델/실험 선택</label>
            <select id="experiment-preset" value={selectedExperimentId} onChange={(event) => setSelectedExperimentId(event.target.value)}>
              {EXPERIMENT_PRESETS.map((preset) => (
                <option key={preset.id} value={preset.id}>{preset.nameKo} · {preset.nameEn}</option>
              ))}
            </select>
            <p>{selectedExperiment.description}</p>
            <div className="preset-meta">
              <span>{statusLabel(selectedExperiment.status)}</span>
              <span>{selectedExperiment.safeAction}</span>
            </div>
          </div>
          <div className="setup-card">
            <label htmlFor="symbol-input">종목 코드</label>
            <input id="symbol-input" value={symbolInput} onChange={(event) => setSymbolInput(event.target.value)} aria-describedby="symbol-help" />
            <p id="symbol-help">쉼표로 구분합니다. 선행 0은 문자열로 유지합니다.</p>
          </div>
          <div className="setup-card locked-setting">
            <span>비용 가정</span>
            <strong>{status.cost_assumption_bps}bp</strong>
            <p>기본 라운드트립 비용. 임의로 낮추지 않습니다.</p>
          </div>
          <div className="setup-card locked-setting">
            <span>비교 기준</span>
            <strong>ts_imb RULE baseline</strong>
            <p>강화학습 모델이 아니라 룰 기준선입니다.</p>
          </div>
        </div>
        <div className="visual-flow" aria-label="Research workflow visual flow">
          {['선택', '세팅', '의도 기록', '증거 수집', '차트 검토', 'NO-GO 판정'].map((step, index) => (
            <div className="flow-step" key={step} data-active={index <= 2}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <strong>{step}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="first-viewport" aria-label="Approved first viewport">
        <section className="status-locks panel" aria-labelledby="status-locks-title">
          <div className="panel-heading">
            <p className="eyebrow">안전 잠금</p>
            <h2 id="status-locks-title">거래·수익 관련 경로는 모두 꺼짐</h2>
          </div>
          <div className="lock-list">
            {orderedLocks.map(([key, lock]) => (
              <article className="lock-row" data-tone={statusTone(lock.status)} key={key}>
                <span className="lock-state" title={lock.status}>{statusLabel(lock.status)}</span>
                <div>
                  <strong>{`${LOCK_COPY[key] ?? key} 꺼짐`}</strong>
                  <p>{lock.label.replace('NO-GO ', 'NO-GO · ')}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="workflow-map panel" aria-labelledby="workflow-map-title">
          <div className="panel-heading">
            <p className="eyebrow">시각적 연구 흐름</p>
            <h2 id="workflow-map-title">D0-D9 증거 경로</h2>
          </div>
          <div className="progress-meter" aria-label={`D0-D9 allowed progress ${processProgress}%`}>
            <span style={{ width: `${Math.max(processProgress, 3)}%` }} />
            <strong>{processProgress}%</strong>
          </div>
          <div className="stage-track">
            {workflow.process_map.map((stage) => (
              <article className="stage-node" data-allowed={stage.allowed} data-tone={statusTone(stage.status)} key={stage.step}>
                <span>{stage.step}</span>
                <strong>{STAGE_COPY[stage.step] ?? stage.name}</strong>
                <small title={stage.status}>{statusLabel(stage.status)}</small>
              </article>
            ))}
          </div>
          <p className="workflow-note">금지된 작업: {workflow.forbidden_work.join(' · ')}</p>
        </section>

        <section className="kpi-grid" aria-label="Exactly six backend-owned KPI and chart cards">
          {cards.map((card, index) => (
            <article className="kpi-card" data-tone={statusTone(card.status)} key={card.id}>
              <p className="card-index">{String(index + 1).padStart(2, '0')}</p>
              <h3>{CARD_COPY[card.id]?.title ?? card.title}</h3>
              <strong>{compactCardValue(card)}</strong>
              <p>{CARD_COPY[card.id]?.help ?? card.label}</p>
              <small title={card.status}>{statusLabel(card.status)}</small>
            </article>
          ))}
        </section>
      </section>

      <section className="below-viewport" aria-label="Evidence drilldowns and disabled controls">
        <div className="job-controls panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">연구 의도 / 컨트롤</p>
              <h2>버튼은 연구 기록용입니다. 학습·주문 실행 버튼이 아닙니다.</h2>
            </div>
            <span className="safe-badge">{selectedExperiment.nameKo}</span>
          </div>
          <p className="status-line">{fetchBanner}</p>
          <div className="control-row" aria-disabled={controlsDisabled}>
            <button type="button" onClick={() => void refreshSummaries()}>백엔드 상태 새로고침</button>
            <button type="button" disabled>증거 묶음 열기</button>
            <button type="button" disabled={!canRecordResearchIntent} onClick={() => void recordResearchIntent()}>선택한 연구 의도 기록</button>
          </div>
          <p className="disabled-note">{jobMessage} 이 UI는 live/broker/order/model/profit 경로를 열지 않습니다.</p>
        </div>

        <div className="chart-grid">
          <section className="panel" aria-labelledby="evidence-chart-title">
            <div className="panel-heading">
              <p className="eyebrow">차트형 증거 상태</p>
              <h2 id="evidence-chart-title">부족한 증거가 어디인지 한눈에 보기</h2>
            </div>
            <div className="evidence-bars">
              {Object.entries(status.evidence_health).map(([key, item]) => (
                <div className="evidence-bar-row" key={key}>
                  <div>
                    <strong>{key}</strong>
                    <span>{statusLabel(item.status)}</span>
                  </div>
                  <div className="evidence-bar"><span style={{ width: `${evidenceScore(item.status)}%` }} /></div>
                  <small>{item.fields.length ? item.fields.join(' · ') : '백엔드 필드 없음'}</small>
                </div>
              ))}
            </div>
          </section>

          <section className="panel" aria-labelledby="audit-title">
            <div className="panel-heading">
              <p className="eyebrow">감사 로그</p>
              <h2 id="audit-title">무엇이 기록됐는지</h2>
            </div>
            <div className="audit-log">
              {audit.events.map((entry, index) => (
                <article key={`${entry.event}-${index}`}>
                  <span title={entry.status}>{statusLabel(entry.status)}</span>
                  <strong>{entry.event}</strong>
                  <p>{entry.details ?? entry.workflow ?? entry.job_id ?? '백엔드 감사 이벤트'}</p>
                </article>
              ))}
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}
