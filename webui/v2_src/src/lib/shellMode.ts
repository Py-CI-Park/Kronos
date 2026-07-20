import { writable, type Writable } from 'svelte/store';
import { isV5DefaultGateAllowed, readLocalV5DefaultGateReceipt } from './v5DefaultGate';

export type DashboardShell = 'v3' | 'v4' | 'v5' | 'v6';

export const SHELL_STORAGE_KEY = 'kronos-dashboard-shell';

export interface ShellResolution {
  shell: DashboardShell;
  source: 'query' | 'storage' | 'default';
  shouldPersist: boolean;
}

const DEFAULT_SHELL: DashboardShell = 'v3';

function isDashboardShell(value: string | null): value is DashboardShell {
  return value === 'v3' || value === 'v4' || value === 'v5' || value === 'v6';
}

function parseSearch(search: string): URLSearchParams {
  const normalized = search.startsWith('?') ? search : `?${search}`;
  try {
    return new URLSearchParams(normalized);
  } catch {
    return new URLSearchParams();
  }
}
function splitUrlHash(url: string): { withoutHash: string; hash: string } {
  const hashIndex = url.indexOf('#');
  if (hashIndex === -1) {
    return { withoutHash: url, hash: '' };
  }
  return { withoutHash: url.slice(0, hashIndex), hash: url.slice(hashIndex) };
}

function splitUrlSearch(url: string): { pathname: string; search: string } {
  const searchIndex = url.indexOf('?');
  if (searchIndex === -1) {
    return { pathname: url, search: '' };
  }
  return { pathname: url.slice(0, searchIndex), search: url.slice(searchIndex + 1) };
}


export function resolveDashboardShell(
  search: string,
  storedValue: string | null,
  v5DefaultGateReceipt: unknown = null,
): ShellResolution {
  const params = parseSearch(search);
  const queryShell = params.get('ui');
  const v5DefaultAllowed = isV5DefaultGateAllowed(v5DefaultGateReceipt);

  if (isDashboardShell(queryShell)) {
    return {
      shell: queryShell,
      source: 'query',
      shouldPersist: params.get('ui_persist') === '1',
    };
  }

  if (isDashboardShell(storedValue)) {
    if (storedValue !== 'v5' || v5DefaultAllowed) {
      return { shell: storedValue, source: 'storage', shouldPersist: false };
    }
  }

  if (v5DefaultAllowed) {
    return { shell: 'v5', source: 'default', shouldPersist: false };
  }

  return { shell: DEFAULT_SHELL, source: 'default', shouldPersist: false };
}
export function preserveShellQuery(targetUrl: string, currentSearch: string): string {
  const currentParams = parseSearch(currentSearch);
  const shell = currentParams.get('ui');

  if (!isDashboardShell(shell)) {
    return targetUrl;
  }

  const { withoutHash, hash } = splitUrlHash(targetUrl);
  const { pathname, search } = splitUrlSearch(withoutHash);
  const targetParams = parseSearch(search);

  targetParams.set('ui', shell);
  if (currentParams.get('ui_persist') === '1') {
    targetParams.set('ui_persist', '1');
  } else {
    targetParams.delete('ui_persist');
  }

  const query = targetParams.toString();
  return `${pathname}${query ? `?${query}` : ''}${hash}`;
}

export const dashboardShell: Writable<DashboardShell> = writable<DashboardShell>(DEFAULT_SHELL);

function getSafeLocalStorage(): Storage | null {
  try {
    if (typeof globalThis === 'undefined') {
      return null;
    }
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

function readStoredShell(): string | null {
  const storage = getSafeLocalStorage();
  if (!storage) {
    return null;
  }

  try {
    return storage.getItem(SHELL_STORAGE_KEY);
  } catch {
    return null;
  }
}

function persistShell(shell: DashboardShell): void {
  const storage = getSafeLocalStorage();
  if (!storage) {
    return;
  }

  try {
    storage.setItem(SHELL_STORAGE_KEY, shell);
  } catch {
    // Dashboard shell selection is UI-only state; storage failures must not break load.
  }
}

function applyShellMarker(shell: DashboardShell): void {
  if (typeof document === 'undefined') {
    return;
  }

  try {
    document.documentElement?.setAttribute('data-kronos-shell', shell);
  } catch {
    // Marker updates are best-effort and must fail closed.
  }
}

export function initializeDashboardShell(): DashboardShell {
  const search = typeof location === 'undefined' ? '' : location.search;
  const resolution = resolveDashboardShell(search, readStoredShell(), readLocalV5DefaultGateReceipt());

  dashboardShell.set(resolution.shell);
  applyShellMarker(resolution.shell);

  if (resolution.shouldPersist) {
    persistShell(resolution.shell);
  }

  return resolution.shell;
}

export function shellSwitchUrl(
  shell: DashboardShell,
  locationLike?: Pick<Location, 'pathname' | 'search' | 'hash'>,
): string {
  const currentLocation =
    locationLike ?? (typeof location === 'undefined' ? { pathname: '', search: '', hash: '' } : location);
  const params = parseSearch(currentLocation.search);
  params.set('ui', shell);
  const query = params.toString();
  return `${currentLocation.pathname}${query ? `?${query}` : ''}${currentLocation.hash}`;
}

export function setDashboardShell(
  shell: DashboardShell,
  options: { persist?: boolean; replace?: boolean } = {},
): void {
  dashboardShell.set(shell);
  applyShellMarker(shell);

  if (options.persist === true) {
    persistShell(shell);
  }

  if (typeof location === 'undefined' || typeof history === 'undefined') {
    return;
  }

  try {
    const url = shellSwitchUrl(shell, location);
    if (options.replace === false) {
      history.pushState(history.state, '', url);
    } else {
      history.replaceState(history.state, '', url);
    }
  } catch {
    // URL/history updates are cosmetic for UI shell state; fail closed.
  }
}
