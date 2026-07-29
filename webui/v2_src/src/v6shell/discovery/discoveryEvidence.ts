import type { JsonObject, JsonValue, RlRunDetail } from '$lib/rlApi';

export interface DiscoveryArmEvidence {
  readonly id: string;
  readonly model: string;
  readonly seed: number;
  readonly trainingTimesteps: number;
  readonly oracleRewardRatio: number;
  readonly exactBasketAccuracy: number;
  readonly dominantActionRate: number;
  readonly invalidActionCount: number;
  readonly blockCount: number;
  readonly noFillCount: number;
  readonly shuffledReward: boolean;
  readonly episodeCount?: number;
  readonly fitRewardRatio?: number;
  readonly diagnosticCostRewardRatio?: number;
}

export type DiscoveryArmAggregate = {
  readonly id: string;
  readonly seedCount: number;
  readonly meanOracleRewardRatio: number;
  readonly meanExactBasketAccuracy: number;
  readonly meanDominantActionRate: number;
};

export interface DiscoveryEvidence {
  readonly authority: 'LIVE_ARTIFACT' | 'REVIEWED_SNAPSHOT';
  readonly evidenceManifest: string | null;
  readonly runName: string;
  readonly status: string;
  readonly verdict: string;
  readonly profile: string;
  readonly freshOos: string;
  readonly type1Outcome: string;
  readonly primaryRoundTripCostBp: number;
  readonly preregSha256: string;
  readonly promotionAllowed: boolean;
  readonly profitabilityClaimAllowed: boolean;
  readonly diagnosticRoundTripCostBp?: number;
  readonly maximumConfirmedEpisodeCount?: number;
  readonly nativeDeltaVsShuffled?: number;
  readonly bestPolicyArm?: string;
  readonly budget4xNativeLift?: number;
  readonly confirmedPolicyArmCount?: number;
  readonly bestRlArm?: string;
  readonly bestRlGapToSupervisedCeiling?: number;
  readonly supervisedCeilingConfirmed?: boolean;
  readonly confirmedRlArmCount?: number;
  readonly arms: readonly DiscoveryArmEvidence[];
}

function d4Arm(row: JsonObject): DiscoveryArmEvidence | null {
  const fit = objectValue(row.fit);
  const native = objectValue(row.native);
  const cost = objectValue(row.cost_23bp);
  const algorithm = textValue(row.algorithm_arm, '');
  const reward = textValue(row.reward_arm, '');
  const seed = strictNumber(row.seed);
  const fitAccuracy = strictNumber(fit?.accuracy);
  const fitReward = strictNumber(fit?.reward_ratio);
  const nativeReward = strictNumber(native?.reward_ratio);
  const costReward = strictNumber(cost?.reward_ratio);
  const dominant = strictNumber(fit?.dominant_action_rate);
  const invalid = strictNumber(fit?.invalid_action_count);
  if (!fit || !native || !cost || !algorithm || !reward || seed === null || fitAccuracy === null
    || fitReward === null || nativeReward === null || costReward === null || dominant === null || invalid === null) return null;
  return {
    id: `D4-${algorithm}/${reward}`,
    model: `${algorithm}__${reward}/seed-${numberValue(row.seed)}`,
    seed,
    trainingTimesteps: numberValue(row.rl_timesteps) || numberValue(row.pretraining_epochs),
    oracleRewardRatio: nativeReward,
    exactBasketAccuracy: fitAccuracy,
    dominantActionRate: dominant,
    invalidActionCount: invalid,
    blockCount: 0,
    noFillCount: 0,
    shuffledReward: reward === 'SHUFFLED',
    episodeCount: 128,
    fitRewardRatio: fitReward,
    diagnosticCostRewardRatio: costReward,
  };
}

function isObjectValue(value: JsonValue | undefined): value is JsonObject {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function objectValue(value: JsonValue | undefined): JsonObject | null {
  return isObjectValue(value) ? value : null;
}
function textValue(value: JsonValue | undefined, fallback = 'MISSING'): string {
  return typeof value === 'string' && value.length ? value : fallback;
}
function numberValue(value: JsonValue | undefined): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}
function strictNumber(value: JsonValue | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}
function booleanValue(value: JsonValue | undefined): boolean {
  return value === true;
}
function modelRows(detail: JsonObject | undefined): readonly JsonObject[] {
  const value = detail?.models;
  if (!Array.isArray(value)) return [];
  return value.map(objectValue).filter((row): row is JsonObject => row !== null);
}

function d2Arm(row: JsonObject): DiscoveryArmEvidence | null {
  const fit = objectValue(row.fit);
  const native = objectValue(row.native);
  const cost = objectValue(row.cost_23bp);
  const arm = textValue(row.arm, '');
  const count = numberValue(row.episode_count);
  if (!fit || !native || !cost || !arm || count <= 0) return null;
  return {
    id: `D2-${count}/${arm}`,
    model: `count-${count}__${arm}/seed-${numberValue(row.seed)}`,
    seed: numberValue(row.seed),
    trainingTimesteps: numberValue(row.training_timesteps),
    oracleRewardRatio: numberValue(native.reward_ratio),
    exactBasketAccuracy: numberValue(fit.accuracy),
    dominantActionRate: numberValue(fit.dominant_action_rate),
    invalidActionCount: numberValue(fit.invalid_action_count),
    blockCount: 0,
    noFillCount: 0,
    shuffledReward: arm === 'B_SHUFFLED',
    episodeCount: count,
    fitRewardRatio: numberValue(fit.reward_ratio),
    diagnosticCostRewardRatio: numberValue(cost.reward_ratio),
  };
}

