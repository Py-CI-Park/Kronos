<script lang="ts">
  import { onMount } from 'svelte';
  import V6SafetyStrip from './V6SafetyStrip.svelte';
  import HomePage from './pages/HomePage.svelte';
  import RLWorkspace from './RLWorkspace.svelte';
  import InsightWorkspace from './InsightWorkspace.svelte';
  import IntradayPage from './pages/IntradayPage.svelte';
  import KronosPage from './pages/KronosPage.svelte';
  import SettingsPage from './pages/SettingsPage.svelte';
  import { V6_BRAND, V6_PAGES, resolveV6Location, resolveV6Page, v6PageUrl, type V6PageDef } from './registry';
  import { v6Scale, v6Theme } from './v6Theme';
  import './v6-themes.css';

  const GROUPS = ['COMMAND', 'RESEARCH', 'PLATFORM', 'ADVANCED'] as const;
  let page = $state<V6PageDef>(V6_PAGES[0]);

  function selectFromLocation(): void {
    const params = new URLSearchParams(window.location.search);
    const location = resolveV6Location(params.get('tab'), params.get('step'), params.get('sub'));
    page = resolveV6Page(location.tab);
    if (params.get('tab') !== location.tab || params.get('step') !== (location.step ?? null) || params.get('sub') !== (location.sub ?? null)) {
      const canonical = new URLSearchParams({ ui: 'v6', tab: location.tab });
      if (location.step) canonical.set('step', location.step);
      if (location.sub) canonical.set('sub', location.sub);
      history.replaceState(history.state, '', `?${canonical.toString()}`);
    }
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

<div class="v6-shell" data-v6-shell data-v6-theme={$v6Theme === 'inherit' ? undefined : $v6Theme} style:zoom={$v6Scale}>
  <aside class="sidebar" aria-label="V6 탐색">
    <header class="brand"><p>{V6_BRAND.subtitle}</p><h1>{V6_BRAND.name}</h1><small>{V6_BRAND.version} · {V6_BRAND.updateDate}</small></header>
    <nav>
      {#each GROUPS as group}
        <section class="nav-group" aria-label={group}>
          <h2>{group}</h2>
          {#each V6_PAGES.filter((item) => item.group === group) as item}
            <button type="button" class:active={page.id === item.id} aria-current={page.id === item.id ? 'page' : undefined} aria-label={`${item.labelKo} (${item.label})`} onclick={() => selectPage(item.id)}>
              {#if item.step !== null}<span class="step-badge">{item.step}</span>{:else}<span class="initial-badge">{item.label.slice(0, 1)}</span>{/if}
              <span class="nav-label">{item.labelKo} <small>{item.label}</small></span>
            </button>
          {/each}
        </section>
      {/each}
    </nav>
  </aside>

  <main>
    <V6SafetyStrip />
    {#if page.id === 'home'}<HomePage />
    {:else if page.id === 'rl'}<RLWorkspace />
    {:else if page.id === 'insight'}<InsightWorkspace />
    {:else if page.id === 'lanes'}<section class="lanes" aria-label="다른 연구 레인"><IntradayPage /><KronosPage /></section>
    {:else}<SettingsPage />{/if}
  </main>
</div>

<style>
  .v6-shell { display: grid; grid-template-columns: minmax(208px, 272px) minmax(0, 1fr); min-height: 100vh; overflow-x: hidden; background: var(--surface-sunken); color: var(--fg); }
  .sidebar { min-width: 0; border-right: 1px solid var(--border); background: var(--surface-raised); padding: 14px 10px; }.brand { min-width: 0; padding: 4px 8px 14px; border-bottom: 1px solid var(--border); }.brand p { margin: 0 0 5px; color: var(--accent); font-size: .68rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; overflow-wrap: anywhere; }.brand h1 { margin: 0; color: var(--fg-strong); font-size: clamp(1rem, 1.4vw, 1.25rem); line-height: 1.2; overflow-wrap: anywhere; }.brand small { display: block; margin-top: 6px; color: var(--muted); font-size: .7rem; overflow-wrap: anywhere; }nav { margin-top: 10px; }.nav-group + .nav-group { margin-top: 10px; }.nav-group h2 { margin: 0 8px 3px; color: var(--dim); font-size: .65rem; letter-spacing: .1em; }.nav-group button { width: 100%; min-width: 0; margin: 1px 0; padding: 6px 8px; display: flex; align-items: center; gap: 8px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: var(--muted); font: inherit; text-align: left; cursor: pointer; }.nav-group button:hover, .nav-group button.active { border-color: var(--accent); background: var(--accent-soft); color: var(--fg-strong); }.nav-group button:focus-visible { outline: 2px solid var(--warn); outline-offset: 2px; }.step-badge, .initial-badge { flex: 0 0 22px; height: 22px; display: grid; place-items: center; border: 1px solid var(--border-strong); border-radius: 50%; color: var(--accent-strong); font-size: .72rem; font-weight: 800; }.initial-badge { font-size: .65rem; }.nav-label { min-width: 0; flex: 1; overflow-wrap: anywhere; font-size: .86rem; }.nav-label small { display: inline; margin-left: 4px; color: var(--muted); font-size: .68rem; }main { width: 100%; min-width: 0; padding: 24px clamp(24px, 3vw, 56px); display: flex; flex-direction: column; gap: 16px; }.lanes { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; min-width: 0; }
  @media (max-width: 900px) { .v6-shell { grid-template-columns: 64px minmax(0, 1fr); }.sidebar { padding: 12px 8px; }.brand { padding: 4px 0 12px; text-align: center; }.brand p, .brand h1, .brand small, .nav-group h2, .nav-label { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }.nav-group button { justify-content: center; padding: 7px 2px; }.lanes { grid-template-columns: 1fr; } }@media (max-width: 390px) { main { padding: 10px; } }
</style>
