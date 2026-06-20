<script lang="ts">
  import { onMount } from 'svelte';
  import { rlApi, type RlFactoryQueueResponse } from '$lib/rlApi';

  let queue = $state<RlFactoryQueueResponse | null>(null);
  let loading = $state(true);

  const available = $derived(queue?.available === true);
  const counts = $derived(queue?.counts_by_status ?? queue?.status_counts ?? {});
  const latestRuns = $derived(queue?.latest_runs ?? []);
  const guardrail = $derived(
    queue?.guardrail ?? 'Read-only research evidence viewer — no profit claim, 23bp cost basis.'
  );

  onMount(() => {
    void load();
  });

  async function load(): Promise<void> {
    loading = true;
    queue = await rlApi.factoryQueue();
    loading = false;
  }

  function verdictTone(verdict: string): string {
    if (verdict.startsWith('NO-GO')) return 'danger';
    if (verdict.includes('INCONCLUSIVE')) return 'warn';
    if (verdict.startsWith('GO_CANDIDATE')) return 'success';
    return '';
  }
</script>

<section class="card" data-rl-factory-status-card>
  <div class="card-header">
    <div>
      <div class="card-eyebrow">FACTORY QUEUE · READ-ONLY EVIDENCE</div>
      <div class="card-title">Experiment queue status</div>
    </div>
    <span class="pill {available ? 'success' : 'warn'}"><span class="dot"></span>{available ? 'registry available' : 'unavailable'}</span>
  </div>
  {#if loading}
    <p class="text-muted">Loading factory queue...</p>
  {:else if !available}
    <p class="text-muted">
      {queue?.reason === 'registry_not_found' ? 'Factory registry not found — no experiments have been queued yet.' : 'Factory queue unavailable.'}
    </p>
    <p class="text-caption safety-note">{guardrail}</p>
  {:else}
    <div class="mini-grid">
      {#each Object.entries(counts) as [status, count]}
        <div><span>{status}</span><strong>{count}</strong></div>
      {/each}
    </div>
    {#if latestRuns.length}
      <div class="table-wrap" style="margin-top:12px">
        <table>
          <thead><tr><th>run_id</th><th>stage</th><th>status</th><th>verdict</th><th>prereg doc</th></tr></thead>
          <tbody>
            {#each latestRuns.slice(0, 12) as row}
              <tr>
                <td>{row.run_id}</td>
                <td>{row.stage ?? '-'}</td>
                <td>{row.status ?? '-'}</td>
                <td><span class="pill {verdictTone(String(row.verdict ?? ''))}">{row.verdict || 'pending'}</span></td>
                <td class="prereg-cell">{row.prereg_doc ?? '-'}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {:else}
      <p class="text-muted" style="margin-top:8px">No runs registered yet.</p>
    {/if}
    <p class="text-caption safety-note">
      {guardrail} Verdict labels are evidence, not profitability.
      {#if queue?.read_only_dashboard_note}
        {queue.read_only_dashboard_note}
      {/if}
    </p>
  {/if}
</section>

<style>
  .prereg-cell {
    max-width: 260px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
