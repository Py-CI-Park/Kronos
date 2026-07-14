<script lang="ts">
  import type { Snippet } from 'svelte';
  import { evidenceStateMeta, normalizeEvidenceState, type EvidenceUiState } from '../evidenceState';
  import LifecyclePill from './LifecyclePill.svelte';

  interface Props {
    state: EvidenceUiState;
    title?: string;
    detail?: string;
    onRetry?: () => void;
    children?: Snippet;
  }

  let { state, title, detail, onRetry, children }: Props = $props();

  let normalized = $derived(normalizeEvidenceState(state));
  let meta = $derived(evidenceStateMeta(normalized));
  let boundaryTitle = $derived(title ?? meta.title);
  let boundaryDetail = $derived(detail ?? meta.detail);
</script>

<section
  class="state-boundary"
  data-v4-state-boundary
  data-state={normalized}
  data-tone={meta.tone}
  data-blocking={meta.blocking ? 'true' : 'false'}
  aria-label={boundaryTitle}
>
  <div class="state-copy" role={meta.blocking ? 'status' : undefined} aria-live={meta.blocking ? 'polite' : undefined}>
    <LifecyclePill state={normalized} detail={meta.statusText} />
    <h2>{boundaryTitle}</h2>
    <p>{boundaryDetail}</p>

    {#if onRetry}
      <button type="button" class="retry-button" onclick={onRetry}>다시 시도</button>
    {/if}
  </div>

  {#if meta.showContent && children}
    <div class="state-content">
      {@render children()}
    </div>
  {/if}
</section>

<style>
  .state-boundary {
    display: grid;
    gap: 14px;
    border: 1px solid var(--border-faint);
    border-radius: var(--r-xl);
    padding: 18px;
    background: var(--surface);
    box-shadow: var(--shadow-sm);
    color: var(--fg);
    overflow-wrap: anywhere;
    word-break: keep-all;
  }

  .state-copy {
    display: grid;
    justify-items: start;
    gap: 9px;
  }

  h2 {
    margin: 0;
    color: var(--fg-strong);
    font: 780 var(--t-h5) / 1.2 var(--font-display);
    letter-spacing: -0.02em;
  }

  p {
    max-width: 70ch;
    margin: 0;
    color: var(--muted);
    font-size: var(--t-body);
    line-height: 1.55;
  }

  .retry-button {
    margin-top: 4px;
    border: 1px solid var(--border-strong);
    border-radius: var(--r-pill);
    padding: 8px 12px;
    background: var(--surface-raised);
    color: var(--fg-strong);
    font-weight: 760;
    transition:
      border-color var(--d-fast) var(--ease-out),
      background var(--d-fast) var(--ease-out),
      color var(--d-fast) var(--ease-out);
  }

  .retry-button:hover {
    border-color: var(--accent);
    background: var(--accent-soft);
    color: var(--accent-strong);
  }

  .state-content {
    min-width: 0;
  }

  .state-boundary[data-tone='info'] {
    border-color: var(--info);
    background: color-mix(in oklab, var(--info-soft) 34%, var(--surface));
  }

  .state-boundary[data-tone='positive'] {
    border-color: var(--success);
    background: color-mix(in oklab, var(--success-soft) 34%, var(--surface));
  }

  .state-boundary[data-tone='warning'] {
    border-color: var(--warn);
    background: color-mix(in oklab, var(--warn-soft) 34%, var(--surface));
  }

  .state-boundary[data-tone='danger'] {
    border-color: var(--danger);
    background: color-mix(in oklab, var(--danger-soft) 34%, var(--surface));
  }
</style>
