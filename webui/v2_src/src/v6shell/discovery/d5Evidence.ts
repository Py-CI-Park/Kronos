import type { JsonObject, JsonValue } from '$lib/rlApi';
import type { DiscoveryArmEvidence } from './discoveryEvidence';

function isObjectValue(value: JsonValue | undefined): value is JsonObject {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function objectValue(value: JsonValue | undefined): JsonObject | null {
  return isObjectValue(value) ? value : null;
}

function textValue(value: JsonValue | undefined): string {
  return typeof value === 'string' ? value : '';
}

function strictNumber(value: JsonValue | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function d5Arm(row: JsonObject): DiscoveryArmEvidence | null {
  const fit = objectValue(row.fit_23bp);
  const nativeCost = objectValue(row.native_23bp);
  const nativeZero = objectValue(row.native_0bp);
  const algorithm = textValue(row.algorithm_arm);
  const reward = textValue(row.reward_arm);
  const seed = strictNumber(row.seed);
  const timesteps = strictNumber(row.rl_timesteps);
  const trainingCost = strictNumber(row.training_round_trip_cost_bp);
  const fitAccuracy = strictNumber(fit?.accuracy);
  const fitReward = strictNumber(fit?.reward_ratio);
  const nativeReward = strictNumber(nativeCost?.reward_ratio);
  const zeroCostReward = strictNumber(nativeZero?.reward_ratio);
  const dominant = strictNumber(fit?.dominant_action_rate);
  const invalid = strictNumber(fit?.invalid_action_count);
  if (!fit || !nativeCost || !nativeZero || algorithm !== 'C_DQN_DISCRETE'
    || !['NATIVE', 'SHUFFLED'].includes(reward) || seed === null || !Number.isInteger(seed)
    || seed < 0 || seed > 4 || timesteps !== 200000 || trainingCost !== 23
    || fitAccuracy === null || fitReward === null || nativeReward === null
    || zeroCostReward === null || dominant === null || invalid === null) return null;
  return {
    id: `D5-${algorithm}/${reward}`,
    model: `${algorithm}__${reward}/seed-${seed}`,
    seed,
    trainingTimesteps: timesteps,
    oracleRewardRatio: nativeReward,
    exactBasketAccuracy: fitAccuracy,
    dominantActionRate: dominant,
    invalidActionCount: invalid,
    blockCount: 0,
    noFillCount: 0,
    shuffledReward: reward === 'SHUFFLED',
    episodeCount: 573,
    fitRewardRatio: fitReward,
    diagnosticCostRewardRatio: zeroCostReward,
  };
}
