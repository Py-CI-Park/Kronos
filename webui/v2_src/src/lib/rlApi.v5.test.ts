import assert from 'node:assert/strict';
import { test } from 'node:test';

import { v5RouteDescriptors } from './generated/kronosRlApiV2.validators';
import type { V5RouteId } from './generated/kronosRlApiV2';
import { V5SemanticError } from './generated/kronosRlApiV2.semantic';
import { rlApi } from './rlApi';
import { V5SchemaValidationError } from './v5SchemaValidationError';

const sha256 = 'a'.repeat(64);
const utc = '2026-07-15T00:00:00Z';
const runId = 'run-1';

type FetchCall = Readonly<{
  url: string;
  init: RequestInit | undefined;
}>;

type BindingCase = Readonly<{
  routeId: V5RouteId;
  request: () => Promise<unknown>;
  expectedUrl: string;
  payload: () => unknown;
}>;

function source() {
  return { source_sha256: sha256, generated_at: utc };
}

function locks() {
  return {
    promotion_allowed: false,
    model_build_allowed: false,
    paper_forward_allowed: false,
    live_broker_order_allowed: false,
    profitability_claim_allowed: false,
    go_summary_allowed: false,
  };
}

function run(id: string = runId) {
  return {
    run_id: id,
    state: {
      status: 'RUNNING',
      progress: { step: 1, total_steps: 3, percent: 33.333333 },
      updated_at: utc,
      started_at: utc,
      finished_at: null,
    },
    source_sha256: sha256,
    created_at: utc,
  };
}

function list() {
  return { items: [], next_cursor: null };
}

function matrixCells() {
  return ['seed-01', 'seed-02', 'seed-03', 'seed-04', 'seed-05'].flatMap((row_id) =>
    ['fold-01', 'fold-02'].flatMap((fold) =>
      ['baseline', 'cost-00bp', 'cost-23bp', 'cost-46bp', 'no-trade'].map((variant) => ({
        row_id,
        column_id: `${fold}:${variant}`,
        state: 'PASS',
      }))
    )
  );
}

const bindings: readonly BindingCase[] = [
  {
    routeId: 'RUNS',
    request: () => rlApi.v5Runs(),
    expectedUrl: '/api/v5/rl/runs',
    payload: () => ({ route_id: 'RUNS', source: source(), locks: locks(), list: { ...list(), items: [run()] } }),
  },
  {
    routeId: 'RUN_DETAIL',
    request: () => rlApi.v5RunDetail(runId),
    expectedUrl: `/api/v5/rl/runs/${runId}`,
    payload: () => ({ route_id: 'RUN_DETAIL', source: source(), locks: locks(), run: run() }),
  },
  {
    routeId: 'EVENTS',
    request: () => rlApi.v5Events(runId),
    expectedUrl: `/api/v5/rl/runs/${runId}/events`,
    payload: () => ({ route_id: 'EVENTS', source: source(), locks: locks(), run_id: runId, list: list() }),
  },
  {
    routeId: 'MATRIX',
    request: () => rlApi.v5Matrix(),
    expectedUrl: '/api/v5/rl/matrix',
    payload: () => ({
      route_id: 'MATRIX',
      source: source(),
      locks: locks(),
      cells: matrixCells(),
      summary: { total_cells: 50, pass_count: 50, fail_count: 0, blocked_count: 0, pending_count: 0 },
    }),
  },
  {
    routeId: 'LEDGER',
    request: () => rlApi.v5Ledger(),
    expectedUrl: '/api/v5/rl/ledger',
    payload: () => ({ route_id: 'LEDGER', source: source(), locks: locks(), list: list() }),
  },
  {
    routeId: 'ARTIFACTS',
    request: () => rlApi.v5Artifacts(),
    expectedUrl: '/api/v5/rl/artifacts',
    payload: () => ({ route_id: 'ARTIFACTS', source: source(), locks: locks(), list: list() }),
  },
  {
    routeId: 'D0',
    request: () => rlApi.v5D0(),
    expectedUrl: '/api/v5/rl/d0',
    payload: () => ({ route_id: 'D0', source: source(), locks: locks(), d0: { status: 'PASS', price_basis: 'ADJUSTED', source_sha256: sha256, updated_at: utc } }),
  },
  {
    routeId: 'D1',
    request: () => rlApi.v5D1(),
    expectedUrl: '/api/v5/rl/d1',
    payload: () => ({ route_id: 'D1', source: source(), locks: locks(), d1: { status: 'PASS', universe: 'OFFICIAL', source_sha256: sha256, updated_at: utc } }),
  },
  {
    routeId: 'FIXTURE',
    request: () => rlApi.v5Fixture(),
    expectedUrl: '/api/v5/rl/fixture',
    payload: () => ({ route_id: 'FIXTURE', source: source(), locks: locks(), fixture: { fixture_id: 'fixture-1', run: run(), source_sha256: sha256, created_at: utc } }),
  },
];

function jsonResponse(payload: unknown, status: number = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async (): Promise<unknown> => payload,
  } as unknown as Response;
}

