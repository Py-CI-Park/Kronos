<script lang="ts">
  import { onMount } from 'svelte';
  import { rlApi, type RlFactoryCalibrationResponse, type RlFactoryLaneRun } from '$lib/rlApi';
  import { num } from '$lib/rlRows';

  let laneRun = $state<RlFactoryLaneRun | null>(null);
  let calibration = $state<RlFactoryCalibrationResponse | null>(null);
  let loading = $state(true);
  let foldIndex = $state(0);

  const available = $derived(calibration?.available === true);
  const folds = $derived(calibration?.folds ?? []);
  const fold = $derived(folds[foldIndex] ?? folds[0] ?? null);
  const brier = $derived(calibration?.brier ?? null);
  const brierConstant = $derived(calibration?.brier_constant ?? null);
  const hasSkill = $derived(brier != null && brierConstant != null && brier < brierConstant);
  const verdict = $derived(String(laneRun?.verdict ?? 'UNKNOWN'));
  const verdictTone = $derived(
    verdict.startsWith('NO-GO') ? 'danger' : verdict.startsWith('GO_CANDIDATE') ? 'success' : 'warn'
  );

  onMount(() => {
    void load();
  });

  async function load(): Promise<void> {
    loading = true;
    const lanePayload = await rlApi.factoryLaneRuns();
    laneRun = lanePayload?.runs?.[0] ?? null;
    calibration = laneRun ? await rlApi.factoryLaneCalibration(laneRun.run) : null;
    foldIndex = 0;
    loading = false;
  }

  function barWidth(value: number | null | undefined): string {
    const n = Number(value);
    if (!Number.isFinite(n)) return '0%';
    return `${(Math.max(0, Math.min(1, n)) * 100).toFixed(1)}%`;
  }
</script>

<section class="card" data-rl-calibration-card>
  <div class="card-header">
    <div>
      <div class="card-eyebrow">PROBABILITY LANE CALIBRATION · supervised gate (NOT RL)</div>
      <div class="card-title">{laneRun?.run ?? 'Lane calibration'}</div>
    </div>
    <span class="pill {verdictTone}"><span class="dot"></span>{verdict}</span>
  </div>
  {#if loading}
    <p class="text-muted">Loading lane calibration...</p>
  {:else if !available}
    <p class="text-muted">Calibration evidence unavailable — no probability-lane run found.</p>
    <p class="text-caption safety-note">supervised gate (NOT RL) · read-only evidence viewer, not profitability proof.</p>
  {:else}
    <div class="mini-grid">
      <div><span>Brier</span><strong>{num(brier, 4)}</strong></div>
      <div><span>Constant Brier</span><strong>{num(brierConstant, 4)}</strong></div>
      <div><span>Skill vs constant</span><strong>{hasSkill ? 'yes (Brier below constant)' : 'no'}</strong></div>
      <div><span>OOS TAKE count</span><strong>{laneRun?.oos_take_count ?? '-'}</strong></div>
    </div>
    <p class="text-caption safety-note">
      Brier score: lower is better; skill exists only when Brier &lt; constant. supervised gate (NOT RL) ·
      read-only calibration evidence, not profitability proof. ts_imb remains the RULE baseline.
    </p>
    <div class="table-wrap" style="margin-top:12px">
      <table>
        <thead><tr><th>fold</th><th>brier</th></tr></thead>
        <tbody>
          {#each folds as f, idx}
            <tr class:fold-active={idx === foldIndex}>
              <td><button type="button" class="fold-btn" onclick={() => (foldIndex = idx)}>fold {f.fold_id}</button></td>
              <td>{num(f.brier, 4)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    {#if fold}
      <div class="table-wrap" style="margin-top:12px">
        <table>
          <thead><tr><th>bin</th><th>count</th><th>mean predicted</th><th>observed rate</th><th>reliability</th></tr></thead>
          <tbody>
            {#each fold.reliability_bins ?? [] as bin}
              <tr>
                <td>{num(bin.lo, 1)}-{num(bin.hi, 1)}</td>
                <td>{bin.count}</td>
                <td>{num(bin.mean_predicted, 3)}</td>
                <td>{num(bin.observed_rate, 3)}</td>
                <td class="bar-cell">
                  <div class="bar predicted" style="width:{barWidth(bin.mean_predicted)}"></div>
                  <div class="bar observed" style="width:{barWidth(bin.observed_rate)}"></div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <p class="text-caption" style="margin-top:6px">
        bars: top = mean predicted, bottom = observed rate (fold {fold.fold_id})
      </p>
    {/if}
  {/if}
</section>

<style>
  .fold-btn {
    border: none;
    background: none;
    padding: 0;
    color: inherit;
    cursor: pointer;
    font: inherit;
    text-decoration: underline dotted;
  }
  .fold-active td {
    background: rgba(20, 184, 166, 0.08);
  }
  .bar-cell {
    min-width: 140px;
  }
  .bar {
    height: 5px;
    border-radius: 3px;
    margin: 2px 0;
    background: var(--accent, #2563eb);
  }
  .bar.observed {
    background: var(--success, #16a34a);
  }
</style>
