<script lang="ts">
  import { onMount } from 'svelte';
  import { getV6Status, type V6Status } from '../v6Api';

  const INDEX_COMMAND = 'py -3.11 scripts/collect_korean_index_artifact.py --market KOSPI --start-date 2018-01-01 --end-date 2026-06-12 --output-dir artifacts/korean_index';
  const TRAIN_COMMAND = 'py -3.11 -m stom_rl.daily_v6_train --dataset v6_dataset_full_001 --seeds 0,1,2';
  const STEPS = [
    ['overview', 'Overview', '개요', (status: V6Status) => status.status],
    ['data', 'Data', '데이터', (status: V6Status) => status.journey.data.state],
    ['experiment', 'Experiment', '실험 설계', (status: V6Status) => status.journey.experiment.state],
    ['training', 'Training', '학습', (status: V6Status) => status.journey.training.state],
    ['evaluation', 'Evaluation', '평가', (status: V6Status) => status.journey.evaluation.state],
    ['compare', 'Compare', '비교', (_status: V6Status) => undefined],
    ['report', 'Report', '보고서', (status: V6Status) => status.journey.report.state],
  ] as const;

  let status = $state<V6Status | null>(null);
  let error = $state<string | null>(null);
  let loading = $state(true);
  let copyMessage = $state<string | null>(null);

  function stateLabel(state: string | undefined): string { return state ?? 'MISSING'; }
  function stateClass(state: string | undefined): string {
    if (state === 'PARTIAL' || state === 'FROZEN' || state === 'HAS_RUNS') return 'partial';
    if (state === 'NOT_FROZEN' || state === 'NOT_RUN') return 'waiting';
    return 'blocked';
  }
  function navigate(id: string): void { history.pushState(history.state, '', `?ui=v6&tab=${encodeURIComponent(id)}`); window.dispatchEvent(new PopStateEvent('popstate')); }
  function nextAction(): { title: string; text: string; command?: string; tab?: string } {
    if (!status) return { title: '상태 확인', text: '상태를 읽을 수 없습니다.' };
    if (status.journey.experiment.state !== 'FROZEN') return { title: 'R-2 사전등록 동결', text: '사전등록이 동결되기 전에는 연구 결과를 주장하지 않습니다.', tab: 'experiment' };
    if (status.journey.training.state === 'NOT_RUN') return { title: '전체 학습 실행', text: '데이터셋이 존재하는지 확인한 뒤 승인된 전체 학습 명령을 복사해 실행하세요.', command: TRAIN_COMMAND, tab: 'training' };
    if (status.journey.training.state === 'HAS_RUNS') return { title: '평가 확인으로 이동', text: '학습 실행이 있으므로 manifest 기반 평가를 확인하세요.', tab: 'evaluation' };
    return { title: '현재 상태 확인', text: 'API가 보고한 다음 상태를 확인하세요.' };
  }
  async function copy(command: string): Promise<void> { try { await navigator.clipboard.writeText(command); copyMessage = '명령을 클립보드에 복사했습니다.'; } catch { copyMessage = '클립보드를 사용할 수 없습니다. 명령을 직접 복사하세요.'; } }
  let action = $derived(nextAction());
  async function load(): Promise<void> { loading = true; error = null; const result = await getV6Status(); loading = false; if (result.ok && result.data) status = result.data; else error = result.error ?? '알 수 없는 오류가 발생했습니다.'; }
  onMount(load);
</script>

