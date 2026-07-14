<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import Sidebar from '$layout/Sidebar.svelte';
  import Header from '$layout/Header.svelte';
  import OpsStrip from '$layout/OpsStrip.svelte';
  import V4Shell from '$layout/V4Shell.svelte';
  import HeroStrip from '$layout/HeroStrip.svelte';
  import MissionControl from '$tabs/MissionControl.svelte';
  import LiveTrainingTab from '$tabs/LiveTrainingTab.svelte';
  import ForecastWorkbenchTab from '$tabs/ForecastWorkbenchTab.svelte';
  import StomDiagnosticsTab from '$tabs/StomDiagnosticsTab.svelte';
  import DailyOhlcvTab from '$tabs/DailyOhlcvTab.svelte';
  import DailyRlGuideTab from '$tabs/DailyRlGuideTab.svelte';
  import RLTradingTab from '$tabs/RLTradingTab.svelte';
  import V4MissionControl from '$lib/../v4/home/V4MissionControl.svelte';
  import V4RLEvidenceConsole from '$lib/../v4/rl/V4RLEvidenceConsole.svelte';
  import V4ForecastStudio from '$lib/../v4/forecast/V4ForecastStudio.svelte';
  import V4DailyResearch from '$lib/../v4/daily/V4DailyResearch.svelte';
  import V4TrainingOps from '$lib/../v4/ops/V4TrainingOps.svelte';
  import V4ArtifactsWorkspace from '$lib/../v4/ops/V4ArtifactsWorkspace.svelte';
  import V4RunsWorkspace from '$lib/../v4/ops/V4RunsWorkspace.svelte';
  import V4SystemOps from '$lib/../v4/ops/V4SystemOps.svelte';
  import V4AdminWorkspace from '$lib/../v4/admin/V4AdminWorkspace.svelte';
  import V4LegacyDomainFrame from '$lib/../v4/qa/V4LegacyDomainFrame.svelte';
  import ArtifactsModelsTab from '$tabs/ArtifactsModelsTab.svelte';
  import HistoryRunsTab from '$tabs/HistoryRunsTab.svelte';
  import SystemHealthTab from '$tabs/SystemHealthTab.svelte';
  import SettingsTab from '$tabs/SettingsTab.svelte';
  import DocsTab from '$tabs/DocsTab.svelte';
  import { activeTab, sidebarCollapsed } from '$lib/stores';
  import { installPollingWatcher, startPolling } from '$lib/polling';
  import { resolveRoute, syncTabFromLocation } from '$lib/routes';
  import { dashboardShell, initializeDashboardShell, type DashboardShell } from '$lib/shellMode';

  let removePopstate: (() => void) | undefined;

  onMount(() => {
    syncTabFromLocation({ replaceAlias: true });
    const handlePopstate = () => {
      initializeDashboardShell();
      syncTabFromLocation();
    };
    window.addEventListener('popstate', handlePopstate);
    removePopstate = () => window.removeEventListener('popstate', handlePopstate);
    installPollingWatcher();
    startPolling();
    return () => {
      removePopstate?.();
    };
  });

  const initialTab = typeof window === 'undefined'
    ? 'mission-control'
    : (resolveRoute(window.location)?.id ?? 'mission-control');
  activeTab.set(initialTab);
  let tab = $state(initialTab);
  const unsubscribeActiveTab = activeTab.subscribe((v) => (tab = v));
  const initialShell: DashboardShell = typeof window === 'undefined' ? 'v3' : initializeDashboardShell();
  let shell = $state<DashboardShell>(initialShell);
  const unsubscribeDashboardShell = dashboardShell.subscribe((v) => (shell = v));
  let collapsed = $state(false);
  const unsubscribeSidebarCollapsed = sidebarCollapsed.subscribe((v) => (collapsed = v));

  onDestroy(() => {
    unsubscribeActiveTab();
    unsubscribeDashboardShell();
    unsubscribeSidebarCollapsed();
  });
</script>

