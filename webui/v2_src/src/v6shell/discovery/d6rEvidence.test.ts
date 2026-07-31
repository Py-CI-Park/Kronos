import assert from 'node:assert/strict';
import test from 'node:test';

import type { JsonObject, RlRunDetail } from '$lib/rlApi';
import { parseD6REvidence } from './d6rEvidence';

function evaluation(
  profile: 'COST_ONLY' | 'TURNOVER_10BP',
  rewardArm: 'NATIVE' | 'SHUFFLED',
  seed: number,
  foldId: number,
): JsonObject {
  const tradeRate = profile === 'COST_ONLY' ? 0.82 : 0.51;
  const totalReward = rewardArm === 'NATIVE' ? 0.18 : 0.04;
  const metric = {
    accuracy: 0.24,
    reward_ratio: rewardArm === 'NATIVE' ? 0.12 : 0.01,
    total_reward: totalReward,
    oracle_reward: 1.0,
    trade_rate: tradeRate,
    dominant_action_rate: 0.4,
    invalid_action_count: 0,
  };
  return {
    profile,
    reward_arm: rewardArm,
    seed,
    fold_id: foldId,
    training_steps: 50_000,
    training_episode_count: 323 + foldId * 50,
    evaluation_episode_count: 50,
    additional_trade_penalty_bp: profile === 'COST_ONLY' ? 0 : 10,
    evaluation_23bp: metric,
    evaluation_0bp: metric,
    maximum_drawdown_23bp: 0.12,
  };
}

const evaluations: readonly JsonObject[] = ['COST_ONLY', 'TURNOVER_10BP'].flatMap((profile) =>
  ['NATIVE', 'SHUFFLED'].flatMap((rewardArm) =>
    [0, 1, 2].flatMap((seed) =>
      [0, 1, 2, 3, 4].map((foldId) =>
        evaluation(
          profile === 'COST_ONLY' ? 'COST_ONLY' : 'TURNOVER_10BP',
          rewardArm === 'NATIVE' ? 'NATIVE' : 'SHUFFLED',
          seed,
          foldId,
        ),
      ),
    ),
  ),
);

function runWithEvaluations(rows: readonly JsonObject[]): Pick<RlRunDetail, 'name' | 'summary' | 'detail'> {
  return {
    name: 'type2-d6r-primary-20260731-001',
    summary: {
      research_lane: 'rl_discovery',
      status: 'COMPLETE',
      verdict: 'D6R_TRAIN_FALSIFICATION_NOT_CONFIRMED',
      profile: 'PRIMARY',
      fresh_oos: 'NOT_RUN_NO_READ',
      primary_round_trip_cost_bp: 23,
      diagnostic_round_trip_cost_bp: 0,
      prereg_sha256: 'a'.repeat(64),
      artifact_manifest_sha256: 'b'.repeat(64),
      promotion_allowed: false,
      profitability_claim_allowed: false,
      live_broker_order_allowed: false,
    },
    detail: {
      evaluations: rows,
      training_partition: 'TRAIN_ONLY',
      normalizer: 'EXISTING_FULL_TRAIN_ONLY_NORMALIZER_NO_REFIT',
      reused_validation: 'NO_READ_ALREADY_CONSUMED_DIAGNOSTIC_ONLY',
      fresh_oos: 'NOT_RUN_NO_READ',
      d7: 'LOCKED',
      candidate_is_not_confirmation: true,
      promotion_allowed: false,
      profitability_claim_allowed: false,
      paper_forward_allowed: false,
      live_broker_order_allowed: false,
      gate: {
        verdict: 'D6R_TRAIN_FALSIFICATION_NOT_CONFIRMED',
        native_median_accuracy: 0.24,
        native_median_reward_ratio: 0.12,
        native_median_total_reward: 0.18,
        native_reward_delta_vs_shuffled: 0.11,
        positive_fold_fraction: 1,
        positive_seed_fraction: 1,
        native_median_trade_rate: 0.51,
        trade_rate_reduction_vs_cost_only: 0.31,
        native_median_reward_drawdown: 0.12,
        invalid_action_count: 0,
        passed_gate_count: 9,
        total_gate_count: 10,
      },
    },
  };
}

test('parseD6REvidence preserves the exact 60-unit TRAIN_ONLY matrix', () => {
  const evidence = parseD6REvidence(runWithEvaluations(evaluations));

  assert.equal(evidence?.evaluations.length, 60);
  assert.equal(evidence?.passedGateCount, 9);
  assert.equal(evidence?.foldCount, 5);
  assert.equal(evidence?.freshOos, 'NOT_RUN_NO_READ');
  assert.equal(evidence?.d7, 'LOCKED');
});

test('parseD6REvidence rejects an incomplete matrix or an opened D7', () => {
  assert.equal(parseD6REvidence(runWithEvaluations(evaluations.slice(1))), null);
  const sealed = runWithEvaluations(evaluations);
  const opened = {
    ...sealed,
    detail: sealed.detail ? { ...sealed.detail, d7: 'OPEN' } : undefined,
  };
  assert.equal(parseD6REvidence(opened), null);
});
