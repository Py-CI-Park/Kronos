<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import * as echarts from 'echarts';

  interface Props {
    option: any;
    height?: string;
    className?: string;
  }

  let { option, height = '320px', className = '' }: Props = $props();

  let container: HTMLDivElement | undefined = $state();
  let chart: echarts.ECharts | null = null;
  let observer: ResizeObserver | null = null;

  function onThemeChange(_e: Event) {
    // 옵션 자체는 CSS 변수를 참조하지 않고 그대로 들어오므로
    // 부모가 option 을 재계산해서 reactive 로 흘려보내면 자동 갱신됨.
    // 여기서는 resize 만 트리거.
    chart?.resize();
  }

  onMount(() => {
    if (!container) return;
    chart = echarts.init(container, null, { renderer: 'canvas' });
    chart.setOption(option);
    observer = new ResizeObserver(() => chart?.resize());
    observer.observe(container);
    document.addEventListener('kronos:theme', onThemeChange);
  });

  onDestroy(() => {
    observer?.disconnect();
    chart?.dispose();
    document.removeEventListener('kronos:theme', onThemeChange);
  });

  $effect(() => {
    if (chart && option) chart.setOption(option, true);
  });
</script>

<div bind:this={container} class={className} style="width: 100%; height: {height};"></div>
