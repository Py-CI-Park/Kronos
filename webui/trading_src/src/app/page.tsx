'use client';

import { useEffect, useMemo, useState } from 'react';
import type { KeyboardEvent } from 'react';
import type { ApiState, AuditPayload, DrilldownPayload, EvidenceArtifact, EvidencePayload, StatusLock, StatusPayload, WorkflowPayload } from './tradingTypes';
import { FALLBACK_AUDIT, FALLBACK_DRILLDOWN, FALLBACK_EVIDENCE, FALLBACK_STATUS, FALLBACK_WORKFLOW, loadCommandSummaries } from './tradingApi';
import {
  CARD_COPY,
  EXPERIMENT_PRESETS,
  GLOSSARY,
  LOCK_COPY,
  REQUIRED_CARD_ORDER,
  STATUS_LOCK_ORDER,
  STAGE_COPY,
  compactCardValue,
  splitSymbols,
  statusLabel,
  statusTone,
} from './tradingFormat';
import {
  EvidenceSourceStrip,
  EvidenceDecisionNote,
  ResearchChart,
  baselineChartOption,
  chartEmptyState,
  controlsChartOption,
  drawdownChartOption,
  evidenceChartOption,
  freshnessChartOption,
  tradeTurnoverChartOption,
} from './components/ResearchCharts';
import { WorkflowGraph } from './components/WorkflowGraph';
import { ArtifactManifestTable, AuditTimelineTable, RunComparisonTable } from './components/EvidenceTables';
import { ArtifactDrilldowns } from './components/ArtifactDrilldowns';
import { IntentHistory } from './components/IntentHistory';

const DASHBOARD_VIEWS = [
  { id: 'home', label: '연구 홈', hint: 'NO-GO 판정', panelId: 'dashboard-panel-home' },
  { id: 'setup', label: '실험 설정', hint: '연구 전용', panelId: 'dashboard-panel-setup' },
  { id: 'queue', label: '연구 큐', hint: '의도 기록', panelId: 'dashboard-panel-queue' },
  { id: 'compare', label: '결과 비교', hint: '차트', panelId: 'dashboard-panel-compare' },
  { id: 'evidence', label: '증거 감사', hint: '증거 묶음', panelId: 'dashboard-panel-evidence' },
  { id: 'guide', label: '사용 가이드', hint: '잠금 유지', panelId: 'dashboard-panel-guide' },
] as const;

type DashboardViewId = typeof DASHBOARD_VIEWS[number]['id'];

function isDashboardViewId(value: string | null): value is DashboardViewId {
  return DASHBOARD_VIEWS.some((view) => view.id === value);
}

function evidenceStatusCounts(evidence: EvidencePayload): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const artifact of evidence.artifacts.length ? evidence.artifacts : FALLBACK_EVIDENCE.artifacts) {
    counts[artifact.status] = (counts[artifact.status] ?? 0) + 1;
  }
  return counts;
}

function ViewPurposeCard({ eyebrow, title, body, checks }: { eyebrow: string; title: string; body: string; checks: string[] }) {
  return (
    <section className="view-purpose-card" aria-label={`${title} 화면 목적`}>
      <p className="eyebrow">{eyebrow}</p>
      <h2>{title}</h2>
      <p>{body}</p>
      <div>
        {checks.map((check) => <span key={check}>{check}</span>)}
      </div>
    </section>
  );
}

function HomeDecisionPanel({ status, evidence, workflow }: { status: StatusPayload; evidence: EvidencePayload; workflow: WorkflowPayload }) {
  const counts = evidenceStatusCounts(evidence);
  const finalGate = workflow.process_map.find((stage) => stage.step === 'D9');
  const missingLike = (counts.MISSING ?? 0) + (counts.NO_GO ?? 0) + (counts.MALFORMED ?? 0) + (counts.STALE ?? 0);
  return (
    <section className="home-decision-grid" aria-label="연구 홈 핵심 판단">
      <article className="decision-tile danger">
        <span>현재 판정</span>
        <strong>NO-GO</strong>
        <p>{status.mode} · 실거래/브로커/주문/계좌/페이퍼/모델 빌드/수익 주장은 열리지 않습니다.</p>
      </article>
      <article className="decision-tile">
        <span>비교 기준</span>
        <strong>ts_imb RULE baseline</strong>
        <p>강화학습 정책이 아니라 23bp 비용 가정으로 비교하는 규칙 기준선입니다.</p>
      </article>
      <article className="decision-tile warn">
        <span>증거 부족</span>
        <strong>{missingLike}개 점검</strong>
        <p>missing/stale/malformed/no-go 증거는 결과 비교와 증거 감사 화면에서 원인만 보여줍니다.</p>
      </article>
      <article className="decision-tile danger">
        <span>D9 게이트</span>
        <strong>{statusLabel(finalGate?.status ?? 'NO_GO')}</strong>
        <p>{finalGate?.blocker_reason ?? '최종 연구 검토가 끝날 때까지 배포·실거래는 금지됩니다.'}</p>
      </article>
    </section>
  );
}

