import assert from 'node:assert/strict';
import test from 'node:test';
import type * as Registry from './registry';

const registryPath = ['.', 'registry.ts'].join('/');
const { V6_BRAND, V6_INSIGHT_SUBTABS, V6_PAGES, V6_RL_STEPS, resolveV6Location }: typeof Registry = await import(registryPath);

test('V6 registry exposes the unified run-centred navigation order', () => {
  // Given / When
  const pageIds = V6_PAGES.map((page) => page.id);
  const groups = V6_PAGES.map((page) => page.group);

  // Then
  assert.deepEqual(pageIds, ['command', 'research', 'live', 'evaluation', 'evidence', 'models', 'governance', 'settings']);
  assert.deepEqual(groups, ['COMMAND', 'RESEARCH', 'RESEARCH', 'RESEARCH', 'EVIDENCE', 'EVIDENCE', 'GOVERNANCE', 'ADVANCED']);
  assert.ok(V6_PAGES.every((page) => page.status === 'BUILT'));
});

test('V6 registry keeps the RL stepper and insight subtabs ordered', () => {
  assert.deepEqual(V6_RL_STEPS.map((step) => step.id), ['discovery', 'data', 'experiment', 'training', 'evaluation', 'compare', 'report']);
  assert.deepEqual(V6_INSIGHT_SUBTABS.map((tab) => tab.id), ['symbol', 'flow', 'regime']);
});

test('V6 registry resolves legacy locations into their workspace deep links', () => {
  // Given / When / Then
  assert.deepEqual(resolveV6Location('overview', null, null), { tab: 'command' });
  assert.deepEqual(resolveV6Location('home', null, null), { tab: 'command' });
  assert.deepEqual(resolveV6Location('scorecard', null, null), { tab: 'command' });
  assert.deepEqual(resolveV6Location('training', null, null), { tab: 'live' });
  assert.deepEqual(resolveV6Location('insight-flow', null, null), { tab: 'evidence', sub: 'flow' });
  assert.deepEqual(resolveV6Location('kronos', null, null), { tab: 'models' });
  assert.deepEqual(resolveV6Location('intraday', null, null), { tab: 'research' });
  assert.deepEqual(resolveV6Location(null, null, null, '/training'), { tab: 'live' });
  assert.deepEqual(resolveV6Location(null, null, null, '/dashboard'), { tab: 'live' });
  assert.deepEqual(resolveV6Location('live-training', null, null), { tab: 'live' });
});

test('V6 brand identifies the released shell', () => {
  assert.deepEqual(V6_BRAND, {
    name: 'Kronos Reinforcement Learning',
    subtitle: 'Evidence-first Quant Research Command Center',
    version: 'v1.28.0-dev',
    updateDate: '2026-08-05',
  });
});
