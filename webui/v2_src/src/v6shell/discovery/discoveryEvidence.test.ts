import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { parseDiscoveryEvidence, summarizeDiscoveryArms } from './discoveryEvidence';
import { REVIEWED_DISCOVERY_SNAPSHOT } from './reviewedDiscoverySnapshot';

const discoveryPage = readFileSync(new URL('../pages/DiscoveryPage.svelte', import.meta.url), 'utf8');

test('discovery evidence parser accepts the dashboard run detail contract', () => {
  const evidence = parseDiscoveryEvidence({
    name: 'type2-d0-smoke-20260726T211644+0900',
    summary: {
      research_lane: 'rl_discovery', status: 'SMOKE_COMPLETE', verdict: 'SMOKE_INCOMPLETE',
      fresh_oos: 'NOT_RUN_NO_READ', type1_outcome: 'COMPLETE_NO_GO', profile: 'SMOKE',
      prereg_sha256: 'abc123', promotion_allowed: false, profitability_claim_allowed: false,
    },
    detail: { models: [
      { algorithm: 'A_PPO_ONLY', model: 'A_PPO_ONLY/seed-0', training_timesteps: 256,
        oracle_reward_ratio: -0.34, exact_basket_accuracy: 0.25, dominant_action_rate: 0.625,
        invalid_action_count: 0, block_count: 0, no_fill_count: 0, shuffled_reward: false },
    ] },
  });

  assert.equal(evidence?.runName, 'type2-d0-smoke-20260726T211644+0900');
  assert.equal(evidence?.arms[0]?.oracleRewardRatio, -0.34);
  assert.equal(evidence?.arms[0]?.seed, 0);
  assert.equal(evidence?.promotionAllowed, false);
});

test('primary discovery evidence preserves seed identity and computes arm aggregates', () => {
  const evidence = parseDiscoveryEvidence({
    name: 'type2-d0-primary-20260727',
    summary: {
      research_lane: 'rl_discovery', status: 'PRIMARY_COMPLETE',
      verdict: 'PPO_ONLY_OVERFIT_NOT_CONFIRMED', fresh_oos: 'NOT_RUN_NO_READ',
      type1_outcome: 'COMPLETE_NO_GO', profile: 'PRIMARY', prereg_sha256: 'abc123',
      promotion_allowed: false, profitability_claim_allowed: false,
    },
    detail: { models: [
      { algorithm: 'A_PPO_ONLY', model: 'A_PPO_ONLY/seed-0', seed: 0,
        training_timesteps: 104000, oracle_reward_ratio: .75, exact_basket_accuracy: .8125,
        dominant_action_rate: .4375, invalid_action_count: 0, block_count: 0,
        no_fill_count: 0, shuffled_reward: false },
      { algorithm: 'A_PPO_ONLY', model: 'A_PPO_ONLY/seed-1', seed: 1,
        training_timesteps: 104000, oracle_reward_ratio: .125, exact_basket_accuracy: .34375,
        dominant_action_rate: .90625, invalid_action_count: 0, block_count: 0,
        no_fill_count: 0, shuffled_reward: false },
    ] },
  });

  const aggregates = summarizeDiscoveryArms(evidence?.arms ?? []);

  assert.deepEqual(evidence?.arms.map((arm) => arm.seed), [0, 1]);
  assert.equal(aggregates[0]?.id, 'A_PPO_ONLY');
  assert.equal(aggregates[0]?.seedCount, 2);
  assert.equal(aggregates[0]?.meanOracleRewardRatio, .4375);
});

test('discovery evidence parser rejects another research lane', () => {
  assert.equal(parseDiscoveryEvidence({ name: 'legacy', summary: { research_lane: 'rule' } }), null);
});

test('discovery page keeps conclusions artifact-driven and handles API failure', () => {
  assert.match(discoveryPage, /catch \{/);
  assert.match(discoveryPage, /evidence\.verdict/);
  assert.match(discoveryPage, /summarizeDiscoveryArms\(evidence\.arms\)/);
  assert.doesNotMatch(discoveryPage, /세 seed 모두 0\.90/);
  assert.doesNotMatch(discoveryPage, /\/ NO-GO<\/b>/);
});

test('reviewed snapshot keeps clean-checkout evidence bound to the committed manifest', () => {
  assert.equal(REVIEWED_DISCOVERY_SNAPSHOT.authority, 'REVIEWED_SNAPSHOT');
  assert.equal(REVIEWED_DISCOVERY_SNAPSHOT.arms.length, 12);
  assert.match(REVIEWED_DISCOVERY_SNAPSHOT.evidenceManifest ?? '', /^[0-9a-f]{64}$/);
  assert.deepEqual(
    [...new Set(REVIEWED_DISCOVERY_SNAPSHOT.arms.map((row) => row.seed))],
    [0, 1, 2],
  );
});
