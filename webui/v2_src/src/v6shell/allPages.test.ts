import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { V6_INSIGHT_SUBTABS, V6_PAGES, V6_RL_STEPS } from './registry';

test('all V6 navigation labels are readable Korean and current', () => {
  // Given / When
  const pageLabels = V6_PAGES.map((page) => page.labelKo);
  const stepLabels = V6_RL_STEPS.map((step) => step.labelKo);
  const insightLabels = V6_INSIGHT_SUBTABS.map((tab) => tab.labelKo);

  // Then
  assert.deepEqual(pageLabels, ['통합 현황', '연구 라이브러리', '실시간 학습', '평가·비교', '데이터·증거', '모델·산출물', '보고서·거버넌스', '설정']);
  assert.deepEqual(stepLabels, ['RL 발견 실험실', '데이터', '실험 설계', '학습', '평가', '비교', '보고서']);
  assert.deepEqual(insightLabels, ['종목 관찰', '수급 흐름', '시장 국면']);
});

test('every official V6 page uses the common page header grammar', async () => {
  // Given
  const sources = await Promise.all([
    './pages/command/CommandCenterPage.svelte', './pages/research/ResearchLibraryPage.svelte',
    './pages/live/LiveTrainingPage.svelte', './pages/evaluation/EvaluationWorkspace.svelte',
    './pages/evidence/DataEvidencePage.svelte', './pages/models/ModelsArtifactsPage.svelte',
    './pages/governance/ReportsGovernancePage.svelte', './pages/settings/UnifiedSettingsPage.svelte',
  ].map((path) => readFile(new URL(path, import.meta.url), 'utf8')));

  // When / Then
  for (const source of sources) assert.match(source, /PageHeader/u);
});

test('shell and independent workspaces contain no legacy mojibake markers', async () => {
  // Given
  const source = (await Promise.all([
    './V6Shell.svelte', './pages/command/CommandCenterPage.svelte',
    './pages/research/ResearchLibraryPage.svelte', './pages/live/LiveTrainingPage.svelte',
    './pages/evaluation/EvaluationWorkspace.svelte', './pages/evidence/DataEvidencePage.svelte',
    './pages/models/ModelsArtifactsPage.svelte', './pages/governance/ReportsGovernancePage.svelte',
    './pages/settings/UnifiedSettingsPage.svelte',
  ].map((path) => readFile(new URL(path, import.meta.url), 'utf8')))).join('\n');

  // When / Then
  assert.doesNotMatch(source, /(?:媛|紐|醫|寃)/u);
});
