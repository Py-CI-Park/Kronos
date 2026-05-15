<script lang="ts">
  import { gpuStatus, refreshSeconds, gpuRing, lastUpdatedAt } from '$lib/stores';
  import { toKst } from '$lib/kstFormat';

  let gpu = $state<any>(null);
  gpuStatus.subscribe((v) => (gpu = v));

  let g = $derived(gpu?.gpus?.[0]);
  let sec = $state(5);
  refreshSeconds.subscribe((v) => (sec = v));
  let ringLen = $state(0);
  gpuRing.subscribe((v) => (ringLen = v.length));
  let last = $state('-');
  lastUpdatedAt.subscribe((v) => (last = v));
</script>

{#if g == null}
  <div class="bg-card border border-border rounded-lg p-4">
    <div class="text-text-dim text-[12px]">GPU 데이터 불러오는 중...</div>
  </div>
{:else}
  <div class="bg-card border border-border rounded-lg p-4 mb-4">
    <h2 class="text-accent-subtle text-[15px] font-semibold m-0 mb-3">GPU 디바이스</h2>
    <table class="w-full border-collapse text-[13px]">
      <tbody>
        <tr class="border-b border-border-muted"><td class="py-2 text-text-dim w-2/5">모델명</td><td class="py-2 text-right text-text font-bold">{g.name ?? '-'}</td></tr>
        <tr class="border-b border-border-muted"><td class="py-2 text-text-dim">디바이스 수</td><td class="py-2 text-right text-text font-bold">{(gpu.gpus?.length ?? 1) + '개'}</td></tr>
        <tr><td class="py-2 text-text-dim">마지막 갱신 (KST)</td><td class="py-2 text-right text-text font-bold font-mono">{gpu?.generated_at ? toKst(gpu.generated_at) : '-'}</td></tr>
      </tbody>
    </table>
  </div>

  <div class="bg-card border border-border rounded-lg p-4 mb-4">
    <h2 class="text-accent-subtle text-[15px] font-semibold m-0 mb-3">실시간 사용률</h2>
    <table class="w-full border-collapse text-[13px]">
      <tbody>
        <tr class="border-b border-border-muted"><td class="py-2 text-text-dim w-2/5">GPU 사용률</td><td class="py-2 text-right text-text font-bold font-mono">{g.utilization_gpu_percent != null ? g.utilization_gpu_percent.toFixed(1) + '%' : '-'}</td></tr>
        <tr class="border-b border-border-muted"><td class="py-2 text-text-dim">온도</td><td class="py-2 text-right text-text font-bold font-mono">{g.temperature_c != null ? g.temperature_c.toFixed(1) + '°C' : '-'}</td></tr>
        <tr class="border-b border-border-muted"><td class="py-2 text-text-dim">VRAM 사용률</td><td class="py-2 text-right text-text font-bold font-mono">{g.memory_used_percent != null ? g.memory_used_percent.toFixed(1) + '%' : '-'}</td></tr>
        <tr><td class="py-2 text-text-dim">VRAM 사용 / 전체</td><td class="py-2 text-right text-text font-bold font-mono">{(g.memory_used_mib != null && g.memory_total_mib != null) ? g.memory_used_mib.toFixed(0) + ' / ' + g.memory_total_mib.toFixed(0) + ' MiB' : '-'}</td></tr>
      </tbody>
    </table>
  </div>

  <div class="bg-card border border-border rounded-lg p-4 mb-4">
    <h2 class="text-accent-subtle text-[15px] font-semibold m-0 mb-3">전력</h2>
    <table class="w-full border-collapse text-[13px]">
      <tbody>
        <tr class="border-b border-border-muted"><td class="py-2 text-text-dim w-2/5">전력 한계</td><td class="py-2 text-right text-text font-bold font-mono">{g.power_limit_watts != null ? g.power_limit_watts.toFixed(0) + ' W' : '-'}</td></tr>
        <tr><td class="py-2 text-text-dim">실측 전력 사용</td><td class="py-2 text-right text-text font-bold font-mono">{g.power_draw_available && g.power_draw_watts != null ? g.power_draw_watts.toFixed(0) + ' W' : '실측 불가'}</td></tr>
      </tbody>
    </table>
    {#if !g.power_draw_available}
      <div class="text-text-dim text-[11px] mt-2">현재 환경에서 nvidia-smi 가 전력 실측값을 보고하지 않습니다. 추정값은 표시하지 않습니다.</div>
    {/if}
  </div>

  <div class="bg-card border border-border rounded-lg p-4 mb-4">
    <h2 class="text-accent-subtle text-[15px] font-semibold m-0 mb-3">대시보드 폴링</h2>
    <table class="w-full border-collapse text-[13px]">
      <tbody>
        <tr class="border-b border-border-muted"><td class="py-2 text-text-dim w-2/5">폴링 간격</td><td class="py-2 text-right text-text font-bold font-mono">{sec} 초</td></tr>
        <tr class="border-b border-border-muted"><td class="py-2 text-text-dim">GPU ring buffer</td><td class="py-2 text-right text-text font-bold font-mono">{ringLen} / 720 points</td></tr>
        <tr><td class="py-2 text-text-dim">마지막 화면 갱신</td><td class="py-2 text-right text-text font-bold font-mono">{last}</td></tr>
      </tbody>
    </table>
  </div>
{/if}
