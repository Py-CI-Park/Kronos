import assert from 'node:assert/strict';
import { test } from 'bun:test';
import { GovernanceSummarySchema } from './governanceApi';

test('governance summary schema preserves hashes deferred linkage and sealed claims', () => {
  const parsed = GovernanceSummarySchema.parse({
    schema_version: 'kronos_v6_governance_summary.v1',
    status: 'OK',
    generated_at: '2026-08-05T00:00:00Z',
    preregistrations: [{ prereg_id: 'daily-v9', doc: 'kronos_v9_prereg.json', status: 'FROZEN', frozen_utc: '2026-08-05T00:00:00Z', family: 'CQL', sha256: 'a'.repeat(64), linkage_state: 'DETAIL_DEFERRED' }],
    result_docs: [{ doc: 'kronos_v9_result.md', size_bytes: 10, sha256: 'b'.repeat(64) }],
    claims: { fresh_oos_opened: false, promotion_allowed: false, human_approval_required: true },
  });

  assert.equal(parsed.preregistrations[0].linkage_state, 'DETAIL_DEFERRED');
  assert.equal(parsed.claims.fresh_oos_opened, false);
  assert.equal(parsed.result_docs[0].sha256.length, 64);
});
