import { preserveShellQuery, type DashboardShell } from './shellMode';
import { activeTab } from './stores';
import type { IconName } from './icons';

export type V5WorkspaceDomain = 'kronos' | 'rl' | 'training-system';
type LegacyComponentKey =
  | 'mission-control' | 'live-training' | 'forecast' | 'stom'
  | 'daily-ohlcv' | 'daily-rl-guide' | 'rl' | 'artifacts'
  | 'history' | 'system-health' | 'settings' | 'docs';

interface RouteNavigation {
  readonly group: string;
  readonly order: number;
  readonly label?: string;
  readonly icon: IconName;
  readonly badge?: string | null;
  readonly status?: 'live' | 'warn' | null;
  readonly activeRouteIds?: readonly string[];
  readonly parentRouteId?: string;
}

interface DashboardRouteManifestEntry {
  readonly id: string;
  readonly label: string;
  readonly shellLabels: Partial<Record<DashboardShell, string>>;
  readonly path: string;
  readonly aliases?: readonly string[];
  readonly queryTabs?: readonly string[];
  readonly shells: readonly DashboardShell[];
  readonly componentKey: LegacyComponentKey;
  readonly v6CompatibilityTarget: string;
  readonly v5Workspace?: V5WorkspaceDomain;
  readonly navigation: Partial<Record<'v3' | 'v4' | 'v5', RouteNavigation>>;
}

