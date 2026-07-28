<script lang="ts">
  // Reusable progressive-disclosure (accordion) primitive.
  // Wraps native <details> so detail-heavy cards can collapse evidence by default.
  import type { Snippet } from 'svelte';

  interface Props {
    summary: string;
    meta?: string;
    open?: boolean;
    lazy?: boolean;
    children?: Snippet;
  }

  let { summary, meta = '', open = false, lazy = false, children }: Props = $props();
  let hasOpened = $state(false);
  $effect(() => {
    if (open) hasOpened = true;
  });

  function handleToggle(event: Event): void {
    if ((event.currentTarget as HTMLDetailsElement).open) hasOpened = true;
  }
</script>

<details class="disclosure" {open} ontoggle={handleToggle}>
  <summary>
    <span class="chev" aria-hidden="true">▶</span>
    <span class="disc-summary">{summary}</span>
    {#if meta}<span class="disc-meta">{meta}</span>{/if}
  </summary>
  <div class="disc-body">
    {#if !lazy || hasOpened}
      {@render children?.()}
    {/if}
  </div>
</details>

<style>
  .disclosure {
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
  }
  .disclosure + :global(.disclosure) { margin-top: 10px; }
  summary {
    list-style: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 13px 15px;
    font: 600 13px/1.3 var(--font-display);
    color: var(--fg-strong);
  }
  summary::-webkit-details-marker { display: none; }
  summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: var(--r-sm); }
  .chev {
    color: var(--dim);
    font-size: 12px;
    transition: transform var(--d-fast, 140ms) var(--ease-out, ease);
  }
  .disclosure[open] .chev { transform: rotate(90deg); }
  .disc-summary { flex: 1; min-width: 0; }
  .disc-meta {
    font: 500 11.5px/1.3 var(--font-mono);
    color: var(--muted);
    text-align: right;
  }
  .disc-body {
    padding: 2px 15px 15px;
    border-top: 1px solid var(--border-faint);
    padding-top: 14px;
  }
  /* When a full card/panel is wrapped directly, flatten it so the
     disclosure is the single visual container (no nested double border). */
  .disc-body > :global(.panel),
  .disc-body > :global(.card) {
    border: 0;
    box-shadow: none;
    border-radius: 0;
    padding: 0;
    background: transparent;
  }
  @media (prefers-reduced-motion: reduce) {
    .chev { transition: none; }
  }
</style>
