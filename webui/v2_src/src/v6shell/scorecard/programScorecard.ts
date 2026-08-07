import { PROGRAM_SCORE_RUBRIC, programRubricScore } from './programRubric';
import type { ProgramLane } from './programTypes';

export * from './programPages';
export { PROGRAM_CAPABILITIES } from './programCapabilities';
export { PROGRAM_SCORE_RUBRIC, programRubricScore };
export type * from './programTypes';

export const PROGRAM_LANES = [
  { id: 'platform', label: 'Platform', labelKo: '플랫폼·UX', score: programRubricScore('platform'), weight: 30, state: 'STRONG', evidence: '8개 통합 페이지, 공통 셸, 반응형 UI, 실제 브라우저 검수', nextAction: 'v1.29.0-dev에서 성능·접근성 회귀를 유지합니다.' },
  { id: 'rl-evidence', label: 'RL Evidence', labelKo: '강화학습 증거', score: programRubricScore('rl-evidence'), weight: 30, state: 'PARTIAL', evidence: '학습 artifact와 통제군은 있으나 경제적 정책과 Fresh OOS가 없습니다.', nextAction: 'PIT 권위 gate 후 같은 사전등록 코드를 재실행합니다.' },
  { id: 'engineering', label: 'Engineering', labelKo: '엔지니어링', score: programRubricScore('engineering'), weight: 20, state: 'STRONG', evidence: 'typed API, 경량 telemetry, 모델 artifact, 회귀검증을 갖췄습니다.', nextAction: '성능 예산과 접근성 회귀를 릴리스 gate로 고정합니다.' },
  { id: 'governance', label: 'Governance', labelKo: '연구 거버넌스', score: programRubricScore('governance'), weight: 10, state: 'PARTIAL', evidence: '사전등록·실패 공개·브랜치 계보는 있고 외부 custody는 미완료입니다.', nextAction: '외부 원천 receipt와 사람 승인을 연결합니다.' },
  { id: 'live', label: 'Live Readiness', labelKo: '실거래 준비도', score: programRubricScore('live'), weight: 10, state: 'BLOCKED', evidence: 'Fresh OOS, paper, broker, 운영 위험 통제가 없습니다.', nextAction: 'G7 승인 전 live 기능 접근을 금지합니다.' },
] as const satisfies readonly ProgramLane[];

export function programOverallScore(lanes: readonly ProgramLane[]): number {
  return Math.round(lanes.reduce((sum, lane) => sum + (lane.score * lane.weight) / 100, 0));
}
