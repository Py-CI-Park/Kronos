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
  { id: 'platform', label: 'Platform', labelKo: '플랫폼', score: 96, weight: 30, state: 'STRONG', evidence: 'V6 전체 페이지, 읽기 전용 API, D2 24-model reviewed snapshot과 terminal receipt', nextAction: 'D3 결과를 같은 evidence 흐름에 연결' },
  { id: 'rl-evidence', label: 'RL Evidence', labelKo: '강화학습 증거', score: 78, weight: 30, state: 'PARTIAL', evidence: '실제 일봉 D2 24/24 완료; 8 episodes 과적합 확인; @128 native−shuffle +0.536', nextAction: 'D3 representation/action ablation 사전등록' },
  { id: 'engineering', label: 'Engineering', labelKo: '엔지니어링', score: 94, weight: 20, state: 'STRONG', evidence: '438MB streaming, custody hash, PPO-only runner, Smoke→Primary 승인, 실패 재현 테스트', nextAction: 'D3 resume 단위를 scale/arm/seed까지 확장' },
  { id: 'governance', label: 'Governance', labelKo: '개발 거버넌스', score: 86, weight: 10, state: 'PARTIAL', evidence: 'prereg SHA, immutable runs, negative control, codex→research→master PR 계보', nextAction: 'D2 merge tag 후 master 통합 PR 검증' },
  { id: 'live', label: 'Live Readiness', labelKo: '라이브 준비도', score: 0, weight: 10, state: 'BLOCKED', evidence: 'train-only 연구; Fresh OOS 봉인; 브로커 주문 권한 없음', nextAction: 'D3~D6 연구 gate 전에는 진행 금지' },
] as const satisfies readonly ProgramLane[];

export const PROGRAM_PAGE_MATRIX = [
  { id: 'home', group: 'COMMAND', page: 'Home', purpose: '전체 연구 상태와 안전 경계 요약', delivery: 'BUILT', evidenceState: 'D2_PARTIAL_CAPACITY', progress: 99, priority: 'P1', nextAction: 'D3 질문과 Fresh OOS 봉인 상태 연결', eta: '20분', mergeGate: '상태·판정·증거 일치' },
  { id: 'scorecard', group: 'COMMAND', page: 'Program Scorecard', purpose: '점수와 페이지 진행률 감사', delivery: 'BUILT', evidenceState: 'D2_AUDITED', progress: 99, priority: 'P1', nextAction: 'D3 완료 후 증거 기반 재채점', eta: '15분', mergeGate: '가중치 100%와 근거 명시' },
  { id: 'rl-discovery', group: 'RL', page: 'Discovery Lab', purpose: 'D0~D7 연구 질문과 arm 귀속성', delivery: 'BUILT', evidenceState: 'D2_PRIMARY_24_OF_24', progress: 100, priority: 'P0', nextAction: 'D3 representation/action ablation', eta: '설계 2~4시간', mergeGate: '24/24 + terminal receipt + control' },
  { id: 'rl-data', group: 'RL', page: 'Data', purpose: '데이터 split·비용·Fresh OOS 경계', delivery: 'BUILT', evidenceState: 'HISTORICAL_128_BOUND', progress: 96, priority: 'P0', nextAction: '특징 표현 후보를 train-only로 고정', eta: '2~3시간', mergeGate: 'rows/normalizer/episode SHA 고정' },
  { id: 'rl-experiment', group: 'RL', page: 'Experiment', purpose: '가설·arm·seed·gate 사전등록', delivery: 'BUILT', evidenceState: 'D2_PREREG_COMPLETE', progress: 100, priority: 'P0', nextAction: 'D3 prereg 신규 작성', eta: '2~3시간', mergeGate: '실행 전 prereg SHA 고정' },
  { id: 'rl-training', group: 'RL', page: 'Training', purpose: '학습 진행·모델·resume 상태', delivery: 'BUILT', evidenceState: 'PRIMARY_COMPLETE', progress: 99, priority: 'P1', nextAction: 'D3 Smoke 후 조건부 Primary', eta: '실행 2~4시간', mergeGate: 'scale·arm·seed·model 보존' },
  { id: 'rl-evaluation', group: 'RL', page: 'Evaluation', purpose: '비용·baseline·negative control 평가', delivery: 'BUILT', evidenceState: 'D2_PARTIAL_CAPACITY', progress: 99, priority: 'P0', nextAction: 'D3에서 32/128 적합 실패 원인 분리', eta: '2~4시간', mergeGate: 'fit/native/23bp를 분리 공개' },
  { id: 'rl-compare', group: 'RL', page: 'Compare', purpose: '정책·rule·shuffled control 비교', delivery: 'BUILT', evidenceState: 'D2_NATIVE_SHUFFLE_COMPARED', progress: 98, priority: 'P1', nextAction: 'representation별 128-episode delta 비교', eta: '1~2시간', mergeGate: 'RULE과 RL 라벨 분리' },
  { id: 'rl-report', group: 'RL', page: 'Report', purpose: '판정·artifact·거버넌스 보고', delivery: 'BUILT', evidenceState: 'D2_PRIMARY_RECEIPT', progress: 99, priority: 'P1', nextAction: 'D3 prereg와 결과 문서 연결', eta: '30~60분', mergeGate: 'SHA·24 outcomes·한계 포함' },
  { id: 'insights', group: 'RESEARCH', page: 'Insights', purpose: '종목·수급·시장 국면 관찰', delivery: 'BUILT', evidenceState: 'OBSERVATION_ONLY', progress: 72, priority: 'P2', nextAction: '관찰과 정책 증거의 경계 강화', eta: '30~60분', mergeGate: 'alpha 주장 없음' },
  { id: 'lanes', group: 'PLATFORM', page: 'Other Lanes', purpose: '인트라데이·Kronos 보조 연구', delivery: 'BUILT', evidenceState: 'INELIGIBLE_FOR_RL_RANK', progress: 70, priority: 'P2', nextAction: 'RL 점수 제외 사유 유지', eta: '30분', mergeGate: 'RL 성과로 합산 금지' },
  { id: 'settings', group: 'ADVANCED', page: 'Settings', purpose: '테마·화면·로컬 연구 환경', delivery: 'BUILT', evidenceState: 'LOCAL_ONLY', progress: 80, priority: 'HOLD', nextAction: '실행 제어 권한 추가 보류', eta: '15분', mergeGate: '읽기 전용 경계 유지' },
] as const satisfies readonly ProgramPageRow[];

