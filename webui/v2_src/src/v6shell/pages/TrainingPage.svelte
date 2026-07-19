<script lang="ts">
  import { onMount } from 'svelte';
  import { getV6Runs, type V6Runs } from '../v6Api';

  let runsData = $state<V6Runs | null>(null);
  let error = $state<string | null>(null);
  let loading = $state(true);

  function display(value: unknown): string {
    if (value === undefined || value === null || value === '') return 'MISSING';
    return typeof value === 'string' ? value : JSON.stringify(value);
  }

  function shortSha(value: string | undefined): string {
    return value ? value.slice(0, 12) : 'MISSING';
  }

  function stateClass(state: string | undefined): string {
    if (state === 'COMPLETED' || state === 'READY') return 'complete';
    if (state === 'RUNNING' || state === 'PARTIAL') return 'running';
    return 'waiting';
  }

  async function load(): Promise<void> {
    loading = true;
    error = null;
    const result = await getV6Runs();
    loading = false;
    if (result.ok && result.data) runsData = result.data;
    else error = result.error ?? '알 수 없는 오류가 발생했습니다.';
  }

  onMount(load);
</script>

{#if loading}
  <section class="panel" aria-live="polite"><p>학습 실행 기록을 확인하고 있습니다.</p></section>
{:else if error}
  <section class="panel error" aria-live="assertive">
    <h1>학습 실행 기록을 불러오지 못했습니다</h1><p>{error}</p><button type="button" onclick={load}>다시 시도</button>
  </section>
{:else if runsData}
  <section class="training-page" aria-labelledby="training-title">
    <header><p class="eyebrow">TRAINING LIFECYCLE</p><h1 id="training-title">학습</h1><p>실행 기록은 읽기 전용 API 응답에서만 표시합니다.</p></header>

    {#if runsData.training_state === 'NOT_RUN'}
      <section class="empty-state" aria-labelledby="empty-title">
        <h2 id="empty-title">아직 어떤 V6 학습도 실행되지 않았습니다</h2>
        <p>승인된 CLI로 학습이 실행되면 다음 증거가 이 화면에 나타납니다.</p>
        <ul><li>run UID와 seed</li><li>episode 및 checkpoint</li><li>reward/loss</li><li>replay</li></ul>
      </section>
    {/if}

    <section class="card" aria-labelledby="datasets-title">
      <h2 id="datasets-title">데이터셋 실행 <span class="chip">{runsData.datasets?.length ?? 0}</span></h2>
      {#if runsData.datasets?.length}
        <div class="table-wrap"><table><thead><tr><th>run_id</th><th>generated_utc</th><th>split_row_counts</th><th>sha256</th></tr></thead><tbody>{#each runsData.datasets as dataset}<tr><td title={dataset.path}>{display(dataset.run_id)}</td><td>{display(dataset.generated_utc)}</td><td>{display(dataset.split_row_counts)}</td><td title={dataset.sha256}>{shortSha(dataset.sha256)}</td></tr>{/each}</tbody></table></div>
      {:else}
        <p class="absence">표시할 데이터셋 실행 기록이 없습니다.</p>
      {/if}
    </section>

    <section class="card" aria-labelledby="runs-title">
      <h2 id="runs-title">학습 실행 <span class={`chip ${stateClass(runsData.training_state)}`}>{display(runsData.training_state)}</span></h2>
      {#if runsData.runs?.length}
        <div class="table-wrap"><table><thead><tr><th>run_id</th><th>state</th><th>seeds</th><th>generated_utc</th></tr></thead><tbody>{#each runsData.runs as run}<tr><td title={run.path}>{display(run.run_id)}</td><td><span class={`chip ${stateClass(run.state)}`}>{display(run.state)}</span></td><td>{display(run.seeds)}</td><td>{display(run.generated_utc)}</td></tr>{/each}</tbody></table></div>
      {:else}
        <p class="absence">표시할 학습 실행 기록이 없습니다.</p>
      {/if}
    </section>
  </section>
{/if}

<style>
  .training-page, .panel { max-width: 980px; border: 1px solid var(--surface-border, #334155); border-radius: 14px; padding: clamp(18px, 4vw, 32px); background: var(--surface, #111827); color: #e5e7eb; }
  .eyebrow { margin: 0; color: #7dd3fc; font-size: .72rem; font-weight: 800; letter-spacing: .1em; } h1 { margin: 7px 0; color: #f8fafc; font-size: clamp(1.7rem, 6vw, 2.5rem); } header > p { color: #cbd5e1; }
  .card, .empty-state { margin-top: 16px; border: 1px solid #475569; border-radius: 10px; padding: 16px; background: #0f172a; } .empty-state { border-color: #a16207; background: #1c1910; } h2 { margin: 0 0 12px; color: #f8fafc; font-size: 1.05rem; } .empty-state h2 { font-size: clamp(1.2rem, 4vw, 1.5rem); } .empty-state li { margin: 5px 0; color: #fde68a; }
  .chip { display: inline-block; margin-left: 5px; border: 1px solid #a16207; border-radius: 999px; padding: 2px 6px; color: #fde68a; font-size: .68rem; vertical-align: middle; white-space: nowrap; } .complete { border-color: #15803d; color: #bbf7d0; } .running { border-color: #0369a1; color: #bae6fd; }
  .absence { color: #94a3b8; } .table-wrap { max-width: 100%; overflow-x: auto; } table { width: 100%; min-width: 620px; border-collapse: collapse; font-size: .78rem; } th, td { border-top: 1px solid #334155; padding: 7px; overflow-wrap: anywhere; text-align: left; } th { color: #94a3b8; } .error { border-color: #b91c1c; color: #fecaca; } button { border: 1px solid #7dd3fc; border-radius: 6px; padding: 6px 10px; background: transparent; color: #e0f2fe; font: inherit; cursor: pointer; }
</style>
