import assert from 'node:assert/strict';
import test from 'node:test';
import type * as Registry from './registry';

const registryPath = ['.', 'registry.ts'].join('/');
const { V6_BRAND, V6_INSIGHT_SUBTABS, V6_PAGES, V6_RL_STEPS, resolveV6Location }: typeof Registry = await import(registryPath);

test('V6 registry exposes the five-tab information architecture in navigation order', () => {
  assert.deepEqual(V6_PAGES.map((page) => page.id), ['home', 'rl', 'insight', 'lanes', 'settings']);
  assert.deepEqual(V6_PAGES.map((page) => page.group), ['COMMAND', 'RESEARCH', 'RESEARCH', 'PLATFORM', 'ADVANCED']);
  assert.ok(V6_PAGES.every((page) => page.status === 'BUILT'));
});

test('V6 registry keeps the RL stepper and insight subtabs ordered', () => {
  assert.deepEqual(V6_RL_STEPS.map((step) => step.id), ['data', 'experiment', 'training', 'evaluation', 'compare', 'report']);
  assert.deepEqual(V6_INSIGHT_SUBTABS.map((tab) => tab.id), ['symbol', 'flow', 'regime']);
});

test('V6 registry resolves legacy locations into their workspace deep links', () => {
  assert.deepEqual(resolveV6Location('overview', null, null), { tab: 'home' });
  assert.deepEqual(resolveV6Location('training', null, null), { tab: 'rl', step: 'training' });
  assert.deepEqual(resolveV6Location('insight-flow', null, null), { tab: 'insight', sub: 'flow' });
  assert.deepEqual(resolveV6Location('intraday', null, null), { tab: 'lanes' });
});

test('V6 brand remains unchanged', () => {
  assert.deepEqual(V6_BRAND, {
    name: 'AI Quant Reinforcement Learning',
    subtitle: 'V6 Workflow Research Platform',
    version: 'v6.0-dev',
    updateDate: '2026-07-19',
  });
});