export const DASHBOARD_ROUTE_MANIFEST = [
  { id: 'mission-control', label: 'Mission Control', shellLabels: {}, path: '/', aliases: [], queryTabs: ['mission-control', 'mission', 'home'], shells: ['v3', 'v4', 'v5'], componentKey: 'mission-control', v6CompatibilityTarget: 'home', navigation: { v3: { group: '커맨드', order: 1, icon: 'pulse' }, v4: { group: 'Home / Mission Control', order: 1, icon: 'pulse' }, v5: { group: 'COMMAND', order: 1, icon: 'pulse' } } },
  { id: 'live-training', label: '실시간 학습', shellLabels: {}, path: '/', aliases: ['/training', '/dashboard'], queryTabs: ['live-training', 'training'], shells: ['v3', 'v4', 'v5'], componentKey: 'live-training', v6CompatibilityTarget: 'rl?step=training', v5Workspace: 'training-system', navigation: { v3: { group: '라이브 · 시스템', order: 1, icon: 'activity', badge: 'LIVE', status: 'live' }, v4: { group: 'Operations', order: 1, icon: 'activity', badge: 'LIVE', status: 'live' }, v5: { group: 'OPERATIONS', order: 1, icon: 'activity', badge: 'LIVE', status: 'live', label: 'Training & System', activeRouteIds: ['live-training', 'system-health'] } } },
  { id: 'forecast', label: '예측 워크벤치', shellLabels: {}, path: '/', aliases: [], queryTabs: ['forecast'], shells: ['v3', 'v4', 'v5'], componentKey: 'forecast', v6CompatibilityTarget: 'lanes', v5Workspace: 'kronos', navigation: { v3: { group: 'Kronos 예측', order: 1, icon: 'wand' }, v4: { group: 'Forecast', order: 1, icon: 'wand' }, v5: { group: 'KRONOS', order: 1, icon: 'wand', label: 'Kronos Research', activeRouteIds: ['forecast', 'stom'] } } },
  { id: 'stom', label: '예측 진단', shellLabels: {}, path: '/', aliases: [], queryTabs: ['stom'], shells: ['v3', 'v4', 'v5'], componentKey: 'stom', v6CompatibilityTarget: 'insight?sub=symbol', v5Workspace: 'kronos', navigation: { v3: { group: 'Kronos 예측', order: 2, icon: 'pulse' }, v4: { group: 'Forecast', order: 2, icon: 'pulse' } } },
  { id: 'daily-ohlcv', label: 'Daily OHLCV', shellLabels: {}, path: '/', aliases: ['/daily-ohlcv'], queryTabs: ['daily-ohlcv', 'daily-ohlcv-panel'], shells: ['v3', 'v4', 'v5'], componentKey: 'daily-ohlcv', v6CompatibilityTarget: 'rl?step=data', v5Workspace: 'rl', navigation: { v3: { group: '트레이딩 리서치', order: 1, icon: 'pulse', badge: '연구' }, v4: { group: 'Daily Research', order: 1, icon: 'pulse', badge: '연구' } } },
  { id: 'daily-rl-guide', label: '일봉 RL 설명서', shellLabels: {}, path: '/', aliases: ['/daily-rl-guide', '/daily-ohlcv/rl-guide'], queryTabs: ['daily-rl-guide', 'daily-ohlcv-rl-guide'], shells: ['v3', 'v4', 'v5'], componentKey: 'daily-rl-guide', v6CompatibilityTarget: 'rl?step=report', v5Workspace: 'rl', navigation: { v3: { group: '트레이딩 리서치', order: 2, icon: 'file', parentRouteId: 'daily-ohlcv' }, v4: { group: 'Daily Research', order: 2, icon: 'file', parentRouteId: 'daily-ohlcv' } } },
  { id: 'rl', label: 'Trading Command Center', shellLabels: {}, path: '/', aliases: ['/rl'], queryTabs: ['rl', 'rl-lab', 'rl-trading'], shells: ['v3', 'v4', 'v5'], componentKey: 'rl', v6CompatibilityTarget: 'rl', v5Workspace: 'rl', navigation: { v3: { group: '트레이딩 리서치', order: 3, icon: 'rocket', badge: 'RL' }, v4: { group: 'RL Evidence', order: 1, icon: 'rocket', badge: 'RL' }, v5: { group: 'REINFORCEMENT LEARNING', order: 1, icon: 'rocket', badge: 'RL', label: 'RL Research & Evidence', activeRouteIds: ['rl', 'daily-ohlcv', 'daily-rl-guide'] } } },
  { id: 'artifacts', label: '아티팩트 & 모델', shellLabels: {}, path: '/', aliases: [], queryTabs: ['artifacts'], shells: ['v3', 'v4', 'v5'], componentKey: 'artifacts', v6CompatibilityTarget: 'rl?step=report', navigation: { v3: { group: '라이브 · 시스템', order: 3, icon: 'package' }, v4: { group: 'Operations', order: 3, icon: 'package' }, v5: { group: 'OPERATIONS', order: 3, icon: 'package', label: 'Artifacts & Models' } } },
  { id: 'history', label: '기록 & 런', shellLabels: {}, path: '/', aliases: [], queryTabs: ['history'], shells: ['v3', 'v4', 'v5'], componentKey: 'history', v6CompatibilityTarget: 'rl?step=compare', navigation: { v3: { group: '라이브 · 시스템', order: 4, icon: 'history' }, v4: { group: 'Operations', order: 4, icon: 'history' }, v5: { group: 'OPERATIONS', order: 2, icon: 'history', label: 'Runs & Reports' } } },
  { id: 'system-health', label: '시스템 상태', shellLabels: {}, path: '/', aliases: [], queryTabs: ['system-health'], shells: ['v3', 'v4', 'v5'], componentKey: 'system-health', v6CompatibilityTarget: 'home', v5Workspace: 'training-system', navigation: { v3: { group: '라이브 · 시스템', order: 2, icon: 'cpu' }, v4: { group: 'Operations', order: 2, icon: 'cpu' } } },
  { id: 'settings', label: '설정', shellLabels: {}, path: '/', aliases: [], queryTabs: ['settings'], shells: ['v3', 'v4', 'v5'], componentKey: 'settings', v6CompatibilityTarget: 'settings', navigation: { v3: { group: '라이브 · 시스템', order: 5, icon: 'settings' }, v4: { group: 'Admin & Docs', order: 1, icon: 'settings' }, v5: { group: 'KNOWLEDGE', order: 3, icon: 'settings', label: 'Settings' } } },
  { id: 'docs', label: '문서 · Wiki', shellLabels: {}, path: '/', aliases: [], queryTabs: ['docs'], shells: ['v3', 'v4', 'v5'], componentKey: 'docs', v6CompatibilityTarget: 'rl?step=report', navigation: { v3: { group: '라이브 · 시스템', order: 6, icon: 'file' }, v4: { group: 'Admin & Docs', order: 2, icon: 'file' }, v5: { group: 'KNOWLEDGE', order: 1, icon: 'file', label: 'Research Reports & Wiki' } } },
] as const satisfies readonly DashboardRouteManifestEntry[];

