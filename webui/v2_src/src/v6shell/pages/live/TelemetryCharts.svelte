<script lang="ts">
  import EChartsRenderer from '../../../charts/EChartsRenderer.svelte';
  import type { TelemetryPoint } from '../../api/telemetryApi';
  import { equityPresentation, rewardPresentation } from './telemetryMetricModel';

  interface Props {
    readonly points: readonly TelemetryPoint[];
  }

  let { points }: Props = $props();

  const rewardMetric = $derived(rewardPresentation(points));
  const equityMetric = $derived(equityPresentation(points));
  const lossRows = $derived(points.filter((point) => point.loss !== null).map((point) => [point.step, point.loss]));
  const explorationRows = $derived(points.filter((point) => point.exploration !== null).map((point) => [point.step, point.exploration]));

  const shared = { animationDuration: 250, tooltip: { trigger: 'axis', confine: true }, grid: { left: 62, right: 30, top: 42, bottom: 82, containLabel: true }, xAxis: { type: 'value', name: 'step', nameGap: 34, axisLabel: { hideOverlap: true } }, dataZoom: [{ type: 'inside', xAxisIndex: 0, filterMode: 'none' }, { type: 'slider', xAxisIndex: 0, bottom: 16, height: 18, filterMode: 'none' }] };
  const rewardOption = $derived({ ...shared, yAxis: { type: 'value', name: rewardMetric.axisLabel }, series: [{ name: '누적 보상', type: 'line', showSymbol: false, data: rewardMetric.rows, lineStyle: { width: 2 } }] });
  const equityOption = $derived({
    ...shared,
    legend: { data: equityMetric.drawdownRows.length ? [equityMetric.title, '낙폭'] : [equityMetric.title] },
    yAxis: equityMetric.drawdownRows.length
      ? [{ type: 'value', name: equityMetric.axisLabel }, { type: 'value', name: '낙폭 %' }]
      : { type: 'value', name: equityMetric.axisLabel },
    series: [
      { name: equityMetric.title, type: 'line', showSymbol: false, data: equityMetric.rows, lineStyle: { width: 2 } },
      ...(equityMetric.drawdownRows.length
        ? [{ name: '낙폭', type: 'line', yAxisIndex: 1, showSymbol: false, data: equityMetric.drawdownRows }]
        : []),
    ],
  });
  const learningOption = $derived({ ...shared, legend: { data: ['손실', '탐색률'] }, yAxis: [{ type: 'value', name: '손실' }, { type: 'value', name: '탐색률', min: 0, max: 1 }], series: [{ name: '손실', type: 'line', showSymbol: false, data: lossRows }, { name: '탐색률', type: 'line', yAxisIndex: 1, showSymbol: false, data: explorationRows }] });
</script>

<div class="charts" data-telemetry-charts>
  <section><h3>{rewardMetric.title}</h3><p>{rewardMetric.notice} 확대 슬라이더로 구간을 점검할 수 있습니다.</p><EChartsRenderer option={rewardOption} height="360px" caption="강화학습 표본 누적 보상" /></section>
  <section class:metric-warning={equityMetric.identity.state !== 'declared'}><h3>{equityMetric.title}</h3><p>{equityMetric.notice}</p><EChartsRenderer option={equityOption} height="360px" caption="단위 계약을 보존한 기록 에쿼티(equity)" /></section>
  <section><h3>손실 · 탐색률</h3><p>학습 안정성과 탐색 감소를 함께 확인합니다. 손실 누락은 0으로 채우지 않습니다.</p><EChartsRenderer option={learningOption} height="360px" caption="학습 손실과 탐색률" /></section>
</div>

<style>
  .charts{display:grid;grid-template-columns:1fr;gap:14px;min-width:0}.charts section{min-width:0;border:1px solid var(--border);border-radius:12px;padding:16px;background:var(--surface-sunken)}.charts section.metric-warning{border-color:var(--warn)}.charts h3{margin:0;color:var(--fg-strong);font-size:.92rem}.charts p{margin:5px 0 10px;color:var(--muted);font-size:.68rem;line-height:1.55}
</style>