{#snippet tabHost()}
  <div
    class="page"
    data-v3-tab-host={shell === 'v3' ? '' : undefined}
    data-v4-domain-host={shell === 'v4' ? '' : undefined}
  >
    {#if tab === 'mission-control'}
      {#if shell === 'v4'}
        <V4MissionControl />
      {:else}
        <MissionControl />
      {/if}
    {:else if tab === 'live-training'}
      <HeroStrip />
      {#if shell === 'v4'}
        <V4TrainingOps>
          <LiveTrainingTab />
        </V4TrainingOps>
      {:else}
        <LiveTrainingTab />
      {/if}
    {:else if tab === 'forecast'}
      {#if shell === 'v4'}
        <V4ForecastStudio>
          <ForecastWorkbenchTab />
        </V4ForecastStudio>
      {:else}
        <ForecastWorkbenchTab />
      {/if}
    {:else if tab === 'stom'}
      {#if shell === 'v4'}
        <V4LegacyDomainFrame surface="diagnostics">
          <StomDiagnosticsTab />
        </V4LegacyDomainFrame>
      {:else}
        <StomDiagnosticsTab />
      {/if}
    {:else if tab === 'rl'}
      {#if shell === 'v4'}
        <V4RLEvidenceConsole>
          <RLTradingTab />
        </V4RLEvidenceConsole>
      {:else}
        <RLTradingTab />
      {/if}
    {:else if tab === 'daily-ohlcv'}
      {#if shell === 'v4'}
        <V4DailyResearch>
          <DailyOhlcvTab />
        </V4DailyResearch>
      {:else}
        <DailyOhlcvTab />
      {/if}
    {:else if tab === 'daily-rl-guide'}
      {#if shell === 'v4'}
        <V4LegacyDomainFrame surface="daily-guide">
          <DailyRlGuideTab />
        </V4LegacyDomainFrame>
      {:else}
        <DailyRlGuideTab />
      {/if}
    {:else if tab === 'artifacts'}
      {#if shell === 'v4'}
        <V4ArtifactsWorkspace>
          <ArtifactsModelsTab />
        </V4ArtifactsWorkspace>
      {:else}
        <ArtifactsModelsTab />
      {/if}
    {:else if tab === 'history'}
      {#if shell === 'v4'}
        <V4RunsWorkspace>
          <HistoryRunsTab />
        </V4RunsWorkspace>
      {:else}
        <HistoryRunsTab />
      {/if}
    {:else if tab === 'system-health'}
      {#if shell === 'v4'}
        <V4SystemOps>
          <SystemHealthTab />
        </V4SystemOps>
      {:else}
        <SystemHealthTab />
      {/if}
    {:else if tab === 'settings'}
      {#if shell === 'v4'}
        <V4AdminWorkspace surface="settings">
          <SettingsTab />
        </V4AdminWorkspace>
      {:else}
        <SettingsTab />
      {/if}
    {:else if tab === 'docs'}
      {#if shell === 'v4'}
        <V4AdminWorkspace surface="docs">
          <DocsTab />
        </V4AdminWorkspace>
      {:else}
        <DocsTab />
      {/if}
    {/if}
  </div>
{/snippet}

{#if shell === 'v4'}
  <V4Shell>
    {@render tabHost()}
  </V4Shell>
{:else}
  <div class="app-shell" data-kronos-shell={shell} data-sidebar={collapsed ? 'collapsed' : 'expanded'}>
    <Sidebar />
    <div class="main">
      <Header />
      <OpsStrip />
      {@render tabHost()}
    </div>
  </div>
{/if}

<style>
  .page {
    max-width: var(--content-max);
    margin: 0 auto;
    padding: 24px 28px 64px;
    display: flex;
    flex-direction: column;
    gap: 24px;
    width: 100%;
    box-sizing: border-box;
  }
  @media (max-width: 900px) {
    .page {
      padding: 16px 16px 48px;
      gap: 16px;
    }
  }
</style>
