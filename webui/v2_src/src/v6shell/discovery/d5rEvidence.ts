import type { JsonObject, JsonValue } from '$lib/rlApi';
import type { DiscoveryArmEvidence } from './discoveryEvidence';

function isObjectValue(value: JsonValue | undefined): value is JsonObject {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function objectValue(value: JsonValue | undefined): JsonObject | null {
  return isObjectValue(value) ? value : null;
}

function strictNumber(value: JsonValue | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function d5rArm(row: JsonObject): DiscoveryArmEvidence | null {
  const fit = objectValue(row.fit_23bp);
  const nativeCost = objectValue(row.native_23bp);
  const nativeZero = objectValue(row.native_0bp);
  const reward = typeof row.reward_arm === 'string' ? row.reward_arm : '';
  const seed = strictNumber(row.seed);
  const steps = strictNumber(row.total_steps);
  const nativeAccuracy = strictNumber(nativeCost?.accuracy);
  const fitReward = strictNumber(fit?.reward_ratio);
  const nativeReward = strictNumber(nativeCost?.reward_ratio);
  const zeroReward = strictNumber(nativeZero?.reward_ratio);
  const dominant = strictNumber(fit?.dominant_action_rate);
  const invalid = strictNumber(fit?.invalid_action_count);
  if (!fit || !nativeCost || !nativeZero || !['NATIVE', 'SHUFFLED'].includes(reward)
    || seed === null || !Number.isInteger(seed) || seed < 0 || seed > 2
    || steps === null || ![400_000, 800_000].includes(steps)
    || nativeAccuracy === null || fitReward === null || nativeReward === null
    || zeroReward === null || dominant === null || invalid !== 0) return null;
  return {
    id: `D5R-C_DQN_DISCRETE/${reward}/${steps}`,
    model: `C_DQN_DISCRETE__${reward}/seed-${seed}/steps-${steps}`,
    seed,
    trainingTimesteps: steps,
    oracleRewardRatio: nativeReward,
    exactBasketAccuracy: nativeAccuracy,
    dominantActionRate: dominant,
    invalidActionCount: invalid,
    blockCount: 0,
    noFillCount: 0,
    shuffledReward: reward === 'SHUFFLED',
    episodeCount: 573,
    fitRewardRatio: fitReward,
    diagnosticCostRewardRatio: zeroReward,
  };
}
