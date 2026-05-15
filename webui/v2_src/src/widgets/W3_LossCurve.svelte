<script lang="ts">
  import EChartsRenderer from '../charts/EChartsRenderer.svelte';
  import { lossPoints } from '$lib/stores';
  import { theme, getEChartsBase } from '$lib/theme';

  let pts = $state<{ step: number; loss: number }[]>([]);
  lossPoints.subscribe((v) => (pts = v));

  let option = $derived.by(() => {
    const base = getEChartsBase();
    const steps = pts.map((p) => p.step);
    const losses = pts.map((p) => p.loss);
    return {
      ...base,
      grid: { left: 56, right: 24, top: 24, bottom: 60 },
      xAxis: {
        type: 'value',
        name: 'Step',
        nameTextStyle: { color: theme.colors.textDim, fontSize: 11 },
        axisLabel: { color: theme.colors.textDim, fontSize: 10 },
        splitLine: { lineStyle: { color: theme.colors.borderMuted } },
        axisLine: { lineStyle: { color: theme.colors.border } },
        scale: true,
        min: 'dataMin',
        max: 'dataMax',
      },
      yAxis: {
        type: 'value',
        name: 'Loss',
        nameTextStyle: { color: theme.colors.textDim, fontSize: 11 },
        axisLabel: { color: theme.colors.textDim, fontSize: 10 },
        splitLine: { lineStyle: { color: theme.colors.borderMuted } },
        axisLine: { lineStyle: { color: theme.colors.border } },
        scale: true,
      },
      dataZoom: [
        { type: 'inside', xAxisIndex: 0, throttle: 50 },
        {
          type: 'slider',
          xAxisIndex: 0,
          height: 18,
          bottom: 6,
          backgroundColor: 'rgba(11,17,32,.5)',
          borderColor: theme.colors.border,
          fillerColor: 'rgba(56,189,248,.18)',
          handleStyle: { color: theme.colors.accent, borderColor: theme.colors.accent },
          textStyle: { color: theme.colors.textDim, fontSize: 9 },
        },
      ],
      tooltip: { ...base.tooltip, trigger: 'axis' },
      series: [
        {
          type: 'line',
          data: steps.map((s, i) => [s, losses[i]]),
          smooth: true,
          symbol: 'none',
          lineStyle: { color: theme.colors.accent, width: 2 },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(56,189,248,.25)' },
                { offset: 1, color: 'rgba(56,189,248,0)' },
              ],
            },
          },
        },
      ],
    };
  });
</script>

<div class="bg-card border border-border rounded-lg p-4 mb-4">
  <h2 class="text-accent-subtle text-[15px] font-semibold m-0 mb-3">학습 손실 곡선 (W3)</h2>
  <EChartsRenderer {option} height="320px" />
  <div class="text-text-dim text-[12px] mt-1">표시 포인트: {pts.length} / 최대 1,000</div>
</div>
