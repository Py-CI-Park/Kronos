<script lang="ts">
  import EChartsRenderer from '../../../charts/EChartsRenderer.svelte';
  import { equityReturnSeries, sampleRewardSeries, type EvaluationEntry } from './evaluationModel';

  interface Props {
    readonly entries: readonly EvaluationEntry[];
  }

  let { entries }: Props = $props();
  const base = { animationDuration: 250, tooltip: { trigger: 'axis' }, legend: { type: 'scroll' }, grid: { left: 54, right: 24, top: 55, bottom: 42 }, xAxis: { type: 'value', name: 'step' } };
  const equityOption = $derived({ ...base, yAxis: { type: 'value', name: '기록 equity (%)' }, series: entries.map((entry) => ({ name: `${entry.run.name} · ${entry.run.status}`, type: 'line', showSymbol: false, data: equityReturnSeries(entry.snapshot) })) });
  const rewardOption = $derived({ ...base, yAxis: { type: 'value', name: '표본 reward 누적' }, series: entries.map((entry) => ({ name: `${entry.run.name} · ${entry.run.status}`, type: 'line', showSymbol: false, data: sampleRewardSeries(entry.snapshot) })) });
</script>

<div class="compare-charts" data-comparison-charts>
  <section><h3>기록 에쿼티 비교</h3><p>event equity의 1.0 대비 변화이며 공식 OOS 수익률 순위가 아닙니다.</p><EChartsRenderer option={equityOption} height="300px" caption="같은 lane 실행의 기록 에쿼티 비교" /></section>
  <section><h3>표본 누적 보상 비교</h3><p>표시된 point의 reward만 누적하며 파일 전체 reward로 확대 해석하지 않습니다.</p><EChartsRenderer option={rewardOption} height="300px" caption="같은 lane 실행의 표본 누적 보상 비교" /></section>
</div>

<style>
  .compare-charts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;min-width:0}.compare-charts section{min-width:0;border:1px solid var(--border);border-radius:10px;padding:14px;background:var(--surface-sunken)}h3{margin:0;color:var(--fg-strong);font-size:.9rem}p{margin:4px 0 10px;color:var(--muted);font-size:.68rem}
  @media(max-width:900px){.compare-charts{grid-template-columns:1fr}}
</style>