function d3Arm(row: JsonObject): DiscoveryArmEvidence | null {
  const fit = objectValue(row.fit);
  const native = objectValue(row.native);
  const cost = objectValue(row.cost_23bp);
  const policy = textValue(row.policy_arm, '');
  const reward = textValue(row.reward_arm, '');
  if (!fit || !native || !cost || !policy || !reward) return null;
  return {
    id: `D3-${policy}/${reward}`,
    model: `${policy}__${reward}/seed-${numberValue(row.seed)}`,
    seed: numberValue(row.seed),
    trainingTimesteps: numberValue(row.training_timesteps),
    oracleRewardRatio: numberValue(native.reward_ratio),
    exactBasketAccuracy: numberValue(fit.accuracy),
    dominantActionRate: numberValue(fit.dominant_action_rate),
    invalidActionCount: numberValue(fit.invalid_action_count),
    blockCount: 0,
    noFillCount: 0,
    shuffledReward: reward === 'SHUFFLED',
    episodeCount: 128,
    fitRewardRatio: numberValue(fit.reward_ratio),
    diagnosticCostRewardRatio: numberValue(cost.reward_ratio),
  };
}

function d3BestDelta(gate: JsonObject | null): number {
  const best = textValue(gate?.best_policy_arm, '');
  const rows = gate?.native_delta_vs_shuffled;
  if (!best || !Array.isArray(rows)) return 0;
  const match = rows.find((row) => Array.isArray(row) && row[0] === best);
  return Array.isArray(match) ? numberValue(match[1]) : 0;
}

export function parseDiscoveryEvidence(run: Pick<RlRunDetail, 'name' | 'summary' | 'detail'>): DiscoveryEvidence | null {
  const summary = run.summary;
  if (!summary || summary.research_lane !== 'rl_discovery') return null;
  const rows = modelRows(run.detail);
  const d4Rows = rows.map(d4Arm).filter((row): row is DiscoveryArmEvidence => row !== null);
  const d3Rows = rows.map(d3Arm).filter((row): row is DiscoveryArmEvidence => row !== null);
  const d2Rows = rows.map(d2Arm).filter((row): row is DiscoveryArmEvidence => row !== null);
  const gate = objectValue(run.detail?.gate);
  if (summary.verdict === 'D4_ALGORITHM_OBJECTIVE_CONFIRMED' && (d4Rows.length !== 24 || d4Rows.length !== rows.length)) return null;
  const arms = d4Rows.length ? d4Rows : d3Rows.length ? d3Rows : d2Rows.length ? d2Rows : rows.map((row) => ({
    id: textValue(row.algorithm),
    model: textValue(row.model),
    seed: numberValue(row.seed),
    trainingTimesteps: numberValue(row.training_timesteps),
    oracleRewardRatio: numberValue(row.oracle_reward_ratio),
    exactBasketAccuracy: numberValue(row.exact_basket_accuracy),
    dominantActionRate: numberValue(row.dominant_action_rate),
    invalidActionCount: numberValue(row.invalid_action_count),
    blockCount: numberValue(row.block_count),
    noFillCount: numberValue(row.no_fill_count),
    shuffledReward: booleanValue(row.shuffled_reward),
  }));
  return {
    authority: 'LIVE_ARTIFACT',
    evidenceManifest: textValue(summary.artifact_manifest_sha256, '') || null,
    runName: run.name,
    status: textValue(summary.status),
    verdict: textValue(summary.verdict),
    profile: textValue(summary.profile),
    freshOos: textValue(summary.fresh_oos),
    type1Outcome: textValue(summary.type1_outcome),
    primaryRoundTripCostBp: numberValue(summary.primary_round_trip_cost_bp),
    preregSha256: textValue(summary.prereg_sha256),
    promotionAllowed: booleanValue(summary.promotion_allowed),
    profitabilityClaimAllowed: booleanValue(summary.profitability_claim_allowed),
    diagnosticRoundTripCostBp: numberValue(summary.diagnostic_round_trip_cost_bp),
    maximumConfirmedEpisodeCount: numberValue(gate?.maximum_confirmed_episode_count),
    nativeDeltaVsShuffled: d3Rows.length ? d3BestDelta(gate) : numberValue(gate?.native_delta_vs_shuffled_at_128),
    bestPolicyArm: textValue(gate?.best_policy_arm, ''),
    budget4xNativeLift: numberValue(gate?.budget_4x_native_lift),
    confirmedPolicyArmCount: Array.isArray(gate?.confirmed_policy_arms) ? gate.confirmed_policy_arms.length : undefined,
    bestRlArm: textValue(gate?.best_rl_arm, ''),
    bestRlGapToSupervisedCeiling: numberValue(gate?.best_rl_gap_to_supervised_ceiling),
    supervisedCeilingConfirmed: booleanValue(gate?.supervised_ceiling_confirmed),
    confirmedRlArmCount: Array.isArray(gate?.confirmed_rl_arms) ? gate.confirmed_rl_arms.length : undefined,
    arms,
  };
}

export function summarizeDiscoveryArms(
  arms: readonly DiscoveryArmEvidence[],
): readonly DiscoveryArmAggregate[] {
  const armIds = [...new Set(arms.map((arm) => arm.id))];
  return armIds.map((id) => {
    const rows = arms.filter((arm) => arm.id === id);
    const divisor = rows.length || 1;
    return {
      id,
      seedCount: rows.length,
      meanOracleRewardRatio: rows.reduce((sum, row) => sum + row.oracleRewardRatio, 0) / divisor,
      meanExactBasketAccuracy: rows.reduce((sum, row) => sum + row.exactBasketAccuracy, 0) / divisor,
      meanDominantActionRate: rows.reduce((sum, row) => sum + row.dominantActionRate, 0) / divisor,
    };
  });
}
