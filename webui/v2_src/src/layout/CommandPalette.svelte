<script lang="ts">
  import { tick, onMount } from 'svelte';
  import {
    OPEN_PALETTE_EVENT,
    activateCommand,
    buildCommandPalette,
    filterCommands,
    firstEnabledIndex,
    moveEnabledIndex,
    shouldClosePaletteAfterActivation,
    type PaletteCommand,
  } from '$lib/commandPalette';
  import { DASHBOARD_ROUTES, navigateToTab } from '$lib/routes';
  import { setDashboardShell } from '$lib/shellMode';

  const LISTBOX_ID = 'v4-command-palette-listbox';
  const INPUT_ID = 'v4-command-palette-input';
  const FOCUSABLE_SELECTOR = 'button:not([disabled]):not([tabindex="-1"]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])';

  let open = $state(false);
  let query = $state('');
  let activeIndex = $state(-1);
  let blockedReason = $state('');
  let previousFocus = $state<HTMLElement | null>(null);
  let dialogEl = $state<HTMLElement>();
  let inputEl = $state<HTMLInputElement>();

  const paletteCommands = buildCommandPalette(DASHBOARD_ROUTES);
  let commands = $derived(filterCommands(query, paletteCommands));
  let activeCommand = $derived(commands[activeIndex] ?? null);
  let activeDescendant = $derived(activeCommand ? `v4-command-${activeCommand.id}` : undefined);
  function defaultActiveIndex(list: readonly PaletteCommand[]): number {
    const enabled = firstEnabledIndex(list);
    return enabled >= 0 ? enabled : list.length > 0 ? 0 : -1;
  }


  $effect(() => {
    if (!open) return;
    if (commands.length === 0) {
      activeIndex = -1;
      return;
    }
    if (activeIndex < 0 || activeIndex >= commands.length) {
      activeIndex = defaultActiveIndex(commands);
    }
  });

  function restoreFocus() {
    previousFocus?.focus();
    previousFocus = null;
  }

  async function openPalette() {
    if (open) {
      await tick();
      inputEl?.focus();
      return;
    }
    previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    open = true;
    query = '';
    blockedReason = '';
    activeIndex = defaultActiveIndex(paletteCommands);
    await tick();
    inputEl?.focus();
  }

  function closePalette() {
    open = false;
    blockedReason = '';
    restoreFocus();
  }

  function focusableElements(): HTMLElement[] {
    return Array.from(dialogEl?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR) ?? []).filter(
      (element) => element.offsetParent !== null || element === document.activeElement,
    );
  }

  function trapFocus(event: KeyboardEvent): void {
    const elements = focusableElements();
    if (elements.length === 0) {
      event.preventDefault();
      dialogEl?.focus();
      return;
    }

    const first = elements[0];
    const last = elements[elements.length - 1];
    const active = document.activeElement;
    const focusIsOutsideOptions = active === dialogEl || !dialogEl?.contains(active);
    if (event.shiftKey) {
      if (active === first || focusIsOutsideOptions) {
        event.preventDefault();
        last.focus();
      }
      return;
    }

    if (active === last || focusIsOutsideOptions) {
      event.preventDefault();
      first.focus();
    }
  }

  function inspectInPage(selector: string) {
    const target = document.querySelector<HTMLElement>(selector);
    target?.scrollIntoView({ block: 'center', inline: 'nearest' });
    target?.focus?.({ preventScroll: true });
  }

  function runCommand(command: PaletteCommand | null) {
    if (!command) return;
    const result = activateCommand(command, {
      navigateToTab,
      inspect: inspectInPage,
      filter: (value) => {
        query = value;
        activeIndex = defaultActiveIndex(filterCommands(value, paletteCommands));
        void tick().then(() => inputEl?.focus());
      },
      setDashboardShell: (shell) => setDashboardShell(shell, { persist: true, replace: true }),
    });
    if (result.status === 'blocked') {
      blockedReason = result.reason ?? 'This command is blocked.';
      return;
    }
    blockedReason = '';
    if (shouldClosePaletteAfterActivation(command, result)) {
      closePalette();
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      event.preventDefault();
      closePalette();
      return;
    }
    if (event.key === 'Tab') {
      trapFocus(event);
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      activeIndex = moveEnabledIndex(commands, activeIndex, 1);
      blockedReason = '';
      return;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      activeIndex = moveEnabledIndex(commands, activeIndex, -1);
      blockedReason = '';
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      runCommand(activeCommand);
    }
  }

  function handleGlobalKeydown(event: KeyboardEvent) {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      void openPalette();
    }
  }

  function selectCommand(index: number) {
    activeIndex = index;
    blockedReason = '';
  }

  function handleSearchInput(event: Event) {
    query = event.currentTarget instanceof HTMLInputElement ? event.currentTarget.value : '';
    blockedReason = '';
    activeIndex = defaultActiveIndex(filterCommands(query, paletteCommands));
  }

  onMount(() => {
    window.addEventListener('keydown', handleGlobalKeydown);
    window.addEventListener(OPEN_PALETTE_EVENT, openPalette);
    return () => {
      window.removeEventListener('keydown', handleGlobalKeydown);
      window.removeEventListener(OPEN_PALETTE_EVENT, openPalette);
    };
  });
</script>

