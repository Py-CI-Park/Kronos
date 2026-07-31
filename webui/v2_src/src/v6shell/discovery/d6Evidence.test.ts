import assert from 'node:assert/strict';
import test from 'node:test';

import type { JsonObject, RlRunDetail } from '$lib/rlApi';
import { D6_PRESENTATION, parseD6Evidence } from './d6Evidence';

const values = [
  ['NATIVE', 0, 0.1796875, -0.0373957, -0.302731, 0.9375, 0.591866],
  ['NATIVE', 1, 0.1484375, -0.0326273, -0.264129, 0.8984375, 0.810130],
  ['NATIVE', 2, 0.1796875, -0.105328, -0.852663, 0.8828125, 1.102873],
  ['SHUFFLED', 0, 0.140625, -0.101667, -0.823026, 0.9453125, 1.055642],
  ['SHUFFLED', 1, 0.1484375, 0.001820, 0.014733, 0.9375, 0.305350],
  ['SHUFFLED', 2, 0.2109375, 0.054725, 0.443015, 0.9453125, 0.683464],
] as const;

const evaluations: readonly JsonObject[] = values.map(
  ([rewardArm, seed, accuracy, rewardRatio, totalReward, tradeRate, drawdown]) => ({
    reward_arm: rewardArm,
    seed,
    selected_steps: 100_000,
    source_model_sha256: `${seed}${rewardArm === 'NATIVE' ? 'a' : 'b'}`.padEnd(64, '0'),
    validation_23bp: {
      accuracy,
      reward_ratio: rewardRatio,
      total_reward: totalReward,
      oracle_reward: 8.095,
      trade_rate: tradeRate,
      dominant_action_rate: 0.3,
      invalid_action_count: 0,
    },
    validation_0bp: {
      accuracy,
      reward_ratio: rewardRatio + 0.03,
      total_reward: totalReward + 0.25,
      oracle_reward: 8.36,
      trade_rate: tradeRate,
      dominant_action_rate: 0.3,
      invalid_action_count: 0,
    },
    maximum_drawdown_23bp: drawdown,
  }),
);

function runWithEvaluations(rows: readonly JsonObject[]): Pick<RlRunDetail, 'name' | 'summary' | 'detail'> {
  return {
    name: 'type2-d6-primary-20260731-002',
    summary: {
      research_lane: 'rl_discovery',
      status: 'COMPLETE',
      verdict: 'D6_REUSED_VALIDATION_NOT_CONFIRMED',
      profile: 'PRIMARY',
      fresh_oos: 'NOT_RUN_NO_READ',
      type1_outcome: 'D6_REUSED_VALIDATION_NOT_CONFIRMED',
      primary_round_trip_cost_bp: 23,
      diagnostic_round_trip_cost_bp: 0,
      prereg_sha256: 'a'.repeat(64),
      artifact_manifest_sha256: 'b'.repeat(64),
      promotion_allowed: false,
      profitability_claim_allowed: false,
    },
    detail: {
      evaluations: rows,
      reused_validation: 'COMPLETE',
      fresh_oos: 'NOT_RUN_NO_READ',
      validation_episode_count: 128,
      validation_episode_sha256: 'c'.repeat(64),
      validation_origin: 'FAILED_RUN_SNAPSHOT',
      validation_read_count: 1,
      recovery_run: 'type2-d6-primary-20260731-001',
      gate: {
        verdict: 'D6_REUSED_VALIDATION_NOT_CONFIRMED',
        native_median_accuracy: 0.1796875,
        native_median_reward_ratio: -0.0373957,
        native_median_total_reward: -0.302731,
        shuffled_median_reward_ratio: 0.001820,
        native_reward_delta_vs_shuffled: -0.0392157,
        native_passing_seed_fraction: 0,
        native_median_reward_drawdown: 0.810130,
        invalid_action_count: 0,
        fresh_oos: 'NOT_RUN_NO_READ',
        promotion_allowed: false,
        profitability_claim_allowed: false,
      },
    },
  };
}

test('parseD6Evidence preserves the exact six-unit validation no-go', () => {
  const evidence = parseD6Evidence(runWithEvaluations(evaluations));

  assert.equal(evidence?.verdict, 'D6_REUSED_VALIDATION_NOT_CONFIRMED');
  assert.equal(evidence?.evaluations.length, 6);
  assert.equal(evidence?.nativeMedianAccuracy, 0.1796875);
  assert.equal(evidence?.nativeRewardDeltaVsShuffled, -0.0392157);
  assert.equal(evidence?.validationEpisodeCount, 128);
  assert.equal(evidence?.freshOos, 'NOT_RUN_NO_READ');
});

test('parseD6Evidence rejects an incomplete matrix or opened Fresh OOS', () => {
  assert.equal(parseD6Evidence(runWithEvaluations(evaluations.slice(0, -1))), null);
  const sealed = runWithEvaluations(evaluations);
  const opened = {
    ...sealed,
    detail: sealed.detail ? { ...sealed.detail, fresh_oos: 'COMPLETE' } : undefined,
  };
  assert.equal(parseD6Evidence(opened), null);
});

test('D6 presentation keeps failed gates and D7 lock visible', () => {
  assert.deepEqual(D6_PRESENTATION, {
    gateStatus: '1 / 7 GATES PASS',
    d7Seal: 'D7 LOCKED',
    claimBoundary: 'RESEARCH ONLY',
  });
});
