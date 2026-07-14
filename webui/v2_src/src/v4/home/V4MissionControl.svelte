<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { dailyOhlcvApi } from '$lib/dailyOhlcvApi';
  import { rlApi } from '$lib/rlApi';
  import { requireJsonPayload } from '$lib/http';
  import { navigateToTab } from '$lib/routes';
  import { metricsLatest, trainingStatus } from '$lib/stores';
  import {
    PROMOTION_LOCK_KEYS,
    deriveMissionControlModel,
    settleMissionControlSources,
    type MissionControlInputs,
    type MissionTone,
  } from './missionControl';

  const lockLabels = {
    promotion_allowed: '승격',
    model_build_allowed: '모델 빌드',
    paper_forward_allowed: '페이퍼',
    live_broker_order_allowed: '브로커/주문',
    profitability_claim_allowed: '수익 주장',
    go_summary_allowed: '요약',
  } as const;

  let inputs = $state<MissionControlInputs>({});
  let train = $state<Record<string, unknown> | null>(null);
  let metrics = $state<Record<string, unknown> | null>(null);
  let loadErrors = $state<readonly string[]>([]);

  const unsubscribeTraining = trainingStatus.subscribe((value) => {
    train = value as unknown as Record<string, unknown> | null;
    inputs = { ...inputs, trainingStatus: train };
  });
  const unsubscribeMetrics = metricsLatest.subscribe((value) => {
    metrics = value as unknown as Record<string, unknown> | null;
    inputs = { ...inputs, metricsLatest: metrics };
  });

  const model = $derived(deriveMissionControlModel(inputs));

  onMount(() => {
    let alive = true;
    void (async () => {
      const { inputs: loadedInputs, errors } = await settleMissionControlSources({
        dailyProgress: requireJsonPayload('dailyProgress', dailyOhlcvApi.progress()),
        closeSlot: requireJsonPayload('closeSlot', dailyOhlcvApi.closeSlotLatest()),
        rlRuns: requireJsonPayload('rlRuns', rlApi.rlRuns(5)),
        rlQueue: requireJsonPayload('rlQueue', rlApi.factoryQueue()),
        rliableStats: requireJsonPayload('rliableStats', rlApi.rliableStats()),
      });
      if (!alive) return;
      inputs = { ...loadedInputs, trainingStatus: train, metricsLatest: metrics };
      loadErrors = errors;
    })();

    return () => {
      alive = false;
    };
  });

  onDestroy(() => {
    unsubscribeTraining();
    unsubscribeMetrics();
  });

  function open(tab: string): void {
    navigateToTab(tab);
  }

  function toneClass(tone: MissionTone): string {
    return `tone-${tone}`;
  }
</script>

