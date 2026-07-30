import assert from 'node:assert/strict';
import test from 'node:test';

import type { JsonObject, RlRunDetail } from '$lib/rlApi';
import { D5S_PRESENTATION, formatD5SCheckpointSteps, parseD5SEvidence } from './d5sEvidence';

const metric = {
  accuracy: 0.74,
  reward_ratio: 0.91,
  total_reward: 0.91,
  oracle_reward: 1,
  trade_rate: 0.8,
  dominant_action_rate: 0.4,
  invalid_action_count: 0,
};

function runWithModels(models: readonly JsonObject[]): Pick<RlRunDetail, 'name' | 'summary' | 'detail'> {
  return {
    name: 'type2-d5s-primary',
    summary: {
      research_lane: 'rl_discovery',
      status: 'COMPLETE',
      verdict: 'D5S_STABILITY_CONFIRMED',
      profile: 'PRIMARY',
      fresh_oos: 'NOT_RUN_NO_READ',
      type1_outcome: 'D5S_STABILITY_EVALUATED',
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
        verdict: 'D5S_STABILITY_CONFIRMED',
        selected_steps: 200_000,
        selected_native_median_accuracy: 0.74,
        selected_native_median_reward_ratio: 0.91,
        selected_native_reward_delta_vs_shuffled: 0.80,
        accuracy_degradation_at_400k: 0.01,
        reward_ratio_degradation_at_400k: 0.03,
        preserved_native_seed_fraction: 1,
        invalid_action_count: 0,
      },
    },
  };
}

const checkpoints = [50_000, 100_000, 150_000, 200_000, 300_000, 400_000] as const;
const models: readonly JsonObject[] = ['NATIVE', 'SHUFFLED'].flatMap((rewardArm) =>
  [0, 1, 2].flatMap((seed) => checkpoints.map((steps) => ({
    reward_arm: rewardArm,
    seed,
    total_steps: steps,
    fit_23bp: metric,
    native_23bp: rewardArm === 'NATIVE' ? metric : { ...metric, reward_ratio: 0.11 },
    native_0bp: metric,
  }))),
);

test('parseD5SEvidence preserves the exact 36-unit stability matrix', () => {
  const evidence = parseD5SEvidence(runWithModels(models));

  assert.equal(evidence?.arms.length, 36);
  assert.equal(evidence?.selectedSteps, 200_000);
  assert.equal(evidence?.selectedNativeMedianRewardRatio, 0.91);
  assert.equal(evidence?.nativeDeltaVsShuffled, 0.80);
  assert.equal(evidence?.preservedNativeSeedFraction, 1);
  assert.equal(evidence?.freshOos, 'NOT_RUN_NO_READ');
});

test('parseD5SEvidence rejects incomplete or nonzero-invalid matrices', () => {
  assert.equal(parseD5SEvidence(runWithModels(models.slice(0, -1))), null);
  const invalid: readonly JsonObject[] = models.map((row, index) => index === 0
    ? { ...row, native_23bp: { ...metric, invalid_action_count: 1 } }
    : row);
  assert.equal(parseD5SEvidence(runWithModels(invalid)), null);
});

test('D5S presentation uses readable checkpoints and keeps validation sealed', () => {
  assert.equal(formatD5SCheckpointSteps(50_000), '50K');
  assert.equal(formatD5SCheckpointSteps(100_000), '100K');
  assert.equal(formatD5SCheckpointSteps(123), 'MISSING');
  assert.deepEqual(D5S_PRESENTATION, {
    d6Seal: 'D6 remains sealed',
    d7Seal: 'D7 remains sealed',
    claimBoundary: 'RESEARCH ONLY',
  });
});
