import { PROGRAM_LANES, PROGRAM_PAGE_MATRIX, programOverallScore } from './programScorecard';

export type ProgramExecution = {
  readonly overallScore: number;
  readonly implementationScore: number;
  readonly economicModelScore: number;
  readonly pageCount: number;
  readonly deliveryLane: string;
  readonly developmentVersion: 'v1.28.0-dev';
  readonly releaseCandidate: string;
  readonly versionPolicy: 'FREEZE_DEV_VERSION_UNTIL_RELEASE_GATE';
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
  implementationScore: 78,
  economicModelScore: 20,
  pageCount: PROGRAM_PAGE_MATRIX.length,
  deliveryLane: 'codex/v1.28.0-dev-g2-custody → develop/v1.28.0-dev → future RC → master',
  developmentVersion: 'v1.28.0-dev',
  releaseCandidate: 'NOT_CREATED',
  versionPolicy: 'FREEZE_DEV_VERSION_UNTIL_RELEASE_GATE',
  stage: 'IMPLEMENTED_CALIBRATED_NO_GO_DATA_CUSTODY',
  nextAction: 'PIT universe·available_at·공식 가격·기업행사 권위 증거 4개를 확보한다',
  eta: 'G2 1~2일 / G3 재실행 2~4시간 / G7 별도 승인',
  freshOos: 'NOT_RUN_NO_READ',
  liveTrading: 'BLOCKED',
  authority: 'REVIEWED_SNAPSHOT',
  reviewedRun: 'DAILY_CLOSE_OFFLINE_RL_G2_SOURCE_SNAPSHOT_V1',
  reviewedEvidenceManifest: 'FULL_SQLITE_SHA256_BOUND_EXTERNAL_CUSTODY_BLOCKED',
};
