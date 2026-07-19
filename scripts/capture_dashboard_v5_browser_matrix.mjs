#!/usr/bin/env node
/** Deterministic validator/normalizer for supplied V5 browser evidence. No browser is launched. */
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { readFile, writeFile } from 'node:fs/promises';
import { dirname, isAbsolute, relative, resolve, sep } from 'node:path';
import { inflateSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';

const SHA256 = (bytes) => createHash('sha256').update(bytes).digest('hex');
const die = (message) => { throw new Error(message); };
const BASE_TABS = Object.freeze(['mission-control', 'forecast', 'stom', 'daily-ohlcv', 'daily-rl-guide', 'rl', 'live-training', 'system-health', 'artifacts', 'history', 'settings', 'docs']);
const THEMES = Object.freeze(['light', 'dark']);
const WIDTHS = Object.freeze([375, 768, 1280]);
const LIFECYCLE = Object.freeze(['ADVANCING', 'STALLED', 'RESUMED', 'RESTARTED_NON_EXACT', 'STOPPED', 'FAILED', 'COMPLETED', 'CONFLICT_BLOCKED', 'NOT_RUN']);
const GOVERNANCE = Object.freeze(['D0_BLOCKED', 'D1_BLOCKED', 'FRESH_OOS_SEALED', 'FRESH_OOS_NOT_AVAILABLE', 'MISSING_CELL']);
const ASYNC_SECURITY = Object.freeze(['ISOLATED_TIMEOUT_RETRY', 'LATE_LIST_DETAIL_RACE', 'ALLOWED_DOWNLOAD', 'DENIED_DOWNLOAD']);
const KEYBOARD_TABS = Object.freeze(['mission-control', 'rl', 'daily-ohlcv', 'live-training']);
const FALSE_LOCKS = Object.freeze({ promotion_allowed: false, model_build_allowed: false, paper_forward_allowed: false, live_broker_order_allowed: false, profitability_claim_allowed: false, go_summary_allowed: false });
const CAPTURE_REQUIREMENTS = Object.freeze(['source_sha256', 'dist_manifest_sha256', 'fixture_sha256', 'browser_sha256', 'url', 'dom', 'screenshot', 'get_ledger', 'expected_isolated_post_probe', 'console_errors', 'page_errors', 'network_errors', 'overflow', 'wcag_a_aa', 'focus_trace', 'chart_table_semantics', 'timing']);
const PROHIBITED_CLAIMS = Object.freeze(['OOS_CONSUMED', 'LIVE_READY', 'PROFIT_READY', 'GO_READY']);
const EXPECTED_ISOLATED_POST_PROBE = Object.freeze({ method: 'POST', path: '/api/v5/jobs', payload: 'create-job', status: 405, accepted: false, side_effects: false });
const POST_PROBE_FIELDS = new Set(Object.keys(EXPECTED_ISOLATED_POST_PROBE));
const INPUT_FIELDS = new Set(['schema', 'capture_kind', 'live_browser_execution', 'nonce', 'browser_pid', 'browser_sha256', 'dist_manifest_sha256', 'fixture_ref', 'source_ref', 'scenarios']);
const ROW_FIELDS = new Set(['scenario_id', 'status', 'screenshot_ref', 'transcript_ref', 'console_errors', 'page_errors', 'network_errors', 'overflow', 'focus', 'keyboard', 'a11y', 'chart_table_semantics']);
const TRANSCRIPT_FIELDS = new Set(['schema', 'capture_kind', 'live_browser_execution', 'scenario_id', 'sequence', 'scenario', ...CAPTURE_REQUIREMENTS]);
const SCREENSHOT_FIELDS = new Set(['sha256', 'media_type', 'width', 'height']);
const DOM_FIELDS = new Set(['scenario_id', 'root', 'landmarks']);
const GET_LEDGER_FIELDS = new Set(['method', 'url', 'status', 'response_sha256']);
const TIMING_FIELDS = new Set(['navigation_start_ms', 'dom_content_loaded_ms', 'hydrated_ms']);

function args(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 2) {
    if (!argv[i]?.startsWith('--') || !argv[i + 1]) die('arguments must be --name value pairs');
    out[argv[i].slice(2)] = argv[i + 1];
  }
  return out;
}

