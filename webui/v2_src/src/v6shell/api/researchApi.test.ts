import assert from 'node:assert/strict';
import test from 'node:test';

import {
  ResearchPageSchema,
  ResearchRunDetailSchema,
  ResearchSummarySchema,
  buildResearchRunsUrl,
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

test('research schemas parse the catalog summary page and detail boundaries', () => {
  // Given
  const summary = {
    schema_version: 'kronos_v6_research_summary.v1', status: 'OK', generated_at: '2026-08-05T00:00:00Z',
    program: { maturity_score: 63, implementation_score: 78, economic_model_score: 20, live_readiness_score: 0 },
    catalog: { total: 1, by_status: { NO_GO: 1 }, latest_run: run },
    claims: { profitability: false, live_ready: false, fresh_oos_opened: false },
  };
  const page = { schema_version: 'kronos_v6_research_runs.v1', status: 'OK', items: [run], total: 1, page: 1, page_size: 40 };
  const detail = { schema_version: 'kronos_v6_research_run_detail.v1', status: 'OK', run, artifacts: [{ name: 'events.jsonl', relative_path: 'daily_close_cql_seed0/events.jsonl', size_bytes: 12, modified_at: '2026-08-05T00:00:00Z' }], evidence_scope: 'DIRECT_DIRECTORY_METADATA_ONLY' };

  // When / Then
  assert.equal(ResearchSummarySchema.parse(summary).program.economic_model_score, 20);
  assert.equal(ResearchPageSchema.parse(page).items[0]?.run_id, 'daily_close_cql_seed0');
  assert.equal(ResearchRunDetailSchema.parse(detail).artifacts[0]?.name, 'events.jsonl');
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
