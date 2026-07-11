<script lang="ts">
  // G2 — cost-sensitivity bar chart (0 / 23 / 46bp) for the close-slot report.
  // base_23bp (primary_cost_scenario_id) is starred/highlighted; 0bp/46bp are controls.
  // Data comes from the REAL close-slot selected_hold_summary.rows already plumbed
  // into DailyCloseSlotCard (cost_scenario_id · total_component_bp · reward). No
  // fabricated numbers — an empty rows set fails closed to a "데이터 없음" state.
  // RESEARCH_ONLY — not a profit / live / broker / order claim.
  import { onDestroy } from 'svelte';
  import EChartsRenderer from './EChartsRenderer.svelte';
  import { tooltipLines, tooltipText, tooltipTitle } from '$lib/safeHtml';
  import { theme } from '$lib/stores';

  interface CostBar {
    readonly scenarioId?: string;
    readonly costBp: number;
    readonly value: number;
    readonly foldRows?: number;
  }
  // Structural row shape: DailyCloseSlotSelectedHoldRow (and any superset) is
  // assignable here. Fields are the REAL close-slot cost-scenario evidence.
  interface CostHoldRow {
    readonly cost_scenario_id?: string;
    readonly total_component_bp?: number | null;
    readonly reward?: number | null;
  }

  interface Props {
    // Preferred: raw close-slot selected_hold rows (grouped/averaged per cost scenario here).
    readonly rows?: readonly CostHoldRow[];
    // Which scenario is the primary/base (starred). Defaults to base_23bp.
    readonly primaryScenarioId?: string;
    // Optional secondary bp source when a row is missing total_component_bp.
    readonly costScenarios?: Readonly<Record<string, { readonly total_bp?: number | null }>>;
    // Escape hatch: pre-shaped bars (used by tests / other callers).
    readonly bars?: readonly CostBar[];
    readonly valueLabel?: string;
    readonly height?: string;
  }
  let {
    rows = [],
    primaryScenarioId = 'base_23bp',
    costScenarios = {},
    bars,
    valueLabel = 'mean daily reward',
    height = '260px',
  }: Props = $props();

  // Colors read from canonical core.css tokens at render time; theme store
  // subscription re-derives the option on [data-theme] flip (LiveRlEventsCard idiom).
  let currentTheme = $state<'light' | 'dark'>('light');
  const unsubscribeTheme = theme.subscribe((value) => (currentTheme = value));
  onDestroy(() => unsubscribeTheme());

  function toNum(value: unknown): number | null {
    const parsed = typeof value === 'number' ? value : Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function deriveBp(row: CostHoldRow, id: string): number {
    const direct = toNum(row.total_component_bp);
    if (direct != null) return direct;
    const scenario = toNum(costScenarios?.[id]?.total_bp);
    if (scenario != null) return scenario;
    const fromId = id.match(/(\d+)\s*bp/i);
    return fromId ? Number(fromId[1]) : Number.NaN;
  }

  const resolvedBars = $derived.by<CostBar[]>(() => {
    if (bars && bars.length) return [...bars].sort((a, b) => a.costBp - b.costBp);
    const grouped = new Map<string, { costBp: number; rewards: number[] }>();
    for (const row of rows ?? []) {
      const id = String(row?.cost_scenario_id ?? '').trim();
      if (!id) continue;
      const bp = deriveBp(row, id);
      const reward = toNum(row?.reward);
      const entry = grouped.get(id) ?? { costBp: bp, rewards: [] };
      if (Number.isFinite(bp)) entry.costBp = bp;
      if (reward != null) entry.rewards.push(reward);
      grouped.set(id, entry);
    }
    const out: CostBar[] = [];
    for (const [scenarioId, entry] of grouped) {
      if (!entry.rewards.length) continue;
      const mean = entry.rewards.reduce((sum, value) => sum + value, 0) / entry.rewards.length;
      out.push({ scenarioId, costBp: entry.costBp, value: mean, foldRows: entry.rewards.length });
    }
    return out.sort((a, b) => a.costBp - b.costBp);
  });

  const hasScenarioMatch = $derived(resolvedBars.some((bar) => bar.scenarioId === primaryScenarioId));

  function isPrimary(bar: CostBar): boolean {
    if (bar.scenarioId) return bar.scenarioId === primaryScenarioId;
    return !hasScenarioMatch && Math.round(bar.costBp) === 23;
  }

  function bpLabel(bar: CostBar): string {
    return Number.isFinite(bar.costBp) ? `${Math.round(bar.costBp)}bp` : bar.scenarioId ?? '—';
  }

  function fmtReward(value: number): string {
    return value.toLocaleString('ko-KR', { maximumFractionDigits: 4 });
  }

  const chartOption = $derived.by(() => {
    void currentTheme;
    if (!resolvedBars.length || typeof window === 'undefined') return {};
    const cs = getComputedStyle(document.documentElement);
    const accent = cs.getPropertyValue('--accent').trim() || '#2fb8a0';
    const accentStrong = cs.getPropertyValue('--accent-strong').trim() || '#1f9c86';
    const dim = cs.getPropertyValue('--dim').trim() || '#8a95a6';
    const faint = cs.getPropertyValue('--faint').trim() || '#b6bfcc';
    const muted = cs.getPropertyValue('--muted').trim() || '#6b7688';
    const fg = cs.getPropertyValue('--fg').trim() || '#e6ebf2';
    const grid = cs.getPropertyValue('--border-faint').trim() || '#243244';
    const mono = cs.getPropertyValue('--font-mono').trim() || 'JetBrains Mono, monospace';
    const surface = cs.getPropertyValue('--surface').trim() || '#141b26';

    const primaryIndex = resolvedBars.findIndex((bar) => isPrimary(bar));

    return {
      backgroundColor: 'transparent',
      grid: { left: 54, right: 22, top: 34, bottom: 30 },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: unknown) => {
          const index = Array.isArray(params) && params[0] && typeof params[0] === 'object'
            ? Number((params[0] as { dataIndex?: number }).dataIndex ?? 0)
            : 0;
          const bar = resolvedBars[index];
          if (!bar) return '';
          return tooltipLines([
            tooltipTitle(`${bpLabel(bar)}${isPrimary(bar) ? ' · base_23bp 기준' : ' · 통제군'}`),
            tooltipText(`${valueLabel} ${fmtReward(bar.value)}`),
            bar.scenarioId ? tooltipText(`scenario ${bar.scenarioId}`) : null,
            bar.foldRows ? tooltipText(`rows ${bar.foldRows}`) : null,
          ]);
        },
      },
      xAxis: {
        type: 'category',
        data: resolvedBars.map((bar) => bpLabel(bar)),
        axisTick: { show: false },
        axisLine: { lineStyle: { color: grid } },
        axisLabel: { color: muted, fontFamily: mono, fontSize: 12 },
      },
      yAxis: {
        type: 'value',
        name: valueLabel,
        nameTextStyle: { color: dim, fontSize: 11, align: 'left' },
        axisLabel: { color: dim, fontFamily: mono, fontSize: 11 },
        splitLine: { lineStyle: { color: grid } },
      },
      series: [
        {
          type: 'bar',
          barMaxWidth: 64,
          data: resolvedBars.map((bar) => {
            const primary = isPrimary(bar);
            return {
              value: bar.value,
              itemStyle: {
                color: primary ? accent : faint,
                borderColor: primary ? accentStrong : dim,
                borderWidth: primary ? 1.5 : 1,
                borderRadius: [6, 6, 0, 0],
              },
            };
          }),
          label: {
            show: true,
            position: 'top',
            color: fg,
            fontFamily: mono,
            fontSize: 12,
            formatter: (p: { dataIndex?: number }) => fmtReward(resolvedBars[p.dataIndex ?? 0]?.value ?? 0),
          },
          markPoint: primaryIndex >= 0
            ? {
                symbol: 'pin',
                symbolSize: 42,
                data: [{ xAxis: primaryIndex, yAxis: resolvedBars[primaryIndex].value }],
                itemStyle: { color: accent, borderColor: accentStrong, borderWidth: 1 },
                label: { show: true, formatter: '★', color: surface, fontSize: 16, fontWeight: 700 },
              }
            : undefined,
        },
      ],
    };
  });