function EvidenceHealthSummary({ evidence, workflow }: { evidence: EvidencePayload; workflow: WorkflowPayload }) {
  const artifacts = evidence.artifacts.length ? evidence.artifacts : FALLBACK_EVIDENCE.artifacts;
  const counts = evidenceStatusCounts(evidence);
  const finalBlocker = workflow.process_map.find((stage) => stage.step === 'D9')?.blocker_reason ?? artifacts[0]?.blocker_reason ?? '최종 차단 사유 없음';
  return (
    <section className="evidence-summary-grid" aria-label="증거 감사 요약">
      {[
        ['FRESH', counts.FRESH ?? 0, '검증된 backend-owned 증거'],
        ['MISSING', counts.MISSING ?? 0, '누락되어 NO-GO 원인이 되는 증거'],
        ['MALFORMED', counts.MALFORMED ?? 0, 'schema/hash/path 형식 문제'],
        ['STALE', counts.STALE ?? 0, '오래되어 신선한 비교로 쓰지 않는 증거'],
      ].map(([label, value, help]) => (
        <article key={String(label)} className="evidence-summary-card" data-status={String(label).toLowerCase()}>
          <span>{label}</span>
          <strong>{value}</strong>
          <p>{help}</p>
        </article>
      ))}
      <article className="evidence-summary-card blocker">
        <span>최종 blocker</span>
        <strong>NO-GO 유지</strong>
        <p>{finalBlocker}</p>
      </article>
    </section>
  );
}

function GuideDecisionManual() {
  return (
    <section className="guide-manual-grid" aria-label="사용 가이드 핵심 판정 기준">
      {[
        ['ts_imb', 'RULE baseline', '강화학습 모델이 아니라 시계열 불균형 규칙 기준선입니다.'],
        ['23bp', '비용 가정', '기본 왕복 비용이며 낮춰 잡지 않습니다.'],
        ['API_UNAVAILABLE', '안전 API lock', '장애가 아니라 실거래·주문·계좌·수익 경로를 열지 않는 안전 잠금입니다.'],
        ['NO-GO', '연구 전용 판정', 'OOS/비용/낙폭/통제 증거가 부족하면 실험은 연구 증거 검토로만 남습니다.'],
        ['000250', '문자열 종목 코드', '선행 0은 숫자로 변환하지 않고 그대로 보존합니다.'],
        ['금지 주장', 'readiness 차단', 'live/broker/order/account/paper/model-build/profit 준비·수익성 주장은 표시하지 않습니다.'],
      ].map(([term, label, body]) => (
        <article key={term}>
          <span>{term}</span>
          <strong>{label}</strong>
          <p>{body}</p>
        </article>
      ))}
    </section>
  );
}
function SafetyLockPanel({ orderedLocks }: { orderedLocks: readonly (readonly [string, StatusLock])[] }) {
  return (
    <article className="panel lock-panel">
      <div className="panel-heading">
        <p className="eyebrow">B · 안전 잠금</p>
        <h2>거래·수익 경로는 모두 꺼짐</h2>
      </div>
      <div className="lock-head" aria-hidden="true">
        <span>경로</span>
        <span>잠금 상태</span>
        <span>상세</span>
      </div>
      <div className="lock-list">
        {orderedLocks.map(([key, lock]) => (
          <div className="lock-row" data-tone={statusTone(lock.status)} key={key} title={lock.reason ?? lock.label}>
            <span>{statusLabel(lock.status)}</span>
            <strong>{`${LOCK_COPY[key] ?? key} 꺼짐`}</strong>
            <small>{lock.label}</small>
          </div>
        ))}
      </div>
    </article>
  );
}

