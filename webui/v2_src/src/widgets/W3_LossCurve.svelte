<script lang="ts">
  import EChartsRenderer from '../charts/EChartsRenderer.svelte';
  import { lossPoints, theme } from '$lib/stores';
  import { fmt } from '$lib/format';

  let pts = $state<{ step: number; loss: number }[]>([]);
  lossPoints.subscribe((v) => (pts = v));

  let currentTheme = $state<'light' | 'dark'>('light');
  theme.subscribe((v) => (currentTheme = v));

  // 윈도우 토글 (100 / 500 / 전체)
  let windowSize = $state<100 | 500 | 'all'>(500);

  // CSS 변수 → JS 값 (theme 변경 시 재평가)
  let palette = $derived.by(() => {
    void currentTheme;
    if (typeof window === 'undefined') return null;
    const cs = getComputedStyle(document.documentElement);
    return {
      accent: cs.getPropertyValue('--accent').trim() || '#38bdf8',
      accentStrong: cs.getPropertyValue('--accent-strong').trim() || '#0891b2',
      c3: cs.getPropertyValue('--c-3').trim() || '#eab308',
      warn: cs.getPropertyValue('--warn').trim() || '#f59e0b',
      grid: cs.getPropertyValue('--border-faint').trim() || '#e2e8f0',
      border: cs.getPropertyValue('--border').trim() || '#cbd5e1',
      text: cs.getPropertyValue('--fg').trim() || '#1e293b',
      textDim: cs.getPropertyValue('--dim').trim() || '#64748b',
      surface: cs.getPropertyValue('--surface').trim() || '#ffffff',
    };
  });

  // 200-step rolling 평균
  function rollingAvg(arr: { step: number; loss: number }[], k: number): [number, number][] {
    const out: [number, number][] = [];
    for (let i = 0; i < arr.length; i++) {
      const from = Math.max(0, i - k);
      const slice = arr.slice(from, i + 1);
      const avg = slice.reduce((a, b) => a + b.loss, 0) / slice.length;
      out.push([arr[i].step, avg]);
    }
    return out;
  }

  let visible = $derived.by(() => {
    if (windowSize === 'all') return pts;
    return pts.slice(-windowSize);
  });

  let stats = $derived.by(() => {
    if (visible.length === 0) return { min: null, max: null };
    const losses = visible.map((p) => p.loss);
    return { min: Math.min(...losses), max: Math.max(...losses) };
  });

  let option = $derived.by(() => {
    void currentTheme;
    if (!palette) return {};
    const stepData = visible.map((p): [number, number] => [p.step, p.loss]);
    const avgData = rollingAvg(visible, Math.min(60, visible.length));
    return {
      backgroundColor: 'transparent',
      textStyle: { color: palette.text, fontFamily: 'Pretendard Variable, sans-serif' },
      grid: { left: 56, right: 24, top: 24, bottom: 60 },
      xAxis: {
        type: 'value',
        name: 'Step',
        nameTextStyle: { color: palette.textDim, fontSize: 11 },
        axisLabel: { color: palette.textDim, fontSize: 10 },
        splitLine: { lineStyle: { color: palette.grid } },
        axisLine: { lineStyle: { color: palette.border } },
        scale: true,
        min: 'dataMin',
        max: 'dataMax',
      },
      yAxis: {
        type: 'value',
        name: 'Loss',
        nameTextStyle: { color: palette.textDim, fontSize: 11 },
        axisLabel: { color: palette.textDim, fontSize: 10 },
        splitLine: { lineStyle: { color: palette.grid } },
        axisLine: { lineStyle: { color: palette.border } },
        scale: true,
      },
      dataZoom: [
        { type: 'inside', xAxisIndex: 0, throttle: 50 },
        {
          type: 'slider',
          xAxisIndex: 0,
          height: 18,
          bottom: 6,
          backgroundColor: 'transparent',
          borderColor: palette.border,
          fillerColor: palette.accent + '33',
          handleStyle: { color: palette.accent, borderColor: palette.accent },
          textStyle: { color: palette.textDim, fontSize: 9 },
        },
      ],
      tooltip: {
        trigger: 'axis',
        backgroundColor: palette.surface,
        borderColor: palette.border,
        textStyle: { color: palette.text, fontSize: 12 },
      },
      series: [
        {
          name: 'step loss',
          type: 'line',
          data: stepData,
          smooth: 0.4,
          symbol: 'none',
          lineStyle: { color: palette.accent, width: 1.5 },
          areaStyle: {
            color: {
              type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: palette.accent + '40' },
                { offset: 1, color: palette.accent + '00' },
              ],
            },
          },
        },
        {
          name: 'rolling avg',
          type: 'line',
          data: avgData,
          smooth: 0.6,
          symbol: 'none',
          lineStyle: { color: palette.c3, width: 2 },
        },
      ],
    };
  });
</script>

<div class="card">
  <div class="card-header">
    <div>
      <div class="card-eyebrow">W3 · /api/training/history</div>
      <div class="card-title">학습 손실 곡선</div>
    </div>
    <div class="row" style="gap:8px">
      <div class="tabs" data-tab-group="loss-window">
        <button data-active={windowSize === 100 ? 'true' : 'false'} onclick={() => (windowSize = 100)}>100</button>
        <button data-active={windowSize === 500 ? 'true' : 'false'} onclick={() => (windowSize = 500)}>500</button>
        <button data-active={windowSize === 'all' ? 'true' : 'false'} onclick={() => (windowSize = 'all')}>전체</button>
      </div>
    </div>
  </div>

  <div class="row" style="gap:16px;flex-wrap:wrap;color:var(--muted);font-size:12px">
    <span class="legend"><span class="swatch" style="background:var(--accent)"></span>step loss</span>
    <span class="legend"><span class="swatch" style="background:var(--c-3)"></span>rolling avg</span>
    <span style="margin-left:auto" class="text-caption">스크롤 / 슬라이더로 줌</span>
  </div>

  <EChartsRenderer {option} height="380px" />

  <div class="row spread" style="border-top:1px solid var(--border-faint);padding-top:12px;margin-top:8px">
    <div class="row" style="gap:18px;flex-wrap:wrap">
      <span class="text-caption">최저 <span class="text-mono tnum" style="color:var(--success);font-weight:600">{stats.min != null ? stats.min.toFixed(4) : '—'}</span></span>
      <span class="text-caption">최고 <span class="text-mono tnum" style="color:var(--danger);font-weight:600">{stats.max != null ? stats.max.toFixed(4) : '—'}</span></span>
      <span class="text-caption">표시 <span class="text-mono tnum" style="color:var(--fg)">{visible.length}</span> 포인트</span>
    </div>
  </div>
</div>
