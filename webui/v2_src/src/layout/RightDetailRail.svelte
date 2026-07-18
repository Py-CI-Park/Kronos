<script lang="ts">
  import { onDestroy } from 'svelte';
  import { rightDetailRailCollapsed, toggleRightDetailRailCollapsed } from '$lib/stores';
  import type { V51FalseResearchLocks, V51NoClaimFlags, V51Protocol } from '$lib/v51Api';

  type RailContract = Pick<
    V51Protocol,
    | 'api_version'
    | 'read_only'
    | 'causal_cutoff_kst'
    | 'price_basis'
    | 'official_close'
    | 'accounting'
    | 'cost_schedule'
    | 'horizon'
    | 'source_policy'
    | 'overlay_policy'
  >;

  const railContract = {
    api_version: 'v5.1',
    read_only: true,
    causal_cutoff_kst: '15:20:00',
    price_basis: '15:20_bar_close_proxy',
    official_close: false,
    accounting: {
      initial_capital_krw: 60000000,
      slot_count: 10,
      slot_budget_krw: 5000000,
      max_invested_krw: 50000000,
      reserve_cash_krw: 10000000,
      reserve_cash_display_percent: '16.6667%',
      max_target_investment_display_percent: '83.3333%',
      shorting_allowed: false,
      leverage_allowed: false,
      duplicate_symbol_slots_allowed: false,
    },
    cost_schedule: {
      primary: { internal_id: 'base_23bp', round_trip_cost_bp: 23, display_percent: '0.23%' },
      zero_cost_control: { internal_id: 'cost_00bp', round_trip_cost_bp: 0, display_percent: '0.00%' },
      stress_control: { internal_id: 'stress_46bp', round_trip_cost_bp: 46, display_percent: '0.46%' },
    },
    horizon: {
      primary_horizon: 'H1',
      validation_horizons: ['H3', 'H5'],
      label_columns: ['future_return_h1_1520_proxy', 'future_return_h3_1520_proxy', 'future_return_h5_1520_proxy'],
    },
    source_policy: {
      daily_1520_source_schema: 'kronos_daily_1520_source.v1',
      causal_panel_schema: 'kronos_daily_v51_causal_panel.v1',
      causal_cutoff_kst: '15:20:00',
      price_basis: '15:20_bar_close_proxy',
      official_close: false,
      nearest_fallback_allowed: false,
      full_day_daily_ohlcv_allowed: false,
      price_volume_amount_approximation_allowed: false,
      pykrx_offline_only: true,
      naver_fallback_allowed: false,
      network_required: false,
    },
    overlay_policy: {
      allowed_index_provider: 'PYKRX',
      offline_artifact_required: true,
      naver_fallback_allowed: false,
      forbidden_provider: 'NAVER',
      missing_index_state: 'BLOCKED_INDEX_SERIES_SOURCE',
    },
  } as const satisfies RailContract;

  const locks = {
    promotion_allowed: false,
    model_build_allowed: false,
    paper_forward_allowed: false,
    live_broker_order_allowed: false,
    profitability_claim_allowed: false,
    go_summary_allowed: false,
  } as const satisfies V51FalseResearchLocks;

  const claims = {
    official_close_claim: false,
    paper_forward_claim: false,
    live_trading_claim: false,
    broker_integration_claim: false,
    profitability_claim: false,
    go_readiness_claim: false,
  } as const satisfies V51NoClaimFlags;

  const compactStatusRows = [
    'NO-GO',
    'READ-ONLY',
    '6 LOCKS FALSE',
    'NO LIVE / PROFIT',
    'NOT_RUN ≠ result',
  ] as const;

  const lockRows = [
    { label: 'Promotion', key: 'promotion_allowed', value: locks.promotion_allowed },
    { label: 'Model build', key: 'model_build_allowed', value: locks.model_build_allowed },
    { label: 'Paper forward', key: 'paper_forward_allowed', value: locks.paper_forward_allowed },
    { label: 'Broker/live order', key: 'live_broker_order_allowed', value: locks.live_broker_order_allowed },
    { label: 'Profitability claim', key: 'profitability_claim_allowed', value: locks.profitability_claim_allowed },
    { label: 'GO summary', key: 'go_summary_allowed', value: locks.go_summary_allowed },
  ] as const;

  const claimRows = [
    { label: 'Official close', key: 'official_close_claim', value: claims.official_close_claim },
    { label: 'Paper forward', key: 'paper_forward_claim', value: claims.paper_forward_claim },
    { label: 'Live trading', key: 'live_trading_claim', value: claims.live_trading_claim },
    { label: 'Broker integration', key: 'broker_integration_claim', value: claims.broker_integration_claim },
    { label: 'Profitability', key: 'profitability_claim', value: claims.profitability_claim },
    { label: 'GO readiness', key: 'go_readiness_claim', value: claims.go_readiness_claim },
  ] as const;

  const costRows = [
    railContract.cost_schedule.primary,
    railContract.cost_schedule.zero_cost_control,
    railContract.cost_schedule.stress_control,
  ] as const;

  let collapsed = $state(false);
  const unsubscribe = rightDetailRailCollapsed.subscribe((value) => (collapsed = value));

  onDestroy(() => {
    unsubscribe();
  });
