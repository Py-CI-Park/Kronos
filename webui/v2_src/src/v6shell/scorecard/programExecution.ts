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
};

export const PROGRAM_EXECUTION: ProgramExecution = {
  overallScore: programOverallScore(PROGRAM_LANES),
  pageCount: PROGRAM_PAGE_MATRIX.length,
  deliveryLane: 'codex/* → research/* → annotated release tag',
  baseRelease: 'fork-v1.8.0-kronos-rl-discovery-scorecard',
  releaseCandidate: 'fork-v1.9.0-kronos-rl-model-lifecycle',
  stage: 'PRIMARY_COMPLETE_NO_GO',
  nextAction: 'D0 closeout 후 D1 reward/action redesign을 preregister',
  eta: '설계 4–8시간 / 구현·smoke 1–2일',
  freshOos: 'NOT_RUN_NO_READ',
  liveTrading: 'BLOCKED',
};
