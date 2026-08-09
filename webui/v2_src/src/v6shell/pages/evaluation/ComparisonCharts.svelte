<script lang="ts">
  import EChartsRenderer from '../../../charts/EChartsRenderer.svelte';
  import type { EvaluationEntry } from './evaluationModel';
  import { comparisonChartOptions, comparisonCompatibility, type ComparisonAxisMode } from './comparisonChartModel';

  interface Props {
    readonly entries: readonly EvaluationEntry[];
  }

  let { entries }: Props = $props();
  let axisMode = $state<ComparisonAxisMode>('progress');
  const equityOption = $derived(comparisonChartOptions(entries, 'equity', axisMode));
  const rewardOption = $derived(comparisonChartOptions(entries, 'reward', axisMode));
  const equityCompatibility = $derived(comparisonCompatibility(entries, 'equity'));
  const rewardCompatibility = $derived(comparisonCompatibility(entries, 'reward'));
</script>

<div class="compare-charts" data-comparison-charts>
  <div class="chart-controls" role="group" aria-label="비교 차트 x축 선택">
    <div><strong>비교 축</strong><span>길이가 다른 run은 진행률 축에서 같은 폭으로 정렬됩니다.</span></div>
    <button type="button" aria-pressed={axisMode === 'progress'} onclick={() => { axisMode = 'progress'; }}>정규화 진행률</button>
    <button type="button" aria-pressed={axisMode === 'step'} onclick={() => { axisMode = 'step'; }}>원본 step</button>
  </div>
  <div class="run-key" aria-label="비교 실행 범례">{#each entries as entry}<span><b>{entry.run.status}</b>{entry.run.name}<small>{entry.snapshot.points.length} point · {entry.snapshot.sampling}</small></span>{/each}</div>
  <section class:blocked={!equityCompatibility.compatible}><h3>기록 equity 비교</h3><p>{equityCompatibility.message} 공식 OOS 수익률 순위가 아닙니다.</p>{#if equityCompatibility.compatible}<EChartsRenderer option={equityOption} height="560px" caption="같은 lane 실행의 단위 호환 equity 비교" />{:else}<div class="comparison-block" role="status"><b>OVERLAY BLOCKED</b><span>{equityCompatibility.message}</span></div>{/if}</section>
  <section class:blocked={!rewardCompatibility.compatible}><h3>표본 누적 보상 비교</h3><p>{rewardCompatibility.message} 표시 point만 누적하며 파일 전체 reward로 확대 해석하지 않습니다.</p>{#if rewardCompatibility.compatible}<EChartsRenderer option={rewardOption} height="560px" caption="같은 lane 실행의 단위 호환 누적 보상 비교" />{:else}<div class="comparison-block" role="status"><b>OVERLAY BLOCKED</b><span>{rewardCompatibility.message}</span></div>{/if}</section>
</div>

<style>
  .compare-charts{display:grid;grid-template-columns:1fr;gap:16px;min-width:0}.compare-charts section{min-width:0;border:1px solid var(--border);border-radius:14px;padding:20px;background:var(--surface-sunken)}.compare-charts section.blocked{border-color:var(--warn)}h3{margin:0;color:var(--fg-strong);font-size:1rem}p{margin:6px 0 12px;color:var(--muted);font-size:.72rem;line-height:1.6}.comparison-block{display:flex;min-height:180px;flex-direction:column;align-items:center;justify-content:center;gap:8px;border:1px dashed var(--warn);border-radius:10px;background:var(--surface-raised);text-align:center}.comparison-block b{color:var(--warn);font:900 .78rem var(--font-mono)}.comparison-block span{max-width:620px;color:var(--fg);font-size:.72rem}.chart-controls{display:grid;grid-template-columns:minmax(220px,1fr) auto auto;gap:8px;align-items:center;border:1px solid var(--border-strong);border-radius:12px;padding:12px;background:var(--surface-raised)}.chart-controls div{display:flex;min-width:0;flex-direction:column;gap:3px}.chart-controls strong{color:var(--fg-strong);font-size:.76rem}.chart-controls span{color:var(--muted);font-size:.65rem}.chart-controls button{border:1px solid var(--border-strong);border-radius:8px;padding:8px 11px;background:var(--surface-sunken);color:var(--fg);font-weight:800;cursor:pointer}.chart-controls button[aria-pressed=true]{border-color:var(--accent);background:var(--accent);color:var(--on-accent)}.run-key{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:8px}.run-key span{display:grid;grid-template-columns:auto 1fr;gap:3px 8px;min-width:0;border:1px solid var(--border);border-radius:9px;padding:12px;background:var(--surface-raised);color:var(--fg);font-size:.7rem;overflow-wrap:anywhere}.run-key b{color:var(--danger);font:.64rem var(--font-mono)}.run-key small{grid-column:2;color:var(--muted)}
  @media(max-width:720px){.chart-controls{grid-template-columns:1fr 1fr}.chart-controls div{grid-column:1/-1}.compare-charts section{padding:14px}}
</style>
