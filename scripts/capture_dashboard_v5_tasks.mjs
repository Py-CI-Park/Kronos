#!/usr/bin/env node
/** Deterministic synthetic V5 task capture; it never launches a browser. */
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";

const FAILURE_CODES = Object.freeze(["TIMEOUT", "WRONG_RUN", "SOURCE_INSPECTION", "PRODUCER_HELP", "ACTION_LIMIT", "MISSING_TRACE", "INVALID_ASSIGNMENT", "RELOAD_NOT_REQUESTED", "OBJECTIVE_MISMATCH"]);
const TASK_IDS = Object.freeze(Array.from({ length: 10 }, (_, index) => `T${String(index + 1).padStart(2, "0")}`));
const DIMENSIONS = Object.freeze(["U", "L", "J"]);
const CAPTURE_KIND = "synthetic_fixture_evidence";
const LIVE_BROWSER_EXECUTION = false;
const DIMENSION_KEYSET = [...DIMENSIONS].sort().join(",");
const INSTRUMENT_PATH = resolve(dirname(fileURLToPath(import.meta.url)), "../docs/kronos_dashboard_v5_usability_instrument_v1.json");
const usage = "usage: capture_dashboard_v5_tasks.mjs --fixture FILE --operator A|B --evidence-dir DIR --out FILE";
const sha = raw => createHash("sha256").update(raw).digest("hex");
function jcs(value) {
  if (value === null || typeof value === "boolean" || typeof value === "number" || typeof value === "string") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(jcs).join(",")}]`;
  if (typeof value === "object") return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${jcs(value[key])}`).join(",")}}`;
  throw new Error("non-JSON value");
}
const bytes = value => Buffer.from(jcs(value), "utf8");
function ref(raw, uri, schema) { return { uri, sha256: sha(raw), byte_length: raw.length, schema }; }
function same(value, expected) { return jcs(value) === jcs(expected); }
function requireRef(value, expected, label) {
  if (!same(value, expected)) fail(`${label} ref does not bind canonical ${expected.schema} bytes`);
}
function requireRunNonce(value) {
  if (typeof value !== "string" || !/^[A-Za-z0-9_-]{43}$/.test(value)) fail("fixture run nonce is invalid");
}
function requireSyntheticTraceLabels(value, label) {
  if (value?.capture_kind !== CAPTURE_KIND || value?.live_browser_execution !== LIVE_BROWSER_EXECUTION) fail(`${label} must declare synthetic fixture evidence with no live browser execution`);
}
function instrumentWrapper(instrument, runNonce) {
  const rawRef = ref(instrument.raw, `kronos-run://${runNonce}/instrument/usability-v1.json`, "kronos_dashboard_v5_usability_instrument.v1");
  const value = { schema: "kronos_instrument.v2", kind: "dashboard-v5-usability-instrument", instrument_ref: rawRef, objective_failure_codes: [...FAILURE_CODES], task_ids: [...TASK_IDS] };
  const raw = bytes(value);
  return { value, raw, rawRef, ref: ref(raw, `kronos-run://${runNonce}/instrument`, "kronos_instrument.v2") };
}
function fixtureContent(fixture) {
  const { fixture_ref, ...content } = fixture;
  return content;
}
function fixtureDescriptor(fixture, instrumentRef) {
  const content = fixtureContent(fixture);
  const contentRaw = bytes(content);
  const value = { schema: "kronos_fixture.v2", capture_kind: CAPTURE_KIND, live_browser_execution: LIVE_BROWSER_EXECUTION, kind: "synthetic-dashboard-v5-task-fixture", run_nonce: fixture.run_nonce, instrument_ref: instrumentRef, task_fixture_ref: ref(contentRaw, `kronos-run://${fixture.run_nonce}/fixture/task-fixture.json`, "kronos_task_fixture.v2"), operator_indices: ["A", "B"], task_ids: [...TASK_IDS] };
  const raw = bytes(value);
  return { content, contentRaw, value, raw, ref: ref(raw, `kronos-run://${fixture.run_nonce}/fixture`, "kronos_fixture.v2") };
}
function crc32(raw) { let c = 0xffffffff; for (const b of raw) { c ^= b; for (let n = 0; n < 8; n++) c = (c >>> 1) ^ (0xedb88320 & -(c & 1)); } return (c ^ 0xffffffff) >>> 0; }
function chunk(type, data) { const out = Buffer.alloc(12 + data.length); out.writeUInt32BE(data.length, 0); out.write(type, 4, 4, "ascii"); data.copy(out, 8); out.writeUInt32BE(crc32(out.subarray(4, 8 + data.length)), 8 + data.length); return out; }
function png(seed) { // Two different RGB pixels: valid, non-uniform PNG evidence.
  const pixels = Buffer.from([0, seed, 255 - seed, (seed * 29) % 256, seed ^ 0xa5, 31, 255 - ((seed * 13) % 256)]);
  return Buffer.concat([Buffer.from("89504e470d0a1a0a", "hex"), chunk("IHDR", Buffer.from([0,0,0,2,0,0,0,1,8,2,0,0,0])), chunk("IDAT", deflateSync(pixels)), chunk("IEND", Buffer.alloc(0))]);
}
function fail(message) { throw new Error(message); }
function argumentsMap(argv) { const result = {}; for (let i = 0; i < argv.length; i += 2) { if (!argv[i]?.startsWith("--") || argv[i + 1] === undefined) fail(usage); result[argv[i].slice(2)] = argv[i + 1]; } return result; }
function iso(second) { return `2026-07-15T00:00:${String(second).padStart(2, "0")}Z`; }
function isFact(value) {
  return value && typeof value === "object" && !Array.isArray(value) && Object.keys(value).sort().join(",") === "code,detail" && typeof value.code === "string" && value.code.length > 0 && typeof value.detail === "string" && value.detail.length > 0;
}
function factList(facts) {
  return DIMENSIONS.map(dimension => facts[dimension]);
}
function frozenInstrument() {
  const raw = readFileSync(INSTRUMENT_PATH);
  const instrument = JSON.parse(raw.toString("utf8"));
  if (instrument.schema !== "kronos_dashboard_v5_usability_instrument.v1" || jcs(instrument.objective_failure_codes) !== jcs(FAILURE_CODES)) fail("frozen instrument failure enum is not G002 canonical");
  if (!Array.isArray(instrument.tasks) || instrument.tasks.map(task => task.id).join(",") !== TASK_IDS.join(",")) fail("frozen instrument tasks are not ordered T01 through T10");
  const max_actions = instrument.tasks.map(task => task.max_actions);
  if (!max_actions.every(value => Number.isInteger(value) && value >= 0)) fail("frozen instrument max actions are invalid");
  const task_specs = {};
  const expected_facts = {};
  for (const task of instrument.tasks) {
    if (!task.facts || Object.keys(task.facts).sort().join(",") !== DIMENSION_KEYSET || !factList(task.facts).every(isFact)) fail("frozen instrument expected facts are invalid");
    task_specs[task.id] = { surface: task.surface, viewport: task.viewport };
    expected_facts[task.id] = task.facts;
  }
  return { raw, spec: { task_ids: [...TASK_IDS], max_actions, objective_failure_codes: [...FAILURE_CODES] }, expected_facts, task_specs };
}
function declaredFailures(spec) {
  const values = spec.failure_codes ?? [];
  if (!Array.isArray(values)) fail("task failure codes must be an array");
  const seen = new Set();
  for (const code of values) {
    if (!FAILURE_CODES.includes(code) || seen.has(code)) fail("task failure codes are not the exact G002 enum");
    seen.add(code);
  }
  return values;
}
function validateFixture(fixture, instrument, instrumentObject, fixtureObject) {
  if (fixture.schema !== "kronos_task_fixture.v2" || !fixture.operators?.A || !fixture.operators?.B || !Array.isArray(fixture.tasks)) fail("fixture is not the frozen ten-task V5 fixture");
  requireRunNonce(fixture.run_nonce);
  requireSyntheticTraceLabels(fixture, "fixture trace labels");
  if (fixture.tasks.map(task => task.task_id).join(",") !== TASK_IDS.join(",")) fail("fixture tasks are not ordered T01 through T10");
  if (jcs(fixture.instrument_spec) !== jcs(instrument.spec)) fail("fixture instrument spec does not match the frozen instrument");
  requireRef(fixture.instrument_ref, instrumentObject.ref, "fixture instrument");
  requireRef(fixture.fixture_ref, fixtureObject.ref, "fixture descriptor");
  fixture.tasks.forEach((task, index) => {
    if (task.max_actions !== instrument.spec.max_actions[index]) fail("fixture max actions do not match the frozen instrument");
    if (!task.submissions || Object.keys(task.submissions).sort().join(",") !== DIMENSION_KEYSET || jcs(task.submissions) !== jcs(instrument.expected_facts[task.task_id])) fail("fixture task submissions do not match frozen expected facts");
    declaredFailures(task);
  });
}
function main() {
  const args = argumentsMap(process.argv.slice(2));
  if (!args.fixture || !args.operator || !args["evidence-dir"] || !args.out || !["A", "B"].includes(args.operator)) fail(usage);
  const instrument = frozenInstrument();
  const fixture = JSON.parse(readFileSync(resolve(args.fixture), "utf8"));
  requireRunNonce(fixture.run_nonce);
  requireSyntheticTraceLabels(fixture, "fixture trace labels");
  const instrumentObject = instrumentWrapper(instrument, fixture.run_nonce);
  const fixtureObject = fixtureDescriptor(fixture, instrumentObject.ref);
  validateFixture(fixture, instrument, instrumentObject, fixtureObject);
  const root = resolve(args["evidence-dir"]); mkdirSync(root, { recursive: true });
  for (const raw of [instrument.raw, instrumentObject.raw, fixtureObject.contentRaw, fixtureObject.raw]) writeFileSync(join(root, sha(raw)), raw);
  const operator = fixture.operators[args.operator];
  const base = args.operator === "A" ? 1 : 31;
  const tasks = fixture.tasks.map((spec, index) => {
    const started_at = iso(base + index * 2), completed_at = iso(base + index * 2 + 1);
    const actions = spec.actions ?? ["navigate", "submit"];
    if (!Array.isArray(actions) || actions.some(action => typeof action !== "string")) fail("task actions are invalid");
    const expected_facts = factList(instrument.expected_facts[spec.task_id]);
    const submitted_facts = spec.submitted_facts ?? expected_facts;
    if (!Array.isArray(submitted_facts) || !submitted_facts.every(isFact)) fail("submitted facts are invalid");
    const failures = new Set(declaredFailures(spec));
    if (actions.length > spec.max_actions) failures.add("ACTION_LIMIT");
    if (actions.includes("source_inspection")) failures.add("SOURCE_INSPECTION");
    if (actions.includes("producer_help")) failures.add("PRODUCER_HELP");
    if (actions.includes("reload") && !spec.reload_requested) failures.add("RELOAD_NOT_REQUESTED");
    if (jcs(submitted_facts) !== jcs(expected_facts)) failures.add("OBJECTIVE_MISMATCH");
    const failure_codes = FAILURE_CODES.filter(code => failures.has(code));
    const trace = { schema: "kronos_task_trace.v2", capture_kind: CAPTURE_KIND, live_browser_execution: LIVE_BROWSER_EXECUTION, operator_index: args.operator, task_id: spec.task_id, started_at, completed_at, actions, submitted_facts, objective_valid: failure_codes.length === 0, failure_codes };
    const traceRaw = bytes(trace), traceUri = `kronos-run://${fixture.run_nonce}/evidence/${args.operator}/${spec.task_id}.trace.json`;
    writeFileSync(join(root, sha(traceRaw)), traceRaw);
    const image = png(base + index), imageUri = `kronos-run://${fixture.run_nonce}/evidence/${args.operator}/${spec.task_id}.png`;
    writeFileSync(join(root, sha(image)), image);
    const screenshot = { schema: "kronos_screenshot.v2", png_ref: ref(image, imageUri, "image/png"), dimensions: { width: 2, height: 1 }, scenario: { operator_index: args.operator, task_id: spec.task_id, surface: instrument.task_specs[spec.task_id].surface, viewport: instrument.task_specs[spec.task_id].viewport } };
    const screenshotRaw = bytes(screenshot), screenshotUri = `kronos-run://${fixture.run_nonce}/evidence/${args.operator}/${spec.task_id}.screenshot.json`;
    writeFileSync(join(root, sha(screenshotRaw)), screenshotRaw);
    return { task_id: spec.task_id, started_at, completed_at, elapsed_ms: 1000, action_count: actions.length, objective_valid: failure_codes.length === 0, submitted_facts, trace_ref: ref(traceRaw, traceUri, "kronos_task_trace.v2"), screenshot_refs: [ref(screenshotRaw, screenshotUri, "kronos_screenshot.v2")], failure_codes };
  });
  const completed = iso(base + 20);
  const objective_failures = tasks.flatMap(task => task.failure_codes.map(failure_code => ({ operator_index: args.operator, task_id: task.task_id, failure_code, evidence_ref: task.trace_ref, detected_at: task.completed_at })));
  const output = { schema: "kronos_operator_trace.v2", attempt_uid: operator.attempt_uid, operator_index: args.operator, browser_pid: operator.browser_pid, profile_uid: operator.profile_uid, fixture_ref: fixtureObject.ref, instrument_ref: instrumentObject.ref, assignment_received_at: fixture.assignment_received_at, attempt_started_at: iso(base), attempt_completed_at: completed, tasks, objective_failures, profile_destroyed_at: iso(base + 21) };
  writeFileSync(resolve(args.out), bytes(output));
}
try { main(); } catch (error) { process.stderr.write(`V5_TASK_CAPTURE_REJECTED: ${error.message}\n`); process.exitCode = 2; }
