import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  V51ApiError,
  V51_MAX_RESPONSE_BYTES,
  isV51RouteRoot,
  isV51ErrorRoot,
  v51Api,
  v51RouteDescriptors,
  type V51ErrorCode,
  type V51RouteId,
  type V51ResearchRouteId,
} from './v51Api';

const sha = 'a'.repeat(64);
const sourceDbSha = 'b'.repeat(64);
const protocolSha = 'c'.repeat(64);
const zeroSha = '0'.repeat(64);
const epochUtc = '1970-01-01T00:00:00Z';
const utc = '2026-07-18T00:00:00Z';

type FetchCall = Readonly<{ url: string; init: RequestInit | undefined }>;
type RouteCase = Readonly<{
  routeId: V51RouteId;
  request: () => Promise<unknown>;
  expectedUrl: string;
  payload: () => unknown;
}>;

const locks = {
  promotion_allowed: false,
  model_build_allowed: false,
  paper_forward_allowed: false,
  live_broker_order_allowed: false,
  profitability_claim_allowed: false,
  go_summary_allowed: false,
} as const;

const claims = {
  official_close_claim: false,
  paper_forward_claim: false,
  live_trading_claim: false,
  broker_integration_claim: false,
  profitability_claim: false,
  go_readiness_claim: false,
} as const;

const accounting = {
  initial_capital_krw: 60000000,
  slot_count: 10,
  slot_budget_krw: 5000000,
  max_invested_krw: 50000000,
  reserve_cash_krw: 10000000,
  reserve_cash_display_percent: '16.6667%',
  max_target_investment_display_percent: '83.3333%',
  shorting_allowed: false,
  leverage_allowed: false,
  duplicate_symbol_slots_allowed: false,
} as const;

const costSchedule = {
  primary: { internal_id: 'base_23bp', round_trip_cost_bp: 23, display_percent: '0.23%' },
  zero_cost_control: { internal_id: 'zero_control_0bp', round_trip_cost_bp: 0, display_percent: '0.00%' },
  stress_control: { internal_id: 'stress_46bp', round_trip_cost_bp: 46, display_percent: '0.46%' },
} as const;

const horizon = {
  primary_horizon: 'H1',
  validation_horizons: ['H3', 'H5'],
  label_columns: ['future_return_h1_1520_proxy', 'future_return_h3_1520_proxy', 'future_return_h5_1520_proxy'],
} as const;

const sourcePolicy = {
  daily_1520_source_schema: 'kronos_daily_1520_source.v1',
  causal_panel_schema: 'kronos_daily_v51_causal_panel.v1',
  causal_cutoff_kst: '15:20:00',
  price_basis: '15:20_bar_close_proxy',
  official_close: false,
  nearest_fallback_allowed: false,
  full_day_daily_ohlcv_allowed: false,
  price_volume_amount_approximation_allowed: false,
  pykrx_offline_only: true,
  naver_fallback_allowed: false,
  network_required: false,
} as const;

const overlayPolicy = {
  allowed_index_provider: 'PYKRX',
  offline_artifact_required: true,
  naver_fallback_allowed: false,
  forbidden_provider: 'NAVER',
  missing_index_state: 'BLOCKED_INDEX_SERIES_SOURCE',
} as const;

const stableArtifactIds = {
  source_coverage: 'daily-close-v51-source-coverage',
  causal_panel: 'daily-close-v51-causal-panel',
  accounting: 'daily-close-v51-accounting',
  evaluator: 'daily-close-v51-evaluator',
  benchmark_overlay: 'daily-close-v51-benchmark-overlay',
} as const;

const artifactKindByRoute = {
  SOURCE_COVERAGE: 'source_coverage',
  CAUSAL_PANEL: 'causal_panel',
  ACCOUNTING: 'accounting',
  EVALUATOR: 'evaluator',
  BENCHMARK_OVERLAY: 'benchmark_overlay',
} as const satisfies Record<V51ResearchRouteId, string>;

const payloadNameByRoute = {
  SOURCE_COVERAGE: 'source_coverage',
  CAUSAL_PANEL: 'causal_panel',
  ACCOUNTING: 'accounting',
  EVALUATOR: 'evaluator',
  BENCHMARK_OVERLAY: 'benchmark_overlay',
} as const satisfies Record<V51ResearchRouteId, string>;

