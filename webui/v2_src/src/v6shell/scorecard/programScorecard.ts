export type ProgramLaneId = 'platform' | 'rl-evidence' | 'engineering' | 'governance' | 'live';
export type ProgramState = 'STRONG' | 'PARTIAL' | 'BLOCKED';
export type CapabilityState = 'AVAILABLE' | 'PARTIAL' | 'BLOCKED';
export type PagePriority = 'P0' | 'P1' | 'P2' | 'HOLD';

export type ProgramLane = {
  readonly id: ProgramLaneId;
  readonly label: string;
  readonly labelKo: string;
  readonly score: number;
  readonly weight: number;
  readonly state: ProgramState;
  readonly evidence: string;
  readonly nextAction: string;
};

export type ProgramPageRow = {
  readonly id: string;
  readonly group: string;
  readonly page: string;
  readonly purpose: string;
  readonly delivery: 'BUILT';
  readonly evidenceState: string;
  readonly progress: number;
  readonly priority: PagePriority;
  readonly nextAction: string;
  readonly eta: string;
  readonly mergeGate: string;
};

export type ProgramCapability = {
  readonly id: string;
  readonly capability: string;
  readonly state: CapabilityState;
  readonly boundary: string;
};

export const PROGRAM_LANES = [
  { id: 'platform', label: 'Platform', labelKo: '플랫폼', score: 94, weight: 30, state: 'STRONG', evidence: 'V6 전체 페이지, 읽기 전용 API, artifact scanner, Primary terminal artifact', nextAction: 'D1 prereg 상태를 동일 evidence 흐름에 연결' },
  { id: 'rl-evidence', label: 'RL Evidence', labelKo: '강화학습 증거', score: 65, weight: 30, state: 'PARTIAL', evidence: 'D0 Primary 12/12 완료; PPO-only overfit 미확인; BC-only 3/3 완전 적합', nextAction: 'D0를 NO-GO로 종료하고 D1 가설 사전등록' },
  { id: 'engineering', label: 'Engineering', labelKo: '엔지니어링', score: 92, weight: 20, state: 'STRONG', evidence: '12개 모델·normalizer·outcome 저장, resume, terminal receipt, Python/TS 검증', nextAction: 'mid-arm checkpoint는 별도 연구 과제로 유지' },
  { id: 'governance', label: 'Governance', labelKo: '개발 거버넌스', score: 78, weight: 10, state: 'PARTIAL', evidence: 'prereg SHA, PRIMARY_COMPLETE receipt, codex 브랜치와 release tag 규칙', nextAction: 'PR 보호 규칙과 CI gate 적용' },
  { id: 'live', label: 'Live Readiness', labelKo: '라이브 준비도', score: 0, weight: 10, state: 'BLOCKED', evidence: '연구 전용; Fresh OOS 봉인; 브로커 권한 없음', nextAction: '연구 gate 통과 전 진행 금지' },
] as const satisfies readonly ProgramLane[];

