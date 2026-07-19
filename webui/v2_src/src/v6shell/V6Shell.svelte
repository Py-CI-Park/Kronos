<script lang="ts">
  import { onMount } from 'svelte';
  import V6PagePlaceholder from './V6PagePlaceholder.svelte';
  import V6SafetyStrip from './V6SafetyStrip.svelte';
  import OverviewPage from './pages/OverviewPage.svelte';
  import DataPage from './pages/DataPage.svelte';
  import { V6_BRAND, V6_PAGES, resolveV6Page, v6PageUrl, type V6PageDef } from './registry';

  const GROUPS = ['COMMAND', 'REINFORCEMENT LEARNING', 'INSIGHT', 'PLATFORM', 'ADVANCED'] as const;
  let page = $state<V6PageDef>(V6_PAGES[0]);

  function selectFromLocation(): void {
    page = resolveV6Page(new URLSearchParams(window.location.search).get('tab'));
  }

  function selectPage(id: string): void {
    page = resolveV6Page(id);
    history.pushState(history.state, '', v6PageUrl(id));
  }

  onMount(() => {
    selectFromLocation();
    window.addEventListener('popstate', selectFromLocation);
    return () => window.removeEventListener('popstate', selectFromLocation);
  });
</script>

<div class="v6-shell" data-v6-shell>
  <aside class="sidebar" aria-label="V6 탐색">
    <header class="brand">
      <p>{V6_BRAND.subtitle}</p>
      <h1>{V6_BRAND.name}</h1>
      <small>{V6_BRAND.version} · {V6_BRAND.updateDate}</small>
    </header>
    <nav>
      {#each GROUPS as group}
        <section class="nav-group" aria-label={group}>
          <h2>{group}</h2>
          {#each V6_PAGES.filter((item) => item.group === group) as item}
            <button
              type="button"
              class:active={page.id === item.id}
              aria-current={page.id === item.id ? 'page' : undefined}
              aria-label={`${item.labelKo} (${item.label})`}
              onclick={() => selectPage(item.id)}
            >
              {#if item.step !== null}
                <span class="step-badge">{item.step}</span>
              {:else}
                <span class="initial-badge">{item.label.slice(0, 1)}</span>
              {/if}
              <span class="nav-label">{item.labelKo} <small>{item.label}</small></span>
              {#if item.status === 'NOT_BUILT'}<span class="planned">예정</span>{/if}
            </button>
          {/each}
        </section>
      {/each}
    </nav>
  </aside>

  <main>
    <V6SafetyStrip />
    {#if page.id === 'overview'}
      <OverviewPage />
    {:else if page.id === 'data'}
      <DataPage />
    {:else}
      <V6PagePlaceholder {page} />
    {/if}
  </main>
</div>

<style>
  .v6-shell { display: grid; grid-template-columns: 272px minmax(0, 1fr); min-height: 100vh; overflow-x: hidden; background: #020617; color: #e2e8f0; }
  .sidebar { min-width: 0; border-right: 1px solid #1e293b; background: #0f172a; padding: 18px 12px; }
  .brand { padding: 4px 8px 20px; border-bottom: 1px solid #334155; }
  .brand p { margin: 0 0 6px; color: #38bdf8; font-size: 0.68rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
  .brand h1 { margin: 0; color: #f8fafc; font-size: 1.25rem; line-height: 1.2; }
  .brand small { display: block; margin-top: 8px; color: #94a3b8; font-size: 0.7rem; }
  nav { margin-top: 14px; }
  .nav-group + .nav-group { margin-top: 14px; }
  .nav-group h2 { margin: 0 8px 5px; color: #64748b; font-size: 0.65rem; letter-spacing: 0.1em; }
  button { width: 100%; min-width: 0; margin: 2px 0; padding: 7px 8px; display: flex; align-items: center; gap: 8px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: #cbd5e1; font: inherit; text-align: left; cursor: pointer; }
  button:hover, button.active { border-color: #0ea5e9; background: #082f49; color: #f0f9ff; }
  button:focus-visible { outline: 2px solid #fef08a; outline-offset: 2px; }
  .step-badge, .initial-badge { flex: 0 0 22px; height: 22px; display: grid; place-items: center; border: 1px solid #475569; border-radius: 50%; color: #bae6fd; font-size: 0.72rem; font-weight: 800; }
  .initial-badge { font-size: 0.65rem; }
  .nav-label { min-width: 0; flex: 1; font-size: 0.86rem; }
  .nav-label small { margin-left: 4px; color: #94a3b8; font-size: 0.68rem; }
  .planned { flex: 0 0 auto; border: 1px solid #a16207; border-radius: 999px; padding: 1px 5px; color: #fcd34d; font-size: 0.63rem; }
  main { min-width: 0; padding: clamp(12px, 3vw, 32px); display: flex; flex-direction: column; gap: 16px; }
  @media (max-width: 900px) {
    .v6-shell { grid-template-columns: 64px minmax(0, 1fr); }
    .sidebar { padding: 12px 8px; }
    .brand { padding: 4px 0 12px; text-align: center; }
    .brand p, .brand h1, .brand small, .nav-group h2, .nav-label, .planned { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
    button { justify-content: center; padding: 7px 2px; }
  }
  @media (max-width: 390px) { main { padding: 10px; } }
</style>
