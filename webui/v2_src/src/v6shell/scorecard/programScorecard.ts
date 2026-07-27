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
  { id: 'platform', label: 'Platform', labelKo: '플랫폼', score: 92, weight: 30, state: 'STRONG', evidence: 'V6 전체 페이지, 읽기 전용 API, artifact scanner, 데스크톱/모바일 UI', nextAction: 'Primary 실행 상태를 실제 artifact로 갱신' },
  { id: 'rl-evidence', label: 'RL Evidence', labelKo: '강화학습 증거', score: 40, weight: 30, state: 'PARTIAL', evidence: 'D0 실제 smoke와 모델 저장 완료; Type1 COMPLETE/NO_GO; Primary 미완료', nextAction: '재개 가능한 D0 Primary 완료' },
  { id: 'engineering', label: 'Engineering', labelKo: '엔지니어링', score: 90, weight: 20, state: 'STRONG', evidence: 'arm/seed 부분 저장, 모델·normalizer 저장, resume, Python/TS 검증', nextAction: '중단·재개 장시간 E2E 추가' },
  { id: 'governance', label: 'Governance', labelKo: '개발 거버넌스', score: 74, weight: 10, state: 'PARTIAL', evidence: 'prereg SHA, terminal receipt, codex 브랜치와 release tag 규칙', nextAction: 'PR 보호 규칙과 CI gate 적용' },
  { id: 'live', label: 'Live Readiness', labelKo: '라이브 준비도', score: 0, weight: 10, state: 'BLOCKED', evidence: '연구 전용; Fresh OOS 봉인; 브로커 권한 없음', nextAction: '연구 gate 통과 전 진행 금지' },
] as const satisfies readonly ProgramLane[];

