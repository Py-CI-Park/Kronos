import { preserveShellQuery } from './shellMode';
import { activeTab } from './stores';

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