function protocol(routeId: V51RouteId) {
  return {
    schema_version: 'kronos_v51_research_api.v1',
    api_version: 'v5.1',
    method: 'GET',
    read_only: true,
    route_id: routeId,
    route_path: v51RouteDescriptors[routeId].path,
    causal_cutoff_kst: '15:20:00',
    price_basis: '15:20_bar_close_proxy',
    official_close: false,
    accounting,
    cost_schedule: costSchedule,
    horizon,
    source_policy: sourcePolicy,
    overlay_policy: overlayPolicy,
  };
}

function source(sourceArtifactId: string) {
  return {
    source_protocol: 'kronos_daily_1520_source.v1',
    source_artifact_id: sourceArtifactId,
    source_sha256: sha,
    source_db_sha256: sourceDbSha,
    generated_at: utc,
    causal_cutoff_kst: '15:20:00',
    price_basis: '15:20_bar_close_proxy',
    official_close: false,
  };
}

function run() {
  return {
    run_id: 'run-1',
    run_revision: 1,
    run_artifact_id: 'run-artifact',
    source_sha256: sha,
    protocol_sha256: protocolSha,
    stable_artifact_ids: stableArtifactIds,
  };
}

function artifact(kind: string, artifactId: string) {
  return {
    artifact_id: artifactId,
    artifact_kind: kind,
    media_type: 'application/json; charset=utf-8',
    byte_length: 2,
    sha256: sha,
    stable_id: true,
  };
}

function sourceCoverage() {
  return {
    coverage_status: 'READY',
    exact_1520_row_count: 1739,
    symbol_count: 1,
    session_count: 1739,
    first_valid_date: '2019-05-09',
    last_valid_date: '2026-06-12',
    sample_symbol: '000250',
    sample_timestamp_yyyymmddhhmm: '202606121520',
    volume_to_1520_status: 'NOT_AVAILABLE_SOURCE_HAS_SINGLE_5MIN_BAR_VOLUME_ONLY',
    amount_to_1520_status: 'NOT_AVAILABLE_5MIN_DB_HAS_NO_AMOUNT_COLUMN_DO_NOT_APPROXIMATE_PRICE_X_VOLUME',
    missing_policy: 'MISSING_1520_BAR_BLOCKS_ROW_NO_NEAREST_FALLBACK',
  };
}

function causalPanel() {
  return {
    panel_schema: 'kronos_daily_v51_causal_panel.v1',
    row_count: 1,
    price_basis: '15:20_bar_close_proxy',
    official_close: false,
    primary_horizon: 'H1',
    validation_horizons: ['H3', 'H5'],
    label_columns: ['future_return_h1_1520_proxy', 'future_return_h3_1520_proxy', 'future_return_h5_1520_proxy'],
    rows_preview: [{
      symbol: '000250',
      session_date: '2026-06-12',
      timestamp_kst: '2026-06-12T15:20:00+09:00',
      price_basis: '15:20_bar_close_proxy',
      official_close: false,
      entry_status: 'READY',
      h1_status: 'READY',
      h3_status: 'READY',
      h5_status: 'READY',
    }],
  };
}

function accountingSummary() {
  return {
    accounting_status: 'READY',
    contract: accounting,
    cost_schedule: costSchedule,
    economic_nav_krw: 60000000,
    cash_reserve_krw: 10000000,
    slots_used: 0,
    max_slots: 10,
    internal_cost_id: 'base_23bp',
    display_cost_percent: '0.23%',
  };
}

function evaluator() {
  return {
    evaluation_status: 'BLOCKED',
    primary_horizon: 'H1',
    validation_horizons: ['H3', 'H5'],
    cost_schedule: costSchedule,
    split_statuses: { train: 'READY', validation: 'BLOCKED', test: 'BLOCKED' },
    metrics: [
      {
        metric_id: 'cumulative_return',
        split: 'validation',
        horizon: 'H1',
        internal_cost_id: 'base_23bp',
        display_cost_percent: '0.23%',
        value: 0,
        display_percent: '0.00%',
      },
      {
        metric_id: 'turnover',
        split: 'validation',
        horizon: 'H1',
        internal_cost_id: 'zero_control_0bp',
        display_cost_percent: '0.00%',
        value: 0,
        display_percent: '0.00%',
      },
    ],
  };
}

