import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path: string) => readFile(new URL(path, import.meta.url), 'utf8');

test('shell applies persisted scale without CSS zoom and restores the root font size', async () => {
  const shell = await read('./V6Shell.svelte');

  assert.match(shell, /applyV6ScaleToRoot/u);
  assert.match(shell, /const root = document\.documentElement/u);
  assert.match(shell, /root\.style\.fontSize = previousRootFontSize/u);
  assert.match(shell, /data-v6-scale/u);
  assert.doesNotMatch(shell, /style:zoom/u);
});

test('all official pages use the shared V6 page rhythm', async () => {
  const sources = await Promise.all([
    './pages/command/CommandCenterPage.svelte',
    './pages/research/ResearchLibraryPage.svelte',
    './pages/live/LiveTrainingPage.svelte',
    './pages/evaluation/EvaluationWorkspace.svelte',
    './pages/evidence/DataEvidencePage.svelte',
    './pages/models/ModelsArtifactsPage.svelte',
    './pages/governance/ReportsGovernancePage.svelte',
    './pages/settings/UnifiedSettingsPage.svelte',
  ].map(read));

  for (const source of sources) assert.match(source, /class="[^"]*v6-page/u);
});

test('shared bar visualization exposes accessible summary and table fallback', async () => {
  const chart = await read('./components/visualization/AccessibleBarChart.svelte');

  assert.match(chart, /<figure/u);
  assert.match(chart, /role="img"/u);
  assert.match(chart, /aria-label=/u);
  assert.match(chart, /<figcaption/u);
  assert.match(chart, /<table/u);
  assert.doesNotMatch(chart, /min-width:2px/u);
});

test('evidence-heavy pages reuse the shared visualization', async () => {
  const sources = await Promise.all([
    './pages/command/CommandCenterPage.svelte',
    './pages/research/ResearchLibraryPage.svelte',
    './pages/evidence/DataEvidencePage.svelte',
    './pages/models/ModelsArtifactsPage.svelte',
    './pages/governance/ReportsGovernancePage.svelte',
  ].map(read));

  for (const source of sources) assert.match(source, /AccessibleBarChart/u);
});

test('navigation provides mobile-safe tap targets and non-overlapping status details', async () => {
  const sidebar = await read('./components/shell/UnifiedSidebar.svelte');
  const rail = await read('./components/shell/SystemStatusRail.svelte');
  const pageHeader = await read('./components/shell/PageHeader.svelte');
  const shellCss = await read('./unified-shell.css');

  assert.match(sidebar, /min-height:44px/u);
  assert.match(sidebar, /touch-action:manipulation/u);
  assert.match(sidebar, /\.sidebar\[data-unified-sidebar\]\{[^}]*transform:none/u);
  assert.match(sidebar, /width:auto/u);
  assert.match(shellCss, /overflow-x:\s*auto/u);
  assert.match(shellCss, /padding-bottom\s*:/u);
  assert.match(rail, /details>div\{position:static/u);
  assert.match(pageHeader, /\.page-header h1\{[^}]*overflow-wrap:anywhere/u);
});
