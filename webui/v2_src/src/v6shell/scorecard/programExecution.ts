import { REVIEWED_D5R_SNAPSHOT } from '../discovery/reviewedD5RSnapshot';
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
  deliveryLane: 'codex/D5R research → research integration → master PR → annotated D5R tag',
  baseRelease: 'fork-v1.15.0-kronos-rl-d5-full-train-cost',
  releaseCandidate: 'fork-v1.16.0-kronos-rl-d5r-capacity-objective',
  stage: 'D5R_CAPACITY_NOT_CONFIRMED',
  nextAction: 'Preregister D5S early-stop / regret objective; keep D6 validation sealed',
  eta: 'D5S prereg 2–4h / train-only stability study 6–12h',
  freshOos: 'NOT_RUN_NO_READ',
  liveTrading: 'BLOCKED',
  authority: 'REVIEWED_SNAPSHOT',
  reviewedRun: REVIEWED_D5R_SNAPSHOT.runName,
  reviewedEvidenceManifest: REVIEWED_D5R_SNAPSHOT.evidenceManifest ?? '',
};