{#if open}
  <button type="button" class="command-palette-backdrop" aria-label="Close command palette" tabindex="-1" onclick={closePalette}></button>
  <div
    class="command-palette"
    bind:this={dialogEl}
    data-v4-command-palette
    role="dialog"
    aria-modal="true"
    aria-labelledby="v4-command-palette-title"
    onkeydown={handleKeydown}
    tabindex="-1"
  >
    <div class="command-palette__header">
      <div>
        <h2 id="v4-command-palette-title">Command palette</h2>
        <p>Read-only navigation, inspection, filtering, and shell selection.</p>
      </div>
      <button type="button" class="command-palette__close" aria-label="Close command palette" onclick={closePalette}>Esc</button>
    </div>

    <label class="command-palette__search" for={INPUT_ID}>
      <span class="sr-only">Search commands</span>
      <input
        id={INPUT_ID}
        bind:this={inputEl}
        value={query}
        type="search"
        role="combobox"
        aria-controls={LISTBOX_ID}
        aria-expanded="true"
        aria-autocomplete="list"
        aria-activedescendant={activeDescendant}
        placeholder="Search tabs, inspect page, filter locally, switch shell…"
        oninput={handleSearchInput}
      />
    </label>

    {#if blockedReason}
      <div class="command-palette__reason" role="status" aria-live="polite">{blockedReason}</div>
    {/if}

    <div id={LISTBOX_ID} class="command-palette__list" role="listbox" aria-label="Available commands">
      {#each commands as command, index (command.id)}
        <button
          id={`v4-command-${command.id}`}
          type="button"
          class:active={index === activeIndex}
          class:disabled={Boolean(command.disabledReason)}
          role="option"
          aria-selected={index === activeIndex}
          aria-disabled={Boolean(command.disabledReason)}
          tabindex="-1"
          onmouseenter={() => selectCommand(index)}
          onclick={() => runCommand(command)}
        >
          <span class="command-palette__title">{command.title}</span>
          <span class="command-palette__description">{command.disabledReason ?? command.description}</span>
          <span class="command-palette__kind">{command.kind}</span>
        </button>
      {:else}
        <div class="command-palette__empty">No local commands match “{query}”.</div>
      {/each}
    </div>
  </div>
{/if}

<style>
  .command-palette-backdrop {
    position: fixed;
    inset: 0;
    z-index: 80;
    background: color-mix(in oklab, var(--bg) 66%, transparent);
    backdrop-filter: blur(8px);
    border: 0;
    padding: 0;
  }

  .command-palette {
    position: fixed;
    top: 12vh;
    left: 50%;
    z-index: 81;
    width: min(720px, calc(100vw - 32px));
    max-height: min(760px, calc(100vh - 96px));
    transform: translateX(-50%);
    overflow: hidden;
    border: 1px solid var(--border-faint);
    border-radius: var(--r-xl);
    background: color-mix(in oklab, var(--surface) 96%, transparent);
    box-shadow: var(--shadow-lg);
    color: var(--fg);
  }

  .command-palette__header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    padding: 20px 22px 12px;
  }

  .command-palette__header h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 800;
  }

  .command-palette__header p {
    margin: 4px 0 0;
    color: var(--muted);
    font-size: 13px;
  }

  .command-palette__close {
    border: 1px solid var(--border-faint);
    border-radius: var(--r-pill);
    background: color-mix(in oklab, var(--surface-sunken) 78%, transparent);
    color: var(--fg);
    cursor: pointer;
    font-size: 12px;
    padding: 6px 10px;
  }

  .command-palette__search {
    display: block;
    padding: 0 22px 14px;
  }

  .command-palette__search input {
    width: 100%;
    border: 1px solid var(--border-faint);
    border-radius: var(--r-md);
    background: color-mix(in oklab, var(--surface-sunken) 72%, transparent);
    color: var(--fg-strong);
    font-size: 16px;
    outline: none;
    padding: 14px 16px;
  }

  .command-palette__search input:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px color-mix(in oklab, var(--accent) 22%, transparent);
  }

  .command-palette__reason {
    margin: 0 22px 12px;
    border: 1px solid color-mix(in oklab, var(--warn) 32%, var(--border-faint));
    border-radius: var(--r-sm);
    background: color-mix(in oklab, var(--warn-soft) 42%, transparent);
    color: var(--warn);
    font-size: 13px;
    padding: 10px 12px;
  }

  .command-palette__list {
    max-height: 520px;
    margin: 0;
    overflow-y: auto;
    padding: 6px 10px 12px;
  }


  .command-palette__list [role='option'] {
    display: grid;
    width: 100%;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 4px 12px;
    border: 1px solid transparent;
    border-radius: var(--r-md);
    background: transparent;
    color: inherit;
    cursor: pointer;
    font: inherit;
    padding: 12px;
    text-align: left;
  }

  .command-palette__list [role='option'].active {
    border-color: color-mix(in oklab, var(--accent) 58%, var(--border));
    background: color-mix(in oklab, var(--accent) 18%, transparent);
  }

  .command-palette__list [role='option'].disabled {
    cursor: not-allowed;
    opacity: 0.62;
  }

  .command-palette__title {
    font-size: 14px;
    font-weight: 800;
  }

  .command-palette__description {
    grid-column: 1 / 2;
    color: var(--muted);
    font-size: 12px;
  }

  .command-palette__kind {
    align-self: center;
    border: 1px solid var(--border-faint);
    border-radius: var(--r-pill);
    color: var(--muted);
    font-size: 11px;
    padding: 4px 8px;
    text-transform: uppercase;
  }

  .command-palette__empty {
    color: var(--muted);
    cursor: default;
  }

  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
  }
</style>
