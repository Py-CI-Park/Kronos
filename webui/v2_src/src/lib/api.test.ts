import assert from 'node:assert/strict';
import { test } from 'node:test';

import { api, V5SchemaValidationError, V5SemanticError, v5RouteDescriptors, validateErrorRoot } from './api';

const sha256 = 'a'.repeat(64);
const utc = '2026-07-15T00:00:00Z';
const source = { source_sha256: sha256, generated_at: utc };
const run = {
  run_id: 'run-1',
  state: { status: 'RUNNING', progress: { step: 1, total_steps: 3, percent: 33.333333 }, updated_at: utc, started_at: utc, finished_at: null },
  source_sha256: sha256,
  created_at: utc,
};
const list = { items: [], next_cursor: null };
const locks = {
  promotion_allowed: false,
  model_build_allowed: false,
  paper_forward_allowed: false,
  live_broker_order_allowed: false,
  profitability_claim_allowed: false,
  go_summary_allowed: false
};
const matrixCells = ['seed-01', 'seed-02', 'seed-03', 'seed-04', 'seed-05'].flatMap((row_id) =>
  ['fold-01', 'fold-02'].flatMap((fold) =>
    ['baseline', 'cost-00bp', 'cost-23bp', 'cost-46bp', 'no-trade'].map((variant) => ({
      row_id,
      column_id: `${fold}:${variant}`,
      state: 'PASS'
    }))
  )
);

function response(payload: unknown, status: number = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async (): Promise<unknown> => payload
  } as unknown as Response;
}

function jsonErrorResponse(status: number = 503): Response {
  return {
    ok: false,
    status,
    json: async (): Promise<unknown> => {
      throw new Error('parse');
    }
  } as unknown as Response;
}

async function withFetch(result: Response | Error, action: (urls: string[]) => Promise<void>): Promise<void> {
  const originalFetch = globalThis.fetch;
  const urls: string[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL): Promise<Response> => {
    urls.push(typeof input === 'string' ? input : input.toString());
    if (result instanceof Error) throw result;
    return result;
  }) as typeof fetch;
  try {
    await action(urls);
  } finally {
    globalThis.fetch = originalFetch;
  }
}
async function withFetchSequence(
  results: readonly (Response | Error)[],
  action: (urls: string[]) => Promise<void>,
): Promise<void> {
  const originalFetch = globalThis.fetch;
  const urls: string[] = [];
  let index = 0;
  globalThis.fetch = (async (input: RequestInfo | URL): Promise<Response> => {
    urls.push(typeof input === 'string' ? input : input.toString());
    const result = results[index++];
    if (result instanceof Error) throw result;
    if (result === undefined) throw new Error('unexpected fetch');
    return result;
  }) as typeof fetch;
  try {
    await action(urls);
  } finally {
    globalThis.fetch = originalFetch;
  }
}

function assertDeepFrozen(value: unknown): void {
  if (value === null || typeof value !== 'object') return;
  assert.ok(Object.isFrozen(value));
  for (const child of Object.values(value)) assertDeepFrozen(child);
}

test('V5 malformed 2xx JSON throws bounded sanitized diagnostics without cursor data', async () => {
  const cursor = 'opaque_cursor-token';
  await withFetch(response({ route_id: 'RUNS' }), async (urls) => {
    await assert.rejects(api.v5Runs(cursor), (caught) =>
      caught instanceof V5SchemaValidationError
      && caught.name === 'V5SchemaValidationError'
      && caught.message === 'V5 response failed schema validation'
      && caught.code === 'V5_SCHEMA_INVALID'
      && caught.routeId === 'RUNS'
      && !JSON.stringify(caught.diagnostics).includes(cursor)
      && caught.diagnostics.every((diagnostic) =>
        typeof diagnostic.instancePath === 'string'
        && typeof diagnostic.keyword === 'string'
        && Object.isFrozen(diagnostic)
      )
      && Object.isFrozen(caught)
      && Object.isFrozen(caught.diagnostics)
    );
    assert.deepEqual(urls, ['/api/v5/rl/runs?cursor=opaque_cursor-token']);
  });
});

