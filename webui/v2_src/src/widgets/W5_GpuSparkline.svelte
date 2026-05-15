<script lang="ts">
  import EChartsRenderer from '../charts/EChartsRenderer.svelte';
  import { gpuRing, gpuStatus } from '$lib/stores';
  import { theme } from '$lib/theme';

  let ring = $state<any[]>([]);
  gpuRing.subscribe((v) => (ring = v));

  let gpu = $state<any>(null);
  gpuStatus.subscribe((v) => (gpu = v));

  let g = $derived(gpu?.gpus?.[0]);

  function sparkOption(values: (number | null)[], color: string) {
    return {
      backgroundColor: 'transparent',
      grid: { left: 0, right: 0, top: 4, bottom: 4 },
      xAxis: { type: 'category', show: false, data: values.map((_, i) => i) },
      yAxis: { type: 'value', show: false, scale: true },
      series: [
        {
          type: 'line',
          data: values,
          smooth: true,
          symbol: 'none',
          lineStyle: { color, width: 1.5 },
          areaStyle: { color, opacity: 0.18 },
        },
      ],
    };
  }

  let utilOpt = $derived(sparkOption(ring.map((p) => p.util), theme.colors.accent));
  let tempOpt = $derived(sparkOption(ring.map((p) => p.temp), theme.colors.warn));
  let vramOpt = $derived(sparkOption(ring.map((p) => p.vram), theme.colors.success));
</script>

<div class="bg-card border border-border rounded-lg p-4 mb-4">
  <h2 class="text-accent-subtle text-[15px] font-semibold m-0 mb-3">GPU 트렌드 (W5)</h2>
  <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
    <div class="bg-card-raised border border-border rounded-md p-3">
      <div class="text-[11px] text-text-dim uppercase tracking-wide font-semibold mb-1 whitespace-nowrap">GPU 사용률</div>
      <div class="text-base font-bold text-text font-mono">{g?.utilization_gpu_percent != null ? g.utilization_gpu_percent.toFixed(1) + '%' : '-'}</div>
      <div class="mt-2">
        <EChartsRenderer option={utilOpt} height="50px" />
      </div>
    </div>
    <div class="bg-card-raised border border-border rounded-md p-3">
      <div class="text-[11px] text-text-dim uppercase tracking-wide font-semibold mb-1 whitespace-nowrap">GPU 온도</div>
      <div class="text-base font-bold text-text font-mono">{g?.temperature_c != null ? g.temperature_c.toFixed(1) + '°C' : '-'}</div>
      <div class="mt-2">
        <EChartsRenderer option={tempOpt} height="50px" />
      </div>
    </div>
    <div class="bg-card-raised border border-border rounded-md p-3">
      <div class="text-[11px] text-text-dim uppercase tracking-wide font-semibold mb-1 whitespace-nowrap">VRAM 사용률</div>
      <div class="text-base font-bold text-text font-mono">{g?.memory_used_percent != null ? g.memory_used_percent.toFixed(1) + '%' : '-'}</div>
      <div class="mt-2">
        <EChartsRenderer option={vramOpt} height="50px" />
      </div>
    </div>
  </div>
  <div class="text-text-dim text-[11px] mt-2">버퍼: {ring.length} / 720 points</div>
</div>
