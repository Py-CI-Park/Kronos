import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const componentSource = readFileSync(new URL('./V51ResearchEvidence.svelte', import.meta.url), 'utf8');
const rlTradingTabSource = readFileSync(new URL('../RLTradingTab.svelte', import.meta.url), 'utf8');

function assertContainsAll(source: string, values: readonly string[]): void {
  for (const value of values) assert.ok(source.includes(value), `missing ${value}`);
}

test('V5.1 research evidence is shell-v5-only and preserves the existing RL tab body', () => {
  assert.match(rlTradingTabSource, /import \{ dashboardShell, type DashboardShell \} from '\$lib\/shellMode';/);
  assert.match(rlTradingTabSource, /import V51ResearchEvidence from '\.\/rlTrading\/V51ResearchEvidence\.svelte';/);
  assert.match(rlTradingTabSource, /\{#if shell === 'v5'\}\s*<V51ResearchEvidence \/>\s*\{\/if\}/);
  assert.match(rlTradingTabSource, /<RunSelector\s+runs=\{runs\}\s+multi/);
});

test('component fetches the five read-only v51Api research routes and no legacy RL route', () => {
  assertContainsAll(componentSource, [
    'v51Api.sourceCoverage()',
    'v51Api.causalPanel()',
    'v51Api.accounting()',
    'v51Api.evaluator()',
    'v51Api.benchmarkOverlay()',
    'READ_ONLY',
    'GET only',
  ]);
  assert.doesNotMatch(componentSource, /rlApi\./);
  assert.equal(componentSource.toLowerCase().includes('rule baseline rl'), false);
});

test('labels keep exact V5.1 no-claim source, accounting, horizon, and cost truths visible', () => {
  assertContainsAll(componentSource, [
    '15:20_bar_close_proxy',
    'false / not official close',
    'Missing bars',
    'MISSING_1520_BAR_BLOCKS_ROW_NO_NEAREST_FALLBACK',
    '60M KRW initial capital',
    '10 slots',
    '5M KRW slot budget',
    '10M KRW reserve cash',
    'H1 primary · H3/H5 validation',
    'cost_00bp → 0.00%',
    'base_23bp → 0.23%',
    'stress_46bp → 0.46%',
    'six-digit',
    'pykrx offline only',
    'Naver disabled',
    'RULE comparison only · NOT RL',
  ]);
});

test('normalized-100 overlay transformation preserves KOSPI/KOSDAQ/RL order and blocked fallback', () => {
  assert.match(componentSource, /export const V51_OVERLAY_SERIES = \['KOSPI', 'KOSDAQ', 'RL_PORTFOLIO'\] as const;/);
  assert.match(componentSource, /export function toOverlayRows\(overlay: V51BenchmarkOverlayRoot \| null\)/);
  assert.match(componentSource, /seriesById\.get\(seriesId\) \?\? null/);
  assert.match(componentSource, /sourceState = series\?\.source_state \?\? 'BLOCKED_INDEX_SERIES_SOURCE'/);
  assert.match(componentSource, /index100Value: series\?\.index_100 \?\? null/);
  assert.match(componentSource, /index100Display: series\?\.index_100 == null \? blockedDisplay : formatIndex100\(series\.index_100\)/);
  assert.match(componentSource, /data-v51-overlay-blocked-fallback/);
  assert.match(componentSource, /Accessible fallback table for KOSPI, KOSDAQ, and RL normalized-100 overlay/);
});

test('six false locks and six no-claim flags fail closed with NOT_RUN fallback', () => {
  assertContainsAll(componentSource, [
    'promotion_allowed',
    'model_build_allowed',
    'paper_forward_allowed',
    'live_broker_order_allowed',
    'profitability_claim_allowed',
    'go_summary_allowed',
    'official_close_claim',
    'paper_forward_claim',
    'live_trading_claim',
    'broker_integration_claim',
    'profitability_claim',
    'go_readiness_claim',
    'root ? String(root.locks[key]) : \'NOT_RUN\'',
    'root ? String(root.claims[key]) : \'NOT_RUN\'',
    'NO-GO / BLOCKED',
    'NOT_RUN / NO-GO',
  ]);
});
