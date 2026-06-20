<script lang="ts">
  import { onMount } from 'svelte';
  import {
    rlApi,
    type RlFactoryModelBuildReadinessResponse,
    type RlFactoryFreshValidationRun,
    type RlFactoryReadinessStep,
    type RlFactoryRiskPolicyRun,
  } from '$lib/rlApi';
  import { num, pct } from '$lib/rlRows';

  let readiness = $state<RlFactoryModelBuildReadinessResponse | null>(null);
  let riskRuns = $state<readonly RlFactoryRiskPolicyRun[]>([]);
  let freshRuns = $state<readonly RlFactoryFreshValidationRun[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  const steps = $derived<readonly RlFactoryReadinessStep[]>(readiness?.readiness_steps ?? []);
  const selectedPolicies = $derived((readiness?.selected_policy_ids ?? []).join(', ') || '-');

  onMount(() => {
    void load();
  });

  async function load(): Promise<void> {
    loading = true;
    error = null;
    try {
      const [readinessPayload, riskPayload, freshPayload] = await Promise.all([
        rlApi.factoryModelBuildReadiness(),
        rlApi.factoryRiskPolicyRuns(),
        rlApi.factoryFreshValidationRuns(),
      ]);
      readiness = readinessPayload;
      riskRuns = riskPayload?.runs?.length ? riskPayload.runs : readinessPayload?.risk_policy_runs ?? [];
      freshRuns = freshPayload?.runs?.length ? freshPayload.runs : readinessPayload?.fresh_validation_runs ?? [];
    } catch (caught) {
      error = caught instanceof Error ? caught.message : 'model build readiness load failed';
    } finally {
      loading = false;
    }
  }

  function tone(status?: string | null): string {
    const value = String(status ?? '').toUpperCase();
    if (value.includes('PASS') || value.includes('READY')) return 'success';
    if (value.includes('CANDIDATE') || value.includes('PARTIAL') || value.includes('REQUIRED')) return 'warn';
    if (value.includes('LOCKED') || value.includes('FAIL') || value.includes('BLOCK')) return 'danger';
    return 'info';
  }
</script>

<section class="card" data-rl-model-build-readiness-card>
  <div class="card-header">
    <div>
      <div class="card-eyebrow">MODEL BUILD READINESS · RL LOCK</div>
      <div class="card-title">Actual RL implementation gate from P1-P4 evidence</div>
    </div>
    <span class="pill {tone(readiness?.restricted_rl_status)}">
      <span class="dot"></span>{readiness?.restricted_rl_status ?? 'CHECKING'}
    </span>
  </div>
  <p class="text-caption safety-note">
    Risk-policy 후보는 deterministic operations design이며 강화학습 모델이 아닙니다. 기존 full OOS를 보고 선택했기 때문에 fresh OOS/forward 재검증 전 상태는 LOCKED_FRESH_OOS_FORWARD_REQUIRED입니다. No profit claim, no live/broker/order readiness, 23bp cost, ts_imb RULE baseline.
  </p>
  {#if loading}
    <p class="text-muted">Loading model-build readiness...</p>
  {:else if error}
    <p class="text-muted">{error}</p>
  {:else if readiness}
    <div class="mini-grid" style="margin-top:12px">
      <div><span>Overall</span><strong>{readiness.status ?? '-'}</strong></div>
      <div><span>P1 fill modes</span><strong>{readiness.p1_status ?? '-'}</strong></div>
      <div><span>Original P2</span><strong>{readiness.original_p2_status ?? '-'}</strong></div>
      <div><span>Risk P2 candidate</span><strong>{readiness.risk_policy_status ?? '-'}</strong></div>
      <div><span>Fresh validation</span><strong>{readiness.fresh_validation_status ?? '-'}</strong></div>
      <div><span>Selected policy</span><strong>{selectedPolicies}</strong></div>
      <div><span>Cost</span><strong>{readiness.cost_bps ?? '-'}bp</strong></div>
    </div>

    <div class="table-wrap readiness-wrap" style="margin-top:12px">
      <table>
        <thead><tr><th>step</th><th>status</th><th>evidence</th></tr></thead>
        <tbody>
          {#each steps as step}
            <tr>
              <td class="step-cell">{step.id} · {step.label}</td>
              <td><span class="pill {tone(step.status)}">{step.status}</span></td>
              <td>{step.evidence ?? '-'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <div class="table-wrap risk-policy-wrap" style="margin-top:12px">
      <table>
        <thead>
          <tr><th>fill</th><th>policy</th><th>P2 candidate</th><th>unlocked</th><th>total Δ</th><th>maxDD Δ</th><th>mean/std Δ</th><th>trades</th><th>halted sessions</th></tr>
        </thead>
        <tbody>
          {#each riskRuns.slice(0, 6) as run}
            <tr>
              <td>{run.fill_mode ?? '-'}</td>
              <td class="policy-cell">{run.best_policy_id ?? run.run}</td>
              <td><span class="pill {run.candidate_p2_pass ? 'success' : 'danger'}">{run.verdict ?? '-'}</span></td>
              <td><span class="pill {run.implementation_unlocked ? 'success' : 'danger'}">{run.implementation_unlocked ? 'UNLOCKED' : 'LOCKED'}</span></td>
              <td>{pct(run.total_pct_delta, 3)}</td>
              <td>{pct(run.max_drawdown_delta, 3)}</td>
              <td>{num(run.risk_adjusted_delta, 3)}</td>
              <td>{run.candidate_trade_count ?? '-'} / {run.baseline_trade_count ?? '-'}</td>
              <td>{run.sessions_halted ?? '-'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <div class="table-wrap fresh-validation-wrap" style="margin-top:12px" data-rl-fresh-validation-table>
      <table>
        <thead>
          <tr><th>fill</th><th>scope</th><th>fresh gate</th><th>unlocked</th><th>total Δ</th><th>maxDD Δ</th><th>mean/std Δ</th><th>trades</th><th>min trades</th></tr>
        </thead>
        <tbody>
          {#if freshRuns.length}
            {#each freshRuns.slice(0, 6) as run}
              <tr>
                <td>{run.fill_mode ?? '-'}</td>
                <td>{run.validation_scope ?? '-'}</td>
                <td><span class="pill {run.fresh_validation_pass ? 'success' : 'danger'}">{run.verdict ?? '-'}</span></td>
                <td><span class="pill {run.implementation_unlocked ? 'success' : 'danger'}">{run.implementation_unlocked ? 'UNLOCKED' : 'LOCKED'}</span></td>
                <td>{pct(run.total_pct_delta, 3)}</td>
                <td>{pct(run.max_drawdown_delta, 3)}</td>
                <td>{num(run.risk_adjusted_delta, 3)}</td>
                <td>{run.policy_trade_count ?? '-'} / {run.baseline_trade_count ?? '-'}</td>
                <td>{run.min_trades ?? '-'}</td>
              </tr>
            {/each}
          {:else}
            <tr>
              <td colspan="9" class="text-muted">FRESH_VALIDATION_REQUIRED: no frozen fresh_oos/fresh_forward validation summaries found.</td>
            </tr>
          {/if}
        </tbody>
      </table>
    </div>

    <p class="text-caption" style="margin-top:8px">{readiness.selection_bias_note}</p>
    {#if readiness.unlock_requirements?.length}
      <ul class="unlock-list">
        {#each readiness.unlock_requirements as item}
          <li>{item}</li>
        {/each}
      </ul>
    {/if}
  {:else}
    <p class="text-muted">No model-build readiness payload.</p>
  {/if}
</section>

<style>
  .readiness-wrap,
  .risk-policy-wrap,
  .fresh-validation-wrap { max-height: 320px; overflow: auto; }
  .step-cell { min-width: 190px; }
  .policy-cell { max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .unlock-list { margin: 8px 0 0; padding-left: 18px; color: var(--text-muted); font-size: 12px; line-height: 1.55; }
</style>
