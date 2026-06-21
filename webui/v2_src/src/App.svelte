<script lang="ts">
  import { onMount } from 'svelte';
  import Sidebar from '$layout/Sidebar.svelte';
  import Header from '$layout/Header.svelte';
  import HeroStrip from '$layout/HeroStrip.svelte';
  import LiveTrainingTab from '$tabs/LiveTrainingTab.svelte';
  import ForecastWorkbenchTab from '$tabs/ForecastWorkbenchTab.svelte';
  import StomDiagnosticsTab from '$tabs/StomDiagnosticsTab.svelte';
  import DailyOhlcvTab from '$tabs/DailyOhlcvTab.svelte';
  import DailyRlGuideTab from '$tabs/DailyRlGuideTab.svelte';
  import ArtifactsModelsTab from '$tabs/ArtifactsModelsTab.svelte';
  import HistoryRunsTab from '$tabs/HistoryRunsTab.svelte';
  import SystemHealthTab from '$tabs/SystemHealthTab.svelte';
  import SettingsTab from '$tabs/SettingsTab.svelte';
  import DocsTab from '$tabs/DocsTab.svelte';
  import { activeTab, sidebarCollapsed } from '$lib/stores';
  import { installPollingWatcher, startPolling } from '$lib/polling';
  import { syncTabFromLocation } from '$lib/routes';
  // Route marker contract for tests: '/rl' '/daily-ohlcv' '/daily-rl-guide' '/daily-ohlcv/rl-guide'

  let removePopstate: (() => void) | undefined;

  onMount(() => {
    syncTabFromLocation({ replaceAlias: true });
    const handlePopstate = () => syncTabFromLocation();
    window.addEventListener('popstate', handlePopstate);
    removePopstate = () => window.removeEventListener('popstate', handlePopstate);
    installPollingWatcher();
    startPolling();
    return () => {
      removePopstate?.();
    };
  });

  let tab = $state('live-training');
  activeTab.subscribe((v) => (tab = v));
  let collapsed = $state(false);
  sidebarCollapsed.subscribe((v) => (collapsed = v));
</script>

<div class="app-shell" data-sidebar={collapsed ? 'collapsed' : 'expanded'}>
  <Sidebar />
  <div class="main">
    <Header />
    <div class="page">
      {#if tab === 'live-training'}
        <HeroStrip />
        <LiveTrainingTab />
      {:else if tab === 'forecast'}
        <ForecastWorkbenchTab />
      {:else if tab === 'stom'}
        <StomDiagnosticsTab />
      {:else if tab === 'rl'}
        <section class="card" data-trading-command-center-redirect>
          <h2>Trading Command Center</h2>
          <p>트레이딩 화면은 Flask가 제공하는 React/Next command center인 <a href="/rl">/rl</a>에서 열립니다.</p>
        </section>
      {:else if tab === 'daily-ohlcv'}
        <DailyOhlcvTab />
      {:else if tab === 'daily-rl-guide'}
        <DailyRlGuideTab />
      {:else if tab === 'artifacts'}
        <ArtifactsModelsTab />
      {:else if tab === 'history'}
        <HistoryRunsTab />
      {:else if tab === 'system-health'}
        <SystemHealthTab />
      {:else if tab === 'settings'}
        <SettingsTab />
      {:else if tab === 'docs'}
        <DocsTab />
      {/if}
    </div>
  </div>
</div>

<style>
  .page {
    max-width: var(--content-max);
    margin: 0 auto;
    padding: 24px 28px 64px;
    display: flex;
    flex-direction: column;
    gap: 24px;
    width: 100%;
  }
  @media (max-width: 900px) {
    .page {
      padding: 16px 16px 48px;
      gap: 16px;
    }
  }
</style>
