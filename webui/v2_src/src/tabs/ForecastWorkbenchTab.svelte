<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { ICONS } from '$lib/icons';
  import EChartsRenderer from '../charts/EChartsRenderer.svelte';
  import { theme } from '$lib/stores';
  import {
    FORECAST_LIMITS,
    buildForecastPredictPayload,
    validateForecastDataSelection,
    validateForecastModelSelection,
    validateForecastPredictionResponse,
    type ForecastPredictionResponse,
  } from '../v4/forecast/forecastEvidence';

  // ── 모델 / 데이터 카탈로그 ──────────────────────────────────────
  let availableModels = $state<any>({});
  let modelAvailable = $state<boolean | null>(null);
  let modelImportError = $state<string | null>(null);
  let modelCatalogError = $state<string | null>(null);
  let dataCatalogError = $state<string | null>(null);
  let dataFiles = $state<any[]>([]);
  let selectedModel = $state<string>('');
  let selectedDataFile = $state<string>('');
  let modelLoaded = $state(false);
  let dataLoaded = $state(false);
  let currentModelLabel = $state<string>('');
  let currentDataLabel = $state<string>('');

  // 슬라이더 상태 (v1 메인 화면 기본값과 일치)
  let lookback = $state(400);
  let predLen = $state(120);
  let temperature = $state(1.0);
  let topP = $state(0.9);
  let sampleCount = $state(1);
  let seedFixed = $state(true);
  let seed = $state(42);

  // 디바이스 (학습 중 GPU 옵션 잠금 — 현재 학습 없으므로 cpu 기본)
  let device = $state<'cpu' | 'cuda'>('cpu');

  // 예측 결과
  let predicting = $state(false);
  let predictionResult = $state<ForecastPredictionResponse | null>(null);
  let predictionError = $state<string | null>(null);
  let loadingModel = $state(false);
  let loadingData = $state(false);
  let loadError = $state<string | null>(null);

  let currentTheme = $state<'light' | 'dark'>('light');
  const unsubscribeTheme = theme.subscribe((v) => (currentTheme = v));

  onDestroy(unsubscribeTheme);

  async function loadAvailableModels() {
    modelCatalogError = null;
    try {
      const response = await fetch('/api/available-models');
      if (!response.ok) throw new Error(`Model catalog HTTP ${response.status}`);
      const payload = await response.json();
      if (!payload || typeof payload !== 'object' || !payload.models || typeof payload.models !== 'object' || Array.isArray(payload.models)) {
        throw new Error('Model catalog response is malformed.');
      }
      availableModels = payload.models;
      modelAvailable = payload.model_available === true;
      modelImportError = typeof payload.model_import_error === 'string' ? payload.model_import_error : null;
      const keys = Object.keys(availableModels);
      selectedModel = keys.includes(selectedModel) ? selectedModel : (keys[0] ?? '');
    } catch (caught) {
      availableModels = {};
      selectedModel = '';
      modelAvailable = false;
      modelImportError = null;
      modelCatalogError = caught instanceof Error ? caught.message : 'Model catalog request failed.';
    }
  }

  async function loadDataFiles() {
    dataCatalogError = null;
    try {
      const response = await fetch('/api/data-files');
      if (!response.ok) throw new Error(`Data catalog HTTP ${response.status}`);
      const payload = await response.json();
      const files = Array.isArray(payload) ? payload : payload && Array.isArray(payload.files) ? payload.files : null;
      if (files === null) throw new Error('Data catalog response is malformed.');
      dataFiles = files;
      const approved = new Set(dataFiles.map((file) => typeof file === 'string' ? file : (file?.path ?? file?.name ?? '')));
      if (!approved.has(selectedDataFile)) {
        const first = dataFiles[0];
        selectedDataFile = typeof first === 'string' ? first : (first?.path ?? first?.name ?? '');
      }
    } catch (caught) {
      dataFiles = [];
      selectedDataFile = '';
      dataCatalogError = caught instanceof Error ? caught.message : 'Data catalog request failed.';
    }
  }

  onMount(() => {
    loadAvailableModels();
    loadDataFiles();
  });

  async function loadModelAction() {
    if (loadingModel) return;
    const validation = validateForecastModelSelection(selectedModel, availableModels, device);
    if (validation.ok === false) {
      loadError = validation.error;
      modelLoaded = false;
      return;
    }
    loadingModel = true;
    loadError = null;
    try {
      const r = await fetch('/api/load-model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_key: validation.value.modelKey, device: validation.value.device }),
      });
      const d = await r.json();
      if (!r.ok || d.success === false) {
        loadError = d?.error ?? d?.message ?? `HTTP ${r.status}`;
        modelLoaded = false;
      } else {
        modelLoaded = true;
        currentModelLabel = availableModels[validation.value.modelKey]?.name ?? validation.value.modelKey;
      }
    } catch (e: any) {
      loadError = e?.message ?? '모델 로드 실패';
    } finally {
      loadingModel = false;
    }
  }

  async function loadDataAction() {
    if (loadingData) return;
    const validation = validateForecastDataSelection(selectedDataFile, dataFiles);
    if (validation.ok === false) {
      loadError = validation.error;
      dataLoaded = false;
      return;
    }
    loadingData = true;
    loadError = null;
    try {
      const r = await fetch('/api/load-data', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: validation.value }),
      });
      const d = await r.json();
      if (!r.ok || d.success === false) {
        loadError = d?.error ?? d?.message ?? `HTTP ${r.status}`;
        dataLoaded = false;
      } else {
        dataLoaded = true;
        currentDataLabel = validation.value.split(/[/\\]/).pop() ?? validation.value;
      }
    } catch (e: any) {
      loadError = e?.message ?? '데이터 로드 실패';
    } finally {
      loadingData = false;
    }
  }
  function clearPredictionEvidence() {
    predictionResult = null;
    predictionError = null;
  }
  function resetLoadedModel() {
    modelLoaded = false;
    currentModelLabel = '';
    clearPredictionEvidence();
  }

  function resetLoadedData() {
    dataLoaded = false;
    currentDataLabel = '';
    clearPredictionEvidence();
  }


  async function runPredict() {
    if (predicting) return;
    const validation = buildForecastPredictPayload({
      selectedModel,
      availableModels,
      modelLoaded,
      selectedDataFile,
      dataFiles,
      dataLoaded,
      lookback,
      predLen,
      sampleCount,
      temperature,
      topP,
      seedFixed,
      seed,
      device,
    });
    if (validation.ok === false) {
      predictionError = validation.error;
      return;
    }
    predictionResult = null;
    predicting = true;
    predictionError = null;
    try {
      const r = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(validation.value),
      });
      const responsePayload = await r.json();
      if (!r.ok || responsePayload?.success === false) {
        predictionError = responsePayload?.error ?? responsePayload?.message ?? `HTTP ${r.status}`;
        return;
      }
      const parsed = validateForecastPredictionResponse(responsePayload);
      if (parsed.ok === false) {
        predictionError = `Malformed /api/predict response: ${parsed.error}`;
        return;
      }
      predictionResult = parsed.value;
    } catch (caught) {
      predictionError = caught instanceof Error ? caught.message : '예측 실행 실패';
    } finally {
      predicting = false;
    }
  }

  // 결과 차트 옵션
  let chartOption = $derived.by(() => {
    void currentTheme;
    if (!predictionResult || typeof window === 'undefined') return {};
    const cs = getComputedStyle(document.documentElement);
    const accent = cs.getPropertyValue('--accent').trim();
    const c4 = cs.getPropertyValue('--c-4').trim();
    const grid = cs.getPropertyValue('--border-faint').trim();
    const text = cs.getPropertyValue('--fg').trim();
    const dim = cs.getPropertyValue('--dim').trim();
    const surface = cs.getPropertyValue('--surface').trim();

    const predSeries = predictionResult.prediction_results.map((point) => [point.timestamp, point.close]);
    const actualSeries = predictionResult.actual_data.map((point) => [point.timestamp, point.close]);

    return {
      backgroundColor: 'transparent',
      textStyle: { color: text, fontFamily: 'Pretendard Variable, sans-serif' },
      grid: { left: 56, right: 24, top: 24, bottom: 36 },
      xAxis: {
        type: 'category',
        axisLabel: { color: dim, fontSize: 10 },
        splitLine: { lineStyle: { color: grid } },
        axisLine: { lineStyle: { color: grid } },
      },
      yAxis: {
        type: 'value',
        scale: true,
        axisLabel: { color: dim, fontSize: 10 },
        splitLine: { lineStyle: { color: grid } },
        axisLine: { show: false },
      },
      tooltip: { trigger: 'axis', backgroundColor: surface, borderColor: grid, textStyle: { color: text, fontSize: 12 } },
      legend: { textStyle: { color: dim, fontSize: 11 }, icon: 'roundRect' },
      series: [
        { name: '예측', type: 'line', data: predSeries, smooth: 0.3, symbol: 'none', lineStyle: { color: accent, width: 2, type: 'solid' } },
        ...(actualSeries.length > 0 ? [{ name: '실측', type: 'line', data: actualSeries, smooth: 0.3, symbol: 'none', lineStyle: { color: c4, width: 1.5, type: 'dashed' as const } }] : []),
      ],
    };
  });
