<script lang="ts">
  import EChartsRenderer from '../../../charts/EChartsRenderer.svelte';
  import type { EvaluationEntry } from './evaluationModel';
  import { comparisonChartOptions } from './comparisonChartModel';

  interface Props {
    readonly entries: readonly EvaluationEntry[];
  }

  let { entries }: Props = $props();
  const equityOption = $derived(comparisonChartOptions(entries, 'equity'));
  const rewardOption = $derived(comparisonChartOptions(entries, 'reward'));
</script>

<div class="compare-charts" data-comparison-charts>
  <div class="run-key" aria-label="비교 실행 범례">{#each entries as entry}<span><b>{entry.run.status}</b>{entry.run.name}<small>{entry.snapshot.points.length} point · {entry.snapshot.sampling}</small></span>{/each}</div>
  <section><h3>기록 에쿼티 비교</h3><p>event equity의 1.0 대비 변화이며 공식 OOS 수익률 순위가 아닙니다. 아래 슬라이더로 혼잡한 구간을 확대할 수 있습니다.</p><EChartsRenderer option={equityOption} height="430px" caption="같은 lane 실행의 기록 에쿼티 비교" /></section>
  <section><h3>표본 누적 보상 비교</h3><p>표시된 point의 reward만 누적하며 파일 전체 reward로 확대 해석하지 않습니다. 범례는 위쪽에 고정했습니다.</p><EChartsRenderer option={rewardOption} height="430px" caption="같은 lane 실행의 표본 누적 보상 비교" /></section>
</div>

<style>
  .compare-charts{display:grid;grid-template-columns:1fr;gap:14px;min-width:0}.compare-charts section{min-width:0;border:1px solid var(--border);border-radius:12px;padding:16px;background:var(--surface-sunken)}h3{margin:0;color:var(--fg-strong);font-size:.95rem}p{margin:5px 0 10px;color:var(--muted);font-size:.68rem;line-height:1.55}.run-key{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:8px}.run-key span{display:grid;grid-template-columns:auto 1fr;gap:3px 8px;min-width:0;border:1px solid var(--border);border-radius:9px;padding:10px;background:var(--surface-raised);color:var(--fg);font-size:.68rem;overflow-wrap:anywhere}.run-key b{color:var(--danger);font:.62rem var(--font-mono)}.run-key small{grid-column:2;color:var(--muted)}
</style>