function benchmarkOverlay() {
  return {
    overlay_status: 'BLOCKED',
    provider_policy: overlayPolicy,
    common_start_index: 100,
    series: [
      { series_id: 'KOSPI', status: 'BLOCKED', source_state: 'BLOCKED_INDEX_SERIES_SOURCE', provider: null, naver_used: false, index_100: null, cumulative_return_display_percent: null },
      { series_id: 'KOSDAQ', status: 'BLOCKED', source_state: 'BLOCKED_INDEX_SERIES_SOURCE', provider: null, naver_used: false, index_100: null, cumulative_return_display_percent: null },
      { series_id: 'RL_PORTFOLIO', status: 'BLOCKED', source_state: 'BLOCKED_INDEX_SERIES_SOURCE', provider: null, naver_used: false, index_100: null, cumulative_return_display_percent: null },
    ],
  };
}


function readyBenchmarkOverlay() {
  return {
    ...benchmarkOverlay(),
    overlay_status: 'READY',
    series: [
      { series_id: 'KOSPI', status: 'READY', source_state: 'READY', provider: 'PYKRX', naver_used: false, index_100: 101, cumulative_return_display_percent: '1.00%' },
      { series_id: 'KOSDAQ', status: 'READY', source_state: 'READY', provider: 'PYKRX', naver_used: false, index_100: 102.5, cumulative_return_display_percent: '2.50%' },
      { series_id: 'RL_PORTFOLIO', status: 'READY', source_state: 'READY', provider: null, naver_used: false, index_100: 105, cumulative_return_display_percent: '5.00%' },
    ],
  };
}


function readyBenchmarkOverlayRoot() {
  const benchmark_overlay = readyBenchmarkOverlay();
  return {
    ...researchPayload('BENCHMARK_OVERLAY', benchmark_overlay),
    status: 'READY',
    status_reason: 'READY',
    benchmark_overlay,
  };
}

function researchPayload(routeId: V51ResearchRouteId, body: unknown) {
  return {
    route_id: routeId,
    status: routeId === 'BENCHMARK_OVERLAY' || routeId === 'EVALUATOR' ? 'BLOCKED' : 'READY',
    status_reason: routeId === 'BENCHMARK_OVERLAY' ? 'BLOCKED_INDEX_SERIES_SOURCE' : routeId === 'EVALUATOR' ? 'BLOCKED_ARTIFACT_UNAVAILABLE' : 'READY',
    protocol: protocol(routeId),
    source: source(stableArtifactIds[payloadNameByRoute[routeId]]),
    run: run(),
    artifact: artifact(artifactKindByRoute[routeId], stableArtifactIds[payloadNameByRoute[routeId]]),
    locks,
    claims,
    [payloadNameByRoute[routeId]]: body,
  };
}

function reportSummary() {
  return {
    report_id: 'report-2026-07-17',
    title: 'V5.1 research requirements',
    relative_path: 'docs/kronos_daily_close_rl_v5_1_requirements_2026-07-17.md',
    root_id: 'docs',
    media_type: 'text/markdown; charset=utf-8',
    byte_length: 1,
    sha256: sha,
    updated_at: utc,
    source_protocol: 'kronos_v51_report_catalog.v1',
    price_basis: '15:20_bar_close_proxy',
    official_close: false,
  };
}

function reportSource() {
  return {
    source_protocol: 'kronos_v51_report_catalog.v1',
    catalog_artifact_id: 'report-catalog',
    catalog_sha256: sha,
    generated_at: utc,
    price_basis: '15:20_bar_close_proxy',
    official_close: false,
  };
}

function reportListPayload() {
  return {
    route_id: 'REPORTS',
    status: 'READY',
    status_reason: 'READY',
    protocol: protocol('REPORTS'),
    source: reportSource(),
    locks,
    claims,
    reports: [reportSummary()],
  };
}

function reportReadPayload() {
  return {
    route_id: 'REPORT_READ',
    status: 'READY',
    status_reason: 'READY',
    protocol: protocol('REPORT_READ'),
    source: reportSource(),
    locks,
    claims,
    report: reportSummary(),
    content: { raw_text: '# V5.1\n', safe_html: '<article data-kronos-report-html="escaped-pre"><pre># V5.1\n</pre></article>' },
  };
}

const errorStatusByCode = {
  BAD_REQUEST: 400,
  CONFLICT: 409,
  VALIDATION_ERROR: 413,
  METHOD_NOT_ALLOWED: 405,
  INTERNAL_ERROR: 503,
} as const satisfies Record<V51ErrorCode, 400 | 409 | 413 | 405 | 503>;

