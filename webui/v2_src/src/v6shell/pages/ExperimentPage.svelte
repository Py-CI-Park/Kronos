<script lang="ts">
  import { onMount } from 'svelte';
  import { getV6Experiment, type V6Experiment } from '../v6Api';

  const DATASET_COMMAND = 'py -3.11 -m stom_rl.daily_v6_dataset --universe-limit 50 --run-id v6_dataset_smoke_001';
  let experiment = $state<V6Experiment | null>(null);
  let error = $state<string | null>(null);
  let loading = $state(true);
  let copyMessage = $state<string | null>(null);

  function display(value: unknown): string {
    if (value === undefined || value === null || value === '') return 'MISSING';
    return typeof value === 'string' ? value : JSON.stringify(value);
  }

  function won(value: number | undefined): string {
    return typeof value === 'number' ? `₩${new Intl.NumberFormat('ko-KR').format(value)}` : 'MISSING';
  }
  function horizon(value: unknown): string {
    if (Array.isArray(value)) return value.map(horizon).join('/');
    const text = display(value);
    return text === 'MISSING' || text.startsWith('H') ? text : `H${text}`;
  }


  function preregClass(state: string | undefined): string {
    return state === 'FROZEN' ? 'frozen' : 'unfrozen';
  }

  async function load(): Promise<void> {
    loading = true;
    error = null;
    const result = await getV6Experiment();
    loading = false;
    if (result.ok && result.data) experiment = result.data;
    else error = result.error ?? '알 수 없는 오류가 발생했습니다.';
  }

  async function copyCommand(): Promise<void> {
    copyMessage = null;
    try {
      await navigator.clipboard.writeText(DATASET_COMMAND);
      copyMessage = '명령을 클립보드에 복사했습니다.';
    } catch {
      copyMessage = '클립보드를 사용할 수 없습니다. 아래 명령을 직접 복사하세요.';
    }
  }

  onMount(load);
</script>

{#if loading}
  <section class="panel" aria-live="polite"><p>실험 설계를 확인하고 있습니다.</p></section>
{:else if error}
  <section class="panel error" aria-live="assertive">
    <h1>실험 설계를 불러오지 못했습니다</h1><p>{error}</p><button type="button" onclick={load}>다시 시도</button>
  </section>
{:else if experiment}
  <section class="experiment-page" aria-labelledby="experiment-title">
    <header><p class="eyebrow">EXPERIMENT CONTRACT</p><h1 id="experiment-title">실험 설계</h1><p>표시된 설계 계약은 읽기 전용 API 응답에서만 가져옵니다.</p></header>

    <section class={`card prereg ${preregClass(experiment.prereg?.state)}`} aria-labelledby="prereg-title">
      <h2 id="prereg-title">사전등록 상태 <span class="chip">{display(experiment.prereg?.state)}</span></h2>
      {#if experiment.prereg?.state === 'FROZEN'}
        <p class="status-text">동결됨 · 사전등록 SHA-256이 확인되었습니다.</p>
        <p class="path">{display(experiment.prereg?.sha256)}</p>
      {:else}
        <p class="status-text">동결 전 · 연구 결과 주장 불가</p>
        <p class="path">{display(experiment.prereg?.path)}</p>
      {/if}
    </section>

    <section class="card" aria-labelledby="planned-title">
      <h2 id="planned-title">계획된 실험 계약</h2>
      <dl>
        <div><dt>전략</dt><dd>{display(experiment.planned?.strategy)}</dd></div>
        <div><dt>자본</dt><dd>{won(experiment.planned?.capital?.initial_krw)} · {display(experiment.planned?.capital?.slots)}슬롯×{won(experiment.planned?.capital?.slot_budget_krw)} · 예비 {won(experiment.planned?.capital?.reserve_krw)}</dd></div>
        <div><dt>비용</dt><dd>{display(experiment.planned?.costs?.primary)} / {display(experiment.planned?.costs?.zero_control)} / {display(experiment.planned?.costs?.stress)}</dd></div>
        <div><dt>예측 구간</dt><dd>{horizon(experiment.planned?.horizons?.primary)} primary · {horizon(experiment.planned?.horizons?.validation)} validation</dd></div>
        <div><dt>실행 기준</dt><dd>{display(experiment.planned?.execution?.price_basis)} proxy · official_close={display(experiment.planned?.execution?.official_close)}</dd></div>
        <div><dt>seeds</dt><dd>{display(experiment.planned?.seeds)}</dd></div>
        <div><dt>universe</dt><dd>{display(experiment.planned?.universe?.manifest)} · {display(experiment.planned?.universe?.size)}</dd></div>
        <div><dt>데이터셋 계약</dt><dd>{display(experiment.planned?.dataset_contract)}</dd></div>
        <div><dt>제약 조건</dt><dd>{display(experiment.planned?.constraints)}</dd></div>
      </dl>
    </section>

    <section class="card boundary" aria-labelledby="boundary-title">
      <h2 id="boundary-title">실행 경계</h2>
      <p>이 화면은 설계 열람용입니다. 학습 실행은 승인된 CLI로만 수행됩니다</p>
      <div class="command"><code>{DATASET_COMMAND}</code><button type="button" onclick={copyCommand}>명령 복사</button></div>
      {#if copyMessage}<p class="copy-message" aria-live="polite">{copyMessage}</p>{/if}
    </section>
  </section>
{/if}

<style>
  .experiment-page, .panel { max-width: 980px; border: 1px solid var(--surface-border, #334155); border-radius: 14px; padding: clamp(18px, 4vw, 32px); background: var(--surface, #111827); color: #e5e7eb; }
  .eyebrow { margin: 0; color: #7dd3fc; font-size: .72rem; font-weight: 800; letter-spacing: .1em; } h1 { margin: 7px 0; color: #f8fafc; font-size: clamp(1.7rem, 6vw, 2.5rem); } header > p { color: #cbd5e1; }
  .card { margin-top: 16px; border: 1px solid #475569; border-radius: 10px; padding: 16px; background: #0f172a; } h2 { margin: 0 0 12px; color: #f8fafc; font-size: 1.05rem; } .chip { display: inline-block; margin-left: 5px; border: 1px solid #a16207; border-radius: 999px; padding: 2px 6px; color: #fde68a; font-size: .68rem; vertical-align: middle; } .frozen { border-color: #15803d; background: #102016; } .frozen .chip { border-color: #15803d; color: #bbf7d0; } .unfrozen { border-color: #a16207; background: #1c1910; } .status-text { font-weight: 700; } .path, dd, code { overflow-wrap: anywhere; }
  dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 0; } dl div { min-width: 0; } dt { color: #94a3b8; font-size: .74rem; } dd { margin: 3px 0 0; color: #e2e8f0; font-size: .86rem; line-height: 1.45; }
  .boundary { border-color: #0369a1; } .command { display: flex; align-items: start; gap: 10px; } code { flex: 1; min-width: 0; border: 1px solid #334155; border-radius: 6px; padding: 9px; color: #bae6fd; font-size: .75rem; line-height: 1.5; } button { flex: 0 0 auto; border: 1px solid #7dd3fc; border-radius: 6px; padding: 6px 10px; background: transparent; color: #e0f2fe; font: inherit; cursor: pointer; } .copy-message { color: #bae6fd; font-size: .82rem; } .error { border-color: #b91c1c; color: #fecaca; }
  @media (max-width: 600px) { dl { grid-template-columns: 1fr; } .command { flex-direction: column; } }
</style>
