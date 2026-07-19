<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import {
    activeTab,
    trainingStatus,
    lastUpdatedAt,
    sidebarCollapsed,
    sidebarMobileOpen,
    theme,
    toggleTheme,
  } from '$lib/stores';
  import { ICONS } from '$lib/icons';
  import { fmt } from '$lib/format';
  import { V51_DEFAULT_POLICY, V51_SHELL_BRAND, routeLabelForShell } from '$lib/routes';
  import { dashboardShell, type DashboardShell } from '$lib/shellMode';
  import { requestCommandPalette } from '$lib/commandPalette';
  // Header route label markers: Daily OHLCV · 일봉 RL 설명서 · RL Trading

  const MOBILE_SIDEBAR_QUERY = '(max-width: 900px)';
  const SIDEBAR_ID = 'kronos-sidebar';

  let tab = $state('live-training');
  activeTab.subscribe((v) => (tab = v));
  let status = $state<any>(null);
  trainingStatus.subscribe((v) => (status = v));
  let last = $state('-');
  lastUpdatedAt.subscribe((v) => (last = v));
  let currentTheme = $state<'light' | 'dark'>('light');
  theme.subscribe((v) => (currentTheme = v));
  let shell = $state<DashboardShell>('v3');
  dashboardShell.subscribe((v) => (shell = v));
  let sidebarIsCollapsed = $state(false);
  sidebarCollapsed.subscribe((v) => (sidebarIsCollapsed = v));
  let sidebarIsMobileOpen = $state(false);
  sidebarMobileOpen.subscribe((v) => (sidebarIsMobileOpen = v));
  let sidebarUsesMobileState = $state(false);
  let sidebarViewportQuery: MediaQueryList | undefined;

  let now = $state(fmt.kstTime(Date.now()));
  let timer: number | undefined;

  function setSidebarViewport(matches: boolean): void {
    sidebarUsesMobileState = matches;
  }

  function syncSidebarViewport(event: MediaQueryListEvent): void {
    setSidebarViewport(event.matches);
  }

  onMount(() => {
    timer = window.setInterval(() => (now = fmt.kstTime(Date.now())), 1000);
    sidebarViewportQuery = window.matchMedia(MOBILE_SIDEBAR_QUERY);
    setSidebarViewport(sidebarViewportQuery.matches);
    sidebarViewportQuery.addEventListener('change', syncSidebarViewport);
  });
  onDestroy(() => {
    if (timer != null) clearInterval(timer);
    sidebarViewportQuery?.removeEventListener('change', syncSidebarViewport);
  });

  function sidebarControlExpanded(): boolean {
    return sidebarUsesMobileState ? sidebarIsMobileOpen : !sidebarIsCollapsed;
  }

  function sidebarToggleLabel(): string {
    if (shell !== 'v5') return '사이드바 토글';
    if (sidebarUsesMobileState) {
      return sidebarIsMobileOpen ? 'Close navigation sidebar' : 'Open navigation sidebar';
    }
    return sidebarIsCollapsed ? 'Expand navigation sidebar' : 'Collapse navigation sidebar';
  }

  function toggleSidebar(): void {
    const useMobileState = window.matchMedia(MOBILE_SIDEBAR_QUERY).matches;
    sidebarUsesMobileState = useMobileState;
    if (useMobileState) {
      sidebarMobileOpen.update((v) => !v);
    } else {
      sidebarCollapsed.update((v) => !v);
    }
  }
</script>

<header class="header" data-kronos-shell={shell} data-v4-shell={shell === 'v4' ? 'header' : undefined}>
  <button
    type="button"
    class="btn icon ghost"
    aria-label={sidebarToggleLabel()}
    aria-expanded={sidebarControlExpanded()}
    aria-controls={SIDEBAR_ID}
    onclick={toggleSidebar}
    title={sidebarToggleLabel()}
  >
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">{@html ICONS.menu}</svg>
  </button>

  <div class="crumb">
    <span class="crumb-root">Kronos</span>
    <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" class="crumb-sep">{@html ICONS.chevron_right}</svg>
    <span class="crumb-current">{routeLabelForShell(tab, shell)}</span>
  </div>

  <div class="header-meta">
    {#if status?.readiness?.level}
      <span
        class="signal"
        data-level={status.readiness.level === 'ready' ? 'live' : status.readiness.level === 'training' ? 'live' : 'waiting'}
      >
        <span class="light"></span>
        <span>{status.readiness.label ?? status.readiness.level}</span>
      </span>
    {/if}
    {#if shell === 'v4'}
      <span class="header-stat text-caption" data-v4-status-marker title="V4 shell opt-in status">
        V4 opt-in · read-only
      </span>
    {/if}
    {#if shell === 'v5'}
      <span class="header-stat text-caption" data-v51-version-marker title={`${V51_SHELL_BRAND.subtitle}; ${V51_DEFAULT_POLICY}`}>
        {V51_SHELL_BRAND.displayVersion}
      </span>
    {/if}
  </div>

  <div class="header-actions">
    <span class="header-stat" title="현재 시각 (KST)">
      <span class="header-stat-dot live"></span>
      <span class="text-mono tnum">{now}</span>
    </span>
    <span class="header-stat text-caption" title="마지막 갱신">
      갱신 <span class="text-mono">{last}</span>
    </span>
    {#if shell === 'v4'}
      <button
        type="button"
        class="btn ghost command-trigger"
        data-v4-command-trigger
        onclick={requestCommandPalette}
        aria-label="명령 팔레트 열기"
        title="명령 팔레트 열기 (Ctrl/Cmd+K)"
      >
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">{@html ICONS.grid}</svg>
        <span class="command-label">Command</span>
        <span class="shortcut">Ctrl/Cmd+K</span>
      </button>
    {/if}
    <button
      type="button"
      class="btn icon ghost"
      data-theme-toggle
      onclick={toggleTheme}
      aria-label="테마 토글"
      title="라이트/다크 전환"
    >
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" style:display={currentTheme === 'dark' ? 'none' : ''}>
        {@html ICONS.sun}
      </svg>
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" style:display={currentTheme === 'dark' ? '' : 'none'}>
        {@html ICONS.moon}
      </svg>
    </button>
  </div>
</header>

<style>
  .crumb {
    display: flex;
    align-items: center;
    gap: 8px;
    font: 600 15px/1.3 var(--font-display);
    color: var(--fg);
    flex: 1;
    min-width: 0;
  }
  .crumb-root {
    color: var(--muted);
    font-weight: 500;
  }
  .crumb-sep {
    color: var(--faint);
    flex-shrink: 0;
  }
  .crumb-current {
    color: var(--fg-strong);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .header-meta {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: auto;
  }
  .header-stat {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: var(--r-pill);
    background: var(--surface-sunken);
    color: var(--fg);
    font-size: 12px;
  }
  .header-stat-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--muted);
  }
  .header-stat-dot.live {
    background: var(--success);
    box-shadow: 0 0 6px var(--success);
  }
  .command-trigger {
    gap: 8px;
    padding: 0 10px;
    min-width: auto;
  }
  .shortcut {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--dim);
  }
  @media (max-width: 640px) {
    .header-meta,
    .header-stat,
    .crumb-root,
    .crumb-sep,
    .command-label,
    .shortcut {
      display: none;
    }
    .command-trigger {
      min-width: 36px;
      padding: 0;
      justify-content: center;
    }
  }
</style>
