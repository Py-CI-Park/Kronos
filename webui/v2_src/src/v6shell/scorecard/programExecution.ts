import { V6_PAGES } from '../registry';
import { PROGRAM_LANES, programOverallScore } from './programScorecard';

export type ProgramExecution = {
  readonly overallScore: number;
  readonly implementationScore: number;
  readonly economicModelScore: number;
  readonly liveReadinessScore: number;
  readonly pageCount: number;
  readonly deliveryLane: string;
  readonly developmentVersion: 'v1.28.0-dev';
  readonly releaseCandidate: string;
  readonly versionPolicy: 'FREEZE_DEV_VERSION_UNTIL_RELEASE_GATE';
  readonly branchRetentionPolicy: 'KEEP_MERGED_BRANCHES';
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
  implementationScore: 94,
  economicModelScore: 20,
  liveReadinessScore: 0,
  pageCount: V6_PAGES.length,
  deliveryLane: 'codex/v1.28.0-dev-<task> → develop/v1.28.0-dev (MERGED 보존) → future RC → master',
  developmentVersion: 'v1.28.0-dev',
  releaseCandidate: 'NOT_CREATED',
  versionPolicy: 'FREEZE_DEV_VERSION_UNTIL_RELEASE_GATE',
  branchRetentionPolicy: 'KEEP_MERGED_BRANCHES',
  stage: 'AUDITED_LOCAL_ANCHOR_NO_GO_EXTERNAL_AUTHORITY',
  nextAction: 'KRX Open API 인증·활용 승인과 OpenDART 키를 준비해 날짜별 PIT·가격·기업행사 원본을 수집한다',
  eta: '외부 키·승인 대기 / 확보 후 G2 1~2일 / G3 재실행 2~4시간',
  freshOos: 'NOT_RUN_NO_READ',
  liveTrading: 'BLOCKED',
  authority: 'REVIEWED_SNAPSHOT',
  reviewedRun: 'DAILY_CLOSE_OFFLINE_RL_G2_PIT_AUTHORITY_AUDIT_V1',
  reviewedEvidenceManifest: 'LOCAL_AUTHORITY_20_CODES_19_STABLE_1_EXCLUDED_EXTERNAL_BLOCKED',
};
