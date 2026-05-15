<script lang="ts">
  import W7StatusBadge from '$widgets/W7_StatusBadge.svelte';
  import W1StageStepper from '$widgets/W1_StageStepper.svelte';
  import W2ReadinessCountdown from '$widgets/W2_ReadinessCountdown.svelte';
</script>

<section id="hero-strip" data-tab="live-training"
  class="rounded-lg border border-border p-4 mb-4 flex flex-wrap gap-4 items-stretch"
  style="background: linear-gradient(135deg, #0f172a 60%, #0c2045);">
  <div class="flex-1 min-w-[260px]">
    <W7StatusBadge />
  </div>
  <div class="flex-[2] min-w-[280px]">
    <W1StageStepper />
  </div>
  <div class="flex-none min-w-[220px]">
    <W2ReadinessCountdown />
  </div>
</section>