</script>

<div class="cost-sensitivity-chart" data-cost-sensitivity-chart>
  {#if resolvedBars.length}
    <EChartsRenderer option={chartOption} {height} caption="비용 민감도 · base_23bp vs 통제군" />
    <p class="cost-legend text-caption">
      <span class="swatch primary" aria-hidden="true"></span>★ base_23bp 기준(primary)
      <span class="swatch control" aria-hidden="true"></span>0bp / 46bp 통제군(control) · RESEARCH_ONLY · 수익 주장 아님
    </p>
  {:else}
    <div class="cost-empty" data-cost-sensitivity-empty>데이터 없음 · 연구 전용 · fail-closed</div>
  {/if}
</div>

<style>
  .cost-sensitivity-chart {
    width: 100%;
    min-width: 0;
    overflow-x: auto;
  }
  .cost-legend {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    margin: 6px 0 0;
    color: var(--muted);
    font-variant-numeric: tabular-nums;
    font-feature-settings: 'tnum', 'zero';
  }
  .swatch {
    display: inline-block;
    width: 11px;
    height: 11px;
    border-radius: 3px;
    margin-left: 8px;
  }
  .swatch.primary {
    background: var(--accent);
    box-shadow: 0 0 0 1px var(--accent-strong) inset;
  }
  .swatch.control {
    background: var(--faint);
    box-shadow: 0 0 0 1px var(--dim) inset;
  }
  .cost-empty {
    border: 1px dashed var(--border);
    border-radius: var(--r-lg);
    padding: 26px 12px;
    text-align: center;
    color: var(--muted);
    background: var(--surface);
    font-size: 13px;
  }
</style>
