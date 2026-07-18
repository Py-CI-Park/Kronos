<script lang="ts" module>
  import type {
    V51AccountingContract,
    V51AccountingRoot,
    V51BenchmarkOverlayRoot,
    V51CausalPanelRoot,
    V51EvaluatorRoot,
    V51FalseResearchLocks,
    V51NoClaimFlags,
    V51OverlaySeries,
    V51Protocol,
    V51ResearchRouteId,
    V51SourceCoverageRoot,
    V51Status,
  } from '$lib/v51Api';

  export type V51PayloadBundle = {
    sourceCoverage: V51SourceCoverageRoot | null;
    causalPanel: V51CausalPanelRoot | null;
    accounting: V51AccountingRoot | null;
    evaluator: V51EvaluatorRoot | null;
    benchmarkOverlay: V51BenchmarkOverlayRoot | null;
  };

  export type V51AnyResearchRoot = NonNullable<V51PayloadBundle[keyof V51PayloadBundle]>;
  export type V51RouteErrorMap = Partial<Record<V51ResearchRouteId, string>>;

  export type V51RouteState = {
    routeId: V51ResearchRouteId;
    label: string;
    status: string;
    reason: string;
    stale: boolean;
  };

  export type V51OverlayRow = {
    seriesId: V51OverlaySeries['series_id'];
    label: string;
    status: string;
    sourceState: string;
    provider: string;
    naverUsed: string;
    index100Value: number | null;
    index100Display: string;
    cumulativeReturnDisplay: string;
  };

  export type V51TruthRow = {
    key: string;
    label: string;
    value: string;
  };

  type PayloadKey = keyof V51PayloadBundle;

  const krwFormatter = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
  const indexFormatter = new Intl.NumberFormat('en-US', { maximumFractionDigits: 6 });

  export const V51_RESEARCH_ROUTE_CARDS = [
    { routeId: 'SOURCE_COVERAGE', payloadKey: 'sourceCoverage', label: 'Source coverage' },
    { routeId: 'CAUSAL_PANEL', payloadKey: 'causalPanel', label: 'Causal panel' },
    { routeId: 'ACCOUNTING', payloadKey: 'accounting', label: 'Accounting' },
    { routeId: 'EVALUATOR', payloadKey: 'evaluator', label: 'Evaluator' },
    { routeId: 'BENCHMARK_OVERLAY', payloadKey: 'benchmarkOverlay', label: 'Benchmark overlay' },
  ] as const satisfies readonly { routeId: V51ResearchRouteId; payloadKey: PayloadKey; label: string }[];

  export const V51_OVERLAY_SERIES = ['KOSPI', 'KOSDAQ', 'RL_PORTFOLIO'] as const;

  export const V51_FALSE_LOCK_KEYS = [
    'promotion_allowed',
    'model_build_allowed',
    'paper_forward_allowed',
    'live_broker_order_allowed',
    'profitability_claim_allowed',
    'go_summary_allowed',
  ] as const satisfies readonly (keyof V51FalseResearchLocks)[];

  export const V51_NO_CLAIM_KEYS = [
    'official_close_claim',
    'paper_forward_claim',
    'live_trading_claim',
    'broker_integration_claim',
    'profitability_claim',
    'go_readiness_claim',
  ] as const satisfies readonly (keyof V51NoClaimFlags)[];

  export const V51_COST_TRUTH_LABELS = [
    'zero_control_0bp → 0.00%',
    'base_23bp → 0.23%',
    'stress_46bp → 0.46%',
  ] as const;

  export const V51_ACCOUNTING_TRUTH_LABELS = [
    '60M KRW initial capital',
    '10 slots',
    '5M KRW slot budget',
    '10M KRW reserve cash',
  ] as const;
  export const V51_MISSING_BAR_POLICY_LABEL = 'MISSING_1520_BAR_BLOCKS_ROW_NO_NEAREST_FALLBACK' as const;

  export function emptyV51PayloadBundle(): V51PayloadBundle {
    return {
      sourceCoverage: null,
      causalPanel: null,
      accounting: null,
      evaluator: null,
      benchmarkOverlay: null,
    };
  }

  export function displayStatus(status: V51Status | string | null | undefined, fallback = 'NOT_RUN'): string {
    return status == null || status === '' ? fallback : String(status);
  }

  export function displayReason(reason: string | null | undefined, fallback = 'NOT_RUN'): string {
    return reason == null || reason === '' ? fallback : reason;
  }

  export function formatKrwBudget(value: number | null | undefined): string {
    if (value == null) return 'NOT_RUN';
    if (value === 60_000_000) return '60M KRW';
    if (value === 10_000_000) return '10M KRW';
    if (value === 5_000_000) return '5M KRW';
    return `${krwFormatter.format(value)} KRW`;
  }

  export function formatBooleanFalse(value: boolean | null | undefined, falseLabel = 'false'): string {
    return value === false ? falseLabel : 'NOT_RUN';
  }

  export function formatBooleanTrue(value: boolean | null | undefined, trueLabel = 'true'): string {
    return value === true ? trueLabel : 'NOT_RUN';
  }

  export function joinValues(values: readonly string[] | null | undefined): string {
    return values?.length ? values.join(' / ') : 'NOT_RUN';
  }

  export function isSixDigitSymbol(value: string | null | undefined): boolean {
    return typeof value === 'string' && /^[0-9]{6}$/u.test(value);
  }

  export function formatSixDigitSymbol(value: string | null | undefined): string {
    if (value == null || value === '') return 'NOT_RUN';
    return isSixDigitSymbol(value) ? `${value} · six-digit` : 'BLOCKED_SYMBOL_NOT_SIX_DIGIT';
  }

  export function hasAnyResearchPayload(bundle: V51PayloadBundle): boolean {
    return Object.values(bundle).some((value) => value !== null);
  }

  export function firstLoadedRoot(bundle: V51PayloadBundle): V51AnyResearchRoot | null {
    return bundle.sourceCoverage ?? bundle.causalPanel ?? bundle.accounting ?? bundle.evaluator ?? bundle.benchmarkOverlay;
  }

  export function firstProtocol(bundle: V51PayloadBundle): V51Protocol | null {
    return firstLoadedRoot(bundle)?.protocol ?? null;
  }

  function routeRoot(bundle: V51PayloadBundle, payloadKey: PayloadKey): V51AnyResearchRoot | null {
    return bundle[payloadKey];
  }

  function routePayloadStatus(bundle: V51PayloadBundle, payloadKey: PayloadKey): string | null {
    if (payloadKey === 'sourceCoverage') return bundle.sourceCoverage?.source_coverage.coverage_status ?? null;
    if (payloadKey === 'causalPanel') return bundle.causalPanel?.status ?? null;
    if (payloadKey === 'accounting') return bundle.accounting?.accounting.accounting_status ?? null;
    if (payloadKey === 'evaluator') return bundle.evaluator?.evaluator.evaluation_status ?? null;
    return bundle.benchmarkOverlay?.benchmark_overlay.overlay_status ?? null;
  }

  export function deriveRouteStates(bundle: V51PayloadBundle, errors: V51RouteErrorMap): readonly V51RouteState[] {
    return V51_RESEARCH_ROUTE_CARDS.map((card) => {
      const root = routeRoot(bundle, card.payloadKey);
      const error = errors[card.routeId];
      return {
        routeId: card.routeId,
        label: card.label,
        status: error ? 'BLOCKED' : displayStatus(routePayloadStatus(bundle, card.payloadKey) ?? root?.status),
        reason: error ?? displayReason(root?.status_reason),
        stale: Boolean(error && root),
      };
    });
  }

  export function deriveKronosVerdictLabel(routeStates: readonly V51RouteState[]): string {
    if (routeStates.some((state) => state.status === 'BLOCKED')) return 'NO-GO / BLOCKED';
    if (routeStates.every((state) => state.status === 'READY')) return 'NO-GO / RESEARCH_READY';
    return 'NO-GO / NOT_RUN';
  }

  export function deriveRlVerdictLabel(evaluator: V51EvaluatorRoot | null, overlay: V51BenchmarkOverlayRoot | null): string {
    if (!evaluator) return 'NOT_RUN / NO-GO';
    const evaluatorBlocked = evaluator.status === 'BLOCKED' || evaluator.evaluator.evaluation_status === 'BLOCKED';
    const splitBlocked = Object.values(evaluator.evaluator.split_statuses).some((value) => value === 'BLOCKED');
    const overlayBlocked = overlay?.status === 'BLOCKED' || overlay?.benchmark_overlay.overlay_status === 'BLOCKED';
    if (evaluatorBlocked || splitBlocked || overlayBlocked) return 'NO-GO / BLOCKED';
    if (!evaluator.evaluator.metrics.length) return 'NOT_RUN / NO-GO';
    return 'NO-GO / RESEARCH_ONLY';
  }

  export function deriveMissionControlSummary(bundle: V51PayloadBundle, routeStates: readonly V51RouteState[]): readonly string[] {
    return [
      `Kronos verdict: ${deriveKronosVerdictLabel(routeStates)}`,
      `RL verdict: ${deriveRlVerdictLabel(bundle.evaluator, bundle.benchmarkOverlay)}`,
      `15:20 proxy: ${firstProtocol(bundle)?.price_basis ?? 'NOT_RUN'} / official close ${formatBooleanFalse(firstProtocol(bundle)?.official_close)}`,
      'RULE baseline remains RULE comparison only; it is never labeled RL.',
    ];
  }

  export function deriveNoClaimRows(root: V51AnyResearchRoot | null): readonly V51TruthRow[] {
    const lockRows = V51_FALSE_LOCK_KEYS.map((key) => ({
      key,
      label: `lock.${key}`,
      value: root ? String(root.locks[key]) : 'NOT_RUN',
    }));
    const claimRows = V51_NO_CLAIM_KEYS.map((key) => ({
      key,
      label: `claim.${key}`,
      value: root ? String(root.claims[key]) : 'NOT_RUN',
    }));
    return [...lockRows, ...claimRows];
  }

  function overlayLabel(seriesId: V51OverlaySeries['series_id']): string {
    if (seriesId === 'RL_PORTFOLIO') return 'RL normalized-100';
    return seriesId;
  }

  function formatIndex100(value: number | null): string {
    return value == null ? 'BLOCKED_INDEX_SERIES_SOURCE' : indexFormatter.format(value);
  }

  export function toOverlayRows(overlay: V51BenchmarkOverlayRoot | null): readonly V51OverlayRow[] {
    const seriesById = new Map<V51OverlaySeries['series_id'], V51OverlaySeries>();
    for (const series of overlay?.benchmark_overlay.series ?? []) {
      seriesById.set(series.series_id, series);
    }

    return V51_OVERLAY_SERIES.map((seriesId) => {
      const series = seriesById.get(seriesId) ?? null;
      const sourceState = series?.source_state ?? 'BLOCKED_INDEX_SERIES_SOURCE';
      const blockedDisplay = sourceState || 'BLOCKED_INDEX_SERIES_SOURCE';
      return {
        seriesId,
        label: overlayLabel(seriesId),
        status: displayStatus(series?.status, 'BLOCKED'),
        sourceState,
        provider: series?.provider ?? 'PYKRX offline artifact required',
        naverUsed: series ? String(series.naver_used) : 'false / Naver disabled',
        index100Value: series?.index_100 ?? null,
        index100Display: series?.index_100 == null ? blockedDisplay : formatIndex100(series.index_100),
        cumulativeReturnDisplay: series?.cumulative_return_display_percent ?? blockedDisplay,
      };
    });
  }

  export function overlayBarWidth(row: V51OverlayRow, rows: readonly V51OverlayRow[]): number {
    if (row.index100Value == null) return 0;
    const values = rows.flatMap((entry) => entry.index100Value == null ? [] : [entry.index100Value]);
    const maxValue = Math.max(100, ...values);
    return Math.min(100, Math.max(4, (row.index100Value / maxValue) * 100));
  }

  export function costRows(contract: V51Protocol['cost_schedule'] | null): readonly V51TruthRow[] {
    return [
      { key: 'zero_control_0bp', label: 'zero_control_0bp internal ID', value: contract?.zero_cost_control.display_percent ?? 'NOT_RUN' },
      { key: 'base_23bp', label: 'base_23bp internal ID', value: contract?.primary.display_percent ?? 'NOT_RUN' },
      { key: 'stress_46bp', label: 'stress_46bp internal ID', value: contract?.stress_control.display_percent ?? 'NOT_RUN' },
    ];
  }

  export function accountingRows(contract: V51AccountingContract | null): readonly V51TruthRow[] {
    return [
      { key: 'initial_capital_krw', label: 'Initial capital', value: formatKrwBudget(contract?.initial_capital_krw) },
      { key: 'slot_count', label: 'Slots', value: contract ? `${contract.slot_count} slots` : 'NOT_RUN' },
      { key: 'slot_budget_krw', label: 'Slot budget', value: formatKrwBudget(contract?.slot_budget_krw) },
      { key: 'reserve_cash_krw', label: 'Reserve cash', value: formatKrwBudget(contract?.reserve_cash_krw) },
    ];
  }
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import { V51ApiError, v51Api, type V51ResearchRouteId as V51RuntimeResearchRouteId } from '$lib/v51Api';

  let payloads = $state<V51PayloadBundle>(emptyV51PayloadBundle());
  let routeErrors = $state<V51RouteErrorMap>({});
  let loading = $state(false);
  let stale = $state(false);
  let loadedAt = $state<string | null>(null);
  let requestSerial = 0;

  const hasPayload = $derived(hasAnyResearchPayload(payloads));
  const activeRoot = $derived(firstLoadedRoot(payloads));
  const protocol = $derived(firstProtocol(payloads));
  const routeStates = $derived(deriveRouteStates(payloads, routeErrors));
  const kronosVerdict = $derived(deriveKronosVerdictLabel(routeStates));
  const rlVerdict = $derived(deriveRlVerdictLabel(payloads.evaluator, payloads.benchmarkOverlay));
  const missionSummary = $derived(deriveMissionControlSummary(payloads, routeStates));
  const noClaimRows = $derived(deriveNoClaimRows(activeRoot));
  const sourcePayload = $derived(payloads.sourceCoverage?.source_coverage ?? null);
  const causalPayload = $derived(payloads.causalPanel?.causal_panel ?? null);
  const accountingContract = $derived(payloads.accounting?.accounting.contract ?? protocol?.accounting ?? null);
  const schedule = $derived(payloads.accounting?.accounting.cost_schedule ?? payloads.evaluator?.evaluator.cost_schedule ?? protocol?.cost_schedule ?? null);
  const costTruthRows = $derived(costRows(schedule));
  const accountingTruthRows = $derived(accountingRows(accountingContract));
  const sourcePolicy = $derived(protocol?.source_policy ?? null);
  const overlayPolicy = $derived(payloads.benchmarkOverlay?.benchmark_overlay.provider_policy ?? protocol?.overlay_policy ?? null);
  const overlayRows = $derived(toOverlayRows(payloads.benchmarkOverlay));
  const overlayUnavailable = $derived(overlayRows.every((row) => row.index100Value == null));
  const routeErrorRows = $derived(Object.entries(routeErrors).map(([routeId, message]) => ({ routeId, message })));

  onMount(() => {
    void loadResearchEvidence();
  });

  function formatRouteError(routeId: V51RuntimeResearchRouteId, caught: unknown): string {
    if (caught instanceof V51ApiError) {
      const status = caught.status == null ? 'no-http-status' : `http-${caught.status}`;
      return `${caught.routeId} ${caught.code} ${status}: ${caught.message}`;
    }
    if (caught instanceof Error) return `${routeId} ERROR: ${caught.message}`;
    return `${routeId} ERROR: ${String(caught)}`;
  }

  function applySettlement<K extends keyof V51PayloadBundle>(
    routeId: V51RuntimeResearchRouteId,
    key: K,
    result: PromiseSettledResult<NonNullable<V51PayloadBundle[K]>>,
    nextPayloads: V51PayloadBundle,
    nextErrors: V51RouteErrorMap,
  ): void {
    if (result.status === 'fulfilled') {
      nextPayloads[key] = result.value as V51PayloadBundle[K];
      return;
    }
    nextErrors[routeId] = formatRouteError(routeId, result.reason);
  }

  async function loadResearchEvidence(): Promise<void> {
    const requestId = ++requestSerial;
    const hadPayload = hasAnyResearchPayload(payloads);
    loading = true;
    stale = hadPayload;
    if (!hadPayload) routeErrors = {};

    try {
      const [sourceResult, causalResult, accountingResult, evaluatorResult, overlayResult] = await Promise.allSettled([
        v51Api.sourceCoverage(),
        v51Api.causalPanel(),
        v51Api.accounting(),
        v51Api.evaluator(),
        v51Api.benchmarkOverlay(),
      ] as const);
      if (requestId !== requestSerial) return;

      const nextPayloads: V51PayloadBundle = { ...payloads };
      const nextErrors: V51RouteErrorMap = {};
      applySettlement('SOURCE_COVERAGE', 'sourceCoverage', sourceResult, nextPayloads, nextErrors);
      applySettlement('CAUSAL_PANEL', 'causalPanel', causalResult, nextPayloads, nextErrors);
      applySettlement('ACCOUNTING', 'accounting', accountingResult, nextPayloads, nextErrors);
      applySettlement('EVALUATOR', 'evaluator', evaluatorResult, nextPayloads, nextErrors);
      applySettlement('BENCHMARK_OVERLAY', 'benchmarkOverlay', overlayResult, nextPayloads, nextErrors);

      payloads = nextPayloads;
      routeErrors = nextErrors;
      loadedAt = new Date().toISOString();
      stale = Object.keys(nextErrors).length > 0 && hasAnyResearchPayload(nextPayloads);
    } finally {
      if (requestId === requestSerial) loading = false;
    }
  }
