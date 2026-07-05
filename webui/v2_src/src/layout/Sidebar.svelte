<script lang="ts">
  import { activeTab, sidebarCollapsed, sidebarMobileOpen, trainingStatus, metricsLatest } from '$lib/stores';
  import { ICONS, type IconName } from '$lib/icons';
  import { fmt } from '$lib/format';
  import { navigateToTab } from '$lib/routes';

  interface NavItem {
    id: string;
    label: string;
    icon: IconName;
    badge?: string | null;
    status?: 'live' | 'warn' | null;
  }

  interface NavGroup {
    label: string;
    items: NavItem[];
  }

  // Technique-based IA: command → forecast (Kronos foundation) → daily research
  // → RL → outputs/system. Grouping mirrors the approved redesign draft.
  const groups: NavGroup[] = [
    {
      label: '커맨드',
      items: [
        { id: 'mission-control', label: 'Mission Control', icon: 'pulse', badge: null },
      ],
    },
    {
      label: '파운데이션 · 예측',
      items: [
        { id: 'live-training', label: '실시간 학습', icon: 'activity', badge: 'LIVE', status: 'live' },
        { id: 'forecast', label: '예측 워크벤치', icon: 'wand', badge: null },
        { id: 'stom', label: '예측 진단', icon: 'pulse', badge: null },
      ],
    },
    {
      label: '일봉 연구',
      items: [
        { id: 'daily-ohlcv', label: 'Daily OHLCV', icon: 'pulse', badge: '연구' },
      ],
    },
    {
      label: '강화학습',
      items: [
        { id: 'rl', label: 'Trading Command Center', icon: 'rocket', badge: 'RL' },
      ],
    },
    {
      label: '산출물 · 시스템',
      items: [
        { id: 'artifacts', label: '아티팩트 & 모델', icon: 'package', badge: null },
        { id: 'history', label: '기록 & 런', icon: 'history', badge: null },
        { id: 'system-health', label: '시스템 상태', icon: 'cpu', badge: null },
        { id: 'settings', label: '설정', icon: 'settings', badge: null },
        { id: 'docs', label: '문서 · Wiki', icon: 'file', badge: null },
      ],
    },
  ];

  let current = $state('live-training');
  activeTab.subscribe((v) => (current = v));

  let collapsed = $state(false);
  sidebarCollapsed.subscribe((v) => (collapsed = v));

  let mobileOpen = $state(false);
  sidebarMobileOpen.subscribe((v) => (mobileOpen = v));

  let status = $state<any>(null);
  trainingStatus.subscribe((v) => (status = v));

  let m = $state<any>({});
  metricsLatest.subscribe((v) => (m = v));

  function pick(id: string) {
    navigateToTab(id);
    sidebarMobileOpen.set(false);
  }
</script>

<aside class="sidebar" data-sidebar-collapsed={collapsed} data-mobile-open={mobileOpen}>
  <div class="brand">
    <div class="brand-mark">
      <svg viewBox="0 0 24 24" aria-hidden="true">{@html ICONS.flame}</svg>
    </div>
    {#if !collapsed}
      <div class="brand-text">
        <span class="brand-name">Kronos 대시보드</span>
        <span class="brand-tag">official · operations</span>
      </div>
    {/if}
  </div>

  {#each groups as g}
    <div class="sidebar-section">
      {#if !collapsed}
        <div class="sidebar-section-label">{g.label}</div>
      {/if}
      <div class="nav-list">
        {#each g.items as item}
          <button
            type="button"
            class="nav-item"
            data-tab={item.id}
            data-active={current === item.id ? 'true' : 'false'}
            data-status={item.status ?? ''}
            aria-current={current === item.id ? 'page' : undefined}
            onclick={() => pick(item.id)}
            title={collapsed ? item.label : undefined}
          >
            <span class="nav-icon">
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">{@html ICONS[item.icon]}</svg>
            </span>
            {#if !collapsed}
              <span class="nav-label">{item.label}</span>
              {#if item.badge}
                <span class="nav-badge">{item.badge}</span>
              {/if}
            {/if}
          </button>
        {/each}
      </div>
    </div>
  {/each}

  {#if !collapsed}
    <div class="sidebar-footer">
      <div class="run-card">
        <div class="run-card-row">
          <span class="signal" data-level={status?.readiness?.level === 'ready' ? 'live' : status?.readiness?.level === 'training' ? 'live' : 'waiting'}>
            <span class="light"></span>
            <span>{status?.status ?? '확인 중'}</span>
          </span>
        </div>
        {#if m.runName}
          <div class="run-name" title={m.runName}>{m.runName}</div>
        {/if}
        <div class="run-meta">
          {#if status?.latest_stage?.train_stage}
            <span>{status.latest_stage.train_stage}</span>
          {/if}
          {#if status?.latest_stage?.overall_percent != null}
            <span>{fmt.pct(status.latest_stage.overall_percent, 1)}</span>
          {/if}
        </div>
      </div>
    </div>
  {/if}
</aside>
