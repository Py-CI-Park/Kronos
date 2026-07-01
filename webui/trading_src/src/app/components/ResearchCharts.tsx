'use client';

import { useEffect, useMemo, useRef } from 'react';
import * as echarts from 'echarts';
import type { EvidenceArtifact, EvidencePayload, StatusPayload, WorkflowPayload } from '../tradingTypes';
import { FALLBACK_EVIDENCE } from '../tradingApi';
import { evidenceScore, isRecord, statusLabel, statusTone, STAGE_COPY } from '../tradingFormat';

function isValidChartArtifact(artifact: EvidenceArtifact | undefined): artifact is EvidenceArtifact {
  return Boolean(artifact)
    && artifact?.series_source === 'BACKEND_OWNED'
    && artifact?.schema_status === 'VALID'
    && artifact?.status === 'FRESH'
    && typeof artifact?.hash === 'string'
    && artifact.hash.length >= 16
    && typeof artifact.timestamp === 'string'
    && typeof artifact.source_run_id === 'string'
    && typeof artifact.source_stage === 'string'
    && typeof artifact.row_count === 'number'
    && artifact.row_count > 0;
}

function artifactsForStage(evidence: EvidencePayload, stage?: string): EvidenceArtifact[] {
  const artifacts = evidence.artifacts.length ? evidence.artifacts : FALLBACK_EVIDENCE.artifacts;
  return stage ? artifacts.filter((artifact) => artifact.source_stage === stage) : artifacts;
}

export function chartEmptyState(evidence: EvidencePayload, stage?: string): string | null {
  const artifacts = artifactsForStage(evidence, stage);
  if (artifacts.some(isValidChartArtifact)) return null;
  const blocker = artifacts[0]?.blocker_reason ?? '검증된 백엔드 산출물이 없어 차트를 비워 둡니다.';
  const scope = stage ? `${stage} ` : '';
  return `${scope}검증된 series_source/hash/timestamp/schema/row_count 증거 없음 · ${blocker}`;
}

export function EvidenceDecisionNote({
  evidence,
  stage,
  title,
  nextAction,
}: {
  evidence: EvidencePayload;
  stage?: string;
  title: string;
  nextAction: string;
}) {
  const artifacts = artifactsForStage(evidence, stage);
  const primary = artifacts[0] ?? evidence.artifacts[0] ?? FALLBACK_EVIDENCE.artifacts[0];
  const valid = artifacts.some(isValidChartArtifact);
  return (
    <div className="chart-decision-note" data-chart-decision-card="true" data-status={valid ? 'fresh' : 'blocked'} title={primary.blocker_reason}>
      <span>{title}</span>
      <strong>{valid ? '검증된 증거 표시' : `${stage ? `${stage} ` : ''}${statusLabel(primary.status)} · NO-GO 근거`}</strong>
      <p>{valid ? `source ${primary.source_run_id} · hash ${primary.hash}` : primary.blocker_reason}</p>
      <small>{primary.source_stage} · {primary.series_source ?? 'BACKEND_OWNED'} · {statusLabel(primary.freshness)} / {statusLabel(primary.schema_status)} · rows {primary.row_count ?? '—'} · 다음 확인: {nextAction}</small>
    </div>
  );
}
export function ResearchChart({ option, ariaLabel, emptyState }: { option: echarts.EChartsOption; ariaLabel: string; emptyState?: string | null }) {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const stableOption = useMemo(() => option, [option]);

  useEffect(() => {
    if (!chartRef.current) return undefined;
    const chart = echarts.init(chartRef.current, undefined, { renderer: 'canvas' });
    chart.setOption(stableOption);
    const handleResize = () => chart.resize();
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      chart.dispose();
    };
  }, [stableOption]);

  return (
    <div className="chart-shell" data-chart-source-gated="true">
      <div ref={chartRef} className="echart-box" data-echarts-chart="true" aria-label={ariaLabel} role="img" />
      {emptyState && <p className="evidence-empty-state" data-evidence-empty-state="true">{emptyState}</p>}
    </div>
  );
}

