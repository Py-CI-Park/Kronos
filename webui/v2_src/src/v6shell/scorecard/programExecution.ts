import {
  PROGRAM_LANES,
  PROGRAM_PAGE_MATRIX,
  programOverallScore,
} from "./programScorecard";

export type ProgramExecution = {
  readonly overallScore: number;
  readonly pageCount: number;
  readonly deliveryLane: string;
  readonly baseRelease: string;
  readonly releaseCandidate: string;
  readonly stage: string;
  readonly nextAction: string;
  readonly eta: string;
  readonly freshOos: "NOT_RUN_NO_READ";
  readonly liveTrading: "BLOCKED";
  readonly authority: "REVIEWED_SNAPSHOT";
  readonly reviewedRun: string;
  readonly reviewedEvidenceManifest: string;
};

export const PROGRAM_EXECUTION: ProgramExecution = {
  overallScore: programOverallScore(PROGRAM_LANES),
  pageCount: PROGRAM_PAGE_MATRIX.length,
  deliveryLane:
    "codex/rl-d6 research → research integration → master PR → annotated D6 tag",
  baseRelease: "fork-v1.17.0-kronos-rl-d5s-stability-earlystop",
  releaseCandidate: "fork-v1.18.0-kronos-rl-d6-reused-validation",
  stage: "D6_REUSED_VALIDATION_NOT_CONFIRMED",
  nextAction: "Preregister D6R train-only falsification; D7 remains locked",
  eta: "D6R prereg 1~2h / train-only diagnostics 2~4h",
  freshOos: "NOT_RUN_NO_READ",
  liveTrading: "BLOCKED",
  authority: "REVIEWED_SNAPSHOT",
  reviewedRun: "type2-d6-primary-20260731-002",
  reviewedEvidenceManifest:
    "4e72f8bf7ef0e52fbe7e7e093a9991980c1aa2806e0d993adb869bc97b676a63",
};
