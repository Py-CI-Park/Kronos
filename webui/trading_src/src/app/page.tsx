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
  controls?: {
    research_intent_record_allowed?: boolean;
    unsafe_trading_controls_allowed?: boolean;
    job_post_endpoint: string;
    allowed_workflows?: string[];
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
  events: Array<Record<string, string>>;
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
  process_map: Array.from({ length: 10 }, (_, index) => ({
    step: `D${index}`,
    name: `Evidence gate ${index}`,
    status: index === 9 ? 'NO_GO' : 'API_UNAVAILABLE',
    allowed: index < 9,
  })),
  forbidden_work: ['live', 'broker', 'order', 'account', 'paper', 'model_build', 'profit_claim'],
};

const FALLBACK_AUDIT: AuditPayload = {
  status: 'RESEARCH_ONLY_AUDIT',
  labels: ['NO-GO', 'RESEARCH_ONLY', '23bp', 'ts_imb RULE baseline'],
  run_id: 'research_ts_imb_rule_baseline_23bp',
  events: [{ event: 'guardrails_loaded', status: 'NO_GO', details: 'fail-closed fallback audit' }],
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

const NAV_ITEMS = [
  ['연구 홈', 'NO-GO 판정'],
  ['실험 설정', 'preset · universe'],
  ['연구 큐', 'intent only'],
  ['결과 비교', 'charts'],
  ['증거 감사', 'artifact manifest'],
  ['사용 가이드', 'guardrails'],
] as const;

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

const GLOSSARY = [
  ['ts_imb', '강화학습이 아니라 룰 기준선입니다. RL 후보는 이 기준선과 비용 반영 후 비교합니다.'],
  ['23bp', '기본 왕복 비용 가정입니다. 결과 차트와 판정에서 임의로 낮추지 않습니다.'],
  ['NO-GO', '실패를 숨기지 않고 보여주는 연구 판정입니다. 이 화면은 실거래 대상이 아닙니다.'],
  ['API 미연결', 'live/broker/order/account/profit 경로를 열지 않는 안전 잠금 상태입니다.'],
];

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
    return `기록 ${stringifyValue(value.recorded_intent_count)} · 실행 ${stringifyValue(value.active_job_count)} · ${statusLabel(stringifyValue(value.latest_status))}`;
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

function MiniLineChart() {
  return (
    <svg viewBox="0 0 320 120" role="img" aria-label="drawdown placeholder line chart" className="mini-chart">
      <defs>
        <linearGradient id="drawdownArea" x1="0" y1="0" x2="0" y2="1">
          <stop stopColor="#38bdf8" stopOpacity="0.45" />
          <stop offset="1" stopColor="#ef4444" stopOpacity="0.08" />
        </linearGradient>
      </defs>
      {[0, 1, 2, 3].map((line) => <line key={line} x1="0" x2="320" y1={20 + line * 25} y2={20 + line * 25} />)}
      <path d="M8 42 C52 30, 70 58, 110 50 C150 42, 165 92, 205 78 C245 66, 260 88, 314 70 L314 112 L8 112 Z" fill="url(#drawdownArea)" />
      <path d="M8 42 C52 30, 70 58, 110 50 C150 42, 165 92, 205 78 C245 66, 260 88, 314 70" fill="none" stroke="#38bdf8" strokeWidth="3" />
      <text x="16" y="106">drawdown 증거 없음 · placeholder</text>
    </svg>
  );
}

function BaselineBars() {
  const bars = [
    ['ts_imb', 74, '#22d3ee', '룰 기준선'],
    ['DQN/PPO', 38, '#f59e0b', '검증 부족'],
    ['Orderbook', 26, '#fb7185', 'NO-GO'],
  ] as const;
  return (
    <div className="bar-compare" aria-label="Baseline versus candidate chart">
      {bars.map(([name, value, color, label]) => (
        <div className="compare-row" key={name}>
          <span>{name}</span>
          <div><i style={{ width: `${value}%`, background: color }} /></div>
          <strong>{label}</strong>
        </div>
      ))}
    </div>
  );
}

function HeatmapMatrix() {
  const cells = ['D0', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9'];
  return (
    <div className="heatmap" aria-label="OOS and negative control matrix">
      {cells.map((cell, index) => (
        <div key={cell} data-tone={index < 3 ? 'watch' : index === 9 ? 'no-go' : 'missing'}>
          <span>{cell}</span>
          <small>{index < 3 ? '검토' : index === 9 ? 'NO-GO' : '증거 없음'}</small>
        </div>
      ))}
    </div>
  );
}

export default function TradingCommandCenter() {
  const [statusState, setStatusState] = useState<ApiState<StatusPayload>>({ data: FALLBACK_STATUS, failedClosed: true });
  const [workflowState, setWorkflowState] = useState<ApiState<WorkflowPayload>>({ data: FALLBACK_WORKFLOW, failedClosed: true });
  const [auditState, setAuditState] = useState<ApiState<AuditPayload>>({ data: FALLBACK_AUDIT, failedClosed: true });
  const [jobMessage, setJobMessage] = useState('아직 이 화면에서 기록한 연구 의도가 없습니다.');
  const [selectedExperimentId, setSelectedExperimentId] = useState(EXPERIMENT_PRESETS[0].id);
  const [symbolInput, setSymbolInput] = useState('000250,005930,035420');

  useEffect(() => {
    let active = true;
    loadCommandSummaries().then(([status, workflow, audit]) => {
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
    if (!canRecordResearchIntent || !status.controls?.job_post_endpoint) return;
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
    <main className="pixel-dashboard" data-kronos-trading-command-center="true">
      <aside className="side-rail" aria-label="Kronos research navigation">
        <div className="brand-mark">
          <span>K</span>
          <div>
            <strong>Kronos</strong>
            <small>research ops</small>
          </div>
        </div>
        <nav>
          {NAV_ITEMS.map(([label, hint], index) => (
            <a href={`#section-${index}`} className={index === 0 ? 'active' : ''} key={label}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <strong>{label}</strong>
              <small>{hint}</small>
            </a>
          ))}
        </nav>
        <div className="source-card">
          <span>design source</span>
          <strong>pixel_svg_v4.zip</strong>
          <small>원본 zip 백업 완료</small>
        </div>
      </aside>

      <section className="main-stage">
        <header className="command-header" id="section-0">
          <div>
            <p className="eyebrow">Kronos Trading Command Center · research-only evidence</p>
            <h1>강화학습 연구 커맨드 센터</h1>
            <p className="lede">연구 전용 증거 검토 화면입니다. 실거래, 브로커, 주문, 계좌, 페이퍼, 모델 빌드, 수익 준비 경로는 열리지 않습니다.</p>
          </div>
          <div className="status-orb">
            <span>NO-GO</span>
            <small>{status.mode}</small>
          </div>
        </header>

        <section className="badge-strip" aria-label="Visible trading guardrails">
          {status.labels.map((label) => <span key={label}>{label}</span>)}
          <span>실거래 없음</span>
          <span>브로커 없음</span>
          <span>주문 없음</span>
          <span>수익 주장 없음</span>
        </section>

        <section className="topology-grid" id="section-1">
          <article className="panel setup-panel">
            <div className="panel-heading">
              <p className="eyebrow">A · 연구 설정</p>
              <h2>실험 선택과 안전 세팅</h2>
            </div>
            <label htmlFor="experiment-preset">모델/실험 선택</label>
            <select id="experiment-preset" value={selectedExperimentId} onChange={(event) => setSelectedExperimentId(event.target.value)}>
              {EXPERIMENT_PRESETS.map((preset) => (
                <option key={preset.id} value={preset.id}>{preset.nameKo} · {preset.nameEn}</option>
              ))}
            </select>
            <p className="copy-muted">{selectedExperiment.description}</p>
            <div className="chip-row">
              <span>{statusLabel(selectedExperiment.status)}</span>
              <span>{selectedExperiment.safeAction}</span>
            </div>
            <div className="setup-fields">
              <label htmlFor="symbol-input">종목 코드</label>
              <input id="symbol-input" value={symbolInput} onChange={(event) => setSymbolInput(event.target.value)} />
              <small>쉼표로 구분합니다. 선행 0은 문자열로 유지합니다.</small>
            </div>
            <div className="setting-pair">
              <div><span>비용 가정</span><strong>{status.cost_assumption_bps}bp</strong></div>
              <div><span>비교 기준</span><strong>ts_imb RULE baseline</strong></div>
            </div>
            <div className="control-row">
              <button type="button" onClick={() => void recordResearchIntent()} disabled={!canRecordResearchIntent}>선택한 연구 의도 기록</button>
              <button type="button" disabled>실제 학습 실행 잠금</button>
            </div>
            <p className="danger-note">이 버튼은 연구 의도만 기록하며 주문·브로커·수익 경로를 열지 않습니다.</p>
          </article>

          <article className="panel lock-panel">
            <div className="panel-heading">
              <p className="eyebrow">B · 안전 잠금</p>
              <h2>거래·수익 경로는 모두 꺼짐</h2>
            </div>
            <div className="lock-list">
              {orderedLocks.map(([key, lock]) => (
                <div className="lock-row" data-tone={statusTone(lock.status)} key={key}>
                  <span>{statusLabel(lock.status)}</span>
                  <strong>{`${LOCK_COPY[key] ?? key} 꺼짐`}</strong>
                  <small>{lock.label.replace('NO-GO ', 'NO-GO · ')}</small>
                </div>
              ))}
            </div>
          </article>

          <article className="panel workflow-panel" id="section-2">
            <div className="panel-heading with-progress">
              <div>
                <p className="eyebrow">C · D0-D9 evidence workflow</p>
                <h2>D0-D9 증거 경로</h2>
              </div>
              <strong>{processProgress}%</strong>
            </div>
            <div className="progress-meter"><span style={{ width: `${Math.max(processProgress, 3)}%` }} /></div>
            <div className="workflow-nodes">
              {workflow.process_map.map((stage, index) => (
                <article className="workflow-node" data-tone={statusTone(stage.status)} data-final={stage.step === 'D9'} key={stage.step}>
                  <span>{stage.step}</span>
                  <strong>{STAGE_COPY[stage.step] ?? stage.name}</strong>
                  <small>{statusLabel(stage.status)}</small>
                  {index < workflow.process_map.length - 1 && <i aria-hidden="true" />}
                </article>
              ))}
            </div>
            <p className="workflow-note">금지된 작업: {workflow.forbidden_work.join(' · ')}</p>
          </article>
        </section>

        <section className="kpi-strip" aria-label="Six backend-owned KPI cards">
          {cards.map((card, index) => (
            <article className="kpi-card" data-tone={statusTone(card.status)} key={card.id}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <h3>{CARD_COPY[card.id]?.title ?? card.title}</h3>
              <strong>{compactCardValue(card)}</strong>
              <p>{CARD_COPY[card.id]?.help ?? card.label}</p>
              <small>{statusLabel(card.status)}</small>
            </article>
          ))}
        </section>

        <section className="analytics-grid" id="section-3">
          <article className="panel chart-panel evidence-card">
            <div className="panel-heading">
              <p className="eyebrow">차트형 증거 상태</p>
              <h2>부족한 증거가 어디인지 한눈에 보기</h2>
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
          </article>

          <article className="panel chart-panel">
            <div className="panel-heading">
              <p className="eyebrow">Baseline vs Candidate</p>
              <h2>23bp 후 기준선 대비 비교</h2>
            </div>
            <BaselineBars />
          </article>

          <article className="panel chart-panel">
            <div className="panel-heading">
              <p className="eyebrow">Drawdown</p>
              <h2>낙폭 곡선 / 증거 없음</h2>
            </div>
            <MiniLineChart />
          </article>

          <article className="panel chart-panel">
            <div className="panel-heading">
              <p className="eyebrow">OOS / controls</p>
              <h2>OOS·음성 통제 매트릭스</h2>
            </div>
            <HeatmapMatrix />
          </article>
        </section>

        <section className="audit-and-guide" id="section-4">
          <article className="panel audit-panel">
            <div className="panel-heading">
              <p className="eyebrow">감사 로그</p>
              <h2>무엇이 기록됐는지</h2>
            </div>
            <p className="status-line">{fetchBanner}</p>
            <div className="audit-log">
              {audit.events.map((entry, index) => (
                <article key={`${entry.event}-${index}`}>
                  <span>{statusLabel(entry.status ?? 'AUDITED')}</span>
                  <strong>{entry.event}</strong>
                  <p>{entry.details ?? entry.workflow ?? entry.job_id ?? '백엔드 감사 이벤트'}</p>
                </article>
              ))}
            </div>
            <p className="danger-note">{jobMessage} 이 UI는 live/broker/order/model/profit 경로를 열지 않습니다.</p>
          </article>

          <article className="panel glossary-panel" id="section-5">
            <div className="panel-heading">
              <p className="eyebrow">사용 가이드</p>
              <h2>용어와 해석 기준</h2>
            </div>
            <div className="glossary-grid">
              {GLOSSARY.map(([term, explanation]) => (
                <div key={term}>
                  <strong>{term}</strong>
                  <p>{explanation}</p>
                </div>
              ))}
            </div>
          </article>
        </section>
      </section>
    </main>
  );
}
