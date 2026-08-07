import assert from 'node:assert/strict';
import test from 'node:test';
import { get } from 'svelte/store';
import { V6_SCALES, V6_THEMES, applyV6ScaleToRoot, normalizeV6Scale, normalizeV6Theme, v6Scale, v6ScaleCssPercent, v6Theme } from './v6Theme';

test('V6 theme ids are unique with inherit as the default first entry', () => {
  const ids = V6_THEMES.map((theme) => theme.id);
  assert.equal(new Set(ids).size, ids.length);
  assert.deepEqual(ids, ['inherit', 'dark', 'ocean', 'forest', 'quant-terminal']);
});

test('normalizeV6Theme falls back to inherit for unknown values', () => {
  assert.equal(normalizeV6Theme('ocean'), 'ocean');
  assert.equal(normalizeV6Theme('neon'), 'inherit');
  assert.equal(normalizeV6Theme(null), 'inherit');
  assert.equal(normalizeV6Theme(123), 'inherit');
});

test('normalizeV6Scale accepts known scales as number or string', () => {
  assert.deepEqual([...V6_SCALES], [0.9, 1, 1.1, 1.25]);
  assert.equal(normalizeV6Scale(1.25), 1.25);
  assert.equal(normalizeV6Scale('0.9'), 0.9);
  assert.equal(normalizeV6Scale('2'), 1);
  assert.equal(normalizeV6Scale(undefined), 1);
});

test('V6 scale maps to an explicit root font-size percentage', () => {
  assert.equal(v6ScaleCssPercent(0.9), '90%');
  assert.equal(v6ScaleCssPercent(1), '100%');
  assert.equal(v6ScaleCssPercent(1.1), '110%');
  assert.equal(v6ScaleCssPercent(1.25), '125%');
});

test('V6 scale changes the observable root font size', () => {
  const root = { style: { fontSize: '100%' } };
  applyV6ScaleToRoot(root, 1.25);
  assert.equal(root.style.fontSize, '125%');
  applyV6ScaleToRoot(root, 0.9);
  assert.equal(root.style.fontSize, '90%');
});

test('stores initialise to safe defaults and accept writes without localStorage', () => {
  assert.ok(V6_THEMES.some((theme) => theme.id === get(v6Theme)));
  assert.ok(V6_SCALES.includes(get(v6Scale)));
  v6Theme.set('forest');
  assert.equal(get(v6Theme), 'forest');
  v6Theme.set('inherit');
  v6Scale.set(1.1);
  assert.equal(get(v6Scale), 1.1);
  v6Scale.set(1);
});
