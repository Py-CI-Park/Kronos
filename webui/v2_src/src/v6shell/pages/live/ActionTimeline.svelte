<script lang="ts">
  import EChartsRenderer from '../../../charts/EChartsRenderer.svelte';
  import AccessibleBarChart from '../../components/visualization/AccessibleBarChart.svelte';
  import type { TelemetryPoint } from '../../api/telemetryApi';
  import { actionDistribution, buildActionHourBuckets, buildActionTimelineRows, recordedActionPoints } from './actionTimelineModel';

  interface Props { readonly points: readonly TelemetryPoint[]; }
  let { points }: Props = $props();

  const distribution = $derived(actionDistribution(points));
  const rows = $derived(buildActionTimelineRows(points));
  const timelineEvents = $derived(recordedActionPoints(points));
  const recent = $derived(timelineEvents.slice(-20).reverse());
  const hourBuckets = $derived(buildActionHourBuckets(points));
  const actionNames = $derived(distribution.map((item) => item.label));
  const chartRows = $derived(rows.map((row) => {
    const time = typeof row[0] === 'string' ? new Date(row[0]).toLocaleTimeString('ko-KR', { hour12: false }) : `step ${row[0]}`;
    return [`${time} · ${row[2]}`, actionNames.indexOf(row[1]), row[2], row[3]];
  }));
  const barItems = $derived(distribution.map((item) => ({ label: item.label, value: item.count, tone: item.label === 'SELL' || item.label === 'EXIT' ? 'danger' as const : 'accent' as const })));
  const option = $derived({
    animationDuration: 220,
    tooltip: { trigger: 'item', confine: true },
    grid: { left: 70, right: 26, top: 24, bottom: 84, containLabel: true },
    xAxis: { type: 'category', name: '기록 시각 / step', axisLabel: { hideOverlap: true, rotate: 24 }, nameGap: 52 },
    yAxis: { type: 'category', data: actionNames, name: '행동' },
    dataZoom: [{ type: 'inside', xAxisIndex: 0 }, { type: 'slider', xAxisIndex: 0, bottom: 18, height: 18 }],
    series: [{ name: '관측 행동', type: 'scatter', symbolSize: 14, data: chartRows }],
  });
  const activityOption = $derived({
    animationDuration: 240,
    tooltip: { trigger: 'axis', confine: true, axisPointer: { type: 'shadow' } },
    legend: { type: 'scroll', top: 0, left: 8, right: 8 },
    grid: { left: 62, right: 28, top: 58, bottom: 102, containLabel: true },
    xAxis: { type: 'category', data: hourBuckets.map((bucket) => bucket.label), name: '한국 시간대', nameGap: 52, axisLabel: { hideOverlap: true, rotate: 24, interval: 'auto' } },
    yAxis: { type: 'value', name: '행동 event' },
    dataZoom: [{ type: 'inside', xAxisIndex: 0 }, { type: 'slider', xAxisIndex: 0, bottom: 18, height: 18 }],
    series: actionNames.map((action) => ({
      name: action, type: 'bar', stack: 'actions', emphasis: { focus: 'series' },
      data: hourBuckets.map((bucket) => bucket.counts[action] ?? 0),
    })),
  });
</script>

