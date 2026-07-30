import assert from 'node:assert/strict';
import test from 'node:test';

import { parseDiscoveryEvidence } from './discoveryEvidence';
import { d5rArm } from './d5rEvidence';

const metric = {
  accuracy: 0.51,
  reward_ratio: 0.49,
  dominant_action_rate: 0.31,
  invalid_action_count: 0,
};

test('d5rArm parses only registered capacity checkpoints', () => {
  const row = d5rArm({
    reward_arm: 'NATIVE',
    seed: 2,
    total_steps: 800_000,
    fit_23bp: metric,
    native_23bp: metric,
    native_0bp: { ...metric, reward_ratio: 0.55 },
  });

  assert.equal(row?.id, 'D5R-C_DQN_DISCRETE/NATIVE/800000');
  assert.equal(row?.trainingTimesteps, 800_000);
  assert.equal(row?.diagnosticCostRewardRatio, 0.55);
  assert.equal(d5rArm({ ...row, total_steps: 600_000 }), null);
});

test('parseDiscoveryEvidence preserves the exact D5R gate and 12-unit matrix', () => {
  const models = ['NATIVE', 'SHUFFLED'].flatMap((rewardArm) =>
    [0, 1, 2].flatMap((seed) => [400_000, 800_000].map((steps) => ({
      reward_arm: rewardArm,
      seed,
      total_steps: steps,
      fit_23bp: metric,
      native_23bp: metric,
      native_0bp: metric,
    }))),
  );
  const evidence = parseDiscoveryEvidence({
    name: 'type2-d5r-primary',
    summary: {
      research_lane: 'rl_discovery',
      status: 'COMPLETE',
      verdict: 'D5R_CAPACITY_NOT_CONFIRMED',
      profile: 'PRIMARY',
      fresh_oos: 'NOT_RUN_NO_READ',
      type1_outcome: 'D5R_CAPACITY_EVALUATED',
      primary_round_trip_cost_bp: 23,
      diagnostic_round_trip_cost_bp: 0,
      prereg_sha256: 'a'.repeat(64),
      artifact_manifest_sha256: 'b'.repeat(64),
      promotion_allowed: false,
      profitability_claim_allowed: false,
    },
    detail: {
      models,
      reused_validation: 'NOT_RUN_NO_READ',
      gate: {
        native_accuracy_lift: 0.01,
        native_reward_ratio_lift: 0.02,
        native_reward_delta_vs_shuffled: 0.4,
        improving_seed_fraction: 2 / 3,
      },
    },
  });

  assert.equal(evidence?.arms.length, 12);
  assert.equal(evidence?.nativeRewardRatioLift, 0.02);
  assert.equal(evidence?.nativeDeltaVsShuffled, 0.4);
  assert.equal(evidence?.reusedValidation, 'NOT_RUN_NO_READ');
});
