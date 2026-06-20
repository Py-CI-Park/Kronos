<script lang="ts">
  import { onMount } from 'svelte';
  import { rlApi, type RlFactorySizingRun } from '$lib/rlApi';
  import { num, pct } from '$lib/rlRows';

  let runs = $state<readonly RlFactorySizingRun[]>([]);
  let loading = $state(true);

  const hasRuns = $derived(runs.length > 0);

  onMount(() => {
    void load();
  });

  async function load(): Promise<void> {
    loading = true;
    const payload = await rlApi.factorySizingRuns();
    runs = payload?.runs ?? [];
    loading = false;
  }

  function statusTone(row: RlFactorySizingRun): string {
    if (row.p5_prerequisite_met) return 'success';
    return 'danger';
  }
</script>

<section class="card" data-rl-sizing-risk-card>
  <div class="card-header">
    <div>
      <div class="card-eyebrow">SIZING / RISK · P2 GATE</div>
      <div class="card-title">Stacked TAKE vs same-fill ts_imb account risk</div>
    </div>
    <span class="pill danger"><span class="dot"></span>P5 currently blocked by P2</span>
  </div>
  <p class="text-caption safety-note">
    Operations-design sizing evidence only. Not RL, not live-ready, no broker/orders, no profit claim. Baseline is same-fill ts_imb RULE.
  </p>
  {#if loading}
    <p class="text-muted">Loading sizing/risk evidence...</p>
  {:else if !hasRuns}
    <p class="text-muted">No sizing/risk artifacts found.</p>
  {:else}
    <div class="table-wrap sizing-wrap">
      <table>
        <thead>
          <tr>
            <th>run</th><th>P5 gate</th><th>fill</th><th>trades strategy/base</th><th>total pp Δ</th><th>mean/trade Δ</th><th>maxDD Δ</th><th>mean/std strategy/base</th><th>halt-5 total strategy/base</th><th>worst session strategy/base</th>
          </tr>
        </thead>
        <tbody>
          {#each runs.slice(0, 8) as row}
            <tr>
              <td class="run-cell">{row.run}</td>
              <td><span class="pill {statusTone(row)}">{row.p5_status ?? 'P5_BLOCKED_BY_P2'}</span></td>
              <td>{row.fill_mode ?? '-'}</td>
              <td>{row.strategy_trade_count ?? '-'} / {row.baseline_trade_count ?? '-'}</td>
              <td>{num(row.total_pct_delta, 3)}</td>
              <td>{pct(row.mean_trade_delta_pct, 3)}</td>
              <td>{pct(row.max_drawdown_delta, 3)}</td>
              <td>{num(row.strategy_risk_adjusted_mean_over_std, 3)} / {num(row.baseline_risk_adjusted_mean_over_std, 3)}</td>
              <td>{pct(row.strategy_daily_halt_5_total_pct, 3)} / {pct(row.baseline_daily_halt_5_total_pct, 3)}</td>
              <td>{pct(row.strategy_worst_session_net_pct, 3)} / {pct(row.baseline_worst_session_net_pct, 3)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <p class="text-caption" style="margin-top:6px">
      P5 requires account-level risk-adjusted improvement and drawdown improvement. Current artifacts keep RL sizing/exit implementation blocked.
    </p>
  {/if}
</section>

<style>
  .sizing-wrap { max-height: 300px; overflow: auto; }
  .run-cell { max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