function SetupPanel({
  status,
  selectedExperimentId,
  symbolInput,
  jobEnabled,
  onExperimentChange,
  onSymbolChange,
  onRecordIntent,
}: {
  status: StatusPayload;
  selectedExperimentId: string;
  symbolInput: string;
  jobEnabled: boolean;
  onExperimentChange: (id: string) => void;
  onSymbolChange: (symbols: string) => void;
  onRecordIntent: () => void;
}) {
  const selectedExperiment = EXPERIMENT_PRESETS.find((preset) => preset.id === selectedExperimentId) ?? EXPERIMENT_PRESETS[0];
  return (
    <article className="panel setup-panel">
      <div className="panel-heading">
        <p className="eyebrow">A · 연구 설정</p>
        <h2>실험 선택과 안전 세팅</h2>
      </div>
      <label htmlFor="experiment-preset">모델/실험 선택</label>
      <select
        id="experiment-preset"
        value={selectedExperimentId}
        onChange={(event) => onExperimentChange(event.target.value)}
        aria-label="연구 모델 또는 실험 선택"
        title="실행 버튼이 아니라 연구 의도와 비교 기준을 고르는 선택입니다."
      >
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
        <input
          id="symbol-input"
          value={symbolInput}
          onChange={(event) => onSymbolChange(event.target.value)}
          aria-label="종목 코드 문자열 입력"
          title="쉼표로 구분하며 000250처럼 선행 0을 유지합니다."
        />
        <small>쉼표로 구분합니다. 선행 0은 문자열로 유지합니다.</small>
      </div>
      <div className="setup-safe-explainer" aria-label="실험 설정 안전 설명">
        <span>API_UNAVAILABLE = 안전 API lock</span>
        <strong>설정은 연구 의도 기록만 바꾸며 실행·주문·브로커 경로를 열지 않습니다.</strong>
        <p>선택값: {selectedExperiment.nameKo} · 종목 {symbolInput} · 비용 {status.cost_assumption_bps}bp · 기준선 ts_imb RULE baseline</p>
      </div>
      <div className="setting-pair">
        <div><span>비용 가정</span><strong>{status.cost_assumption_bps}bp</strong></div>
        <div><span>비교 기준</span><strong>ts_imb RULE baseline</strong></div>
      </div>
      <div className="control-row">
        <button
          type="button"
          onClick={onRecordIntent}
          disabled={!jobEnabled}
          aria-label="선택한 연구 의도를 안전 큐에 기록"
          title="허용된 workflow만 연구 의도로 기록하며 실제 학습·주문은 실행하지 않습니다."
        >
          선택한 연구 의도 기록
        </button>
        <button
          type="button"
          disabled
          aria-label="실제 학습 실행은 안전 잠금"
          title="이 대시보드는 연구 증거 검토 전용이므로 실제 학습 실행 버튼을 열지 않습니다."
        >
          실제 학습 실행 잠금
        </button>
      </div>
      <p className="danger-note">이 버튼은 연구 의도만 기록하며 주문·브로커·수익 경로를 열지 않습니다.</p>
    </article>
  );
}