{#if loading}
  <section class="panel" aria-live="polite"><p>현재 연구 상태를 확인하고 있습니다.</p></section>
{:else if error}
  <section class="panel error" aria-live="assertive"><h1>상태를 불러오지 못했습니다</h1><p>{error}</p><button type="button" onclick={load}>다시 시도</button></section>
{:else if status}
  <section class="overview" aria-labelledby="overview-title">
    <header><p class="eyebrow">RL JOURNEY HOME</p><h1 id="overview-title">강화학습 연구 여정</h1><p>각 단계는 API가 보고한 상태 토큰을 그대로 표시합니다.</p></header>
    <ol class="journey" aria-label="7단계 연구 여정">
      {#each STEPS as [id, label, labelKo, getState], index}
        {@const rawState = getState(status)}
        <li><button type="button" onclick={() => navigate(id)}><span class="number">{index + 1}</span><span><strong>{labelKo}</strong><small>{label}</small></span><span class={`chip ${stateClass(rawState)}`}>{stateLabel(rawState)}</span></button></li>
      {/each}
    </ol>
    {#if status.journey.data.index_overlay === 'BLOCKED_INDEX_SERIES_SOURCE'}
      <section class="blocker" aria-labelledby="blocker-title"><p class="eyebrow">PRIMARY BLOCKER</p><h2 id="blocker-title">KOSPI/KOSDAQ 지수 수집이 KRX 자격증명(KRX_ID/KRX_PW)을 요구합니다</h2><p>{status.journey.data.index_blocker_reason ?? 'BLOCKED_INDEX_SERIES_SOURCE'}</p><p class="action-label">다음 실행 명령</p><code>{INDEX_COMMAND}</code></section>
    {/if}
    <section class="next-action" aria-labelledby="next-action-title"><p class="eyebrow">NEXT ACTION</p><h2 id="next-action-title">{action.title}</h2><p>{action.text}</p>{#if action.command}<div class="command"><code>{action.command}</code><button type="button" onclick={() => copy(action.command!)}>명령 복사</button></div>{/if}{#if action.tab}<button type="button" onclick={() => navigate(action.tab!)}>{action.title}</button>{/if}{#if copyMessage}<p class="copy-message" aria-live="polite">{copyMessage}</p>{/if}</section>
    <p class="locks" aria-label="여섯 안전 잠금 상태">여섯 안전 잠금: {Object.values(status.locks).length === 6 && Object.values(status.locks).every((locked) => locked === false) ? '6/6 false' : 'MISSING'} · {Object.values(status.locks).length === 6 && Object.values(status.locks).every((locked) => locked === false) ? '모든 잠금은 false입니다.' : '잠금 상태를 확인할 수 없습니다.'}</p>
  </section>
{/if}

<style>
  .overview, .panel { max-width: 980px; border: 1px solid var(--border); border-radius: 14px; padding: clamp(18px, 4vw, 32px); background: var(--surface); color: var(--fg); } header > p, .locks { color: var(--muted); line-height: 1.55; } .eyebrow { margin: 0; color: var(--accent); font-size: .72rem; font-weight: 800; letter-spacing: .1em; } h1, h2 { color: var(--fg-strong); } h1 { margin: 7px 0 8px; font-size: clamp(1.7rem, 6vw, 2.5rem); } h2 { margin: 6px 0 10px; font-size: 1.08rem; line-height: 1.4; } .journey { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 8px; margin: 24px 0; padding: 0; list-style: none; } .journey button { width: 100%; min-width: 0; border: 1px solid var(--border-strong); border-radius: 10px; padding: 10px; background: var(--surface-raised); color: var(--fg); font: inherit; text-align: left; } .number { display: grid; width: 26px; height: 26px; place-items: center; border-radius: 50%; background: var(--accent-soft); color: var(--accent-strong); font-weight: 800; } .journey strong, .journey small { display: block; overflow-wrap: anywhere; } .journey strong { margin-top: 8px; font-size: .8rem; } .journey small { color: var(--muted); font-size: .67rem; } .chip { display: inline-block; margin-top: 9px; border: 1px solid currentColor; border-radius: 999px; padding: 2px 6px; font-size: .68rem; font-weight: 800; white-space: nowrap; } .partial { color: var(--info); } .waiting { color: var(--warn); } .blocked { color: var(--danger); } .blocker, .next-action { margin-top: 16px; border: 1px solid var(--danger); border-radius: 10px; padding: 16px; background: var(--danger-soft); } .next-action { border-color: var(--warn); background: var(--warn-soft); } .action-label { margin-bottom: 5px; color: var(--warn); font-size: .78rem; font-weight: 700; } code { display: block; max-width: 100%; overflow-wrap: anywhere; border: 1px solid var(--border-strong); border-radius: 6px; padding: 9px; color: var(--fg); font-size: .75rem; line-height: 1.5; } button { border: 1px solid var(--accent); border-radius: 6px; padding: 6px 10px; background: transparent; color: var(--accent-strong); font: inherit; cursor: pointer; } .command { display: flex; align-items: start; gap: 10px; } .command code { flex: 1; } .copy-message { color: var(--accent-strong); } .error { border-color: var(--danger); color: var(--danger); } @media (max-width: 700px) { .journey { grid-template-columns: repeat(2, minmax(0, 1fr)); } .command { flex-direction: column; } }
</style>
