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
  overallScore: 65,
  pageCount: 12,
  branch: 'codex/rl-model-lifecycle-v1',
  baseTag: 'fork-v1.8.0-kronos-rl-discovery-scorecard',
  stage: 'IMPLEMENTED_PENDING_PR',
  nextAction: 'D0 Primary를 resume 가능한 runner로 실행',
  eta: 'CPU 3–4시간+ / 평가·보고 1시간',
  freshOos: 'NOT_RUN_NO_READ',
  liveTrading: 'BLOCKED',
};