</script>

<aside class="right-detail-rail" data-collapsed={collapsed} aria-labelledby="v51-rail-title">
  <div class="rail-sticky">
    <div class="rail-control-row">
      <div class="rail-heading">
        <span class="rail-eyebrow">V5.1 guardrail</span>
        <h2 id="v51-rail-title">Right detail rail</h2>
      </div>
      <button
        type="button"
        class="rail-toggle"
        aria-expanded={!collapsed}
        aria-controls="v51-detail-rail-panel"
        onclick={toggleRightDetailRailCollapsed}
      >
        <span aria-hidden="true">{collapsed ? 'Open' : 'Close'}</span>
        <span class="sr-only">{collapsed ? 'Expand V5.1 detail rail' : 'Collapse V5.1 detail rail'}</span>
      </button>
    </div>

    <section class="compact-summary" aria-label="V5.1 blocker and status summary">
      <p class="summary-title">Research status</p>
      <div class="status-stack" aria-label="Collapsed-visible guardrails">
        {#each compactStatusRows as row}
          <span class="status-pill">{row}</span>
        {/each}
      </div>
      <p class="summary-blocker"><strong>Blocker:</strong> D0/D1/source and index evidence remain proof-bound.</p>
      <p class="summary-note">Collapsed rail still exposes NO-GO, read-only, NOT_RUN and six false locks.</p>
    </section>

    {#if collapsed}
      <div id="v51-detail-rail-panel" class="sr-only">
        Expanded V5.1 details are collapsed. The visible summary still states NO-GO, read-only, NOT_RUN and six false locks.
      </div>
    {:else}
      <div id="v51-detail-rail-panel" class="rail-panel">
        <section class="rail-card version-card" aria-labelledby="v51-version-title">
          <span class="rail-eyebrow">Kronos</span>
          <h3 id="v51-version-title">AI Quant Reinforcement Learning</h3>
          <p class="version-line">{railContract.api_version} · Updated 2026-07-17</p>
          <p class="muted">Research UI only. V3 default/routes and V4 behavior remain unchanged unless shell v5 is active.</p>
        </section>

        <section class="rail-card" aria-labelledby="v51-protocol-title">
          <h3 id="v51-protocol-title">Causal source contract</h3>
          <dl class="fact-list">
            <div><dt>Decision cutoff</dt><dd>{railContract.causal_cutoff_kst} KST</dd></div>
            <div><dt>Price basis</dt><dd>{railContract.price_basis}</dd></div>
            <div><dt>Official close</dt><dd>{String(railContract.official_close)}</dd></div>
            <div><dt>Nearest fallback</dt><dd>{String(railContract.source_policy.nearest_fallback_allowed)}</dd></div>
            <div><dt>Symbol identity</dt><dd>Six-digit strings, e.g. 000250</dd></div>
          </dl>
        </section>

        <section class="rail-card" aria-labelledby="v51-accounting-title">
          <h3 id="v51-accounting-title">Capital and costs</h3>
          <dl class="fact-list">
            <div><dt>Initial capital</dt><dd>₩60,000,000</dd></div>
            <div><dt>Slots</dt><dd>{railContract.accounting.slot_count} × ₩5,000,000</dd></div>
            <div><dt>Max invested</dt><dd>₩50,000,000 · {railContract.accounting.max_target_investment_display_percent}</dd></div>
            <div><dt>Reserve cash</dt><dd>₩10,000,000 · {railContract.accounting.reserve_cash_display_percent}</dd></div>
          </dl>
          <ul class="cost-list" aria-label="Internal cost IDs with user-facing percentages">
            {#each costRows as cost}
              <li><code>{cost.internal_id}</code><span>{cost.display_percent}</span></li>
            {/each}
          </ul>
        </section>

        <section class="rail-card" aria-labelledby="v51-horizon-title">
          <h3 id="v51-horizon-title">Horizons</h3>
          <p class="horizon-line"><span>{railContract.horizon.primary_horizon}</span><span>H3</span><span>H5</span></p>
          <p class="muted">H1 is primary; H3/H5 are validation variants using the same 15:20 proxy.</p>
        </section>

        <section class="rail-card" aria-labelledby="v51-source-title">
          <h3 id="v51-source-title">Offline source policy</h3>
          <dl class="fact-list">
            <div><dt>Index provider</dt><dd>{railContract.overlay_policy.allowed_index_provider}</dd></div>
            <div><dt>Offline artifact</dt><dd>{String(railContract.overlay_policy.offline_artifact_required)}</dd></div>
            <div><dt>PyKRX</dt><dd>offline-only</dd></div>
            <div><dt>Naver fallback</dt><dd>{String(railContract.source_policy.naver_fallback_allowed)}</dd></div>
            <div><dt>Network required</dt><dd>{String(railContract.source_policy.network_required)}</dd></div>
            <div><dt>Missing index</dt><dd>{railContract.overlay_policy.missing_index_state}</dd></div>
          </dl>
        </section>

        <section class="rail-card danger-card" aria-labelledby="v51-locks-title">
          <h3 id="v51-locks-title">Six false locks</h3>
          <ul class="lock-list">
            {#each lockRows as row}
              <li><span>{row.label}</span><code>{row.key}={String(row.value)}</code></li>
            {/each}
          </ul>
        </section>

        <section class="rail-card" aria-labelledby="v51-claims-title">
          <h3 id="v51-claims-title">No-claim facts</h3>
          <ul class="lock-list">
            {#each claimRows as row}
              <li><span>{row.label}</span><code>{row.key}={String(row.value)}</code></li>
            {/each}
          </ul>
          <p class="muted">No live trading, no broker integration, no paper-forward and no profitability claim.</p>
        </section>
      </div>
    {/if}
  </div>
</aside>

<style>
  .right-detail-rail {
    width: var(--v5-right-rail-w);
    min-width: var(--v5-right-rail-w);
    min-height: 100vh;
    background:
      linear-gradient(180deg, color-mix(in oklab, var(--surface) 96%, var(--accent-soft) 4%), var(--surface-sunken));
    border-left: 1px solid var(--border);
    color: var(--fg);
    transition: width var(--d-base) var(--ease-out), min-width var(--d-base) var(--ease-out), box-shadow var(--d-base) var(--ease-out);
  }

  .right-detail-rail[data-collapsed="true"] {
    width: var(--v5-right-rail-collapsed-w);
    min-width: var(--v5-right-rail-collapsed-w);
  }

  .rail-sticky {
    position: sticky;
    top: 0;
    max-height: 100vh;
    overflow: auto;
    overscroll-behavior: contain;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .right-detail-rail[data-collapsed="true"] .rail-sticky {
    padding: 12px 10px;
  }

  .rail-control-row,
  .rail-heading,
  .compact-summary,
  .rail-panel,
  .rail-card {
    min-width: 0;
  }

  .rail-control-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 10px;
  }

  .right-detail-rail[data-collapsed="true"] .rail-control-row {
    flex-direction: column;
  }

  .rail-heading {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .rail-heading h2,
  .rail-card h3 {
    color: var(--fg-strong);
    font-family: var(--font-display);
    letter-spacing: -0.01em;
  }

  .rail-heading h2 {
    font-size: 15px;
    line-height: 1.25;
  }

  .rail-card h3 {
    font-size: 14px;
    line-height: 1.3;
  }

  .rail-eyebrow,
  .summary-title {
    font: 700 10.5px/1.1 var(--font-display);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
  }

  .rail-toggle {
    min-height: 34px;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 7px 10px;
    background: var(--surface);
    color: var(--fg-strong);
    font: 700 11px/1 var(--font-display);
    box-shadow: var(--shadow-xs);
  }

  .rail-toggle:hover {
    border-color: var(--border-strong);
    background: var(--surface-raised);
  }

  .rail-toggle:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 3px;
  }

  .compact-summary,
  .rail-card {
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    background: color-mix(in oklab, var(--surface) 92%, transparent);
    box-shadow: var(--shadow-sm), var(--card-highlight);
  }

  .compact-summary {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 12px;
  }

  .status-stack {
    display: grid;
    gap: 6px;
  }

  .status-pill {
    display: inline-flex;
    align-items: center;
    min-height: 24px;
    border-radius: var(--r-pill);
    padding: 5px 8px;
    background: var(--danger-soft);
    color: var(--danger);
    font: 800 10.5px/1.1 var(--font-mono);
    letter-spacing: 0.01em;
    overflow-wrap: anywhere;
  }

  .status-pill:nth-child(2) {
    background: var(--info-soft);
    color: var(--info);
  }

  .status-pill:nth-child(3) {
    background: var(--warn-soft);
    color: var(--warn);
  }

  .summary-blocker,
  .summary-note,
  .muted {
    color: var(--muted);
    font-size: 12px;
    line-height: 1.45;
  }

  .summary-blocker strong {
    color: var(--fg-strong);
  }

  .rail-panel {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .rail-card {
    padding: 13px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .version-card {
    border-color: color-mix(in oklab, var(--accent) 34%, var(--border));
    background: linear-gradient(180deg, var(--surface), color-mix(in oklab, var(--accent-soft) 36%, var(--surface)));
  }

  .danger-card {
    border-color: color-mix(in oklab, var(--danger) 36%, var(--border));
  }

  .version-line {
    color: var(--accent-strong);
    font: 800 12px/1.2 var(--font-mono);
  }

  .fact-list {
    display: grid;
    gap: 8px;
  }

  .fact-list div,
  .lock-list li,
  .cost-list li {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    min-width: 0;
  }

  .fact-list dt,
  .lock-list span {
    color: var(--muted);
    font-size: 12px;
    line-height: 1.35;
  }

  .fact-list dd,
  .lock-list code,
  .cost-list code,
  .cost-list span {
    color: var(--fg-strong);
    font: 700 11px/1.35 var(--font-mono);
    text-align: right;
    overflow-wrap: anywhere;
  }

  .cost-list,
  .lock-list {
    display: grid;
    gap: 7px;
  }

  .cost-list li {
    align-items: center;
    border-radius: 9px;
    background: var(--surface-sunken);
    padding: 7px 8px;
  }

  .horizon-line {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .horizon-line span {
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    padding: 6px 9px;
    background: var(--surface-sunken);
    color: var(--fg-strong);
    font: 800 12px/1 var(--font-mono);
  }

  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  @media (max-width: 1180px), (orientation: portrait) {
    .right-detail-rail {
      position: fixed;
      top: calc(var(--header-h) + 10px);
      right: 12px;
      z-index: 25;
      width: min(var(--v5-right-rail-w), calc(100vw - 24px));
      min-width: 0;
      max-width: calc(100vw - 24px);
      min-height: 0;
      max-height: calc(100dvh - var(--header-h) - 22px);
      border: 1px solid var(--border);
      border-radius: 18px;
      box-shadow: var(--shadow-lg);
    }

    .right-detail-rail[data-collapsed="true"] {
      width: min(220px, calc(100vw - 24px));
      min-width: 0;
    }

    .rail-sticky {
      max-height: inherit;
      padding: 12px;
    }
  }

  @media (max-width: 520px) {
    .right-detail-rail {
      inset: auto 10px 10px 10px;
      width: auto;
      max-width: none;
      max-height: min(72dvh, 620px);
    }

    .right-detail-rail[data-collapsed="true"] {
      width: auto;
    }

    .rail-control-row {
      flex-direction: row;
      align-items: center;
    }

    .status-stack {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
</style>