function canonical(value) {
  if (value === null || typeof value === 'boolean' || typeof value === 'string') {
    if (typeof value === 'string' && /[\uD800-\uDFFF]/.test(value)) die('lone surrogate is not JCS');
    return JSON.stringify(value);
  }
  if (typeof value === 'number') {
    if (!Number.isSafeInteger(value)) die('only safe integer measurements are accepted');
    return String(value);
  }
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (!value || typeof value !== 'object') die('invalid JCS value');
  return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
}

function sameArray(actual, expected) {
  return Array.isArray(actual) && actual.length === expected.length && actual.every((value, index) => value === expected[index]);
}

function requireObject(value, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) die(`${label} must be an object`);
  return value;
}

function requireExactFields(value, fields, label) {
  const object = requireObject(value, label);
  const keys = Object.keys(object);
  if (keys.length !== fields.size || keys.some((key) => !fields.has(key))) die(`${label} fields are not canonical`);
  return object;
}

function rejectProhibitedClaims(value, label) {
  if (typeof value === 'string') {
    const upper = value.toUpperCase();
    const claim = PROHIBITED_CLAIMS.find((token) => upper.includes(token));
    if (claim) die(`${label} contains prohibited claim ${claim}`);
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => rejectProhibitedClaims(item, `${label}[${index}]`));
    return;
  }
  if (value && typeof value === 'object') {
    for (const [key, item] of Object.entries(value)) {
      rejectProhibitedClaims(key, `${label}.${key} key`);
      rejectProhibitedClaims(item, `${label}.${key}`);
    }
  }
}

function buildMatrix() {
  const ids = [];
  const metadata = new Map();
  const push = (id, scenario) => { ids.push(id); metadata.set(id, Object.freeze(scenario)); };
  for (const tab of BASE_TABS) for (const theme of THEMES) for (const width of WIDTHS) push(`S-BASE-${tab}-${theme}-${width}`, { group: 'BASE', tab, theme, width });
  for (const state of LIFECYCLE) for (const theme of THEMES) push(`S-LIFE-${state}-${theme}`, { group: 'LIFE', state, theme });
  for (const state of GOVERNANCE) for (const theme of THEMES) push(`S-GOV-${state}-${theme}`, { group: 'GOV', state, theme });
  for (const state of ASYNC_SECURITY) for (const theme of THEMES) push(`S-ASYNC-${state}-${theme}`, { group: 'ASYNC', state, theme });
  for (const tab of KEYBOARD_TABS) push(`S-KBD-${tab}`, { group: 'KBD', tab, keyboard_only: true, width: 375 });
  return { ids: Object.freeze(ids), metadata };
}

function loadCanonicalMatrix() {
  const matrixPath = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'docs', 'kronos_dashboard_v5_browser_matrix_v1.json');
  const matrix = JSON.parse(readFileSync(matrixPath, 'utf8'));
  const generated = buildMatrix();
  if (matrix.schema !== 'kronos_dashboard_v5_browser_matrix.v1' || matrix.scenario_count !== 112) die('canonical browser matrix metadata is invalid');
  if (!sameArray(matrix.base_tabs, BASE_TABS) || !sameArray(matrix.themes, THEMES) || !sameArray(matrix.widths, WIDTHS)) die('canonical browser matrix dimensions drifted');
  if (!sameArray(matrix.scenarios, generated.ids) || new Set(matrix.scenarios).size !== 112) die('canonical browser matrix scenarios drifted');
  if (!sameArray(matrix.capture_requirements, CAPTURE_REQUIREMENTS) || !sameArray(matrix.prohibited_claims, PROHIBITED_CLAIMS)) die('canonical browser matrix capture or claim contract drifted');
  return generated;
}

const CANONICAL = loadCanonicalMatrix();
export const SCENARIO_IDS = CANONICAL.ids;

function requireSha(value, name) {
  if (typeof value !== 'string' || !/^[a-f0-9]{64}$/.test(value)) die(`${name} must be a lowercase sha256`);
  return value;
}

function contained(root, rel) {
  if (typeof rel !== 'string' || !rel || rel.includes('\0') || rel.includes('\\') || rel.split('/').includes('..') || isAbsolute(rel)) die('ObjectRef relative_path is required');
  const target = resolve(root, rel);
  const distance = relative(root, target);
  if (distance === '..' || distance.startsWith('..' + sep) || isAbsolute(distance)) die(`ObjectRef escapes evidence root: ${rel}`);
  return target;
}