function parseErrorResponse(): Response {
  return {
    ok: true,
    status: 200,
    json: async (): Promise<unknown> => {
      throw new Error('parse-secret-token');
    },
  } as unknown as Response;
}

function countedNonOkResponse(): { response: Response; jsonCalls: () => number } {
  let calls = 0;
  return {
    response: {
      ok: false,
      status: 503,
      json: async (): Promise<unknown> => {
        calls += 1;
        return { route_id: 'RUNS', error: { code: 'INTERNAL_ERROR', message: 'server-secret-token' } };
      },
    } as unknown as Response,
    jsonCalls: () => calls,
  };
}

async function withFetch(result: Response | Error, action: (calls: readonly FetchCall[]) => Promise<void>): Promise<void> {
  const originalFetch = globalThis.fetch;
  const calls: FetchCall[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    calls.push({ url: typeof input === 'string' ? input : input.toString(), init });
    if (result instanceof Error) throw result;
    return result;
  }) as typeof fetch;
  try {
    await action(calls);
  } finally {
    globalThis.fetch = originalFetch;
  }
}

function expectedCall(binding: BindingCase): FetchCall {
  return { url: binding.expectedUrl, init: { method: v5RouteDescriptors[binding.routeId].method } };
}

function assertDeepFrozen(value: unknown): void {
  if (value === null || typeof value !== 'object') return;
  assert.ok(Object.isFrozen(value));
  for (const child of Object.values(value)) assertDeepFrozen(child);
}

test('generic V5 helpers delegate all generated bindings through fetchJson with descriptor init', async () => {
  assert.deepEqual(bindings.map((binding) => binding.routeId), Object.keys(v5RouteDescriptors));

  for (const binding of bindings) {
    const payload = binding.payload();
    await withFetch(jsonResponse(payload), async (calls) => {
      assert.equal(await binding.request(), payload, binding.routeId);
      assert.deepEqual(calls, [expectedCall(binding)], binding.routeId);
      assertDeepFrozen(payload);
    });
  }
});

test('generic V5 helpers preserve fetchJson null transport semantics for every binding', async () => {
  const transportResults: readonly (Response | Error)[] = [
    new Error('network-secret-token'),
    jsonResponse({ route_id: 'RUNS', error: { code: 'INTERNAL_ERROR', message: 'server-secret-token' } }, 503),
    parseErrorResponse(),
    jsonResponse(null),
  ];

  for (const binding of bindings) {
    for (const result of transportResults) {
      await withFetch(result, async (calls) => {
        assert.equal(await binding.request(), null, binding.routeId);
        assert.deepEqual(calls, [expectedCall(binding)], binding.routeId);
      });
    }
  }
});

test('generic V5 fetchJson path does not parse non-2xx bodies for any binding', async () => {
  for (const binding of bindings) {
    const counted = countedNonOkResponse();
    await withFetch(counted.response, async (calls) => {
      assert.equal(await binding.request(), null, binding.routeId);
      assert.equal(counted.jsonCalls(), 0, binding.routeId);
      assert.deepEqual(calls, [expectedCall(binding)], binding.routeId);
    });
  }
});

test('generic V5 schema failures use sanitized validator diagnostics without request or payload leaks', async () => {
  const cursor = 'secret_cursor_000';
  const payload = { route_id: 'RUNS', source: { generated_at: 'payload-secret-token' }, error: { message: 'server-secret-token' } };

  await withFetch(jsonResponse(payload), async (calls) => {
    await assert.rejects(rlApi.v5Runs(cursor), (caught) => {
      assert.ok(caught instanceof V5SchemaValidationError);
      assert.equal(caught.routeId, 'RUNS');
      assert.ok(caught.diagnostics.length > 0);
      const serialized = `${caught.message}\n${JSON.stringify(caught)}`;
      assert.equal(serialized.includes(cursor), false);
      assert.equal(serialized.includes('payload-secret-token'), false);
      assert.equal(serialized.includes('server-secret-token'), false);
      return true;
    });
    assert.deepEqual(calls, [{ url: `/api/v5/rl/runs?cursor=${cursor}`, init: { method: 'GET' } }]);
  });

  await withFetch(jsonResponse(undefined), async (calls) => {
    await assert.rejects(rlApi.v5Runs(), V5SchemaValidationError);
    assert.deepEqual(calls, [expectedCall(bindings[0])]);
  });
});

test('generic V5 helper leaves generated query validation and unexpected validator errors unchanged', async () => {
  await withFetch(jsonResponse({}), async (calls) => {
    await assert.rejects(rlApi.v5Runs('short'), V5SemanticError);
    assert.deepEqual(calls, []);
  });

  const originalValidator = v5RouteDescriptors.RUNS.validator;
  const thrown = new Error('validator-secret-token');
  (v5RouteDescriptors.RUNS as { validator: typeof originalValidator }).validator = ((() => {
    throw thrown;
  }) as unknown) as typeof originalValidator;
  try {
    await withFetch(jsonResponse({ route_id: 'RUNS' }), async () => {
      await assert.rejects(rlApi.v5Runs(), (caught) => caught === thrown);
    });
  } finally {
    (v5RouteDescriptors.RUNS as { validator: typeof originalValidator }).validator = originalValidator;
  }
});
