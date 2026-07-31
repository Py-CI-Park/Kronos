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
    "codex/rl-d6r research → research integration → master PR → annotated D6R tag",
  baseRelease: "fork-v1.18.0-kronos-rl-d6-reused-validation",
  releaseCandidate: "fork-v1.19.0-kronos-rl-d6r-train-falsification",
  stage: "D6R_TRAIN_FALSIFICATION_NOT_CONFIRMED",
  nextAction: "Preregister D6R2 MDP-specification falsification; D7 remains locked",
  eta: "D6R2 design/prereg 2~4h / train-only execution 1~3h",
  freshOos: "NOT_RUN_NO_READ",
  liveTrading: "BLOCKED",
  authority: "REVIEWED_SNAPSHOT",
  reviewedRun: "type2-d6r-primary-20260731-001",
  reviewedEvidenceManifest:
    "83e71bc3bf9d5bfae66c7af3ac76521e1e1a6f700ec81fb6eb90d0ffe53aeee4",
};
