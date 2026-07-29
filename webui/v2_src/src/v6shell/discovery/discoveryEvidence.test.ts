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
      prereg_sha256: 'abc123', primary_round_trip_cost_bp: 23,
      promotion_allowed: false, profitability_claim_allowed: false,
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
  assert.equal(evidence?.primaryRoundTripCostBp, 23);
});

test('primary discovery evidence preserves seed identity and computes arm aggregates', () => {
  const evidence = parseDiscoveryEvidence({
    name: 'type2-d0-primary-20260727',
    summary: {
      research_lane: 'rl_discovery', status: 'PRIMARY_COMPLETE',
      verdict: 'PPO_ONLY_OVERFIT_NOT_CONFIRMED', fresh_oos: 'NOT_RUN_NO_READ',
      type1_outcome: 'COMPLETE_NO_GO', profile: 'PRIMARY', prereg_sha256: 'abc123',
      primary_round_trip_cost_bp: 23,
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

test('reviewed snapshot keeps D4 algorithm evidence bound to the committed custody', () => {
  assert.equal(REVIEWED_DISCOVERY_SNAPSHOT.authority, 'REVIEWED_SNAPSHOT');
  assert.equal(REVIEWED_DISCOVERY_SNAPSHOT.runName, 'type2-d4-primary-20260729-v2');
  assert.equal(REVIEWED_DISCOVERY_SNAPSHOT.verdict, 'D4_ALGORITHM_OBJECTIVE_CONFIRMED');
  assert.equal(REVIEWED_DISCOVERY_SNAPSHOT.arms.length, 24);
  assert.equal(REVIEWED_DISCOVERY_SNAPSHOT.confirmedRlArmCount, 1);
  assert.equal(REVIEWED_DISCOVERY_SNAPSHOT.bestRlArm, 'C_DQN_DISCRETE');
  assert.equal(REVIEWED_DISCOVERY_SNAPSHOT.supervisedCeilingConfirmed, true);
  assert.ok((REVIEWED_DISCOVERY_SNAPSHOT.bestRlGapToSupervisedCeiling ?? 1) < .013);
  assert.ok((REVIEWED_DISCOVERY_SNAPSHOT.nativeDeltaVsShuffled ?? 0) > 1.09);
  assert.match(REVIEWED_DISCOVERY_SNAPSHOT.evidenceManifest ?? '', /^[0-9a-f]{64}$/);
  assert.deepEqual(
    [...new Set(REVIEWED_DISCOVERY_SNAPSHOT.arms.map((row) => row.seed))],
    [0, 1, 2],
  );
});

test('D1 primary parser preserves all reduced-action arm seeds', () => {
  const evidence = parseDiscoveryEvidence({
    name: 'type2-d1-primary-v3-20260728',
    summary: {
      research_lane: 'rl_discovery', status: 'PRIMARY_COMPLETE',
      verdict: 'D1_ACTION_REWARD_CONFIRMED', fresh_oos: 'NOT_RUN_NO_READ',
      type1_outcome: 'COMPLETE_NO_GO', profile: 'PRIMARY', prereg_sha256: 'abc123',
      primary_round_trip_cost_bp: 23,
      promotion_allowed: false, profitability_claim_allowed: false,
    },
    detail: { models: [0, 1, 2].map((seed) => ({
      algorithm: 'A_BINARY_NATIVE', model: `A_BINARY_NATIVE/seed-${seed}`, seed,
      training_timesteps: 16384, oracle_reward_ratio: 1, exact_basket_accuracy: 1,
      dominant_action_rate: .75, invalid_action_count: 0, block_count: 0,
      no_fill_count: 0, shuffled_reward: false,
    })) },
  });

  assert.deepEqual(evidence?.arms.map((arm) => arm.seed), [0, 1, 2]);
  assert.match(discoveryPage, /action \/ reward/);
  assert.match(discoveryPage, /historical scale/);
});

test('D4 reviewed page exposes train-only confirmation, cost diagnostic, and blocked claims', () => {
  assert.match(discoveryPage, /D4 algorithm \/ objective/);
  assert.match(discoveryPage, /23bp diagnostic/i);
  assert.match(discoveryPage, /confirmedRlArmCount/);
  assert.equal(REVIEWED_DISCOVERY_SNAPSHOT.primaryRoundTripCostBp, 0);
  assert.equal(REVIEWED_DISCOVERY_SNAPSHOT.diagnosticRoundTripCostBp, 23);
  assert.equal(REVIEWED_DISCOVERY_SNAPSHOT.promotionAllowed, false);
});

test('live D4 nested summary preserves RL ceiling gap and all gate fields', () => {
  const evidence = parseDiscoveryEvidence({
    name: 'type2-d4-primary-20260729-v2',
    summary: { research_lane: 'rl_discovery', status: 'COMPLETE', verdict: 'D4_ALGORITHM_OBJECTIVE_CONFIRMED', profile: 'PRIMARY', fresh_oos: 'NOT_RUN_NO_READ', prereg_sha256: 'abc123', primary_round_trip_cost_bp: 0, diagnostic_round_trip_cost_bp: 23, promotion_allowed: false, profitability_claim_allowed: false },
    detail: { gate: { best_rl_arm: 'C_DQN_DISCRETE', best_rl_gap_to_supervised_ceiling: .0124, supervised_ceiling_confirmed: true, confirmed_rl_arms: ['C_DQN_DISCRETE'] }, models: [{ algorithm_arm: 'C_DQN_DISCRETE', reward_arm: 'NATIVE', seed: 2, rl_timesteps: 65536, fit: { accuracy: .90625, reward_ratio: .984, dominant_action_rate: .21875, invalid_action_count: 0 }, native: { reward_ratio: .984 }, cost_23bp: { reward_ratio: .982 } }] },
  });
  assert.equal(evidence?.arms[0]?.id, 'D4-C_DQN_DISCRETE/NATIVE');
  assert.equal(evidence?.bestRlArm, 'C_DQN_DISCRETE');
  assert.equal(evidence?.confirmedRlArmCount, 1);
  assert.equal(evidence?.supervisedCeilingConfirmed, true);
  assert.equal(evidence?.bestRlGapToSupervisedCeiling, .0124);
});

test('live D3 nested summary preserves best arm, budget lift, and all units', () => {
  const evidence = parseDiscoveryEvidence({
    name: 'type2-d3-primary-20260729-v1',
    summary: {
      research_lane: 'rl_discovery', status: 'COMPLETE', verdict: 'D3_REPRESENTATION_ACTION_NOT_CONFIRMED',
      profile: 'PRIMARY', fresh_oos: 'NOT_RUN_NO_READ', type1_outcome: 'COMPLETE_NO_GO',
      prereg_sha256: 'abc123', primary_round_trip_cost_bp: 0,
      diagnostic_round_trip_cost_bp: 23, promotion_allowed: false,
      profitability_claim_allowed: false,
    },
    detail: { gate: {
      best_policy_arm: 'D_TOP5_CONTEXT_4X', confirmed_policy_arms: [],
      budget_4x_native_lift: .067865,
      native_delta_vs_shuffled: [['D_TOP5_CONTEXT_4X', .760268]],
    }, models: [{
      policy_arm: 'D_TOP5_CONTEXT_4X', reward_arm: 'NATIVE', seed: 2,
      training_timesteps: 65536,
      fit: { accuracy: .43, reward_ratio: .572, dominant_action_rate: .28, invalid_action_count: 0 },
      native: { reward_ratio: .572 }, cost_23bp: { reward_ratio: .552 },
    }] },
  });

  assert.equal(evidence?.arms[0]?.id, 'D3-D_TOP5_CONTEXT_4X/NATIVE');
  assert.equal(evidence?.bestPolicyArm, 'D_TOP5_CONTEXT_4X');
  assert.equal(evidence?.confirmedPolicyArmCount, 0);
  assert.equal(evidence?.budget4xNativeLift, .067865);
  assert.equal(evidence?.nativeDeltaVsShuffled, .760268);
});

test('live D2 nested summary parses without falling back to the reviewed snapshot', () => {
  const evidence = parseDiscoveryEvidence({
    name: 'type2-d2-primary-20260728-v1',
    summary: {
      research_lane: 'rl_discovery', status: 'COMPLETE', verdict: 'D2_PARTIAL_CAPACITY_CONFIRMED',
      profile: 'PRIMARY', fresh_oos: 'NOT_RUN_NO_READ', type1_outcome: 'COMPLETE_NO_GO',
      prereg_sha256: 'abc123', primary_round_trip_cost_bp: 0,
      diagnostic_round_trip_cost_bp: 23, promotion_allowed: false,
      profitability_claim_allowed: false,
    },
    detail: { gate: {
      maximum_confirmed_episode_count: 8,
      native_delta_vs_shuffled_at_128: .5355,
    }, models: [{
      arm: 'A_NATIVE', episode_count: 128, seed: 2, training_timesteps: 16384,
      fit: { accuracy: .71, reward_ratio: .52, dominant_action_rate: .8, invalid_action_count: 0 },
      native: { reward_ratio: .52 }, cost_23bp: { reward_ratio: .519 },
    }] },
  });

  assert.equal(evidence?.arms[0]?.id, 'D2-128/A_NATIVE');
  assert.equal(evidence?.arms[0]?.diagnosticCostRewardRatio, .519);
  assert.equal(evidence?.diagnosticRoundTripCostBp, 23);
  assert.equal(evidence?.maximumConfirmedEpisodeCount, 8);
  assert.equal(evidence?.nativeDeltaVsShuffled, .5355);
});
