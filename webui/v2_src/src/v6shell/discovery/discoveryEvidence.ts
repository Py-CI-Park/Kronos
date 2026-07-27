import type { JsonObject, JsonValue, RlRunDetail } from '$lib/rlApi';

export interface DiscoveryArmEvidence {
  readonly id: string;
  readonly model: string;
  readonly trainingTimesteps: number;
  readonly oracleRewardRatio: number;
  readonly exactBasketAccuracy: number;
  readonly dominantActionRate: number;
  readonly invalidActionCount: number;
  readonly blockCount: number;
  readonly noFillCount: number;
  readonly shuffledReward: boolean;
}

export interface DiscoveryEvidence {
  readonly runName: string;
  readonly status: string;
  readonly verdict: string;
  readonly profile: string;
  readonly freshOos: string;
  readonly type1Outcome: string;
  readonly preregSha256: string;
  readonly promotionAllowed: boolean;
  readonly profitabilityClaimAllowed: boolean;
  readonly arms: readonly DiscoveryArmEvidence[];
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
function booleanValue(value: JsonValue | undefined): boolean {
  return value === true;
}
function modelRows(detail: JsonObject | undefined): readonly JsonObject[] {
  const value = detail?.models;
  if (!Array.isArray(value)) return [];
  return value.map(objectValue).filter((row): row is JsonObject => row !== null);
}

export function parseDiscoveryEvidence(run: Pick<RlRunDetail, 'name' | 'summary' | 'detail'>): DiscoveryEvidence | null {
  const summary = run.summary;
  if (!summary || summary.research_lane !== 'rl_discovery') return null;
  const arms = modelRows(run.detail).map((row) => ({
    id: textValue(row.algorithm),
    model: textValue(row.model),
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
    runName: run.name,
    status: textValue(summary.status),
    verdict: textValue(summary.verdict),
    profile: textValue(summary.profile),
    freshOos: textValue(summary.fresh_oos),
    type1Outcome: textValue(summary.type1_outcome),
    preregSha256: textValue(summary.prereg_sha256),
    promotionAllowed: booleanValue(summary.promotion_allowed),
    profitabilityClaimAllowed: booleanValue(summary.profitability_claim_allowed),
    arms,
  };
}
