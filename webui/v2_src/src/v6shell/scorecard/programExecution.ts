import { PROGRAM_LANES, PROGRAM_PAGE_MATRIX, programOverallScore } from './programScorecard';

export type ProgramExecution = {
  readonly overallScore: number;
  readonly pageCount: number;
  readonly deliveryLane: string;
  readonly baseRelease: string;
  readonly releaseCandidate: string;
  readonly stage: string;
  readonly nextAction: string;
  readonly eta: string;
  readonly freshOos: 'NOT_RUN_NO_READ';
  readonly liveTrading: 'BLOCKED';
  readonly authority: 'REVIEWED_SNAPSHOT';
  readonly reviewedRun: string;
  readonly reviewedEvidenceManifest: string;
};

export const PROGRAM_EXECUTION: ProgramExecution = {
  overallScore: programOverallScore(PROGRAM_LANES),
  pageCount: PROGRAM_PAGE_MATRIX.length,
  deliveryLane: 'codex/D5S research → research integration → master PR → annotated D5S tag',
  baseRelease: 'fork-v1.16.0-kronos-rl-d5r-capacity-objective',
  releaseCandidate: 'fork-v1.17.0-kronos-rl-d5s-stability-earlystop',
  stage: 'D5S_STABILITY_CONFIRMED',
  nextAction: 'Preregister the fixed 100k D5S policy for D6; keep validation sealed until commit',
  eta: 'D6 prereg 1–2h / reused-validation study 1–3h',
  freshOos: 'NOT_RUN_NO_READ',
  liveTrading: 'BLOCKED',
  authority: 'REVIEWED_SNAPSHOT',
  reviewedRun: 'type2-d5s-primary-20260730-001',
  reviewedEvidenceManifest: 'c9f7f0a35c16491b02a78fe2932f9b006891d62e5318b731d696893e788387f9',
};
