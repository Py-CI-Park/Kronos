<script lang="ts">
  import { onMount } from 'svelte';
  import Sidebar from '$layout/Sidebar.svelte';
  import HeroStrip from '$layout/HeroStrip.svelte';
  import LiveTrainingTab from '$tabs/LiveTrainingTab.svelte';
  import ForecastWorkbenchTab from '$tabs/ForecastWorkbenchTab.svelte';
  import StomDiagnosticsTab from '$tabs/StomDiagnosticsTab.svelte';
  import ArtifactsModelsTab from '$tabs/ArtifactsModelsTab.svelte';
  import HistoryRunsTab from '$tabs/HistoryRunsTab.svelte';
  import SystemHealthTab from '$tabs/SystemHealthTab.svelte';
  import SettingsTab from '$tabs/SettingsTab.svelte';
  import { activeTab, lastUpdatedAt, refreshSeconds, trainingStatus } from '$lib/stores';
  import { applyThemeToDocument } from '$lib/theme';
  import { installPollingWatcher, startPolling } from '$lib/polling';

  onMount(() => {
    applyThemeToDocument();
    installPollingWatcher();
    startPolling();
  });

  let tab = $state('live-training');
  activeTab.subscribe((v) => (tab = v));
</script>

<div class="min-h-screen flex flex-col bg-bg text-text">
  <header class="flex items-center justify-between px-6 py-3 border-b border-border-muted"
    style="background: linear-gradient(135deg, #111827, #1d4ed8);">
    <h1 class="text-xl text-accent-subtle tracking-wide m-0">
      Kronos v2
      <span class="text-text-faint text-sm ml-2">P1.5 SPA</span>
    </h1>
    <div class="text-text-dim text-xs flex items-center gap-3">
      <span>기존 화면:</span>
      <a class="text-info hover:underline" href="/">예측 UI</a>
      <a class="text-info hover:underline" href="/stom">STOM 대시보드</a>
      <a class="text-info hover:underline" href="/training">학습 모니터</a>
    </div>
  </header>

  <div class="flex-1 flex flex-col md:flex-row overflow-hidden">
    <Sidebar />

    <main class="flex-1 overflow-y-auto p-4 md:p-6">
      {#if tab === 'live-training'}
        <HeroStrip />
        <LiveTrainingTab />
      {:else if tab === 'forecast'}
        <ForecastWorkbenchTab />
      {:else if tab === 'stom'}
        <StomDiagnosticsTab />
      {:else if tab === 'artifacts'}
        <ArtifactsModelsTab />
      {:else if tab === 'history'}
        <HistoryRunsTab />
      {:else if tab === 'system-health'}
        <SystemHealthTab />
      {:else if tab === 'settings'}
        <SettingsTab />
      {/if}
    </main>
  </div>

  <footer class="px-6 py-2 border-t border-border-muted text-text-faint text-xs flex flex-wrap gap-x-3 gap-y-1 items-center"
    style="background:#0b1120;">
    <span>Kronos v2 P1.5 SPA</span>
    <span>·</span>
    <span>마지막 갱신: {$lastUpdatedAt}</span>
    <span>·</span>
    <span>폴링: {$refreshSeconds}초</span>
    <span>·</span>
    <span>상태: { $trainingStatus?.status ?? '확인 중...' }</span>
  </footer>
</div>
