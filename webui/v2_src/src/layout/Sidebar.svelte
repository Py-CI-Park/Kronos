<script lang="ts">
  import { activeTab, sidebarCollapsed, sidebarMobileOpen, trainingStatus, metricsLatest } from '$lib/stores';
  import { ICONS } from '$lib/icons';
  import { fmt } from '$lib/format';
  import {
    V51_NAV_GROUPS,
    V51_SHELL_BRAND,
    V51_VERSION_HISTORY,
    navigateToTab,
    type V51NavGroup,
    type V51NavItem,
  } from '$lib/routes';
  import { dashboardShell, type DashboardShell } from '$lib/shellMode';
  import { requestCommandPalette } from '$lib/commandPalette';

  type NavItem = V51NavItem;
  type NavGroup = V51NavGroup;

  // v3 "AI Quant" technique-based IA (code-grounded):
  //   커맨드 → Kronos 예측(독립 파운데이션) → 트레이딩 리서치(일봉 D0–D9 ⊃ D4 RL·종가매매,
  //   + 인트라데이 커맨드센터) → 라이브·시스템. Kronos와 RL은 독립 축(데이터만 공유).
  const v3Groups: NavGroup[] = [
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
        {
          id: 'daily-ohlcv',
          label: 'Daily OHLCV',
          icon: 'pulse',
          badge: '연구',
          // daily-rl-guide는 daily-ohlcv 라인의 하위(자식) 항목으로 귀속.
          children: [
            { id: 'daily-rl-guide', label: '일봉 RL 설명서', icon: 'file', badge: null },
          ],
        },
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

  const v4Groups: NavGroup[] = [
    {
      label: 'Home / Mission Control',
      items: [
        { id: 'mission-control', label: 'Mission Control', icon: 'pulse', badge: null },
      ],
    },
    {
      label: 'Forecast',
      items: [
        { id: 'forecast', label: '예측 워크벤치', icon: 'wand', badge: null },
        { id: 'stom', label: '예측 진단', icon: 'pulse', badge: null },
      ],
    },
    {
      label: 'Daily Research',
      items: [
        {
          id: 'daily-ohlcv',
          label: 'Daily OHLCV',
          icon: 'pulse',
          badge: '연구',
          // daily-rl-guide는 daily-ohlcv 라인의 하위(자식) 항목으로 귀속.
          children: [
            { id: 'daily-rl-guide', label: '일봉 RL 설명서', icon: 'file', badge: null },
          ],
        },
      ],
    },
    {
      label: 'RL Evidence',
      items: [
        { id: 'rl', label: 'Trading Command Center', icon: 'rocket', badge: 'RL' },
      ],
    },
    {
      label: 'Operations',
      items: [
        { id: 'live-training', label: '실시간 학습', icon: 'activity', badge: 'LIVE', status: 'live' },
        { id: 'system-health', label: '시스템 상태', icon: 'cpu', badge: null },
        { id: 'artifacts', label: '아티팩트 & 모델', icon: 'package', badge: null },
        { id: 'history', label: '기록 & 런', icon: 'history', badge: null },
      ],
    },
    {
      label: 'Admin & Docs',
      items: [
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

  let shell = $state<DashboardShell>('v3');
  dashboardShell.subscribe((v) => (shell = v));
  let navGroups = $derived<readonly NavGroup[]>(shell === 'v5' ? V51_NAV_GROUPS : shell === 'v4' ? v4Groups : v3Groups);
  let versionHistoryOpen = $state(false);

  $effect(() => {
    if (shell !== 'v5') versionHistoryOpen = false;
  });

  function itemRouteId(item: NavItem): string | null {
    return item.routeId ?? item.id ?? null;
  }

  function itemIsActive(item: NavItem): boolean {
    const routeId = itemRouteId(item);
    return routeId != null && current === routeId;
  }

  function toggleVersionHistory(): void {
    versionHistoryOpen = !versionHistoryOpen;
    if (versionHistoryOpen && collapsed) sidebarCollapsed.set(false);
  }

  function pick(item: NavItem): void {
    if (item.action === 'version-history') {
      toggleVersionHistory();
      return;
    }
    const routeId = itemRouteId(item);
    if (!routeId) return;
    navigateToTab(routeId);
    sidebarMobileOpen.set(false);
  }
</script>

<aside
  id="kronos-sidebar"
  class="sidebar"
  data-sidebar-collapsed={collapsed}
  data-mobile-open={mobileOpen}
  data-kronos-shell={shell}
  data-v4-shell={shell === 'v4' ? 'sidebar' : undefined}
>
  <div class="brand">
    <div
      class="brand-mark"
      aria-label={shell === 'v5' ? `${V51_SHELL_BRAND.name} — ${V51_SHELL_BRAND.subtitle}` : 'Kronos 대시보드'}
      title={collapsed ? (shell === 'v5' ? `${V51_SHELL_BRAND.name} · ${V51_SHELL_BRAND.displayVersion}` : 'Kronos 대시보드') : undefined}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">{@html ICONS.flame}</svg>
    </div>
    {#if !collapsed}
      <div class="brand-text">
        {#if shell === 'v5'}
          <span class="brand-name">{V51_SHELL_BRAND.name}</span>
          <span class="brand-tag brand-tag--subtitle">{V51_SHELL_BRAND.subtitle}</span>
          <span class="brand-version">{V51_SHELL_BRAND.displayVersion}</span>
          <button
            type="button"
            class="version-toggle"
            aria-expanded={versionHistoryOpen}
            aria-controls="v51-version-history-panel"
            onclick={toggleVersionHistory}
          >
            Version History
          </button>
        {:else}
          <span class="brand-name">Kronos 대시보드</span>
          <span class="brand-tag">official · operations</span>
        {/if}
      </div>
    {/if}
  </div>

  {#if shell === 'v4'}
    <div class="sidebar-command">
      <button
        type="button"
        class="nav-item nav-item--command"
        data-v4-command-trigger
        aria-label="명령 팔레트 열기"
        title="명령 팔레트 열기 (Ctrl/Cmd+K)"
        onclick={requestCommandPalette}
      >
        <span class="nav-icon">
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">{@html ICONS.grid}</svg>
        </span>
        {#if !collapsed}
          <span class="nav-label">Command Palette</span>
          <span class="nav-badge">Ctrl/Cmd+K</span>
        {/if}
      </button>
    </div>
  {/if}

  {#each navGroups as g}
    <div class="sidebar-section">
      {#if !collapsed}
        <div class="sidebar-section-label">{g.label}</div>
      {/if}
      <div class="nav-list">
        {#each g.items as item}
          <button
            type="button"
            class="nav-item"
            data-tab={itemRouteId(item) ?? undefined}
            data-nav-action={item.action ?? undefined}
            data-active={itemIsActive(item) ? 'true' : 'false'}
            data-status={item.status ?? ''}
            aria-current={itemIsActive(item) ? 'page' : undefined}
            aria-expanded={item.action === 'version-history' ? versionHistoryOpen : undefined}
            aria-controls={item.action === 'version-history' ? 'v51-version-history-panel' : undefined}
            aria-label={collapsed ? item.label : undefined}
            onclick={() => pick(item)}
            title={collapsed ? item.label : item.action === 'version-history' ? 'Open V5/V5.1 version history' : undefined}
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
          {#if !collapsed && item.children}
            {#each item.children as child}
              <button
                type="button"
                class="nav-item nav-item--child"
                data-tab={itemRouteId(child) ?? undefined}
                data-nav-child="true"
                data-active={itemIsActive(child) ? 'true' : 'false'}
                data-status={child.status ?? ''}
                aria-current={itemIsActive(child) ? 'page' : undefined}
                aria-label={collapsed ? child.label : undefined}
                onclick={() => pick(child)}
                title={collapsed ? child.label : undefined}
              >
                <span class="nav-icon">
                  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">{@html ICONS[child.icon]}</svg>
                </span>
                <span class="nav-label">{child.label}</span>
                {#if child.badge}
                  <span class="nav-badge">{child.badge}</span>
                {/if}
              </button>
            {/each}
          {/if}
        {/each}
      </div>
    </div>
  {/each}

  {#if shell === 'v5' && versionHistoryOpen && !collapsed}
    <section
      id="v51-version-history-panel"
      class="version-history"
      aria-label="Kronos version history"
      data-v51-version-history
    >
      <div class="version-history-title">Version History</div>
      {#each V51_VERSION_HISTORY as entry}
        <article class="version-entry">
          <div class="version-entry-head">
            <strong>{entry.version}</strong>
            <span>{entry.date}</span>
          </div>
          <dl class="version-entry-facts">
            <div><dt>Commit</dt><dd>{entry.commitSha}</dd></div>
            <div><dt>Tag</dt><dd>{entry.releaseTag}</dd></div>
            <div><dt>Changes</dt><dd>{entry.changes}</dd></div>
            <div><dt>Validation</dt><dd>{entry.validation}</dd></div>
            <div><dt>Default</dt><dd>{entry.defaultUi}</dd></div>
            <div><dt>Rollback</dt><dd>{entry.rollbackTarget}</dd></div>
          </dl>
        </article>
      {/each}
    </section>
  {/if}

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

<style>
  .sidebar-command {
    padding: 12px 20px 0;
  }
  .nav-item--command {
    width: 100%;
    border: 1px solid var(--border-faint);
    background: var(--surface-sunken);
  }
  .brand-version {
    margin-top: 4px;
    color: var(--fg);
    font: 600 11px/1.3 var(--font-mono);
  }
  .brand-tag--subtitle {
    font-family: var(--font-display);
    letter-spacing: 0;
  }
  .version-toggle {
    align-self: flex-start;
    margin-top: 8px;
    padding: 4px 8px;
    border: 1px solid var(--border-faint);
    border-radius: var(--r-pill);
    background: var(--surface-sunken);
    color: var(--fg);
    font: 600 11px/1 var(--font-display);
  }
  .version-toggle:hover {
    border-color: var(--border);
    color: var(--accent-strong);
  }
  .version-history {
    margin: 8px 20px 12px;
    padding: 12px;
    border: 1px solid var(--border-faint);
    border-radius: var(--r-md);
    background: var(--surface-sunken);
    color: var(--fg);
    overflow: auto;
    max-height: min(420px, 45vh);
  }
  .version-history-title {
    margin-bottom: 10px;
    font: 700 12px/1 var(--font-display);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--fg-strong);
  }
  .version-entry + .version-entry {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--border-faint);
  }
  .version-entry-head {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 8px;
    font: 600 12px/1.2 var(--font-display);
  }
  .version-entry-head span {
    color: var(--muted);
    font-family: var(--font-mono);
  }
  .version-entry-facts {
    display: grid;
    gap: 6px;
    margin: 0;
    font-size: 11px;
    line-height: 1.35;
  }
  .version-entry-facts div {
    display: grid;
    gap: 2px;
  }
  .version-entry-facts dt {
    color: var(--dim);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .version-entry-facts dd {
    margin: 0;
    color: var(--muted);
  }
</style>
