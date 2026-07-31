import type { JsonObject, JsonValue, RlRunDetail } from "$lib/rlApi";

export type D6EvaluationEvidence = {
  readonly rewardArm: "NATIVE" | "SHUFFLED";
  readonly seed: number;
  readonly accuracy: number;
  readonly rewardRatio: number;
  readonly totalReward: number;
  readonly zeroCostRewardRatio: number;
  readonly tradeRate: number;
  readonly maximumDrawdown: number;
  readonly sourceModelSha: string;
};

export type D6Evidence = {
  readonly runName: string;
  readonly status: string;
  readonly verdict: string;
  readonly profile: string;
  readonly freshOos: string;
  readonly reusedValidation: string;
  readonly primaryCostBp: number;
  readonly diagnosticCostBp: number;
  readonly preregSha: string;
  readonly manifestSha: string;
  readonly validationEpisodeCount: number;
  readonly validationEpisodeSha: string;
  readonly validationOrigin: string;
  readonly validationReadCount: number;
  readonly recoveryRun: string;
  readonly nativeMedianAccuracy: number;
  readonly nativeMedianRewardRatio: number;
  readonly nativeMedianTotalReward: number;
  readonly shuffledMedianRewardRatio: number;
  readonly nativeRewardDeltaVsShuffled: number;
  readonly nativePassingSeedFraction: number;
  readonly nativeMedianDrawdown: number;
  readonly nativeMedianZeroCostRewardRatio: number;
  readonly invalidActionCount: number;
  readonly evaluations: readonly D6EvaluationEvidence[];
};

export const D6_PRESENTATION = Object.freeze({
  gateStatus: "1 / 7 GATES PASS",
  d7Seal: "D7 LOCKED",
  claimBoundary: "RESEARCH ONLY",
});

