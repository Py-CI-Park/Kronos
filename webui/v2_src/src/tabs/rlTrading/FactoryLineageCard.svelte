<script lang="ts">
  import { onMount } from 'svelte';
  import { rlApi, type RlFactoryLaneRun } from '$lib/rlApi';
  import { num, pct } from '$lib/rlRows';

  let runs = $state<readonly RlFactoryLaneRun[]>([]);
  let loading = $state(true);

  const hasRuns = $derived(runs.length > 0);

  onMount(() => {
    void load();
  });

  async function load(): Promise<void> {
    loading = true;
    const payload = await rlApi.factoryLaneRuns();
    runs = payload?.runs ?? [];
    loading = false;
  }

  function verdictTone(verdict: string | null | undefined): string {
    const value = String(verdict ?? '');
    if (value.startsWith('NO-GO')) return 'danger';
    if (value.startsWith('GO_CANDIDATE')) return 'success';
    if (value.includes('INCONCLUSIVE')) return 'warn';
    return '';
  }
</script>

<section class="card" data-rl-factory-lineage-card>
  <div class="card-header">
    <div>
      <div class="card-eyebrow">FACTORY LINEAGE · FILL-MODE ROBUSTNESS</div>
      <div class="card-title">Probability lane lineage and same-fill ts_imb baseline</div>
    </div>
    <span class="pill info"><span class="dot"></span>supervised gate · NOT RL</span>
  </div>
  <p class="text-caption safety-note">
    Shows parent lineage, split/seed/hash, 23bp cost, fill_mode, failed gate reasons, and total pp vs mean/trade tradeoff. ts_imb is a RULE baseline.
  </p>
  {#if loading}
    <p class="text-muted">Loading lineage evidence...</p>
  {:else if !hasRuns}
    <p class="text-muted">No probability-lane lineage runs found.</p>
  {:else}
    <div class="table-wrap lineage-wrap">
      <table>
        <thead>
          <tr>
            <th>run</th><th>verdict</th><th>fill</th><th>parent</th><th>split/seed</th><th>TAKE</th><th>TAKE mean</th><th>ts_imb mean</th><th>mean Δ</th><th>total pp Δ</th><th>controls</th>
          </tr>
        </thead>
        <tbody>
          {#each runs.slice(0, 8) as row}
            <tr>
              <td class="run-cell">{row.run}</td>
              <td><span class="pill {verdictTone(row.verdict)}">{row.verdict ?? 'UNKNOWN'}</span></td>
              <td>{row.fill_mode ?? '-'}</td>
              <td class="run-cell">{row.parent_run ?? '-'}</td>
              <td>{row.split_hash ?? '-'} / {row.split_seed ?? row.seed ?? '-'}</td>
              <td>{row.oos_take_count ?? '-'}</td>
              <td>{pct(row.oos_take_mean_net_pct, 3)}</td>
              <td>{pct(row.ts_imb_mean_net_pct, 3)}</td>
              <td>{pct(row.mean_trade_delta_pct, 3)}</td>
              <td>{num(row.total_pp_delta, 3)}</td>
              <td>{row.blocking_reasons?.length ? row.blocking_reasons.join(', ') : `folds ${row.consistent_folds ?? '-'} · ablations ${row.ablations_better_than_full ?? '-'}`}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <p class="text-caption" style="margin-top:6px">
      Positive mean/trade can still lose total pp when many positive low-edge trades are skipped; dashboard exposes both instead of hiding the tradeoff.
    </p>
  {/if}
</section>

<style>
  .lineage-wrap { max-height: 300px; overflow: auto; }
  .run-cell { max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
