<script lang="ts">
  import { onDestroy, onMount, type Component } from 'svelte';
  import Sidebar from '$layout/Sidebar.svelte';
  import Header from '$layout/Header.svelte';
  import OpsStrip from '$layout/OpsStrip.svelte';
  import RightDetailRail from '$layout/RightDetailRail.svelte';
  import V4Shell from '$layout/V4Shell.svelte';
  import HeroStrip from '$layout/HeroStrip.svelte';
  import V51WorkspaceNav from '$layout/V51WorkspaceNav.svelte';
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
  import { installPollingWatcher, startPolling, stopPolling } from '$lib/polling';
  import { resolveRoute, routeForTab, syncTabFromLocation, v5WorkspaceForRoute, type DashboardRouteComponentKey, type V5WorkspaceDomain } from '$lib/routes';
  import { dashboardShell, DEFAULT_DASHBOARD_SHELL, initializeDashboardShell, type DashboardShell } from '$lib/shellMode';
  import { isLearningNowRouteLocation } from './v5/learningNow';
  import V6Shell from './v6shell/V6Shell.svelte';

  const LEGACY_COMPONENTS: Record<DashboardRouteComponentKey, Component> = {
    'mission-control': MissionControl, 'live-training': LiveTrainingTab, forecast: ForecastWorkbenchTab, stom: StomDiagnosticsTab,
    'daily-ohlcv': DailyOhlcvTab, 'daily-rl-guide': DailyRlGuideTab, rl: RLTradingTab, artifacts: ArtifactsModelsTab,
    history: HistoryRunsTab, 'system-health': SystemHealthTab, settings: SettingsTab, docs: DocsTab,
  };
  const V4_WRAPPERS: Record<DashboardRouteComponentKey, Component<any>> = {
    'mission-control': V4MissionControl, 'live-training': V4TrainingOps, forecast: V4ForecastStudio, stom: V4LegacyDomainFrame,
    'daily-ohlcv': V4DailyResearch, 'daily-rl-guide': V4LegacyDomainFrame, rl: V4RLEvidenceConsole, artifacts: V4ArtifactsWorkspace,
    history: V4RunsWorkspace, 'system-health': V4SystemOps, settings: V4AdminWorkspace, docs: V4AdminWorkspace,
  };
  const V4_WRAPPER_PROPS: Partial<Record<DashboardRouteComponentKey, Record<string, string>>> = {
    stom: { surface: 'diagnostics' }, 'daily-rl-guide': { surface: 'daily-guide' }, settings: { surface: 'settings' }, docs: { surface: 'docs' },
  };

  function v51WorkspaceDomainForTab(tabId: string, activeShell: DashboardShell): V5WorkspaceDomain | null {
    return activeShell === 'v5' ? v5WorkspaceForRoute(tabId) : null;
  }


  function shouldRenderLearningNowRoute(
    activeShell: DashboardShell,
    locationLike: Pick<Location, 'pathname' | 'search'> | null,
  ): boolean {
    return activeShell !== 'v6' && isLearningNowRouteLocation(locationLike);
  }

  function activateLearningNowRoute(): void {
    learningNowRouteActive = true;
    activeTab.set('learning-now');
    void ensureLearningNowTab();
  }

  let removePopstate: (() => void) | undefined;
  let disposePollingWatcher: (() => void) | undefined;

  function startLegacyPolling(): void {
    if (disposePollingWatcher) return;
    startPolling();
    disposePollingWatcher = installPollingWatcher();
  }

  function stopLegacyPolling(): void {
    disposePollingWatcher?.();
    disposePollingWatcher = undefined;
    stopPolling();
  }
  let LearningNowTab = $state<Component | null>(null);
  let learningNowLoading = $state(false);
  let learningNowLoadError = $state<string | null>(null);

  async function ensureLearningNowTab(): Promise<void> {
    if (LearningNowTab || learningNowLoading) return;
    learningNowLoading = true;
    learningNowLoadError = null;
    try {
      const module = await import('./v5/LearningNowTab.svelte');
      LearningNowTab = module.default;
    } catch {
      learningNowLoadError = 'Learning Now route component unavailable.';
    } finally {
      learningNowLoading = false;
    }
  }


  onMount(() => {
    const mountedShell = initializeDashboardShell();
    if (mountedShell === 'v6') {
      learningNowRouteActive = false;
    } else if (shouldRenderLearningNowRoute(mountedShell, window.location)) {
      activateLearningNowRoute();
    } else {
      learningNowRouteActive = false;
      routeUnavailable = syncTabFromLocation({ replaceAlias: true }) === null;
    }
    const handlePopstate = () => {
      const nextShell = initializeDashboardShell();
      if (nextShell === 'v6') {
        learningNowRouteActive = false;
      } else if (shouldRenderLearningNowRoute(nextShell, window.location)) {
        activateLearningNowRoute();
      } else {
        learningNowRouteActive = false;
        routeUnavailable = syncTabFromLocation() === null;
      }
    };
    window.addEventListener('popstate', handlePopstate);
    removePopstate = () => window.removeEventListener('popstate', handlePopstate);
    const unsubscribePollingShell = dashboardShell.subscribe((activeShell) => {
      if (activeShell === 'v6') {
        stopLegacyPolling();
      } else {
        startLegacyPolling();
      }
    });
    return () => {
      removePopstate?.();
      unsubscribePollingShell();
      stopLegacyPolling();
    };
  });

  const currentLocation = typeof window === 'undefined' ? null : window.location;
  const initialShell: DashboardShell = typeof window === 'undefined' ? DEFAULT_DASHBOARD_SHELL : initializeDashboardShell();
  const initialLearningNowRoute = shouldRenderLearningNowRoute(initialShell, currentLocation);
  const resolvedInitialTab = initialLearningNowRoute ? null : currentLocation ? resolveRoute(currentLocation)?.id : null;
  const initialRouteUnavailable = !initialLearningNowRoute && currentLocation !== null && resolvedInitialTab === null;
  const initialTab = initialLearningNowRoute ? 'learning-now' : (resolvedInitialTab ?? 'mission-control');
  if (initialLearningNowRoute || resolvedInitialTab) activeTab.set(initialTab);
  let tab = $state(initialTab);
  let learningNowRouteActive = $state(initialLearningNowRoute);
  let routeUnavailable = $state(initialRouteUnavailable);
  const unsubscribeActiveTab = activeTab.subscribe((v) => (tab = v));
  let shell = $state<DashboardShell>(initialShell);
  const unsubscribeDashboardShell = dashboardShell.subscribe((v) => (shell = v));
  let activeRoute = $derived(routeUnavailable ? null : routeForTab(tab));
  let v51WorkspaceDomain = $derived(v51WorkspaceDomainForTab(tab, shell));
  let collapsed = $state(false);
  const unsubscribeSidebarCollapsed = sidebarCollapsed.subscribe((v) => (collapsed = v));
  $effect(() => {
    if (tab !== 'learning-now' && learningNowRouteActive) {
      learningNowRouteActive = false;
    }
    if (routeUnavailable && tab !== initialTab) {
      routeUnavailable = false;
    }
  });
  $effect(() => {
    if (learningNowRouteActive) void ensureLearningNowTab();
  });


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
    {#if v51WorkspaceDomain}
      <V51WorkspaceNav domain={v51WorkspaceDomain} selectedRouteId={tab} />
    {/if}
    {#if activeRoute}
      {@const RouteComponent = LEGACY_COMPONENTS[activeRoute.componentKey]}
      {#if activeRoute.componentKey === 'live-training'}
        <HeroStrip />
      {/if}
      {#if shell === 'v4'}
        {@const V4Wrapper = V4_WRAPPERS[activeRoute.componentKey]}
        <V4Wrapper {...V4_WRAPPER_PROPS[activeRoute.componentKey]}>
          <RouteComponent />
        </V4Wrapper>
      {:else}
        <RouteComponent />
      {/if}
    {:else}
      <section class="lazy-loading" role="status" aria-live="polite">
        요청한 대시보드 경로를 사용할 수 없습니다.
      </section>
    {/if}
  </div>
{/snippet}

{#if learningNowRouteActive}
  <div class="app-shell" data-kronos-shell={shell} data-sidebar={collapsed ? 'collapsed' : 'expanded'}>
    <Sidebar />
    <div class="main">
      <Header />
      <OpsStrip />
      <div class="page" data-v5-learning-host>
        {#if LearningNowTab}
          <LearningNowTab />
        {:else}
          <section class="lazy-loading" role="status" aria-live="polite">
            {learningNowLoadError ?? 'Loading Learning Now route…'}
          </section>
        {/if}
      </div>
    </div>
    {#if shell === 'v5'}
      <RightDetailRail />
    {/if}
  </div>
{:else}
{#if shell === 'v4'}
  <V4Shell>
    {@render tabHost()}
  </V4Shell>
{:else if shell === 'v6'}
  <V6Shell />
{:else}
  <div class="app-shell" data-kronos-shell={shell} data-sidebar={collapsed ? 'collapsed' : 'expanded'}>
    <Sidebar />
    <div class="main">
      <Header />
      <OpsStrip />
      {@render tabHost()}
    </div>
    {#if shell === 'v5'}
      <RightDetailRail />
    {/if}
  </div>
{/if}
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
    min-width: 0;
    box-sizing: border-box;
  }
  .lazy-loading {
    border: 1px dashed var(--border);
    border-radius: 18px;
    padding: 24px;
    color: var(--muted);
    background: var(--surface-sunken);
  }
  @media (max-width: 900px) {
    .page {
      padding: 16px 16px 48px;
      gap: 16px;
    }
  }
</style>
