import assert from 'node:assert/strict';
import test from 'node:test';
import { compactOutcomeLabel } from './observedOutcomeChartModel';

test('outcome chart labels keep policy identity without overflowing the axis', () => {
  assert.equal(compactOutcomeLabel('NO_TRADE'), 'NO TRADE');
  assert.equal(compactOutcomeLabel('COST_AWARE_MOMENTUM_RULE'), 'MOMENTUM');
  assert.equal(compactOutcomeLabel('DQN/seed-4'), 'DQN/s4');
  assert.equal(compactOutcomeLabel('CQL_REWARD_SHUFFLED/seed-2'), 'CQL-RS/s2');
  assert.equal(compactOutcomeLabel('CQL_ACTION_SHUFFLED/seed-3'), 'CQL-AS/s3');
});