test('V5 unavailable lane returns null for network, non-2xx, and null payloads', async () => {
  for (const result of [new Error('network'), jsonErrorResponse(), response(null)]) {
    await withFetch(result, async (urls) => {
      assert.equal(await api.v5Runs(), null);
      assert.deepEqual(urls, ['/api/v5/rl/runs']);
    });
  }
});

test('V5 transport preserves fetchJson null semantics for all non-2xx responses', async () => {
  for (const payload of [
    { route_id: 'RUNS', error: { code: 'BAD_REQUEST', message: 'server-only diagnostic' } },
    { route_id: 'RUNS', error: { code: 'NOT_FOUND' } },
  ]) {
    await withFetch(response(payload, 400), async (urls) => {
      assert.equal(await api.v5Runs(), null);
      assert.deepEqual(urls, ['/api/v5/rl/runs']);
    });
  }
});

test('V4 fetch behavior and progress semantics remain unvalidated', async () => {
  const payload = { overall_progress_pct: 200, pages: 'not-a-list' };
  await withFetch(response(payload), async (urls) => {
    assert.equal(await api.rlProgress(), payload);
    assert.deepEqual(urls, ['/api/rl/progress']);
  });
});

test('V5 route helpers validate every generated route root and URL-safe run IDs', async () => {
  const runId = 'run.id_1-2';
  const boundRun = { ...run, run_id: runId };
  const routes: readonly [() => Promise<unknown>, unknown, string][] = [
    [api.v5Runs, { route_id: 'RUNS', source, locks, list: { ...list, items: [run] } }, '/api/v5/rl/runs'],
    [() => api.v5RunDetail(runId), { route_id: 'RUN_DETAIL', source, locks, run: boundRun }, `/api/v5/rl/runs/${runId}`],
    [() => api.v5Events(runId), { route_id: 'EVENTS', source, locks, list, run_id: runId }, `/api/v5/rl/runs/${runId}/events`],
    [api.v5Matrix, { route_id: 'MATRIX', source, locks, cells: matrixCells, summary: { total_cells: 50, pass_count: 50, fail_count: 0, blocked_count: 0, pending_count: 0 } }, '/api/v5/rl/matrix'],
    [api.v5Ledger, { route_id: 'LEDGER', source, locks, list }, '/api/v5/rl/ledger'],
    [api.v5Artifacts, { route_id: 'ARTIFACTS', source, locks, list }, '/api/v5/rl/artifacts'],
    [api.v5D0, { route_id: 'D0', source, locks, d0: { status: 'PASS', price_basis: 'ADJUSTED', source_sha256: sha256, updated_at: utc } }, '/api/v5/rl/d0'],
    [api.v5D1, { route_id: 'D1', source, locks, d1: { status: 'PASS', universe: 'OFFICIAL', source_sha256: sha256, updated_at: utc } }, '/api/v5/rl/d1'],
    [api.v5Fixture, { route_id: 'FIXTURE', source, locks, fixture: { fixture_id: 'fixture-1', run, source_sha256: sha256, created_at: utc } }, '/api/v5/rl/fixture'],
  ];

  for (const [fetchRoute, payload, expectedUrl] of routes) {
    await withFetch(response(payload), async (urls) => {
      assert.equal(await fetchRoute(), payload);
      assert.deepEqual(urls, [expectedUrl]);
    });
      assertDeepFrozen(payload);
  }

  await withFetch(response({}), async (urls) => {
    await assert.rejects(api.v5RunDetail('run/unsafe'), V5SemanticError);
    await assert.rejects(api.v5Events('run unsafe'), V5SemanticError);
    assert.deepEqual(urls, []);
  });
});
test('V5 paginated helpers encode grammar-checked opaque cursors and traverse subsequent pages', async () => {
  const pageCursor = 'next_cursor_token';
  const opaqueCursor = 'opaque_cursor-token';
  const paginated: readonly [
    string,
    (cursor?: string) => Promise<unknown>,
    () => object,
  ][] = [
    ['/api/v5/rl/runs', api.v5Runs, () => ({ route_id: 'RUNS', source, locks, list: { items: [], next_cursor: pageCursor } })],
    [`/api/v5/rl/runs/run-1/events`, (cursor?: string) => api.v5Events('run-1', cursor), () => ({ route_id: 'EVENTS', source, locks, run_id: 'run-1', list: { items: [], next_cursor: pageCursor } })],
    ['/api/v5/rl/ledger', api.v5Ledger, () => ({ route_id: 'LEDGER', source, locks, list: { items: [], next_cursor: pageCursor } })],
    ['/api/v5/rl/artifacts', api.v5Artifacts, () => ({ route_id: 'ARTIFACTS', source, locks, list: { items: [], next_cursor: pageCursor } })],
  ];

  for (const [path, request, firstPage] of paginated) {
    await withFetch(response(firstPage()), async (urls) => {
      assert.ok(await request(opaqueCursor));
      assert.deepEqual(urls, [`${path}?cursor=opaque_cursor-token`]);
    });

    const first = firstPage();
    const second = { ...first, list: { items: [], next_cursor: null } };
    await withFetchSequence([response(first), response(second)], async (urls) => {
      const page = await request();
      assert.ok(page);
      const cursor = (page as { readonly list: { readonly next_cursor: string | null } }).list.next_cursor;
      assert.equal(cursor, pageCursor);
      assert.ok(await request(cursor ?? undefined));
      assert.deepEqual(urls, [path, `${path}?cursor=${pageCursor}`]);
      assertDeepFrozen(first);
      assertDeepFrozen(second);
    });
  }

  await withFetch(response({}), async (urls) => {
    await assert.rejects(api.v5Runs('short'), (caught) =>
      caught instanceof V5SemanticError && caught.message === 'invalid cursor'
    );
    await assert.rejects(api.v5Runs('opaque+cursor-token'), (caught) =>
      caught instanceof V5SemanticError && caught.message === 'invalid cursor'
    );
    await assert.rejects(api.v5Artifacts('a'.repeat(2049)), (caught) =>
      caught instanceof V5SemanticError && caught.message === 'invalid cursor'
    );
    assert.deepEqual(urls, []);
  });
});