function isObject(value: JsonValue | undefined): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function textValue(value: JsonValue | undefined): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function numberValue(value: JsonValue | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function isClosedClaim(value: JsonValue | undefined): boolean {
  return value === false;
}

function parseEvaluation(value: JsonValue): D6EvaluationEvidence | null {
  if (!isObject(value)) return null;
  const rewardArm = textValue(value.reward_arm);
  const seed = numberValue(value.seed);
  const selectedSteps = numberValue(value.selected_steps);
  const sourceModelSha = textValue(value.source_model_sha256);
  const primary = isObject(value.validation_23bp)
    ? value.validation_23bp
    : null;
  const diagnostic = isObject(value.validation_0bp)
    ? value.validation_0bp
    : null;
  const accuracy = primary ? numberValue(primary.accuracy) : null;
  const rewardRatio = primary ? numberValue(primary.reward_ratio) : null;
  const totalReward = primary ? numberValue(primary.total_reward) : null;
  const tradeRate = primary ? numberValue(primary.trade_rate) : null;
  const invalidActions = primary
    ? numberValue(primary.invalid_action_count)
    : null;
  const zeroCostRewardRatio = diagnostic
    ? numberValue(diagnostic.reward_ratio)
    : null;
  const maximumDrawdown = numberValue(value.maximum_drawdown_23bp);
  if (
    (rewardArm !== "NATIVE" && rewardArm !== "SHUFFLED") ||
    seed === null ||
    !Number.isInteger(seed) ||
    seed < 0 ||
    seed > 2 ||
    selectedSteps !== 100_000 ||
    sourceModelSha === null ||
    !/^[0-9a-f]{64}$/u.test(sourceModelSha) ||
    accuracy === null ||
    rewardRatio === null ||
    totalReward === null ||
    tradeRate === null ||
    zeroCostRewardRatio === null ||
    maximumDrawdown === null ||
    invalidActions !== 0
  )
    return null;
  return {
    rewardArm,
    seed,
    accuracy,
    rewardRatio,
    totalReward,
    zeroCostRewardRatio,
    tradeRate,
    maximumDrawdown,
    sourceModelSha,
  };
}

function parseEvaluationMatrix(
  value: JsonValue | undefined,
): readonly D6EvaluationEvidence[] | null {
  if (!Array.isArray(value) || value.length !== 6) return null;
  const evaluations: D6EvaluationEvidence[] = [];
  const identities = new Set<string>();
  for (const row of value) {
    const parsed = parseEvaluation(row);
    if (parsed === null) return null;
    identities.add(`${parsed.rewardArm}:${parsed.seed}`);
    evaluations.push(parsed);
  }
  if (identities.size !== 6) return null;
  for (const arm of ["NATIVE", "SHUFFLED"]) {
    for (const seed of [0, 1, 2]) {
      if (!identities.has(`${arm}:${seed}`)) return null;
    }
  }
  return evaluations;
}

function median(values: readonly number[]): number {
  const ordered = [...values].sort((left, right) => left - right);
  return ordered[Math.floor(ordered.length / 2)] ?? Number.NaN;
}

export function parseD6Evidence(
  run: Pick<RlRunDetail, "name" | "summary" | "detail">,
): D6Evidence | null {
  const summary = run.summary;
  const detail = run.detail;
  if (!summary || !detail || !isObject(detail.gate)) return null;
  const gate = detail.gate;
  const evaluations = parseEvaluationMatrix(detail.evaluations);
  const status = textValue(summary.status);
  const verdict = textValue(summary.verdict);
  const profile = textValue(summary.profile);
  const freshOos = textValue(summary.fresh_oos);
  const reusedValidation = textValue(detail.reused_validation);
  const primaryCostBp = numberValue(summary.primary_round_trip_cost_bp);
  const diagnosticCostBp = numberValue(summary.diagnostic_round_trip_cost_bp);
  const preregSha = textValue(summary.prereg_sha256);
  const manifestSha = textValue(summary.artifact_manifest_sha256);
  const validationEpisodeCount = numberValue(detail.validation_episode_count);
  const validationEpisodeSha = textValue(detail.validation_episode_sha256);
  const validationOrigin = textValue(detail.validation_origin);
  const validationReadCount = numberValue(detail.validation_read_count);
  const recoveryRun = textValue(detail.recovery_run);
  const nativeMedianAccuracy = numberValue(gate.native_median_accuracy);
  const nativeMedianRewardRatio = numberValue(gate.native_median_reward_ratio);
  const nativeMedianTotalReward = numberValue(gate.native_median_total_reward);
  const shuffledMedianRewardRatio = numberValue(
    gate.shuffled_median_reward_ratio,
  );
  const nativeRewardDeltaVsShuffled = numberValue(
    gate.native_reward_delta_vs_shuffled,
  );
  const nativePassingSeedFraction = numberValue(
    gate.native_passing_seed_fraction,
  );
  const nativeMedianDrawdown = numberValue(gate.native_median_reward_drawdown);
  const invalidActionCount = numberValue(gate.invalid_action_count);
  if (
    evaluations === null ||
    status !== "COMPLETE" ||
    profile !== "PRIMARY" ||
    verdict === null ||
    !verdict.startsWith("D6_REUSED_VALIDATION_") ||
    textValue(gate.verdict) !== verdict ||
    freshOos !== "NOT_RUN_NO_READ" ||
    detail.fresh_oos !== freshOos ||
    gate.fresh_oos !== freshOos ||
    reusedValidation !== "COMPLETE" ||
    primaryCostBp !== 23 ||
    diagnosticCostBp !== 0 ||
    preregSha === null ||
    manifestSha === null ||
    validationEpisodeCount !== 128 ||
    validationEpisodeSha === null ||
    validationOrigin !== "FAILED_RUN_SNAPSHOT" ||
    validationReadCount !== 1 ||
    recoveryRun === null ||
    nativeMedianAccuracy === null ||
    nativeMedianRewardRatio === null ||
    nativeMedianTotalReward === null ||
    shuffledMedianRewardRatio === null ||
    nativeRewardDeltaVsShuffled === null ||
    nativePassingSeedFraction === null ||
    nativeMedianDrawdown === null ||
    invalidActionCount !== 0 ||
    !isClosedClaim(summary.promotion_allowed) ||
    !isClosedClaim(summary.profitability_claim_allowed) ||
    !isClosedClaim(gate.promotion_allowed) ||
    !isClosedClaim(gate.profitability_claim_allowed)
  )
    return null;
  const nativeZeroCostRatios = evaluations
    .filter((row) => row.rewardArm === "NATIVE")
    .map((row) => row.zeroCostRewardRatio);
  return {
    runName: run.name,
    status,
    verdict,
    profile,
    freshOos,
    reusedValidation,
    primaryCostBp,
    diagnosticCostBp,
    preregSha,
    manifestSha,
    validationEpisodeCount,
    validationEpisodeSha,
    validationOrigin,
    validationReadCount,
    recoveryRun,
    nativeMedianAccuracy,
    nativeMedianRewardRatio,
    nativeMedianTotalReward,
    shuffledMedianRewardRatio,
    nativeRewardDeltaVsShuffled,
    nativePassingSeedFraction,
    nativeMedianDrawdown,
    nativeMedianZeroCostRewardRatio: median(nativeZeroCostRatios),
    invalidActionCount,
    evaluations,
  };
}
