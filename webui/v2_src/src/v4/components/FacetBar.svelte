<script lang="ts" module>
  export type V4Facet = {
    id: string;
    label: string;
    value?: string;
    active?: boolean;
    disabled?: boolean;
    reason?: string;
  };
</script>

<script lang="ts">
  interface Props {
    facets: readonly V4Facet[];
    ariaLabel?: string;
    onSelect?: (id: string) => void;
  }

  let { facets, ariaLabel = 'Evidence facets', onSelect }: Props = $props();

  const componentId = $props.id();
  const fallbackDisabledReason = '비활성 사유: 현재 증거 상태에서 선택할 수 없습니다.';

  const toIdPart = (value: string) =>
    value
      .toLowerCase()
      .replace(/[^a-z0-9가-힣]+/g, '-')
      .replace(/^-+|-+$/g, '') || 'facet';

  const reasonFor = (facet: V4Facet) => {
    const reason = facet.reason?.trim();
    if (reason) return reason;
    return facet.disabled ? fallbackDisabledReason : undefined;
  };

  const reasonIdFor = (facet: V4Facet) => `facet-reason-${componentId}-${toIdPart(facet.id)}`;

  const selectFacet = (facet: V4Facet, event?: Event) => {
    if (facet.disabled) {
      event?.preventDefault();
      event?.stopPropagation();
      return;
    }
    onSelect?.(facet.id);
  };

  const suppressDisabledKey = (facet: V4Facet, event: KeyboardEvent) => {
    if (!facet.disabled || (event.key !== 'Enter' && event.key !== ' ')) return;
    event.preventDefault();
    event.stopPropagation();
  };
</script>

<nav class="facet-bar" aria-label={ariaLabel} data-v4-facet-bar>
  {#each facets as facet (facet.id)}
    {@const explanation = reasonFor(facet)}
    <button
      type="button"
      class="facet"
      class:active={facet.active}
      aria-disabled={facet.disabled ? 'true' : 'false'}
      aria-pressed={facet.active ? 'true' : 'false'}
      aria-describedby={explanation ? reasonIdFor(facet) : undefined}
      onkeydown={(event) => suppressDisabledKey(facet, event)}
      onclick={(event) => selectFacet(facet, event)}
    >
      <span class="label">{facet.label}</span>
      {#if facet.value}
        <span class="value">{facet.value}</span>
      {/if}
      {#if explanation}
        <span class="reason" id={reasonIdFor(facet)}>{explanation}</span>
      {/if}
    </button>
  {/each}
</nav>

<style>
  .facet-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    min-width: 0;
    padding: 6px;
    border: 1px solid var(--border-faint);
    border-radius: 20px;
    background: color-mix(in oklab, var(--surface) 88%, transparent);
    font-family: var(--font-body);
    overflow-wrap: anywhere;
    word-break: auto-phrase;
  }

  .facet {
    min-width: min(100%, 128px);
    max-width: 100%;
    display: inline-grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 3px;
    border: 1px solid var(--border-faint);
    border-radius: 16px;
    padding: 9px 12px;
    color: var(--fg);
    background: var(--surface-raised);
    text-align: start;
    cursor: pointer;
    transition:
      border-color 160ms ease,
      background-color 160ms ease,
      transform 160ms ease;
  }

  .facet:hover:not([aria-disabled='true']) {
    border-color: color-mix(in oklab, var(--accent) 46%, var(--border));
    background: color-mix(in oklab, var(--accent) 9%, var(--surface-raised));
    transform: translateY(-1px);
  }

  .facet:focus-visible {
    outline: 2px solid var(--accent-strong);
    outline-offset: 2px;
  }

  .facet[aria-disabled='true'] {
    cursor: not-allowed;
    opacity: 0.62;
  }

  .facet.active {
    border-color: color-mix(in oklab, var(--accent) 55%, var(--border));
    color: var(--accent-strong);
    background: color-mix(in oklab, var(--accent) 12%, var(--surface));
  }

  .label {
    min-width: 0;
    color: inherit;
    font: 750 12px/1.2 var(--font-body);
  }

  .value {
    color: var(--muted);
    font: 700 11px/1.2 var(--font-mono);
  }

  .reason {
    color: var(--muted);
    font: 650 10px/1.35 var(--font-mono);
  }

  @media (max-width: 560px) {
    .facet-bar,
    .facet {
      display: grid;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .facet {
      transition: none;
    }

    .facet:hover:not([aria-disabled='true']) {
      transform: none;
    }
  }
</style>