export const PROGRAM_PAGE_MATRIX = [
  { id: 'home', group: 'COMMAND', page: 'Home', purpose: '전체 연구 상태와 안전 경계 요약', delivery: 'BUILT', evidenceState: 'READ_ONLY', progress: 95, priority: 'P1', nextAction: 'Primary 실행 상태 링크 검수', eta: '15분', mergeGate: '상태·판정 값 일치' },
  { id: 'scorecard', group: 'COMMAND', page: 'Program Scorecard', purpose: '점수, 페이지 진행률, 개발 흐름 감사', delivery: 'BUILT', evidenceState: 'AUDITED', progress: 92, priority: 'P1', nextAction: 'Primary 종료 후 점수 재산정', eta: '20분', mergeGate: '가중치 100% + 근거 명시' },
  { id: 'rl-discovery', group: 'RL', page: 'Discovery Lab', purpose: 'D0~D6 연구 질문과 arm 귀속성', delivery: 'BUILT', evidenceState: 'SMOKE_COMPLETE', progress: 80, priority: 'P0', nextAction: 'D0 Primary 4-arm × 3-seed 실행', eta: 'CPU 3–4시간+', mergeGate: '모든 arm/seed + control 완료' },
  { id: 'rl-data', group: 'RL', page: 'Data', purpose: '데이터 split·비용·Fresh OOS 경계', delivery: 'BUILT', evidenceState: 'MIXED', progress: 85, priority: 'P1', nextAction: 'Primary 입력 provenance 재확인', eta: '30분', mergeGate: 'train-only + SHA 일치' },
  { id: 'rl-experiment', group: 'RL', page: 'Experiment', purpose: '사전등록과 실험 잠금', delivery: 'BUILT', evidenceState: 'PREREGISTERED', progress: 88, priority: 'P0', nextAction: 'run ID와 prereg SHA 고정', eta: '20분', mergeGate: '사전등록 변경 없음' },
  { id: 'rl-training', group: 'RL', page: 'Training', purpose: '학습 실행·seed·부분 결과·resume 상태', delivery: 'BUILT', evidenceState: 'RESUME_READY', progress: 72, priority: 'P0', nextAction: 'Primary 실행 후 중단·재개 검증', eta: 'CPU 3–4시간+', mergeGate: '모델·normalizer·outcome 저장' },
  { id: 'rl-evaluation', group: 'RL', page: 'Evaluation', purpose: '비용·baseline·negative control 평가', delivery: 'BUILT', evidenceState: 'NO_GO', progress: 78, priority: 'P0', nextAction: 'Primary terminal gate 계산', eta: '실행 후 20–40분', mergeGate: '23bp + control + collapse 공개' },
  { id: 'rl-compare', group: 'RL', page: 'Compare', purpose: '정책·rule·shuffled control 비교', delivery: 'BUILT', evidenceState: 'RESEARCH_ONLY', progress: 75, priority: 'P1', nextAction: '12개 Primary 결과 교차 비교', eta: '20분', mergeGate: 'RULE과 RL 라벨 분리' },
  { id: 'rl-report', group: 'RL', page: 'Report', purpose: '판정·artifact·계보 보고', delivery: 'BUILT', evidenceState: 'HAS_REPORTS', progress: 82, priority: 'P1', nextAction: 'Primary terminal receipt 반영', eta: '30분', mergeGate: 'NO-GO/GO 근거와 SHA 포함' },
  { id: 'insights', group: 'RESEARCH', page: 'Insights', purpose: '종목·수급·시장 국면 관찰', delivery: 'BUILT', evidenceState: 'OBSERVATION', progress: 70, priority: 'P2', nextAction: '관찰과 정책 증거의 경계 강화', eta: '30–60분', mergeGate: 'alpha 주장 없음' },
  { id: 'lanes', group: 'PLATFORM', page: 'Other Lanes', purpose: '인트라데이·Kronos 보조 연구', delivery: 'BUILT', evidenceState: 'INELIGIBLE_FOR_RL_RANK', progress: 68, priority: 'P2', nextAction: 'RL 점수 제외 표식 재검수', eta: '30분', mergeGate: 'RL 성과로 합산 금지' },
  { id: 'settings', group: 'ADVANCED', page: 'Settings', purpose: '테마·화면·로컬 연구 환경', delivery: 'BUILT', evidenceState: 'LOCAL_ONLY', progress: 80, priority: 'HOLD', nextAction: '실행 제어 권한 추가 금지 유지', eta: '15분', mergeGate: '읽기 전용 경계 유지' },
] as const satisfies readonly ProgramPageRow[];

export const PROGRAM_CAPABILITIES = [
  { id: 'type1-review', capability: 'Type1 NO-GO 증거 조회', state: 'AVAILABLE', boundary: '기존 판정을 변경하지 않음' },
  { id: 'd0-smoke', capability: 'D0 4-arm 실제 smoke·모델 생성', state: 'AVAILABLE', boundary: '수익성 또는 일반화 증거가 아님' },
  { id: 'resume', capability: 'arm/seed 부분 저장·재개', state: 'AVAILABLE', boundary: '완료된 단위만 건너뛰는 재개' },
  { id: 'artifact-audit', capability: 'prereg SHA·receipt·artifact 감사', state: 'AVAILABLE', boundary: '읽기 전용 evidence' },
  { id: 'primary', capability: 'D0 Primary 104k × 3 seed', state: 'PARTIAL', boundary: '실행 가능하지만 아직 terminal artifact 없음' },
  { id: 'd1-d6', capability: 'D1~D6 연구 사다리', state: 'PARTIAL', boundary: '이전 단계 gate 뒤 순차 실행' },
  { id: 'fresh-oos', capability: 'Fresh OOS 조회', state: 'BLOCKED', boundary: 'NOT_RUN_NO_READ' },
  { id: 'live-trading', capability: '브로커 주문·라이브 운영', state: 'BLOCKED', boundary: '권한·검증·규제 준비 없음' },
] as const satisfies readonly ProgramCapability[];

export function programOverallScore(lanes: readonly ProgramLane[]): number {
  return Math.round(lanes.reduce((total, lane) => total + lane.score * lane.weight / 100, 0));
}
