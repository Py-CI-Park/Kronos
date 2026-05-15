<script lang="ts">
  import W3LossCurve from '$widgets/W3_LossCurve.svelte';
  import W4EtaTimeline from '$widgets/W4_EtaTimeline.svelte';
  import W5GpuSparkline from '$widgets/W5_GpuSparkline.svelte';
  import { metricsLatest, lossPoints } from '$lib/stores';

  let m = $state<any>({ loss: null, samplesPerSec: null, learningRate: null, epoch: null, epochs: null, runName: null });
  metricsLatest.subscribe((v) => (m = v));

  let lossCount = $state(0);
  lossPoints.subscribe((v) => (lossCount = v.length));
</script>

<!-- P0 메트릭 스트립 -->
<div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
  <div class="bg-card-raised border border-border rounded-lg p-3 flex flex-col gap-1">
    <div class="text-[10px] uppercase tracking-wide text-text-dim font-semibold">현재 손실</div>
    <div class="text-2xl font-extrabold text-accent font-mono leading-tight">{m.loss != null ? m.loss.toFixed(4) : '-'}</div>
    <div class="text-[11px] text-text-dim">{lossCount} 포인트 누적</div>
  </div>
  <div class="bg-card-raised border border-border rounded-lg p-3 flex flex-col gap-1">
    <div class="text-[10px] uppercase tracking-wide text-text-dim font-semibold">학습 속도</div>
    <div class="text-2xl font-extrabold text-success font-mono leading-tight">
      {m.samplesPerSec != null ? m.samplesPerSec.toFixed(1) : '-'}<span class="text-[11px] text-text-muted ml-1">samples/s</span>
    </div>
    <div class="text-[11px] text-text-dim">{m.samplesPerSec != null ? `~ ${(m.samplesPerSec * 60 / 4).toFixed(0)} step/분 (batch=4)` : '-'}</div>
  </div>
  <div class="bg-card-raised border border-border rounded-lg p-3 flex flex-col gap-1">
    <div class="text-[10px] uppercase tracking-wide text-text-dim font-semibold">학습률 (LR)</div>
    <div class="text-2xl font-extrabold text-warn font-mono leading-tight">{m.learningRate != null ? m.learningRate.toExponential(2) : '-'}</div>
    <div class="text-[11px] text-text-dim">{m.learningRate != null ? '소수: ' + m.learningRate.toFixed(6) : '-'}</div>
  </div>
  <div class="bg-card-raised border border-border rounded-lg p-3 flex flex-col gap-1">
    <div class="text-[10px] uppercase tracking-wide text-text-dim font-semibold">현재 Epoch</div>
    <div class="text-2xl font-extrabold text-[#c084fc] font-mono leading-tight">
      {m.epoch != null ? m.epoch : '-'}{m.epochs != null ? ` / ${m.epochs}` : ''}
    </div>
    <div class="text-[11px] text-text-dim truncate" title={m.runName ?? ''}>{m.runName ? 'run: ' + m.runName : '-'}</div>
  </div>
</div>

<div class="grid grid-cols-1 lg:grid-cols-[60%_40%] gap-4">
  <W3LossCurve />
  <W4EtaTimeline />
</div>
<W5GpuSparkline />
