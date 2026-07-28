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
  deliveryLane: 'codex/* → research/* → annotated release tag',
  baseRelease: 'fork-v1.9.0-kronos-rl-model-lifecycle',
  releaseCandidate: 'fork-v1.10.0-kronos-rl-d1-action-reward',
  stage: 'D1_TRAIN_ONLY_PRIMARY_CONFIRMED',
  nextAction: 'D2 episode scale(1/8/32/128) 별도 사전등록',
  eta: '설계 2~4시간 / Smoke·Primary 1~3시간',
  freshOos: 'NOT_RUN_NO_READ',
  liveTrading: 'BLOCKED',
  authority: 'REVIEWED_SNAPSHOT',
  reviewedRun: REVIEWED_DISCOVERY_SNAPSHOT.runName,
  reviewedEvidenceManifest: REVIEWED_DISCOVERY_SNAPSHOT.evidenceManifest ?? '',
};
