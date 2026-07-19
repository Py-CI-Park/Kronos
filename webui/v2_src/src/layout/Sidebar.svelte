<script lang="ts">
  import { tick } from 'svelte';
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
  let versionHistoryDialog = $state<HTMLDivElement | null>(null);
  let versionHistoryTrigger = $state<HTMLButtonElement | null>(null);

  $effect(() => {
    if (shell !== 'v5') versionHistoryOpen = false;
  });

  function itemRouteId(item: NavItem): string | null {
    return item.routeId ?? item.id ?? null;
  }

  function itemIsActive(item: NavItem): boolean {
    const routeId = itemRouteId(item);
    return (routeId != null && current === routeId) || item.activeRouteIds?.includes(current) === true;
  }

  function closeVersionHistory(): void {
    const trigger = versionHistoryTrigger;
    versionHistoryOpen = false;
    void tick().then(() => trigger?.focus());
  }

  function toggleVersionHistory(trigger?: HTMLButtonElement): void {
    if (versionHistoryOpen) {
      closeVersionHistory();
      return;
    }
    versionHistoryTrigger = trigger ?? null;
    versionHistoryOpen = true;
    if (collapsed) sidebarCollapsed.set(false);
    void tick().then(() => versionHistoryDialog?.focus());
  }

  function handleVersionHistoryKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      closeVersionHistory();
      return;
    }
    if (event.key !== 'Tab' || !versionHistoryDialog) return;
    const focusable = Array.from(
      versionHistoryDialog.querySelectorAll<HTMLElement>(
        'button:not([disabled]):not([tabindex="-1"]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    );
    if (focusable.length === 0) {
      event.preventDefault();
      versionHistoryDialog.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function pick(item: NavItem, trigger?: HTMLButtonElement): void {
    if (item.action === 'version-history') {
      toggleVersionHistory(trigger);
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
            onclick={(event) => toggleVersionHistory(event.currentTarget)}
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
            onclick={(event) => pick(item, event.currentTarget)}
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

{#if shell === 'v5' && versionHistoryOpen}
  <div class="version-history-layer" data-v51-version-history-layer>
    <div
      id="v51-version-history-panel"
      class="version-history"
      role="dialog"
      aria-modal="true"
      aria-labelledby="v51-version-history-title"
      tabindex="-1"
      bind:this={versionHistoryDialog}
      onkeydown={handleVersionHistoryKeydown}
      data-v51-version-history
    >
      <div class="version-history-header">
        <div>
          <p class="version-history-kicker">V5 / V5.1 governance</p>
          <h2 id="v51-version-history-title">Version History</h2>
        </div>
        <button
          type="button"
          class="version-history-close"
          aria-label="Close version history"
          onclick={closeVersionHistory}
        >
          Close
        </button>
      </div>
      <div class="version-history-list">
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
      </div>
    </div>
    <button
      type="button"
      class="version-history-backdrop"
      aria-label="Close version history"
      tabindex="-1"
      onclick={closeVersionHistory}
    ></button>
  </div>
{/if}

<style>
  .sidebar-command {
    padding: 12px 20px 0;
  }
  .nav-item--command {
    width: 100%;
    border: 1px solid var(--border-faint);
    background: var(--surface-sunken);
  }
  :global(.sidebar[data-kronos-shell="v5"]) .brand {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
  :global(.sidebar[data-kronos-shell="v5"][data-sidebar-collapsed="true"]) .brand {
    align-items: center;
    padding-inline: 0;
  }
  :global(.sidebar[data-kronos-shell="v5"]) .brand-text {
    min-width: 0;
    width: 100%;
    max-width: 100%;
  }
  :global(.sidebar[data-kronos-shell="v5"]) .brand-name {
    color: var(--fg-strong);
    font: 800 clamp(18px, 1.2vw, 21px)/1.06 var(--font-display);
    letter-spacing: -0.025em;
    white-space: normal;
    overflow-wrap: break-word;
  }
  .brand-version {
    margin-top: 5px;
    color: var(--fg);
    font: 600 11px/1.3 var(--font-mono);
  }
  .brand-tag--subtitle {
    margin-top: 5px;
    font-family: var(--font-display);
    font-size: 12px;
    letter-spacing: 0;
  }
  .version-toggle {
    align-self: flex-start;
    margin-top: 9px;
    padding: 5px 9px;
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
  .version-toggle:focus-visible,
  .version-history-close:focus-visible,
  .version-history-backdrop:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 3px;
  }
  .version-history-layer {
    position: fixed;
    inset: 0;
    z-index: 80;
    display: grid;
    place-items: center;
    padding: clamp(16px, 4vw, 48px);
  }
  .version-history-backdrop {
    position: fixed;
    inset: 0;
    z-index: 0;
    background: color-mix(in oklab, var(--fg-strong) 34%, transparent);
  }
  .version-history {
    position: relative;
    z-index: 1;
    width: min(760px, calc(100vw - 32px));
    max-height: min(78dvh, 720px);
    overflow: auto;
    padding: clamp(18px, 3vw, 26px);
    border: 1px solid var(--border);
    border-radius: 22px;
    background: var(--surface-elev);
    color: var(--fg);
    box-shadow: var(--shadow-lg), var(--card-highlight);
  }
  .version-history-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 18px;
  }
  .version-history-kicker {
    margin-bottom: 6px;
    color: var(--muted);
    font: 700 11px/1.1 var(--font-display);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .version-history-header h2 {
    color: var(--fg-strong);
    font: 800 clamp(24px, 4vw, 32px)/1.1 var(--font-display);
    letter-spacing: -0.03em;
  }
  .version-history-close {
    flex: 0 0 auto;
    min-height: 36px;
    padding: 8px 12px;
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    background: var(--surface-sunken);
    color: var(--fg-strong);
    font: 700 12px/1 var(--font-display);
  }
  .version-history-close:hover {
    border-color: var(--border-strong);
    background: var(--surface-raised);
    color: var(--accent-strong);
  }
  .version-entry {
    padding: 16px 0;
    border-top: 1px solid var(--border-faint);
  }
  .version-entry:first-child {
    padding-top: 0;
    border-top: 0;
  }
  .version-entry:last-child {
    padding-bottom: 0;
  }
  .version-entry-head {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
    color: var(--fg-strong);
    font: 700 14px/1.2 var(--font-display);
  }
  .version-entry-head span {
    color: var(--muted);
    font-family: var(--font-mono);
  }
  .version-entry-facts {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px 14px;
    margin: 0;
    font-size: 12px;
    line-height: 1.45;
  }
  .version-entry-facts div {
    display: grid;
    gap: 3px;
    min-width: 0;
  }
  .version-entry-facts dt {
    color: var(--dim);
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .version-entry-facts dd {
    margin: 0;
    color: var(--muted);
    overflow-wrap: anywhere;
  }
  @media (max-width: 640px) {
    .version-history {
      width: min(100%, calc(100vw - 24px));
      padding: 16px;
      border-radius: 18px;
    }
    .version-history-header {
      flex-direction: column;
      align-items: stretch;
    }
    .version-history-close {
      align-self: flex-start;
    }
    .version-entry-head {
      flex-direction: column;
    }
    .version-entry-facts {
      grid-template-columns: 1fr;
    }
  }
</style>
