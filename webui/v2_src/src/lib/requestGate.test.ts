import { test } from 'node:test';
import assert from 'node:assert/strict';

// Node's native TypeScript type-stripping runtime (used by
// `node --experimental-strip-types --test`) requires an explicit file
// extension on every relative import specifier, while this project's
// `tsconfig.json` (moduleResolution: "bundler", no
// `allowImportingTsExtensions`) rejects a literal `.ts` extension in a
// *static* import specifier. A dynamic `import()` is not subject to that
// static specifier check, so it satisfies both the runtime and svelte-check
// without touching tsconfig.json.
import type * as RequestGate from './requestGate';

const requestGatePath = ['.', 'requestGate.ts'].join('/');
const { createRequestGate, makeAbortable }: typeof RequestGate = await import(requestGatePath);

test('next() increments the generation token on each call', () => {
  const gate = createRequestGate();
  const a = gate.next();
  const b = gate.next();
  const c = gate.next();
  assert.equal(a, 1);
  assert.equal(b, 2);
  assert.equal(c, 3);
});

test('isCurrent(oldToken) is false after a newer next() call', () => {
  const gate = createRequestGate();
  const oldToken = gate.next();
  gate.next();
  assert.equal(gate.isCurrent(oldToken), false);
});

test('the newest token is current', () => {
  const gate = createRequestGate();
  gate.next();
  gate.next();
  const newest = gate.next();
  assert.equal(gate.isCurrent(newest), true);
  assert.equal(gate.current(), newest);
});

test('a token from a gate that never advanced further stays current', () => {
  const gate = createRequestGate();
  const token = gate.next();
  assert.equal(gate.isCurrent(token), true);
});

test('makeAbortable aborts the previous controller and returns a fresh one', () => {
  const first = new AbortController();
  assert.equal(first.signal.aborted, false);
  const second = makeAbortable(first);
  assert.equal(first.signal.aborted, true);
  assert.equal(second.signal.aborted, false);
  assert.notEqual(second, first);
});

test('makeAbortable with no previous controller just returns a fresh one', () => {
  const controller = makeAbortable(undefined);
  assert.equal(controller.signal.aborted, false);
});
