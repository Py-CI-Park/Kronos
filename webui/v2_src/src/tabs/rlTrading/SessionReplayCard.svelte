<script lang="ts">
  import { onMount } from 'svelte';
  import { rlApi, type RlFactoryEdgeLedgerRow, type RlFactoryLaneRun } from '$lib/rlApi';
  import { num, numberValue, pct } from '$lib/rlRows';

  let laneRun = $state<RlFactoryLaneRun | null>(null);
  let rows = $state<readonly RlFactoryEdgeLedgerRow[]>([]);
  let available = $state(false);
  let loading = $state(true);
  let session = $state('');
  let stepIndex = $state(0);

  const sessions = $derived.by(() => {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const row of rows) {
      const key = String(row.session ?? '');
      if (!key || seen.has(key)) continue;
      seen.add(key);
      out.push(key);
    }
    return out;
  });
  const sessionRows = $derived(rows.filter((row) => String(row.session ?? '') === session));
  const maxIndex = $derived(Math.max(sessionRows.length - 1, 0));
  const revealed = $derived(sessionRows.slice(0, Math.min(stepIndex, maxIndex) + 1));
  const cumulativeTakeNet = $derived(
    revealed.reduce((acc, row) => (row.decision === 'TAKE' ? acc + numberValue(row.net_pct_23bp) : acc), 0)
  );
  const revealedTakeCount = $derived(revealed.filter((row) => row.decision === 'TAKE').length);

  onMount(() => {
    void load();
  });

  async function load(): Promise<void> {
    loading = true;
    const lanePayload = await rlApi.factoryLaneRuns();
    laneRun = lanePayload?.runs?.[0] ?? null;
    const ledger = laneRun ? await rlApi.factoryLaneEdgeLedger(laneRun.run, 2000) : null;
    available = ledger?.available === true;
    rows = ledger?.rows ?? [];
    session = '';
    stepIndex = 0;
    const first = rows.find((row) => String(row.session ?? ''));
    if (first) session = String(first.session ?? '');
    loading = false;
  }

  function chooseSession(next: string): void {
    session = next;
    stepIndex = 0;
  }

  function step(delta: number): void {
    stepIndex = Math.max(0, Math.min(maxIndex, stepIndex + delta));
  }
</script>

<section class="card" data-rl-session-replay-card>
  <div class="card-header">
    <div>
      <div class="card-eyebrow">SESSION REPLAY · supervised gate (NOT RL)</div>
      <div class="card-title">{laneRun?.run ?? 'Session replay'}</div>
    </div>
    <span class="pill"><span class="dot"></span>manual stepping</span>
  </div>
  <p class="text-caption safety-note">
    Session replay — observation tool, not evidence of profitability; read-only. Net values at 23bp cost basis.
  </p>
  {#if loading}
    <p class="text-muted">Loading session ledger...</p>
  {:else if !available || !sessions.length}
    <p class="text-muted">Replay unavailable — no probability-lane ledger rows found.</p>
  {:else}
    <div class="replay-controls">
      <select value={session} onchange={(event) => chooseSession((event.currentTarget as HTMLSelectElement).value)}>
        {#each sessions as item}
          <option value={item}>{item}</option>
        {/each}
      </select>
      <button type="button" class="step-btn" onclick={() => step(-1)} disabled={stepIndex <= 0}>prev</button>
      <input
        type="range"
        min="0"
        max={maxIndex}
        value={Math.min(stepIndex, maxIndex)}
        oninput={(event) => (stepIndex = Number((event.currentTarget as HTMLInputElement).value))}
      />
      <button type="button" class="step-btn" onclick={() => step(1)} disabled={stepIndex >= maxIndex}>next</button>
    </div>
    <div class="mini-grid" style="margin-top:12px">
      <div><span>Revealed rows</span><strong>{revealed.length} / {sessionRows.length}</strong></div>
      <div><span>TAKE rows revealed</span><strong>{revealedTakeCount}</strong></div>
      <div><span>Running TAKE net (23bp)</span><strong>{pct(cumulativeTakeNet, 3)}</strong></div>
    </div>
    <div class="table-wrap replay-wrap" style="margin-top:12px">
      <table>
        <thead><tr><th>#</th><th>symbol</th><th>p_win</th><th>edge</th><th>decision</th><th>net (23bp)</th></tr></thead>
        <tbody>
          {#each revealed as row, idx}
            <tr>
              <td>{idx + 1}</td>
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
  {/if}
</section>

<style>
  .replay-controls {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 8px;
  }
  .replay-controls select {
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--card);
    padding: 6px 8px;
    font: inherit;
    min-width: 140px;
  }
  .replay-controls input[type='range'] {
    flex: 1;
    min-width: 80px;
  }
  .step-btn {
    border: 1px solid var(--border);
    border-radius: 999px;
    background: var(--card);
    padding: 4px 12px;
    font: 600 11px/1 var(--font-display);
    cursor: pointer;
  }
  .step-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .replay-wrap {
    max-height: 300px;
    overflow: auto;
  }
</style>
