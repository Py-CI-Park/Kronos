import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

test('command center uses the lightweight unified APIs and exposes every page', async () => {
  const command = await readFile(new URL('./pages/command/CommandCenterPage.svelte', import.meta.url), 'utf8');
  const shell = await readFile(new URL('./V6Shell.svelte', import.meta.url), 'utf8');

  assert.match(command, /loadResearchSummary/u);
  assert.match(command, /loadTelemetryRuns/u);
  assert.match(command, /loadGovernanceSummary/u);
  assert.match(command, /V6_PAGES/u);
  assert.match(command, /제품 구현·UX/u);
  assert.match(command, /경제 모델/u);
  assert.doesNotMatch(command, /getV6ResearchRegistry|getV6Runs|getV6DataReadiness/u);
  assert.match(shell, /CommandCenterPage/u);
  assert.doesNotMatch(shell, /HomePage/u);
});

test('settings follows the common shell grammar and preserves read-only controls', async () => {
  const settings = await readFile(new URL('./pages/settings/UnifiedSettingsPage.svelte', import.meta.url), 'utf8');
  const shell = await readFile(new URL('./V6Shell.svelte', import.meta.url), 'utf8');

  assert.match(settings, /PageHeader/u);
  assert.match(settings, /ResearchPanel/u);
  assert.match(settings, /StateMatrix/u);
  assert.match(settings, /aria-pressed/u);
  assert.match(settings, /주문 권한/u);
  assert.match(shell, /UnifiedSettingsPage/u);
  assert.doesNotMatch(shell, /pages\/SettingsPage/u);
});

test('unified score keeps product quality separate from model and live readiness', async () => {
  const score = await readFile(new URL('./scorecard/programExecution.ts', import.meta.url), 'utf8');

  assert.match(score, /implementationScore: 94/u);
  assert.match(score, /economicModelScore: 20/u);
  assert.match(score, /liveReadinessScore: 0/u);
  assert.match(score, /overallScore: programOverallScore/u);
});