function errorSource(routeId: V51RouteId) {
  if (routeId === 'REPORTS' || routeId === 'REPORT_READ') return reportSource();
  return source(stableArtifactIds[payloadNameByRoute[routeId]]);
}

function errorPayload(routeId: V51RouteId, code: V51ErrorCode, message = 'request failed') {
  return {
    route_id: routeId,
    status: 'ERROR',
    protocol: protocol(routeId),
    source: errorSource(routeId),
    locks,
    claims,
    error: { code, message, status_code: errorStatusByCode[code] },
  };
}

const routeCases: readonly RouteCase[] = [
  {
    routeId: 'SOURCE_COVERAGE',
    request: () => v51Api.sourceCoverage({ runId: 'run-1', artifactId: stableArtifactIds.source_coverage, revision: 2 }),
    expectedUrl: `/api/daily-close-v51/source-coverage?run_id=run-1&artifact_id=${stableArtifactIds.source_coverage}&revision=2`,
    payload: () => researchPayload('SOURCE_COVERAGE', sourceCoverage()),
  },
  {
    routeId: 'CAUSAL_PANEL',
    request: () => v51Api.causalPanel(),
    expectedUrl: '/api/daily-close-v51/causal-panel',
    payload: () => researchPayload('CAUSAL_PANEL', causalPanel()),
  },
  {
    routeId: 'ACCOUNTING',
    request: () => v51Api.accounting(),
    expectedUrl: '/api/daily-close-v51/accounting',
    payload: () => researchPayload('ACCOUNTING', accountingSummary()),
  },
  {
    routeId: 'EVALUATOR',
    request: () => v51Api.evaluator(),
    expectedUrl: '/api/daily-close-v51/evaluator',
    payload: () => researchPayload('EVALUATOR', evaluator()),
  },
  {
    routeId: 'BENCHMARK_OVERLAY',
    request: () => v51Api.benchmarkOverlay(),
    expectedUrl: '/api/daily-close-v51/benchmark-overlay',
    payload: () => researchPayload('BENCHMARK_OVERLAY', benchmarkOverlay()),
  },
  {
    routeId: 'REPORTS',
    request: () => v51Api.listReports(),
    expectedUrl: '/api/daily-close-v51/reports',
    payload: reportListPayload,
  },
  {
    routeId: 'REPORT_READ',
    request: () => v51Api.readReport('report-2026-07-17'),
    expectedUrl: '/api/daily-close-v51/reports/report-2026-07-17',
    payload: reportReadPayload,
  },
];

function response(payload: unknown, status: number = 200, headers: HeadersInit = {}): Response {
  return textResponse(JSON.stringify(payload), status, headers);
}

function textResponse(text: string, status: number = 200, headers: HeadersInit = {}): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers(headers),
    text: async (): Promise<string> => text,
  } as unknown as Response;
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

function assertDeepFrozen(value: unknown): void {
  if (value === null || typeof value !== 'object') return;
  assert.ok(Object.isFrozen(value));
  for (const child of Object.values(value)) assertDeepFrozen(child);
}

test('V5.1 descriptors are additive GET-only routes outside the V5 API v2 namespace', () => {
  assert.deepEqual(Object.keys(v51RouteDescriptors), [
    'SOURCE_COVERAGE',
    'CAUSAL_PANEL',
    'ACCOUNTING',
    'EVALUATOR',
    'BENCHMARK_OVERLAY',
    'REPORTS',
    'REPORT_READ',
  ]);
  for (const descriptor of Object.values(v51RouteDescriptors)) {
    assert.equal(descriptor.method, 'GET');
    assert.equal(descriptor.path.startsWith('/api/daily-close-v51/'), true);
    assert.equal(descriptor.path.startsWith('/api/v5/rl/'), false);
  }
});

test('V5.1 client functions use GET, route/query/path strings, and frozen guarded payloads', async () => {
  for (const routeCase of routeCases) {
    const payload = routeCase.payload();
    await withFetch(response(payload), async (calls) => {
      const result = await routeCase.request();
      assert.deepEqual(result, payload, routeCase.routeId);
      assert.equal(isV51RouteRoot(routeCase.routeId, result), true, routeCase.routeId);
      assert.deepEqual(calls, [{ url: routeCase.expectedUrl, init: { method: 'GET' } }], routeCase.routeId);
      assertDeepFrozen(result);
    });
  }
});