async function objectRef(root, claimed, expectedMedia) {
  if (!claimed || typeof claimed !== 'object' || Array.isArray(claimed)) die('ObjectRef is required');
  const allowed = new Set(['relative_path', 'sha256', 'byte_length', 'media_type', 'schema_id', 'captured_at']);
  if (Object.keys(claimed).some((key) => !allowed.has(key))) die('ObjectRef has an unknown field');
  const file = contained(root, claimed.relative_path);
  const bytes = await readFile(file);
  const actual = { relative_path: claimed.relative_path, sha256: SHA256(bytes), byte_length: bytes.length, media_type: expectedMedia };
  for (const key of ['sha256', 'byte_length', 'media_type']) if (claimed[key] !== actual[key]) die(`ObjectRef ${claimed.relative_path} has incorrect ${key}`);
  return actual;
}

function pngNonUniform(bytes) {
  if (bytes.subarray(0, 8).compare(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])) !== 0) die('screenshot is not PNG');
  let pos = 8;
  let width = 0;
  let height = 0;
  let depth = 0;
  let type = 0;
  const data = [];
  while (pos < bytes.length) {
    if (pos + 12 > bytes.length) die('truncated PNG chunk');
    const length = bytes.readUInt32BE(pos);
    const kind = bytes.toString('ascii', pos + 4, pos + 8);
    const chunk = bytes.subarray(pos + 8, pos + 8 + length);
    if (pos + 12 + length > bytes.length) die('truncated PNG chunk');
    pos += length + 12;
    if (kind === 'IHDR') { width = chunk.readUInt32BE(0); height = chunk.readUInt32BE(4); depth = chunk[8]; type = chunk[9]; }
    if (kind === 'IDAT') data.push(chunk);
    if (kind === 'IEND') break;
  }
  if (!width || !height || depth !== 8 || ![2, 6].includes(type) || !data.length) die('screenshot PNG must be 8-bit RGB/RGBA');
  const channels = type === 6 ? 4 : 3;
  const stride = width * channels;
  const raw = inflateSync(Buffer.concat(data));
  let offset = 0;
  let prev = Buffer.alloc(stride);
  const distinct = new Set();
  for (let y = 0; y < height; y += 1) {
    if (offset + 1 + stride > raw.length) die('truncated PNG image data');
    const filter = raw[offset++];
    const row = Buffer.from(raw.subarray(offset, offset + stride));
    offset += stride;
    for (let x = 0; x < stride; x += 1) {
      const left = x >= channels ? row[x - channels] : 0;
      const up = prev[x];
      const ul = x >= channels ? prev[x - channels] : 0;
      if (filter === 1) row[x] = (row[x] + left) & 255;
      else if (filter === 2) row[x] = (row[x] + up) & 255;
      else if (filter === 3) row[x] = (row[x] + Math.floor((left + up) / 2)) & 255;
      else if (filter === 4) {
        const p = left + up - ul;
        const pa = Math.abs(p - left);
        const pb = Math.abs(p - up);
        const pc = Math.abs(p - ul);
        row[x] = (row[x] + (pa <= pb && pa <= pc ? left : pb <= pc ? up : ul)) & 255;
      } else if (filter !== 0) die('invalid PNG filter');
    }
    for (let x = 0; x < row.length; x += channels) {
      distinct.add(row.subarray(x, x + channels).toString('hex'));
      if (distinct.size > 1) return { width, height };
    }
    prev = row;
  }
  die('screenshot PNG is uniform');
}

function isEmptyArray(value) {
  return Array.isArray(value) && value.length === 0;
}

function containsScenario(value, expected) {
  return typeof value === 'string' && (value.includes(expected) || value.includes(encodeURIComponent(expected)));
}

function validateTiming(value, expected) {
  const timing = requireExactFields(value, TIMING_FIELDS, `${expected}: transcript timing`);
  if (!Object.values(timing).every((item) => Number.isSafeInteger(item) && item >= 0)) die(`${expected}: transcript timing is invalid`);
  if (timing.dom_content_loaded_ms < timing.navigation_start_ms || timing.hydrated_ms < timing.dom_content_loaded_ms) die(`${expected}: transcript timing is not monotonic`);
}

