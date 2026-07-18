import { preserveShellQuery, type DashboardShell } from './shellMode';
import { activeTab } from './stores';
import type { IconName } from './icons';

export interface DashboardRoute {
  id: string;
  label: string;
  path: string;
  aliases?: readonly string[];
  queryTabs?: readonly string[];
}

export const DASHBOARD_ROUTES: readonly DashboardRoute[] = [
  { id: 'mission-control', label: 'Mission Control', path: '/', queryTabs: ['mission-control', 'mission', 'home'] },
  { id: 'live-training', label: '실시간 학습', path: '/', aliases: ['/training', '/dashboard'], queryTabs: ['live-training', 'training'] },
  { id: 'forecast', label: '예측 워크벤치', path: '/', queryTabs: ['forecast'] },
  { id: 'stom', label: '예측 진단', path: '/', queryTabs: ['stom'] },
  { id: 'daily-ohlcv', label: 'Daily OHLCV', path: '/', aliases: ['/daily-ohlcv'], queryTabs: ['daily-ohlcv', 'daily-ohlcv-panel'] },
  {
    id: 'daily-rl-guide',
    label: '일봉 RL 가이드',
    path: '/',
    aliases: ['/daily-rl-guide', '/daily-ohlcv/rl-guide'],
    queryTabs: ['daily-rl-guide', 'daily-ohlcv-rl-guide'],
  },
  {
    id: 'rl',
    label: 'Trading Command Center',
    path: '/',
    aliases: ['/rl'],
    queryTabs: ['rl', 'rl-lab', 'rl-trading'],
  },
  { id: 'artifacts', label: '아티팩트 & 모델', path: '/', queryTabs: ['artifacts'] },
  { id: 'history', label: '기록 & 런', path: '/', queryTabs: ['history'] },
  { id: 'system-health', label: '시스템 상태', path: '/', queryTabs: ['system-health'] },
  { id: 'settings', label: '설정', path: '/', queryTabs: ['settings'] },
  { id: 'docs', label: '문서 · Wiki', path: '/', queryTabs: ['docs'] },
] as const;

export interface V51NavItem {
  readonly id?: string;
  readonly routeId?: string;
  readonly action?: 'version-history';
  readonly label: string;
  readonly icon: IconName;
  readonly badge?: string | null;
  readonly status?: 'live' | 'warn' | null;
  readonly children?: readonly V51NavItem[];
}

export interface V51NavGroup {
  readonly label: string;
  readonly items: readonly V51NavItem[];
}

export interface V51VersionHistoryEntry {
  readonly version: 'V5' | 'V5.1';
  readonly date: string;
  readonly commitSha: string;
  readonly releaseTag: string;
  readonly changes: string;
  readonly validation: string;
  readonly defaultUi: string;
  readonly rollbackTarget: string;
}

export const V51_SHELL_BRAND = {
  name: 'Kronos',
  subtitle: 'AI Quant Reinforcement Learning',
  version: 'v5.1',
  updateDate: '2026-07-17',
  displayVersion: 'v5.1 · Updated 2026-07-17',
} as const;

export const V51_DEFAULT_POLICY = 'V3 기본 유지 · V5 기본 전환은 미승인·미실행';

export const V51_VERSION_HISTORY = [
  {
    version: 'V5.1',
    date: '2026-07-17',
    commitSha: '6a8fd02',
    releaseTag: 'not released',
    changes: 'Brand, V5.1 information architecture, evidence views, and report access orientation.',
    validation: 'Current verified browser bundle revision 6a8fd02; current frontend tests: 351. Read-only evidence only; no release-default, live-readiness, GO, profit, broker, or order claim.',
    defaultUi: V51_DEFAULT_POLICY,
    rollbackTarget: 'V3 shell and existing V3 route bookmarks',
  },
  {
    version: 'V5',
    date: '2026-07-16',
    commitSha: '59fb74c',
    releaseTag: 'fork-v1.3.0-dashboard-v5-research-preview',
    changes: 'Learning evidence shell, 12-tab restoration, read-only V5 routes, and research-preview governance.',
    validation: 'V5 engineering result recorded as 98/100; no model, profit, live-trading, release, or GO claim.',
    defaultUi: V51_DEFAULT_POLICY,
    rollbackTarget: 'V3 shell and existing V3 route bookmarks',
  },
] as const satisfies readonly V51VersionHistoryEntry[];