test('V5.1 client guards route-aware backend ERROR envelopes for bounded status roots', async () => {
  const cases: readonly {
    readonly routeId: V51RouteId;
    readonly code: V51ErrorCode;
    readonly request: () => Promise<unknown>;
  }[] = [
    { routeId: 'SOURCE_COVERAGE', code: 'BAD_REQUEST', request: () => v51Api.sourceCoverage() },
    { routeId: 'ACCOUNTING', code: 'CONFLICT', request: () => v51Api.accounting() },
    { routeId: 'REPORT_READ', code: 'VALIDATION_ERROR', request: () => v51Api.readReport('report-2026-07-17') },
    { routeId: 'REPORTS', code: 'INTERNAL_ERROR', request: () => v51Api.listReports() },
    { routeId: 'SOURCE_COVERAGE', code: 'METHOD_NOT_ALLOWED', request: () => v51Api.sourceCoverage() },
  ];

  for (const { routeId, code, request } of cases) {
    const message = `${code} envelope`;
    const payload = errorPayload(routeId, code, message);
    assert.equal(isV51ErrorRoot(routeId, payload), true, routeId);
    await withFetch(response(payload, payload.error.status_code), async () => {
      await assert.rejects(
        request(),
        (caught) => caught instanceof V51ApiError
          && caught.routeId === routeId
          && caught.code === code
          && caught.status === payload.error.status_code
          && caught.message === message,
      );
    });
  }
});

test('V5.1 client rejects malformed backend ERROR envelopes before surfacing backend codes', async () => {
  const payload = errorPayload('SOURCE_COVERAGE', 'BAD_REQUEST');
  assert.equal(isV51ErrorRoot('SOURCE_COVERAGE', { ...payload, unexpected: true }), false);
  assert.equal(isV51ErrorRoot('CAUSAL_PANEL', payload), false);
  assert.equal(isV51ErrorRoot('SOURCE_COVERAGE', { ...payload, status: 'BLOCKED' }), false);
  assert.equal(isV51ErrorRoot('SOURCE_COVERAGE', { ...payload, claims: { ...claims, profitability_claim: true } }), false);
  assert.equal(isV51ErrorRoot('SOURCE_COVERAGE', { ...payload, source: source(stableArtifactIds.causal_panel) }), false);
  assert.equal(isV51ErrorRoot('SOURCE_COVERAGE', { ...payload, error: { ...payload.error, status_code: 409 } }), false);

  await withFetch(response({ ...payload, error: { ...payload.error, status_code: 409 } }, 400), async () => {
    await assert.rejects(v51Api.sourceCoverage(), (caught) => caught instanceof V51ApiError && caught.code === 'HTTP_STATUS' && caught.status === 400);
  });

  await withFetch(response(payload, 503), async () => {
    await assert.rejects(v51Api.sourceCoverage(), (caught) => caught instanceof V51ApiError && caught.code === 'HTTP_STATUS' && caught.status === 503);
  });

  await withFetch(response({ ...payload, claims: { ...claims, live_trading_claim: true } }, 400), async () => {
    await assert.rejects(v51Api.sourceCoverage(), (caught) => caught instanceof V51ApiError && caught.code === 'HTTP_STATUS' && caught.status === 400);
  });
});

test('V5.1 client validates query and report path identifiers before fetch', async () => {
  await withFetch(response({}), async (calls) => {
    await assert.rejects(v51Api.sourceCoverage({ runId: '../run' }), V51ApiError);
    await assert.rejects(v51Api.sourceCoverage({ artifactId: 'artifact/unsafe' }), V51ApiError);
    await assert.rejects(v51Api.sourceCoverage({ revision: 0 }), V51ApiError);
    await assert.rejects(v51Api.readReport('../secret'), V51ApiError);
    assert.deepEqual(calls, []);
  });
});

