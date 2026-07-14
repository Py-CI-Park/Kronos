<script lang="ts">
  import { onDestroy, type Snippet } from 'svelte';
  import Sidebar from '$layout/Sidebar.svelte';
  import Header from '$layout/Header.svelte';
  import OpsStrip from '$layout/OpsStrip.svelte';
  import CommandPalette from '$layout/CommandPalette.svelte';
  import { sidebarCollapsed } from '$lib/stores';
  import { dashboardShell, type DashboardShell } from '$lib/shellMode';

  interface Props {
    children: Snippet;
  }

  let { children }: Props = $props();

  let collapsed = $state(false);
  const unsubscribeSidebarCollapsed = sidebarCollapsed.subscribe((v) => (collapsed = v));

  let shell = $state<DashboardShell>('v4');
  const unsubscribeDashboardShell = dashboardShell.subscribe((v) => (shell = v));

  onDestroy(() => {
    unsubscribeSidebarCollapsed();
    unsubscribeDashboardShell();
  });
</script>

<div
  class="app-shell v4-shell"
  data-kronos-shell={shell}
  data-v4-shell
  data-sidebar={collapsed ? 'collapsed' : 'expanded'}
>
  <Sidebar />
  <div class="main v4-main">
    <Header />
    <OpsStrip />
    <section class="v4-foundation" aria-label="V4 shell preview">
      <div>
        <span class="v4-eyebrow">Paper Ops Ledger foundation</span>
        <h1>V4 opt-in shell</h1>
        <p>Read-only command surface and dense domain navigation; existing tabs remain unchanged below.</p>
      </div>
      <span class="v4-badge" data-v4-opt-in-badge>V4 opt-in · read-only</span>
    </section>
    {@render children()}
  </div>
  <CommandPalette />
</div>

<style>
  .v4-shell {
    background:
      radial-gradient(circle at top left, color-mix(in oklab, var(--accent) 14%, transparent), transparent 34rem),
      var(--bg);
  }

  .v4-main {
    min-height: 100vh;
  }

  .v4-foundation {
    max-width: var(--content-max);
    width: calc(100% - 56px);
    margin: 24px auto 0;
    padding: 18px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    border: 1px solid var(--border-faint);
    border-radius: 22px;
    background: color-mix(in oklab, var(--surface) 88%, transparent);
    box-shadow: var(--shadow-sm);
  }

  .v4-eyebrow {
    color: var(--accent-strong);
    font: 700 11px/1.2 var(--font-mono);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .v4-foundation h1 {
    margin: 6px 0 4px;
    color: var(--fg-strong);
    font: 750 clamp(22px, 3vw, 32px)/1 var(--font-display);
    letter-spacing: -0.04em;
  }

  .v4-foundation p {
    margin: 0;
    color: var(--muted);
    font-size: 13px;
    line-height: 1.5;
  }

  .v4-badge {
    flex: 0 0 auto;
    display: inline-flex;
    align-items: center;
    border: 1px solid color-mix(in oklab, var(--accent) 40%, var(--border));
    border-radius: var(--r-pill);
    padding: 7px 11px;
    color: var(--accent-strong);
    background: color-mix(in oklab, var(--accent) 10%, transparent);
    font: 700 11px/1 var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  @media (max-width: 900px) {
    .v4-foundation {
      width: calc(100% - 32px);
      margin-top: 16px;
      align-items: flex-start;
      flex-direction: column;
    }
  }
</style>
