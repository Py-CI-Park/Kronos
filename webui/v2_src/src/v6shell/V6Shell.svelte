<script lang="ts">
  import { onMount } from 'svelte';
  import UnifiedSidebar from './components/shell/UnifiedSidebar.svelte';
  import SystemStatusRail from './components/shell/SystemStatusRail.svelte';
  import HomePage from './pages/HomePage.svelte';
  import ResearchWorkspace from './pages/research/ResearchWorkspace.svelte';
  import LiveTrainingPage from './pages/live/LiveTrainingPage.svelte';
  import EvaluationWorkspace from './pages/evaluation/EvaluationWorkspace.svelte';
  import RLWorkspace from './RLWorkspace.svelte';
  import InsightWorkspace from './InsightWorkspace.svelte';
  import KronosPage from './pages/KronosPage.svelte';
  import SettingsPage from './pages/SettingsPage.svelte';
  import { V6_PAGES, resolveV6Location, resolveV6Page, v6PageUrl, type V6PageDef } from './registry';
  import { v6Theme } from './v6Theme';
  import './v6-themes.css';
  import './unified-shell.css';

  function initialPage(): V6PageDef {
    if (typeof window === 'undefined') return V6_PAGES[0];
    const params = new URLSearchParams(window.location.search);
    const location = resolveV6Location(params.get('tab'), params.get('step'), params.get('sub'), window.location.pathname);
    return resolveV6Page(location.tab);
  }

  let page = $state<V6PageDef>(initialPage());

  function selectFromLocation(): void {
    const params = new URLSearchParams(window.location.search);
    const location = resolveV6Location(params.get('tab'), params.get('step'), params.get('sub'), window.location.pathname);
    page = resolveV6Page(location.tab);
    const requestedTab = params.get('tab');
    if (window.location.pathname !== '/' || (requestedTab !== null && requestedTab !== location.tab)) {
      history.replaceState(history.state, '', v6PageUrl(location.tab));
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

<div class="unified-v6-shell" data-unified-v6-shell data-v6-theme={$v6Theme === 'inherit' ? undefined : $v6Theme}>
  <UnifiedSidebar activePageId={page.id} onSelect={selectPage} />
  <main class="unified-v6-main">
    <SystemStatusRail />
    {#if page.id === 'command'}<HomePage />
    {:else if page.id === 'research'}<ResearchWorkspace />
    {:else if page.id === 'live'}<LiveTrainingPage />
    {:else if page.id === 'evaluation'}<EvaluationWorkspace />
    {:else if page.id === 'evidence'}<InsightWorkspace />
    {:else if page.id === 'models'}<KronosPage />
    {:else if page.id === 'governance'}<RLWorkspace initialStep="report" />
    {:else}<SettingsPage />{/if}
  </main>
</div>
