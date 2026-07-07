<script lang="ts">
  // G3 — compact, axis-less sparkline primitive for the live-monitor tile row.
  // Data-source-agnostic: takes a plain number[] and a canonical color token so
  // a tile can feed it loss / GPU% / RAM% without this component owning any fetch.
  // Reuses EChartsRenderer + the theme-subscribe / getComputedStyle palette idiom
  // used by LossCurveChart and W5_GpuSparkline (no charting reinvented here).
  // Fail-closed: empty series renders an explicit "—" placeholder, never a flat
  // fabricated baseline. RESEARCH_ONLY diagnostic — not a profit/live claim.
  import { onDestroy } from 'svelte';
  import EChartsRenderer from './EChartsRenderer.svelte';
  import { theme } from '$lib/stores';

  interface Props {
    readonly values?: readonly number[];
    // Canonical core.css custom property, e.g. '--accent' | '--c-3' | '--success'.
    readonly colorVar?: string;
    readonly height?: string;
    readonly area?: boolean;
  }
  let { values = [], colorVar = '--accent', height = '40px', area = true }: Props = $props();

  let currentTheme = $state<'light' | 'dark'>('light');
  const unsubscribeTheme = theme.subscribe((value) => (currentTheme = value));
  onDestroy(() => unsubscribeTheme());

  const clean = $derived.by<number[]>(() =>
    (values ?? []).map((v) => Number(v)).filter((v) => Number.isFinite(v)),
  );

  const option = $derived.by(() => {
    void currentTheme;
    if (!clean.length || typeof window === 'undefined') return {};
    const cs = getComputedStyle(document.documentElement);
    const stroke = cs.getPropertyValue(colorVar).trim() || '#2fb8a0';
    const single = clean.length <= 2;
    return {
      backgroundColor: 'transparent',
      animation: false,
      grid: { left: 2, right: 2, top: 4, bottom: 2 },
      xAxis: {
        type: 'category',
        show: false,
        boundaryGap: false,
        data: clean.map((_, i) => i),
      },
      yAxis: { type: 'value', show: false, scale: true },
      tooltip: { show: false },
      series: [
        {
          type: 'line',
          data: clean,
          smooth: 0.35,
          symbol: single ? 'circle' : 'none',
          showSymbol: single,
          symbolSize: 4,
          lineStyle: { color: stroke, width: 1.6 },
          itemStyle: { color: stroke },
          areaStyle: area
            ? { color: stroke, opacity: 0.14 }
            : undefined,
        },
      ],
    };
  });
</script>

{#if clean.length}
  <EChartsRenderer {option} {height} />
{:else}
  <div class="spark-empty" data-mini-sparkline-empty style="height:{height}">—</div>
{/if}

<style>
  .spark-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--dim);
    font-family: var(--font-mono);
    font-size: 12px;
  }
</style>