function WorkflowPanel({ workflow, evidence, processProgress, artifactsByStage }: {
  workflow: WorkflowPayload;
  evidence: EvidencePayload;
  processProgress: number;
  artifactsByStage: Map<string, EvidenceArtifact>;
}) {
  return (
    <article className="panel workflow-panel" id="section-2">
      <div className="panel-heading with-progress">
        <div>
          <p className="eyebrow">C · D0-D9 evidence workflow</p>
          <h2>D0-D9 증거 경로</h2>
        </div>
        <strong>{processProgress}%</strong>
      </div>
      <div className="progress-meter" aria-label={`D0-D9 연구 검토 가능 단계 비율 ${processProgress}%`}><span style={{ width: `${Math.max(processProgress, 3)}%` }} /></div>
      <div className="workflow-legend" aria-label="D0-D9 상태 범례">
        <span data-tone="success">통과/검토 가능</span>
        <span data-tone="warn">점검 필요</span>
        <span data-tone="danger">누락/NO-GO</span>
        <span data-tone="lock">실거래 금지</span>
      </div>
      <div className="workflow-nodes">
        {workflow.process_map.map((stage, index) => {
          const artifact = artifactsByStage.get(stage.step);
          const artifactHash = artifact?.hash ?? 'hash 없음';
          const artifactFreshness = artifact ? `${statusLabel(artifact.freshness)} / ${statusLabel(artifact.schema_status)}` : '증거 없음';
          const artifactBlocker = artifact?.blocker_reason ?? stage.blocker_reason ?? '차단 사유 없음';
          return (
            <article className="workflow-node" data-tone={statusTone(stage.status)} data-final={stage.step === 'D9'} key={stage.step} title={artifactBlocker}>
              <span>{stage.step}</span>
              <strong>{STAGE_COPY[stage.step] ?? stage.name}</strong>
              <small>{statusLabel(stage.status)}</small>
              {stage.artifact_refs?.[0] && <em>{stage.artifact_refs[0]}</em>}
              {index < workflow.process_map.length - 1 && <i aria-hidden="true" />}
              <b>{artifactHash}</b>
              <b>{artifactFreshness}</b>
            </article>
          );
        })}
      </div>
      <WorkflowGraph steps={workflow.process_map} />
      <p className="workflow-note">금지된 작업: {workflow.forbidden_work.join(' · ')}</p>
      <EvidenceSourceStrip evidence={evidence} />
    </article>
  );
}

