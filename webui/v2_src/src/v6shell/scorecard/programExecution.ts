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
    "codex/rl-etf-q0-q2-foundation-v1 → codex/rl-etf-stateful-mdp-v1 → integration PR → annotated ETF foundation tag",
  baseRelease: "fork-v1.20.0-kronos-rl-d6r2-mdp-falsification",
  releaseCandidate: "etf-stateful-q0-q2-foundation-v1",
  stage: "ETF_Q0_Q2_BLOCKED_Q1_Q2A",
  nextAction: "Acquire point-in-time ETF identity, available_at, and total-return custody before Q3",
  eta: "Q1 data 1~2d / Q2-A rerun 1~2d / Q3 remains locked",
  freshOos: "NOT_RUN_NO_READ",
  liveTrading: "BLOCKED",
  authority: "REVIEWED_SNAPSHOT",
  reviewedRun: "etf-stateful-q0-q2-canary-20260801",
  reviewedEvidenceManifest:
    "5547b7379ccd9b82e1fb55fa56bcaebc77a8b51f4fb7f7a20a8921fb796e669c",
};
