<script lang="ts">
  import { onDestroy, type Snippet } from 'svelte';
  import { artifacts } from '$lib/stores';
  import EvidenceDisclosure from '../components/EvidenceDisclosure.svelte';
  import PromotionLocksGrid from '../components/PromotionLocksGrid.svelte';
  import StateBoundary from '../components/StateBoundary.svelte';
  import {
    normalizeArtifactsEvidence,
    NOT_RECORDED,
    type ArtifactCategoryEvidence,
  } from './artifactEvidence';
  import type { EvidenceUiState } from '../evidenceState';

  interface Props {
    children?: Snippet;
  }

  let { children }: Props = $props();

  let payload = $state<unknown>(null);
  let subscribed = $state(false);

  const unsubscribeArtifacts = artifacts.subscribe((value) => {
    payload = value;
    subscribed = true;
  });
  onDestroy(unsubscribeArtifacts);

  const evidence = $derived(normalizeArtifactsEvidence(payload as never));
  const workspaceState = $derived<EvidenceUiState>(
    !subscribed ? 'loading' : evidence.status === 'not_recorded' ? 'missing' : evidence.status === 'empty' ? 'empty' : 'completed',
  );

  const categories: { key: 'checkpoints' | 'pretrainedWeights' | 'predictorOutputs'; label: string; category: string; evidence: ArtifactCategoryEvidence }[] = $derived([
    { key: 'checkpoints', label: 'Checkpoints', category: 'checkpoint', evidence: evidence.checkpoints },
    { key: 'pretrainedWeights', label: 'Pretrained / model weights', category: 'pretrained_weight', evidence: evidence.pretrainedWeights },
    { key: 'predictorOutputs', label: 'Predictor outputs', category: 'predictor_output', evidence: evidence.predictorOutputs },
  ]);

  const authorityRows = $derived([
    { key: 'checkpoint_ready', label: 'Checkpoint ready', authority: evidence.checkpointReady },
    { key: 'predictor_started', label: 'Predictor started', authority: evidence.predictorStarted },
    { key: 'predictor_complete', label: 'Predictor complete', authority: evidence.predictorComplete },
  ]);
</script>

