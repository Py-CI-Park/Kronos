<script lang="ts">
  import EChartsRenderer from '../../charts/EChartsRenderer.svelte';
  import type { RlTableRow } from '$lib/rlApi';
  import { theme } from '$lib/stores';
  import { actionPnlChartOption, costGateChartOption, equityChartOption, leaderboardChartOption, tradeChartOption } from './chartOptions';

  interface Props {
    readonly leaderboardRows: readonly RlTableRow[];
    readonly gateRows: readonly RlTableRow[];
    readonly equityRows: readonly RlTableRow[];
    readonly actionRows: readonly RlTableRow[];
    readonly episodeRows: readonly RlTableRow[];
    readonly tradeRows: readonly RlTableRow[];
    readonly selectedName: string;
  }
  let { leaderboardRows, gateRows, equityRows, actionRows, episodeRows, tradeRows, selectedName }: Props = $props();

  // chartOptions.ts resolves colors from CSS custom properties at build time;
  // re-invoke the builders on theme flip so the resolved colors stay current.
  let currentTheme = $state<'light' | 'dark'>('light');
  theme.subscribe((v) => (currentTheme = v));

  const leaderboardOption = $derived.by(() => { void currentTheme; return leaderboardChartOption(leaderboardRows); });
  const costGateOption = $derived.by(() => { void currentTheme; return costGateChartOption(gateRows); });
  const equityOption = $derived.by(() => { void currentTheme; return equityChartOption(equityRows); });
  const actionPnlOption = $derived.by(() => { void currentTheme; return actionPnlChartOption(actionRows, episodeRows, selectedName); });
  const tradeOption = $derived.by(() => { void currentTheme; return tradeChartOption(tradeRows); });
</script>

<section class="chart-grid">
  <section class="card" data-rl-leaderboard-chart>
    <div class="card-title">Performance leaderboard</div>
    {#if leaderboardRows.length}<EChartsRenderer option={leaderboardOption} height="300px" caption="Performance leaderboard · 정책별 net/MDD" />{:else}<p class="empty">No leaderboard rows.</p>{/if}
  </section>
  <section class="card" data-rl-cost-gate-table>
    <div class="card-title">23bp cost gate evidence</div>
    {#if gateRows.length}<EChartsRenderer option={costGateOption} height="300px" caption="23bp 비용 게이트 증거 · 정책별 net" />{:else}<p class="empty">No cost gate rows.</p>{/if}
  </section>
  <section class="card">
    <div class="card-title">CUMULATIVE REWARD EVIDENCE + ts_imb baseline</div>
    {#if actionRows.length}<EChartsRenderer option={actionPnlOption} height="300px" caption="누적 보상 증거 + ts_imb baseline" />{:else}<p class="empty">No actions/live event data for cumulative reward evidence.</p>{/if}
  </section>
  <section class="card">
    <div class="card-title">Time equity curve / net-return evidence</div>
    {#if equityRows.length}<EChartsRenderer option={equityOption} height="300px" caption="시간 에쿼티 곡선 / 순수익 증거" />{:else}<EChartsRenderer option={tradeOption} height="300px" caption="거래별 순수익 증거" />{/if}
  </section>
</section>