function validateGetLedger(value, expected) {
  if (!Array.isArray(value) || value.length === 0) die(`${expected}: get_ledger must be a non-empty array`);
  let bound = false;
  value.forEach((rawEntry, index) => {
    const entry = requireExactFields(rawEntry, GET_LEDGER_FIELDS, `${expected}: get_ledger[${index}]`);
    if (entry.method !== 'GET' || !Number.isSafeInteger(entry.status) || entry.status < 200 || entry.status >= 400 || !containsScenario(entry.url, expected)) die(`${expected}: get_ledger[${index}] must be a successful scenario-bound GET`);
    requireSha(entry.response_sha256, `${expected}: get_ledger[${index}].response_sha256`);
    bound = true;
  });
  if (!bound) die(`${expected}: get_ledger is not bound to the scenario`);
}

function validateScreenshot(value, expected, screenshot, png) {
  const actual = requireExactFields(value, SCREENSHOT_FIELDS, `${expected}: transcript screenshot`);
  if (actual.sha256 !== screenshot.sha256 || actual.media_type !== 'image/png' || actual.width !== png.width || actual.height !== png.height) die(`${expected}: transcript screenshot binding is invalid`);
}

function validateDom(value, expected) {
  const dom = requireExactFields(value, DOM_FIELDS, `${expected}: transcript DOM`);
  if (dom.scenario_id !== expected || typeof dom.root !== 'string' || !dom.root) die(`${expected}: transcript DOM binding is invalid`);
  if (!Array.isArray(dom.landmarks) || dom.landmarks.length === 0 || dom.landmarks.some((item) => typeof item !== 'string' || !item)) die(`${expected}: transcript DOM landmarks are invalid`);
}

function validateExpectedPostProbe(value, expected) {
  const probe = requireExactFields(value, POST_PROBE_FIELDS, `${expected}: expected_isolated_post_probe`);
  for (const [key, expectedValue] of Object.entries(EXPECTED_ISOLATED_POST_PROBE)) if (probe[key] !== expectedValue) die(`${expected}: expected isolated POST probe is invalid`);
}

function validateTranscript(raw, expected, sequence, context, screenshot, png) {
  if (raw && typeof raw === 'object' && !Array.isArray(raw) && raw.request_errors !== undefined) die(`${expected}: transcript must use network_errors, not request_errors`);
  rejectProhibitedClaims(raw, `${expected}: transcript`);
  requireExactFields(raw, TRANSCRIPT_FIELDS, `${expected}: transcript`);
  if (raw.schema !== 'kronos_v5_browser_transcript.v1' || raw.capture_kind !== 'synthetic_fixture_evidence' || raw.live_browser_execution !== false) die(`${expected}: transcript identity is invalid`);
  if (raw.scenario_id !== expected || raw.sequence !== sequence) die(`${expected}: transcript scenario binding is invalid`);
  if (canonical(raw.scenario) !== canonical(CANONICAL.metadata.get(expected))) die(`${expected}: transcript scenario semantics are invalid`);
  if (raw.fixture_sha256 !== context.fixture_ref.sha256 || raw.source_sha256 !== context.source_ref.sha256 || raw.browser_sha256 !== context.browser_sha256 || raw.dist_manifest_sha256 !== context.dist_manifest_sha256) die(`${expected}: transcript hash binding is invalid`);
  validateScreenshot(raw.screenshot, expected, screenshot, png);
  if (!containsScenario(raw.url, expected)) die(`${expected}: transcript URL is not scenario-bound`);
  validateDom(raw.dom, expected);
  validateGetLedger(raw.get_ledger, expected);
  validateExpectedPostProbe(raw.expected_isolated_post_probe, expected);
  validateTiming(raw.timing, expected);
  for (const key of ['console_errors', 'page_errors', 'network_errors']) if (!isEmptyArray(raw[key])) die(`${expected}: transcript ${key} must be empty`);
  if (raw.overflow !== false || raw.wcag_a_aa !== 'passed' || raw.focus_trace !== 'passed' || raw.chart_table_semantics !== 'passed') die(`${expected}: transcript semantic checks failed`);
}

