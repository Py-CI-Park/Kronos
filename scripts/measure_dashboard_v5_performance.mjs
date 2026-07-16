#!/usr/bin/env node
/** Deterministic reduction and budget gate for caller-supplied fixture measurements. */
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const BUDGETS_MS = Object.freeze({ first_critical_cold_ms: 3000, first_critical_warm_ms: 1500, full_hydration_cold_ms: 10000, full_hydration_warm_ms: 6000, api_cold_ms: 5000, api_warm_ms: 2000, isolated_timeout_ms: 20500, palette_ms: 100, filter_1000_ms: 150 });
const sha256 = (value) => createHash('sha256').update(value).digest('hex');
const fail = (message) => { throw new Error(message); };
function canonical(value) { if (value === null || typeof value === 'boolean' || typeof value === 'string') return JSON.stringify(value); if (typeof value === 'number') { if (!Number.isSafeInteger(value) || value < 0) fail('measurements must be non-negative safe integer milliseconds'); return String(value); } if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`; if (!value || typeof value !== 'object') fail('invalid JCS value'); return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`; }
function parse(argv) { const result = {}; for (let i = 0; i < argv.length; i += 2) { if (!argv[i]?.startsWith('--') || !argv[i + 1]) fail('arguments must be --name value pairs'); result[argv[i].slice(2)] = argv[i + 1]; } return result; }
export function nearestRankP95(samples) { if (!Array.isArray(samples) || !samples.length || !samples.every(Number.isSafeInteger)) fail('samples must be non-empty integer milliseconds'); return [...samples].sort((a, b) => a - b)[Math.ceil(samples.length * 0.95) - 1]; }
function reducedSeries(series, count, label) { if (!series || typeof series !== 'object' || !Array.isArray(series.discarded_warmup) || series.discarded_warmup.length !== 1 || !Array.isArray(series.samples) || series.samples.length !== count) fail(`${label} requires one discarded warmup and ${count} samples`); return nearestRankP95(series.samples); }
export function produce(input) {
  if (!input || input.schema !== 'kronos_v5_performance_input.v1' || input.capture_kind !== 'synthetic_fixture_evidence' || input.live_browser_execution !== false) fail('only explicitly synthetic fixture evidence is accepted by this producer');
  if (!/^[a-f0-9]{64}$/.test(input.nonce) || !/^[a-f0-9]{64}$/.test(input.fixture_sha256) || !/^[a-f0-9]{64}$/.test(input.source_sha256)) fail('nonce and input hashes must be sha256');
  const m = input.measurements; if (!m || typeof m !== 'object') fail('measurements is required');
  const p95 = {
    first_critical_cold_ms: reducedSeries(m.first_critical_cold, 5, 'first_critical_cold'),
    first_critical_warm_ms: reducedSeries(m.first_critical_warm, 10, 'first_critical_warm'),
    full_hydration_cold_ms: reducedSeries(m.full_hydration_cold, 5, 'full_hydration_cold'),
    full_hydration_warm_ms: reducedSeries(m.full_hydration_warm, 10, 'full_hydration_warm'),
    api_cold_ms: reducedSeries(m.api_cold, 10, 'api_cold'),
    api_warm_ms: reducedSeries(m.api_warm, 10, 'api_warm'),
    isolated_timeout_ms: reducedSeries(m.isolated_timeout, 10, 'isolated_timeout'),
    palette_ms: reducedSeries(m.palette, 10, 'palette'),
    filter_1000_ms: reducedSeries(m.filter_1000, 10, 'filter_1000'),
  };
  if (m.retry_visible !== true) fail('retry must be visibly rendered');
  const failures = Object.entries(BUDGETS_MS).filter(([name, budget]) => p95[name] > budget).map(([name]) => name);
  if (failures.length) fail(`performance budget exceeded: ${failures.join(',')}`);
  const result = { schema: 'kronos_v5_performance_result.v1', capture_kind: 'synthetic_fixture_evidence', live_browser_execution: false, nonce: input.nonce, fixture_sha256: input.fixture_sha256, source_sha256: input.source_sha256, measurement_sha256: sha256(canonical(m)), sample_contract: { cold_contexts: 5, warm_samples_after_discarded_warmup: 10, endpoint_calls_after_discarded_warmup: 10, percentile: 'nearest-rank-p95' }, budgets_ms: BUDGETS_MS, p95_ms: p95, retry_visible: true, status: 'passed' };
  return { ...result, result_sha256: sha256(canonical(result)) };
}
async function main() { const a = parse(process.argv.slice(2)); if (!a.input || !a.out) fail('usage: --input INPUT --out OUT'); const result = produce(JSON.parse(await readFile(a.input, 'utf8'))); await writeFile(a.out, `${canonical(result)}\n`, 'utf8'); }
function isMain() { return Boolean(process.argv[1]) && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url)); }
if (isMain()) main().catch((error) => { process.stderr.write(`performance failed closed: ${error.message}\n`); process.exitCode = 1; });