export default function TradingCommandCenter() {
  const [statusState, setStatusState] = useState<ApiState<StatusPayload>>({ data: FALLBACK_STATUS, failedClosed: true });
  const [workflowState, setWorkflowState] = useState<ApiState<WorkflowPayload>>({ data: FALLBACK_WORKFLOW, failedClosed: true });
  const [auditState, setAuditState] = useState<ApiState<AuditPayload>>({ data: FALLBACK_AUDIT, failedClosed: true });
  const [evidenceState, setEvidenceState] = useState<ApiState<EvidencePayload>>({ data: FALLBACK_EVIDENCE, failedClosed: true });
  const [drilldownState, setDrilldownState] = useState<ApiState<DrilldownPayload>>({ data: FALLBACK_DRILLDOWN, failedClosed: true });
  const [jobMessage, setJobMessage] = useState('아직 이 화면에서 기록한 연구 의도가 없습니다.');
  const [selectedExperimentId, setSelectedExperimentId] = useState(EXPERIMENT_PRESETS[0].id);
  const [symbolInput, setSymbolInput] = useState('000250,005930,035420');
  const [activeView, setActiveView] = useState<DashboardViewId>('home');

  useEffect(() => {
    let active = true;
    loadCommandSummaries().then(([status, workflow, audit, evidence, drilldown]) => {
      if (!active) return;
      setStatusState(status);
      setWorkflowState(workflow);
      setAuditState(audit);
      setEvidenceState(evidence);
      setDrilldownState(drilldown);
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const applyUrlView = () => {
      const urlView = new URL(window.location.href).searchParams.get('view');
      setActiveView(isDashboardViewId(urlView) ? urlView : 'home');
    };

    applyUrlView();
    window.addEventListener('popstate', applyUrlView);
    return () => window.removeEventListener('popstate', applyUrlView);
  }, []);

  const status = statusState.data;
  const workflow = workflowState.data;
  const audit = auditState.data;
  const evidence = evidenceState.data;
  const drilldown = drilldownState.data;
  const selectedExperiment = EXPERIMENT_PRESETS.find((preset) => preset.id === selectedExperimentId) ?? EXPERIMENT_PRESETS[0];
  const selectedSymbols = splitSymbols(symbolInput);
  const cards = useMemo(() => {
    const byId = new Map(status.first_viewport.cards.map((card) => [card.id, card]));
    return REQUIRED_CARD_ORDER.map((id) => byId.get(id) ?? FALLBACK_STATUS.first_viewport.cards.find((card) => card.id === id)!);
  }, [status.first_viewport.cards]);
  const fetchBanner = statusState.failedClosed || workflowState.failedClosed || auditState.failedClosed || evidenceState.failedClosed || drilldownState.failedClosed
    ? '백엔드 요약 중 하나가 닫힘 우선(fail-closed)으로 표시되었습니다. API 미연결은 오류가 아니라 안전 잠금입니다.'
    : 'Flask 백엔드 상태·워크플로우·감사 요약을 불러왔습니다.';
  const canRecordResearchIntent = Boolean(status.controls?.research_intent_record_allowed);
  const allowedWorkflowLabel = status.queue_summary?.allowed_workflows?.join(', ') || status.controls?.allowed_workflows?.join(', ') || 'record_research_intent';
  const orderedLocks = STATUS_LOCK_ORDER
    .map((key) => [key, status.status_locks[key]] as const)
    .filter((entry): entry is readonly [string, StatusLock] => Boolean(entry[1]));
  const processProgress = Math.round((workflow.process_map.filter((stage) => stage.review_allowed ?? stage.allowed).length / Math.max(workflow.process_map.length, 1)) * 100);
  const artifactsByStage = useMemo(() => {
    const mapped = new Map<string, EvidenceArtifact>();
    for (const artifact of evidence.artifacts.length ? evidence.artifacts : FALLBACK_EVIDENCE.artifacts) {
      if (!mapped.has(artifact.source_stage)) mapped.set(artifact.source_stage, artifact);
    }
    return mapped;
  }, [evidence.artifacts]);

  function selectDashboardView(viewId: DashboardViewId): void {
    setActiveView(viewId);
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    if (viewId === 'home') url.searchParams.delete('view');
    else url.searchParams.set('view', viewId);
    window.history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`);
  }

  function focusDashboardTab(viewId: DashboardViewId): void {
    if (typeof window === 'undefined') return;
    window.setTimeout(() => document.getElementById(`dashboard-tab-${viewId}`)?.focus(), 0);
  }

  function selectDashboardViewByIndex(index: number): void {
    const next = DASHBOARD_VIEWS[(index + DASHBOARD_VIEWS.length) % DASHBOARD_VIEWS.length];
    selectDashboardView(next.id);
    focusDashboardTab(next.id);
  }

  function handleDashboardTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number): void {
    if (event.key === 'ArrowDown' || event.key === 'ArrowRight') {
      event.preventDefault();
      selectDashboardViewByIndex(index + 1);
    } else if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') {
      event.preventDefault();
      selectDashboardViewByIndex(index - 1);
    } else if (event.key === 'Home') {
      event.preventDefault();
      selectDashboardViewByIndex(0);
    } else if (event.key === 'End') {
      event.preventDefault();
      selectDashboardViewByIndex(DASHBOARD_VIEWS.length - 1);
    }
  }

  function showView(...viewIds: DashboardViewId[]): boolean {
    return activeView === 'home' || viewIds.includes(activeView);
  }
  const primaryAuditArtifact = evidence.artifacts[0] ?? FALLBACK_EVIDENCE.artifacts[0];

  async function refreshSummaries(): Promise<void> {
    const [nextStatus, nextWorkflow, nextAudit, nextEvidence, nextDrilldown] = await loadCommandSummaries();
    setStatusState(nextStatus);
    setWorkflowState(nextWorkflow);
    setAuditState(nextAudit);
    setEvidenceState(nextEvidence);
    setDrilldownState(nextDrilldown);
  }

  function koreanRejectReason(message: string): string {
    if (message.includes('path traversal')) return '경로 이동/절대 경로 요청은 차단됐습니다.';
    if (message.includes('symbols must be strings')) return '종목 코드는 선행 0 보존을 위해 문자열만 허용됩니다.';
    if (message.includes('unsafe research command token')) return '실거래·주문·계좌·수익 주장이나 준비 상태 표현은 연구 큐에서 차단됐습니다.';
    if (message.includes('not allowlisted')) return '허용된 연구 workflow가 아니어서 차단됐습니다.';
    return message || '알 수 없는 오류';
  }

  async function recordResearchIntent(): Promise<void> {
    if (!canRecordResearchIntent || !status.controls?.job_post_endpoint) {
      setJobMessage('연구 의도 기록 API가 안전 잠금 상태입니다. 실제 학습·주문 실행은 열지 않습니다.');
      return;
    }
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
      setJobMessage(`연구 의도 기록 거부: ${error instanceof Error ? koreanRejectReason(error.message) : '알 수 없는 오류'}`);
    }
  }

  return (
    <main className="pixel-dashboard" data-kronos-trading-command-center="true" data-active-view={activeView}>
      <aside className="side-rail" aria-label="Kronos 연구 대시보드 탐색">
        <div className="brand-mark">
          <span>K</span>
          <div>
            <strong>Kronos</strong>
            <small>research ops</small>
          </div>
        </div>
        <nav role="tablist" aria-label="대시보드 화면 탭" data-dashboard-view-tabs="true">
          {DASHBOARD_VIEWS.map((view, index) => (
            <button
              type="button"
              role="tab"
              id={`dashboard-tab-${view.id}`}
              aria-selected={activeView === view.id}
              aria-controls={view.panelId}
              data-active={activeView === view.id}
              data-view={view.id}
              tabIndex={activeView === view.id ? 0 : -1}
              onClick={() => selectDashboardView(view.id)}
              onKeyDown={(event) => handleDashboardTabKeyDown(event, index)}
              key={view.id}
            >
              <span>{String(index + 1).padStart(2, '0')}</span>
              <strong>{view.label}</strong>
              <small>{view.hint}</small>
            </button>
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
            <p className="lede">연구 전용 증거 검토 화면입니다. 실거래, 브로커, 주문, 계좌, 페이퍼, 모델 빌드, 수익 주장 경로는 열리지 않습니다.</p>
          </div>
          <div className="status-orb">
            <span>NO-GO</span>
            <small>{status.mode}</small>
          </div>
        </header>

        <section className="badge-strip" aria-label="연구 전용 안전 가드레일">
          {status.labels.map((label) => <span key={label}>{label}</span>)}
          <span>실거래 없음</span>
          <span>브로커 없음</span>
          <span>주문 없음</span>
          <span>수익 주장 없음</span>
        </section>

        <section
          className="dashboard-view-intro"
          id="dashboard-panel-home"
          role="tabpanel"
          aria-labelledby="dashboard-tab-home"
          data-dashboard-view-panel="home"
          hidden={activeView !== 'home'}
        >
          <strong>전체 연구 홈</strong>
          <span>첫 화면은 NO-GO 안전 상태, 연구 설정, 증거 경로, KPI, 6개 증거 차트를 한 번에 보는 개요입니다.</span>
        </section>
        {activeView === 'home' && <HomeDecisionPanel status={status} evidence={evidence} workflow={workflow} />}

        <section
          className="topology-grid dashboard-view-panel"
          id="dashboard-panel-setup"
          role="tabpanel"
          aria-labelledby="dashboard-tab-setup"
          data-dashboard-view-panel="setup"
          hidden={!showView('setup')}
        >
          {activeView === 'setup' && (
            <ViewPurposeCard
              eyebrow="Page 2 · setup"
              title="실험 설정은 실행 버튼이 아니라 연구 의도와 비교 기준을 고르는 화면입니다"
              body="API_UNAVAILABLE은 장애가 아니라 안전 잠금입니다. 선택값은 연구 의도 기록과 증거 비교 문맥에만 사용됩니다."
              checks={['NO-GO 유지', '23bp 비용 가정', 'ts_imb RULE baseline', '000250 문자열 보존']}
            />
          )}
          <SetupPanel
            status={status}
            selectedExperimentId={selectedExperimentId}
            symbolInput={symbolInput}
            jobEnabled={canRecordResearchIntent}
            onExperimentChange={setSelectedExperimentId}
            onSymbolChange={setSymbolInput}
            onRecordIntent={() => void recordResearchIntent()}
          />
          <WorkflowPanel workflow={workflow} evidence={evidence} processProgress={processProgress} artifactsByStage={artifactsByStage} />
          <SafetyLockPanel orderedLocks={orderedLocks} />
        </section>

        <section
          className="kpi-strip dashboard-view-panel"
          aria-label="백엔드 소유 핵심 지표 카드 6개"
          data-dashboard-view-panel="kpi"
          hidden={!showView('compare')}
        >
          {cards.map((card, index) => (
            <article className="kpi-card" data-tone={statusTone(card.status)} key={card.id} title={CARD_COPY[card.id]?.help ?? card.label}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <h3>{CARD_COPY[card.id]?.title ?? card.title}</h3>
              <strong>{compactCardValue(card)}</strong>
              <p>{CARD_COPY[card.id]?.help ?? card.label}</p>
              <small>{statusLabel(card.status)}</small>
            </article>
          ))}
        </section>

        <section
          className="analytics-grid dashboard-view-panel"
          id="dashboard-panel-compare"
          role="tabpanel"
          aria-labelledby="dashboard-tab-compare"
          data-dashboard-view-panel="compare"
          hidden={!showView('compare')}
        >
          {activeView === 'compare' && (
            <ViewPurposeCard
              eyebrow="Page 4 · comparison"
              title="결과 비교는 NO-GO 근거를 빠르게 찾는 화면입니다"
              body="각 차트는 검증된 backend-owned series가 있을 때만 값을 표시하며, 빈 상태는 누락·오래됨·형식 문제를 설명합니다."
              checks={['차트별 blocker', 'source run/hash', 'freshness/schema', '다음 증거 행동']}
            />
          )}
          <article className="panel chart-panel evidence-card">
            <div className="panel-heading">
              <p className="eyebrow">ECharts · evidence health</p>
              <h2>부족한 증거가 어디인지 한눈에 보기</h2>
            </div>
            <EvidenceDecisionNote evidence={evidence} title="증거 상태 판단" nextAction="missing/stale/malformed 원인을 먼저 해소" />
            <ResearchChart option={evidenceChartOption(evidence)} ariaLabel="증거 상태 ECharts 막대 차트" emptyState={chartEmptyState(evidence)} />
            <EvidenceSourceStrip evidence={evidence} />
          </article>

          <article className="panel chart-panel">
            <div className="panel-heading">
              <p className="eyebrow">ECharts · baseline vs candidate</p>
              <h2>23bp 후 기준선 대비 비교</h2>
            </div>
            <EvidenceDecisionNote evidence={evidence} stage="D1" title="기준선 비교 판단" nextAction="fresh ts_imb RULE 비교 artifact 확보" />
            <ResearchChart option={baselineChartOption(status, evidence)} ariaLabel="23bp 기준선 대비 ECharts 차트" emptyState={chartEmptyState(evidence, 'D1')} />
            <EvidenceSourceStrip evidence={evidence} stage="D1" />
          </article>

          <article className="panel chart-panel">
            <div className="panel-heading">
              <p className="eyebrow">ECharts · drawdown</p>
              <h2>낙폭 곡선 / 증거 없음</h2>
            </div>
            <EvidenceDecisionNote evidence={evidence} stage="D3" title="낙폭 판단" nextAction="D3 drawdown artifact 재생성" />
            <ResearchChart option={drawdownChartOption(evidence)} ariaLabel="낙폭 ECharts 라인 차트" emptyState={chartEmptyState(evidence, 'D3')} />
            <EvidenceSourceStrip evidence={evidence} stage="D3" />
          </article>
          <article className="panel chart-panel">
            <div className="panel-heading">
              <p className="eyebrow">ECharts · trade / turnover</p>
              <h2>거래 수·회전율 증거</h2>
            </div>
            <EvidenceDecisionNote evidence={evidence} stage="D4" title="거래 수·회전율 판단" nextAction="D4 trade_count/turnover artifact 확인" />
            <ResearchChart option={tradeTurnoverChartOption(status, evidence)} ariaLabel="거래 수와 회전율 ECharts 차트" emptyState={chartEmptyState(evidence, 'D4')} />
            <EvidenceSourceStrip evidence={evidence} stage="D4" />
          </article>

          <article className="panel chart-panel">
            <div className="panel-heading">
              <p className="eyebrow">ECharts · OOS / controls</p>
              <h2>OOS·음성 통제 매트릭스</h2>
            </div>
            <EvidenceDecisionNote evidence={evidence} stage="D5" title="OOS·음성 통제 판단" nextAction="D5/D6 control artifact 확보" />
            <ResearchChart option={controlsChartOption(workflow, evidence)} ariaLabel="OOS와 음성 통제 ECharts 히트맵" emptyState={chartEmptyState(evidence, 'D5')} />
            <EvidenceSourceStrip evidence={evidence} stage="D5" />
          </article>

          <article className="panel chart-panel">
            <div className="panel-heading">
              <p className="eyebrow">ECharts · artifact freshness</p>
              <h2>증거 신선도 타임라인</h2>
            </div>
            <EvidenceDecisionNote evidence={evidence} title="신선도 판단" nextAction="7일 이내 schema-valid artifact만 비교에 사용" />
            <ResearchChart option={freshnessChartOption(evidence)} ariaLabel="artifact freshness ECharts chart" emptyState={chartEmptyState(evidence)} />
            <EvidenceSourceStrip evidence={evidence} />
          </article>
        </section>

        <section
          className="evidence-table-section dashboard-view-panel"
          id="dashboard-panel-evidence"
          role="tabpanel"
          aria-labelledby="dashboard-tab-evidence"
          data-dashboard-view-panel="evidence"
          hidden={!showView('evidence')}
        >
          <ViewPurposeCard
            eyebrow="Page 5 · evidence audit"
            title="증거 감사는 테이블을 읽기 전에 건강 상태와 최종 차단 사유를 먼저 보여줍니다"
            body="manifest, run 비교, audit timeline, raw JSON preview는 hash-backed/path-safe 증거만 보여주는 읽기 전용 화면입니다."
            checks={['fresh/missing/malformed/stale 요약', '최종 NO-GO blocker', 'artifact lineage', 'path-safe preview']}
          />
          <EvidenceHealthSummary evidence={evidence} workflow={workflow} />
          <article className="panel table-panel">
            <div className="panel-heading">
              <p className="eyebrow">TanStack Table · evidence manifest</p>
              <h2>증거 manifest · hash/path/timestamp/freshness/schema/blocker</h2>
            </div>
            <ArtifactManifestTable artifacts={evidence.artifacts} />
          </article>
          <article className="panel table-panel">
            <div className="panel-heading">
              <p className="eyebrow">TanStack Table · run comparison</p>
              <h2>선택 산출물·비용·낙폭·거래 지표 비교</h2>
            </div>
            <RunComparisonTable status={status} evidence={evidence} />
          </article>

          <article className="panel table-panel">
            <div className="panel-heading">
              <p className="eyebrow">TanStack Table · audit timeline</p>
              <h2>감사 타임라인 / 연구 의도 기록</h2>
            </div>
            <AuditTimelineTable audit={audit} />
          </article>

          <article className="panel table-panel raw-json-panel">
            <div className="panel-heading">
              <p className="eyebrow">Raw JSON · drilldown tabs</p>
              <h2>manifest/run/audit/연구 의도 원본 드릴다운</h2>
            </div>
            <ArtifactDrilldowns drilldown={drilldown} />
          </article>
        </section>

        <section
          className="audit-and-guide dashboard-view-panel"
          id="dashboard-panel-queue"
          role="tabpanel"
          aria-labelledby="dashboard-tab-queue"
          data-dashboard-view-panel="queue"
          hidden={!showView('queue')}
        >
          <ViewPurposeCard
            eyebrow="Page 3 · research queue"
            title="연구 큐는 실행 큐가 아니라 recorded-only 감사 큐입니다"
            body="허용 workflow는 record_research_intent이며 active job count는 0이어야 합니다. 실거래·주문·브로커·모델 빌드는 차단됩니다."
            checks={['recorded-only', 'active count zero', 'config_hash/idempotency', 'blocked workflows']}
          />
          <IntentHistory
            audit={audit}
            evidence={evidence}
            status={status}
            fetchBanner={fetchBanner}
            jobMessage={jobMessage}
            allowedWorkflowLabel={allowedWorkflowLabel}
            primaryAuditArtifact={primaryAuditArtifact}
            drilldown={drilldown}
          />

        </section>

        <section
          className="audit-and-guide guide-only dashboard-view-panel"
          id="dashboard-panel-guide"
          role="tabpanel"
          aria-labelledby="dashboard-tab-guide"
          data-dashboard-view-panel="guide"
          hidden={!showView('guide')}
        >
          <ViewPurposeCard
            eyebrow="Page 6 · guide"
            title="사용 가이드는 연구자가 오해 없이 NO-GO와 안전 잠금을 해석하는 매뉴얼입니다"
            body="ts_imb는 RULE baseline이고, 23bp는 비용 가정이며, API_UNAVAILABLE은 안전 잠금입니다."
            checks={['NO-GO 정의', 'RESEARCH_ONLY', 'API lock', '금지 readiness 문구']}
          />
          <GuideDecisionManual />
          <article className="panel glossary-panel">
            <div className="panel-heading">
              <p className="eyebrow">사용 가이드</p>
              <h2>용어와 해석 기준</h2>
            </div>
            <div className="glossary-grid">
              {GLOSSARY.map(([term, explanation]) => (
                <div key={term} title={explanation}>
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
