import assert from 'node:assert/strict';
import { test } from 'bun:test';
import { runStatusLabel, runStatusTone } from './runStatusModel';

test('run status presentation fails closed for reproduction and contaminated test evidence', () => {
  assert.equal(runStatusLabel('REPRODUCTION_ONLY_VALIDATION_CONSUMED'), 'REPRO ONLY');
  assert.equal(runStatusTone('REPRODUCTION_ONLY_VALIDATION_CONSUMED'), 'warning');
  assert.equal(runStatusLabel('REPRODUCTION_MISMATCH_VALIDATION_CONSUMED'), 'REPRO FAIL');
  assert.equal(runStatusTone('REPRODUCTION_MISMATCH_VALIDATION_CONSUMED'), 'danger');
  assert.equal(runStatusLabel('LEGACY_EXPLORATORY_CANDIDATE_TEST_FEATURES_CONSUMED'), 'LEGACY · TEST CONTAMINATED');
  assert.equal(runStatusTone('LEGACY_EXPLORATORY_CANDIDATE_TEST_FEATURES_CONSUMED'), 'danger');
  assert.equal(runStatusTone('NO_GO_VALIDATION_SCREEN'), 'danger');
  assert.equal(runStatusTone('VALIDATION_CANDIDATE'), 'warning');
});
