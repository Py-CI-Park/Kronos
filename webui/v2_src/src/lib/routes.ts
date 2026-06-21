import { activeTab } from './stores';

export interface DashboardRoute {
  id: string;
  label: string;
  path: string;
  aliases?: readonly string[];
  queryTabs?: readonly string[];
}

export const DASHBOARD_ROUTES: readonly DashboardRoute[] = [
  { id: 'live-training', label: '실시간 학습', path: '/', aliases: ['/training', '/dashboard'], queryTabs: ['live-training', 'training'] },
  { id: 'forecast', label: '예측 워크벤치', path: '/', queryTabs: ['forecast'] },
  { id: 'stom', label: '예측 진단', path: '/', queryTabs: ['stom'] },
  {
    id: 'rl',
    label: 'Trading Command Center',
    path: '/rl',
    aliases: ['/daily-ohlcv', '/daily', '/daily-rl-guide', '/daily-ohlcv/rl-guide', '/rl-lab', '/v2/rl-trading', '/v2/rl-lab'],
    queryTabs: ['rl', 'rl-lab', 'rl-trading', 'daily-ohlcv', 'daily', 'daily-rl-guide', 'daily-ohlcv-rl-guide'],
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

function canonicalUrlForRoute(route: DashboardRoute, locationLike: Location = window.location): string {
  if (route.id === 'rl' && normalizePath(locationLike.pathname) === '/rl') {
    const section = new URLSearchParams(locationLike.search).get('section');
    if (section && RL_SECTIONS.has(section)) {
      return `/rl?section=${encodeURIComponent(section)}`;
    }
  }
  return routeUrl(route.id);
}

function shouldHardNavigate(route: DashboardRoute): boolean {
  return route.id === 'rl' && route.path !== '/';
}

export function routeForTab(tabId: string): DashboardRoute | null {
  return ROUTE_BY_ID.get(tabId) ?? null;
}

export function routeLabel(tabId: string): string {
  return routeForTab(tabId)?.label ?? tabId;
}

export function routeUrl(tabId: string): string {
  const route = routeForTab(tabId);
  if (!route) return '/';
  if (route.path !== '/') return route.path;
  return route.id === 'live-training' ? '/' : `/?tab=${encodeURIComponent(route.id)}`;
}

export function resolveRoute(locationLike: Location = window.location): DashboardRoute | null {
  const requested = new URLSearchParams(locationLike.search).get('tab');
  return routeFromQuery(requested) ?? routeFromPath(locationLike.pathname);
}

export function syncTabFromLocation(options: { replaceAlias?: boolean } = {}): string {
  if (typeof window === 'undefined') return 'live-training';
  const route = resolveRoute(window.location) ?? routeForTab('live-training')!;
  const canonical = canonicalUrlForRoute(route);
  const current = `${window.location.pathname}${window.location.search}`;
  if (shouldHardNavigate(route) && current !== canonical) {
    window.location.replace(canonical);
    return route.id;
  }
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
  const route = routeForTab(tabId);
  if (route && shouldHardNavigate(route) && current !== nextUrl) {
    window.location.assign(nextUrl);
    return;
  }
  const state = { tab: tabId };
  if (options.replace || current === nextUrl) {
    window.history.replaceState(state, '', nextUrl);
  } else {
    window.history.pushState(state, '', nextUrl);
  }
}