export const V51_NAV_GROUPS = [
  {
    label: 'COMMAND',
    items: [
      { routeId: 'mission-control', label: 'Mission Control', icon: 'pulse', badge: null },
    ],
  },
  {
    label: 'KRONOS',
    items: [
      { routeId: 'forecast', label: 'Forecast Workbench', icon: 'wand', badge: null },
      { routeId: 'stom', label: 'Prediction Diagnostics', icon: 'pulse', badge: null },
    ],
  },
  {
    label: 'REINFORCEMENT LEARNING',
    items: [
      { routeId: 'daily-ohlcv', label: 'Daily Close RL', icon: 'database', badge: null },
      { routeId: 'rl', label: 'RL Trading Evidence', icon: 'rocket', badge: 'RL' },
      { routeId: 'daily-rl-guide', label: 'RL Guide', icon: 'file', badge: null },
    ],
  },
  {
    label: 'OPERATIONS',
    items: [
      { routeId: 'live-training', label: 'Live Training', icon: 'activity', badge: 'LIVE', status: 'live' },
      { routeId: 'history', label: 'Runs & Reports', icon: 'history', badge: null },
      { routeId: 'artifacts', label: 'Artifacts & Models', icon: 'package', badge: null },
      { routeId: 'system-health', label: 'System Health', icon: 'cpu', badge: null },
    ],
  },
  {
    label: 'KNOWLEDGE',
    items: [
      { routeId: 'docs', label: 'Research Reports & Wiki', icon: 'file', badge: null },
      { action: 'version-history', label: 'Version History', icon: 'history', badge: 'v5.1' },
      { routeId: 'settings', label: 'Settings', icon: 'settings', badge: null },
    ],
  },
] as const satisfies readonly V51NavGroup[];

function v51RouteLabel(tabId: string): string | null {
  for (const group of V51_NAV_GROUPS) {
    for (const item of group.items) {
      if ('routeId' in item && item.routeId === tabId) return item.label;
    }
  }
  return null;
}

const ROUTE_BY_ID = new Map(DASHBOARD_ROUTES.map((route) => [route.id, route]));

function normalizePath(pathname: string): string {
  const normalized = pathname.replace(/\/+$/, '');
  return normalized || '/';
}

function routeFromQuery(tab: string | null): DashboardRoute | null {
  if (!tab) return null;
  return DASHBOARD_ROUTES.find((route) => route.queryTabs?.includes(tab) || route.id === tab) ?? null;
}

function routeFromPath(pathname: string): DashboardRoute | null {
  const path = normalizePath(pathname);
  return DASHBOARD_ROUTES.find((route) => route.path === path || route.aliases?.includes(path)) ?? null;
}
const RL_SECTIONS = new Set(['daily-gates', 'workflow', 'evidence']);


function canonicalUrlForRoute(route: DashboardRoute, locationLike: Pick<Location, 'pathname' | 'search'>): string {
  if (route.id === 'rl' && normalizePath(locationLike.pathname) === '/rl') {
    const section = new URLSearchParams(locationLike.search).get('section');
    if (section && RL_SECTIONS.has(section)) {
      return preserveShellQuery(`/rl?section=${encodeURIComponent(section)}`, locationLike.search);
    }
  }
  return routeUrl(route.id, { currentSearch: locationLike.search });
}

export function routeForTab(tabId: string): DashboardRoute | null {
  return ROUTE_BY_ID.get(tabId) ?? null;
}

export function routeLabel(tabId: string): string {
  return routeForTab(tabId)?.label ?? tabId;
}

export function routeLabelForShell(tabId: string, shell: DashboardShell): string {
  if (shell === 'v5') return v51RouteLabel(tabId) ?? routeLabel(tabId);
  return routeLabel(tabId);
}

export function routeUrl(tabId: string, options: { currentSearch?: string } = {}): string {
  const currentSearch = options.currentSearch ?? (typeof window === 'undefined' ? '' : window.location.search);
  const route = routeForTab(tabId);
  if (!route) return preserveShellQuery('/', currentSearch);
  const baseUrl = route.path !== '/' ? route.path : route.id === 'mission-control' ? '/' : `/?tab=${encodeURIComponent(route.id)}`;
  return preserveShellQuery(baseUrl, currentSearch);
}

export function resolveRoute(locationLike?: Pick<Location, 'pathname' | 'search'>): DashboardRoute | null {
  const currentLocation = locationLike ?? (typeof window === 'undefined' ? null : window.location);
  if (!currentLocation) return null;
  const requested = new URLSearchParams(currentLocation.search).get('tab');
  return routeFromQuery(requested) ?? routeFromPath(currentLocation.pathname);
}

export function syncTabFromLocation(options: { replaceAlias?: boolean } = {}): string {
  if (typeof window === 'undefined') return 'mission-control';
  const route = resolveRoute(window.location) ?? routeForTab('mission-control')!;
  const canonical = canonicalUrlForRoute(route, window.location);
  const current = `${window.location.pathname}${window.location.search}`;
  activeTab.set(route.id);
  if (options.replaceAlias) {
    if (current !== canonical) {
      window.history.replaceState({ tab: route.id }, '', canonical);
    }
  }
  return route.id;
}

export function navigateToTab(tabId: string, options: { replace?: boolean } = {}): void {
  activeTab.set(tabId);
  if (typeof window === 'undefined') return;
  const nextUrl = routeUrl(tabId);
  const current = `${window.location.pathname}${window.location.search}`;
  const state = { tab: tabId };
  if (options.replace || current === nextUrl) {
    window.history.replaceState(state, '', nextUrl);
  } else {
    window.history.pushState(state, '', nextUrl);
  }
}