test('V5 matrix missing its required summary is rejected', async () => {
  await withFetch(response({ route_id: 'MATRIX', source, cells: [] }), async (urls) => {
    await assert.rejects(api.v5Matrix(), V5SchemaValidationError);
    assert.deepEqual(urls, ['/api/v5/rl/matrix']);
  });
});
test('V5 semantic validation rejects valid-schema progress, source, requested/payload run, matrix, download, and event hash violations', async () => {
  const artifacts = {
    route_id: 'ARTIFACTS',
    source,
    locks,
    list: {
      items: [{
        artifact: { artifact_id: 'artifact-1', filename: 'report.json', media_type: 'application/json', byte_length: 1, sha256, created_at: utc },
        download_url: '/api/v5/rl/artifacts/artifact-1/download',
        portable_filename: 'report.json',
      }],
      next_cursor: null,
    },
  };
  const invalidCases: readonly [() => Promise<unknown>, unknown][] = [
    [() => api.v5RunDetail('run-1'), { route_id: 'RUN_DETAIL', source, locks, run: { ...run, state: { ...run.state, progress: { step: 3, total_steps: 3, percent: 0 } } } }],
    [() => api.v5RunDetail('run-1'), { route_id: 'RUN_DETAIL', source, locks, run: { ...run, source_sha256: 'b'.repeat(64) } }],
    [() => api.v5RunDetail('run-1'), { route_id: 'RUN_DETAIL', source, locks, run: { ...run, run_id: 'other-run' } }],
    [() => api.v5Events('run-1'), { route_id: 'EVENTS', source, locks, run_id: 'other-run', list }],
    [api.v5Matrix, { route_id: 'MATRIX', source, locks, cells: matrixCells, summary: { total_cells: 50, pass_count: 49, fail_count: 1, blocked_count: 0, pending_count: 0 } }],
    [api.v5Artifacts, { ...artifacts, list: { ...artifacts.list, items: [{ ...artifacts.list.items[0], download_url: '/api/v5/rl/artifacts/other/download' }] } }],
    [() => api.v5Events('run-1'), { route_id: 'EVENTS', source, locks, run_id: 'run-1', list: { items: [{ event_type: 'MESSAGE', event_id: 'event-1', occurred_at: utc, payload_sha256: sha256, level: 'INFO', message: 'hello' }], next_cursor: null } }],
  ];

  for (const [request, payload] of invalidCases) {
    await withFetch(response(payload), async () => {
      await assert.rejects(request(), V5SemanticError);
    });
  }
});

