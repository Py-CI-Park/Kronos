<script lang="ts">
  import { metricsLatest, lossPoints, trainingStatus } from '$lib/stores';
  import { fmt } from '$lib/format';
  import type { DatasetSplitSummary, TrainingStatus } from '$lib/api';
  import W3LossCurve from '$widgets/W3_LossCurve.svelte';
  import W4EtaTimeline from '$widgets/W4_EtaTimeline.svelte';
  import W5GpuSparkline from '$widgets/W5_GpuSparkline.svelte';
  import W6LossVolatility from '$widgets/W6_LossVolatility.svelte';
  import W9LogTail from '$widgets/W9_LogTail.svelte';

  type SplitRow = {
    key: 'train' | 'val' | 'test';
    label: string;
    tone: 'accent' | 'info' | 'warn';
    summary: DatasetSplitSummary;
  };

  let m = $state<any>({});
  metricsLatest.subscribe((v) => (m = v));

  let pts = $state<{ step: number; loss: number }[]>([]);
  lossPoints.subscribe((v) => (pts = v));

  let status = $state<TrainingStatus | null>(null);
  trainingStatus.subscribe((v) => (status = v));

  const stats = $derived.by(() => {
    const window = pts.slice(-200);
    if (window.length === 0) return { mean: null, std: null, min: null, max: null, n: 0 };
    const losses = window.map((p) => p.loss);
    const mean = losses.reduce((a, b) => a + b, 0) / losses.length;
    const variance = losses.reduce((a, b) => a + (b - mean) ** 2, 0) / losses.length;
    const std = Math.sqrt(variance);
    return {
      mean,
      std,
      min: Math.min(...losses),
      max: Math.max(...losses),
      n: window.length,
    };
  });

  const trend = $derived.by(() => {
    if (pts.length < 100) return { dir: 'flat' as const, pct: 0 };
    const recent = pts.slice(-50).map((p) => p.loss);
    const prev = pts.slice(-100, -50).map((p) => p.loss);
    const rAvg = recent.reduce((a, b) => a + b, 0) / recent.length;
    const pAvg = prev.reduce((a, b) => a + b, 0) / prev.length;
    if (Math.abs(rAvg - pAvg) < 1e-6) return { dir: 'flat' as const, pct: 0 };
    const pct = pAvg !== 0 ? Math.abs((rAvg - pAvg) / pAvg) * 100 : 0;
    return { dir: rAvg < pAvg ? ('down' as const) : ('up' as const), pct };
  });

  let lr = $derived(m.learningRate);
  const dataset = $derived(status?.dataset_summary ?? null);

  const splitRows = $derived.by<SplitRow[]>(() => {
    const splits = dataset?.splits ?? {};
    const rows: Array<{ key: 'train' | 'val' | 'test'; label: string; tone: 'accent' | 'info' | 'warn' }> = [
      { key: 'train', label: '학습', tone: 'accent' },
      { key: 'val', label: '검증', tone: 'info' },
      { key: 'test', label: '테스트', tone: 'warn' },
    ];
    return rows
      .map((row) => ({ ...row, summary: splits[row.key] }))
      .filter((row): row is SplitRow => Boolean(row.summary));
  });

  function ymd(value?: string | null): string {
    if (!value || value.length !== 8) return value ?? '-';
    return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`;
  }

  function hms(value?: string | null): string {
    if (!value || value.length < 6) return value ?? '-';
    return `${value.slice(0, 2)}:${value.slice(2, 4)}:${value.slice(4, 6)}`;
  }

  function featureLabel(value: string): string {
    const labels: Record<string, string> = {
      open: '시가',
      high: '고가',
      low: '저가',
      close: '종가/현재가',
      vol: '거래량',
      amt: '거래대금',
      minute: '분',
      hour: '시',
      weekday: '요일',
      day: '일',
      month: '월',
    };
    return labels[value] ?? value;
  }
</script>

<!-- ===== 핵심 실시간 지표 ===== -->
<section class="grid-1-1-1-1">
  <div class="metric glow">
    <div class="metric-head">
      <span class="metric-label">현재 손실</span>
      {#if trend.dir !== 'flat'}
        <span class="delta {trend.dir === 'down' ? 'down' : 'up'}">
          {trend.dir === 'down' ? '↓ 개선' : '↑ 상승'} {fmt.num(trend.pct, 1)}%
        </span>
      {:else}
        <span class="delta flat">→ 0.0%</span>
      {/if}
    </div>
    <div class="metric-value tnum">
      {m.loss != null ? m.loss.toFixed(4) : '-'}<span class="metric-unit">최근값</span>
    </div>
    <div class="metric-foot">
      평균 <span class="text-mono" style="color:var(--fg)">{stats.mean != null ? stats.mean.toFixed(4) : '-'}</span>
      ± <span class="text-mono" style="color:var(--fg)">{stats.std != null ? stats.std.toFixed(4) : '-'}</span>
    </div>
  </div>

  <div class="metric">
    <div class="metric-head">
      <span class="metric-label">단계 진행률</span>
      <span class="pill accent" style="padding:2px 8px;font-size:10px">step</span>
    </div>
    <div class="metric-value tnum">
      {status?.latest_stage?.stage_percent != null ? status.latest_stage.stage_percent.toFixed(1) : '-'}<span class="metric-unit">%</span>
    </div>
    <div class="metric-foot">
      step <span class="text-mono" style="color:var(--fg)">{fmt.int(status?.latest_stage?.step)}</span>
      / {fmt.int(status?.latest_stage?.total_steps)}
    </div>
  </div>

  <div class="metric">
    <div class="metric-head">
      <span class="metric-label">처리 속도</span>
      <span class="pill success" style="padding:2px 8px;font-size:10px">live</span>
    </div>
    <div class="metric-value tnum">
      {fmt.num(m.samplesPerSec, 1)}<span class="metric-unit">samples/s</span>
    </div>
    <div class="metric-foot">현재 batch 기준 처리량</div>
  </div>

  <div class="metric">
    <div class="metric-head">
      <span class="metric-label">Learning Rate</span>
      <span class="pill" style="padding:2px 8px;font-size:10px">scheduled</span>
    </div>
    <div class="metric-value mono tnum">
      {lr != null ? lr.toExponential(2) : '-'}
    </div>
    <div class="metric-foot">
      소수 표기 <span class="text-mono" style="color:var(--fg)">{lr != null ? lr.toFixed(6) : '-'}</span>
    </div>
  </div>
</section>

<!-- ===== 학습 데이터 범위 / 특징 요약 ===== -->
{#if dataset?.available}
  <section class="card dataset-card glow" aria-label="STOM 학습 데이터 범위 요약">
    <div class="dataset-hero">
      <div>
        <div class="text-eyebrow">DATASET SCOPE</div>
        <h2>STOM 2025 전체 1초봉 · pred{dataset.horizon_seconds ?? dataset.predict_window ?? '-'}</h2>
        <p>
          공식 Kronos OHLCV 입력에 맞춰 <strong>{dataset.features?.map(featureLabel).join(' · ')}</strong>를 사용하고,
          시간 feature는 <strong>{dataset.time_features?.map(featureLabel).join(' · ')}</strong>로 보강합니다.
        </p>
      </div>
      <div class="dataset-badges" aria-label="데이터 설정">
        <span class="pill accent">{dataset.freq ?? '1s'}</span>
        <span class="pill">{hms(dataset.range?.time_start)}~{hms(dataset.range?.time_end)}</span>
        <span class="pill">lookback {fmt.int(dataset.lookback_window)}</span>
        <span class="pill">window {fmt.int(dataset.sample_window)}</span>
        {#if dataset.regularize_1s}<span class="pill success">1초 정규화</span>{/if}
      </div>
    </div>

    <div class="dataset-metrics">
      <div class="dataset-mini">
        <span>학습 samples</span>
        <strong class="tnum">{fmt.int(dataset.current_targets?.train_samples)}</strong>
        <small>검증 {fmt.int(dataset.current_targets?.val_samples)}</small>
      </div>
      <div class="dataset-mini">
        <span>전체 rows</span>
        <strong class="tnum">{fmt.int(dataset.counts?.exported_row_count)}</strong>
        <small>그룹 {fmt.int(dataset.counts?.exported_group_count)}</small>
      </div>
      <div class="dataset-mini">
        <span>종목 테이블</span>
        <strong class="tnum">{fmt.int(dataset.counts?.tables_with_rows)}</strong>
        <small>전체 {fmt.int(dataset.counts?.table_count)} · 0행 {fmt.int(dataset.counts?.tables_zero_rows)}</small>
      </div>
      <div class="dataset-mini">
        <span>실제 거래일</span>
        <strong>{ymd(dataset.range?.actual_start)}</strong>
        <small>~ {ymd(dataset.range?.actual_end)}</small>
      </div>
    </div>

    <div class="dataset-detail-grid">
      <div class="split-table" role="table" aria-label="학습 검증 테스트 분할">
        <div class="split-row split-head" role="row">
          <span>구간</span>
          <span>기간</span>
          <span>세션</span>
          <span>그룹</span>
          <span>rows</span>
          <span>samples</span>
        </div>
        {#each splitRows as row (row.key)}
          <div class="split-row" role="row">
            <span><span class="pill {row.tone}">{row.label}</span></span>
            <span>{ymd(row.summary.first_session)} ~ {ymd(row.summary.last_session)}</span>
            <span class="tnum">{fmt.int(row.summary.sessions)}</span>
            <span class="tnum">{fmt.int(row.summary.groups)}</span>
            <span class="tnum">{fmt.int(row.summary.rows)}</span>
            <span class="tnum">{fmt.int(row.summary.current_target_samples ?? row.summary.possible_samples)}</span>
          </div>
        {/each}
      </div>

      <div class="feature-panel">
        <div>
          <div class="text-eyebrow">FEATURES</div>
          <div class="feature-chips">
            {#each dataset.features ?? [] as feature}
              <span class="feature-chip">{featureLabel(feature)}<em>{feature}</em></span>
            {/each}
          </div>
        </div>
        <div>
          <div class="text-eyebrow">TIME FEATURES</div>
          <div class="feature-chips muted">
            {#each dataset.time_features ?? [] as feature}
              <span class="feature-chip">{featureLabel(feature)}<em>{feature}</em></span>
            {/each}
          </div>
        </div>
        <div class="dataset-note">
          <strong>주의:</strong> price_mode가 <code>{dataset.price_mode ?? '-'}</code>이면 STOM tick DB의 현재가 기반으로 OHLC가 구성됩니다.
          {#if dataset.warnings?.length}
            <br />{dataset.warnings[0]}
          {/if}
        </div>
      </div>
    </div>

    <div class="dataset-source text-caption">
      DB: <span class="text-mono">{dataset.source_db ?? '-'}</span>
      · Report: <span class="text-mono">{dataset.report_path ?? '-'}</span>
    </div>
  </section>
{:else if dataset}
  <section class="card dataset-card dataset-card-warn" aria-label="STOM 학습 데이터 범위 요약 없음">
    <div class="dataset-hero">
      <div>
        <div class="text-eyebrow">DATASET SCOPE</div>
        <h2>데이터 요약을 아직 읽지 못했습니다</h2>
        <p>{dataset.message ?? '현재 run의 Qlib export report를 찾는 중입니다.'}</p>
      </div>
      <span class="pill warn">확인 필요</span>
    </div>
  </section>
{/if}

<!-- ===== 손실 곡선 + 변동성 ===== -->
<section class="grid-3-1">
  <W3LossCurve />
  <W6LossVolatility {stats} {trend} />
</section>

<!-- ===== ETA 타임라인 ===== -->
<W4EtaTimeline />

<!-- ===== GPU 추세 ===== -->
<W5GpuSparkline />

<!-- ===== 로그 tail ===== -->
<W9LogTail />

<style>
  .grid-1-1-1-1 {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
  }
  .grid-3-1 {
    display: grid;
    grid-template-columns: 3fr 1fr;
    gap: 16px;
  }

  .dataset-card {
    overflow: hidden;
  }
  .dataset-card::before {
    content: '';
    position: absolute;
    inset: 0 0 auto 0;
    height: 4px;
    background: linear-gradient(90deg, var(--accent), color-mix(in oklab, var(--accent) 45%, var(--warm)));
  }
  .dataset-card-warn::before {
    background: linear-gradient(90deg, var(--warn), var(--warm));
  }
  .dataset-hero {
    display: flex;
    justify-content: space-between;
    gap: 18px;
    align-items: flex-start;
  }
  .dataset-hero h2 {
    margin-top: 4px;
    font: 700 22px/1.25 var(--font-display);
    letter-spacing: -0.018em;
    color: var(--fg-strong);
  }
  .dataset-hero p {
    margin-top: 8px;
    max-width: 780px;
    color: var(--muted);
  }
  .dataset-hero strong {
    color: var(--fg-strong);
    font-weight: 700;
  }
  .dataset-badges {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 8px;
    min-width: min(360px, 100%);
  }
  .dataset-metrics {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
  }
  .dataset-mini {
    padding: 14px 16px;
    border: 1px solid var(--border-faint);
    border-radius: var(--r-md);
    background: color-mix(in oklab, var(--surface-raised) 82%, var(--accent-soft));
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }
  .dataset-mini span,
  .dataset-mini small {
    color: var(--muted);
    font: 600 11px/1.35 var(--font-display);
  }
  .dataset-mini strong {
    color: var(--fg-strong);
    font: 700 21px/1.15 var(--font-display);
    letter-spacing: -0.012em;
    word-break: keep-all;
  }
  .dataset-detail-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.6fr) minmax(300px, 0.9fr);
    gap: 16px;
  }
  .split-table {
    border: 1px solid var(--border-faint);
    border-radius: var(--r-md);
    overflow: hidden;
    background: var(--surface);
  }
  .split-row {
    display: grid;
    grid-template-columns: 74px 1.25fr 0.55fr 0.65fr 0.8fr 0.9fr;
    align-items: center;
    gap: 10px;
    padding: 11px 14px;
    border-top: 1px solid var(--border-faint);
    font: 500 12px/1.35 var(--font-mono);
  }
  .split-row:first-child {
    border-top: none;
  }
  .split-head {
    background: var(--surface-sunken);
    color: var(--muted);
    font: 700 11px/1.2 var(--font-display);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .feature-panel {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 16px;
    border-radius: var(--r-md);
    border: 1px solid var(--border-faint);
    background: var(--surface-raised);
  }
  .feature-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 8px;
  }
  .feature-chip {
    display: inline-flex;
    align-items: baseline;
    gap: 6px;
    padding: 7px 10px;
    border-radius: var(--r-pill);
    background: var(--accent-soft);
    color: var(--accent-strong);
    font: 700 12px/1 var(--font-display);
  }
  :global([data-theme='dark']) .feature-chip {
    color: var(--accent);
  }
  .feature-chips.muted .feature-chip {
    background: var(--surface-sunken);
    color: var(--muted);
  }
  .feature-chip em {
    font: 600 10px/1 var(--font-mono);
    opacity: 0.72;
    font-style: normal;
  }
  .dataset-note {
    padding: 12px;
    border-radius: var(--r-md);
    background: var(--warm-soft);
    color: var(--fg);
    font-size: 12px;
    line-height: 1.55;
  }
  .dataset-note code {
    font-family: var(--font-mono);
    color: var(--accent-strong);
  }
  .dataset-source {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding-top: 2px;
    word-break: break-all;
  }

  @media (max-width: 1200px) {
    .grid-1-1-1-1 { grid-template-columns: repeat(2, 1fr); }
    .grid-3-1 { grid-template-columns: 1fr; }
    .dataset-metrics { grid-template-columns: repeat(2, 1fr); }
    .dataset-detail-grid { grid-template-columns: 1fr; }
  }
  @media (max-width: 760px) {
    .dataset-hero { flex-direction: column; }
    .dataset-badges { justify-content: flex-start; min-width: 0; }
    .split-table { overflow-x: auto; }
    .split-row { min-width: 740px; }
  }
  @media (max-width: 560px) {
    .grid-1-1-1-1 { grid-template-columns: 1fr; }
    .dataset-metrics { grid-template-columns: 1fr; }
  }
</style>
