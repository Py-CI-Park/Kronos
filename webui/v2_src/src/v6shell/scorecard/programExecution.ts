import { REVIEWED_D5_SNAPSHOT } from '../discovery/reviewedD5Snapshot';
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
  deliveryLane: 'codex/D5 research → research integration → master PR → annotated D5 tag',
  baseRelease: 'fork-v1.14.0-kronos-rl-d4-algorithm-objective',
  releaseCandidate: 'fork-v1.15.0-kronos-rl-d5-full-train-cost',
  stage: 'D5_FULL_TRAIN_COST_NOT_CONFIRMED',
  nextAction: 'D5R capacity / objective preregistration; keep D6 validation sealed',
  eta: 'D5R prereg 2–4h / train-only diagnostic 6–12h',
  freshOos: 'NOT_RUN_NO_READ',
  liveTrading: 'BLOCKED',
  authority: 'REVIEWED_SNAPSHOT',
  reviewedRun: REVIEWED_D5_SNAPSHOT.runName,
  reviewedEvidenceManifest: REVIEWED_D5_SNAPSHOT.evidenceManifest ?? '',
};