test('V5.1 client rejects schema max boundary overflows for panel previews and report paths', async () => {
  const previewRow = causalPanel().rows_preview[0];
  const twentyOnePreviewRows = Array.from({ length: 21 }, () => ({ ...previewRow }));
  assert.equal(twentyOnePreviewRows.length, 21);
  await withFetch(response(researchPayload('CAUSAL_PANEL', {
    ...causalPanel(),
    rows_preview: twentyOnePreviewRows,
  })), async () => {
    await assert.rejects(v51Api.causalPanel(), (caught) => caught instanceof V51ApiError && caught.code === 'SCHEMA_INVALID');
  });

  const safeLowercasePath = `${'a'.repeat(510)}.md`;
  assert.equal(safeLowercasePath.length, 513);
  assert.equal(safeLowercasePath, safeLowercasePath.toLowerCase());
  await withFetch(response({
    ...reportReadPayload(),
    report: { ...reportSummary(), relative_path: safeLowercasePath },
  }), async () => {
    await assert.rejects(v51Api.readReport('report-2026-07-17'), (caught) => caught instanceof V51ApiError && caught.code === 'SCHEMA_INVALID');
  });
});

test('V5.1 client keeps BLOCKED identity sentinels but rejects READY zero and epoch identities', () => {
  const blocked = researchPayload('EVALUATOR', evaluator());
  assert.equal(isV51RouteRoot('EVALUATOR', {
    ...blocked,
    source: {
      ...source(stableArtifactIds.evaluator),
      source_sha256: zeroSha,
      source_db_sha256: zeroSha,
      generated_at: epochUtc,
    },
    run: {
      ...run(),
      source_sha256: zeroSha,
      protocol_sha256: zeroSha,
    },
    artifact: {
      ...artifact('evaluator', stableArtifactIds.evaluator),
      sha256: zeroSha,
    },
  }), true);

  const ready = researchPayload('SOURCE_COVERAGE', sourceCoverage());
  const readySentinelCases: readonly { readonly name: string; readonly payload: unknown }[] = [
    {
      name: 'source/run source_sha256',
      payload: {
        ...ready,
        source: { ...source(stableArtifactIds.source_coverage), source_sha256: zeroSha },
        run: { ...run(), source_sha256: zeroSha },
      },
    },
    {
      name: 'source_db_sha256',
      payload: {
        ...ready,
        source: { ...source(stableArtifactIds.source_coverage), source_db_sha256: zeroSha },
      },
    },
    {
      name: 'protocol_sha256',
      payload: {
        ...ready,
        run: { ...run(), protocol_sha256: zeroSha },
      },
    },
    {
      name: 'artifact.sha256',
      payload: {
        ...ready,
        artifact: { ...artifact('source_coverage', stableArtifactIds.source_coverage), sha256: zeroSha },
      },
    },
    {
      name: 'generated_at',
      payload: {
        ...ready,
        source: { ...source(stableArtifactIds.source_coverage), generated_at: epochUtc },
      },
    },
  ];

  for (const { name, payload } of readySentinelCases) {
    assert.equal(isV51RouteRoot('SOURCE_COVERAGE', payload), false, name);
  }
});

