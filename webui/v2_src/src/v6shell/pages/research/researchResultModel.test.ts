import assert from 'node:assert/strict';
import { test } from 'bun:test';
import { resultEvidenceHealth } from './researchResultModel';
import { ResearchRunSchema } from '../../api/researchApi';

test('result evidence health counts only directly observed metadata fields', () => {
  const run = ResearchRunSchema.parse({
    run_id: 'lane/run', name: 'run', lane: 'daily_close', status: 'NO-GO',
    algorithm: 'MISSING', dataset_id: 'dataset-1', updated_at: '2026-08-06T00:00:00Z',
    source_file: 'summary.json', artifact_count: 2,
    detail_url: '/api/v6/research-runs/lane/run',
  });

  assert.deepEqual(resultEvidenceHealth(run), {
    observed: 3,
    total: 4,
    percent: 75,
    missing: ['알고리즘'],
  });
});
