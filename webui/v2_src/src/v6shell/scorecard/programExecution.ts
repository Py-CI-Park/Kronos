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
  baseRelease: 'fork-v1.10.0-kronos-rl-d1-action-reward',
  releaseCandidate: 'fork-v1.11.0-kronos-rl-d2-historical-scale',
  stage: 'D2_PARTIAL_CAPACITY_CONFIRMED',
  nextAction: 'D3 representation/action ablation 사전등록',
  eta: '설계 2~4시간 / Smoke·Primary 2~4시간',
  freshOos: 'NOT_RUN_NO_READ',
  liveTrading: 'BLOCKED',
  authority: 'REVIEWED_SNAPSHOT',
  reviewedRun: REVIEWED_DISCOVERY_SNAPSHOT.runName,
  reviewedEvidenceManifest: REVIEWED_DISCOVERY_SNAPSHOT.evidenceManifest ?? '',
};
