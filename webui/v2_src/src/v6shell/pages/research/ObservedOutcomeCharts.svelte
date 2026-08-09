<script lang="ts">
  import EChartsRenderer from '../../../charts/EChartsRenderer.svelte';
  import AccessibleBarChart from '../../components/visualization/AccessibleBarChart.svelte';
  import type { ObservedOutcome, ObservedOutcomeSeries } from '../../api/researchApi';
  import { compactOutcomeLabel } from './observedOutcomeChartModel';

  interface Props { readonly outcome: ObservedOutcome; }
  let { outcome }: Props = $props();

  const labels = $derived(outcome.series.map((row) => row.label));
  const netPnl = (row: ObservedOutcomeSeries): number | null => row.total_net_pnl_krw ?? row.net_pnl_krw ?? null;
  const hasMoney = $derived(outcome.series.some((row) => netPnl(row) !== null || row.total_cost_krw !== undefined));
  const hasReward = $derived(outcome.series.some((row) => row.mean_reward !== undefined || row.cumulative_reward !== undefined));
  const activityItems = $derived(outcome.series.flatMap((row) => [
    ...(row.date_count === undefined ? [] : [{ label: `${row.label} · 거래일`, value: row.date_count, tone: 'accent' as const }]),
    ...(row.filled_slots === undefined ? [] : [{ label: `${row.label} · 체결 슬롯`, value: row.filled_slots, tone: 'warning' as const }]),
  ]));
  const moneyOption = $derived({
    animationDuration: 240,
    tooltip: { trigger: 'axis', confine: true, axisPointer: { type: 'shadow' } },
    legend: { top: 0 },
    grid: { left: 82, right: 30, top: 54, bottom: 94, containLabel: true },
    xAxis: { type: 'category', data: labels, axisLabel: { hideOverlap: true, interval: 0, rotate: labels.length > 7 ? 38 : 0, fontSize: 10, formatter: compactOutcomeLabel } },
    yAxis: { type: 'value', name: '원 (KRW)' },
    dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 18, height: 18 }],
    series: [
      { name: '비용 후 손익', type: 'bar', data: outcome.series.map(netPnl), emphasis: { focus: 'series' } },
      { name: '총 비용', type: 'bar', data: outcome.series.map((row) => row.total_cost_krw ?? null), emphasis: { focus: 'series' } },
    ],
  });
  const rewardOption = $derived({
    animationDuration: 240,
    tooltip: { trigger: 'axis', confine: true, axisPointer: { type: 'shadow' } },
    legend: { top: 0 },
    grid: { left: 72, right: 30, top: 54, bottom: 94, containLabel: true },
    xAxis: { type: 'category', data: labels, axisLabel: { hideOverlap: true, interval: 0, rotate: labels.length > 7 ? 38 : 0, fontSize: 10, formatter: compactOutcomeLabel } },
    yAxis: { type: 'value', name: '관측 reward' },
    dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 18, height: 18 }],
    series: [
      { name: '평균 reward', type: 'bar', data: outcome.series.map((row) => row.mean_reward ?? null) },
      { name: '누적 reward', type: 'bar', data: outcome.series.map((row) => row.cumulative_reward ?? null) },
    ],
  });
  const won = (value: number | null): string => value === null ? 'MISSING' : `${new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 0 }).format(value)}원`;
</script>

<div class="outcome" data-observed-outcome>
  <header>
    <div><span>{outcome.scope}</span><h3>{outcome.headline}</h3></div>
    <code>{outcome.source_file}</code>
  </header>
  {#if outcome.reasons.length}
    <ul aria-label="관측된 판정 이유">{#each outcome.reasons as reason}<li>{reason}</li>{/each}</ul>
  {/if}
  {#if outcome.series.length}
    <div class="charts">
      {#if hasMoney}<section><h4>비용 후 손익 · 비용</h4><p>직접 summary에 기록된 원화 숫자만 표시합니다.</p><EChartsRenderer option={moneyOption} height="400px" caption="정책 또는 split별 관측 손익과 비용" /></section>{/if}
      {#if hasReward}<section><h4>학습 reward</h4><p>reward는 경제 수익률과 동일하지 않으므로 별도 축으로 분리합니다.</p><EChartsRenderer option={rewardOption} height="400px" caption="정책 또는 split별 관측 reward" /></section>{/if}
      {#if activityItems.length}<section><AccessibleBarChart title="관측 범위와 행동량" ariaLabel="정책 또는 split별 거래일과 체결 슬롯 수" summary="직접 summary의 date_count와 filled_slots만 사용합니다." items={activityItems} valueHeader="count" /></section>{/if}
    </div>
    <div class="table-wrap"><table><thead><tr><th>정책 / split</th><th>비용 후 손익</th><th>총 비용</th><th>평균 reward</th><th>누적 reward</th><th>거래일</th><th>체결 슬롯</th></tr></thead><tbody>{#each outcome.series as row}<tr><th>{row.label}</th><td>{won(netPnl(row))}</td><td>{won(row.total_cost_krw ?? null)}</td><td>{row.mean_reward ?? 'MISSING'}</td><td>{row.cumulative_reward ?? 'MISSING'}</td><td>{row.date_count ?? 'MISSING'}</td><td>{row.filled_slots ?? 'MISSING'}</td></tr>{/each}</tbody></table></div>
  {:else}
    <div class="missing"><strong>STRUCTURED OUTCOME MISSING</strong><p>직접 summary에 시각화 가능한 정책·split 숫자가 없습니다. 파일 크기나 이름으로 성과를 추정하지 않습니다.</p></div>
  {/if}
</div>

<style>
  .outcome{display:flex;min-width:0;flex-direction:column;gap:12px}.outcome>header{display:flex;align-items:start;justify-content:space-between;gap:14px;border-bottom:1px solid var(--border);padding-bottom:12px}.outcome>header div{min-width:0}.outcome>header span{color:var(--accent);font:900 .56rem var(--font-mono)}h3{margin:4px 0 0;color:var(--fg-strong);font-size:.94rem;overflow-wrap:anywhere}.outcome>header code{max-width:45%;color:var(--muted);font:.62rem var(--font-mono);overflow-wrap:anywhere}ul{display:grid;gap:5px;margin:0;padding:0;list-style:none}li{border-left:3px solid var(--danger);padding:6px 9px;background:var(--surface-sunken);color:var(--fg);font-size:.68rem}.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:12px}.charts section{min-width:0;border:1px solid var(--border);border-radius:10px;padding:14px;background:var(--surface-sunken)}h4{margin:0;color:var(--fg-strong);font-size:.82rem}.charts p{margin:4px 0 9px;color:var(--muted);font-size:.64rem}.table-wrap{max-width:100%;overflow:auto;border:1px solid var(--border);border-radius:9px}table{width:100%;min-width:820px;border-collapse:collapse;font-size:.65rem}th,td{padding:8px;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap}thead th{background:var(--surface-raised);color:var(--muted)}tbody th{color:var(--fg-strong)}td{color:var(--fg)}.missing{border:1px dashed var(--warn);border-radius:10px;padding:16px;background:var(--surface-sunken)}.missing strong{color:var(--warn);font:.66rem var(--font-mono)}.missing p{margin:6px 0 0;color:var(--muted);font-size:.7rem}@media(max-width:620px){.outcome>header{flex-direction:column}.outcome>header code{max-width:100%}}
</style>
