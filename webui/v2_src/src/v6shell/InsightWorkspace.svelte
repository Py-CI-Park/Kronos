<script lang="ts">
  import { onMount } from 'svelte';
  import { resolveV6Location, V6_INSIGHT_SUBTABS } from './registry';
  import InsightSymbolPage from './pages/InsightSymbolPage.svelte';
  import InsightFlowPage from './pages/InsightFlowPage.svelte';
  import InsightRegimePage from './pages/InsightRegimePage.svelte';

  let active = $state('symbol');

  function selectFromLocation(): void {
    const params = new URLSearchParams(window.location.search);
    const location = resolveV6Location(params.get('tab'), null, params.get('sub'));
    active = location.tab === 'insight' && location.sub ? location.sub : 'symbol';
  }
  function selectSubtab(id: string): void {
    active = id;
    history.pushState(history.state, '', `?ui=v6&tab=insight&sub=${encodeURIComponent(id)}`);
  }

  onMount(() => {
    selectFromLocation();
    window.addEventListener('popstate', selectFromLocation);
    return () => window.removeEventListener('popstate', selectFromLocation);
  });
</script>

<section class="workspace" aria-labelledby="insight-title">
  <header><p class="eyebrow">RESEARCH INSIGHTS</p><h1 id="insight-title">인사이트</h1><p>시장 관찰은 추천이나 수익 주장으로 해석하지 않습니다.</p></header>
  <div class="segments" role="tablist" aria-label="인사이트 유형">
    {#each V6_INSIGHT_SUBTABS as tab}
      <button type="button" role="tab" aria-selected={active === tab.id} class:active={active === tab.id} onclick={() => selectSubtab(tab.id)}>{tab.labelKo}</button>
    {/each}
  </div>
  <div class="body">
    {#if active === 'symbol'}<InsightSymbolPage />
    {:else if active === 'flow'}<InsightFlowPage />
    {:else}<InsightRegimePage />{/if}
  </div>
</section>

<style>
  .workspace { width: 100%; min-width: 0; }
  .eyebrow { margin: 0; color: var(--accent); font-size: .72rem; font-weight: 800; letter-spacing: .1em; }
  h1 { margin: 5px 0; color: var(--fg-strong); font-size: clamp(1.7rem, 4vw, 2.3rem); }
  header p:last-child { color: var(--muted); }
  .segments { display: flex; flex-wrap: wrap; gap: 8px; margin: 20px 0; }
  button { border: 1px solid var(--border-strong); border-radius: 999px; padding: 8px 14px; background: var(--surface-raised); color: var(--muted); font: inherit; cursor: pointer; }
  button.active { border-color: var(--accent); background: var(--accent-soft); color: var(--accent-strong); font-weight: 800; }
  button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .body { min-width: 0; }
</style>
