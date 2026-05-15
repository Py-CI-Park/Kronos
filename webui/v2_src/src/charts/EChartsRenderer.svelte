<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import * as echarts from 'echarts';

  interface Props {
    option: any;
    height?: string;
  }

  let { option, height = '320px' }: Props = $props();

  let container: HTMLDivElement | undefined = $state();
  let chart: echarts.ECharts | null = null;
  let observer: ResizeObserver | null = null;

  onMount(() => {
    if (!container) return;
    chart = echarts.init(container, null, { renderer: 'canvas' });
    chart.setOption(option);
    observer = new ResizeObserver(() => chart?.resize());
    observer.observe(container);
  });

  onDestroy(() => {
    observer?.disconnect();
    chart?.dispose();
  });

  $effect(() => {
    if (chart && option) chart.setOption(option, true);
  });
</script>

<div bind:this={container} style="width: 100%; height: {height};"></div>
