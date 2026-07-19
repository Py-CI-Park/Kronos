<script lang="ts">
  import { onMount } from 'svelte';
  import { getV6Status, type V6Status } from '../v6Api';

  const INDEX_COMMAND = 'py -3.11 scripts/collect_korean_index_artifact.py --market KOSPI --start-date 2018-01-01 --end-date 2026-06-12 --output-dir artifacts/korean_index';
  const STEPS = [
    ['Overview', '개요', (status: V6Status) => status.status],
    ['Data', '데이터', (status: V6Status) => status.journey.data.state],
    ['Experiment', '실험 설계', (status: V6Status) => status.journey.experiment.state],
    ['Training', '학습', (status: V6Status) => status.journey.training.state],
    ['Evaluation', '평가', (status: V6Status) => status.journey.evaluation.state],
    ['Compare', '비교', (_status: V6Status) => undefined],
    ['Report', '보고서', (status: V6Status) => status.journey.report.state],
  ] as const;

  let status = $state<V6Status | null>(null);
  let error = $state<string | null>(null);
  let loading = $state(true);

  function stateLabel(state: string | undefined): string {
    if (state === 'PARTIAL') return '진행 중';
    if (state === 'NOT_FROZEN' || state === 'NOT_RUN') return '대기';
    if (state === 'MISSING' || state === 'BLOCKED' || !state) return '차단';
    return state;
  }

  function stateClass(state: string | undefined): string {
    if (state === 'PARTIAL') return 'partial';
    if (state === 'NOT_FROZEN' || state === 'NOT_RUN') return 'waiting';
    return 'blocked';
  }

  async function load(): Promise<void> {
    loading = true;
    error = null;
    const result = await getV6Status();
    loading = false;
    if (result.ok && result.data) status = result.data;
    else error = result.error ?? '알 수 없는 오류가 발생했습니다.';
  }

  onMount(load);
</script>

{#if loading}
  <section class="panel" aria-live="polite"><p>현재 연구 상태를 확인하고 있습니다.</p></section>
{:else if error}
  <section class="panel error" aria-live="assertive">
    <h1>상태를 불러오지 못했습니다</h1>
    <p>{error}</p>
    <button type="button" onclick={load}>다시 시도</button>
  </section>
{:else if status}
  <section class="overview" aria-labelledby="overview-title">
    <header>
      <p class="eyebrow">RL JOURNEY HOME</p>
      <h1 id="overview-title">강화학습 연구 여정</h1>
      <p>각 단계는 API가 보고한 상태만 표시합니다. 없는 상태는 차단으로 표시됩니다.</p>
    </header>

    <ol class="journey" aria-label="7단계 연구 여정">
      {#each STEPS as [label, labelKo, getState], index}
        {@const rawState = getState(status)}
        <li>
          <span class="number">{index + 1}</span>
          <div><strong>{labelKo}</strong><small>{label}</small></div>
          <span class={`chip ${stateClass(rawState)}`}>{stateLabel(rawState)}</span>
        </li>
      {/each}
    </ol>

    {#if status.journey.data.index_overlay === 'BLOCKED'}
      <section class="blocker" aria-labelledby="blocker-title">
        <p class="eyebrow">PRIMARY BLOCKER</p>
        <h2 id="blocker-title">KOSPI/KOSDAQ 지수 수집이 KRX 자격증명(KRX_ID/KRX_PW)을 요구합니다</h2>
        <p>{status.journey.data.index_blocker_reason ?? 'BLOCKED'}</p>
        <p class="action-label">다음 실행 명령</p>
        <code>{INDEX_COMMAND}</code>
      </section>
    {/if}

    <section class="next-action" aria-labelledby="next-action-title">
      <p class="eyebrow">NEXT ACTION</p>
      <h2 id="next-action-title">다음 행동</h2>
      <p><strong>R-2 사전등록 동결</strong>이 대기 중입니다. 동결 전에는 연구 결과를 주장하지 않습니다.</p>
    </section>

    <p class="locks" aria-label="여섯 안전 잠금 상태">여섯 안전 잠금: {Object.values(status.locks).length === 6 && Object.values(status.locks).every((locked) => locked === false) ? '6/6 false' : 'MISSING'} · {Object.values(status.locks).length === 6 && Object.values(status.locks).every((locked) => locked === false) ? '모든 잠금은 false입니다.' : '잠금 상태를 확인할 수 없습니다.'}</p>
  </section>
{/if}

<style>
  .overview, .panel { max-width: 980px; border: 1px solid var(--surface-border, #334155); border-radius: 14px; padding: clamp(18px, 4vw, 32px); background: var(--surface, #111827); color: #e5e7eb; }
  header > p { color: #cbd5e1; line-height: 1.55; }
  .eyebrow { margin: 0; color: #7dd3fc; font-size: .72rem; font-weight: 800; letter-spacing: .1em; }
  h1 { margin: 7px 0 8px; color: #f8fafc; font-size: clamp(1.7rem, 6vw, 2.5rem); }
  h2 { margin: 6px 0 10px; color: #f8fafc; font-size: 1.08rem; line-height: 1.4; }
  .journey { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 8px; margin: 24px 0; padding: 0; list-style: none; }
  .journey li { min-width: 0; border: 1px solid #475569; border-radius: 10px; padding: 10px; background: #0f172a; }
  .number { display: grid; width: 26px; height: 26px; place-items: center; border-radius: 50%; background: #0c4a6e; color: #e0f2fe; font-weight: 800; }
  .journey strong, .journey small { display: block; overflow-wrap: anywhere; }
  .journey strong { margin-top: 8px; font-size: .8rem; }
  .journey small { color: #94a3b8; font-size: .67rem; }
  .chip { display: inline-block; margin-top: 9px; border: 1px solid; border-radius: 999px; padding: 2px 6px; font-size: .68rem; font-weight: 800; white-space: nowrap; }
  .partial { border-color: #0369a1; color: #bae6fd; } .waiting { border-color: #a16207; color: #fde68a; } .blocked { border-color: #b91c1c; color: #fecaca; }
  .blocker, .next-action { margin-top: 16px; border: 1px solid #7f1d1d; border-radius: 10px; padding: 16px; background: #1c1012; }
  .next-action { border-color: #a16207; background: #1c1910; }
  .action-label { margin-bottom: 5px; color: #fcd34d; font-size: .78rem; font-weight: 700; }
  code { display: block; max-width: 100%; overflow-wrap: anywhere; border: 1px solid #7f1d1d; border-radius: 6px; padding: 9px; color: #fecaca; font-size: .75rem; line-height: 1.5; }
  .locks { margin: 18px 0 0; color: #cbd5e1; font-size: .82rem; }
  .error { border-color: #b91c1c; color: #fecaca; } button { border: 1px solid #7dd3fc; border-radius: 6px; padding: 6px 10px; background: transparent; color: #e0f2fe; font: inherit; cursor: pointer; }
  @media (max-width: 700px) { .journey { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
