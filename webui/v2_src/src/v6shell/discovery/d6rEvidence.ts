import type { JsonObject, JsonValue, RlRunDetail } from '$lib/rlApi';

export type D6REvaluationEvidence = {
  readonly profile: 'COST_ONLY' | 'TURNOVER_10BP';
  readonly rewardArm: 'NATIVE' | 'SHUFFLED';
  readonly seed: number;
  readonly foldId: number;
  readonly accuracy: number;
  readonly rewardRatio: number;
  readonly totalReward: number;
  readonly zeroCostRewardRatio: number;
  readonly tradeRate: number;
  readonly maximumDrawdown: number;
};

export type D6REvidence = {
  readonly runName: string;
  readonly verdict: string;
  readonly freshOos: string;
  readonly d7: 'LOCKED';
  readonly trainingPartition: 'TRAIN_ONLY';
  readonly normalizer: string;
  readonly reusedValidation: string;
  readonly preregSha: string;
  readonly manifestSha: string;
  readonly primaryCostBp: number;
  readonly diagnosticCostBp: number;
  readonly nativeMedianAccuracy: number;
  readonly nativeMedianRewardRatio: number;
  readonly nativeMedianTotalReward: number;
  readonly nativeRewardDeltaVsShuffled: number;
  readonly positiveFoldFraction: number;
  readonly positiveSeedFraction: number;
  readonly nativeMedianTradeRate: number;
  readonly tradeRateReductionVsCostOnly: number;
  readonly nativeMedianDrawdown: number;
  readonly invalidActionCount: number;
  readonly passedGateCount: number;
  readonly totalGateCount: number;
  readonly foldCount: number;
  readonly evaluations: readonly D6REvaluationEvidence[];
};