export type DashboardRouteId = (typeof DASHBOARD_ROUTE_MANIFEST)[number]['id'];
export type DashboardRoute = DashboardRouteManifestEntry & { readonly id: DashboardRouteId };
export type DashboardRouteComponentKey = (typeof DASHBOARD_ROUTE_MANIFEST)[number]['componentKey'];

export const DASHBOARD_ROUTES: readonly DashboardRoute[] = DASHBOARD_ROUTE_MANIFEST;

export interface V51NavItem {
  readonly id?: DashboardRouteId;
  readonly routeId?: DashboardRouteId;
  readonly activeRouteIds?: readonly DashboardRouteId[];
  readonly action?: 'version-history';
  readonly label: string;
  readonly icon: IconName;
  readonly badge?: string | null;
  readonly status?: 'live' | 'warn' | null;
  children?: V51NavItem[];
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
  name: 'AI Quant Reinforcement Learning',
  subtitle: 'Research & Operations',
  version: 'v5.1',
  updateDate: '2026-07-19',
  displayVersion: 'v5.1 · Updated 2026-07-19',
} as const;

export const V51_DEFAULT_POLICY = 'V3 기본 유지 · V5 기본 전환은 미승인·미실행';

export const V51_VERSION_HISTORY = [
  {
    version: 'V5.1',
    date: '2026-07-19',
    commitSha: '11268cb',
    releaseTag: 'not released',
    changes: 'Consolidated Kronos, RL, and training/system workspaces; widened the Evidence & Safety rail; enlarged the V5.1 title; and replaced the cramped history panel with an accessible dialog.',
    validation: 'Commit 11268cb passed 353 frontend tests, Svelte check across 409 files with zero errors/warnings, dashboard regression tests, V3 contract tests, production build, and live Chromium checks at 3440x1440 and 2160x3840. Read-only evidence only; no release-default, live-readiness, GO, profit, broker, or order claim.',
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

const NAV_GROUP_ORDER = {
  v3: ['커맨드', 'Kronos 예측', '트레이딩 리서치', '라이브 · 시스템'],
  v4: ['Home / Mission Control', 'Forecast', 'Daily Research', 'RL Evidence', 'Operations', 'Admin & Docs'],
  v5: ['COMMAND', 'KRONOS', 'REINFORCEMENT LEARNING', 'OPERATIONS', 'KNOWLEDGE'],
} as const;

function navigationFor(route: DashboardRoute, shell: 'v3' | 'v4' | 'v5'): RouteNavigation | undefined {
  return (route.navigation as Partial<Record<'v3' | 'v4' | 'v5', RouteNavigation>>)[shell];
}

function navGroupsForShell(shell: 'v3' | 'v4' | 'v5'): readonly V51NavGroup[] {
  const routesByGroup = new Map<string, (typeof DASHBOARD_ROUTE_MANIFEST)[number][]>();

  for (const route of DASHBOARD_ROUTE_MANIFEST) {
    const navigation = navigationFor(route, shell);
    if (!navigation) continue;
    const group = navigation.group;
    routesByGroup.set(group, [...(routesByGroup.get(group) ?? []), route]);
  }

  return NAV_GROUP_ORDER[shell].flatMap((label) => {
    const routes = [...routesByGroup.get(label) ?? []].sort(
      (left, right) => navigationFor(left, shell)!.order - navigationFor(right, shell)!.order,
    );
    if (routes.length === 0) return [];
    const itemsByRoute = new Map<DashboardRouteId, V51NavItem>();
    for (const route of routes) {
      const navigation = navigationFor(route, shell)!;
      if (navigation.parentRouteId) continue;
      itemsByRoute.set(route.id, {
        routeId: route.id,
        label: navigation.label ?? route.shellLabels[shell] ?? route.label,
        icon: navigation.icon,
        badge: navigation.badge,
        status: navigation.status,
        activeRouteIds: navigation.activeRouteIds as readonly DashboardRouteId[] | undefined,
      });
    }
    for (const route of routes) {
      const navigation = navigationFor(route, shell)!;
      if (!navigation.parentRouteId) continue;
      const parent = itemsByRoute.get(navigation.parentRouteId as DashboardRouteId);
      if (!parent) continue;
      parent.children = [
        ...(parent.children ?? []),
        { routeId: route.id, label: navigation.label ?? route.shellLabels[shell] ?? route.label, icon: navigation.icon, badge: navigation.badge },
      ];
    }
    return [{ label, items: [...itemsByRoute.values()] }];
  });
}

export const V3_NAV_GROUPS = navGroupsForShell('v3');
export const V4_NAV_GROUPS = navGroupsForShell('v4');
export const V51_NAV_GROUPS: readonly V51NavGroup[] = [
  ...navGroupsForShell('v5').map((group): V51NavGroup => group.label === 'KNOWLEDGE'
    ? { ...group, items: [...group.items.slice(0, 1), { action: 'version-history' as const, label: 'Version History', icon: 'history', badge: 'v5.1' }, ...group.items.slice(1)] }
    : group),
];

export function v5WorkspaceForRoute(tabId: string): V5WorkspaceDomain | null {
  const route = routeForTab(tabId);
  return route ? (route as DashboardRouteManifestEntry).v5Workspace ?? null : null;
}

function v51ItemMatchesRoute(item: V51NavItem, tabId: string): boolean {
  return item.routeId === tabId || item.activeRouteIds?.includes(tabId as DashboardRouteId) === true;
}

function v51RouteLabel(tabId: string): string | null {
  for (const group of V51_NAV_GROUPS) {
    for (const item of group.items) {
      if (v51ItemMatchesRoute(item, tabId)) return item.label;
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
  return DASHBOARD_ROUTES.find((route) => (route.queryTabs as readonly string[]).includes(tab) || route.id === tab) ?? null;
}

function routeFromPath(pathname: string): DashboardRoute | null {
  const path = normalizePath(pathname);
  return DASHBOARD_ROUTES.find((route) => route.path === path || (route as DashboardRouteManifestEntry).aliases?.includes(path)) ?? null;
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
  return ROUTE_BY_ID.get(tabId as DashboardRouteId) ?? null;
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
  return requested ? routeFromQuery(requested) : routeFromPath(currentLocation.pathname);
}
export function v6CompatibilityTarget(locationLike: Pick<Location, 'pathname' | 'search'>): string | null {
  return resolveRoute(locationLike)?.v6CompatibilityTarget ?? null;
}

export function syncTabFromLocation(options: { replaceAlias?: boolean } = {}): DashboardRouteId | null {
  if (typeof window === 'undefined') return null;
  const route = resolveRoute(window.location);
  if (!route) return null;
  const canonical = canonicalUrlForRoute(route, window.location);
  const current = `${window.location.pathname}${window.location.search}`;
  activeTab.set(route.id);
  if (options.replaceAlias && current !== canonical) {
    window.history.replaceState({ tab: route.id }, '', canonical);
  }
  return route.id;
}

export function navigateToTab(tabId: string, options: { replace?: boolean } = {}): void {
  const route = routeForTab(tabId);
  if (!route) return;
  activeTab.set(route.id);
  if (typeof window === 'undefined') return;
  const nextUrl = routeUrl(route.id);
  const current = `${window.location.pathname}${window.location.search}`;
  const state = { tab: route.id };
  if (options.replace || current === nextUrl) {
    window.history.replaceState(state, '', nextUrl);
  } else {
    window.history.pushState(state, '', nextUrl);
  }
}
