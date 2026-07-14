<script lang="ts">
  import { onDestroy, type Snippet } from 'svelte';
  import { trainingHistory, trainingStatus } from '$lib/stores';
  import EvidenceDisclosure from '../components/EvidenceDisclosure.svelte';
  import PromotionLocksGrid from '../components/PromotionLocksGrid.svelte';
  import StateBoundary from '../components/StateBoundary.svelte';
  import LifecyclePill from '../components/LifecyclePill.svelte';
  import { adaptRunSnapshot } from './artifactEvidence';
  import type { EvidenceUiState } from '../evidenceState';

  interface Props {
    children?: Snippet;
  }

  let { children }: Props = $props();

  let statusPayload = $state<unknown>(null);
  let historyPayload = $state<unknown>(null);
  let statusSubscribed = $state(false);
  let historySubscribed = $state(false);

  const unsubscribeStatus = trainingStatus.subscribe((value) => {
    statusPayload = value;
    statusSubscribed = true;
  });
  const unsubscribeHistory = trainingHistory.subscribe((value) => {
    historyPayload = value;
    historySubscribed = true;
  });
  onDestroy(() => {
    unsubscribeStatus();
    unsubscribeHistory();
  });

  const snapshot = $derived(
    adaptRunSnapshot(statusPayload as never, historyPayload as never, { source_endpoint: '/api/training/status' }),
  );

  const workspaceState = $derived<EvidenceUiState>(
    !statusSubscribed || !historySubscribed ? 'loading' : snapshot.authority.level === 'missing' ? 'missing' : 'completed',
  );

  const evidenceRows = $derived([
    { key: 'run_id', label: 'Run ID', value: snapshot.run.run_id },
    { key: 'stage', label: 'Stage', value: snapshot.stage },
    { key: 'lifecycle', label: 'Lifecycle', value: snapshot.run.lifecycle },
    { key: 'status', label: 'Status', value: snapshot.statusLabel },
    { key: 'artifact_hash', label: 'Artifact hash', value: snapshot.identity.sha256 },
    { key: 'prereg', label: 'Prereg doc', value: snapshot.run.prereg_doc },
    { key: 'cost_bps', label: 'Cost (bps)', value: snapshot.run.cost_bps === null ? 'COST_NOT_RECORDED' : String(snapshot.run.cost_bps) },
    { key: 'split', label: 'Split', value: snapshot.run.split },
    { key: 'split_hash', label: 'Split hash', value: snapshot.run.split_hash },
    { key: 'seed', label: 'Seed', value: snapshot.run.seed },
  ]);
</script>

