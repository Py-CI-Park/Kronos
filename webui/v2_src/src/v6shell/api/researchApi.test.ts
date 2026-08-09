import assert from 'node:assert/strict';
import test from 'node:test';
import ky from 'ky';

import {
  ResearchPageSchema,
  ResearchRunDetailSchema,
  ResearchSummarySchema,
  buildResearchRunsUrl,
  loadResearchSummary,
} from './researchApi';

const run = {
  run_id: 'daily_close_cql_seed0',
  name: 'daily_close_cql_seed0',
  lane: 'daily_close',
  status: 'NO_GO',
  algorithm: 'CQL',
  dataset_id: 'daily-close-v2',
  updated_at: '2026-08-05T00:00:00Z',
  source_file: 'rl_live_summary.json',
  artifact_count: 2,
  detail_url: '/api/v6/research-runs/daily_close_cql_seed0',
};

const summaryPayload = {
  schema_version: 'kronos_v6_research_summary.v1', status: 'OK', generated_at: '2026-08-05T00:00:00Z',
  program: { maturity_score: 70, implementation_score: 94, economic_model_score: 20, live_readiness_score: 0 },
  catalog: { total: 1, by_status: { NO_GO: 1 }, latest_run: run },
  claims: { profitability: false, live_ready: false, fresh_oos_opened: false },
} as const;

function delayedSummaryFetch(delayMs: number): typeof fetch {
  return async (input, init) => {
    const signal = input instanceof Request ? input.signal : init?.signal;
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(resolve, delayMs);
      signal?.addEventListener('abort', () => {
        clearTimeout(timer);
        reject(new DOMException('Request aborted', 'AbortError'));
      }, { once: true });
    });
    return new Response(JSON.stringify(summaryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };
}

test('summary request distinguishes a slow success from a real bounded timeout', async () => {
  const client = ky.create({ fetch: delayedSummaryFetch(25), retry: 0 });
  const testUrl = 'http://kronos.test/api/v6/summary';
  const slowSuccess = await loadResearchSummary(50, client, testUrl);
  assert.equal(slowSuccess.ok, true);

  const timedOut = await loadResearchSummary(5, client, testUrl);
  assert.deepEqual(timedOut, { ok: false, kind: 'timeout', message: '응답 제한 시간을 초과했습니다.' });
});

test('research schemas parse the catalog summary page and detail boundaries', () => {
  // Given
  const page = { schema_version: 'kronos_v6_research_runs.v1', status: 'OK', items: [run], total: 1, page: 1, page_size: 40 };
  const detail = {
    schema_version: 'kronos_v6_research_run_detail.v1', status: 'OK', run,
    artifacts: [{ name: 'events.jsonl', relative_path: 'daily_close_cql_seed0/events.jsonl', size_bytes: 12, modified_at: '2026-08-05T00:00:00Z' }],
    evidence_scope: 'DIRECT_DIRECTORY_METADATA_ONLY',
    observed_outcome: {
      scope: 'DIRECT_SUMMARY_NUMERIC_ONLY', source_file: 'rl_live_summary.json', headline: 'NO_GO', reasons: ['cost gate'],
      series: [{ label: 'CQL', total_net_pnl_krw: -1200, total_cost_krw: 300, mean_reward: -0.001 }],
    },
  };

  // When / Then
  assert.equal(ResearchSummarySchema.parse(summaryPayload).program.economic_model_score, 20);
  assert.equal(ResearchPageSchema.parse(page).items[0]?.run_id, 'daily_close_cql_seed0');
  assert.equal(ResearchRunDetailSchema.parse(detail).artifacts[0]?.name, 'events.jsonl');
  assert.equal(ResearchRunDetailSchema.parse(detail).observed_outcome.series[0]?.total_net_pnl_krw, -1200);
});

test('research schemas reject a catalog row without explicit evidence identity', () => {
  // Given
  const invalid = { schema_version: 'kronos_v6_research_runs.v1', status: 'OK', items: [{ ...run, source_file: undefined }], total: 1, page: 1, page_size: 40 };

  // When / Then
  assert.equal(ResearchPageSchema.safeParse(invalid).success, false);
});

test('research catalog URL preserves encoded filters without empty parameters', () => {
  // Given / When
  const url = buildResearchRunsUrl({ search: 'CQL seed', lane: 'daily_close', status: 'NO_GO', page: 2, pageSize: 20 });

  // Then
  assert.equal(url, '/api/v6/research-runs?search=CQL+seed&lane=daily_close&status=NO_GO&page=2&page_size=20');
});
