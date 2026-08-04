import { PROGRAM_SCORE_RUBRIC, programRubricScore } from './programRubric';
import type { ProgramLane } from './programTypes';

export * from './programPages';
export { PROGRAM_CAPABILITIES } from './programCapabilities';
export { PROGRAM_SCORE_RUBRIC, programRubricScore };
export type * from './programTypes';

export const PROGRAM_LANES = [
  { id: 'platform', label: 'Platform', labelKo: '플랫폼', score: programRubricScore('platform'), weight: 30, state: 'STRONG', evidence: '13개 화면, 공통 결정 레일, 반응형 연구 상태 패널', nextAction: '정적 스냅샷을 영수증 API로 동적 연결' },
  { id: 'rl-evidence', label: 'RL Evidence', labelKo: '강화학습 증거', score: programRubricScore('rl-evidence'), weight: 30, state: 'PARTIAL', evidence: 'G3 진단 4/4, 합성 CQL 3/3. 실제 시장 모델과 Fresh OOS는 없음', nextAction: 'G2 데이터 관리 통과 후 G3를 재실행' },
  { id: 'engineering', label: 'Engineering', labelKo: '엔지니어링', score: programRubricScore('engineering'), weight: 20, state: 'STRONG', evidence: '타입 계약, 10슬롯 환경, DQN/CQL, 회귀 테스트', nextAction: '영수증 API와 실제 브라우저 뷰포트 QA 추가' },
  { id: 'governance', label: 'Governance', labelKo: '연구 거버넌스', score: programRubricScore('governance'), weight: 10, state: 'PARTIAL', evidence: '실패 공개, 주장 분리, 브랜치 계보. G2·G7 승인 미완료', nextAction: 'PIT 관리 영수증 고정 후 Draft PR 생성' },
  { id: 'live', label: 'Live Readiness', labelKo: '실거래 준비도', score: programRubricScore('live'), weight: 10, state: 'BLOCKED', evidence: 'Fresh OOS, paper, broker, 운영 위험 통제 미실행', nextAction: 'G7 승인 전 paper·broker·live 기능 접근 금지' },
] as const satisfies readonly ProgramLane[];

export function programOverallScore(lanes: readonly ProgramLane[]): number {
  return Math.round(lanes.reduce((sum, lane) => sum + (lane.score * lane.weight) / 100, 0));
}
