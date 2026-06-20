<script lang="ts">
  import { onMount } from 'svelte';
  import {
    rlApi,
    type RlFactoryDecisionFilter,
    type RlFactoryEdgeLedgerResponse,
    type RlFactoryLaneRun,
  } from '$lib/rlApi';
  import { num, pct } from '$lib/rlRows';

  type FilterChoice = 'ALL' | RlFactoryDecisionFilter;
  const FILTERS: readonly FilterChoice[] = ['ALL', 'TAKE', 'SKIP'];

  let laneRun = $state<RlFactoryLaneRun | null>(null);
  let ledger = $state<RlFactoryEdgeLedgerResponse | null>(null);
  let decisionFilter = $state<FilterChoice>('ALL');
  let loading = $state(true);

  const available = $derived(ledger?.available === true);
  const summary = $derived(ledger?.summary ?? {});
  const rows = $derived(ledger?.rows ?? []);

  onMount(() => {
    void load();
  });

  async function load(): Promise<void> {
    loading = true;
    const lanePayload = await rlApi.factoryLaneRuns();
    laneRun = lanePayload?.runs?.[0] ?? null;
    await loadLedger();
    loading = false;
  }

  async function loadLedger(): Promise<void> {
    if (!laneRun) {
      ledger = null;
      return;
    }
    ledger = await rlApi.factoryLaneEdgeLedger(
      laneRun.run,
      200,
      decisionFilter === 'ALL' ? undefined : decisionFilter
    );
  }

  async function setFilter(next: FilterChoice): Promise<void> {
    if (decisionFilter === next) return;
    decisionFilter = next;
    loading = true;
    await loadLedger();
    loading = false;
  }
</script>

<section class="card" data-rl-edge-ledger-card>
  <div class="card-header">
    <div>
      <div class="card-eyebrow">EDGE LEDGER · supervised gate (NOT RL)</div>
      <div class="card-title">{laneRun?.run ?? 'Edge ledger'}</div>
    </div>
    <div class="filter-toggle">
      {#each FILTERS as choice}
        <button type="button" class:active={decisionFilter === choice} onclick={() => void setFilter(choice)}>
          {choice}
        </button>
      {/each}
    </div>
  </div>
  <p class="text-caption safety-note">
    Edge ledger — read-only evidence, 23bp cost basis, not a profit claim.
  </p>
  {#if loading}
    <p class="text-muted">Loading edge ledger...</p>
  {:else if !available}
    <p class="text-muted">Edge ledger unavailable — no probability-lane run found.</p>
  {:else}
    <div class="mini-grid">
      <div><span>Rows (total / take / skip)</span><strong>{summary.total_rows ?? '-'} / {summary.take_count ?? '-'} / {summary.skip_count ?? '-'}</strong></div>
      <div><span>TAKE mean net (23bp)</span><strong>{pct(summary.take_mean_net_pct, 3)}</strong></div>
      <div><span>SKIP mean net (23bp)</span><strong>{pct(summary.skip_mean_net_pct, 3)}</strong></div>
      <div><span>Mean edge</span><strong>{pct(summary.mean_edge_pct, 3)}</strong></div>
    </div>
    <p class="text-caption" style="margin-top:6px">
      {summary.breakeven_note ?? ''} {summary.cost_note ?? ''}
    </p>
    <div class="table-wrap ledger-wrap" style="margin-top:12px">
      <table>
        <thead><tr><th>session</th><th>symbol</th><th>p_win</th><th>edge</th><th>decision</th><th>net (23bp)</th></tr></thead>
        <tbody>
          {#each rows.slice(0, 40) as row}
            <tr>
              <td>{row.session ?? '-'}</td>
              <td>{row.symbol ?? '-'}</td>
              <td>{num(row.p_win, 3)}</td>
              <td>{pct(row.edge_pct, 3)}</td>
              <td><span class="pill {row.decision === 'TAKE' ? 'info' : ''}">{row.decision ?? '-'}</span></td>
              <td>{pct(row.net_pct_23bp, 3)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <p class="text-caption" style="margin-top:6px">
      showing {Math.min(rows.length, 40)} of {ledger?.returned_rows ?? rows.length} returned rows
      {#if ledger?.decision_filter}
        · decision filter {ledger.decision_filter}
      {/if}
    </p>
  {/if}
</section>

<style>
  .filter-toggle {
    display: inline-flex;
    gap: 4px;
  }
  .filter-toggle button {
    border: 1px solid var(--border);
    border-radius: 999px;
    background: var(--card);
    padding: 4px 12px;
    font: 600 11px/1 var(--font-display);
    cursor: pointer;
  }
  .filter-toggle button.active {
    border-color: #14b8a6;
    box-shadow: 0 0 0 2px rgba(20, 184, 166, 0.16);
  }
  .ledger-wrap {
    max-height: 320px;
    overflow: auto;
  }
</style>
