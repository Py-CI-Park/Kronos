<script lang="ts">
  // G2 — reusable loss-over-step line chart. Data-source-agnostic on purpose:
  // it takes a plain { step, loss }[] prop so a later story (G3) can feed it a
  // live-training tile from the lossPoints store without this component owning
  // any fetch or endpoint. RESEARCH_ONLY diagnostic — not a profit/live claim.
  import { onDestroy } from 'svelte';
  import EChartsRenderer from './EChartsRenderer.svelte';
  import { tooltipLines, tooltipText, tooltipTitle } from '$lib/safeHtml';
  import { theme } from '$lib/stores';

  interface LossDatum {
    readonly step: number;
    readonly loss: number;
  }

  interface Props {
    readonly points?: readonly LossDatum[];
    readonly title?: string;
    readonly valueLabel?: string;
    readonly height?: string;
    readonly smooth?: boolean;
  }
  let {
    points = [],
    title = 'loss over step',
    valueLabel = 'loss',
    height = '260px',
    smooth = true,
  }: Props = $props();

  let currentTheme = $state<'light' | 'dark'>('light');
  const unsubscribeTheme = theme.subscribe((value) => (currentTheme = value));
  onDestroy(() => unsubscribeTheme());

  const cleanPoints = $derived.by<LossDatum[]>(() =>
    (points ?? [])
      .filter((point) => point && Number.isFinite(point.step) && Number.isFinite(point.loss))
      .map((point) => ({ step: point.step, loss: point.loss }))
      .sort((a, b) => a.step - b.step)
  );

  function fmtLoss(value: number): string {
    return value.toLocaleString('en-US', { maximumFractionDigits: 5 });
  }

  const chartOption = $derived.by(() => {
    void currentTheme;
    if (!cleanPoints.length || typeof window === 'undefined') return {};
    const cs = getComputedStyle(document.documentElement);
    const accent = cs.getPropertyValue('--accent').trim() || '#2fb8a0';
    const dim = cs.getPropertyValue('--dim').trim() || '#8a95a6';
    const muted = cs.getPropertyValue('--muted').trim() || '#6b7688';
    const grid = cs.getPropertyValue('--border-faint').trim() || '#243244';
    const mono = cs.getPropertyValue('--font-mono').trim() || 'JetBrains Mono, monospace';

    return {
      backgroundColor: 'transparent',
      grid: { left: 58, right: 22, top: 34, bottom: 32 },
      tooltip: {
        trigger: 'axis',
        formatter: (params: unknown) => {
          const index = Array.isArray(params) && params[0] && typeof params[0] === 'object'
            ? Number((params[0] as { dataIndex?: number }).dataIndex ?? 0)
            : 0;
          const point = cleanPoints[index];
          if (!point) return '';
          return tooltipLines([
            tooltipTitle(`step ${point.step.toLocaleString('en-US')}`),
            tooltipText(`${valueLabel} ${fmtLoss(point.loss)}`),
          ]);
        },
      },
      xAxis: {
        type: 'category',
        name: 'step',
        nameTextStyle: { color: dim, fontSize: 11 },
        data: cleanPoints.map((point) => String(point.step)),
        axisTick: { show: false },
        axisLine: { lineStyle: { color: grid } },
        axisLabel: { color: muted, fontFamily: mono, fontSize: 10, hideOverlap: true },
      },
      yAxis: {
        type: 'value',
        name: valueLabel,
        nameTextStyle: { color: dim, fontSize: 11 },
        scale: true,
        axisLabel: { color: dim, fontFamily: mono, fontSize: 10 },
        splitLine: { lineStyle: { color: grid } },
      },
      series: [
        {
          name: valueLabel,
          type: 'line',
          smooth: smooth ? 0.25 : false,
          symbol: 'none',
          data: cleanPoints.map((point) => point.loss),
          lineStyle: { color: accent, width: 2.2 },
          itemStyle: { color: accent },
          areaStyle: { color: accent, opacity: 0.14 },
        },
      ],
    };
  });
</script>

<div class="loss-curve-chart" data-loss-curve-chart>
  {#if title}
    <div class="loss-curve-title text-eyebrow">{title}</div>
  {/if}
  {#if cleanPoints.length}
    <EChartsRenderer option={chartOption} {height} />
  {:else}
    <div class="loss-empty" data-loss-curve-empty>loss 데이터 없음 · 연구 전용</div>
  {/if}
</div>

<style>
  .loss-curve-chart {
    width: 100%;
    min-width: 0;
    overflow-x: auto;
  }
  .loss-curve-title {
    margin-bottom: 6px;
    font-variant-numeric: tabular-nums;
  }
  .loss-empty {
    border: 1px dashed var(--border);
    border-radius: var(--r-lg);
    padding: 26px 12px;
    text-align: center;
    color: var(--muted);
    background: var(--surface);
    font-size: 13px;
  }
</style>
