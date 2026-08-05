import assert from 'node:assert/strict';
import { test } from 'bun:test';
import { readFile } from 'node:fs/promises';

const root = new URL('./', import.meta.url);

test('data evidence page exposes coverage corruption authority and sealed OOS', async () => {
  const source = await readFile(new URL('pages/evidence/DataEvidencePage.svelte', root), 'utf8');

  for (const token of ['데이터·증거', 'DIRECT METADATA', 'CORRUPT', 'PIT', 'EXTERNAL KRX AUTHORITY', 'FRESH OOS SEALED']) assert.ok(source.includes(token));
  assert.match(source, /loadResearchSummary/u);
  assert.match(source, /loadTelemetryRuns/u);
});

test('models page separates file presence loading promotion and Kronos availability', async () => {
  const source = await readFile(new URL('pages/models/ModelsArtifactsPage.svelte', root), 'utf8');

  for (const token of ['모델·산출물', 'FILE PRESENT', 'LOADED', 'PROMOTED', 'Kronos Core', '자동 승격 금지']) assert.ok(source.includes(token));
  assert.match(source, /loadResearchRunDetail/u);
  assert.match(source, /getV6ModelStatus/u);
  assert.match(source, /runSearch/u);
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
