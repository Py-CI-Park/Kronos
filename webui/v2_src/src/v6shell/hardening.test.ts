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

test('system status distinguishes created checkpoints from an economic GO model', async () => {
  const rail = await readFile(new URL('./components/shell/SystemStatusRail.svelte', import.meta.url), 'utf8');
  const safety = await readFile(new URL('./V6SafetyStrip.svelte', import.meta.url), 'utf8');

  assert.match(rail, /경제성 통과 모델 없음/u);
  assert.match(rail, /PRIOR TEST: NO-GO/u);
  assert.match(rail, /TEST FEATURES CONSUMED/u);
  assert.match(rail, /001 VAL CONSUMED ≠ GO/u);
  assert.match(rail, /002 CUSTODY REPRO/u);
  assert.doesNotMatch(rail, /· 미생성/u);
  assert.match(safety, /이전 이진 DQN\/CQL 20개/u);
  assert.match(safety, /4행동 001\/002도 TEST feature를 파싱/u);
  assert.match(safety, /보상·체결만 미열람/u);
});

test('live telemetry pairs each response with the selected run and handles an empty catalog', async () => {
  const live = await readFile(new URL('./pages/live/LiveTrainingPage.svelte', import.meta.url), 'utf8');

  assert.match(live, /const requestedId = selected/u);
  assert.match(live, /const generation = \+\+refreshGeneration/u);
  assert.match(live, /generation !== refreshGeneration \|\| requestedId !== selected/u);
  assert.match(live, /if \(!selected\) \{[\s\S]*?loading = false;/u);
  assert.match(live, /runStatusTone/u);
});

test('desktop sidebar clips hover motion without creating a horizontal scrollbar', async () => {
  const sidebar = await readFile(new URL('./components/shell/UnifiedSidebar.svelte', import.meta.url), 'utf8');

  assert.match(sidebar, /nav\{[^}]*overflow-y:auto[^}]*overflow-x:clip/u);
  assert.match(sidebar, /@media\(max-width:680px\)[\s\S]*?\.sidebar nav\{[^}]*overflow-x:auto/u);
});