</script>

<section class="page-hero">
  <div class="row" style="gap:10px;flex-wrap:wrap">
    <span class="text-eyebrow">본격</span>
    <span class="pill {modelAvailable === true ? 'success' : modelAvailable === false ? 'warn' : ''}">
      <span class="dot"></span>
      {modelAvailable === true ? '모델 라이브러리 사용 가능' : modelAvailable === false ? '모델 라이브러리 미가용 (시뮬레이션)' : '확인 중'}
    </span>
    <span class="pill"><span class="dot" style="background:var(--info)"></span>/api/predict · POST</span>
  </div>
  <h1 class="text-h2" style="margin-top:8px">예측 워크벤치</h1>
  <p class="text-muted" style="margin-top:6px">
    사전학습 Kronos 모델로 K-line 연구용 시계열 출력을 생성합니다. 이 출력은 매매, 주문, 수익성, 모델 승격의 증거가 아닙니다.
    caps: lookback 1..4096 · pred_len 1..1024 · sample_count 1..16 · temperature 0.1..2 · top_p 0.1..1 · device cpu|cuda.
  </p>
  {#if modelImportError}
    <div class="card compact flat" style="background:var(--warn-soft);border-color:transparent;margin-top:10px;padding:10px 14px">
      <span class="text-caption">⚠ {modelImportError}</span>
    </div>
  {/if}
  {#if modelCatalogError}
    <div class="card compact flat" role="alert" style="background:var(--danger-soft);border-color:transparent;margin-top:10px;padding:10px 14px">
      <span class="text-caption" style="color:var(--danger)">Model catalog unavailable · {modelCatalogError}</span>
    </div>
  {/if}
</section>

<!-- ===== Setup: 모델 + 데이터 ===== -->
<section class="grid-2-setup">
  <div class="card">
    <div class="card-header">
      <div>
        <div class="card-eyebrow">MODEL · 사전학습 weight</div>
        <div class="card-title">모델 선택 / 로드</div>
      </div>
      {#if modelLoaded}
        <span class="pill success"><span class="dot"></span>{currentModelLabel}</span>
      {:else}
        <span class="pill"><span class="dot"></span>미로드</span>
      {/if}
    </div>
    <select
      class="fw-select"
      aria-label="예측 모델 선택"
      bind:value={selectedModel}
      onchange={resetLoadedModel}
      disabled={Object.keys(availableModels).length === 0}
    >
      {#each Object.entries(availableModels) as [key, m]}
        {@const meta = m as any}
        <option value={key}>{meta.name ?? key} · {meta.params ?? '?'} · ctx {meta.context_length ?? '?'}</option>
      {/each}
    </select>
    {#if selectedModel && availableModels[selectedModel]}
      <div class="text-caption" style="margin-top:8px;line-height:1.5">
        {availableModels[selectedModel].description}
      </div>
    {/if}
    <div class="row" style="gap:8px;margin-top:12px">
      <button class="btn primary" disabled={loadingModel || Object.keys(availableModels).length === 0} onclick={loadModelAction}>
        {loadingModel ? '로드 중…' : '모델 로드'}
      </button>
      <select class="fw-select" bind:value={device} onchange={resetLoadedModel} style="max-width:120px" aria-label="예측 실행 장치 선택">
        <option value="cpu">CPU</option>
        <option value="cuda">GPU (CUDA)</option>
      </select>
    </div>
  </div>

  <div class="card">
    <div class="card-header">
      <div>
        <div class="card-eyebrow">DATA · 입력 시계열</div>
        <div class="card-title">데이터 파일 선택 / 로드</div>
      </div>
      {#if dataLoaded}
        <span class="pill success"><span class="dot"></span>{currentDataLabel}</span>
      {:else}
        <span class="pill"><span class="dot"></span>미로드</span>
      {/if}
    </div>
    {#if dataCatalogError}
      <div class="text-caption" role="alert" style="color:var(--danger)">Data catalog unavailable · {dataCatalogError}</div>
    {:else if dataFiles.length === 0}
      <div class="text-caption">로드 가능한 데이터 파일이 없습니다</div>
    {:else}
      <select class="fw-select" bind:value={selectedDataFile} onchange={resetLoadedData} aria-label="예측 입력 데이터 파일 선택">
        {#each dataFiles as f}
          {@const path = typeof f === 'string' ? f : (f.path ?? f.name ?? '')}
          {@const label = path.split(/[/\\]/).pop()}
          <option value={path}>{label}</option>
        {/each}
      </select>
      <div class="text-caption" style="margin-top:8px">{selectedDataFile}</div>
    {/if}
    <div class="row" style="gap:8px;margin-top:12px">
      <button class="btn primary" disabled={loadingData || dataFiles.length === 0} onclick={loadDataAction}>
        {loadingData ? '로드 중…' : '데이터 로드'}
      </button>
    </div>
  </div>
</section>

{#if loadError}
  <div class="card" style="border-color:var(--danger-soft);background:var(--danger-soft)">
    <div class="text-caption" style="color:var(--danger);font-weight:600">⚠ {loadError}</div>
  </div>
{/if}

<!-- ===== Sliders ===== -->
<section class="card">
  <div class="card-header">
    <div>
      <div class="card-eyebrow">PARAMETERS · sampling</div>
      <div class="card-title">예측 파라미터</div>
    </div>
    <span class="pill"><span class="dot" style="background:var(--info)"></span>seed {seedFixed ? `고정 ${seed}` : '랜덤'}</span>
  </div>
  <div class="grid-2-params">
    <div class="param-row">
      <div class="row spread">
        <label for="lookback" class="lbl-sm">Lookback (입력 길이)</label>
        <span class="text-mono tnum" style="font-weight:600">{lookback}</span>
      </div>
      <input id="lookback" type="range" min={FORECAST_LIMITS.lookback.min} max={FORECAST_LIMITS.lookback.max} step="1" bind:value={lookback} />
      <div class="text-caption">최근 {lookback} step 의 캔들을 입력으로 사용 · 허용 {FORECAST_LIMITS.lookback.min}..{FORECAST_LIMITS.lookback.max}</div>
    </div>
    <div class="param-row">
      <div class="row spread">
        <label for="pred_len" class="lbl-sm">Pred Length (예측 길이)</label>
        <span class="text-mono tnum" style="font-weight:600">{predLen}</span>
      </div>
      <input id="pred_len" type="range" min={FORECAST_LIMITS.predLen.min} max={FORECAST_LIMITS.predLen.max} step="1" bind:value={predLen} />
      <div class="text-caption">앞으로 {predLen} step 의 캔들을 예측 · 허용 {FORECAST_LIMITS.predLen.min}..{FORECAST_LIMITS.predLen.max}</div>
    </div>
    <div class="param-row">
      <div class="row spread">
        <label for="temperature" class="lbl-sm">Temperature (다양성)</label>
        <span class="text-mono tnum" style="font-weight:600">{temperature.toFixed(2)}</span>
      </div>
      <input id="temperature" type="range" min={FORECAST_LIMITS.temperature.min} max={FORECAST_LIMITS.temperature.max} step="0.05" bind:value={temperature} />
      <div class="text-caption">허용 {FORECAST_LIMITS.temperature.min}..{FORECAST_LIMITS.temperature.max} · 낮을수록 보수적 · 높을수록 다양한 시나리오 생성</div>
    </div>
    <div class="param-row">
      <div class="row spread">
        <label for="top_p" class="lbl-sm">Top-P (누클리어스)</label>
        <span class="text-mono tnum" style="font-weight:600">{topP.toFixed(2)}</span>
      </div>
      <input id="top_p" type="range" min={FORECAST_LIMITS.topP.min} max={FORECAST_LIMITS.topP.max} step="0.05" bind:value={topP} />
      <div class="text-caption">허용 {FORECAST_LIMITS.topP.min}..{FORECAST_LIMITS.topP.max} · 누적 확률 {topP.toFixed(2)} 미만의 토큰만 샘플링</div>
    </div>
    <div class="param-row">
      <div class="row spread">
        <label for="sample_count" class="lbl-sm">Sample Count (시나리오 수)</label>
        <span class="text-mono tnum" style="font-weight:600">{sampleCount}</span>
      </div>
      <input id="sample_count" type="range" min={FORECAST_LIMITS.sampleCount.min} max={FORECAST_LIMITS.sampleCount.max} step="1" bind:value={sampleCount} />
      <div class="text-caption">/api/predict payload sample_count · 허용 {FORECAST_LIMITS.sampleCount.min}..{FORECAST_LIMITS.sampleCount.max} · n_samples 미사용</div>
    </div>
  </div>

  <div class="row" style="gap:16px;flex-wrap:wrap;border-top:1px solid var(--border-faint);padding-top:14px;margin-top:8px">
    <label class="row" style="gap:6px;cursor:pointer">
      <input type="checkbox" bind:checked={seedFixed} />
      <span class="text-caption">Seed 고정 (결정성)</span>
    </label>
    {#if seedFixed}
      <label class="row" style="gap:6px">
        <span class="text-caption">SEED</span>
        <input type="number" bind:value={seed} class="fw-input-num" min="0" max="2147483647" />
      </label>
    {/if}
    <button
      class="btn primary lg"
      style="margin-left:auto;min-width:160px"
      disabled={predicting}
      onclick={runPredict}
    >
      {#if predicting}
        예측 실행 중…
      {:else}
        <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">{@html ICONS.play}</svg>
        예측 실행
      {/if}
    </button>
  </div>

  {#if !modelLoaded || !dataLoaded}
    <div class="text-caption" style="margin-top:8px;color:var(--muted)">
      💡 예측 실행을 위해서는 모델과 데이터를 먼저 로드해야 합니다.
    </div>
  {/if}
</section>

<!-- ===== Results ===== -->
{#if predictionError}
  <div class="card" style="border-color:var(--danger-soft)">
    <div class="card-header">
      <div class="card-title" style="color:var(--danger)">예측 실패</div>
      <span class="pill danger"><span class="dot"></span>오류</span>
    </div>
    <div class="text-caption" style="white-space:pre-wrap">{predictionError}</div>
  </div>
{:else if predictionResult}
  <section class="card">
    <div class="card-header">
      <div>
        <div class="card-eyebrow">RESULT · /api/predict</div>
        <div class="card-title">{predictionResult.prediction_type}</div>
      </div>
      <div class="row" style="gap:8px;flex-wrap:wrap">
        <span class="pill success"><span class="dot"></span>완료</span>
        <span class="pill"><span class="dot"></span>{predictionResult.has_comparison ? '실측 비교 포함' : '예측만 기록'}</span>
      </div>
    </div>
    <div class="text-caption" style="margin-bottom:12px">{predictionResult.message}</div>
    <div class="row" style="gap:16px;flex-wrap:wrap;margin-bottom:12px">
      <span class="pill">예측 {predictionResult.prediction_results.length}</span>
      <span class="pill">실측 {predictionResult.actual_data.length}</span>
    </div>
    <EChartsRenderer option={chartOption} height="380px" caption="예측 vs 실제 종가 · 예측 워크벤치" />
  </section>
{/if}

<style>
  .page-hero { padding: 8px 0; }
  .grid-2-setup {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }
  .grid-2-params {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px 32px;
  }
  @media (max-width: 900px) {
    .grid-2-setup, .grid-2-params { grid-template-columns: 1fr; }
  }
  .fw-select {
    width: 100%;
    padding: 10px 12px;
    border-radius: var(--r-sm);
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--fg);
    font: 500 13px/1.3 var(--font-mono);
    cursor: pointer;
  }
  .fw-select:focus { border-color: var(--accent); }
  .fw-select:focus-visible,
  .fw-input-num:focus-visible,
  .param-row input[type="range"]:focus-visible {
    outline: 2px solid var(--accent-strong);
    outline-offset: 2px;
  }
  .fw-input-num {
    width: 100px;
    padding: 6px 10px;
    border-radius: var(--r-sm);
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--fg);
    font: 500 12px/1.3 var(--font-mono);
  }
  .lbl-sm {
    font: 600 12px/1.3 var(--font-display);
    color: var(--fg-strong);
  }
  .param-row {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .param-row input[type="range"] {
    -webkit-appearance: none;
    appearance: none;
    width: 100%;
    height: 6px;
    background: var(--surface-sunken);
    border-radius: var(--r-pill);
    outline: none;
  }
  .param-row input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: var(--accent);
    cursor: pointer;
    border: 2px solid var(--surface);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  }
  .param-row input[type="range"]::-moz-range-thumb {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: var(--accent);
    cursor: pointer;
    border: 2px solid var(--surface);
  }
  .btn.primary {
    background: var(--accent-strong);
  }
  .btn.primary:hover {
    background: var(--accent-strong);
    box-shadow: var(--shadow-sm);
  }
</style>
