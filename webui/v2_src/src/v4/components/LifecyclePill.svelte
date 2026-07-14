<script lang="ts">
  import { evidenceStateMeta, normalizeEvidenceState, type EvidenceUiState } from '../evidenceState';

  interface Props {
    state: EvidenceUiState;
    detail?: string;
  }

  let { state, detail }: Props = $props();

  let normalized = $derived(normalizeEvidenceState(state));
  let meta = $derived(evidenceStateMeta(normalized));
</script>

<span
  class="lifecycle-pill"
  data-v4-lifecycle-pill
  data-state={normalized}
  data-tone={meta.tone}
  aria-label={`${meta.label}: ${detail ?? meta.statusText}`}
>
  <span class="status-dot" aria-hidden="true"></span>
  <span class="label">{meta.label}</span>
  {#if detail}
    <span class="detail">{detail}</span>
  {/if}
</span>

<style>
  .lifecycle-pill {
    display: inline-flex;
    max-width: 100%;
    align-items: center;
    gap: 7px;
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    padding: 6px 10px;
    background: var(--surface-raised);
    color: var(--fg);
    font: 740 var(--t-caption) / 1.2 var(--font-body);
    overflow-wrap: anywhere;
    word-break: keep-all;
  }

  .status-dot {
    width: 8px;
    height: 8px;
    flex: 0 0 auto;
    border-radius: var(--r-pill);
    background: var(--muted);
  }

  .label {
    color: var(--fg-strong);
    white-space: nowrap;
  }

  .detail {
    min-width: 0;
    color: var(--muted);
    font-weight: 620;
  }

  .lifecycle-pill[data-tone='info'] {
    border-color: var(--info);
    background: var(--info-soft);
    color: var(--info);
  }

  .lifecycle-pill[data-tone='positive'] {
    border-color: var(--success);
    background: var(--success-soft);
    color: var(--success);
  }

  .lifecycle-pill[data-tone='warning'] {
    border-color: var(--warn);
    background: var(--warn-soft);
    color: var(--warn);
  }

  .lifecycle-pill[data-tone='danger'] {
    border-color: var(--danger);
    background: var(--danger-soft);
    color: var(--danger);
  }

  .lifecycle-pill[data-tone='info'] .status-dot {
    background: var(--info);
  }

  .lifecycle-pill[data-tone='positive'] .status-dot {
    background: var(--success);
  }

  .lifecycle-pill[data-tone='warning'] .status-dot {
    background: var(--warn);
  }

  .lifecycle-pill[data-tone='danger'] .status-dot {
    background: var(--danger);
  }
</style>
