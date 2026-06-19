<script lang="ts">
  import { onMount } from 'svelte';
  import {
    dailyOhlcvApi,
    type DailyArtifactsResponse,
    type DailyDatasetChartResponse,
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
  import ResearchStatusShell from './ResearchStatusShell.svelte';

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
  let endpointErrors = $state<string[]>([]);
  let loading = $state(false);

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
  const dailyCockpitStages = ['D0', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9'] as const;
  const stageById = (id: string) => progress?.stages?.find((stage) => stage.id === id);
  async function loadDailyOhlcv(): Promise<void> {
    loading = true;
    try {
      const [p, d, u, a, ds, dc, pred, port, wf, reg, predChart, portChart, wfChart, decision, scenarios, scenarioRunsResult, flow, glossary, diagnostics, equity, heatmap, scatter, universeBreakdown] = await Promise.all([
        dailyOhlcvApi.progress(),
        dailyOhlcvApi.dbSummary(),
        dailyOhlcvApi.universePreview(),
        dailyOhlcvApi.artifacts(),
        dailyOhlcvApi.datasetLatest(),
        dailyOhlcvApi.datasetChart(),
        dailyOhlcvApi.predictionLatest(),
        dailyOhlcvApi.portfolioLatest(),
        dailyOhlcvApi.walkForwardLatest(),
        dailyOhlcvApi.registryLatest(),
        dailyOhlcvApi.predictionChart(),
        dailyOhlcvApi.portfolioChart(),
        dailyOhlcvApi.walkForwardChart(),
        dailyOhlcvApi.decisionCockpitChart(),
        dailyOhlcvApi.scenarios(),
        dailyOhlcvApi.scenarioRuns(),
        dailyOhlcvApi.flowChart(),
        dailyOhlcvApi.glossaryChart(),
        dailyOhlcvApi.researchDiagnosticsChart(),
        dailyOhlcvApi.equityOverlayChart(),
        dailyOhlcvApi.walkForwardHeatmapChart(),
        dailyOhlcvApi.runScatterChart(),
        dailyOhlcvApi.universeBreakdownChart(),
      ]);
      const resolved = [
        ['progress', p],
        ['db-summary', d],
        ['universe', u],
        ['artifacts', a],
        ['dataset', ds],
        ['dataset-chart', dc],
        ['prediction', pred],
        ['portfolio', port],
        ['walk-forward', wf],
        ['registry', reg],
        ['prediction-chart', predChart],
        ['portfolio-chart', portChart],
        ['walk-forward-chart', wfChart],
        ['decision-cockpit', decision],
        ['scenarios', scenarios],
        ['scenario-runs', scenarioRunsResult],
        ['flow-chart', flow],
        ['glossary-chart', glossary],
        ['research-diagnostics', diagnostics],
        ['equity-overlay', equity],
        ['walk-forward-heatmap', heatmap],
        ['run-scatter', scatter],
        ['universe-breakdown', universeBreakdown],
      ] as const;
      endpointErrors = resolved.filter(([, payload]) => payload === null).map(([name]) => name);
      progress = p;
      dbSummary = d;
      universe = u;
      artifacts = a;
      dataset = ds;
      datasetChart = dc;
      prediction = pred;
      portfolio = port;
      walkForward = wf;
      registry = reg;
      predictionChart = predChart;
      portfolioChart = portChart;
      walkForwardChart = wfChart;
      decisionCockpit = decision;
      scenarioLab = scenarios;
      scenarioRuns = scenarioRunsResult;
      flowChart = flow;
      glossaryChart = glossary;
      researchDiagnosticsChart = diagnostics;
      equityOverlayChart = equity;
      walkForwardHeatmapChart = heatmap;
      runScatterChart = scatter;
      universeBreakdownChart = universeBreakdown;
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
    <button type="button" class="btn" onclick={() => void loadDailyOhlcv()} disabled={loading}>{loading ? '갱신 중…' : '새로고침'}</button>
  </div>
  {#if endpointErrors.length > 0}
    <div class="notice danger" data-daily-api-error style="margin-top:12px">
      API_UNAVAILABLE: {endpointErrors.join(', ')} · 데이터 없음(NOT_STARTED)과 API 실패를 분리합니다. decision locks remain false; no model/profit/live readiness is inferred.
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
<section class="panel daily-command-cockpit" data-daily-ohlcv-command-cockpit>
  <div class="panel-head">
    <div>
      <div class="text-eyebrow">D0-D9 review cockpit · before raw cards</div>
      <h2 class="text-h3">일봉 연구 상태를 한 줄로 먼저 확인</h2>
      <p class="text-muted">API failure는 `API_UNAVAILABLE`로 따로 표시하고, 산출물이 없는 단계는 `NOT_STARTED`로 구분합니다. leading-zero code 예시는 문자열 `000250` 그대로 유지합니다.</p>
    </div>
    <span class="pill warn"><span class="dot"></span>{progress?.overall_status ?? 'RESEARCH_ONLY'}</span>
  </div>
  <div class="daily-stage-grid" data-daily-ohlcv-d0-d9-cockpit>
    {#each dailyCockpitStages as id}
      {@const stage = stageById(id)}
      <article class="daily-stage-tile" data-status={stage?.status ?? 'NOT_STARTED'}>
        <strong>{id}</strong>
        <span>{stage?.label ?? 'not started'}</span>
        <b>{stage?.status ?? 'NOT_STARTED'}</b>
      </article>
    {/each}
  </div>
  <div class="daily-review-grid" style="margin-top:14px">
    <div><span>API failure vs NOT_STARTED</span><b>{endpointErrors.length ? `API_UNAVAILABLE: ${endpointErrors.join(', ')}` : 'API_OK; missing artifacts stay NOT_STARTED'}</b></div>
    <div><span>leading-zero code</span><b>000250 string preserved</b></div>
    <div><span>D5 gate</span><b>NO-GO / model_build_allowed=false</b></div>
    <div><span>live/model/paper/profit</span><b>false / 0%</b></div>
  </div>
</section>
<DailyProgressTimeline {progress} />
<DailyScenarioLabCard {scenarioLab} />
<DailyScenarioRunLedgerCard ledger={scenarioRuns} />
<DailyDbQualityCard summary={dbSummary} />
<DailyUniverseCard {universe} onSymbolSelect={(code) => void loadSymbolDrilldown(code)} />
<DailyDatasetBuilderCard {dataset} chart={datasetChart} />
<DailyModelResultsCard {prediction} {portfolio} {walkForward} {predictionChart} {portfolioChart} {walkForwardChart} />
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
    <table>
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
  .daily-stage-grid { margin-top:14px; display:grid; grid-template-columns:repeat(auto-fit, minmax(96px, 1fr)); gap:8px; }
  .daily-stage-tile { border:1px solid var(--border-faint); border-radius:14px; padding:10px; background:var(--surface); display:grid; gap:4px; }
  .daily-stage-tile strong { font-family:var(--font-mono); font-size:13px; }
  .daily-stage-tile span { color:var(--muted); font-size:11px; min-height:28px; }
  .daily-stage-tile b { font-family:var(--font-mono); font-size:11px; }
  .daily-stage-tile[data-status='PASS'] { border-color:rgba(34,197,94,0.45); background:rgba(34,197,94,0.07); }
  .daily-stage-tile[data-status='WATCH'] { border-color:rgba(245,158,11,0.45); background:rgba(245,158,11,0.07); }
  .daily-stage-tile[data-status='NO-GO'], .daily-stage-tile[data-status='BLOCKED'] { border-color:rgba(239,68,68,0.45); background:rgba(239,68,68,0.07); }
  .daily-review-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(210px, 1fr)); gap:10px; }
  .daily-review-grid div { border:1px solid var(--border-faint); border-radius:14px; padding:12px; background:var(--surface-sunken); }
  .daily-review-grid span { display:block; color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:0.04em; }
  .daily-review-grid b { display:block; margin-top:6px; font-size:13px; }
  table { width:100%; border-collapse:collapse; font-size:12px; }
  th, td { border-bottom:1px solid var(--border-faint); padding:7px; text-align:left; vertical-align:top; }
  .mono { font-family: var(--font-mono); font-size:11px; color:var(--muted); }
</style>
