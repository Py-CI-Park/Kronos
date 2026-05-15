<script lang="ts">
  import { refreshSeconds } from '$lib/stores';

  const opts = [2, 5, 10, 30, 60];
  let sec = $state(5);
  refreshSeconds.subscribe((v) => (sec = v));

  function setSec(v: number) {
    refreshSeconds.set(v);
  }
</script>

<div class="bg-card border border-border rounded-lg p-4 mb-4">
  <h2 class="text-accent-subtle text-[15px] font-semibold m-0 mb-3">새로고침 간격</h2>
  <div class="flex flex-wrap gap-2">
    {#each opts as v}
      <button
        type="button"
        class="px-3 py-2 rounded-md border text-[13px] font-semibold transition-colors duration-base
          {sec === v ? 'border-accent text-accent bg-accent/[.12]' : 'border-border text-text-muted hover:text-text hover:border-accent'}"
        onclick={() => setSec(v)}
      >
        {v} 초
      </button>
    {/each}
  </div>
  <p class="text-text-dim text-[12px] mt-3">학습 status, history, GPU 폴링 주기. artifacts 는 항상 30초 고정.</p>
</div>
