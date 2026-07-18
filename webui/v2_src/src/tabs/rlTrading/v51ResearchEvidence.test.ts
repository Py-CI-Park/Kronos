import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const componentSource = readFileSync(new URL('./V51ResearchEvidence.svelte', import.meta.url), 'utf8');
const rlTradingTabSource = readFileSync(new URL('../RLTradingTab.svelte', import.meta.url), 'utf8');
const dailyRlGuideTabSource = readFileSync(new URL('../DailyRlGuideTab.svelte', import.meta.url), 'utf8');
const rightDetailRailSource = readFileSync(new URL('../../layout/RightDetailRail.svelte', import.meta.url), 'utf8');
const dailyOhlcvTabSource = readFileSync(new URL('../DailyOhlcvTab.svelte', import.meta.url), 'utf8');
const dailyVisualLabCardSource = readFileSync(new URL('../dailyOhlcv/DailyVisualLabCard.svelte', import.meta.url), 'utf8');

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
    'zero_control_0bp → 0.00%',
    'base_23bp → 0.23%',
    'stress_46bp → 0.46%',
    'six-digit',
    'pykrx offline only',
    'Naver disabled',
    'RULE comparison only · NOT RL',
  ]);
});

test('daily guide source markers use 15:20 H1/H3/H5 labels and fail-closed tones', () => {
  assertContainsAll(dailyRlGuideTabSource, [
    "const H1520_PROXY_LABEL = 'H1: D 15:20 → D+1 exact 15:20 · future_return_h1_1520_proxy / H3: D 15:20 → D+3 exact 15:20 · future_return_h3_1520_proxy / H5: D 15:20 → D+5 exact 15:20 · future_return_h5_1520_proxy';",
    "const H1520_PROXY_DETAIL = 'exact 15:20 proxy labels; H1 primary · H3/H5 validation · price_basis=15:20_bar_close_proxy';",
    '보상 label marker: {H1520_PROXY_LABEL} ({H1520_PROXY_DETAIL}).',
    'legacy ' + 'future_return_' + '1d' + ' is forbidden in state observations',
    "if (normalized === 'PASS') return 'pass';",
    "normalized.includes('MISSING')",
    "normalized.includes('INCOMPLETE')",
  ]);
  assert.doesNotMatch(dailyRlGuideTabSource, new RegExp('보상 label marker: future_return_' + '1d'));
  assert.doesNotMatch(dailyRlGuideTabSource, new RegExp('다음날 ' + '연구용 ' + 'future_return_' + '1d'));
  assert.doesNotMatch(dailyRlGuideTabSource, /normalized === 'PASS' \|\| normalized === 'INPUT'/);
  assertContainsAll(dailyRlGuideTabSource, [
    'RESEARCH_ONLY_GUIDE',
    'READ_ONLY_WORKFLOW_CATALOG',
    'UNAVAILABLE_FROM_READ_ONLY_DASHBOARD',
    'V51_CONTRACT_INITIAL_CAPITAL_KRW = 60000000',
  ]);
  assert.doesNotMatch(dailyRlGuideTabSource, new RegExp('RL_ENV_VISUAL_GUIDE_' + 'MVP'));
  assert.doesNotMatch(dailyRlGuideTabSource, new RegExp('APP' + 'ROVED_FOR_RESEARCH_' + 'INTENT'));
  assert.doesNotMatch(dailyRlGuideTabSource, new RegExp('POST /api/daily-ohlcv/research-' + 'workflows'));
  assert.doesNotMatch(dailyRlGuideTabSource, new RegExp("display_capital_krw'\\) \\?\\? " + '100000' + '00'));
});

