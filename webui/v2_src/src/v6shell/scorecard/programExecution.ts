import { PROGRAM_LANES, PROGRAM_PAGE_MATRIX, programOverallScore } from './programScorecard';

export type ProgramExecution = {
  readonly overallScore: number;
  readonly implementationScore: number;
  readonly economicModelScore: number;
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
  implementationScore: 75,
  economicModelScore: 20,
  pageCount: PROGRAM_PAGE_MATRIX.length,
  deliveryLane: 'codex/rl-all-pages-v1-28 → research/daily-close-offline-rl-v2 → Draft PR → master',
  baseRelease: 'v1.27.0-dev',
  releaseCandidate: 'v1.28.0-rc.1',
  stage: 'IMPLEMENTED_CALIBRATED_NO_GO_DATA_CUSTODY',
  nextAction: 'PIT universe·available_at·수정주가·source hash를 확보해 G2를 통과한다',
  eta: 'G2 1~2일 / G3 재실행 2~4시간 / G7 별도 승인',
  freshOos: 'NOT_RUN_NO_READ',
  liveTrading: 'BLOCKED',
  authority: 'REVIEWED_SNAPSHOT',
  reviewedRun: 'DAILY_CLOSE_OFFLINE_RL_G1_G6_V2',
  reviewedEvidenceManifest: 'LOCAL_RECEIPT_UNHASHED_NOT_PROMOTION_ELIGIBLE',
};