test('V5.1 client fails closed for malformed schema, identity/status/cost/report guards, JSON, status, and size', async () => {
  const metricCoercion = evaluator();
  assert.equal(isV51RouteRoot('EVALUATOR', researchPayload('EVALUATOR', {
    ...metricCoercion,
    metrics: [{ ...metricCoercion.metrics[0], metric_id: { toString: () => 'cumulative_return' } }],
  })), false);

  const overlayCoercion = benchmarkOverlay();
  assert.equal(isV51RouteRoot('BENCHMARK_OVERLAY', researchPayload('BENCHMARK_OVERLAY', {
    ...overlayCoercion,
    series: [
      { ...overlayCoercion.series[0], source_state: { toString: () => 'BLOCKED_INDEX_SERIES_SOURCE' } },
      overlayCoercion.series[1],
      overlayCoercion.series[2],
    ],
  })), false);

  const readyOverlay = readyBenchmarkOverlayRoot();
  assert.equal(isV51RouteRoot('BENCHMARK_OVERLAY', readyOverlay), true);
  assert.deepEqual(readyOverlay.benchmark_overlay.series.map((series) => series.provider), ['PYKRX', 'PYKRX', null]);

  const invalidCases: readonly { readonly request: () => Promise<unknown>; readonly payload: unknown }[] = [
    { request: () => v51Api.sourceCoverage(), payload: { ...researchPayload('SOURCE_COVERAGE', sourceCoverage()), unexpected: true } },
    { request: () => v51Api.sourceCoverage(), payload: { ...researchPayload('SOURCE_COVERAGE', sourceCoverage()), route_id: 'CAUSAL_PANEL' } },
    { request: () => v51Api.sourceCoverage(), payload: { ...researchPayload('SOURCE_COVERAGE', sourceCoverage()), locks: { ...locks, promotion_allowed: true } } },
    { request: () => v51Api.sourceCoverage(), payload: { ...researchPayload('SOURCE_COVERAGE', sourceCoverage()), claims: { ...claims, profitability_claim: true } } },
    { request: () => v51Api.sourceCoverage(), payload: { ...researchPayload('SOURCE_COVERAGE', sourceCoverage()), status_reason: 'BLOCKED_SCHEMA_INVALID' } },
    { request: () => v51Api.benchmarkOverlay(), payload: { ...researchPayload('BENCHMARK_OVERLAY', benchmarkOverlay()), status_reason: 'READY' } },
    {
      request: () => v51Api.sourceCoverage(),
      payload: {
        ...researchPayload('SOURCE_COVERAGE', { ...sourceCoverage(), coverage_status: 'BLOCKED' }),
      },
    },
    {
      request: () => v51Api.sourceCoverage(),
      payload: {
        ...researchPayload('SOURCE_COVERAGE', sourceCoverage()),
        run: { ...run(), source_sha256: 'd'.repeat(64) },
      },
    },
    {
      request: () => v51Api.sourceCoverage(),
      payload: {
        ...researchPayload('SOURCE_COVERAGE', sourceCoverage()),
        source: { ...source(stableArtifactIds.source_coverage), source_artifact_id: stableArtifactIds.causal_panel },
      },
    },
    {
      request: () => v51Api.sourceCoverage(),
      payload: {
        ...researchPayload('SOURCE_COVERAGE', sourceCoverage()),
        artifact: { ...artifact('source_coverage', 'other-source-coverage') },
      },
    },
    {
      request: () => v51Api.accounting(),
      payload: {
        ...researchPayload('ACCOUNTING', accountingSummary()),
        accounting: { ...accountingSummary(), display_cost_percent: '23bp' },
      },
    },
    {
      request: () => v51Api.accounting(),
      payload: {
        ...researchPayload('ACCOUNTING', accountingSummary()),
        accounting: {
          ...accountingSummary(),
          cost_schedule: {
            ...costSchedule,
            primary: { ...costSchedule.primary, round_trip_cost_bp: 46 },
          },
        },
      },
    },
    {
      request: () => v51Api.accounting(),
      payload: {
        ...researchPayload('ACCOUNTING', accountingSummary()),
        accounting: {
          ...accountingSummary(),
          cost_schedule: {
            ...costSchedule,
            zero_cost_control: { ...costSchedule.zero_cost_control, internal_id: 'cost_00bp' },
          },
        },
      },
    },
    {
      request: () => v51Api.accounting(),
      payload: {
        ...researchPayload('ACCOUNTING', accountingSummary()),
        accounting: { ...accountingSummary(), economic_nav_krw: Number.MAX_SAFE_INTEGER + 1 },
      },
    },
    {
      request: () => v51Api.evaluator(),
      payload: {
        ...researchPayload('EVALUATOR', evaluator()),
        evaluator: {
          ...evaluator(),
          metrics: [{ ...evaluator().metrics[0], display_cost_percent: '0.20%' }],
        },
      },
    },
    {
      request: () => v51Api.evaluator(),
      payload: {
        ...researchPayload('EVALUATOR', evaluator()),
        evaluator: {
          ...evaluator(),
          metrics: [{ ...evaluator().metrics[0], internal_cost_id: 'cost_00bp' }],
        },
      },
    },
    {
      request: () => v51Api.benchmarkOverlay(),
      payload: {
        ...researchPayload('BENCHMARK_OVERLAY', benchmarkOverlay()),
        benchmark_overlay: {
          ...benchmarkOverlay(),
          series: [benchmarkOverlay().series[2], benchmarkOverlay().series[0], benchmarkOverlay().series[1]],
        },
      },
    },
    {
      request: () => v51Api.benchmarkOverlay(),
      payload: {
        ...researchPayload('BENCHMARK_OVERLAY', benchmarkOverlay()),
        benchmark_overlay: {
          ...benchmarkOverlay(),
          series: [
            { ...benchmarkOverlay().series[0], provider: 'NAVER', naver_used: true },
            benchmarkOverlay().series[1],
            benchmarkOverlay().series[2],
          ],
        },
      },
    },
    {
      request: () => v51Api.benchmarkOverlay(),
      payload: {
        ...researchPayload('BENCHMARK_OVERLAY', benchmarkOverlay()),
        benchmark_overlay: {
          ...benchmarkOverlay(),
          series: [
            { ...benchmarkOverlay().series[0], provider: 'PYKRX' },
            benchmarkOverlay().series[1],
            benchmarkOverlay().series[2],
          ],
        },
      },
    },
    {
      request: () => v51Api.benchmarkOverlay(),
      payload: {
        ...readyBenchmarkOverlayRoot(),
        benchmark_overlay: {
          ...readyBenchmarkOverlay(),
          series: [
            readyBenchmarkOverlay().series[0],
            readyBenchmarkOverlay().series[1],
            { ...readyBenchmarkOverlay().series[2], provider: 'PYKRX' },
          ],
        },
      },
    },
    {
      request: () => v51Api.benchmarkOverlay(),
      payload: {
        ...researchPayload('BENCHMARK_OVERLAY', benchmarkOverlay()),
        benchmark_overlay: {
          ...benchmarkOverlay(),
          series: [
            { ...benchmarkOverlay().series[0], status: 'READY' },
            benchmarkOverlay().series[1],
            benchmarkOverlay().series[2],
          ],
        },
      },
    },
    {
      request: () => v51Api.benchmarkOverlay(),
      payload: {
        ...researchPayload('BENCHMARK_OVERLAY', benchmarkOverlay()),
        benchmark_overlay: {
          ...benchmarkOverlay(),
          series: [
            benchmarkOverlay().series[0],
            benchmarkOverlay().series[1],
            { ...benchmarkOverlay().series[2], index_100: Number.MAX_SAFE_INTEGER + 1 },
          ],
        },
      },
    },
    { request: () => v51Api.readReport('report-2026-07-17'), payload: { ...reportReadPayload(), report: { ...reportSummary(), relative_path: '../secret.md' } } },
    { request: () => v51Api.readReport('report-2026-07-17'), payload: { ...reportReadPayload(), report: { ...reportSummary(), relative_path: 'Docs/report.md' } } },
    { request: () => v51Api.readReport('report-2026-07-17'), payload: { ...reportReadPayload(), content: { raw_text: '# V5.1\n', safe_html: '<h1>V5.1</h1>' } } },
    { request: () => v51Api.readReport('report-2026-07-17'), payload: { ...reportReadPayload(), content: { raw_text: '# V5.1\n', safe_html: '<article data-kronos-report-html="escaped-pre"><pre>javascript:alert(1)</pre></article>' } } },
  ];

  for (const { request, payload } of invalidCases) {
    await withFetch(response(payload), async () => {
      await assert.rejects(request(), (caught) => caught instanceof V51ApiError && caught.code === 'SCHEMA_INVALID');
    });
  }

  await withFetch(textResponse('{not-json'), async () => {
    await assert.rejects(v51Api.sourceCoverage(), (caught) => caught instanceof V51ApiError && caught.code === 'INVALID_JSON');
  });

  await withFetch(textResponse(JSON.stringify(reportListPayload()), 503), async () => {
    await assert.rejects(v51Api.listReports(), (caught) => caught instanceof V51ApiError && caught.code === 'HTTP_STATUS' && caught.status === 503);
  });

  await withFetch(textResponse('x'.repeat(V51_MAX_RESPONSE_BYTES + 1)), async () => {
    await assert.rejects(v51Api.sourceCoverage(), (caught) => caught instanceof V51ApiError && caught.code === 'RESPONSE_TOO_LARGE');
  });

  await withFetch(textResponse('{}', 200, { 'Content-Length': String(V51_MAX_RESPONSE_BYTES + 1) }), async () => {
    await assert.rejects(v51Api.sourceCoverage(), (caught) => caught instanceof V51ApiError && caught.code === 'RESPONSE_TOO_LARGE');
  });

  await withFetch(textResponse('{}', 200, { 'Content-Length': 'not-a-safe-integer' }), async () => {
    await assert.rejects(v51Api.sourceCoverage(), (caught) => caught instanceof V51ApiError && caught.code === 'RESPONSE_TOO_LARGE');
  });

  await withFetch(textResponse('한'.repeat(3)), async () => {
    await assert.rejects(v51Api.sourceCoverage(undefined, { maxBytes: 5 }), (caught) => caught instanceof V51ApiError && caught.code === 'RESPONSE_TOO_LARGE');
  });
});
