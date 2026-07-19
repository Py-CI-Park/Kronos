import assert from 'node:assert/strict';
import test from 'node:test';
import type * as Registry from './registry';

const registryPath = ['.', 'registry.ts'].join('/');
const { V6_BRAND, V6_PAGES, resolveV6Page, v6PageUrl }: typeof Registry = await import(registryPath);

const expectedIds = [
  'overview', 'data', 'experiment', 'training', 'evaluation', 'compare', 'report',
  'insight-symbol', 'insight-flow', 'insight-regime', 'intraday', 'kronos', 'settings',
];

test('V6 registry preserves the planned page order and group membership', () => {
  assert.deepEqual(V6_PAGES.map((page) => page.id), expectedIds);
  assert.deepEqual(V6_PAGES.filter((page) => page.group === 'COMMAND').map((page) => page.id), ['overview']);
  assert.deepEqual(V6_PAGES.filter((page) => page.group === 'REINFORCEMENT LEARNING').map((page) => page.id), ['data', 'experiment', 'training', 'evaluation', 'compare', 'report']);
  assert.deepEqual(V6_PAGES.filter((page) => page.group === 'INSIGHT').map((page) => page.id), ['insight-symbol', 'insight-flow', 'insight-regime']);
  assert.deepEqual(V6_PAGES.filter((page) => page.group === 'PLATFORM').map((page) => page.id), ['intraday', 'kronos']);
  assert.deepEqual(V6_PAGES.filter((page) => page.group === 'ADVANCED').map((page) => page.id), ['settings']);
});

test('V6 registry keeps workflow steps and implementation status honest', () => {
  assert.deepEqual(V6_PAGES.map((page) => page.step).filter((step): step is number => step !== null), [1, 2, 3, 4, 5, 6, 7]);
  assert.ok(V6_PAGES.every((page) => page.status === 'NOT_BUILT'));
});

test('V6 brand, fallback, and URLs match the shell contract', () => {
  assert.deepEqual(V6_BRAND, {
    name: 'AI Quant Reinforcement Learning',
    subtitle: 'V6 Workflow Research Platform',
    version: 'v6.0-dev',
    updateDate: '2026-07-19',
  });
  assert.equal(resolveV6Page('training').id, 'training');
  assert.equal(resolveV6Page(null).id, 'overview');
  assert.equal(resolveV6Page('unknown').id, 'overview');
  assert.equal(v6PageUrl('overview'), '/?ui=v6');
  assert.equal(v6PageUrl('training'), '/?ui=v6&tab=training');
});
