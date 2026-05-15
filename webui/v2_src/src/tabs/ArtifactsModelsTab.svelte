<script lang="ts">
  import { artifacts } from '$lib/stores';

  let a = $state<any>(null);
  artifacts.subscribe((v) => (a = v));

  let loaded = $derived(a != null);
  let ckCount = $derived(a?.checkpoint_file_count ?? 0);
  let mwCount = $derived(a?.model_weight_file_count ?? 0);
  let ckReady = $derived(!!a?.checkpoint_ready);
  let pStarted = $derived(!!a?.predictor_started);
  let pComplete = $derived(!!a?.stages?.predictor?.checkpoint_ready);
  let recentCk = $derived<any[]>(Array.isArray(a?.recent_checkpoint_files) ? a.recent_checkpoint_files.slice(0, 5) : []);
  let recentMw = $derived<any[]>(Array.isArray(a?.recent_model_weight_files) ? a.recent_model_weight_files.slice(0, 5) : []);

  function fileName(f: any): string {
    return typeof f === 'string' ? f : (f?.path ?? f?.name ?? '-');
  }
</script>

<div class="bg-card border border-border rounded-lg p-4 mb-4">
  <h2 class="text-accent-subtle text-[15px] font-semibold m-0 mb-3">아티팩트 & 모델</h2>
  {#if !loaded}
    <div class="text-text-dim text-[12px]">아티팩트 상태를 불러오는 중...</div>
  {:else}
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
      <div class="bg-card-raised border border-border rounded-md p-3">
        <div class="text-[11px] uppercase tracking-wide text-text-dim font-semibold">Checkpoint</div>
        <div class="text-2xl font-extrabold text-text mt-1 font-mono">{ckCount}개</div>
        <div class="text-[11px] text-text-dim mt-1">{ckReady ? '✅ 사용 가능' : '⏳ 생성 대기'}</div>
      </div>
      <div class="bg-card-raised border border-border rounded-md p-3">
        <div class="text-[11px] uppercase tracking-wide text-text-dim font-semibold">Model Weight</div>
        <div class="text-2xl font-extrabold text-text mt-1 font-mono">{mwCount}개</div>
        <div class="text-[11px] text-text-dim mt-1">
          {pComplete ? '✅ 예측기 완료' : pStarted ? '🔄 예측기 학습 중' : '⏸ 예측기 미시작'}
        </div>
      </div>
    </div>
    <p class="text-text-muted text-[12px] m-0 mb-2">{a?.message ?? '-'}</p>
    {#if recentCk.length > 0}
      <h3 class="text-info text-[13px] font-semibold m-0 mb-1">최근 checkpoint 파일</h3>
      <ul class="text-text text-[12px] leading-relaxed pl-5 mb-2">
        {#each recentCk as f}
          <li>{fileName(f)}</li>
        {/each}
      </ul>
    {/if}
    {#if recentMw.length > 0}
      <h3 class="text-info text-[13px] font-semibold m-0 mb-1">최근 model weight 파일</h3>
      <ul class="text-text text-[12px] leading-relaxed pl-5 mb-2">
        {#each recentMw as f}
          <li>{fileName(f)}</li>
        {/each}
      </ul>
    {/if}
    {#if recentCk.length === 0 && recentMw.length === 0}
      <div class="text-text-dim text-[11px] mt-2">아직 생성된 파일이 없습니다. tokenizer/predictor 진행 시 자동으로 표시됩니다.</div>
    {/if}
  {/if}
</div>
