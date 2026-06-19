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
  { id: 'rl', label: 'RL Trading', path: '/rl', aliases: ['/rl-lab', '/v2/rl-trading', '/v2/rl-lab'], queryTabs: ['rl', 'rl-lab', 'rl-trading'] },
  { id: 'daily-ohlcv', label: 'Daily OHLCV', path: '/daily-ohlcv', aliases: ['/daily'], queryTabs: ['daily-ohlcv', 'daily'] },
  { id: 'daily-rl-guide', label: '일봉 RL 설명서', path: '/daily-rl-guide', aliases: ['/daily-ohlcv/rl-guide'], queryTabs: ['daily-rl-guide', 'daily-ohlcv-rl-guide'] },
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
  activeTab.set(route.id);
  if (options.replaceAlias) {
    const canonical = routeUrl(route.id);
    const current = `${window.location.pathname}${window.location.search}`;
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