test('V5 error-root wire validator remains available while transport hides error bodies', async () => {
  const requests = [
    ['RUNS', api.v5Runs],
    ['RUN_DETAIL', () => api.v5RunDetail('run-1')],
    ['EVENTS', () => api.v5Events('run-1')],
    ['MATRIX', api.v5Matrix],
    ['LEDGER', api.v5Ledger],
    ['ARTIFACTS', api.v5Artifacts],
    ['D0', api.v5D0],
    ['D1', api.v5D1],
    ['FIXTURE', api.v5Fixture],
  ] as const;

  for (const [routeId, request] of requests) {
    for (const code of v5RouteDescriptors[routeId].allowedErrors) {
      const payload = { route_id: routeId, error: { code, message: 'server-only diagnostic' } };
      assert.equal(validateErrorRoot(payload), true);
      await withFetch(response(payload, 400), async () => {
        assert.equal(await request(), null);
      });
    }
    assert.equal(validateErrorRoot({ route_id: routeId, error: { code: 'VALIDATION_ERROR', message: 'safe' } }), false);
  }
});

test('V5 schema validation error exported by API exposes immutable sanitized diagnostic pairs', () => {
  const diagnostics = [
    { instancePath: '/z', keyword: 'type', params: { token: 'secret-token' } },
    { instancePath: '/a\u0000', keyword: 'required' },
    { instancePath: '/z', keyword: 'type' },
    { instancePath: 'not-a-pointer', keyword: 'bad keyword' },
    ...Array.from({ length: 100 }, (_, index) => ({
      instancePath: `/item/${String(index).padStart(3, '0')}`,
      keyword: 'type',
    })),
  ] as ConstructorParameters<typeof V5SchemaValidationError>[1];
  const error = new V5SchemaValidationError('RUNS', diagnostics);

  assert.ok(error instanceof V5SchemaValidationError);
  assert.equal(error.message, 'V5 response failed schema validation');
  assert.equal(error.code, 'V5_SCHEMA_INVALID');
  assert.equal(error.diagnostics.length, 16);
  assert.ok(error.diagnostics.every((diagnostic) => typeof diagnostic.instancePath === 'string' && typeof diagnostic.keyword === 'string'));
  assert.ok(error.diagnostics.every((diagnostic) => [...diagnostic.instancePath].length <= 256));
  assert.ok(error.diagnostics.some((diagnostic) => diagnostic.instancePath === '/a' && diagnostic.keyword === 'required'));
  assert.ok(!JSON.stringify(error).includes('secret-token'));
  assert.ok(Object.isFrozen(error));
  assert.ok(Object.isFrozen(error.diagnostics));
  assert.ok(error.diagnostics.every((diagnostic) => Object.isFrozen(diagnostic)));
});
