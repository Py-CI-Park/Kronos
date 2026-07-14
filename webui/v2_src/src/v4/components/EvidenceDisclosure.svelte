<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    summary: string;
    meta?: string;
    open?: boolean;
    lazy?: boolean;
    children?: Snippet;
  }

  let { summary, meta, open = false, lazy = false, children }: Props = $props();
  let expanded = $state(false);

  $effect(() => {
    expanded = open;
  });
</script>

<details class="evidence-disclosure" bind:open={expanded} data-v4-evidence-disclosure>
  <summary>
    <span class="summary-text">{summary}</span>
    {#if meta}
      <span class="meta">{meta}</span>
    {/if}
  </summary>
  {#if children && (!lazy || expanded)}
    <div class="content">
      {@render children()}
    </div>
  {/if}
</details>

<style>
  .evidence-disclosure {
    border: 1px solid var(--border-faint);
    border-radius: 18px;
    background: color-mix(in oklab, var(--surface) 92%, transparent);
    color: var(--fg);
    font-family: var(--font-body);
    overflow: clip;
    overflow-wrap: anywhere;
    word-break: auto-phrase;
  }

  summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    min-height: 46px;
    padding: 13px 16px;
    color: var(--fg-strong);
    cursor: pointer;
    list-style: none;
    outline: none;
    position: relative;
  }

  summary::-webkit-details-marker {
    display: none;
  }

  summary::before {
    content: '›';
    flex: 0 0 auto;
    color: var(--accent-strong);
    font: 800 18px/1 var(--font-mono);
    transform: rotate(0deg);
    transition: transform var(--d-fast) var(--ease-out);
  }

  .evidence-disclosure[open] summary::before {
    transform: rotate(90deg);
  }

  summary:focus-visible {
    box-shadow: inset 0 0 0 2px var(--accent-strong);
  }

  .summary-text {
    flex: 1 1 auto;
    font: 750 13px/1.3 var(--font-body);
  }

  .meta {
    flex: 0 1 auto;
    color: var(--muted);
    font: 700 10px/1.2 var(--font-mono);
    letter-spacing: 0.05em;
    text-transform: uppercase;
    text-align: end;
  }

  .content {
    border-top: 1px solid var(--border-faint);
    padding: 16px;
    color: var(--fg);
    line-height: 1.55;
  }

  @media (max-width: 560px) {
    summary {
      align-items: flex-start;
      flex-direction: column;
    }

    summary::before {
      position: absolute;
    }

    .summary-text,
    .meta {
      padding-inline-start: 24px;
      text-align: start;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    summary::before {
      transition: none;
    }
  }
</style>