<section class="v4-home" data-v4-mission-control aria-label="V4 Mission Control">
  <div class="top-blocker {model.topBlocker.status}" data-v4-top-blocker role="status" aria-live="polite">
    <div>
      <span class="eyebrow">Mission Control · 연구 전용</span>
      <h1>{model.topBlocker.text}</h1>
      <p>{model.topBlocker.detail}</p>
    </div>
    <span class="blocker-pill">{loadErrors.length > 0 ? 'API_UNAVAILABLE' : model.topBlocker.status === 'blocked' ? 'BLOCKED' : '확인 중'}</span>
  </div>
  {#if loadErrors.length > 0}
    <div class="api-errors" data-v4-home-api-errors>
      {#each loadErrors as error}
        <span>{error}</span>
      {/each}
    </div>
  {/if}

  <section class="locks" data-v4-home-locks aria-label="상태 잠금 6종">
    <div class="section-head">
      <span class="eyebrow">Status locks</span>
      <strong>정확한 6개 잠금 · 누락 시 false</strong>
    </div>
    <div class="lock-chips">
      {#each PROMOTION_LOCK_KEYS as key (key)}
        {@const state = model.locks.states[key]}
        {@const allowed = state?.sourceStatus === 'declared' && state.allowed === true}
        <span class="lock-chip" data-lock-key={key} data-allowed={allowed ? 'true' : 'false'} data-source-status={state?.sourceStatus ?? 'missing'}>
          <span>{lockLabels[key]}</span>
          <code>{key}</code>
          <b>{allowed ? 'true' : 'false'}</b>
        </span>
      {/each}
    </div>
  </section>

  <section class="workflow" data-v4-workflow-map aria-label="증거 워크플로우 맵">
    <div class="section-head compact">
      <span class="eyebrow">Workflow map</span>
      <strong>data → split → baseline → policy → TEST OOS → verdict</strong>
    </div>
    <ol>
      {#each model.workflow as step (step.id)}
        <li class={toneClass(step.tone)} data-v4-workflow-step={step.marker}>
          <span class="step-label">{step.label}</span>
          <span class="step-status">{step.status}</span>
        </li>
      {/each}
    </ol>
  </section>

  <section class="cards" aria-label="Mission Control cards">
    {#each model.cards as card (card.id)}
      <button type="button" class="home-card {toneClass(card.tone)}" data-v4-home-card data-card-id={card.id} onclick={() => open(card.tab)}>
        <span class="card-eyebrow">{card.eyebrow}</span>
        <span class="card-title">{card.title}</span>
        <span class="card-verdict">{card.verdict}</span>
        <span class="card-metric">{card.metric}</span>
        <span class="card-detail">{card.detail}</span>
        <span class="card-foot"><b>{card.source}</b><i>열기 →</i></span>
      </button>
    {/each}
  </section>
</section>

<style>
  .v4-home {
    width: calc(100% - 56px);
    max-width: min(var(--content-max), 100%);
    min-width: 0;
    margin: 18px auto 0;
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 12px;
    color: var(--fg);
  }

  .v4-home > * {
    min-width: 0;
  }

  .top-blocker,
  .locks,
  .workflow,
  .home-card {
    border: 1px solid var(--border-faint);
    background: color-mix(in oklab, var(--surface) 91%, transparent);
    box-shadow: var(--shadow-sm), var(--card-highlight);
  }

  .top-blocker {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    min-height: 82px;
    border-radius: 22px;
    padding: 14px 18px;
    border-color: color-mix(in oklab, var(--danger) 42%, var(--border));
    background:
      linear-gradient(100deg, color-mix(in oklab, var(--danger) 12%, transparent), transparent 52%),
      color-mix(in oklab, var(--surface) 92%, transparent);
  }
  .top-blocker > div {
    min-width: 0;
    max-width: 100%;
  }

  .top-blocker h1 {
    margin: 4px 0 3px;
    color: var(--fg-strong);
    font: 780 clamp(20px, 2.5vw, 30px)/1.08 var(--font-display);
    letter-spacing: -0.04em;
  }

  .top-blocker p {
    margin: 0;
    color: var(--muted);
    font: 520 12.5px/1.45 var(--font-sans);
    overflow-wrap: anywhere;
  }

  .eyebrow,
  .card-eyebrow {
    color: var(--accent-strong);
    font: 780 10px/1.1 var(--font-mono);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .blocker-pill {
    flex: 0 0 auto;
    border: 1px solid var(--danger);
    border-radius: var(--r-pill);
    padding: 8px 11px;
    color: var(--danger);
    background: var(--danger-soft);
    font: 800 11px/1 var(--font-mono);
  }

  .api-errors {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: -6px;
  }

  .api-errors span {
    border: 1px solid color-mix(in oklab, var(--danger) 35%, var(--border));
    border-radius: var(--r-pill);
    padding: 6px 9px;
    color: var(--danger);
    background: var(--danger-soft);
    font: 750 10px/1 var(--font-mono);
  }

  .locks,
  .workflow {
    border-radius: 18px;
    padding: 12px 14px;
  }

  .section-head {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: baseline;
    margin-bottom: 10px;
  }

  .section-head.compact {
    margin-bottom: 8px;
  }

  .section-head strong {
    color: var(--fg-strong);
    font: 720 12.5px/1.2 var(--font-display);
  }

  .lock-chips {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 7px;
  }

  .lock-chip {
    min-width: 0;
    display: grid;
    gap: 3px;
    border: 1px solid color-mix(in oklab, var(--danger) 35%, var(--border));
    border-radius: 13px;
    padding: 8px 9px;
    background: var(--danger-soft);
  }

  .lock-chip span {
    color: var(--fg-strong);
    font: 760 11px/1.1 var(--font-display);
  }

  .lock-chip code {
    color: var(--muted);
    font: 650 9px/1.25 var(--font-mono);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .lock-chip b {
    color: var(--danger);
    font: 850 11px/1 var(--font-mono);
  }

  .workflow ol {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 7px;
  }

  .workflow li {
    min-width: 0;
    border: 1px solid var(--border-faint);
    border-radius: 13px;
    padding: 8px 9px;
    background: var(--surface-raised);
    position: relative;
  }

  .workflow li::after {
    content: '→';
    position: absolute;
    right: -8px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--dim);
    font: 800 11px/1 var(--font-mono);
  }

  .workflow li:last-child::after {
    content: '';
  }

  .step-label,
  .step-status {
    display: block;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .step-label {
    color: var(--fg-strong);
    font: 800 11px/1.1 var(--font-mono);
  }

  .step-status {
    margin-top: 5px;
    color: var(--muted);
    font: 650 10px/1.1 var(--font-mono);
  }

  .cards {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
  }

  .home-card {
    min-width: 0;
    text-align: left;
    cursor: pointer;
    border-radius: 18px;
    padding: 13px 14px 12px;
    display: grid;
    gap: 5px;
    min-height: 142px;
    position: relative;
    overflow: hidden;
    transition: transform var(--d-fast) var(--ease-out), border-color var(--d-fast) var(--ease-out);
  }

  .home-card:hover {
    transform: translateY(-2px);
    border-color: var(--border-strong);
  }

  .home-card::before {
    content: '';
    position: absolute;
    inset: 0 0 auto 0;
    height: 3px;
    background: var(--dim);
  }

  .tone-danger::before,
  .workflow .tone-danger::before { background: var(--danger); }
  .tone-warn::before,
  .workflow .tone-warn::before { background: var(--warn); }
  .tone-ok::before,
  .workflow .tone-ok::before { background: var(--success); }
  .tone-accent::before,
  .workflow .tone-accent::before { background: var(--accent); }

  .card-title {
    color: var(--fg-strong);
    font: 780 15px/1.1 var(--font-display);
    letter-spacing: -0.02em;
  }

  .card-verdict {
    color: var(--fg-strong);
    font: 850 21px/1.05 var(--font-display);
    letter-spacing: -0.04em;
    overflow-wrap: anywhere;
  }

  .card-metric,
  .card-detail {
    color: var(--muted);
    font: 650 11px/1.3 var(--font-mono);
    overflow-wrap: anywhere;
  }

  .card-detail {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .card-foot {
    margin-top: auto;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    color: var(--dim);
    font: 800 10px/1 var(--font-mono);
  }

  .card-foot b {
    color: var(--muted);
  }

  .card-foot i {
    color: var(--accent-strong);
    font-style: normal;
  }

  .tone-danger .card-verdict,
  .workflow .tone-danger .step-status { color: var(--danger); }
  .tone-warn .card-verdict,
  .workflow .tone-warn .step-status { color: var(--warn); }
  .tone-ok .card-verdict,
  .workflow .tone-ok .step-status { color: var(--success); }

  @media (min-width: 1001px) {
    .v4-home {
      margin-top: 12px;
      gap: 8px;
    }

    .cards {
      gap: 8px;
    }

    .home-card {
      min-height: 128px;
      padding: 10px 12px;
      gap: 4px;
    }
  }
  @media (max-width: 1000px) {
    .lock-chips,
    .workflow ol {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .workflow li::after {
      content: '';
    }

    .cards {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 640px) {
    .v4-home {
      width: calc(100% - 32px);
    }

    .top-blocker,
    .section-head {
      align-items: flex-start;
      flex-direction: column;
    }

    .lock-chips,
    .workflow ol,
    .cards {
      grid-template-columns: 1fr;
    }
  }
</style>
