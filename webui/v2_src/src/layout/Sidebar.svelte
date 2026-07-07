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

  // v3 "AI Quant" technique-based IA (code-grounded):
  //   커맨드 → Kronos 예측(독립 파운데이션) → 트레이딩 리서치(일봉 D0–D9 ⊃ D4 RL·종가매매,
  //   + 인트라데이 커맨드센터) → 라이브·시스템. Kronos와 RL은 독립 축(데이터만 공유).
  const groups: NavGroup[] = [
    {
      label: '커맨드',
      items: [
        { id: 'mission-control', label: 'Mission Control', icon: 'pulse', badge: null },
      ],
    },
    {
      label: 'Kronos 예측',
      items: [
        { id: 'forecast', label: '예측 워크벤치', icon: 'wand', badge: null },
        { id: 'stom', label: '예측 진단', icon: 'pulse', badge: null },
      ],
    },
    {
      label: '트레이딩 리서치',
      items: [
        { id: 'daily-ohlcv', label: 'Daily OHLCV', icon: 'pulse', badge: '연구' },
        { id: 'daily-rl-guide', label: '일봉 RL 설명서', icon: 'file', badge: null },
        { id: 'rl', label: 'Trading Command Center', icon: 'rocket', badge: 'RL' },
      ],
    },
    {
      label: '라이브 · 시스템',
      items: [
        { id: 'live-training', label: '실시간 학습', icon: 'activity', badge: 'LIVE', status: 'live' },
        { id: 'system-health', label: '시스템 상태', icon: 'cpu', badge: null },
        { id: 'artifacts', label: '아티팩트 & 모델', icon: 'package', badge: null },
        { id: 'history', label: '기록 & 런', icon: 'history', badge: null },
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
