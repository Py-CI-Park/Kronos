import { REVIEWED_DISCOVERY_SNAPSHOT } from '../discovery/reviewedDiscoverySnapshot';
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
  deliveryLane: 'codex/D4 research → research integration → master PR → annotated D4 tag',
  baseRelease: 'fork-v1.13.0-kronos-rl-d3-representation-action',
  releaseCandidate: 'fork-v1.14.0-kronos-rl-d4-algorithm-objective',
  stage: 'D4_ALGORITHM_OBJECTIVE_CONFIRMED',
  nextAction: 'D5 full-train cost/control 연구 사전등록',
  eta: 'D5 설계 2~4시간 / Smoke·Primary 4~8시간',
  freshOos: 'NOT_RUN_NO_READ',
  liveTrading: 'BLOCKED',
  authority: 'REVIEWED_SNAPSHOT',
  reviewedRun: REVIEWED_DISCOVERY_SNAPSHOT.runName,
  reviewedEvidenceManifest: REVIEWED_DISCOVERY_SNAPSHOT.evidenceManifest ?? '',
};
