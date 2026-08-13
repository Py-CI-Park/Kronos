import { V6_PAGES } from '../registry';
import { PROGRAM_LANES, programOverallScore } from './programScorecard';

export type ProgramExecution = {
  readonly overallScore: number;
  readonly implementationScore: number;
  readonly economicModelScore: number;
  readonly liveReadinessScore: number;
  readonly pageCount: number;
  readonly deliveryLane: string;
  readonly developmentVersion: 'v1.29.0-dev';
  readonly latestRelease: 'v1.28.0';
  readonly versionPolicy: 'ONE_DEV_LINE_TASK_BRANCH_NO_FF_PRESERVE';
  readonly branchRetentionPolicy: 'KEEP_MERGED_BRANCHES';
  readonly stage: string;
  readonly nextAction: string;
  readonly eta: string;
  readonly freshOos: 'NOT_RUN_NO_READ';
  readonly liveTrading: 'BLOCKED';
  readonly authority: 'BOUND_LOCAL_AUDIT_BLOCKED';
  readonly reviewedRun: string;
  readonly reviewedEvidenceManifest: string;
};

export const PROGRAM_EXECUTION: ProgramExecution = {
  overallScore: programOverallScore(PROGRAM_LANES),
  implementationScore: 94,
  economicModelScore: 20,
  liveReadinessScore: 0,
  pageCount: V6_PAGES.length,
  deliveryLane: 'tag v1.28.0 → develop/v1.29.0-dev → codex/v1.29.0-dev-<task> → develop/v1.29.0-dev (--no-ff · MERGED 보존)',
  developmentVersion: 'v1.29.0-dev',
  latestRelease: 'v1.28.0',
  versionPolicy: 'ONE_DEV_LINE_TASK_BRANCH_NO_FF_PRESERVE',
  branchRetentionPolicy: 'KEEP_MERGED_BRANCHES',
  stage: 'V1_29_DEV_CUSTODY_REPRODUCTION_AUTHORITY_BLOCKED',
  nextAction: '서명된 reviewer trust root·검토자 key·raw-to-normalized extraction receipt를 구현한 뒤 PIT·가격 원천을 재감사하고 Fresh OOS를 20~60거래일 축적한다',
  eta: '외부 원천 확보·검토 1~3일 / Fresh OOS 표본 축적 4~12주 / 판정 실행 2~4시간 / 사람 승인 별도',
  freshOos: 'NOT_RUN_NO_READ',
  liveTrading: 'BLOCKED',
  authority: 'BOUND_LOCAL_AUDIT_BLOCKED',
  reviewedRun: 'DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_002',
  reviewedEvidenceManifest: 'POST_HOC_REPRO_002_D0_BLOCKED_D1_0_OF_28182_TEST_FEATURES_CONSUMED_REWARDS_SEALED',
};