<section class="artifacts-workspace" data-v4-artifacts-workspace aria-labelledby="v4-artifacts-workspace-title">
  <div class="intro">
    <p class="eyebrow">V4 Artifacts Workspace · GET-only evidence</p>
    <h2 id="v4-artifacts-workspace-title">아티팩트 증거는 checkpoint / pretrained weight / predictor output을 분리하고 hash·authority를 먼저 표시합니다</h2>
    <p>
      /api/training/artifacts 응답을 세 범주로 분리합니다. sha256/authority는 정확한 64자 hex와 명시적 문자열이 기록된 경우에만 노출되며,
      그 외에는 {NOT_RECORDED}로 표시됩니다. 이 화면은 model promotion, live broker/order, profit을 선언하지 않습니다.
    </p>
  </div>

  {#if workspaceState === 'missing'}
    <StateBoundary state="missing" title="Artifacts evidence not recorded" detail="/api/training/artifacts store payload is not yet populated." />
  {:else if workspaceState === 'loading'}
    <StateBoundary state="loading" title="Artifacts evidence loading" detail="training artifacts store subscription pending." />
  {/if}

  <section class="authority-panel" data-v4-artifact-stage-authority aria-label="Artifact stage authority booleans">
    {#each authorityRows as row (row.key)}
      <article data-v4-artifact-authority data-authority-key={row.key} data-declared={row.authority.declared ? 'true' : 'false'} data-source-status={row.authority.sourceStatus}>
        <span>{row.label}</span>
        <strong>{row.authority.declared ? 'true' : 'false'}</strong>
        <p>source: {row.authority.sourceStatus}</p>
      </article>
    {/each}
    <article data-v4-artifact-label>
      <span>Label</span>
      <strong>{evidence.label}</strong>
      <p>{evidence.message}</p>
    </article>
  </section>

  <section class="category-grid" aria-label="Checkpoint, pretrained weight, and predictor output category separation">
    {#each categories as row (row.key)}
      <article data-v4-artifact-category data-category={row.category} data-status={row.evidence.status}>
        <div class="category-head">
          <span>{row.label}</span>
          <strong>{row.evidence.files.length}</strong>
        </div>
        <p>declared count: {row.evidence.declaredCount === null ? NOT_RECORDED : row.evidence.declaredCount}</p>
        <p>status: {row.evidence.status}</p>
      </article>
    {/each}
  </section>

  <PromotionLocksGrid result={evidence.promotionLocks} compact />

  <EvidenceDisclosure summary="File-level hash / authority evidence per category" meta="selectors: data-v4-artifact-file" open>
    <div class="file-audit" data-v4-artifact-file-audit>
      {#each categories as row (row.key)}
        <section aria-label={`${row.label} file list`}>
          <h3>{row.label}</h3>
          {#if row.evidence.files.length === 0}
            <p class="empty-note">{row.evidence.status === 'not_recorded' ? NOT_RECORDED : 'EMPTY'}</p>
          {:else}
            <div class="file-table" role="table" aria-label={`${row.label} files`}>
              <div class="file-row file-row-head" role="row">
                <span role="columnheader">Name</span>
                <span role="columnheader">Hash</span>
                <span role="columnheader">Authority</span>
                <span role="columnheader">Size</span>
                <span role="columnheader">Modified</span>
              </div>
              {#each row.evidence.files as file (file.path + file.name)}
                <div class="file-row" role="row" data-v4-artifact-file data-category={file.category} data-hash-state={file.hash === NOT_RECORDED ? 'not_recorded' : 'recorded'}>
                  <span role="cell" class="file-name" title={file.path}>{file.name}</span>
                  <span role="cell" class="mono">{file.hash}</span>
                  <span role="cell" class="mono">{file.authority}</span>
                  <span role="cell" class="mono">{file.sizeLabel}</span>
                  <span role="cell" class="mono">{file.modifiedLabel}</span>
                </div>
              {/each}
            </div>
          {/if}
        </section>
      {/each}
    </div>
  </EvidenceDisclosure>

  <EvidenceDisclosure summary="Legacy Artifacts & Models functions · lazy child surface" meta="final disclosure; no duplicate initial storm" open={false} lazy>
    <div class="legacy-child" data-v4-artifacts-legacy-child data-v4-raw-audit>
      {#if children}
        {@render children()}
      {:else}
        <p>Legacy Artifacts child surface not supplied. V4 evidence remains GET-only and read-only.</p>
      {/if}
    </div>
  </EvidenceDisclosure>
</section>

<style>
  .artifacts-workspace {
    display: grid;
    gap: 16px;
    width: min(100%, var(--content-max));
    min-width: 0;
    max-width: 100%;
    margin-inline: auto;
    color: var(--fg);
    font-family: var(--font-body);
  }

  .artifacts-workspace > * {
    min-width: 0;
    max-width: 100%;
  }

  .intro,
  .authority-panel article,
  .category-grid article {
    border: 1px solid var(--border-faint);
    border-radius: var(--r-xl);
    background: var(--surface);
    box-shadow: var(--shadow-sm);
  }

  .intro {
    padding: 18px 20px;
    display: grid;
    gap: 8px;
  }

  .eyebrow,
  .authority-panel span,
  .category-grid span {
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
    font: 780 clamp(22px, 3.6vw, 34px) / 1.1 var(--font-display);
    letter-spacing: -0.03em;
  }

  .intro p {
    max-width: 88ch;
    color: var(--muted);
    line-height: 1.55;
  }

  .authority-panel,
  .category-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
  }

  .authority-panel article,
  .category-grid article {
    display: grid;
    gap: 8px;
    padding: 14px;
    min-width: 0;
    background: var(--surface-raised);
  }

  .authority-panel article[data-declared='true'] {
    border-color: var(--success);
    background: color-mix(in oklab, var(--success-soft) 34%, var(--surface));
  }

  .authority-panel article[data-source-status='missing'],
  .authority-panel article[data-source-status='invalid'] {
    border-color: var(--warn);
  }

  .category-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 8px;
  }

  .category-head strong {
    font: 760 clamp(20px, 6cqi, 30px) / 1 var(--font-display);
  }

  .category-grid article p,
  .authority-panel article p {
    color: var(--muted);
    font-size: var(--t-caption);
    line-height: 1.45;
    overflow-wrap: anywhere;
  }

  .file-audit {
    display: grid;
    gap: 16px;
  }

  .file-audit h3 {
    margin: 0 0 8px;
    font: 760 var(--t-h6, 15px) / 1.2 var(--font-display);
  }

  .empty-note {
    color: var(--muted);
    font: 700 12px/1.4 var(--font-mono);
    letter-spacing: 0.04em;
  }

  .file-table {
    display: grid;
    gap: 6px;
  }

  .file-row {
    display: grid;
    grid-template-columns: minmax(140px, 1.4fr) minmax(160px, 1.6fr) minmax(100px, 0.8fr) minmax(80px, 0.6fr) minmax(120px, 0.8fr);
    gap: 10px;
    align-items: center;
    border: 1px solid var(--border-faint);
    border-radius: var(--r-md);
    padding: 8px 10px;
    background: var(--surface-raised);
  }

  .file-row-head {
    border: 0;
    background: transparent;
    color: var(--muted);
    font: 760 11px/1.2 var(--font-mono);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .file-name {
    overflow-wrap: anywhere;
    color: var(--fg-strong);
    font-weight: 650;
  }

  .mono {
    font: 650 11px/1.35 var(--font-mono);
    color: var(--fg);
    overflow-wrap: anywhere;
  }

  .file-row[data-hash-state='not_recorded'] .mono:nth-child(2) {
    color: var(--warn);
  }

  .legacy-child {
    display: grid;
    gap: 12px;
  }

  @media (max-width: 1100px) {
    .authority-panel,
    .category-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 720px) {
    .authority-panel,
    .category-grid {
      grid-template-columns: 1fr;
    }

    .file-row {
      grid-template-columns: 1fr;
    }

    .file-row-head {
      position: absolute;
      width: 1px;
      height: 1px;
      margin: -1px;
      overflow: hidden;
      clip: rect(0 0 0 0);
      white-space: nowrap;
    }
  }
</style>
