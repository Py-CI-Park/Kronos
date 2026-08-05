<script lang="ts">
  import EChartsRenderer from '../../../charts/EChartsRenderer.svelte';
  import type { TelemetryPoint } from '../../api/telemetryApi';

  interface Props {
    readonly points: readonly TelemetryPoint[];
  }

  let { points }: Props = $props();

  const rewardRows = $derived.by(() => {
    let cumulative = 0;
    return points.map((point) => {
      cumulative += point.reward ?? 0;
      return [point.step, cumulative];
    });
  });
  const equityRows = $derived(points.filter((point) => point.equity !== null).map((point) => [point.step, point.equity]));
  const drawdownRows = $derived.by(() => {
    let peak = Number.NEGATIVE_INFINITY;
    return points.flatMap((point) => {
      if (point.equity === null) return [];
      peak = Math.max(peak, point.equity);
      return [[point.step, peak > 0 ? ((point.equity / peak) - 1) * 100 : 0]];
    });
  });
  const lossRows = $derived(points.filter((point) => point.loss !== null).map((point) => [point.step, point.loss]));
  const explorationRows = $derived(points.filter((point) => point.exploration !== null).map((point) => [point.step, point.exploration]));

  const shared = { animationDuration: 250, tooltip: { trigger: 'axis' }, grid: { left: 48, right: 24, top: 35, bottom: 42 }, xAxis: { type: 'value', name: 'step' } };
  const rewardOption = $derived({ ...shared, yAxis: { type: 'value', name: '누적 보상' }, series: [{ name: '누적 보상', type: 'line', showSymbol: false, data: rewardRows, lineStyle: { width: 2 } }] });
  const equityOption = $derived({ ...shared, legend: { data: ['에쿼티', '낙폭'] }, yAxis: [{ type: 'value', name: '에쿼티' }, { type: 'value', name: '낙폭 %' }], series: [{ name: '에쿼티', type: 'line', showSymbol: false, data: equityRows }, { name: '낙폭', type: 'line', yAxisIndex: 1, showSymbol: false, data: drawdownRows }] });
  const learningOption = $derived({ ...shared, legend: { data: ['손실', '탐색률'] }, yAxis: [{ type: 'value', name: '손실' }, { type: 'value', name: '탐색률', min: 0, max: 1 }], series: [{ name: '손실', type: 'line', showSymbol: false, data: lossRows }, { name: '탐색률', type: 'line', yAxisIndex: 1, showSymbol: false, data: explorationRows }] });
</script>

<div class="charts" data-telemetry-charts>
  <section><h3>누적 보상</h3><p>표시된 표본 reward의 누적값이며 경제적 수익률이 아닙니다.</p><EChartsRenderer option={rewardOption} height="280px" caption="강화학습 표본 누적 보상" /></section>
  <section><h3>에쿼티 · 낙폭</h3><p>event에 직접 기록된 에쿼티와 표본 내 고점 대비 낙폭입니다.</p><EChartsRenderer option={equityOption} height="280px" caption="기록된 에쿼티와 표본 낙폭" /></section>
  <section class="wide"><h3>손실 · 탐색률</h3><p>학습 안정성과 탐색 감소를 함께 확인합니다.</p><EChartsRenderer option={learningOption} height="280px" caption="학습 손실과 탐색률" /></section>
</div>

<style>
  .charts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;min-width:0}.charts section{min-width:0;border:1px solid var(--border);border-radius:10px;padding:14px;background:var(--surface-sunken)}.charts section.wide{grid-column:1/-1}.charts h3{margin:0;color:var(--fg-strong);font-size:.9rem}.charts p{margin:4px 0 10px;color:var(--muted);font-size:.68rem}
  @media(max-width:850px){.charts{grid-template-columns:1fr}.charts section.wide{grid-column:auto}}
</style>
