<script lang="ts">
  import { metricsLatest, lossPoints, gpuStatus, gpuRing, trainingStatus } from '$lib/stores';
  import { fmt } from '$lib/format';
  import W3LossCurve from '$widgets/W3_LossCurve.svelte';
  import W4EtaTimeline from '$widgets/W4_EtaTimeline.svelte';
  import W5GpuSparkline from '$widgets/W5_GpuSparkline.svelte';
  import W6LossVolatility from '$widgets/W6_LossVolatility.svelte';

  let m = $state<any>({});
  metricsLatest.subscribe((v) => (m = v));

  let pts = $state<{ step: number; loss: number }[]>([]);
  lossPoints.subscribe((v) => (pts = v));

  let status = $state<any>(null);
  trainingStatus.subscribe((v) => (status = v));

  // 손실 통계 — 최근 200개 윈도우
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

  // 손실 추세 (최근 50개 vs 그 이전 50개 평균 비교)
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
</script>

<!-- ===== METRIC STRIP (4 cards) ===== -->
<section class="grid-1-1-1-1">
  <div class="metric">
    <div class="metric-head">
      <span class="metric-label">현재 손실</span>
      {#if trend.dir !== 'flat'}
        <span class="delta {trend.dir === 'down' ? 'down' : 'up'}">
          {trend.dir === 'down' ? '▼' : '▲'} {fmt.num(trend.pct, 1)}%
        </span>
      {:else}
        <span class="delta flat">— 0.0%</span>
      {/if}
    </div>
    <div class="metric-value tnum">
      {m.loss != null ? m.loss.toFixed(4) : '—'}<span class="metric-unit">최근값</span>
    </div>
    <div class="metric-foot">
      μ <span class="text-mono" style="color:var(--fg)">{stats.mean != null ? stats.mean.toFixed(4) : '—'}</span>
      · σ <span class="text-mono" style="color:var(--fg)">{stats.std != null ? stats.std.toFixed(4) : '—'}</span>
    </div>
  </div>

  <div class="metric">
    <div class="metric-head">
      <span class="metric-label">학습 진척</span>
      <span class="pill accent" style="padding:2px 8px;font-size:10px">step</span>
    </div>
    <div class="metric-value tnum">
      {status?.latest_stage?.stage_percent != null ? status.latest_stage.stage_percent.toFixed(1) : '—'}<span class="metric-unit">% 단계</span>
    </div>
    <div class="metric-foot">
      step <span class="text-mono" style="color:var(--fg)">{fmt.int(status?.latest_stage?.step)}</span>
      / {fmt.int(status?.latest_stage?.total_steps)}
    </div>
  </div>

  <div class="metric">
    <div class="metric-head">
      <span class="metric-label">처리 속도</span>
      <span class="pill" style="padding:2px 8px;font-size:10px">live</span>
    </div>
    <div class="metric-value tnum">
      {fmt.num(m.samplesPerSec, 1)}<span class="metric-unit">samples/s</span>
    </div>
    <div class="metric-foot">batch 기준 추정 step/min</div>
  </div>

  <div class="metric">
    <div class="metric-head">
      <span class="metric-label">Learning Rate</span>
      <span class="pill" style="padding:2px 8px;font-size:10px">scheduled</span>
    </div>
    <div class="metric-value mono tnum">
      {lr != null ? lr.toExponential(2) : '—'}
    </div>
    <div class="metric-foot">
      소수 표기 <span class="text-mono" style="color:var(--fg)">{lr != null ? lr.toFixed(6) : '—'}</span>
    </div>
  </div>
</section>

<!-- ===== W3 LOSS CURVE + W6 VOLATILITY ===== -->
<section class="grid-3-1">
  <W3LossCurve />
  <W6LossVolatility {stats} {trend} />
</section>

<!-- ===== W4 ETA TIMELINE ===== -->
<W4EtaTimeline />

<!-- ===== W5 GPU TREND ===== -->
<W5GpuSparkline />

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
  @media (max-width: 1200px) {
    .grid-1-1-1-1 { grid-template-columns: repeat(2, 1fr); }
    .grid-3-1 { grid-template-columns: 1fr; }
  }
  @media (max-width: 560px) {
    .grid-1-1-1-1 { grid-template-columns: 1fr; }
  }
</style>
