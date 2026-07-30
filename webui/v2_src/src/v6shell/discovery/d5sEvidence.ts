import type { JsonObject, JsonValue, RlRunDetail } from '$lib/rlApi';
import type { DiscoveryArmEvidence } from './discoveryEvidence';

const CHECKPOINTS = [50_000, 100_000, 150_000, 200_000, 300_000, 400_000] as const;

export const D5S_PRESENTATION = Object.freeze({
  d6Seal: 'D6 remains sealed',
  d7Seal: 'D7 remains sealed',
  claimBoundary: 'RESEARCH ONLY',
});

export function formatD5SCheckpointSteps(steps: number): string {
  return Number.isInteger(steps) && CHECKPOINTS.includes(steps as (typeof CHECKPOINTS)[number])
    ? `${steps / 1000}K`
    : 'MISSING';
}

export interface D5SEvidence {
  readonly runName: string;
  readonly status: string;
  readonly verdict: string;
  readonly profile: string;
  readonly freshOos: string;
  readonly reusedValidation: string;
  readonly primaryRoundTripCostBp: number;
  readonly diagnosticRoundTripCostBp: number;
  readonly preregSha256: string;
  readonly evidenceManifest: string;
  readonly promotionAllowed: false;
  readonly profitabilityClaimAllowed: false;
  readonly selectedSteps: number;
  readonly selectedNativeMedianAccuracy: number;
  readonly selectedNativeMedianRewardRatio: number;
  readonly nativeDeltaVsShuffled: number;
  readonly accuracyDegradationAt400k: number;
  readonly rewardRatioDegradationAt400k: number;
  readonly preservedNativeSeedFraction: number;
  readonly invalidActionCount: 0;
  readonly arms: readonly DiscoveryArmEvidence[];
}

