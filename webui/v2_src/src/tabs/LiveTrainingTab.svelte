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
      { key: 'train', label: '??', tone: 'accent' },
      { key: 'val', label: '??', tone: 'info' },
      { key: 'test', label: '???', tone: 'warn' },
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
      open: '??',
      high: '??',
      low: '??',
      close: '??/???',
      vol: '???',
      amt: '????',
      minute: '?',
      hour: '?',
      weekday: '??',
      day: '?',
      month: '?',
    };
    return labels[value] ?? value;
  }
</script>

<!-- ===== ?? ??? ?? ===== -->
<section class="grid-1-1-1-1">
  <div class="metric glow">
    <div class="metric-head">
      <span class="metric-label">?? ??</span>
      {#if trend.dir !== 'flat'}
        <span class="delta {trend.dir === 'down' ? 'down' : 'up'}">
          {trend.dir === 'down' ? '? ??' : '? ??'} {fmt.num(trend.pct, 1)}%
        </span>
      {:else}
        <span class="delta flat">? 0.0%</span>
      {/if}
    </div>
    <div class="metric-value tnum">
      {m.loss != null ? m.loss.toFixed(4) : '-'}<span class="metric-unit">???</span>
    </div>
    <div class="metric-foot">
      ?? <span class="text-mono" style="color:var(--fg)">{stats.mean != null ? stats.mean.toFixed(4) : '-'}</span>
      ? <span class="text-mono" style="color:var(--fg)">{stats.std != null ? stats.std.toFixed(4) : '-'}</span>
    </div>
  </div>

  <div class="metric">
    <div class="metric-head">
      <span class="metric-label">?? ???</span>
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
      <span class="metric-label">?? ??</span>
      <span class="pill success" style="padding:2px 8px;font-size:10px">live</span>
    </div>
    <div class="metric-value tnum">
      {fmt.num(m.samplesPerSec, 1)}<span class="metric-unit">samples/s</span>
    </div>
    <div class="metric-foot">?? batch ?? ???</div>
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
      ?? ?? <span class="text-mono" style="color:var(--fg)">{lr != null ? lr.toFixed(6) : '-'}</span>
    </div>
  </div>
</section>

<!-- ===== ?? ??? ?? / ?? ?? ===== -->
{#if dataset?.available}
  <section class="card dataset-card glow" aria-label="STOM ?? ??? ?? ??">
    <div class="dataset-hero">
      <div>
        <div class="text-eyebrow">DATASET SCOPE</div>
        <h2>STOM 2025 ?? 1?? ? pred{dataset.horizon_seconds ?? dataset.predict_window ?? '-'}</h2>
        <p>
          ?? Kronos OHLCV ??? ?? <strong>{dataset.features?.map(featureLabel).join(' ? ')}</strong>? ????,
          ?? feature? <strong>{dataset.time_features?.map(featureLabel).join(' ? ')}</strong>? ?????.
        </p>
      </div>
      <div class="dataset-badges" aria-label="??? ??">
        <span class="pill accent">{dataset.freq ?? '1s'}</span>
        <span class="pill">{hms(dataset.range?.time_start)}~{hms(dataset.range?.time_end)}</span>
        <span class="pill">lookback {fmt.int(dataset.lookback_window)}</span>
        <span class="pill">window {fmt.int(dataset.sample_window)}</span>
        {#if dataset.regularize_1s}<span class="pill success">1? ???</span>{/if}
      </div>
    </div>

    <div class="dataset-metrics">
      <div class="dataset-mini">
        <span>?? samples</span>
        <strong class="tnum">{fmt.int(dataset.current_targets?.train_samples)}</strong>
        <small>?? {fmt.int(dataset.current_targets?.val_samples)}</small>
      </div>
      <div class="dataset-mini">
        <span>?? rows</span>
        <strong class="tnum">{fmt.int(dataset.counts?.exported_row_count)}</strong>
        <small>?? {fmt.int(dataset.counts?.exported_group_count)}</small>
      </div>
      <div class="dataset-mini">
        <span>?? ???</span>
        <strong class="tnum">{fmt.int(dataset.counts?.tables_with_rows)}</strong>
        <small>?? {fmt.int(dataset.counts?.table_count)} ? 0? {fmt.int(dataset.counts?.tables_zero_rows)}</small>
      </div>
      <div class="dataset-mini">
        <span>?? ???</span>
        <strong>{ymd(dataset.range?.actual_start)}</strong>
        <small>~ {ymd(dataset.range?.actual_end)}</small>
      </div>
    </div>

    <div class="dataset-detail-grid">
      <div class="split-table" role="table" aria-label="?? ?? ??? ??">
        <div class="split-row split-head" role="row">
          <span>??</span>
          <span>??</span>
          <span>??</span>
          <span>??</span>
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
          <strong>??:</strong> price_mode? <code>{dataset.price_mode ?? '-'}</code>?? STOM tick DB? ??? ???? OHLC? ?????.
          {#if dataset.warnings?.length}
            <br />{dataset.warnings[0]}
          {/if}
        </div>
      </div>
    </div>

    <div class="dataset-source text-caption">
      DB: <span class="text-mono">{dataset.source_db ?? '-'}</span>
      ? Report: <span class="text-mono">{dataset.report_path ?? '-'}</span>
    </div>
  </section>
{:else if dataset}
  <section class="card dataset-card dataset-card-warn" aria-label="STOM ?? ??? ?? ?? ??">
    <div class="dataset-hero">
      <div>
        <div class="text-eyebrow">DATASET SCOPE</div>
        <h2>??? ??? ?? ?? ?????</h2>
        <p>{dataset.message ?? '?? run? Qlib export report? ?? ????.'}</p>
      </div>
      <span class="pill warn">?? ??</span>
    </div>
  </section>
{/if}

<!-- ===== ?? ?? + ??? ===== -->
<section class="grid-3-1">
  <W3LossCurve />
  <W6LossVolatility {stats} {trend} />
</section>

<!-- ===== ETA ???? ===== -->
<W4EtaTimeline />

<!-- ===== GPU ?? ===== -->
<W5GpuSparkline />

<!-- ===== ?? tail ===== -->
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
