<script lang="ts">
  import { onMount } from 'svelte';
  import {
    rlApi,
    type RlFactoryForwardLedgerResponse,
    type RlFactoryForwardLedgerRun,
  } from '$lib/rlApi';
  import { num, pct } from '$lib/rlRows';

  type StatusFilter = 'ALL' | 'pending' | 'resolved';
  const FILTERS: readonly StatusFilter[] = ['ALL', 'pending', 'resolved'];

  let runs = $state<readonly RlFactoryForwardLedgerRun[]>([]);
  let selectedRun = $state<string>('');
  let ledger = $state<RlFactoryForwardLedgerResponse | null>(null);
  let statusFilter = $state<StatusFilter>('ALL');
  let loading = $state(true);

  const rows = $derived(ledger?.rows ?? []);
  const summary = $derived(ledger?.summary ?? {});
  const selectedMeta = $derived(runs.find((run) => run.run === selectedRun) ?? null);

  onMount(() => {
    void load();
  });

  async function load(): Promise<void> {
    loading = true;
    const payload = await rlApi.factoryForwardLedgers();
    runs = payload?.runs ?? [];
    selectedRun = selectedRun || runs[0]?.run || '';
    await loadLedger();
    loading = false;
  }

  async function loadLedger(): Promise<void> {
    if (!selectedRun) {
      ledger = null;
      return;
    }
    ledger = await rlApi.factoryForwardLedger(
      selectedRun,
      200,
      statusFilter === 'ALL' ? undefined : statusFilter
    );
  }

  async function selectRun(run: string): Promise<void> {
    if (selectedRun === run) return;
    selectedRun = run;
    loading = true;
    await loadLedger();
    loading = false;
  }

  async function setStatus(next: StatusFilter): Promise<void> {
    if (statusFilter === next) return;
    statusFilter = next;
    loading = true;
    await loadLedger();
    loading = false;
  }
</script>

<section class="card" data-rl-forward-ledger-card>
  <div class="card-header">
    <div>
      <div class="card-eyebrow">FORWARD / PAPER LEDGER · READ-ONLY</div>
      <div class="card-title">Pending/resolved decision evidence</div>
    </div>
    <div class="filter-toggle">
      {#each FILTERS as choice}
        <button type="button" class:active={statusFilter === choice} onclick={() => void setStatus(choice)}>{choice}</button>
      {/each}
    </div>
  </div>
  <p class="text-caption safety-note">
    Generated research ledger only: no orders, no broker integration, no live-readiness or profit claim. Codes stay strings; schema/cost/duplicate policy are displayed.
  </p>
  {#if loading}
    <p class="text-muted">Loading forward/paper ledger...</p>
  {:else if !runs.length}
    <p class="text-muted">No forward/paper ledgers found.</p>
  {:else}
    <div class="run-pills">
      {#each runs.slice(0, 4) as run}
        <button type="button" class:active={selectedRun === run.run} onclick={() => void selectRun(run.run)}>
          {run.fill_assumption ?? run.run}
        </button>
      {/each}
    </div>
    <div class="mini-grid" style="margin-top:12px">
      <div><span>Total / resolved / pending</span><strong>{summary.total_rows ?? selectedMeta?.total_count ?? '-'} / {summary.resolved_count ?? selectedMeta?.resolved_count ?? '-'} / {summary.pending_count ?? selectedMeta?.pending_count ?? '-'}</strong></div>
      <div><span>Schema</span><strong>{summary.schema_version ?? selectedMeta?.schema_version ?? '-'}</strong></div>
      <div><span>Cost</span><strong>{summary.cost_bps ?? selectedMeta?.cost_bps ?? '-'}bp</strong></div>
      <div><span>Duplicate policy</span><strong>{summary.duplicate_policy ?? selectedMeta?.duplicate_policy ?? '-'}</strong></div>
    </div>
    <div class="table-wrap forward-wrap" style="margin-top:12px">
      <table>
        <thead><tr><th>session</th><th>code</th><th>decision</th><th>status</th><th>p_win</th><th>edge</th><th>realized</th><th>baseline</th><th>fill</th></tr></thead>
        <tbody>
          {#each rows.slice(0, 40) as row}
            <tr>
              <td>{row.session ?? '-'}</td>
              <td>{row.code ?? '-'}</td>
              <td><span class="pill {row.decision === 'TAKE' ? 'info' : ''}">{row.decision ?? '-'}</span></td>
              <td>{row.outcome_status ?? '-'}</td>
              <td>{num(row.p_win, 3)}</td>
              <td>{pct(row.edge_pct, 3)}</td>
              <td>{pct(row.realized_outcome_pct, 3)}</td>
              <td>{pct(row.baseline_outcome_pct, 3)}</td>
              <td>{row.fill_assumption ?? '-'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <p class="text-caption" style="margin-top:6px">
      showing {Math.min(rows.length, 40)} of {ledger?.returned_rows ?? rows.length} returned rows · {ledger?.status_filter ?? 'all statuses'}
    </p>
  {/if}
</section>

<style>
  .filter-toggle,
  .run-pills {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 4px;
  }
  .filter-toggle button,
  .run-pills button {
    border: 1px solid var(--border);
    border-radius: 999px;
    background: var(--card);
    padding: 4px 12px;
    font: 600 11px/1 var(--font-display);
    cursor: pointer;
  }
  .filter-toggle button.active,
  .run-pills button.active {
    border-color: #14b8a6;
    box-shadow: 0 0 0 2px rgba(20, 184, 166, 0.16);
  }
  .forward-wrap { max-height: 320px; overflow: auto; }
</style>