export const PROGRAM_CAPABILITIES = [
  { id: 'type1-review', capability: 'Type1 NO-GO 증거 조회', state: 'AVAILABLE', boundary: '기존 판정을 변경하지 않음' },
  { id: 'd0-smoke', capability: 'D0 4-arm Smoke·Primary 조회', state: 'AVAILABLE', boundary: 'PPO-only 귀속성 미확인' },
  { id: 'd1-primary', capability: 'D1 3-arm × 3-seed Primary', state: 'AVAILABLE', boundary: '합성 train-only 행동·보상 메커니즘 확인' },
  { id: 'd2-primary', capability: 'D2 실제 일봉 4-scale × 2-arm × 3-seed', state: 'AVAILABLE', boundary: '8 episodes까지만 PPO-only 과적합 확인; 수익성 근거 아님' },
  { id: 'artifact-audit', capability: 'prereg SHA·receipt·custody 감사', state: 'AVAILABLE', boundary: '로컬 연구 evidence' },
  { id: 'd3-d6', capability: 'D3~D6 연구 사다리', state: 'PARTIAL', boundary: 'representation, cost, full train, reused validation은 별도 사전등록 필요' },
  { id: 'fresh-oos', capability: 'Fresh OOS 조회', state: 'BLOCKED', boundary: 'NOT_RUN_NO_READ' },
  { id: 'live-trading', capability: '브로커 주문·라이브 운영', state: 'BLOCKED', boundary: '권한·검증·운영 준비 없음' },
] as const satisfies readonly ProgramCapability[];

export function programOverallScore(lanes: readonly ProgramLane[]): number {
  return Math.round(lanes.reduce((total, lane) => total + lane.score * lane.weight / 100, 0));
}