export function evidenceChartOption(evidence: EvidencePayload): echarts.EChartsOption {
  const artifacts = evidence.artifacts.length ? evidence.artifacts : FALLBACK_EVIDENCE.artifacts;
  return {
    backgroundColor: 'transparent',
    grid: { left: 22, right: 14, top: 18, bottom: 34, containLabel: true },
    xAxis: { type: 'value', max: 100, axisLabel: { color: '#91a8ba' }, splitLine: { lineStyle: { color: 'rgba(145,168,186,0.12)' } } },
    yAxis: { type: 'category', data: artifacts.map((artifact) => artifact.source_stage || artifact.kind), axisLabel: { color: '#d8e9f7' } },
    series: [{
      name: '검증된 row_count 기반 증거',
      type: 'bar',
      data: artifacts.map((artifact) => ({
        value: isValidChartArtifact(artifact) ? Math.min(100, Math.max(1, artifact.row_count ?? 0) * 10) : 0,
        itemStyle: { color: isValidChartArtifact(artifact) ? '#22d3ee' : '#334155' },
      })),
      label: { show: true, position: 'right', color: '#eaf4ff', formatter: ({ dataIndex }) => {
        const artifact = artifacts[Number(dataIndex)] as EvidenceArtifact | undefined;
        if (isValidChartArtifact(artifact)) return `row ${artifact.row_count}`;
        return '';
      } },
    }],
    tooltip: { trigger: 'axis', formatter: '검증된 backend-owned artifact row_count만 차트 값으로 사용합니다.' },
  };
}

export function baselineChartOption(status: StatusPayload, evidence: EvidencePayload): echarts.EChartsOption {
  const baselineArtifact = evidence.artifacts.find((artifact) => artifact.source_stage === 'D1');
  const validBaseline = isValidChartArtifact(baselineArtifact);
  const baselineCard = status.first_viewport.cards.find((card) => card.id === 'cost_baseline_delta_23bp');
  const baselineStatus = baselineArtifact?.status ?? baselineCard?.status ?? 'NO_GO_MISSING_FRESH_COMPARISON';
  return {
    backgroundColor: 'transparent',
    legend: { top: 0, textStyle: { color: '#cce6f8' } },
    grid: { left: 30, right: 18, top: 38, bottom: 34, containLabel: true },
    xAxis: { type: 'category', data: ['ts_imb RULE', '후보 비교', '23bp 비용'], axisLabel: { color: '#d8e9f7' } },
    yAxis: { type: 'value', max: 100, axisLabel: { color: '#91a8ba' }, splitLine: { lineStyle: { color: 'rgba(145,168,186,0.12)' } } },
    series: [{
      name: '백엔드 검증 series',
      type: 'bar',
      data: [
        { value: validBaseline ? Math.min(100, (baselineArtifact.row_count ?? 0) * 10) : 0, itemStyle: { color: validBaseline ? '#38bdf8' : '#334155' } },
        { value: 0, itemStyle: { color: '#fb7185' } },
        { value: status.cost_assumption_bps, itemStyle: { color: '#a78bfa' } },
      ],
      label: { show: true, color: '#eaf4ff', position: 'top', formatter: ({ dataIndex }) => (dataIndex === 0 ? statusLabel(baselineStatus) : dataIndex === 1 ? '신선한 비교 없음' : `${status.cost_assumption_bps}bp`) },
    }],
    tooltip: { trigger: 'axis', formatter: 'ts_imb는 RULE baseline이며, 후보 비교는 검증된 백엔드 series가 있을 때만 표시합니다.' },
  };
}