<div class="action-lab" data-action-timeline>
  <section class="timeline">
    <header><div><h3>시간대별 행동 타임라인</h3><p>표본 event의 기록 시각과 step을 그대로 사용합니다. 빈 구간은 보간하지 않습니다.</p></div><span>{rows.length} events</span></header>
    {#if rows.length}
      <EChartsRenderer {option} height="360px" caption="기록 시각에 따른 강화학습 행동 타임라인" />
      <details class="timeline-data">
        <summary>전체 행동 event 표 ({timelineEvents.length}건)</summary>
        <div class="table-scroll">
          <table>
            <thead><tr><th scope="col">기록 시각</th><th scope="col">step</th><th scope="col">행동</th><th scope="col">phase</th></tr></thead>
            <tbody>{#each timelineEvents as event}<tr><td>{event.decision_timestamp ?? event.timestamp}</td><td>{event.step}</td><td>{event.action_name.toUpperCase()}</td><td>{event.phase}</td></tr>{/each}</tbody>
          </table>
        </div>
      </details>
    {:else}<p class="empty">표시할 행동 event가 없습니다.</p>{/if}
  </section>
  <section class="distribution">
    <h3>행동 분포</h3><p>표시된 표본 안에서의 횟수이며 정책 전체 확률이 아닙니다.</p>
    <AccessibleBarChart title="표본 행동 분포" ariaLabel="표시된 텔레메트리 표본의 행동별 횟수" summary="실제 event에 기록된 행동만 집계합니다." items={barItems} valueHeader="event" />
    <div class="shares">{#each distribution as item}<span><b>{item.label}</b>{item.count}회 · {item.sharePct}%</span>{/each}</div>
  </section>
  <section class="activity">
    <header><div><h3>시간대별 행동 빈도</h3><p>유효한 event 시각을 한국 시간의 1시간 구간으로 묶습니다. 기록이 없는 구간은 학습 없음으로 추정하지 않습니다.</p></div><span>{hourBuckets.length} buckets</span></header>
    {#if hourBuckets.length}
      <EChartsRenderer option={activityOption} height="420px" caption="한국 시간대별 강화학습 행동 event 누적 막대" />
    {:else}<p class="empty">시간대 집계에 사용할 유효한 timestamp가 없습니다.</p>{/if}
  </section>
  <section class="recent">
    <h3>최근 20개 결정</h3><p>가장 최신 기록부터 표시합니다. 카드 색은 행동 종류를 구분하며 수익성을 뜻하지 않습니다.</p>
    <ol>{#each recent as action}<li data-action={action.action_name.toUpperCase()}><i></i><div><b>{action.action_name.toUpperCase()}</b><span>step {action.step} · {action.phase}</span><time>{action.decision_timestamp ?? action.timestamp}</time>{#if action.reward_observed_at}<small>보상 관측 {action.reward_observed_at}</small>{/if}</div></li>{:else}<li class="empty">표시할 행동 event가 없습니다.</li>{/each}</ol>
  </section>
</div>

<style>
  .action-lab{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(260px,.75fr);gap:12px}.action-lab section{min-width:0;border:1px solid var(--border);border-radius:10px;padding:14px;background:var(--surface-sunken)}.timeline{grid-column:1/2}.distribution{grid-column:2/3}.activity,.recent{grid-column:1/-1}header{display:flex;align-items:start;justify-content:space-between;gap:12px}h3{margin:0;color:var(--fg-strong);font-size:.9rem}p{margin:4px 0 10px;color:var(--muted);font-size:.68rem;line-height:1.55}header>span{white-space:nowrap;border:1px solid var(--border-strong);border-radius:999px;padding:4px 8px;color:var(--accent);font:.62rem var(--font-mono)}.timeline-data{margin-top:10px;border-top:1px solid var(--border);padding-top:10px}.timeline-data summary{cursor:pointer;color:var(--accent-strong);font-size:.68rem;font-weight:800}.table-scroll{max-height:280px;margin-top:8px;overflow:auto;border:1px solid var(--border);border-radius:8px}table{width:100%;border-collapse:collapse;font-size:.62rem}th,td{padding:7px 8px;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap}th{position:sticky;top:0;background:var(--surface-raised);color:var(--fg-strong)}td{color:var(--muted)}.shares{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.shares span{border:1px solid var(--border);border-radius:999px;padding:5px 8px;color:var(--muted);font-size:.62rem}.shares b{margin-right:5px;color:var(--fg-strong)}ol{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:8px;margin:10px 0 0;padding:0;list-style:none}li{display:grid;grid-template-columns:10px 1fr;gap:8px;border:1px solid var(--border);border-radius:8px;padding:11px;background:var(--surface-raised)}li i{width:8px;height:8px;margin-top:4px;border-radius:50%;background:var(--accent)}li[data-action=SELL] i,li[data-action=EXIT] i{background:var(--danger)}li div{display:flex;min-width:0;flex-direction:column;gap:3px}li b{color:var(--fg-strong);font-size:.74rem}li span,li time,li small{color:var(--muted);font-size:.62rem;overflow-wrap:anywhere}.empty{color:var(--muted)}
  @media(max-width:960px){.action-lab{grid-template-columns:1fr}.timeline,.distribution,.activity,.recent{grid-column:auto}}
</style>