async function validateScenario(root, row, expected, sequence, context, seen) {
  if (!row || typeof row !== 'object' || Array.isArray(row)) die(`invalid scenario ${expected}`);
  const keys = Object.keys(row);
  if (keys.length !== ROW_FIELDS.size || keys.some((key) => !ROW_FIELDS.has(key))) die(`${expected}: scenario evidence fields are not canonical`);
  if (row.scenario_id !== expected || row.status !== 'passed') die(`invalid scenario ${expected}`);
  for (const key of ['console_errors', 'page_errors', 'network_errors']) if (!isEmptyArray(row[key])) die(`${expected}: ${key} must be empty`);
  if (row.overflow !== false || row.focus !== 'passed' || row.keyboard !== 'passed' || row.a11y !== 'passed' || row.chart_table_semantics !== 'passed') die(`${expected}: required semantic check failed`);
  const screenshot = await objectRef(root, row.screenshot_ref, 'image/png');
  const screenshotBytes = await readFile(contained(root, screenshot.relative_path));
  const png = pngNonUniform(screenshotBytes);
  const expectedMeta = CANONICAL.metadata.get(expected);
  if (Number.isSafeInteger(expectedMeta.width) && png.width !== expectedMeta.width) die(`${expected}: screenshot width ${png.width} does not match canonical width ${expectedMeta.width}`);
  const transcript = await objectRef(root, row.transcript_ref, 'application/json');
  for (const [kind, value] of [['screenshot sha', screenshot.sha256], ['screenshot path', screenshot.relative_path], ['transcript sha', transcript.sha256], ['transcript path', transcript.relative_path]]) {
    if (seen.has(value)) die(`${expected}: duplicate ${kind} is not scenario-specific`);
    seen.add(value);
  }
  let transcriptJson;
  try {
    transcriptJson = JSON.parse(await readFile(contained(root, transcript.relative_path), 'utf8'));
  } catch (error) {
    die(`${expected}: transcript is not valid JSON`);
  }
  validateTranscript(transcriptJson, expected, sequence, context, screenshot, png);
  return { scenario_id: expected, status: 'passed', screenshot_ref: screenshot, screenshot: png, transcript_ref: transcript, console_errors: [], page_errors: [], network_errors: [], overflow: false, focus: 'passed', keyboard: 'passed', a11y: 'passed', chart_table_semantics: 'passed' };
}

export async function produce(input, root) {
  rejectProhibitedClaims(input, 'input');
  requireExactFields(input, INPUT_FIELDS, 'input');
  if (input.schema !== 'kronos_v5_browser_input.v1' || input.capture_kind !== 'synthetic_fixture_evidence' || input.live_browser_execution !== false || !Array.isArray(input.scenarios)) die('input must be explicit synthetic fixture evidence with scenarios');
  if (!/^[a-f0-9]{64}$/.test(input.nonce) || !Number.isSafeInteger(input.browser_pid) || input.browser_pid <= 0) die('nonce/browser_pid is invalid');
  const browser_sha256 = requireSha(input.browser_sha256, 'browser_sha256');
  const dist_manifest_sha256 = requireSha(input.dist_manifest_sha256, 'dist_manifest_sha256');
  const fixture_ref = await objectRef(root, input.fixture_ref, 'application/json');
  const source_ref = await objectRef(root, input.source_ref, 'application/javascript');
  const ids = input.scenarios.map((row) => row?.scenario_id);
  if (ids.length !== SCENARIO_IDS.length || new Set(ids).size !== ids.length || ids.join('\n') !== SCENARIO_IDS.join('\n')) die('scenario matrix must be the ordered frozen 112 S-* IDs');
  const context = { fixture_ref, source_ref, browser_sha256, dist_manifest_sha256 };
  const seen = new Set();
  const scenarios = [];
  for (let i = 0; i < SCENARIO_IDS.length; i += 1) scenarios.push(await validateScenario(root, input.scenarios[i], SCENARIO_IDS[i], i + 1, context, seen));
  const result = { schema: 'kronos_v5_browser_capture.v1', capture_kind: 'synthetic_fixture_evidence', live_browser_execution: false, nonce: input.nonce, browser_pid: input.browser_pid, fixture_ref, source_ref, scenario_ids: Array.from(SCENARIO_IDS), scenario_count: SCENARIO_IDS.length, scenarios, false_locks: FALSE_LOCKS };
  return { ...result, capture_sha256: SHA256(canonical(result)) };
}

async function main() {
  const a = args(process.argv.slice(2));
  if (!a.input || !a['evidence-root'] || !a.out) die('usage: --input INPUT --evidence-root ROOT --out OUT');
  const root = resolve(a['evidence-root']);
  const input = JSON.parse(await readFile(a.input, 'utf8'));
  const result = await produce(input, root);
  await writeFile(a.out, `${canonical(result)}\n`, 'utf8');
}
function isMain() { return Boolean(process.argv[1]) && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url)); }
if (isMain()) main().catch((error) => { process.stderr.write(`capture failed closed: ${error.message}\n`); process.exitCode = 1; });
