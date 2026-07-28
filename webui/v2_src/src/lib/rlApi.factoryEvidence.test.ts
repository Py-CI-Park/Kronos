import assert from 'node:assert/strict';
import { test } from 'node:test';

import { rlApi } from './rlApi';

type FetchStub = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

function jsonResponse(payload: unknown, ok: boolean = true): Response {
  return {
    ok,
    json: async (): Promise<unknown> => payload,
  } as Response;
}

async function withFetch(stub: FetchStub, action: () => Promise<void>): Promise<void> {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = stub as typeof fetch;
  rlApi.resetFactoryLaneRuns();
  try {
    await action();
  } finally {
    rlApi.resetFactoryLaneRuns();
    globalThis.fetch = originalFetch;
  }
}

test('factory lane runs shares concurrent and sequential successful requests', async () => {
  let calls = 0;
  let resolveFetch: ((response: Response) => void) | undefined;
  const pendingFetch = new Promise<Response>((resolve) => {
    resolveFetch = resolve;
  });

  await withFetch(async () => {
    calls += 1;
    return pendingFetch;
  }, async () => {
    const first = rlApi.factoryLaneRuns();
    const second = rlApi.factoryLaneRuns();
    assert.strictEqual(first, second);
    assert.equal(calls, 1);

    resolveFetch?.(jsonResponse({ runs: [{ run: 'lane-1' }] }));
    const payload = await first;
    assert.deepEqual(payload, { runs: [{ run: 'lane-1' }] });

    assert.strictEqual(rlApi.factoryLaneRuns(), first);
    assert.equal(calls, 1);
  });
});

test('factory lane runs caches an authoritative empty response', async () => {
  let calls = 0;
  await withFetch(async () => {
    calls += 1;
    return jsonResponse({ runs: [] });
  }, async () => {
    assert.deepEqual(await rlApi.factoryLaneRuns(), { runs: [] });
    assert.deepEqual(await rlApi.factoryLaneRuns(), { runs: [] });
    assert.equal(calls, 1);
  });
});

test('factory lane runs evicts null responses so a later request retries', async () => {
  let calls = 0;
  await withFetch(async () => {
    calls += 1;
    return calls === 1 ? jsonResponse(null, false) : jsonResponse({ runs: [] });
  }, async () => {
    assert.equal(await rlApi.factoryLaneRuns(), null);
    assert.deepEqual(await rlApi.factoryLaneRuns(), { runs: [] });
    assert.equal(calls, 2);
  });
});

test('factory lane runs evicts rejected fetches so a later request retries', async () => {
  let calls = 0;
  await withFetch(async () => {
    calls += 1;
    if (calls === 1) throw new Error('network unavailable');
    return jsonResponse({ runs: [] });
  }, async () => {
    assert.equal(await rlApi.factoryLaneRuns(), null);
    assert.deepEqual(await rlApi.factoryLaneRuns(), { runs: [] });
    assert.equal(calls, 2);
  });
});

test('factory lane runs reset starts a new tab-lifetime request', async () => {
  let calls = 0;
  await withFetch(async () => {
    calls += 1;
    return jsonResponse({ runs: [] });
  }, async () => {
    await rlApi.factoryLaneRuns();
    rlApi.resetFactoryLaneRuns();
    await rlApi.factoryLaneRuns();
    assert.equal(calls, 2);
  });
});