<section class="runs-workspace" data-v4-runs-workspace aria-labelledby="v4-runs-workspace-title">
  <div class="intro">
    <p class="eyebrow">V4 Runs Workspace · training history/status evidence</p>
    <h2 id="v4-runs-workspace-title">Run 증거는 authority·lifecycle·잠금을 raw 목록보다 먼저 표시합니다</h2>
    <p>
      training status/history store payload만 읽으며 run_id, seed, split/hash, prereg, cost는 출처가 명시한 값만 노출합니다.
      live broker, order, profit, model promotion GO는 선언하지 않습니다.
    </p>
  </div>

  {#if workspaceState === 'missing'}
    <StateBoundary state="missing" title="Run authority not recorded" detail="training status/history stores have not declared a run_name yet." />
  {:else if workspaceState === 'loading'}
    <StateBoundary state="loading" title="Run evidence loading" detail="training status/history store subscription pending." />
  {/if}

  <section class="authority-panel" data-v4-run-authority data-authority-level={snapshot.authority.level} aria-label="Run authority hierarchy">
    <div>
      <p class="eyebrow">Authority hierarchy</p>
      <h3>{snapshot.authority.label}</h3>
      <p>{snapshot.authority.source} · {snapshot.authority.reason}</p>
    </div>
    <dl>
      <div><dt>Stage</dt><dd>{snapshot.stage}</dd></div>
      <div>
        <dt>Lifecycle</dt>
        <dd><LifecyclePill state={workspaceState} detail={snapshot.run.lifecycle} /></dd>
      </div>
    </dl>
  </section>

  <section class="evidence-grid" data-v4-run-summary aria-label="Run identity, hash, prereg, cost, split, seed evidence">
    {#each evidenceRows as row (row.key)}
      <article data-run-field={row.key}>
        <span>{row.label}</span>
        <strong>{row.value}</strong>
      </article>
    {/each}
  </section>

  <section class="blockers" data-v4-run-blockers aria-label="Run blocking reasons">
    <div class="section-head">
      <p class="eyebrow">Blocking reasons</p>
      <h3>NO-GO는 기본값이며 blocker는 출처에서 dedupe합니다</h3>
    </div>
    <ul>
      {#each snapshot.run.blocking_reasons as blocker (blocker)}
        <li>{blocker}</li>
      {/each}
    </ul>
  </section>

  <PromotionLocksGrid result={snapshot.run.promotion_locks} compact />

  <EvidenceDisclosure summary="Legacy History & Runs functions · lazy child surface" meta="final disclosure; no duplicate initial storm" open={false} lazy>
    <div class="legacy-child" data-v4-runs-legacy-child data-v4-raw-audit>
      {#if children}
        {@render children()}
      {:else}
        <p>Legacy Runs child surface not supplied. V4 evidence remains GET-only and read-only.</p>
      {/if}
    </div>
  </EvidenceDisclosure>
</section>

<style>
  .runs-workspace {
    display: grid;
    gap: 16px;
    width: min(100%, var(--content-max));
    min-width: 0;
    max-width: 100%;
    margin-inline: auto;
    color: var(--fg);
    font-family: var(--font-body);
  }

  .runs-workspace > * {
    min-width: 0;
    max-width: 100%;
  }

  .intro,
  .authority-panel,
  .blockers,
  .evidence-grid article {
    border: 1px solid var(--border-faint);
    border-radius: var(--r-xl);
    background: var(--surface);
    box-shadow: var(--shadow-sm);
  }

  .intro,
  .authority-panel,
  .blockers {
    padding: 18px 20px;
  }

  .eyebrow,
  .evidence-grid span,
  dt {
    margin: 0;
    color: var(--accent-strong);
    font: 750 var(--t-eyebrow) / 1.2 var(--font-mono);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  h2,
  h3,
  p {
    margin-block: 0;
  }

  h2,
  h3,
  strong {
    color: var(--fg-strong);
    overflow-wrap: anywhere;
  }

  h2 {
    margin-top: 6px;
    font: 780 clamp(22px, 3.6vw, 34px) / 1.1 var(--font-display);
    letter-spacing: -0.03em;
  }

  .intro p {
    max-width: 88ch;
    color: var(--muted);
    line-height: 1.55;
  }

  .intro,
  .authority-panel > div,
  .section-head,
  .evidence-grid article {
    display: grid;
    gap: 8px;
  }

  .authority-panel {
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(280px, 1fr);
    gap: 16px;
  }

  .authority-panel[data-authority-level='canonical'] {
    border-color: var(--success);
  }

  .authority-panel[data-authority-level='missing'] {
    border-color: var(--warn);
  }

  .authority-panel p {
    color: var(--muted);
    line-height: 1.55;
    overflow-wrap: anywhere;
  }

  dl {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    margin: 0;
  }

  dl div {
    display: grid;
    gap: 4px;
    border: 1px solid var(--border-faint);
    border-radius: var(--r-md);
    padding: 10px;
    background: var(--surface-sunken);
  }

  dd {
    margin: 0;
    font: 720 var(--t-body) / 1.35 var(--font-mono);
    overflow-wrap: anywhere;
  }

  .evidence-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 12px;
  }

  .evidence-grid article {
    padding: 14px;
    min-width: 0;
    background: var(--surface-raised);
  }

  .evidence-grid strong {
    font: 700 12px/1.4 var(--font-mono);
    overflow-wrap: anywhere;
  }

  .blockers ul {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 14px 0 0;
    padding: 0;
    list-style: none;
  }

  .blockers li {
    border: 1px solid var(--danger);
    border-radius: var(--r-pill);
    padding: 7px 10px;
    background: var(--danger-soft);
    color: var(--danger);
    font: 760 var(--t-caption) / 1.2 var(--font-mono);
    overflow-wrap: anywhere;
  }

  .legacy-child {
    display: grid;
    gap: 12px;
  }

  @media (max-width: 980px) {
    .authority-panel,
    .evidence-grid {
      grid-template-columns: minmax(0, 1fr);
    }
  }

  @media (max-width: 720px) {
    .evidence-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 620px) {
    dl {
      grid-template-columns: 1fr;
    }

    .evidence-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
