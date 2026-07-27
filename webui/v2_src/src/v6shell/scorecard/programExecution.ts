export type ProgramExecution = {
  readonly overallScore: number;
  readonly pageCount: number;
  readonly branch: string;
  readonly baseTag: string;
  readonly stage: string;
  readonly nextAction: string;
  readonly eta: string;
  readonly freshOos: 'NOT_RUN_NO_READ';
  readonly liveTrading: 'BLOCKED';
};

export const PROGRAM_EXECUTION: ProgramExecution = {
  overallScore: 74,
  pageCount: 12,
  branch: 'codex/rl-model-lifecycle-v1',
  baseTag: 'fork-v1.8.0-kronos-rl-discovery-scorecard',
  stage: 'PRIMARY_COMPLETE_NO_GO',
  nextAction: 'D0 closeout 후 D1 reward/action redesign을 preregister',
  eta: '설계 4–8시간 / 구현·smoke 1–2일',
  freshOos: 'NOT_RUN_NO_READ',
  liveTrading: 'BLOCKED',
};