function isObject(value: JsonValue | undefined): value is JsonObject {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function textValue(value: JsonValue | undefined): string | null {
  return typeof value === 'string' && value.length > 0 ? value : null;
}

function numberValue(value: JsonValue | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function parseEvaluation(value: JsonValue): D6REvaluationEvidence | null {
  if (!isObject(value)) return null;
  const profile = textValue(value.profile);
  const rewardArm = textValue(value.reward_arm);
  const seed = numberValue(value.seed);
  const foldId = numberValue(value.fold_id);
  const primary = isObject(value.evaluation_23bp) ? value.evaluation_23bp : null;
  const diagnostic = isObject(value.evaluation_0bp) ? value.evaluation_0bp : null;
  const accuracy = primary ? numberValue(primary.accuracy) : null;
  const rewardRatio = primary ? numberValue(primary.reward_ratio) : null;
  const totalReward = primary ? numberValue(primary.total_reward) : null;
  const tradeRate = primary ? numberValue(primary.trade_rate) : null;
  const invalidActions = primary ? numberValue(primary.invalid_action_count) : null;
  const zeroCostRewardRatio = diagnostic ? numberValue(diagnostic.reward_ratio) : null;
  const maximumDrawdown = numberValue(value.maximum_drawdown_23bp);
  if (
    (profile !== 'COST_ONLY' && profile !== 'TURNOVER_10BP')
    || (rewardArm !== 'NATIVE' && rewardArm !== 'SHUFFLED')
    || seed === null || !Number.isInteger(seed) || seed < 0 || seed > 2
    || foldId === null || !Number.isInteger(foldId) || foldId < 0 || foldId > 4
    || numberValue(value.training_steps) !== 50_000
    || numberValue(value.evaluation_episode_count) !== 50
    || accuracy === null || rewardRatio === null || totalReward === null
    || tradeRate === null || zeroCostRewardRatio === null || maximumDrawdown === null
    || invalidActions !== 0
  ) return null;
  return {
    profile,
    rewardArm,
    seed,
    foldId,
    accuracy,
    rewardRatio,
    totalReward,
    zeroCostRewardRatio,
    tradeRate,
    maximumDrawdown,
  };
}

function parseMatrix(value: JsonValue | undefined): readonly D6REvaluationEvidence[] | null {
  if (!Array.isArray(value) || value.length !== 60) return null;
  const rows: D6REvaluationEvidence[] = [];
  const identities = new Set<string>();
  for (const candidate of value) {
    const row = parseEvaluation(candidate);
    if (row === null) return null;
    identities.add(`${row.profile}:${row.rewardArm}:${row.seed}:${row.foldId}`);
    rows.push(row);
  }
  if (identities.size !== 60) return null;
  return rows;
}

function closedClaims(detail: JsonObject, summary: JsonObject): boolean {
  return summary.promotion_allowed === false
    && summary.profitability_claim_allowed === false
    && summary.live_broker_order_allowed === false
    && detail.promotion_allowed === false
    && detail.profitability_claim_allowed === false
    && detail.paper_forward_allowed === false
    && detail.live_broker_order_allowed === false;
}

export function parseD6REvidence(
  run: Pick<RlRunDetail, 'name' | 'summary' | 'detail'>,
): D6REvidence | null {
  const summary = run.summary;
  const detail = run.detail;
  if (!summary || !detail || !isObject(detail.gate)) return null;
  const gate = detail.gate;
  const evaluations = parseMatrix(detail.evaluations);
  const verdict = textValue(summary.verdict);
  const values = {
    nativeMedianAccuracy: numberValue(gate.native_median_accuracy),
    nativeMedianRewardRatio: numberValue(gate.native_median_reward_ratio),
    nativeMedianTotalReward: numberValue(gate.native_median_total_reward),
    nativeRewardDeltaVsShuffled: numberValue(gate.native_reward_delta_vs_shuffled),
    positiveFoldFraction: numberValue(gate.positive_fold_fraction),
    positiveSeedFraction: numberValue(gate.positive_seed_fraction),
    nativeMedianTradeRate: numberValue(gate.native_median_trade_rate),
    tradeRateReductionVsCostOnly: numberValue(gate.trade_rate_reduction_vs_cost_only),
    nativeMedianDrawdown: numberValue(gate.native_median_reward_drawdown),
    invalidActionCount: numberValue(gate.invalid_action_count),
    passedGateCount: numberValue(gate.passed_gate_count),
    totalGateCount: numberValue(gate.total_gate_count),
  } as const;
  if (
    evaluations === null
    || summary.status !== 'COMPLETE' || summary.profile !== 'PRIMARY'
    || verdict === null || !verdict.startsWith('D6R_TRAIN_FALSIFICATION_')
    || gate.verdict !== verdict
    || summary.fresh_oos !== 'NOT_RUN_NO_READ' || detail.fresh_oos !== 'NOT_RUN_NO_READ'
    || detail.d7 !== 'LOCKED' || detail.training_partition !== 'TRAIN_ONLY'
    || detail.reused_validation !== 'NO_READ_ALREADY_CONSUMED_DIAGNOSTIC_ONLY'
    || detail.candidate_is_not_confirmation !== true
    || numberValue(summary.primary_round_trip_cost_bp) !== 23
    || numberValue(summary.diagnostic_round_trip_cost_bp) !== 0
    || textValue(summary.prereg_sha256) === null
    || textValue(summary.artifact_manifest_sha256) === null
    || textValue(detail.normalizer) === null
    || Object.values(values).some((value) => value === null)
    || values.invalidActionCount !== 0 || values.totalGateCount !== 10
    || !closedClaims(detail, summary)
  ) return null;
  return {
    runName: run.name,
    verdict,
    freshOos: 'NOT_RUN_NO_READ',
    d7: 'LOCKED',
    trainingPartition: 'TRAIN_ONLY',
    normalizer: textValue(detail.normalizer) ?? '',
    reusedValidation: 'NO_READ_ALREADY_CONSUMED_DIAGNOSTIC_ONLY',
    preregSha: textValue(summary.prereg_sha256) ?? '',
    manifestSha: textValue(summary.artifact_manifest_sha256) ?? '',
    primaryCostBp: 23,
    diagnosticCostBp: 0,
    nativeMedianAccuracy: values.nativeMedianAccuracy ?? 0,
    nativeMedianRewardRatio: values.nativeMedianRewardRatio ?? 0,
    nativeMedianTotalReward: values.nativeMedianTotalReward ?? 0,
    nativeRewardDeltaVsShuffled: values.nativeRewardDeltaVsShuffled ?? 0,
    positiveFoldFraction: values.positiveFoldFraction ?? 0,
    positiveSeedFraction: values.positiveSeedFraction ?? 0,
    nativeMedianTradeRate: values.nativeMedianTradeRate ?? 0,
    tradeRateReductionVsCostOnly: values.tradeRateReductionVsCostOnly ?? 0,
    nativeMedianDrawdown: values.nativeMedianDrawdown ?? 0,
    invalidActionCount: values.invalidActionCount ?? 0,
    passedGateCount: values.passedGateCount ?? 0,
    totalGateCount: values.totalGateCount ?? 10,
    foldCount: 5,
    evaluations,
  };
}