export function drawdownChartOption(evidence: EvidencePayload): echarts.EChartsOption {
  const drawdownArtifact = evidence.artifacts.find((artifact) => artifact.kind === 'drawdown' || artifact.source_stage === 'D3');
  const validDrawdown = isValidChartArtifact(drawdownArtifact);
  const stageLabels = ['D0', 'D1', 'D2', 'D3', 'D4', 'D5'];
  const drawdownScore = validDrawdown ? Math.min(100, Math.max(1, drawdownArtifact.row_count ?? 0) * 10) : null;
  return {
    backgroundColor: 'transparent',
    legend: { top: 0, textStyle: { color: '#cce6f8' } },
    grid: { left: 36, right: 16, top: 42, bottom: 30 },
    xAxis: { type: 'category', data: stageLabels, axisLabel: { color: '#91a8ba' } },
    yAxis: { type: 'value', max: 100, axisLabel: { color: '#91a8ba' }, splitLine: { lineStyle: { color: 'rgba(145,168,186,0.12)' } } },
    series: [
      {
        name: `backend-owned D3 artifact ${statusLabel(drawdownArtifact?.status ?? 'MISSING')}`,
        type: 'scatter',
        symbolSize: validDrawdown ? 14 : 8,
        data: stageLabels.map((stage) => (stage === 'D3' ? drawdownScore : null)),
        itemStyle: { color: validDrawdown ? '#22d3ee' : '#64748b' },
        label: {
          show: true,
          color: '#eaf4ff',
          position: 'top',
          formatter: ({ value }) => (typeof value === 'number' && validDrawdown ? `row ${drawdownArtifact.row_count}` : ''),
        },
      },
    ],
    tooltip: { trigger: 'axis', formatter: '낙폭 차트는 검증된 backend-owned D3 artifact row_count만 표시하며 가짜 equity 곡선을 만들지 않습니다.' },
  };
}

export function tradeTurnoverChartOption(status: StatusPayload, evidence: EvidencePayload): echarts.EChartsOption {
  const tradeArtifact = evidence.artifacts.find((artifact) => artifact.source_stage === 'D4');
  const validTrade = isValidChartArtifact(tradeArtifact);
  const tradeCard = status.first_viewport.cards.find((card) => card.id === 'trade_count_turnover');
  const value = isRecord(tradeCard?.value) ? tradeCard.value : {};
  const tradeCount = validTrade ? tradeArtifact.row_count ?? 0 : 0;
  const turnover = validTrade && typeof value.turnover === 'number' ? value.turnover : 0;
  return {
    backgroundColor: 'transparent',
    legend: { top: 0, textStyle: { color: '#cce6f8' } },
    grid: { left: 38, right: 20, top: 40, bottom: 34, containLabel: true },
    xAxis: { type: 'category', data: ['거래 수', '회전율 증거', '비용 가정'], axisLabel: { color: '#d8e9f7' } },
    yAxis: { type: 'value', axisLabel: { color: '#91a8ba' }, splitLine: { lineStyle: { color: 'rgba(145,168,186,0.12)' } } },
    series: [
      {
        name: '백엔드 검증 증거값',
        type: 'bar',
        data: [
          { value: tradeCount, itemStyle: { color: validTrade ? '#22d3ee' : '#334155' } },
          { value: turnover, itemStyle: { color: turnover > 0 ? '#fbbf24' : '#334155' } },
          { value: status.cost_assumption_bps, itemStyle: { color: '#a78bfa' } },
        ],
        label: { show: true, position: 'top', color: '#eaf4ff', formatter: ({ value }) => String(value ?? '—') },
      },
    ],
    tooltip: { trigger: 'axis', formatter: '거래 수·회전율은 검증된 연구 증거용이며 실행 신호가 아닙니다.' },
  };
}

