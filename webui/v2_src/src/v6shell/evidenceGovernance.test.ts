import assert from 'node:assert/strict';
import { test } from 'bun:test';
import { readFile } from 'node:fs/promises';

const root = new URL('./', import.meta.url);

test('data evidence page exposes coverage corruption authority and sealed OOS', async () => {
  const source = await readFile(new URL('pages/evidence/DataEvidencePage.svelte', root), 'utf8');

  for (const token of ['데이터·증거', 'DIRECT METADATA', 'CORRUPT', 'PIT', 'EXTERNAL KRX AUTHORITY', 'FRESH OOS SEALED']) assert.ok(source.includes(token));
  assert.match(source, /loadResearchSummary/u);
  assert.match(source, /loadResearchRunDetail/u);
  assert.match(source, /loadTelemetryRuns/u);
  assert.match(source, /REPRODUCTION_ONLY_VALIDATION_CONSUMED/u);
  assert.match(source, /REPRODUCTION_MISMATCH_VALIDATION_CONSUMED/u);
  assert.match(source, /REPRO FAIL/u);
  for (const token of ['REPRODUCTION ONLY', 'MODEL FILES DISCOVERED', 'CQL 씨드별 비용 후 손익']) assert.ok(source.includes(token));
  assert.doesNotMatch(source, /BLOCKED 0 \/ 28,182/u);
  assert.match(source, /authorityD1/u);
  assert.match(source, /실제 키움 계좌 영수증이 아닙니다/u);
});

test('models page separates file presence loading promotion and Kronos availability', async () => {
  const source = await readFile(new URL('pages/models/ModelsArtifactsPage.svelte', root), 'utf8');

  for (const token of ['모델·산출물', 'FILE PRESENT', 'LOADED', 'PROMOTED', 'Kronos Core', '자동 승격 금지', 'VALIDATION CANDIDATE']) assert.ok(source.includes(token));
  assert.match(source, /loadResearchRunDetail/u);
  assert.match(source, /getV6ModelStatus/u);
  assert.match(source, /runSearch/u);
  assert.match(source, /const generation = \+\+detailGeneration/u);
  assert.match(source, /if \(generation !== detailGeneration\) return/u);
  assert.match(source, /if \(result\.ok === false\) \{[\s\S]*?detail = null;/u);
  assert.match(source, /REPRODUCTION_MISMATCH_VALIDATION_CONSUMED/u);
  assert.match(source, /REPRODUCTION FAILED/u);
});

test('governance page renders preregistration report hashes verdicts and human gate', async () => {
  const source = await readFile(new URL('pages/governance/ReportsGovernancePage.svelte', root), 'utf8');

  for (const token of ['보고서·거버넌스', 'PREREGISTRATION', 'SHA-256', 'NO-GO', 'FRESH OOS', 'HUMAN APPROVAL']) assert.ok(source.includes(token));
  assert.match(source, /getV6ProjectReports/u);
  assert.match(source, /loadGovernanceSummary/u);
  assert.doesNotMatch(source, /getV6ResearchRegistry/u);
});

test('unified shell maps evidence models and governance to independent pages', async () => {
  const shell = await readFile(new URL('V6Shell.svelte', root), 'utf8');

  for (const page of ['DataEvidencePage', 'ModelsArtifactsPage', 'ReportsGovernancePage']) assert.match(shell, new RegExp(`import ${page}`, 'u'));
  assert.match(shell, /page\.id === 'evidence'\}<DataEvidencePage/u);
  assert.match(shell, /page\.id === 'models'\}<ModelsArtifactsPage/u);
  assert.match(shell, /page\.id === 'governance'\}<ReportsGovernancePage/u);
  assert.doesNotMatch(shell, /page\.id === 'evidence'\}<InsightWorkspace/u);
  assert.doesNotMatch(shell, /page\.id === 'models'\}<KronosPage/u);
  assert.doesNotMatch(shell, /page\.id === 'governance'\}<RLWorkspace/u);
});
