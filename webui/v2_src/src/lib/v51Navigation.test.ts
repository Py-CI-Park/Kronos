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
      const snapshot: { label: string; routeId?: string; activeRouteIds?: readonly string[]; action?: string } = { label: item.label };
      if (item.routeId) snapshot.routeId = item.routeId;
      if (item.activeRouteIds) snapshot.activeRouteIds = item.activeRouteIds;
      if (item.action) snapshot.action = item.action;
      return snapshot;
    }),
  }));
}

function navRouteIds(): string[] {
  return V51_NAV_GROUPS.flatMap((group) => group.items.flatMap((item) => item.routeId ? [item.routeId] : []));
}

function navCoveredRouteIds(): string[] {
  return [
    ...new Set(
      V51_NAV_GROUPS.flatMap((group) =>
        group.items.flatMap((item) => [
          ...(item.routeId ? [item.routeId] : []),
          ...(item.activeRouteIds ?? []),
        ]),
      ),
    ),
  ];
}

test('V5.1 brand and version history preserve default, current receipt, and no-release wording', () => {
  assert.deepEqual(V51_SHELL_BRAND, {
    name: 'AI Quant Reinforcement Learning',
    subtitle: 'Research & Operations',
    version: 'v5.1',
    updateDate: '2026-07-19',
    displayVersion: 'v5.1 · Updated 2026-07-19',
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
      { version: 'V5.1', date: '2026-07-17', commitSha: 'c43ee9b', defaultUi: V51_DEFAULT_POLICY, releaseTag: 'not released' },
      { version: 'V5', date: '2026-07-16', commitSha: '59fb74c', defaultUi: V51_DEFAULT_POLICY, releaseTag: 'fork-v1.3.0-dashboard-v5-research-preview' },
    ],
  );
  assert.match(V51_VERSION_HISTORY[0]?.validation ?? '', /Verification snapshot c43ee9b recorded 353 frontend tests/);
  assert.match(V51_VERSION_HISTORY[0]?.validation ?? '', /metadata-only bundles do not claim new research validation/);
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
        { routeId: 'forecast', activeRouteIds: ['forecast', 'stom'], label: 'Kronos Research' },
      ],
    },
    {
      group: 'REINFORCEMENT LEARNING',
      items: [
        { routeId: 'rl', activeRouteIds: ['rl', 'daily-ohlcv', 'daily-rl-guide'], label: 'RL Research & Evidence' },
      ],
    },
    {
      group: 'OPERATIONS',
      items: [
        { routeId: 'live-training', activeRouteIds: ['live-training', 'system-health'], label: 'Training & System' },
        { routeId: 'history', label: 'Runs & Reports' },
        { routeId: 'artifacts', label: 'Artifacts & Models' },
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
    'rl',
    'live-training',
    'history',
    'artifacts',
    'docs',
    'settings',
  ]);
  assert.deepEqual(new Set(navCoveredRouteIds()), new Set(routeIds));

  const aliases = Object.fromEntries(DASHBOARD_ROUTES.map((route) => [route.id, route.aliases ?? []]));
  assert.deepEqual(aliases['rl'], ['/rl']);
  assert.deepEqual(aliases['daily-ohlcv'], ['/daily-ohlcv']);
  assert.deepEqual(aliases['daily-rl-guide'], ['/daily-rl-guide', '/daily-ohlcv/rl-guide']);

  assert.equal(routeLabelForShell('forecast', 'v3'), '예측 워크벤치');
  assert.equal(routeLabelForShell('forecast', 'v4'), '예측 워크벤치');
  assert.equal(routeLabelForShell('forecast', 'v5'), 'Kronos Research');
  assert.equal(routeLabelForShell('stom', 'v5'), 'Kronos Research');
  assert.equal(routeLabelForShell('rl', 'v5'), 'RL Research & Evidence');
  assert.equal(routeLabelForShell('daily-ohlcv', 'v5'), 'RL Research & Evidence');
  assert.equal(routeLabelForShell('daily-rl-guide', 'v5'), 'RL Research & Evidence');
  assert.equal(routeLabelForShell('live-training', 'v5'), 'Training & System');
  assert.equal(routeLabelForShell('system-health', 'v5'), 'Training & System');
  assert.equal(routeLabelForShell('docs', 'v5'), 'Research Reports & Wiki');
});
