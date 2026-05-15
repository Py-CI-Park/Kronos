<script lang="ts">
  import { trainingStatus } from '$lib/stores';
  import { finishKst, nowKst, toKst } from '$lib/kstFormat';

  let status = $state<any>(null);
  trainingStatus.subscribe((v) => (status = v));

  let latest = $derived(status?.latest_stage ?? {});
  let etaSeconds = $derived(latest?.eta_seconds ?? null);
  let updatedAt = $derived(latest?.updated_at ?? null);
  let startKst = $derived(updatedAt ? toKst(updatedAt) : '-');
  let now = $state(nowKst());
  let etaKst = $derived(finishKst(etaSeconds, updatedAt));
  let progress = $derived(latest?.overall_percent ?? 0);

  let nowTimer: number | undefined;
  $effect(() => {
    nowTimer = window.setInterval(() => (now = nowKst()), 1000);
    return () => clearInterval(nowTimer);
  });
</script>

<div class="bg-card border border-border rounded-lg p-4 mb-4">
  <h2 class="text-accent-subtle text-[15px] font-semibold m-0 mb-3">ETA 타임라인 (W4)</h2>
  <div class="flex flex-col gap-3">
    <div class="flex items-start gap-3">
      <div class="w-8 h-8 rounded-full bg-card-raised border border-border flex items-center justify-center">🚀</div>
      <div>
        <div class="text-text-dim text-[11px]">학습 시작</div>
        <div class="text-text font-bold text-[13px] font-mono">{startKst}</div>
      </div>
    </div>
    <div class="w-[2px] h-[20px] bg-border-muted ml-4"></div>
    <div class="flex items-start gap-3">
      <div class="w-8 h-8 rounded-full bg-card-raised border border-border flex items-center justify-center">⏱</div>
      <div>
        <div class="text-text-dim text-[11px]">현재 (KST)</div>
        <div class="text-text font-bold text-[13px] font-mono">{now}</div>
      </div>
    </div>
    <div class="w-[2px] h-[20px] bg-border-muted ml-4"></div>
    <div class="flex items-start gap-3">
      <div class="w-8 h-8 rounded-full bg-card-raised border border-success flex items-center justify-center">🏁</div>
      <div>
        <div class="text-text-dim text-[11px]">완료 예상 (KST)</div>
        <div class="text-text font-bold text-[13px] font-mono">{etaKst}</div>
      </div>
    </div>
    <div class="mt-2">
      <div class="text-text-dim text-[11px]">진행률</div>
      <div class="w-full h-2 rounded-full bg-card-raised overflow-hidden border border-border mt-1">
        <div class="h-full" style="width: {progress}%; background: linear-gradient(90deg, #22c55e, #38bdf8); transition: width .4s ease;"></div>
      </div>
      <div class="text-text-muted text-[12px] mt-1">{progress.toFixed(1)}%</div>
    </div>
  </div>
</div>
