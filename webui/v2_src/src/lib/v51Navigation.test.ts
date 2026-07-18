import assert from 'node:assert/strict';
import { test } from 'node:test';

import type * as Routes from './routes';

const routesPath = ['.', 'routes.ts'].join('/');
const {
  DASHBOARD_ROUTES,
  V51_DEFAULT_POLICY,
  V51_NAV_GROUPS,
  V51_SHELL_BRAND,
  V51_VERSION_HISTORY,
  routeLabelForShell,
}: typeof Routes = await import(routesPath);

function navSnapshot() {
  return V51_NAV_GROUPS.map((group) => ({
    group: group.label,
    items: group.items.map((item) => {
      const snapshot: { label: string; routeId?: string; action?: string } = { label: item.label };
      if (item.routeId) snapshot.routeId = item.routeId;
      if (item.action) snapshot.action = item.action;
      return snapshot;
    }),
  }));
}

function navRouteIds(): string[] {
  return V51_NAV_GROUPS.flatMap((group) => group.items.flatMap((item) => item.routeId ? [item.routeId] : []));
}

test('V5.1 brand and version history preserve default, current receipt, and no-release wording', () => {
  assert.deepEqual(V51_SHELL_BRAND, {
    name: 'Kronos',
    subtitle: 'AI Quant Reinforcement Learning',
    version: 'v5.1',
    updateDate: '2026-07-17',
    displayVersion: 'v5.1 · Updated 2026-07-17',
  });
  assert.equal(V51_DEFAULT_POLICY, 'V3 기본 유지 · V5 기본 전환은 미승인·미실행');
  assert.deepEqual(
    V51_VERSION_HISTORY.map((entry) => ({
      version: entry.version,
      date: entry.date,
      commitSha: entry.commitSha,
      defaultUi: entry.defaultUi,
      releaseTag: entry.releaseTag,
    })),
    [
      { version: 'V5.1', date: '2026-07-17', commitSha: '6a8fd02', defaultUi: V51_DEFAULT_POLICY, releaseTag: 'not released' },
      { version: 'V5', date: '2026-07-16', commitSha: '59fb74c', defaultUi: V51_DEFAULT_POLICY, releaseTag: 'fork-v1.3.0-dashboard-v5-research-preview' },
    ],
  );
  assert.match(V51_VERSION_HISTORY[0]?.validation ?? '', /Current verified browser bundle revision 6a8fd02/);
  assert.match(V51_VERSION_HISTORY[0]?.validation ?? '', /current frontend tests: 351/);
  assert.match(V51_VERSION_HISTORY[0]?.validation ?? '', /no release-default, live-readiness/);
});

test('V5.1 navigation groups, order, labels, and actions match the IA contract', () => {
  assert.deepEqual(navSnapshot(), [
    {
      group: 'COMMAND',
      items: [
        { routeId: 'mission-control', label: 'Mission Control' },
      ],
    },
    {
      group: 'KRONOS',
      items: [
        { routeId: 'forecast', label: 'Forecast Workbench' },
        { routeId: 'stom', label: 'Prediction Diagnostics' },
      ],
    },
    {
      group: 'REINFORCEMENT LEARNING',
      items: [
        { routeId: 'daily-ohlcv', label: 'Daily Close RL' },
        { routeId: 'rl', label: 'RL Trading Evidence' },
        { routeId: 'daily-rl-guide', label: 'RL Guide' },
      ],
    },
    {
      group: 'OPERATIONS',
      items: [
        { routeId: 'live-training', label: 'Live Training' },
        { routeId: 'history', label: 'Runs & Reports' },
        { routeId: 'artifacts', label: 'Artifacts & Models' },
        { routeId: 'system-health', label: 'System Health' },
      ],
    },
    {
      group: 'KNOWLEDGE',
      items: [
        { routeId: 'docs', label: 'Research Reports & Wiki' },
        { action: 'version-history', label: 'Version History' },
        { routeId: 'settings', label: 'Settings' },
      ],
    },
  ]);
});

test('V5.1 navigation reuses existing route IDs and aliases without changing V3/V4 route labels', () => {
  const routeIds = DASHBOARD_ROUTES.map((route) => route.id);
  assert.deepEqual(routeIds, [
    'mission-control',
    'live-training',
    'forecast',
    'stom',
    'daily-ohlcv',
    'daily-rl-guide',
    'rl',
    'artifacts',
    'history',
    'system-health',
    'settings',
    'docs',
  ]);
  assert.deepEqual(navRouteIds(), [
    'mission-control',
    'forecast',
    'stom',
    'daily-ohlcv',
    'rl',
    'daily-rl-guide',
    'live-training',
    'history',
    'artifacts',
    'system-health',
    'docs',
    'settings',
  ]);
  assert.deepEqual(new Set(navRouteIds()), new Set(routeIds));

  const aliases = Object.fromEntries(DASHBOARD_ROUTES.map((route) => [route.id, route.aliases ?? []]));
  assert.deepEqual(aliases['rl'], ['/rl']);
  assert.deepEqual(aliases['daily-ohlcv'], ['/daily-ohlcv']);
  assert.deepEqual(aliases['daily-rl-guide'], ['/daily-rl-guide', '/daily-ohlcv/rl-guide']);

  assert.equal(routeLabelForShell('forecast', 'v3'), '예측 워크벤치');
  assert.equal(routeLabelForShell('forecast', 'v4'), '예측 워크벤치');
  assert.equal(routeLabelForShell('forecast', 'v5'), 'Forecast Workbench');
  assert.equal(routeLabelForShell('rl', 'v5'), 'RL Trading Evidence');
  assert.equal(routeLabelForShell('docs', 'v5'), 'Research Reports & Wiki');
});
