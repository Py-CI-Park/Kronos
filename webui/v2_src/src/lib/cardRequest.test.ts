import assert from 'node:assert/strict';
import test from 'node:test';

import type * as CardRequest from './cardRequest';

const cardRequestPath = ['.', 'cardRequest.ts'].join('/');
const { createCardRequestManager }: typeof CardRequest = await import(cardRequestPath);
type CardRequestState = CardRequest.CardRequestState;

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

test('independent cards publish independently when one request stalls', async () => {
  const manager = createCardRequestManager(1_000);
  const slow = deferred<string | null>();
  const states = new Map<string, CardRequestState>();
  const applied: string[] = [];
  const publish = (key: string, state: CardRequestState) => states.set(key, state);

  const slowLoad = manager.load('slow-card', () => slow.promise, (value) => applied.push(value), publish);
  await manager.load('fast-card', async () => 'fast', (value) => applied.push(value), publish);

  assert.deepEqual(applied, ['fast']);
  assert.deepEqual(states.get('fast-card'), { loading: false, error: null });
  assert.deepEqual(states.get('slow-card'), { loading: true, error: null });

  slow.resolve(null);
  await slowLoad;
  assert.match(states.get('slow-card')?.error ?? '', /unavailable/);
  assert.deepEqual(applied, ['fast']);
});

test('new request aborts and suppresses stale same-card response', async () => {
  const manager = createCardRequestManager(1_000);
  const first = deferred<string | null>();
  let firstSignal: AbortSignal | null = null;
  const applied: string[] = [];
  const publish = () => undefined;

  const firstLoad = manager.load('card', (signal) => {
    firstSignal = signal;
    return first.promise;
  }, (value) => applied.push(value), publish);
  await manager.load('card', async () => 'new', (value) => applied.push(value), publish);

  assert.equal(firstSignal?.aborted, true);
  first.resolve('stale');
  await firstLoad;
  assert.deepEqual(applied, ['new']);
});

test('timeout aborts only the stalled card and publishes retryable error', async () => {
  const manager = createCardRequestManager(10);
  const states = new Map<string, CardRequestState>();
  let signal: AbortSignal | null = null;

  await manager.load('timeout-card', (requestSignal) => {
    signal = requestSignal;
    return new Promise<null>((resolve) => requestSignal.addEventListener('abort', () => resolve(null), { once: true }));
  }, () => assert.fail('timed-out payload must not apply'), (key, state) => states.set(key, state));

  assert.equal(signal?.aborted, true);
  assert.deepEqual(states.get('timeout-card'), { loading: false, error: 'timeout-card request timed out' });
});