test('daily guide missing replay/performance evidence does not render optimistic placeholders', () => {
  assertContainsAll(dailyRlGuideTabSource, [
    "const MISSING_ACTION_EVIDENCE = 'MISSING_ACTION_EVIDENCE';",
    "if (typeof value === 'number') return Number.isFinite(value) ? value : null;",
    "if (typeof value !== 'string') return null;",
    "if (trimmed === '') return null;",
    "return action === '' ? MISSING_ACTION_EVIDENCE : action;",
    "action<br />{frameActionExecuted()}",
    '<h3>{frameActionExecuted()}</h3>',
    'const signedMetricTone = (value: unknown): string => {',
    'const numeric = numberValue(value);',
    "if (numeric === null) return 'warn';",
    "return numeric < 0 ? 'danger' : 'pass';",
    "const performanceCardTone = (card: Record<string, unknown>): string => signedMetricTone(field(card, 'total_return_pct'));",
    "data-tone={signedMetricTone(field(row, 'total_reward'))}",
    'data-card-tone={performanceCardTone(card)}',
    ".performance-card[data-card-tone='warn']",
  ]);
  assert.doesNotMatch(dailyRlGuideTabSource, /\?\? 'hold'/);
  assert.doesNotMatch(dailyRlGuideTabSource, /frameActionExecuted\(\) === '—'/);
  assert.doesNotMatch(dailyRlGuideTabSource, /data-card-tone=\{numberValue\(field\(card, 'total_return_pct'\)\) !== null && Number\(field\(card, 'total_return_pct'\)\) < 0 \? 'danger' : 'pass'\}/);
  assert.doesNotMatch(dailyRlGuideTabSource, /data-tone=\{numberValue\(field\(row, 'total_reward'\)\) !== null/);
});

test('dashboard cost wording is percent-first with bp only secondary or internal', () => {
  assertContainsAll(rlTradingTabSource, [
    '0.23% (23 bp) cost gate',
    'selected verdict, 0.23% (23 bp) cost',
  ]);
  assertContainsAll(dailyRlGuideTabSource, [
    '0.23% (23 bp)',
    'cost sensitivity: {formatCostBpList',
    'reward labels are H1: D 15:20 → D+1 exact 15:20 · future_return_h1_1520_proxy / H3: D 15:20 → D+3 exact 15:20 · future_return_h3_1520_proxy / H5: D 15:20 → D+5 exact 15:20 · future_return_h5_1520_proxy only',
  ]);
  assertContainsAll(rightDetailRailSource, [
    'aria-label="User-facing cost percentages with internal cost IDs"',
    '<li><span>{cost.display_percent}</span><code>{cost.internal_id} · {cost.round_trip_cost_bp} bp</code></li>',
    "label: 'D 15:20 → D+1 exact 15:20'",
    "label: 'D 15:20 → D+3 exact 15:20'",
    "label: 'D 15:20 → D+5 exact 15:20'",
    'exact D+N 15:20 proxy exits',
  ]);
  assertContainsAll(dailyOhlcvTabSource, [
    "value: '0.23% (23 bp)'",
    'account envelope · 0.23% base cost (base_23bp)',
    '0.00% ({v51DailyProtocol.cost_schedule.zero_cost_control.internal_id})',
    '0.23% ({v51DailyProtocol.cost_schedule.primary.internal_id})',
    '0.46% ({v51DailyProtocol.cost_schedule.stress_control.internal_id})',
    'display_percent} · {v51AccountingState.data.accounting.cost_schedule.primary.internal_id} · {v51AccountingState.data.accounting.cost_schedule.primary.round_trip_cost_bp} bp',
  ]);
  assertContainsAll(dailyVisualLabCardSource, [
    'const bpCost = (value: unknown)',
    'bpCost(cost.cost_bp)',
  ]);
});

test('visual diagnostics fail closed instead of optimistic placeholder readiness', () => {
  assert.doesNotMatch(dailyVisualLabCardSource, new RegExp('PLACEHOLDER_' + 'READY'));
  assertContainsAll(dailyVisualLabCardSource, [
    "status: 'MISSING_ARTIFACT'",
    "status: 'NOT_STARTED'",
    "status: 'BLOCKED'",
    "status === 'MISSING_ARTIFACT'",
    "status === 'NOT_STARTED'",
    "status.includes('INCOMPLETE')",
    'next action: {item.next_action}',
    '.term-card.warn',
    '.term-card.danger',
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