</script>

<section class="v51-research card" data-v51-research-evidence aria-labelledby="v51-research-title">
  <div class="v51-hero">
    <div>
      <div class="text-eyebrow">V5.1 research evidence · shell v5 only</div>
      <h2 id="v51-research-title" class="text-h3">15:20 proxy evidence overlay</h2>
      <p class="text-muted">
        Read-only V5.1 evidence uses the v51Api causal/source/accounting/evaluator/benchmark routes.
        It is not official close evidence, not broker/order/account integration, and not a profitability claim.
      </p>
    </div>
    <button class="btn ghost" type="button" onclick={() => void loadResearchEvidence()} disabled={loading} data-v51-refresh>
      {loading ? 'LOADING' : 'Refresh read-only evidence'}
    </button>
  </div>

  <div class="state-strip" role="status" aria-live="polite" data-v51-readonly-state>
    <span class="state-chip safe">READ_ONLY</span>
    <span class="state-chip">{loading ? 'LOADING' : hasPayload ? 'LOADED' : 'NOT_RUN'}</span>
    {#if stale}
      <span class="state-chip warn">STALE</span>
    {/if}
    <span class="state-chip danger">NO-GO</span>
    <span class="state-chip">official_close=false</span>
    <span class="state-chip">updated {loadedAt ?? 'NOT_RUN'}</span>
  </div>

  {#if loading && !hasPayload}
    <div class="state-panel" role="status" data-v51-loading-state>
      LOADING · fetching SOURCE_COVERAGE / CAUSAL_PANEL / ACCOUNTING / EVALUATOR / BENCHMARK_OVERLAY with GET only.
    </div>
  {/if}

  {#if routeErrorRows.length}
    <div class="state-panel error" role="alert" data-v51-error-state>
      <strong>BLOCKED route errors</strong>
      <ul>
        {#each routeErrorRows as item (item.routeId)}
          <li><span class="text-mono">{item.routeId}</span> — {item.message}</li>
        {/each}
      </ul>
    </div>
  {/if}

  {#if stale}
    <div class="state-panel stale" role="status" data-v51-stale-state>
      STALE · cached read-only evidence remains visible while the latest refresh is pending or partially BLOCKED.
    </div>
  {/if}

  <div class="verdict-grid">
    <article class="verdict-card" data-v51-kronos-verdict>
      <div class="text-eyebrow">Kronos verdict</div>
      <h3>{kronosVerdict}</h3>
      <p class="text-muted">Kronos stays NO-GO unless every source route is usable and separate promotion locks remain false.</p>
    </article>
    <article class="verdict-card" data-v51-rl-verdict>
      <div class="text-eyebrow">RL verdict</div>
      <h3>{rlVerdict}</h3>
      <p class="text-muted">Evaluator evidence is research-only. RULE baseline remains RULE comparison only; it is never labeled RL.</p>
    </article>
    <article class="verdict-card" data-v51-mission-control-summary>
      <div class="text-eyebrow">Mission Control summary</div>
      <ul>
        {#each missionSummary as item}
          <li>{item}</li>
        {/each}
      </ul>
    </article>
  </div>

  <div class="route-grid" aria-label="V5.1 route states">
    {#each routeStates as state (state.routeId)}
      <article class="route-card" class:blocked={state.status === 'BLOCKED'} class:stale={state.stale}>
        <span class="text-eyebrow">{state.routeId}</span>
        <strong>{state.label}</strong>
        <span class="state-chip" class:danger={state.status === 'BLOCKED'}>{state.status}</span>
        <span class="reason">{state.reason}</span>
        {#if state.stale}
          <span class="state-chip warn">STALE CACHE</span>
        {/if}
      </article>
    {/each}
  </div>

  <div class="evidence-grid">
    <article class="evidence-card" data-v51-source-card>
      <div class="panel-head compact">
        <div>
          <div class="text-eyebrow">Source coverage</div>
          <h3>15:20 proxy source · not official close</h3>
        </div>
        <span class="state-chip">{displayStatus(sourcePayload?.coverage_status)}</span>
      </div>
      <dl class="fact-grid">
        <div><dt>Price basis</dt><dd>{sourcePayload?.missing_policy ? '15:20_bar_close_proxy' : protocol?.price_basis ?? 'NOT_RUN'}</dd></div>
        <div><dt>Official close</dt><dd>{formatBooleanFalse(protocol?.official_close, 'false / not official close')}</dd></div>
        <div><dt>Exact 15:20 rows</dt><dd>{sourcePayload?.exact_1520_row_count ?? 'NOT_RUN'}</dd></div>
        <div><dt>Six-digit symbols</dt><dd>{sourcePayload?.symbol_count ?? 'NOT_RUN'} · sample {formatSixDigitSymbol(sourcePayload?.sample_symbol)}</dd></div>
        <div><dt>Sessions</dt><dd>{sourcePayload?.session_count ?? 'NOT_RUN'}</dd></div>
        <div><dt>Sample timestamp</dt><dd>{sourcePayload?.sample_timestamp_yyyymmddhhmm ?? 'NOT_RUN'}</dd></div>
        <div><dt>Missing bars</dt><dd>{sourcePayload?.missing_policy ?? 'NOT_RUN'}</dd></div>
        <div><dt>Volume to 15:20</dt><dd>{sourcePayload?.volume_to_1520_status ?? 'NOT_RUN'}</dd></div>
        <div><dt>Amount approximation</dt><dd>{sourcePayload?.amount_to_1520_status ?? 'NOT_RUN'}</dd></div>
        <div><dt>pykrx policy</dt><dd>{formatBooleanTrue(sourcePolicy?.pykrx_offline_only, 'true / pykrx offline only')}</dd></div>
        <div><dt>Naver fallback</dt><dd>{formatBooleanFalse(sourcePolicy?.naver_fallback_allowed, 'false / Naver disabled')}</dd></div>
        <div><dt>Network required</dt><dd>{formatBooleanFalse(sourcePolicy?.network_required, 'false / offline artifact')}</dd></div>
      </dl>
    </article>

    <article class="evidence-card" data-v51-causal-card>
      <div class="panel-head compact">
        <div>
          <div class="text-eyebrow">Causal panel</div>
          <h3>H1 primary · H3/H5 validation</h3>
        </div>
        <span class="state-chip">{displayStatus(payloads.causalPanel?.status)}</span>
      </div>
      <dl class="fact-grid">
        <div><dt>Panel schema</dt><dd>{causalPayload?.panel_schema ?? 'NOT_RUN'}</dd></div>
        <div><dt>Rows</dt><dd>{causalPayload?.row_count ?? 'NOT_RUN'}</dd></div>
        <div><dt>Cutoff</dt><dd>{protocol?.causal_cutoff_kst ?? 'NOT_RUN'} KST</dd></div>
        <div><dt>Basis</dt><dd>{causalPayload?.price_basis ?? protocol?.price_basis ?? 'NOT_RUN'} · official close {formatBooleanFalse(causalPayload?.official_close ?? protocol?.official_close)}</dd></div>
        <div><dt>Primary horizon</dt><dd>{causalPayload?.primary_horizon ?? protocol?.horizon.primary_horizon ?? 'NOT_RUN'}</dd></div>
        <div><dt>Validation horizons</dt><dd>{joinValues(causalPayload?.validation_horizons ?? protocol?.horizon.validation_horizons)}</dd></div>
        <div class="wide"><dt>Label columns</dt><dd>{joinValues(causalPayload?.label_columns ?? protocol?.horizon.label_columns)}</dd></div>
      </dl>
      {#if causalPayload?.rows_preview.length}
        <div class="table-wrap">
          <table>
            <caption>Causal preview rows with six-digit symbols and 15:20 proxy statuses</caption>
            <thead>
              <tr><th>Symbol</th><th>Session</th><th>Timestamp KST</th><th>Entry</th><th>H1</th><th>H3</th><th>H5</th></tr>
            </thead>
            <tbody>
              {#each causalPayload.rows_preview as row (`${row.symbol}-${row.session_date}-${row.timestamp_kst}`)}
                <tr>
                  <td>{formatSixDigitSymbol(row.symbol)}</td>
                  <td>{row.session_date}</td>
                  <td>{row.timestamp_kst}</td>
                  <td>{row.entry_status}</td>
                  <td>{row.h1_status}</td>
                  <td>{row.h3_status}</td>
                  <td>{row.h5_status}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {:else}
        <p class="fallback">NOT_RUN · no causal preview rows available; no symbols or labels are invented.</p>
      {/if}
    </article>

    <article class="evidence-card" data-v51-accounting-card>
      <div class="panel-head compact">
        <div>
          <div class="text-eyebrow">Accounting and cost schedule</div>
          <h3>60M / 10 slots / 5M budget / 10M reserve</h3>
        </div>
        <span class="state-chip">{displayStatus(payloads.accounting?.accounting.accounting_status)}</span>
      </div>
      <dl class="fact-grid">
        {#each accountingTruthRows as row (row.key)}
          <div><dt>{row.label}</dt><dd>{row.value}</dd></div>
        {/each}
        <div><dt>Max invested</dt><dd>{formatKrwBudget(accountingContract?.max_invested_krw)}</dd></div>
        <div><dt>Shorting</dt><dd>{formatBooleanFalse(accountingContract?.shorting_allowed)}</dd></div>
        <div><dt>Leverage</dt><dd>{formatBooleanFalse(accountingContract?.leverage_allowed)}</dd></div>
        <div><dt>Duplicate slots</dt><dd>{formatBooleanFalse(accountingContract?.duplicate_symbol_slots_allowed)}</dd></div>
        <div><dt>Active internal cost</dt><dd>{payloads.accounting?.accounting.internal_cost_id ?? 'NOT_RUN'} → {payloads.accounting?.accounting.display_cost_percent ?? 'NOT_RUN'}</dd></div>
      </dl>
      <div class="cost-grid" aria-label="Internal cost IDs with user-facing percentages">
        {#each costTruthRows as row (row.key)}
          <div><span class="text-mono">{row.label}</span><strong>{row.value}</strong></div>
        {/each}
      </div>
    </article>

    <article class="evidence-card" data-v51-evaluator-card>
      <div class="panel-head compact">
        <div>
          <div class="text-eyebrow">Evaluator</div>
          <h3>RL verdict · NO-GO unless independently proven</h3>
        </div>
        <span class="state-chip" class:danger={payloads.evaluator?.evaluator.evaluation_status === 'BLOCKED'}>{displayStatus(payloads.evaluator?.evaluator.evaluation_status)}</span>
      </div>
      <dl class="fact-grid">
        <div><dt>Primary horizon</dt><dd>{payloads.evaluator?.evaluator.primary_horizon ?? protocol?.horizon.primary_horizon ?? 'NOT_RUN'}</dd></div>
        <div><dt>Validation horizons</dt><dd>{joinValues(payloads.evaluator?.evaluator.validation_horizons ?? protocol?.horizon.validation_horizons)}</dd></div>
        <div><dt>Train split</dt><dd>{displayStatus(payloads.evaluator?.evaluator.split_statuses.train)}</dd></div>
        <div><dt>Validation split</dt><dd>{displayStatus(payloads.evaluator?.evaluator.split_statuses.validation)}</dd></div>
        <div><dt>Test split</dt><dd>{displayStatus(payloads.evaluator?.evaluator.split_statuses.test)}</dd></div>
        <div><dt>Rule baseline label</dt><dd>RULE comparison only · NOT RL</dd></div>
      </dl>
      {#if payloads.evaluator?.evaluator.metrics.length}
        <div class="table-wrap">
          <table>
            <caption>Evaluator metrics use internal cost IDs and user-facing cost percentages</caption>
            <thead>
              <tr><th>Metric</th><th>Split</th><th>Horizon</th><th>Cost ID</th><th>Cost</th><th>Value</th><th>Display</th></tr>
            </thead>
            <tbody>
              {#each payloads.evaluator.evaluator.metrics as metric (`${metric.metric_id}-${metric.split}-${metric.horizon}-${metric.internal_cost_id}`)}
                <tr>
                  <td>{metric.metric_id}</td>
                  <td>{metric.split}</td>
                  <td>{metric.horizon}</td>
                  <td>{metric.internal_cost_id}</td>
                  <td>{metric.display_cost_percent}</td>
                  <td>{metric.value}</td>
                  <td>{metric.display_percent}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {:else}
        <p class="fallback">NOT_RUN · evaluator metrics unavailable; no RL score or profitability value is invented.</p>
      {/if}
    </article>

    <article class="evidence-card wide-card" data-v51-overlay-card>
      <div class="panel-head compact">
        <div>
          <div class="text-eyebrow">Benchmark overlay</div>
          <h3>KOSPI / KOSDAQ / RL normalized-100</h3>
        </div>
        <span class="state-chip" class:danger={payloads.benchmarkOverlay?.benchmark_overlay.overlay_status === 'BLOCKED'}>{displayStatus(payloads.benchmarkOverlay?.benchmark_overlay.overlay_status)}</span>
      </div>
      <dl class="fact-grid">
        <div><dt>Common start</dt><dd>{payloads.benchmarkOverlay?.benchmark_overlay.common_start_index ?? 'NOT_RUN'}</dd></div>
        <div><dt>Provider</dt><dd>{overlayPolicy?.allowed_index_provider ?? 'NOT_RUN'} · offline artifact required {formatBooleanTrue(overlayPolicy?.offline_artifact_required)}</dd></div>
        <div><dt>Naver fallback</dt><dd>{formatBooleanFalse(overlayPolicy?.naver_fallback_allowed, 'false / Naver disabled')}</dd></div>
        <div><dt>Missing index state</dt><dd>{overlayPolicy?.missing_index_state ?? 'BLOCKED_INDEX_SERIES_SOURCE'}</dd></div>
      </dl>
      {#if overlayUnavailable}
        <p class="fallback" data-v51-overlay-blocked-fallback>
          BLOCKED_INDEX_SERIES_SOURCE · normalized-100 KOSPI/KOSDAQ/RL overlay unavailable; no index values are invented.
        </p>
      {/if}
      <div class="overlay-bars" aria-hidden="true">
        {#each overlayRows as row (row.seriesId)}
          <div class="overlay-bar-row" class:blocked={row.index100Value == null}>
            <span class="bar-label">{row.label}</span>
            {#if row.index100Value == null}
              <span class="bar-missing">{row.index100Display}</span>
            {:else}
              <span class="bar-track">
                <span class="bar-fill" style={`width:${overlayBarWidth(row, overlayRows)}%`}></span>
                <span class="bar-value">{row.index100Display}</span>
              </span>
            {/if}
          </div>
        {/each}
      </div>
      <div class="table-wrap">
        <table>
          <caption>Accessible fallback table for KOSPI, KOSDAQ, and RL normalized-100 overlay</caption>
          <thead>
            <tr><th>Series</th><th>Status</th><th>Source state</th><th>Provider</th><th>Naver used</th><th>Index 100</th><th>Cumulative return</th></tr>
          </thead>
          <tbody>
            {#each overlayRows as row (row.seriesId)}
              <tr>
                <td>{row.label}</td>
                <td>{row.status}</td>
                <td>{row.sourceState}</td>
                <td>{row.provider}</td>
                <td>{row.naverUsed}</td>
                <td>{row.index100Display}</td>
                <td>{row.cumulativeReturnDisplay}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </article>

    <article class="evidence-card wide-card" data-v51-no-claim-guardrail>
      <div class="panel-head compact">
        <div>
          <div class="text-eyebrow">No-claim guardrails</div>
          <h3>Six false locks · no official close / paper / live / profit / GO claims</h3>
        </div>
        <span class="state-chip danger">NO-GO</span>
      </div>
      <div class="claim-grid">
        {#each noClaimRows as row (row.key)}
          <div>
            <span>{row.label}</span>
            <strong>{row.value}</strong>
          </div>
        {/each}
      </div>
      <p class="text-muted">
        False values are displayed as evidence constraints, not permissions. Missing guardrail payloads render NOT_RUN.
      </p>
    </article>
  </div>
</section>

<style>
  .v51-research {
    display: grid;
    gap: 16px;
    border-color: rgba(20, 184, 166, 0.35);
    background:
      linear-gradient(135deg, rgba(20, 184, 166, 0.08), rgba(59, 130, 246, 0.04)),
      var(--surface);
  }

  .v51-hero,
  .panel-head {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: flex-start;
  }

  .panel-head.compact {
    margin-bottom: 12px;
  }

  .panel-head h3,
  .verdict-card h3 {
    margin: 4px 0 0;
  }

  .state-strip,
  .route-grid,
  .verdict-grid,
  .evidence-grid,
  .fact-grid,
  .cost-grid,
  .claim-grid {
    display: grid;
    gap: 10px;
  }

  .state-strip {
    grid-template-columns: repeat(auto-fit, minmax(120px, max-content));
    align-items: center;
  }

  .state-chip {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: fit-content;
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 4px 9px;
    background: rgba(148, 163, 184, 0.08);
    color: var(--muted);
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.02em;
  }

  .state-chip.safe {
    border-color: rgba(20, 184, 166, 0.45);
    color: #14b8a6;
  }

  .state-chip.warn {
    border-color: rgba(245, 158, 11, 0.5);
    color: #f59e0b;
  }

  .state-chip.danger {
    border-color: rgba(239, 68, 68, 0.5);
    color: #ef4444;
  }

  .state-panel {
    border: 1px dashed var(--border);
    border-radius: 14px;
    padding: 12px;
    color: var(--muted);
    background: rgba(148, 163, 184, 0.07);
  }

  .state-panel.error {
    border-color: rgba(239, 68, 68, 0.45);
    color: #ef4444;
  }

  .state-panel.stale {
    border-color: rgba(245, 158, 11, 0.45);
    color: #f59e0b;
  }

  .verdict-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .verdict-card,
  .route-card,
  .evidence-card {
    border: 1px solid var(--border);
    border-radius: 16px;
    background: var(--surface);
    padding: 14px;
    min-width: 0;
  }

  .verdict-card ul {
    margin: 8px 0 0;
    padding-left: 18px;
    color: var(--muted);
  }

  .route-grid {
    grid-template-columns: repeat(5, minmax(0, 1fr));
  }

  .route-card {
    display: grid;
    gap: 8px;
  }

  .route-card.blocked {
    border-color: rgba(239, 68, 68, 0.45);
  }

  .route-card.stale {
    border-style: dashed;
  }

  .route-card .reason {
    color: var(--muted);
    font-size: 12px;
    overflow-wrap: anywhere;
  }

  .evidence-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .wide-card {
    grid-column: 1 / -1;
  }

  .fact-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .fact-grid div,
  .cost-grid div,
  .claim-grid div {
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 10px;
    background: rgba(148, 163, 184, 0.06);
    min-width: 0;
  }

  .fact-grid div.wide {
    grid-column: 1 / -1;
  }

  dt,
  .cost-grid span,
  .claim-grid span {
    display: block;
    color: var(--muted);
    font-size: 12px;
    margin-bottom: 4px;
  }

  dd {
    margin: 0;
    font-weight: 700;
    overflow-wrap: anywhere;
  }

  .cost-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    margin-top: 12px;
  }

  .claim-grid {
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  }

  .table-wrap {
    margin-top: 12px;
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    min-width: 680px;
  }

  caption {
    text-align: left;
    color: var(--muted);
    font-size: 12px;
    margin-bottom: 6px;
  }

  th,
  td {
    border-bottom: 1px solid var(--border);
    padding: 8px;
    text-align: left;
    vertical-align: top;
  }

  th {
    color: var(--muted);
    font-size: 12px;
  }

  .fallback {
    border: 1px dashed rgba(239, 68, 68, 0.4);
    border-radius: 12px;
    padding: 10px;
    color: #ef4444;
    background: rgba(239, 68, 68, 0.06);
  }

  .overlay-bars {
    display: grid;
    gap: 10px;
    margin-top: 12px;
  }

  .overlay-bar-row {
    display: grid;
    grid-template-columns: minmax(120px, 180px) minmax(0, 1fr);
    gap: 10px;
    align-items: center;
  }

  .bar-label {
    font-weight: 700;
  }

  .bar-track,
  .bar-missing {
    position: relative;
    min-height: 28px;
    border: 1px solid var(--border);
    border-radius: 999px;
    overflow: hidden;
    background: rgba(15, 23, 42, 0.18);
  }

  .bar-fill {
    position: absolute;
    inset: 0 auto 0 0;
    border-radius: inherit;
    background: linear-gradient(90deg, rgba(20, 184, 166, 0.45), rgba(59, 130, 246, 0.55));
  }

  .bar-value,
  .bar-missing {
    display: flex;
    align-items: center;
    padding: 0 10px;
    font-weight: 700;
  }

  .bar-value {
    position: relative;
    z-index: 1;
  }

  .bar-missing {
    color: #ef4444;
    border-style: dashed;
  }

  @media (min-width: 1600px) {
    .evidence-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .wide-card {
      grid-column: span 3;
    }
  }

  @media (max-width: 1100px) {
    .verdict-grid,
    .route-grid,
    .evidence-grid {
      grid-template-columns: 1fr;
    }

    .wide-card {
      grid-column: auto;
    }
  }

  @media (max-width: 700px) {
    .v51-hero,
    .panel-head,
    .overlay-bar-row {
      grid-template-columns: 1fr;
      display: grid;
    }

    .fact-grid,
    .cost-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
