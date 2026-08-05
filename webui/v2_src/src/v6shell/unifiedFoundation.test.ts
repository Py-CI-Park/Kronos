import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

test('unified shell uses one status rail and reusable shell components', async () => {
  // Given
  const shell = await readFile(new URL('./V6Shell.svelte', import.meta.url), 'utf8');

  // When / Then
  assert.match(shell, /<UnifiedSidebar/u);
  assert.match(shell, /<SystemStatusRail/u);
  assert.match(shell, /data-unified-v6-shell/u);
  assert.doesNotMatch(shell, /style:zoom/u);
  assert.doesNotMatch(shell, /<V6SafetyStrip/u);
  assert.doesNotMatch(shell, /<ProgramExecutionStrip/u);
  assert.doesNotMatch(shell, /<ResearchContext/u);
  assert.doesNotMatch(shell, /<IntradayPage \/><KronosPage/u);
  assert.match(shell, /function initialPage\(\): V6PageDef/u);
  assert.match(shell, /\$state<V6PageDef>\(initialPage\(\)\)/u);
  assert.doesNotMatch(shell, /\$state<V6PageDef>\(V6_PAGES\[0\]\)/u);
});

test('foundation components expose the shared page grammar', async () => {
  // Given
  const sources = await Promise.all([
    './components/shell/UnifiedSidebar.svelte',
    './components/shell/SystemStatusRail.svelte',
    './components/shell/PageHeader.svelte',
    './components/shell/KpiStrip.svelte',
    './components/shell/ResearchPanel.svelte',
  ].map((path) => readFile(new URL(path, import.meta.url), 'utf8')));

  // When
  const source = sources.join('\n');

  // Then
  assert.match(source, /data-unified-sidebar/u);
  assert.match(source, /data-system-status-rail/u);
  assert.match(source, /data-page-header/u);
  assert.match(source, /data-kpi-strip/u);
  assert.match(source, /data-research-panel/u);
  assert.match(source, /prefers-reduced-motion/u);
});
