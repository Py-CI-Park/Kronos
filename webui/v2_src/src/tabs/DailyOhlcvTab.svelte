<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';
  import {
    dailyOhlcvApi,
    type DailyArtifactsResponse,
    type DailyDatasetChartResponse,
    type DailyCloseSlotArtifactsResponse,
    type DailyCloseSlotEquityResponse,
    type DailyCloseSlotLatestResponse,
    type DailyCloseSlotSelectionResponse,
    type DailyDatasetResponse,
    type DailyDbSummaryResponse,
    type DailyModelChartResponse,
    type DailyPortfolioResponse,
    type DailyPredictionResponse,
    type DailyProgressResponse,
    type DailyRegistryResponse,
    type DailyScenarioLabResponse,
    type DailyScenarioRunLedgerResponse,
    type DailySymbolResponse,
    type DailyUniverseResponse,
    type DailyVisualChartResponse,
    type DailyWalkForwardResponse,
  } from '$lib/dailyOhlcvApi';
  import DailyProgressTimeline from './dailyOhlcv/DailyProgressTimeline.svelte';
  import DailyDbQualityCard from './dailyOhlcv/DailyDbQualityCard.svelte';
  import DailyUniverseCard from './dailyOhlcv/DailyUniverseCard.svelte';
  import DailyDatasetBuilderCard from './dailyOhlcv/DailyDatasetBuilderCard.svelte';
  import DailyModelResultsCard from './dailyOhlcv/DailyModelResultsCard.svelte';
  import DailyVisualLabCard from './dailyOhlcv/DailyVisualLabCard.svelte';
  import DailyScenarioLabCard from './dailyOhlcv/DailyScenarioLabCard.svelte';
  import DailyScenarioRunLedgerCard from './dailyOhlcv/DailyScenarioRunLedgerCard.svelte';
  import DailyCloseSlotCard from './dailyOhlcv/DailyCloseSlotCard.svelte';
  import CloseSlotAgentScreen from './dailyOhlcv/CloseSlotAgentScreen.svelte';
  import DailyGateLadder from './dailyOhlcv/DailyGateLadder.svelte';
  import ResearchStatusShell from './ResearchStatusShell.svelte';
  import Disclosure from '$lib/Disclosure.svelte';
  import { createRequestGate } from '$lib/requestGate';
  import { createCardRequestManager, type CardRequestState } from '$lib/cardRequest';
  import { dashboardShell, type DashboardShell } from '$lib/shellMode';
  import {
    V51ApiError,
    fetchV51Accounting,
    fetchV51CausalPanel,
    fetchV51SourceCoverage,
    type V51AccountingRoot,
    type V51CausalPanelRoot,
    type V51FalseResearchLocks,
    type V51NoClaimFlags,
    type V51ResearchRouteId,
    type V51SourceCoverageRoot,
  } from '$lib/v51Api';

  let progress = $state<DailyProgressResponse | null>(null);
  let dbSummary = $state<DailyDbSummaryResponse | null>(null);
  let universe = $state<DailyUniverseResponse | null>(null);
  let artifacts = $state<DailyArtifactsResponse | null>(null);
  let dataset = $state<DailyDatasetResponse | null>(null);
  let datasetChart = $state<DailyDatasetChartResponse | null>(null);
  let prediction = $state<DailyPredictionResponse | null>(null);
  let portfolio = $state<DailyPortfolioResponse | null>(null);
  let walkForward = $state<DailyWalkForwardResponse | null>(null);
  let registry = $state<DailyRegistryResponse | null>(null);
  let predictionChart = $state<DailyModelChartResponse | null>(null);
  let portfolioChart = $state<DailyModelChartResponse | null>(null);
  let walkForwardChart = $state<DailyModelChartResponse | null>(null);
  let closeSlotLatest = $state<DailyCloseSlotLatestResponse | null>(null);
  let closeSlotGate = $state<DailyCloseSlotLatestResponse | null>(null);
  let closeSlotArtifacts = $state<DailyCloseSlotArtifactsResponse | null>(null);
  let closeSlotEquity = $state<DailyCloseSlotEquityResponse | null>(null);
  let closeSlotSelection = $state<DailyCloseSlotSelectionResponse | null>(null);
  let decisionCockpit = $state<DailyVisualChartResponse | null>(null);
  let scenarioLab = $state<DailyScenarioLabResponse | null>(null);
  let scenarioRuns = $state<DailyScenarioRunLedgerResponse | null>(null);
  let flowChart = $state<DailyVisualChartResponse | null>(null);
  let glossaryChart = $state<DailyVisualChartResponse | null>(null);
  let researchDiagnosticsChart = $state<DailyVisualChartResponse | null>(null);
  let equityOverlayChart = $state<DailyVisualChartResponse | null>(null);
  let walkForwardHeatmapChart = $state<DailyVisualChartResponse | null>(null);
  let runScatterChart = $state<DailyVisualChartResponse | null>(null);
  let universeBreakdownChart = $state<DailyVisualChartResponse | null>(null);
  let selectedSymbol = $state<DailySymbolResponse | null>(null);
  let selectedSymbolChart = $state<DailyVisualChartResponse | null>(null);
  let selectedSymbolError = $state<string | null>(null);
  let endpointErrors = $state<SecondaryCardKey[]>([]);
  let loading = $state(false);
  let shell = $state<DashboardShell>('v3');
  const unsubscribeDashboardShell = dashboardShell.subscribe((value) => (shell = value));

  interface V51DailyCardState<T> {
    data: T | null;
    loading: boolean;
    error: string | null;
    loaded: boolean;
  }

  function emptyV51DailyCardState<T>(): V51DailyCardState<T> {
    return { data: null, loading: false, error: null, loaded: false };
  }

  let v51SourceCoverageState = $state<V51DailyCardState<V51SourceCoverageRoot>>(emptyV51DailyCardState());
  let v51CausalPanelState = $state<V51DailyCardState<V51CausalPanelRoot>>(emptyV51DailyCardState());
  let v51AccountingState = $state<V51DailyCardState<V51AccountingRoot>>(emptyV51DailyCardState());
  let v51EvidenceTouched = $state(false);
  let v51EvidenceRequestId = 0;

  const v51LockRows: readonly { key: keyof V51FalseResearchLocks; label: string }[] = [
    { key: 'promotion_allowed', label: 'promotion_allowed' },
    { key: 'model_build_allowed', label: 'model_build_allowed' },
    { key: 'paper_forward_allowed', label: 'paper_forward_allowed' },
    { key: 'live_broker_order_allowed', label: 'live_broker_order_allowed' },
    { key: 'profitability_claim_allowed', label: 'profitability_claim_allowed' },
    { key: 'go_summary_allowed', label: 'go_summary_allowed' },
  ];

  const v51ClaimRows: readonly { key: keyof V51NoClaimFlags; label: string }[] = [
    { key: 'official_close_claim', label: 'official_close_claim' },
    { key: 'paper_forward_claim', label: 'paper_forward_claim' },
    { key: 'live_trading_claim', label: 'live_trading_claim' },
    { key: 'broker_integration_claim', label: 'broker_integration_claim' },
    { key: 'profitability_claim', label: 'profitability_claim' },
    { key: 'go_readiness_claim', label: 'go_readiness_claim' },
  ];

  let v51DailyProtocol = $derived(
    v51SourceCoverageState.data?.protocol ?? v51CausalPanelState.data?.protocol ?? v51AccountingState.data?.protocol ?? null,
  );
  let v51DailyLocks = $derived(
    v51SourceCoverageState.data?.locks ?? v51CausalPanelState.data?.locks ?? v51AccountingState.data?.locks ?? null,
  );
  let v51DailyClaims = $derived(
    v51SourceCoverageState.data?.claims ?? v51CausalPanelState.data?.claims ?? v51AccountingState.data?.claims ?? null,
  );

  // G009 Todo 9 — critical (always-visible, not behind a Disclosure) cards
  // get INDEPENDENT loaders + own {loading, error} state so one slow/failed
  // card (progress, or the close-slot group) can never block the other from
  // rendering. A timed-out or failed card renders an explicit ERROR/RETRY
  // state below — it is never silently masked as NOT_STARTED/MISSING.
  interface CriticalCardState {
    loading: boolean;
    error: string | null;
  }
  let progressCardState = $state<CriticalCardState>({ loading: false, error: null });
  let closeSlotCardState = $state<CriticalCardState>({ loading: false, error: null });
  const progressGate = createRequestGate();
  const closeSlotGateReq = createRequestGate();
  const CARD_TIMEOUT_MS = 20000;
  type SecondaryCardKey =
    | 'db-summary' | 'universe' | 'artifacts' | 'dataset' | 'dataset-chart'
    | 'prediction' | 'portfolio' | 'walk-forward' | 'registry'
    | 'prediction-chart' | 'portfolio-chart' | 'walk-forward-chart'
    | 'decision-cockpit' | 'scenarios' | 'scenario-runs' | 'flow-chart'
    | 'glossary-chart' | 'research-diagnostics' | 'equity-overlay'
    | 'walk-forward-heatmap' | 'run-scatter' | 'universe-breakdown';
  let secondaryCardStates = $state<Partial<Record<SecondaryCardKey, CardRequestState>>>({});
  const secondaryCardRequests = createCardRequestManager(CARD_TIMEOUT_MS);

  function publishSecondaryState(key: string, state: CardRequestState): void {
    const cardKey = key as SecondaryCardKey;
    secondaryCardStates = { ...secondaryCardStates, [cardKey]: state };
    endpointErrors = (Object.entries(secondaryCardStates) as [SecondaryCardKey, CardRequestState][])
      .filter(([, cardState]) => cardState.error !== null)
      .map(([failedKey]) => failedKey);
  }

  function loadSecondaryCard<T>(
    key: SecondaryCardKey,
    request: (signal: AbortSignal) => Promise<T | null>,
    apply: (payload: T) => void,
  ): Promise<void> {
    return secondaryCardRequests.load(key, request, apply, publishSecondaryState);
  }

  function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T | 'TIMEOUT'> {
    return new Promise((resolve) => {
      let settled = false;
      const timer = setTimeout(() => {
        if (settled) return;
        settled = true;
        resolve('TIMEOUT');
      }, ms);
      void promise.then((value) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        resolve(value);
      });
    });
  }

  const dailyStatusLocks = [
    { label: 'live trading', value: 'false', tone: 'danger' },
    { label: 'broker/order/account', value: 'false', tone: 'danger' },
    { label: 'paper forward', value: 'false', tone: 'danger' },
    { label: 'model build allowed', value: 'false', tone: 'danger' },
    { label: 'go summary', value: 'false', tone: 'danger' },
    { label: 'default cost', value: '23bp', tone: 'warn' },
  ] as const;
  const dailyStatusBlockers = [
    'D0 price_basis / adjusted-price evidence is still a blocker for stronger claims.',
    'D1 universe remains governance evidence; unknown instruments and Q-products stay quarantined.',
    'D5 walk-forward gates remain NO-GO/blocked until fresh preregistered evidence passes.',
  ] as const;
  const dailyNextInspection = [
    'D0-D9 progress timeline에서 PASS/WATCH/NOT_STARTED/BLOCKED를 먼저 확인합니다.',
    '000250 같은 leading-zero 종목 코드는 문자열 그대로 drilldown합니다.',
    '모델·수익·실거래 판단 전에 artifact hashes, stale/malformed fail-closed 상태를 확인합니다.',
  ] as const;

  function describeV51DailyError(routeId: V51ResearchRouteId, reason: unknown): string {
    if (reason instanceof V51ApiError) {
      const status = reason.status === null ? 'no-http-status' : `HTTP ${reason.status}`;
      return `${routeId} ${reason.code} · ${status} · ${reason.message}`;
    }
    return `${routeId} ERROR · ${reason instanceof Error ? reason.message : String(reason)}`;
  }

  function v51DailyStateFromResult<T>(
    routeId: V51ResearchRouteId,
    result: PromiseSettledResult<T>,
  ): V51DailyCardState<T> {
    if (result.status === 'fulfilled') {
      return { data: result.value, loading: false, error: null, loaded: true };
    }
    return { data: null, loading: false, error: describeV51DailyError(routeId, result.reason), loaded: true };
  }

  async function loadV51DailyEvidence(): Promise<void> {
    if (shell !== 'v5') return;
    const requestId = ++v51EvidenceRequestId;
    v51EvidenceTouched = true;
    v51SourceCoverageState = { ...v51SourceCoverageState, loading: true, error: null };
    v51CausalPanelState = { ...v51CausalPanelState, loading: true, error: null };
    v51AccountingState = { ...v51AccountingState, loading: true, error: null };
    const [sourceCoverage, causalPanel, accounting] = await Promise.allSettled([
      fetchV51SourceCoverage(),
      fetchV51CausalPanel(),
      fetchV51Accounting(),
    ]);
    if (requestId !== v51EvidenceRequestId || shell !== 'v5') return;
    v51SourceCoverageState = v51DailyStateFromResult('SOURCE_COVERAGE', sourceCoverage);
    v51CausalPanelState = v51DailyStateFromResult('CAUSAL_PANEL', causalPanel);
    v51AccountingState = v51DailyStateFromResult('ACCOUNTING', accounting);
  }
  // G009 Todo 9 — progress card: INDEPENDENT loader with its own
  // loading/error state. A timeout resolves to 'TIMEOUT' (never hangs
  // forever) and renders as an explicit ERROR/RETRY state, never as
  // NOT_STARTED/MISSING.
  async function loadProgressCard(): Promise<void> {
    const token = progressGate.next();
    progressCardState = { loading: true, error: null };
    const result = await withTimeout(dailyOhlcvApi.progress(), CARD_TIMEOUT_MS);
    if (!progressGate.isCurrent(token)) return;
    if (result === 'TIMEOUT') {
      progress = null;
      progressCardState = { loading: false, error: 'progress card request timed out' };
      return;
    }
    progress = result;
    progressCardState = { loading: false, error: result === null ? 'progress card data unavailable' : null };
  }

  // G009 Todo 9 — close-slot card group (CloseSlotAgentScreen +
  // DailyCloseSlotCard): INDEPENDENT loader with its own loading/error
  // state, decoupled from the progress card and the secondary (Disclosure)
  // cards so a slow/timed-out endpoint in one group can never block another.
  async function loadCloseSlotCard(): Promise<void> {
    const token = closeSlotGateReq.next();
    closeSlotCardState = { loading: true, error: null };

    // Resolve the two always-visible decision payloads first. The larger
    // artifact/chart payloads must not delay the critical card.
    const [latestR, gateR] = await Promise.all([
      withTimeout(dailyOhlcvApi.closeSlotLatest(), CARD_TIMEOUT_MS),
      withTimeout(dailyOhlcvApi.closeSlotGate(), CARD_TIMEOUT_MS),
    ]);
    if (!closeSlotGateReq.isCurrent(token)) return;
    closeSlotLatest = latestR === 'TIMEOUT' ? null : latestR;
    closeSlotGate = gateR === 'TIMEOUT' ? null : gateR;
    const primaryFailures = [
      latestR === 'TIMEOUT' || latestR === null ? 'latest' : null,
      gateR === 'TIMEOUT' || gateR === null ? 'gate' : null,
    ].filter((name): name is string => name !== null);
    const primaryError = primaryFailures.length
      ? `close-slot primary request unavailable: ${primaryFailures.join(', ')}`
      : null;
    closeSlotCardState = {
      loading: false,
      error: primaryError,
    };

    void Promise.all([
      withTimeout(dailyOhlcvApi.closeSlotArtifacts(), CARD_TIMEOUT_MS),
      withTimeout(dailyOhlcvApi.closeSlotEquity(), CARD_TIMEOUT_MS),
      withTimeout(dailyOhlcvApi.closeSlotSelection(), CARD_TIMEOUT_MS),
    ]).then(([artifactsR, equityR, selectionR]) => {
      if (!closeSlotGateReq.isCurrent(token)) return;
      closeSlotArtifacts = artifactsR === 'TIMEOUT' ? null : artifactsR;
      closeSlotEquity = equityR === 'TIMEOUT' ? null : equityR;
      closeSlotSelection = selectionR === 'TIMEOUT' ? null : selectionR;
      const auxiliaryFailures = [
        artifactsR === 'TIMEOUT' || artifactsR === null ? 'artifacts' : null,
        equityR === 'TIMEOUT' || equityR === null ? 'equity' : null,
        selectionR === 'TIMEOUT' || selectionR === null ? 'selection' : null,
      ].filter((name): name is string => name !== null);
      closeSlotCardState = {
        loading: false,
        error: primaryError ?? (
          auxiliaryFailures.length
            ? `close-slot auxiliary request unavailable: ${auxiliaryFailures.join(', ')}`
            : null
        ),
      };
    });
  }

  const secondaryLoaders: Record<SecondaryCardKey, () => Promise<void>> = {
    'db-summary': () => loadSecondaryCard('db-summary', (signal) => dailyOhlcvApi.dbSummary(signal), (value) => { dbSummary = value; }),
    'universe': () => loadSecondaryCard('universe', (signal) => dailyOhlcvApi.universePreview(signal), (value) => { universe = value; }),
    'artifacts': () => loadSecondaryCard('artifacts', (signal) => dailyOhlcvApi.artifacts(signal), (value) => { artifacts = value; }),
    'dataset': () => loadSecondaryCard('dataset', (signal) => dailyOhlcvApi.datasetLatest(signal), (value) => { dataset = value; }),
    'dataset-chart': () => loadSecondaryCard('dataset-chart', (signal) => dailyOhlcvApi.datasetChart(signal), (value) => { datasetChart = value; }),
    'prediction': () => loadSecondaryCard('prediction', (signal) => dailyOhlcvApi.predictionLatest(signal), (value) => { prediction = value; }),
    'portfolio': () => loadSecondaryCard('portfolio', (signal) => dailyOhlcvApi.portfolioLatest(signal), (value) => { portfolio = value; }),
    'walk-forward': () => loadSecondaryCard('walk-forward', (signal) => dailyOhlcvApi.walkForwardLatest(signal), (value) => { walkForward = value; }),
    'registry': () => loadSecondaryCard('registry', (signal) => dailyOhlcvApi.registryLatest(signal), (value) => { registry = value; }),
    'prediction-chart': () => loadSecondaryCard('prediction-chart', (signal) => dailyOhlcvApi.predictionChart(signal), (value) => { predictionChart = value; }),
    'portfolio-chart': () => loadSecondaryCard('portfolio-chart', (signal) => dailyOhlcvApi.portfolioChart(signal), (value) => { portfolioChart = value; }),
    'walk-forward-chart': () => loadSecondaryCard('walk-forward-chart', (signal) => dailyOhlcvApi.walkForwardChart(signal), (value) => { walkForwardChart = value; }),
    'decision-cockpit': () => loadSecondaryCard('decision-cockpit', (signal) => dailyOhlcvApi.decisionCockpitChart(signal), (value) => { decisionCockpit = value; }),
    'scenarios': () => loadSecondaryCard('scenarios', (signal) => dailyOhlcvApi.scenarios(signal), (value) => { scenarioLab = value; }),
    'scenario-runs': () => loadSecondaryCard('scenario-runs', (signal) => dailyOhlcvApi.scenarioRuns(signal), (value) => { scenarioRuns = value; }),
    'flow-chart': () => loadSecondaryCard('flow-chart', (signal) => dailyOhlcvApi.flowChart(signal), (value) => { flowChart = value; }),
    'glossary-chart': () => loadSecondaryCard('glossary-chart', (signal) => dailyOhlcvApi.glossaryChart(signal), (value) => { glossaryChart = value; }),
    'research-diagnostics': () => loadSecondaryCard('research-diagnostics', (signal) => dailyOhlcvApi.researchDiagnosticsChart(signal), (value) => { researchDiagnosticsChart = value; }),
    'equity-overlay': () => loadSecondaryCard('equity-overlay', (signal) => dailyOhlcvApi.equityOverlayChart(signal), (value) => { equityOverlayChart = value; }),
    'walk-forward-heatmap': () => loadSecondaryCard('walk-forward-heatmap', (signal) => dailyOhlcvApi.walkForwardHeatmapChart(signal), (value) => { walkForwardHeatmapChart = value; }),
    'run-scatter': () => loadSecondaryCard('run-scatter', (signal) => dailyOhlcvApi.runScatterChart(signal), (value) => { runScatterChart = value; }),
    'universe-breakdown': () => loadSecondaryCard('universe-breakdown', (signal) => dailyOhlcvApi.universeBreakdownChart(signal), (value) => { universeBreakdownChart = value; }),
  };

  async function loadSecondaryCards(): Promise<void> {
    await Promise.all(Object.values(secondaryLoaders).map((loadCard) => loadCard()));
  }

  function retrySecondaryCard(key: SecondaryCardKey): void {
    void secondaryLoaders[key]();
  }

  function retryProgressCard(): void {
    void loadProgressCard();
  }

  function retryCloseSlotCard(): void {
    void loadCloseSlotCard();
  }

  function refreshDailyOhlcv(): void {
    void loadDailyOhlcv();
    if (shell === 'v5') void loadV51DailyEvidence();
  }

  // Give the first-card progress request a short priority window before the
  // close-slot/secondary artifact scans start. The groups still own independent
  // state and a slow progress request cannot block the others beyond 3s.
  async function loadDailyOhlcv(): Promise<void> {
    loading = true;
    try {
      const progressRequest = loadProgressCard();
      await Promise.race([
        progressRequest,
        new Promise<void>((resolve) => window.setTimeout(resolve, 3000)),
      ]);
      if (!progressCardState.loading) {
        await tick();
        await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()));
      }
      const closeSlotRequest = loadCloseSlotCard();
      await Promise.race([
        Promise.all([progressRequest, closeSlotRequest]),
        new Promise<void>((resolve) => window.setTimeout(resolve, 7000)),
      ]);
      await loadSecondaryCards();
      await Promise.all([progressRequest, closeSlotRequest]);
    } finally {
      loading = false;
    }
  }

  async function loadSymbolDrilldown(code: string): Promise<void> {
    selectedSymbolError = null;
    const normalized = String(code ?? '').trim();
    if (!normalized) return;
    const [payload, chart] = await Promise.all([
      dailyOhlcvApi.symbol(normalized, 20),
      dailyOhlcvApi.symbolChart(normalized, 160),
    ]);
    if (payload) {
      selectedSymbol = payload;
      selectedSymbolChart = chart;
    } else {
      selectedSymbolChart = null;
      selectedSymbolError = `${normalized} 종목 상세를 불러오지 못했습니다.`;
    }
  }

  $effect(() => {
    if (
      shell === 'v5'
      && !v51EvidenceTouched
      && !v51SourceCoverageState.loading
      && !v51CausalPanelState.loading
      && !v51AccountingState.loading
    ) {
      void loadV51DailyEvidence();
    }
  });

  onDestroy(() => {
    unsubscribeDashboardShell();
  });

  onMount(() => { void loadDailyOhlcv(); });
