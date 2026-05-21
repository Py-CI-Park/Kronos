<script lang="ts">
  import EChartsRenderer from '../charts/EChartsRenderer.svelte';
  import { gpuRing, gpuStatus, theme } from '$lib/stores';
  import { fmt } from '$lib/format';

  let ring = $state<any[]>([]);
  gpuRing.subscribe((v) => (ring = v));

  let gpu = $state<any>(null);
  gpuStatus.subscribe((v) => (gpu = v));

  let currentTheme = $state<'light' | 'dark'>('light');
  theme.subscribe((v) => (currentTheme = v));

  let g = $derived(gpu?.gpus?.[0]);

  type GpuTrendPoint = {
    util: number | null;
    temp: number | null;
    vram: number | null;
    ts: number;
  };

  function currentGpuPoint(): GpuTrendPoint | null {
    if (!g) return null;
    return {
      util: g.utilization_gpu_percent ?? null,
      temp: g.temperature_c ?? null,
      vram: g.memory_used_percent ?? null,
      ts: Date.now(),
    };
  }

  function formatTime(ts: number | null | undefined): string {
    if (!ts) return '—';
    return new Date(ts).toLocaleTimeString('ko-KR', {
      timeZone: 'Asia/Seoul',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  }

  function formatGpuTooltip(params: any, points: GpuTrendPoint[]): string {
    const rows = Array.isArray(params) ? params : [params];
    const idx = rows[0]?.dataIndex ?? 0;
    const point = points[idx];
    const body = rows
      .map((p: any) => {
        const value = p.value;
        if (value == null || Number.isNaN(Number(value))) return '';
        const unit = p.seriesName?.includes('온도') ? '°C' : '%';
        return `<div style="display:flex;gap:10px;justify-content:space-between;min-width:170px">
          <span>${p.marker ?? ''}${p.seriesName}</span>
          <b>${Number(value).toFixed(1)}${unit}</b>
        </div>`;
      })
      .filter(Boolean)
      .join('');
    return `<div style="font-weight:700;margin-bottom:4px">${formatTime(point?.ts)}</div>${body}`;
  }

  let chartRing = $derived.by(() => {
    if (ring.length > 0) return ring as GpuTrendPoint[];
    const point = currentGpuPoint();
    return point ? [point] : [];
  });

  let palette = $derived.by(() => {
    void currentTheme;
    if (typeof window === 'undefined') return null;
    const cs = getComputedStyle(document.documentElement);
    return {
      c2: cs.getPropertyValue('--c-2').trim() || '#3b82f6',
      c3: cs.getPropertyValue('--c-3').trim() || '#eab308',
      c4: cs.getPropertyValue('--c-4').trim() || '#f97316',
      grid: cs.getPropertyValue('--border-faint').trim() || '#e2e8f0',
      border: cs.getPropertyValue('--border').trim() || '#cbd5e1',
      text: cs.getPropertyValue('--fg').trim() || '#1e293b',
      textDim: cs.getPropertyValue('--dim').trim() || '#64748b',
      surface: cs.getPropertyValue('--surface').trim() || '#ffffff',
    };
  });

  let option = $derived.by(() => {
    void currentTheme;
    if (!palette) return {};
    const data = chartRing;
    const xs = data.map((p) => formatTime(p.ts));
    const showSymbols = data.length <= 2;
    return {
      backgroundColor: 'transparent',
      textStyle: { color: palette.text, fontFamily: 'Pretendard Variable, sans-serif' },
      grid: { left: 40, right: 24, top: 20, bottom: 32 },
      xAxis: {
        type: 'category',
        data: xs,
        axisLabel: { show: false },
        axisLine: { lineStyle: { color: palette.border } },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        axisLabel: { color: palette.textDim, fontSize: 10, formatter: '{value}%' },
        splitLine: { lineStyle: { color: palette.grid } },
        axisLine: { show: false },
      },
      tooltip: {
        trigger: 'axis',
        appendToBody: true,
        confine: true,
        axisPointer: { type: 'line', lineStyle: { color: palette.border, type: 'dashed' } },
        backgroundColor: palette.surface,
        borderColor: palette.border,
        textStyle: { color: palette.text, fontSize: 12 },
        formatter: (params: any) => formatGpuTooltip(params, data),
      },
      graphic: data.length === 0 ? [{
        type: 'text',
        left: 'center',
        top: 'middle',
        style: {
          text: 'GPU 데이터 수신 대기 중…',
          fill: palette.textDim,
          fontSize: 12,
          fontFamily: 'Pretendard Variable, sans-serif',
        },
      }] : [],
      series: [
        { name: 'GPU util %', type: 'line', smooth: 0.5, symbol: 'circle', showSymbol: showSymbols, symbolSize: 5, data: data.map((p) => p.util), lineStyle: { color: palette.c3, width: 1.8 } },
        { name: 'VRAM %',     type: 'line', smooth: 0.5, symbol: 'circle', showSymbol: showSymbols, symbolSize: 5, data: data.map((p) => p.vram), lineStyle: { color: palette.c2, width: 1.8 } },
        { name: '온도 °C',    type: 'line', smooth: 0.5, symbol: 'circle', showSymbol: showSymbols, symbolSize: 5, data: data.map((p) => p.temp), lineStyle: { color: palette.c4, width: 1.8 } },
      ],
    };
  });

  // 도넛형 미니 표시기 (Hero 와 유사하나 더 작음)
  function donutDash(pct: number | null | undefined, max: number = 100): string {
    if (pct == null) return '0 264';
    const ratio = Math.max(0, Math.min(1, pct / max));
    return `${ratio * 264} 264`;
  }
</script>

<div class="card">
  <div class="card-header">
    <div>
      <div class="card-eyebrow">W5 · /api/training/gpu</div>
      <div class="card-title">{g?.name ?? 'GPU'} · 실시간 트렌드</div>
    </div>
    <div class="row" style="gap:8px;flex-wrap:wrap">
      <span class="pill">
        <span class="dot" style="background:{g?.power_draw_available ? 'var(--success)' : 'var(--muted)'}"></span>
        전원 {g?.power_draw_available ? '실측 OK' : '실측 불가'}
      </span>
    </div>
  </div>

  <div class="row" style="gap:16px;flex-wrap:wrap">
    <span class="legend"><span class="swatch" style="background:var(--c-3)"></span>GPU util %</span>
    <span class="legend"><span class="swatch" style="background:var(--c-2)"></span>VRAM %</span>
    <span class="legend"><span class="swatch" style="background:var(--c-4)"></span>온도 °C</span>
    <span style="margin-left:auto" class="text-caption">버퍼 {ring.length} / 720 points · 최신 {formatTime(chartRing.at(-1)?.ts)}</span>
  </div>

  <EChartsRenderer {option} height="240px" />

  <div class="grid-3" style="gap:14px;border-top:1px solid var(--border-faint);padding-top:14px;margin-top:8px">
    <div class="stack" style="gap:8px;align-items:center">
      <svg viewBox="0 0 100 100" width="84" height="84" aria-hidden="true">
        <circle cx="50" cy="50" r="42" fill="none" stroke="var(--border-faint)" stroke-width="9" />
        <circle
          cx="50" cy="50" r="42"
          fill="none"
          stroke="var(--c-3)"
          stroke-width="9"
          stroke-linecap="round"
          stroke-dasharray={donutDash(g?.utilization_gpu_percent)}
          transform="rotate(-90 50 50)"
          style="transition:stroke-dasharray 300ms ease"
        />
        <text x="50" y="54" text-anchor="middle" font-family="var(--font-mono)" font-size="18" font-weight="700" fill="var(--fg-strong)">
          {g?.utilization_gpu_percent != null ? Math.round(g.utilization_gpu_percent) + '%' : '—'}
        </text>
      </svg>
      <span class="text-caption">활용률</span>
    </div>
    <div class="stack" style="gap:8px;align-items:center">
      <svg viewBox="0 0 100 100" width="84" height="84" aria-hidden="true">
        <circle cx="50" cy="50" r="42" fill="none" stroke="var(--border-faint)" stroke-width="9" />
        <circle
          cx="50" cy="50" r="42"
          fill="none"
          stroke="var(--c-4)"
          stroke-width="9"
          stroke-linecap="round"
          stroke-dasharray={donutDash(g?.temperature_c, 90)}
          transform="rotate(-90 50 50)"
          style="transition:stroke-dasharray 300ms ease"
        />
        <text x="50" y="54" text-anchor="middle" font-family="var(--font-mono)" font-size="18" font-weight="700" fill="var(--fg-strong)">
          {g?.temperature_c != null ? Math.round(g.temperature_c) + '°' : '—'}
        </text>
      </svg>
      <span class="text-caption">온도</span>
    </div>
    <div class="stack" style="gap:8px;align-items:center">
      <svg viewBox="0 0 100 100" width="84" height="84" aria-hidden="true">
        <circle cx="50" cy="50" r="42" fill="none" stroke="var(--border-faint)" stroke-width="9" />
        <circle
          cx="50" cy="50" r="42"
          fill="none"
          stroke="var(--c-2)"
          stroke-width="9"
          stroke-linecap="round"
          stroke-dasharray={donutDash(g?.memory_used_percent)}
          transform="rotate(-90 50 50)"
          style="transition:stroke-dasharray 300ms ease"
        />
        <text x="50" y="54" text-anchor="middle" font-family="var(--font-mono)" font-size="18" font-weight="700" fill="var(--fg-strong)">
          {g?.memory_used_percent != null ? Math.round(g.memory_used_percent) + '%' : '—'}
        </text>
      </svg>
      <span class="text-caption">VRAM</span>
    </div>
  </div>

  {#if g?.memory_used_mib != null && g?.memory_total_mib != null}
    <div class="text-caption" style="margin-top:8px;text-align:center">
      VRAM 사용 <span class="text-mono" style="color:var(--fg);font-weight:600">{fmt.bytes(g.memory_used_mib)} / {fmt.bytes(g.memory_total_mib)}</span>
      {#if g.power_limit_watts}
        · 전력 한계 <span class="text-mono" style="color:var(--fg);font-weight:600">{g.power_limit_watts.toFixed(0)} W</span>
      {/if}
    </div>
  {/if}
</div>