export function controlsChartOption(workflow: WorkflowPayload, evidence: EvidencePayload): echarts.EChartsOption {
  const controlStages = workflow.process_map.filter((stage) => ['D5', 'D6'].includes(stage.step));
  return {
    backgroundColor: 'transparent',
    grid: { left: 88, right: 12, top: 24, bottom: 26 },
    xAxis: { type: 'category', data: ['백엔드 증거 상태'], axisLabel: { color: '#91a8ba' } },
    yAxis: { type: 'category', data: controlStages.map((stage) => STAGE_COPY[stage.step] ?? stage.name), axisLabel: { color: '#d8e9f7' } },
    visualMap: { min: 0, max: 100, show: false, inRange: { color: ['#10253a', '#fbbf24', '#fb7185'] } },
    series: [{
      type: 'heatmap',
      data: controlStages.map((stage, index) => {
        const artifact = evidence.artifacts.find((item) => item.source_stage === stage.step);
        return [0, index, isValidChartArtifact(artifact) ? evidenceScore('FRESH') : 0];
      }),
      label: { show: true, color: '#eaf4ff', formatter: ({ value }) => {
        if (!Array.isArray(value)) return '차단';
        const stage = controlStages[Number(value[1])];
        const artifact = evidence.artifacts.find((item) => item.source_stage === stage?.step) as EvidenceArtifact | undefined;
        const fallbackStatus = artifact ? String((artifact as { status?: string }).status ?? stage?.status ?? 'MISSING') : stage?.status ?? 'MISSING';
        return isValidChartArtifact(artifact) ? '검증됨' : statusLabel(fallbackStatus);
      } },
    }],
    tooltip: { formatter: 'OOS/음성 통제는 검증된 backend-owned artifact가 있을 때만 통과 값으로 표시됩니다.' },
  };
}

export function freshnessChartOption(evidence: EvidencePayload): echarts.EChartsOption {
  const artifacts = evidence.artifacts.length ? evidence.artifacts : FALLBACK_EVIDENCE.artifacts;
  return {
    backgroundColor: 'transparent',
    grid: { left: 30, right: 12, top: 20, bottom: 60, containLabel: true },
    xAxis: { type: 'category', data: artifacts.map((artifact) => artifact.source_stage), axisLabel: { color: '#d8e9f7' } },
    yAxis: { type: 'value', max: 100, axisLabel: { color: '#91a8ba' }, splitLine: { lineStyle: { color: 'rgba(145,168,186,0.12)' } } },
    series: [{
      name: 'freshness',
      type: 'bar',
      data: artifacts.map((artifact) => ({ value: isValidChartArtifact(artifact) ? evidenceScore('FRESH') : 0, itemStyle: { color: isValidChartArtifact(artifact) ? '#22d3ee' : '#334155' } })),
      label: { show: true, position: 'top', color: '#eaf4ff', formatter: ({ dataIndex }) => (isValidChartArtifact(artifacts[Number(dataIndex)]) ? statusLabel(artifacts[Number(dataIndex)]?.freshness ?? 'MISSING') : '') },
    }],
    tooltip: { trigger: 'axis', formatter: 'artifact freshness · FRESH는 hash/timestamp/schema/row_count가 모두 검증될 때만 표시됩니다.' },
  };
}

export function EvidenceSourceStrip({ evidence, stage }: { evidence: EvidencePayload; stage?: string }) {
  const matchedArtifacts = artifactsForStage(evidence, stage);
  const primary = matchedArtifacts[0] ?? evidence.artifacts[0] ?? FALLBACK_EVIDENCE.artifacts[0];
  return (
    <div className="source-strip" title={primary.blocker_reason}>
      <span>run {primary.source_run_id}</span>
      <span>{primary.source_stage}</span>
      <span>{primary.series_source ?? 'BACKEND_OWNED'}</span>
      <span>hash {primary.hash ?? '없음'}</span>
      <span>{statusLabel(primary.freshness)} / {statusLabel(primary.schema_status)}</span>
      <span>rows {primary.row_count ?? '—'}</span>
      <span>{primary.blocker_reason}</span>
    </div>
  );
}