function isObjectValue(value: JsonValue | undefined): value is JsonObject {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function objectValue(value: JsonValue | undefined): JsonObject | null {
  return isObjectValue(value) ? value : null;
}

function numberValue(value: JsonValue | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function textValue(value: JsonValue | undefined): string | null {
  return typeof value === 'string' && value.length > 0 ? value : null;
}

function checkpointArm(row: JsonObject): DiscoveryArmEvidence | null {
  const fit = objectValue(row.fit_23bp);
  const native = objectValue(row.native_23bp);
  const zero = objectValue(row.native_0bp);
  const rewardArm = textValue(row.reward_arm);
  const seed = numberValue(row.seed);
  const steps = numberValue(row.total_steps);
  const fitReward = numberValue(fit?.reward_ratio);
  const nativeReward = numberValue(native?.reward_ratio);
  const zeroReward = numberValue(zero?.reward_ratio);
  const accuracy = numberValue(native?.accuracy);
  const dominant = numberValue(native?.dominant_action_rate);
  const invalid = numberValue(native?.invalid_action_count);
  if (!fit || !native || !zero || !rewardArm || !['NATIVE', 'SHUFFLED'].includes(rewardArm)
    || seed === null || !Number.isInteger(seed) || seed < 0 || seed > 2
    || steps === null || !CHECKPOINTS.includes(steps as (typeof CHECKPOINTS)[number])
    || fitReward === null || nativeReward === null || zeroReward === null
    || accuracy === null || dominant === null || invalid !== 0
    || numberValue(fit.invalid_action_count) !== 0 || numberValue(zero.invalid_action_count) !== 0) return null;
  return {
    id: `D5S-D_DQN_STABLE_LR/${rewardArm}/${steps}`,
    model: `D_DQN_STABLE_LR__${rewardArm}/seed-${seed}/steps-${steps}`,
    seed,
    trainingTimesteps: steps,
    oracleRewardRatio: nativeReward,
    exactBasketAccuracy: accuracy,
    dominantActionRate: dominant,
    invalidActionCount: invalid,
    blockCount: 0,
    noFillCount: 0,
    shuffledReward: rewardArm === 'SHUFFLED',
    episodeCount: 573,
    fitRewardRatio: fitReward,
    diagnosticCostRewardRatio: zeroReward,
  };
}

export function parseD5SEvidence(
  run: Pick<RlRunDetail, 'name' | 'summary' | 'detail'>,
): D5SEvidence | null {
  const summary = run.summary;
  const detail = run.detail;
  const gate = objectValue(detail?.gate);
  const modelValues = detail?.models;
  if (!summary || summary.research_lane !== 'rl_discovery' || !gate || !Array.isArray(modelValues)) return null;
  const rows = modelValues.map(objectValue).filter((row): row is JsonObject => row !== null);
  const arms = rows.map(checkpointArm).filter((row): row is DiscoveryArmEvidence => row !== null);
  const units = new Set(arms.map((row) => `${row.shuffledReward ? 'SHUFFLED' : 'NATIVE'}/${row.seed}/${row.trainingTimesteps}`));
  const expected = new Set(
    ['NATIVE', 'SHUFFLED'].flatMap((arm) =>
      [0, 1, 2].flatMap((seed) => CHECKPOINTS.map((steps) => `${arm}/${seed}/${steps}`)),
    ),
  );
  const selectedSteps = numberValue(gate.selected_steps);
  const selectedAccuracy = numberValue(gate.selected_native_median_accuracy);
  const selectedReward = numberValue(gate.selected_native_median_reward_ratio);
  const nativeDelta = numberValue(gate.selected_native_reward_delta_vs_shuffled);
  const accuracyDegradation = numberValue(gate.accuracy_degradation_at_400k);
  const rewardDegradation = numberValue(gate.reward_ratio_degradation_at_400k);
  const preservedSeeds = numberValue(gate.preserved_native_seed_fraction);
  const invalidActions = numberValue(gate.invalid_action_count);
  const verdict = textValue(summary.verdict);
  const preregSha = textValue(summary.prereg_sha256);
  const manifest = textValue(summary.artifact_manifest_sha256);
  if (!verdict?.startsWith('D5S_STABILITY_') || summary.status !== 'COMPLETE' || summary.profile !== 'PRIMARY'
    || summary.fresh_oos !== 'NOT_RUN_NO_READ' || detail.reused_validation !== 'NOT_RUN_NO_READ'
    || summary.primary_round_trip_cost_bp !== 23 || summary.diagnostic_round_trip_cost_bp !== 0
    || summary.promotion_allowed !== false || summary.profitability_claim_allowed !== false
    || textValue(gate.verdict) !== verdict || rows.length !== 36 || arms.length !== 36
    || units.size !== expected.size || [...expected].some((unit) => !units.has(unit))
    || selectedSteps === null || !CHECKPOINTS.includes(selectedSteps as (typeof CHECKPOINTS)[number])
    || selectedAccuracy === null || selectedReward === null || nativeDelta === null
    || accuracyDegradation === null || rewardDegradation === null || preservedSeeds === null
    || invalidActions !== 0 || !preregSha || !manifest) return null;
  return {
    runName: run.name,
    status: 'COMPLETE',
    verdict,
    profile: 'PRIMARY',
    freshOos: 'NOT_RUN_NO_READ',
    reusedValidation: 'NOT_RUN_NO_READ',
    primaryRoundTripCostBp: 23,
    diagnosticRoundTripCostBp: 0,
    preregSha256: preregSha,
    evidenceManifest: manifest,
    promotionAllowed: false,
    profitabilityClaimAllowed: false,
    selectedSteps,
    selectedNativeMedianAccuracy: selectedAccuracy,
    selectedNativeMedianRewardRatio: selectedReward,
    nativeDeltaVsShuffled: nativeDelta,
    accuracyDegradationAt400k: accuracyDegradation,
    rewardRatioDegradationAt400k: rewardDegradation,
    preservedNativeSeedFraction: preservedSeeds,
    invalidActionCount: 0,
    arms,
  };
}