</script>

<section class="page-hero" data-daily-ohlcv-tab>
  <div class="row" style="gap:10px; flex-wrap:wrap">
    <span class="text-eyebrow">Daily OHLCV Research</span>
    <span class="pill warn"><span class="dot"></span>READ_ONLY · WATCH</span>
    <span class="pill"><span class="dot"></span>no live/broker/orders</span>
  </div>
  <h1 class="text-h2" style="margin-top:8px">일봉 기반 딥러닝·강화학습 준비 대시보드</h1>
  <p class="text-muted" style="margin-top:6px">
    현재 화면은 D0 DB 분석, D1 유니버스, D2 데이터셋, D3 예측 베이스라인, D4 포트폴리오 RL, D5 워크포워드/게이트, D6 시각화, D7 연구 진단, D8/D9 레지스트리·페이퍼 포워드 잠금 증거를 표시합니다. 수익 보장, 실거래, 주문, 브로커 준비 상태가 아니며 현재 모델 생성 GO가 아니라 NO-GO/RESEARCH_ONLY 상태를 그대로 노출합니다.
  </p>
  <div style="margin-top:12px">
    <button type="button" class="btn" onclick={refreshDailyOhlcv} disabled={loading}>{loading ? '갱신 중…' : '새로고침'}</button>
  </div>
  {#if endpointErrors.length > 0}
    <div class="notice danger" data-daily-api-error style="margin-top:12px">
      <strong>API_UNAVAILABLE</strong> · 데이터 없음(NOT_STARTED)과 API 실패를 분리합니다. decision locks remain false; no model/profit/live readiness is inferred.
      <div class="daily-error-list" style="margin-top:8px">
        {#each endpointErrors as endpoint}
          <div data-daily-card-error={endpoint}>
            <span>{endpoint}: {secondaryCardStates[endpoint]?.error}</span>
            <button type="button" class="btn" onclick={() => retrySecondaryCard(endpoint)}>RETRY</button>
          </div>
        {/each}
      </div>
    </div>
  {/if}
</section>

<ResearchStatusShell
  pageId="daily-ohlcv"
  eyebrow="Daily OHLCV · Research Command Center"
  title="Daily OHLCV는 데이터·게이트 증거 화면입니다"
  verdict="WATCH / RESEARCH_ONLY / D5 NO-GO locked"
  summary="D0-D9 증거를 한 흐름으로 검토하되, 가격 기준·유니버스·워크포워드 blocker를 통과하기 전에는 모델 생성, paper-forward, live/broker/order, profit claim이 모두 잠금입니다."
  locks={dailyStatusLocks}
  blockers={dailyStatusBlockers}
  nextActions={dailyNextInspection}
/>
{#if shell === 'v5'}
  <section class="panel v51-daily-evidence" data-v51-daily-evidence>
    <div class="panel-head v51-evidence-head">
      <div>
        <div class="text-eyebrow">V5.1 Daily causal/accounting evidence</div>
        <h2 class="text-h3">15:20 프록시 · 원천/패널/회계 증거</h2>
        <p class="text-muted" style="margin-top:6px">
          shell=v5에서만 V5.1 GET API를 읽습니다. v3/v4 Daily 화면은 기존 API/레이아웃을 그대로 유지합니다.
        </p>
      </div>
      <div class="row" style="gap:8px;flex-wrap:wrap;justify-content:flex-end">
        <span class="pill"><span class="dot"></span>GET-only</span>
        <span class="pill warn"><span class="dot"></span>READ_ONLY · NOT_RUN until API evidence</span>
      </div>
    </div>

    <div class="v51-evidence-grid">
      <article class="v51-evidence-card" data-v51-source-coverage-card>
        <div class="text-eyebrow">Source coverage</div>
        <h3 class="text-h3">source coverage · exact 15:20</h3>
        {#if v51SourceCoverageState.error}
          <div class="notice danger" data-v51-source-coverage-error>ERROR · {v51SourceCoverageState.error}</div>
        {:else if v51SourceCoverageState.loading}
          <div class="notice" data-v51-source-coverage-loading>V5.1 SOURCE_COVERAGE 로딩 중…</div>
        {:else if v51SourceCoverageState.data}
          {#if v51SourceCoverageState.data.status !== 'READY'}
            <div class="notice warn" data-v51-source-coverage-blocked>BLOCKED · {v51SourceCoverageState.data.status_reason}</div>
          {/if}
          <dl class="v51-fact-list">
            <div><dt>coverage_status</dt><dd>{v51SourceCoverageState.data.source_coverage.coverage_status}</dd></div>
            <div><dt>source_artifact_id</dt><dd class="mono">{v51SourceCoverageState.data.source.source_artifact_id}</dd></div>
            <div><dt>source_sha256</dt><dd class="mono">{v51SourceCoverageState.data.source.source_sha256}</dd></div>
            <div><dt>source_db_sha256</dt><dd class="mono">{v51SourceCoverageState.data.source.source_db_sha256}</dd></div>
            <div><dt>generated_at</dt><dd>{v51SourceCoverageState.data.source.generated_at}</dd></div>
            <div><dt>exact_1520_row_count</dt><dd class="tnum">{v51SourceCoverageState.data.source_coverage.exact_1520_row_count.toLocaleString('ko-KR')}</dd></div>
            <div><dt>symbol_count</dt><dd class="tnum">{v51SourceCoverageState.data.source_coverage.symbol_count.toLocaleString('ko-KR')}</dd></div>
            <div><dt>session_count</dt><dd class="tnum">{v51SourceCoverageState.data.source_coverage.session_count.toLocaleString('ko-KR')}</dd></div>
            <div><dt>date_range</dt><dd>{v51SourceCoverageState.data.source_coverage.first_valid_date ?? 'NOT_AVAILABLE'} → {v51SourceCoverageState.data.source_coverage.last_valid_date ?? 'NOT_AVAILABLE'}</dd></div>
            <div><dt>six_digit_sample_symbol</dt><dd class="tnum">{v51SourceCoverageState.data.source_coverage.sample_symbol}</dd></div>
            <div><dt>exact_1520_sample</dt><dd class="tnum">{v51SourceCoverageState.data.source_coverage.sample_timestamp_yyyymmddhhmm}</dd></div>
            <div><dt>price_basis=15:20_bar_close_proxy</dt><dd>official_close=false · nearest_fallback_allowed=false</dd></div>
            <div><dt>bar_volume_1520</dt><dd>SOURCE_SINGLE_5MIN_BAR_VOLUME</dd></div>
            <div><dt>cumulative_volume_to_1520=NOT_AVAILABLE</dt><dd>{v51SourceCoverageState.data.source_coverage.volume_to_1520_status}</dd></div>
            <div><dt>amount_to_1520=NOT_AVAILABLE</dt><dd>{v51SourceCoverageState.data.source_coverage.amount_to_1520_status}</dd></div>
            <div><dt>missing_policy</dt><dd>{v51SourceCoverageState.data.source_coverage.missing_policy}</dd></div>
          </dl>
        {:else}
          <div class="notice" data-v51-source-coverage-not-run>NOT_RUN · V5.1 source coverage evidence has not loaded.</div>
        {/if}
      </article>

      <article class="v51-evidence-card" data-v51-causal-panel-card>
        <div class="text-eyebrow">Causal panel</div>
        <h3 class="text-h3">H1/H3/H5 · 15:20 labels</h3>
        {#if v51CausalPanelState.error}
          <div class="notice danger" data-v51-causal-panel-error>ERROR · {v51CausalPanelState.error}</div>
        {:else if v51CausalPanelState.loading}
          <div class="notice" data-v51-causal-panel-loading>V5.1 CAUSAL_PANEL 로딩 중…</div>
        {:else if v51CausalPanelState.data}
          {#if v51CausalPanelState.data.status !== 'READY'}
            <div class="notice warn" data-v51-causal-panel-blocked>BLOCKED · {v51CausalPanelState.data.status_reason}</div>
          {/if}
          <dl class="v51-fact-list">
            <div><dt>panel_schema</dt><dd>{v51CausalPanelState.data.causal_panel.panel_schema}</dd></div>
            <div><dt>row_count</dt><dd class="tnum">{v51CausalPanelState.data.causal_panel.row_count.toLocaleString('ko-KR')}</dd></div>
            <div><dt>price_basis=15:20_bar_close_proxy</dt><dd>official_close=false</dd></div>
            <div><dt>H1/H3/H5</dt><dd>{v51CausalPanelState.data.causal_panel.primary_horizon} primary · {v51CausalPanelState.data.causal_panel.validation_horizons.join('/')} validation</dd></div>
            <div><dt>label_columns</dt><dd class="mono">{v51CausalPanelState.data.causal_panel.label_columns.join(' · ')}</dd></div>
          </dl>
          <div class="table-wrap v51-panel-preview">
            <table>
              <thead><tr><th>six-digit symbol</th><th>session</th><th>timestamp</th><th>entry</th><th>H1</th><th>H3</th><th>H5</th></tr></thead>
              <tbody>
                {#each v51CausalPanelState.data.causal_panel.rows_preview as row}
                  <tr>
                    <td class="tnum">{row.symbol}</td>
                    <td>{row.session_date}</td>
                    <td class="tnum">{row.timestamp_kst}</td>
                    <td>{row.entry_status}</td>
                    <td>{row.h1_status}</td>
                    <td>{row.h3_status}</td>
                    <td>{row.h5_status}</td>
                  </tr>
                {:else}
                  <tr><td colspan="7">rows_preview=NOT_AVAILABLE</td></tr>
                {/each}
              </tbody>
            </table>
          </div>
        {:else}
          <div class="notice" data-v51-causal-panel-not-run>NOT_RUN · V5.1 causal panel evidence has not loaded.</div>
        {/if}
      </article>

      <article class="v51-evidence-card" data-v51-accounting-card>
        <div class="text-eyebrow">Accounting</div>
        <h3 class="text-h3">account envelope · base_23bp</h3>
        {#if v51AccountingState.error}
          <div class="notice danger" data-v51-accounting-error>ERROR · {v51AccountingState.error}</div>
        {:else if v51AccountingState.loading}
          <div class="notice" data-v51-accounting-loading>V5.1 ACCOUNTING 로딩 중…</div>
        {:else if v51AccountingState.data}
          {#if v51AccountingState.data.status !== 'READY'}
            <div class="notice warn" data-v51-accounting-blocked>BLOCKED · {v51AccountingState.data.status_reason}</div>
          {/if}
          <dl class="v51-fact-list">
            <div><dt>accounting_status</dt><dd>{v51AccountingState.data.accounting.accounting_status}</dd></div>
            <div><dt>account envelope</dt><dd>{v51AccountingState.data.accounting.contract.initial_capital_krw.toLocaleString('ko-KR')} KRW · {v51AccountingState.data.accounting.contract.slot_count} slots</dd></div>
            <div><dt>slot_budget_krw</dt><dd class="tnum">{v51AccountingState.data.accounting.contract.slot_budget_krw.toLocaleString('ko-KR')}</dd></div>
            <div><dt>max_invested_krw</dt><dd>{v51AccountingState.data.accounting.contract.max_invested_krw.toLocaleString('ko-KR')} · {v51AccountingState.data.accounting.contract.max_target_investment_display_percent}</dd></div>
            <div><dt>reserve_cash_krw</dt><dd>{v51AccountingState.data.accounting.contract.reserve_cash_krw.toLocaleString('ko-KR')} · {v51AccountingState.data.accounting.contract.reserve_cash_display_percent}</dd></div>
            <div><dt>slots_used/max_slots</dt><dd>{v51AccountingState.data.accounting.slots_used} / {v51AccountingState.data.accounting.max_slots}</dd></div>
            <div><dt>economic_nav_krw</dt><dd class="tnum">{v51AccountingState.data.accounting.economic_nav_krw.toLocaleString('ko-KR')}</dd></div>
            <div><dt>cash_reserve_krw</dt><dd class="tnum">{v51AccountingState.data.accounting.cash_reserve_krw.toLocaleString('ko-KR')}</dd></div>
            <div><dt>internal_cost_id</dt><dd>{v51AccountingState.data.accounting.internal_cost_id} · display_cost_percent={v51AccountingState.data.accounting.display_cost_percent}</dd></div>
            <div><dt>cost_schedule.primary</dt><dd>{v51AccountingState.data.accounting.cost_schedule.primary.internal_id} · {v51AccountingState.data.accounting.cost_schedule.primary.round_trip_cost_bp}bp · {v51AccountingState.data.accounting.cost_schedule.primary.display_percent}</dd></div>
            <div><dt>shorting/leverage/duplicates</dt><dd>{String(v51AccountingState.data.accounting.contract.shorting_allowed)} / {String(v51AccountingState.data.accounting.contract.leverage_allowed)} / {String(v51AccountingState.data.accounting.contract.duplicate_symbol_slots_allowed)}</dd></div>
          </dl>
        {:else}
          <div class="notice" data-v51-accounting-not-run>NOT_RUN · V5.1 accounting evidence has not loaded.</div>
        {/if}
      </article>

      <article class="v51-evidence-card" data-v51-daily-locks-card>
        <div class="text-eyebrow">No-claim rails</div>
        <h3 class="text-h3">six false locks · read-only protocol</h3>
        {#if v51DailyProtocol}
          <dl class="v51-fact-list">
            <div><dt>method</dt><dd>{v51DailyProtocol.method}</dd></div>
            <div><dt>read_only</dt><dd>{String(v51DailyProtocol.read_only)}</dd></div>
            <div><dt>causal_cutoff_kst</dt><dd>{v51DailyProtocol.causal_cutoff_kst}</dd></div>
            <div><dt>price_basis=15:20_bar_close_proxy</dt><dd>official_close={String(v51DailyProtocol.official_close)}</dd></div>
            <div><dt>cost ids</dt><dd>{v51DailyProtocol.cost_schedule.zero_cost_control.internal_id}=0.00% · {v51DailyProtocol.cost_schedule.primary.internal_id}=0.23% · {v51DailyProtocol.cost_schedule.stress_control.internal_id}=0.46%</dd></div>
          </dl>
        {:else}
          <div class="notice" data-v51-protocol-not-run>NOT_RUN · no V5.1 protocol root loaded.</div>
        {/if}
        {#if v51DailyLocks}
          <div class="v51-mini-grid" data-v51-six-false-locks>
            {#each v51LockRows as row}
              <div><span>{row.label}</span><b>{String(v51DailyLocks[row.key])}</b></div>
            {/each}
          </div>
        {/if}
        {#if v51DailyClaims}
          <div class="v51-mini-grid" data-v51-no-claim-facts>
            {#each v51ClaimRows as row}
              <div><span>{row.label}</span><b>{String(v51DailyClaims[row.key])}</b></div>
            {/each}
          </div>
        {/if}
      </article>
    </div>
  </section>
{/if}
{#if progressCardState.error}
  <div class="notice danger" data-daily-progress-card-error style="margin-top:12px">
    ERROR: {progressCardState.error}
    <button type="button" class="btn" onclick={retryProgressCard} style="margin-left:8px">RETRY</button>
  </div>
{:else if progressCardState.loading && !progress}
  <div class="notice" data-daily-progress-card-loading style="margin-top:12px">progress 카드 로딩 중…</div>
{/if}
<DailyGateLadder {progress} />
<div class="daily-review-grid" style="margin-top:14px">
  <div><span>leading-zero code</span><b>000250 string preserved</b></div>
  <div><span>D5 gate</span><b>NO-GO / model_build_allowed=false</b></div>
  <div><span>live/model/paper/profit</span><b>false / 0%</b></div>
</div>
<DailyProgressTimeline {progress} />

{#if closeSlotCardState.error}
  <div class="notice danger" data-daily-close-slot-card-error style="margin-top:12px">
    ERROR: {closeSlotCardState.error}
    <button type="button" class="btn" onclick={retryCloseSlotCard} style="margin-left:8px">RETRY</button>
  </div>
{:else if closeSlotCardState.loading && !closeSlotLatest && !closeSlotGate}
  <div class="notice" data-daily-close-slot-card-loading style="margin-top:12px">close-slot 카드 로딩 중…</div>
{/if}
<CloseSlotAgentScreen
  latest={closeSlotLatest}
  gate={closeSlotGate}
  equity={closeSlotEquity}
  selection={closeSlotSelection}
/>

<DailyCloseSlotCard
  latest={closeSlotLatest}
  gate={closeSlotGate}
  artifacts={closeSlotArtifacts}
  equity={closeSlotEquity}
  selection={closeSlotSelection}
/>

<div class="text-eyebrow" style="margin-top:4px">D0–D6 세부 증거 카드 · 필요할 때 펼치기</div>

<Disclosure summary="D0 · DB 품질 점검" meta="RESEARCH_ONLY">
  <DailyDbQualityCard summary={dbSummary} />
</Disclosure>
<Disclosure summary="D1 · 유니버스 미리보기" meta="WATCH">
  <DailyUniverseCard {universe} onSymbolSelect={(code) => void loadSymbolDrilldown(code)} />
</Disclosure>
<Disclosure summary="D2 · 데이터셋 빌더">
  <DailyDatasetBuilderCard {dataset} chart={datasetChart} />
</Disclosure>
<Disclosure summary="D3–D4 · 모델 · 포트폴리오 결과">
  <DailyModelResultsCard {prediction} {portfolio} {walkForward} {predictionChart} {portfolioChart} {walkForwardChart} />
</Disclosure>
<Disclosure summary="D6 · 시각 랩 · 착시 방지">
  <DailyVisualLabCard
    decision={decisionCockpit}
    flow={flowChart}
    glossary={glossaryChart}
    researchDiagnostics={researchDiagnosticsChart}
    equityOverlay={equityOverlayChart}
    heatmap={walkForwardHeatmapChart}
    runScatter={runScatterChart}
    universeBreakdown={universeBreakdownChart}
    registry={registry}
    symbolChart={selectedSymbolChart}
  />
</Disclosure>
<Disclosure summary="시나리오 · 가정 생성 플랫폼" meta="RESEARCH_ONLY">
  <DailyScenarioLabCard {scenarioLab} />
</Disclosure>
<Disclosure summary="시나리오 실행 원장 · 모델 비교">
  <DailyScenarioRunLedgerCard ledger={scenarioRuns} />
</Disclosure>

<section class="panel" data-daily-symbol-panel>
  <div class="panel-head">
    <div>
      <div class="text-eyebrow">D0 Symbol Drilldown</div>
      <h2 class="text-h3">종목 상세 조회</h2>
    </div>
    <span class="pill warn"><span class="dot"></span>{selectedSymbol?.price_basis ?? 'unknown'}</span>
  </div>
  <p class="text-muted" style="margin-top:8px">유니버스 미리보기의 상세 버튼은 `/api/daily-ohlcv/symbol/{'{code}'}`를 호출하며 000250 같은 선행 0 코드를 문자열로 유지합니다.</p>
  {#if selectedSymbolError}
    <div class="notice danger" style="margin-top:12px">{selectedSymbolError}</div>
  {:else if selectedSymbol}
    <div class="grid-4-kpi" style="margin-top:16px">
      <div class="metric"><div class="metric-label">code</div><div class="metric-value tnum">{selectedSymbol.code}</div></div>
      <div class="metric"><div class="metric-label">table</div><div class="metric-value tnum">{selectedSymbol.table}</div></div>
      <div class="metric"><div class="metric-label">rows</div><div class="metric-value tnum">{selectedSymbol.row_count?.toLocaleString('ko-KR') ?? '—'}</div></div>
      <div class="metric"><div class="metric-label">range</div><div class="metric-value tnum" style="font-size:18px">{selectedSymbol.first_date ?? '—'} → {selectedSymbol.last_date ?? '—'}</div></div>
    </div>
  {:else}
    <div class="notice" style="margin-top:12px">아직 선택된 종목이 없습니다. 유니버스 미리보기에서 상세 버튼을 누르세요.</div>
  {/if}
</section>

<section class="panel" data-daily-ohlcv-artifacts>
  <div class="panel-head">
    <div>
      <div class="text-eyebrow">Artifacts</div>
      <h2 class="text-h3">생성 증거 파일</h2>
    </div>
    <span class="pill"><span class="dot"></span>GET-only</span>
  </div>
  <div class="table-wrap" style="margin-top:12px; max-height:300px; overflow:auto">
    <a class="sr-only" href="#daily-artifact-table">Daily OHLCV 생성 증거 파일 표로 이동</a>
    <table id="daily-artifact-table">
      <thead><tr><th>kind</th><th>run</th><th>file</th><th>bytes</th></tr></thead>
      <tbody>
        {#each artifacts?.artifacts ?? [] as row}
          <tr>
            <td>{row.kind}</td>
            <td>{row.run_id}</td>
            <td class="mono">{row.primary_file}</td>
            <td class="tnum">{row.size_bytes}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</section>

<style>
  .daily-review-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(210px, 1fr)); gap:10px; }
  .daily-review-grid div { border:1px solid var(--border-faint); border-radius:14px; padding:12px; background:var(--surface-sunken); }
  .daily-review-grid span { display:block; color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:0.04em; }
  .daily-review-grid b { display:block; margin-top:6px; font-size:13px; }
  .daily-error-list { display:grid; gap:6px; }
  .daily-error-list > div { display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; }
  table { width:100%; border-collapse:collapse; font-size:12px; }
  th, td { border-bottom:1px solid var(--border-faint); padding:7px; text-align:left; vertical-align:top; }
  .mono { font-family: var(--font-mono); font-size:11px; color:var(--muted); }
  .v51-daily-evidence { display:grid; gap:16px; }
  .v51-evidence-head { align-items:flex-start; }
  .v51-evidence-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:12px; }
  .v51-evidence-card { border:1px solid var(--border-faint); border-radius:16px; background:var(--surface-sunken); padding:14px; min-width:0; }
  .v51-evidence-card h3 { margin:4px 0 12px; }
  .v51-fact-list { display:grid; gap:8px; margin:0; }
  .v51-fact-list > div { display:grid; grid-template-columns:minmax(120px, 0.45fr) minmax(0, 1fr); gap:10px; align-items:start; }
  .v51-fact-list dt { color:var(--muted); font-size:11px; text-transform:none; letter-spacing:0.02em; }
  .v51-fact-list dd { margin:0; min-width:0; overflow-wrap:anywhere; }
  .v51-panel-preview { margin-top:12px; max-height:220px; overflow:auto; }
  .v51-mini-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); gap:8px; margin-top:12px; }
  .v51-mini-grid > div { border:1px solid var(--border-faint); border-radius:12px; padding:10px; background:var(--surface); }
  .v51-mini-grid span { display:block; color:var(--muted); font-size:10px; overflow-wrap:anywhere; }
  .v51-mini-grid b { display:block; margin-top:4px; font-size:12px; }
  @media (max-width: 760px) {
    .v51-fact-list > div { grid-template-columns:1fr; gap:2px; }
  }
</style>
