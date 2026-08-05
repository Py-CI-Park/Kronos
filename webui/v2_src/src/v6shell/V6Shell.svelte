<script lang="ts">
  import { onMount } from 'svelte';
  import UnifiedSidebar from './components/shell/UnifiedSidebar.svelte';
  import SystemStatusRail from './components/shell/SystemStatusRail.svelte';
  import HomePage from './pages/HomePage.svelte';
  import RLWorkspace from './RLWorkspace.svelte';
  import InsightWorkspace from './InsightWorkspace.svelte';
  import KronosPage from './pages/KronosPage.svelte';
  import SettingsPage from './pages/SettingsPage.svelte';
  import { V6_PAGES, resolveV6Location, resolveV6Page, v6PageUrl, type V6PageDef } from './registry';
  import { v6Theme } from './v6Theme';
  import './v6-themes.css';
  import './unified-shell.css';

  let page = $state<V6PageDef>(V6_PAGES[0]);

  function selectFromLocation(): void {
    const params = new URLSearchParams(window.location.search);
    const location = resolveV6Location(params.get('tab'), params.get('step'), params.get('sub'), window.location.pathname);
    page = resolveV6Page(location.tab);
    const canonical = v6PageUrl(location.tab);
    const current = `${window.location.pathname}${window.location.search}`;
    if (current !== canonical) history.replaceState(history.state, '', canonical);
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

<div class="unified-v6-shell" data-unified-v6-shell data-v6-theme={$v6Theme === 'inherit' ? undefined : $v6Theme}>
  <UnifiedSidebar activePageId={page.id} onSelect={selectPage} />
  <main class="unified-v6-main">
    <SystemStatusRail />
    {#if page.id === 'command'}<HomePage />
    {:else if page.id === 'research'}<RLWorkspace initialStep="discovery" />
    {:else if page.id === 'live'}<RLWorkspace initialStep="training" />
    {:else if page.id === 'evaluation'}<RLWorkspace initialStep="evaluation" />
    {:else if page.id === 'evidence'}<InsightWorkspace />
    {:else if page.id === 'models'}<KronosPage />
    {:else if page.id === 'governance'}<RLWorkspace initialStep="report" />
    {:else}<SettingsPage />{/if}
  </main>
</div>
