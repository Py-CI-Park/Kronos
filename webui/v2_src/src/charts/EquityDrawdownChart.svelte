<script lang="ts">
  // G2 — research equity curve + drawdown shading for the close-slot report.
  // Equity line = cumulative_net_pnl_krw (KRW) from the REAL close-slot equity
  // ledger; drawdown = peak-to-current of that same cumulative curve, computed
  // client-side (a derived view of real data, not a separate fabricated series).
  // Explicit RESEARCH_ONLY / NO PROFIT CLAIM caption is rendered under the chart.
  import { onMount, onDestroy } from 'svelte';
  import EChartsRenderer from './EChartsRenderer.svelte';
  import { tooltipLines, tooltipText, tooltipTitle } from '$lib/safeHtml';
  import { theme } from '$lib/stores';
  import { dailyOhlcvApi, type DailyCloseSlotEquityResponse } from '$lib/dailyOhlcvApi';

  interface Props {
    // Preferred: the equity payload already fetched by DailyCloseSlotCard.
    readonly equity?: DailyCloseSlotEquityResponse | null;
    // Which policy series to plot (defaults to the first available).
    readonly policy?: string;
    readonly height?: string;
  }
  let { equity = null, policy, height = '300px' }: Props = $props();

  let currentTheme = $state<'light' | 'dark'>('light');
  const unsubscribeTheme = theme.subscribe((value) => (currentTheme = value));

  // Self-sufficient fallback: if no equity prop is supplied (reuse elsewhere),
  // fetch the same read-only endpoint DailyOhlcvTab uses. No new backend route.
  let fetched = $state<DailyCloseSlotEquityResponse | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);

  onMount(() => {
    if (equity) return;
    loading = true;
    dailyOhlcvApi
      .closeSlotEquity()
      .then((payload) => (fetched = payload))
      .catch((caught) => (error = caught instanceof Error ? caught.message : 'close-slot equity load failed'))
      .finally(() => (loading = false));
  });

  onDestroy(() => unsubscribeTheme());

  const source = $derived(equity ?? fetched);

  interface EquityPoint {
    readonly date: string;
    readonly equity: number;
    readonly drawdown: number;
  }

  function toNum(value: unknown): number | null {
    const parsed = typeof value === 'number' ? value : Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  const points = $derived.by<EquityPoint[]>(() => {
    const series = source?.series ?? [];
    const chosen = policy ? series.find((s) => s?.policy === policy) : series[0];
    const rawPoints = (chosen?.points ?? []) as readonly Record<string, unknown>[];
    let peak = Number.NEGATIVE_INFINITY;
    const out: EquityPoint[] = [];
    for (const raw of rawPoints) {
      const cumulative = toNum(raw.cumulative_net_pnl_krw);
      if (cumulative == null) continue;
      peak = Math.max(peak, cumulative);
      out.push({
        date: String(raw.date ?? ''),
        equity: cumulative,
        // Drawdown as a non-positive gap from the running peak (KRW).
        drawdown: -Math.max(0, peak - cumulative),
      });
    }
    return out;
  });

  function fmtKrw(value: number): string {
    return `${Math.round(value).toLocaleString('ko-KR')} KRW`;
  }

  const chartOption = $derived.by(() => {
    void currentTheme;
    if (!points.length || typeof window === 'undefined') return {};
    const cs = getComputedStyle(document.documentElement);
    const accent = cs.getPropertyValue('--accent').trim() || '#2fb8a0';
    const danger = cs.getPropertyValue('--danger').trim() || '#e0576a';
    const dim = cs.getPropertyValue('--dim').trim() || '#8a95a6';
    const muted = cs.getPropertyValue('--muted').trim() || '#6b7688';
    const grid = cs.getPropertyValue('--border-faint').trim() || '#243244';
    const mono = cs.getPropertyValue('--font-mono').trim() || 'JetBrains Mono, monospace';

    return {
      backgroundColor: 'transparent',
      grid: { left: 66, right: 60, top: 40, bottom: 34 },
      legend: { top: 0, textStyle: { color: dim }, data: ['cumulative equity', 'drawdown from peak'] },
      tooltip: {
        trigger: 'axis',
        formatter: (params: unknown) => {
          const index = Array.isArray(params) && params[0] && typeof params[0] === 'object'
            ? Number((params[0] as { dataIndex?: number }).dataIndex ?? 0)
            : 0;
          const point = points[index];
          if (!point) return '';
          return tooltipLines([
            tooltipTitle(point.date || `t${index}`),
            tooltipText(`equity ${fmtKrw(point.equity)}`),
            tooltipText(`drawdown ${fmtKrw(point.drawdown)}`),
          ]);
        },
      },
      xAxis: {
        type: 'category',
        data: points.map((point) => point.date),
        boundaryGap: false,
        axisLine: { lineStyle: { color: grid } },
        axisLabel: { color: muted, fontFamily: mono, fontSize: 10, hideOverlap: true },
      },
      yAxis: [
        {
          type: 'value',
          name: 'equity KRW',
          nameTextStyle: { color: dim, fontSize: 11 },
          position: 'left',
          axisLabel: { color: dim, fontFamily: mono, fontSize: 10, formatter: (v: number) => Math.round(v).toLocaleString('ko-KR') },
          splitLine: { lineStyle: { color: grid } },
        },
        {
          type: 'value',
          name: 'drawdown',
          position: 'right',
          axisLabel: { color: dim, fontFamily: mono, fontSize: 10, formatter: (v: number) => Math.round(v).toLocaleString('ko-KR') },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: 'cumulative equity',
          type: 'line',
          smooth: 0.2,
          symbol: 'none',
          yAxisIndex: 0,
          data: points.map((point) => point.equity),
          lineStyle: { color: accent, width: 2.2 },
          itemStyle: { color: accent },
          areaStyle: { color: accent, opacity: 0.12 },
        },
        {
          name: 'drawdown from peak',
          type: 'line',
          smooth: 0.2,
          symbol: 'none',
          yAxisIndex: 1,
          data: points.map((point) => point.drawdown),
          lineStyle: { color: danger, width: 1.6, type: 'dashed' },
          itemStyle: { color: danger },
          areaStyle: { color: danger, opacity: 0.14 },
        },
      ],
    };
  });
</script>

<div class="equity-drawdown-chart" data-equity-drawdown-chart>
  {#if points.length}
    <EChartsRenderer option={chartOption} {height} caption="에쿼티 / 낙폭 곡선 · 연구 전용" />
  {:else}
    <div class="equity-empty" data-equity-drawdown-empty>
      {loading ? 'equity 로딩 중 · 연구 전용' : error ? error : 'equity series 없음 · 연구 전용 · fail-closed'}
    </div>
  {/if}
  <p class="equity-caption text-caption">
    RESEARCH_ONLY · close-to-next-close 누적 순손익(KRW) 시각화입니다 · <b>수익 주장 아님 (NO PROFIT CLAIM)</b> ·
    no live / broker / order / account / paper-forward. drawdown은 누적 곡선의 최고점 대비 하락폭을 파생 계산한 값입니다.
  </p>
</div>

<style>
  .equity-drawdown-chart {
    width: 100%;
    min-width: 0;
    overflow-x: auto;
  }
  .equity-empty {
    border: 1px dashed var(--border);
    border-radius: var(--r-lg);
    padding: 28px 12px;
    text-align: center;
    color: var(--muted);
    background: var(--surface);
    font-size: 13px;
  }
  .equity-caption {
    margin: 8px 0 0;
    color: var(--warn);
    line-height: 1.5;
    font-variant-numeric: tabular-nums;
  }
  .equity-caption b {
    color: var(--danger);
  }
</style>