export const PROGRAM_PAGE_MATRIX = [
  { id: 'home', group: 'COMMAND', page: 'Home', purpose: '전체 연구 상태와 안전 경계 요약', delivery: 'BUILT', evidenceState: 'PRIMARY_NO_GO', progress: 97, priority: 'P1', nextAction: 'D1 진입 조건을 NO-GO 경계와 연결', eta: '30분', mergeGate: '상태·판정 값 일치' },
  { id: 'scorecard', group: 'COMMAND', page: 'Program Scorecard', purpose: '점수, 페이지 진행률, 개발 흐름 감사', delivery: 'BUILT', evidenceState: 'AUDITED', progress: 96, priority: 'P1', nextAction: 'PR 리뷰 후 릴리스 점수 고정', eta: '20분', mergeGate: '가중치 100% + 근거 명시' },
  { id: 'rl-discovery', group: 'RL', page: 'Discovery Lab', purpose: 'D0~D6 연구 질문과 arm 귀속성', delivery: 'BUILT', evidenceState: 'PRIMARY_COMPLETE', progress: 96, priority: 'P0', nextAction: 'D0 NO-GO 종료와 D1 가설 사전등록', eta: '설계 4–8시간', mergeGate: '12/12 + terminal receipt 확인' },
  { id: 'rl-data', group: 'RL', page: 'Data', purpose: '데이터 split·비용·Fresh OOS 경계', delivery: 'BUILT', evidenceState: 'TRAIN_ONLY_LOCKED', progress: 90, priority: 'P1', nextAction: 'D1 train-only 입력 계약 작성', eta: '1–2시간', mergeGate: 'Fresh OOS 봉인 + SHA 일치' },
  { id: 'rl-experiment', group: 'RL', page: 'Experiment', purpose: '사전등록과 실험 잠금', delivery: 'BUILT', evidenceState: 'D0_TERMINAL', progress: 95, priority: 'P0', nextAction: 'D1 reward/action redesign preregister', eta: '4–8시간', mergeGate: 'D0 변경 금지 + 새 가설 분리' },
  { id: 'rl-training', group: 'RL', page: 'Training', purpose: '학습 실행·seed·부분 결과·resume 상태', delivery: 'BUILT', evidenceState: 'PRIMARY_COMPLETE', progress: 96, priority: 'P1', nextAction: 'D1 smoke budget만 새 실행', eta: '구현 후 30분', mergeGate: '12 모델·normalizer·outcome 보존' },
  { id: 'rl-evaluation', group: 'RL', page: 'Evaluation', purpose: '비용·baseline·negative control 평가', delivery: 'BUILT', evidenceState: 'NO_GO', progress: 94, priority: 'P0', nextAction: 'PPO 귀속 실패와 BC 효과 문서화', eta: '30분', mergeGate: 'control + collapse + failure 공개' },
  { id: 'rl-compare', group: 'RL', page: 'Compare', purpose: '정책·rule·shuffled control 비교', delivery: 'BUILT', evidenceState: 'PRIMARY_COMPARED', progress: 92, priority: 'P1', nextAction: 'A/B/C/D 평균 비교 고정', eta: '20분', mergeGate: 'RULE과 RL 라벨 분리' },
  { id: 'rl-report', group: 'RL', page: 'Report', purpose: '판정·artifact·계보 보고', delivery: 'BUILT', evidenceState: 'PRIMARY_RECEIPT', progress: 94, priority: 'P1', nextAction: 'PR에 terminal receipt와 결과표 첨부', eta: '30분', mergeGate: 'NO-GO 근거·SHA·12 outcomes 포함' },
  { id: 'insights', group: 'RESEARCH', page: 'Insights', purpose: '종목·수급·시장 국면 관찰', delivery: 'BUILT', evidenceState: 'OBSERVATION', progress: 70, priority: 'P2', nextAction: '관찰과 정책 증거의 경계 강화', eta: '30–60분', mergeGate: 'alpha 주장 없음' },
  { id: 'lanes', group: 'PLATFORM', page: 'Other Lanes', purpose: '인트라데이·Kronos 보조 연구', delivery: 'BUILT', evidenceState: 'INELIGIBLE_FOR_RL_RANK', progress: 68, priority: 'P2', nextAction: 'RL 점수 제외 표식 재검수', eta: '30분', mergeGate: 'RL 성과로 합산 금지' },
  { id: 'settings', group: 'ADVANCED', page: 'Settings', purpose: '테마·화면·로컬 연구 환경', delivery: 'BUILT', evidenceState: 'LOCAL_ONLY', progress: 80, priority: 'HOLD', nextAction: '실행 제어 권한 추가 금지 유지', eta: '15분', mergeGate: '읽기 전용 경계 유지' },
] as const satisfies readonly ProgramPageRow[];

export const PROGRAM_CAPABILITIES = [
  { id: 'type1-review', capability: 'Type1 NO-GO 증거 조회', state: 'AVAILABLE', boundary: '기존 판정을 변경하지 않음' },
  { id: 'd0-smoke', capability: 'D0 4-arm 실제 smoke·모델 생성', state: 'AVAILABLE', boundary: '수익성 또는 일반화 증거가 아님' },
  { id: 'resume', capability: 'arm/seed 부분 저장·재개', state: 'AVAILABLE', boundary: '완료된 단위만 건너뛰는 재개' },
  { id: 'artifact-audit', capability: 'prereg SHA·receipt·artifact 감사', state: 'AVAILABLE', boundary: '읽기 전용 evidence' },
  { id: 'primary', capability: 'D0 Primary 4-arm × 3-seed', state: 'AVAILABLE', boundary: 'PRIMARY_COMPLETE / PPO_ONLY_OVERFIT_NOT_CONFIRMED' },
  { id: 'd1-d6', capability: 'D1~D6 연구 사다리', state: 'PARTIAL', boundary: 'D0 NO-GO 종료 후 새 가설을 사전등록해야 함' },
  { id: 'fresh-oos', capability: 'Fresh OOS 조회', state: 'BLOCKED', boundary: 'NOT_RUN_NO_READ' },
  { id: 'live-trading', capability: '브로커 주문·라이브 운영', state: 'BLOCKED', boundary: '권한·검증·규제 준비 없음' },
] as const satisfies readonly ProgramCapability[];

export function programOverallScore(lanes: readonly ProgramLane[]): number {
  return Math.round(lanes.reduce((total, lane) => total + lane.score * lane.weight / 100, 0));
}
