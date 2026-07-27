export type ProgramLaneId = 'platform' | 'rl-evidence' | 'engineering' | 'governance' | 'live';
export type ProgramState = 'STRONG' | 'PARTIAL' | 'BLOCKED';
export type CapabilityState = 'AVAILABLE' | 'PARTIAL' | 'BLOCKED';

export type ProgramLane = {
  readonly id: ProgramLaneId; readonly label: string; readonly labelKo: string;
  readonly score: number; readonly weight: number; readonly state: ProgramState;
  readonly evidence: string; readonly nextAction: string;
};
export type ProgramPageRow = {
  readonly id: string; readonly group: string; readonly page: string; readonly purpose: string;
  readonly delivery: 'BUILT'; readonly evidenceState: string;
};
export type ProgramCapability = {
  readonly id: string; readonly capability: string; readonly state: CapabilityState; readonly boundary: string;
};

export const PROGRAM_LANES = [
  { id: 'platform', label: 'Platform', labelKo: '플랫폼', score: 88, weight: 30, state: 'STRONG', evidence: 'V6 shell, read-only APIs, artifact scanner, desktop/mobile UI', nextAction: 'Primary resume checkpoints' },
  { id: 'rl-evidence', label: 'RL Evidence', labelKo: '강화학습 증거', score: 38, weight: 30, state: 'PARTIAL', evidence: 'D0 smoke complete; Type1 complete/NO_GO; Primary incomplete', nextAction: 'Finish immutable D0 Primary' },
  { id: 'engineering', label: 'Engineering', labelKo: '엔지니어링', score: 86, weight: 20, state: 'STRONG', evidence: 'Python/TS tests, strict types, production build, Chromium QA', nextAction: 'Add resumable long-run E2E' },
  { id: 'governance', label: 'Governance', labelKo: '개발 거버넌스', score: 70, weight: 10, state: 'PARTIAL', evidence: 'Prereg SHA, receipts, branch and release convention', nextAction: 'Protect release flow in CI' },
  { id: 'live', label: 'Live Readiness', labelKo: '라이브 준비도', score: 0, weight: 10, state: 'BLOCKED', evidence: 'Research-only; Fresh OOS sealed; no broker authorization', nextAction: 'No action before research gates' },
] as const satisfies readonly ProgramLane[];

export const PROGRAM_PAGE_MATRIX = [
  { id: 'home', group: 'COMMAND', page: 'Home', purpose: '연구 상태와 안전 경계 요약', delivery: 'BUILT', evidenceState: 'READ_ONLY' },
  { id: 'scorecard', group: 'COMMAND', page: 'Program Scorecard', purpose: '전체 프로그램 점수와 개발 흐름', delivery: 'BUILT', evidenceState: 'AUDITED' },
  { id: 'rl-discovery', group: 'RL', page: 'Discovery Lab', purpose: 'D0~D6 사다리와 arm 귀속성', delivery: 'BUILT', evidenceState: 'SMOKE_COMPLETE' },
  { id: 'rl-data', group: 'RL', page: 'Data', purpose: '데이터·split·Fresh OOS 경계', delivery: 'BUILT', evidenceState: 'MIXED' },
  { id: 'rl-experiment', group: 'RL', page: 'Experiment', purpose: '사전등록과 실험 잠금', delivery: 'BUILT', evidenceState: 'PREREGISTERED' },
  { id: 'rl-training', group: 'RL', page: 'Training', purpose: '학습 실행·seed·step 상태', delivery: 'BUILT', evidenceState: 'PRIMARY_INCOMPLETE' },
  { id: 'rl-evaluation', group: 'RL', page: 'Evaluation', purpose: '비용·baseline·control 평가', delivery: 'BUILT', evidenceState: 'NO_GO' },
  { id: 'rl-compare', group: 'RL', page: 'Compare', purpose: '정책·rule·negative control 비교', delivery: 'BUILT', evidenceState: 'RESEARCH_ONLY' },
  { id: 'rl-report', group: 'RL', page: 'Report', purpose: '판정·아티팩트·계보 보고', delivery: 'BUILT', evidenceState: 'HAS_REPORTS' },
  { id: 'insights', group: 'RESEARCH', page: 'Insights', purpose: '종목·수급·시장 국면 관찰', delivery: 'BUILT', evidenceState: 'OBSERVATION' },
  { id: 'lanes', group: 'PLATFORM', page: 'Other Lanes', purpose: '인트라데이·Kronos 보조 연구', delivery: 'BUILT', evidenceState: 'INELIGIBLE_FOR_RL_RANK' },
  { id: 'settings', group: 'ADVANCED', page: 'Settings', purpose: '테마·화면·연구 환경 설정', delivery: 'BUILT', evidenceState: 'LOCAL_ONLY' },
] as const satisfies readonly ProgramPageRow[];

export const PROGRAM_CAPABILITIES = [
  { id: 'type1-review', capability: 'Type1 NO_GO 증거 조회', state: 'AVAILABLE', boundary: '기존 판정을 변경하지 않음' },
  { id: 'd0-smoke', capability: 'D0 4-arm smoke 실행·비교', state: 'AVAILABLE', boundary: '수익성 또는 일반화 판정 아님' },
  { id: 'artifact-audit', capability: 'Prereg SHA·receipt·artifact 감사', state: 'AVAILABLE', boundary: 'read-only evidence' },
  { id: 'primary', capability: 'D0 Primary 104k×3 seed', state: 'PARTIAL', boundary: '체크포인트·재개 기능 필요' },
  { id: 'd1-d6', capability: 'D1~D6 연구 사다리', state: 'PARTIAL', boundary: '이전 단계 gate 후 순차 실행' },
  { id: 'fresh-oos', capability: 'Fresh OOS 조회', state: 'BLOCKED', boundary: 'NOT_RUN_NO_READ' },
  { id: 'live-trading', capability: '브로커 주문·라이브 운용', state: 'BLOCKED', boundary: '권한·검증·제품화 없음' },
] as const satisfies readonly ProgramCapability[];

export function programOverallScore(lanes: readonly ProgramLane[]): number {
  return Math.round(lanes.reduce((total, lane) => total + lane.score * lane.weight / 100, 0));
}
