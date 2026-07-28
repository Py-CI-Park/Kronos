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
  { id: 'platform', label: 'Platform', labelKo: '플랫폼', score: 95, weight: 30, state: 'STRONG', evidence: 'V6 전체 페이지, 읽기 전용 API, artifact scanner, D1 Primary terminal receipt', nextAction: 'D2 episode-scale 계약을 동일 evidence 흐름에 연결' },
  { id: 'rl-evidence', label: 'RL Evidence', labelKo: '강화학습 증거', score: 72, weight: 30, state: 'PARTIAL', evidence: 'D1 Primary 9/9 완료; 23bp accounting; native/diagnostic 학습 및 shuffled control 분리', nextAction: 'D2 1/8/32/128 episode scale을 별도 사전등록' },
  { id: 'engineering', label: 'Engineering', labelKo: '엔지니어링', score: 93, weight: 20, state: 'STRONG', evidence: '재현 가능한 runner, 안전한 terminal receipt, Python/TS 회귀 테스트, Windows Torch preloader', nextAction: 'D2 장기 실행 checkpoint와 실패 복구 계약 추가' },
  { id: 'governance', label: 'Governance', labelKo: '개발 거버넌스', score: 82, weight: 10, state: 'PARTIAL', evidence: 'prereg/fixture SHA, immutable run, custody manifest, codex→research→release tag 흐름', nextAction: 'D2 prereg와 PR 보호 규칙을 유지' },
  { id: 'live', label: 'Live Readiness', labelKo: '라이브 준비도', score: 0, weight: 10, state: 'BLOCKED', evidence: 'train-only 연구; Fresh OOS 봉인; 브로커 주문 권한 없음', nextAction: 'D2~D5 연구 gate 전에는 진행 금지' },
] as const satisfies readonly ProgramLane[];

export const PROGRAM_PAGE_MATRIX = [
  { id: 'home', group: 'COMMAND', page: 'Home', purpose: '전체 연구 상태와 안전 경계 요약', delivery: 'BUILT', evidenceState: 'D1_TRAIN_ONLY_CONFIRMED', progress: 98, priority: 'P1', nextAction: 'D2 계획과 Fresh OOS 봉인 상태 연결', eta: '20분', mergeGate: '상태·판정·증거 일치' },
  { id: 'scorecard', group: 'COMMAND', page: 'Program Scorecard', purpose: '점수와 페이지 진행률 감사', delivery: 'BUILT', evidenceState: 'D1_AUDITED', progress: 97, priority: 'P1', nextAction: 'D2 완료 시 증거 기반 재채점', eta: '15분', mergeGate: '가중치 100%와 근거 명시' },
  { id: 'rl-discovery', group: 'RL', page: 'Discovery Lab', purpose: 'D0~D7 연구 질문과 arm 귀속성', delivery: 'BUILT', evidenceState: 'D1_PRIMARY_COMPLETE', progress: 98, priority: 'P0', nextAction: 'D2 episode scale 사전등록', eta: '설계 2~4시간', mergeGate: '9/9 + terminal receipt + custody' },
  { id: 'rl-data', group: 'RL', page: 'Data', purpose: '데이터 split·비용·Fresh OOS 경계', delivery: 'BUILT', evidenceState: 'TRAIN_ONLY_FIXTURE_BOUND', progress: 92, priority: 'P0', nextAction: 'D2 1/8/32/128 episode registry 정의', eta: '2~4시간', mergeGate: 'fixture SHA와 episode identity 고정' },
  { id: 'rl-experiment', group: 'RL', page: 'Experiment', purpose: '가설·arm·seed·gate 사전등록', delivery: 'BUILT', evidenceState: 'D1_PREREG_COMPLETE', progress: 97, priority: 'P0', nextAction: 'D2 prereg 신규 작성', eta: '2~3시간', mergeGate: '실행 전 prereg SHA 고정' },
  { id: 'rl-training', group: 'RL', page: 'Training', purpose: '학습 진행·모델·resume 상태', delivery: 'BUILT', evidenceState: 'PRIMARY_COMPLETE', progress: 97, priority: 'P1', nextAction: 'D2 Smoke 후 조건부 Primary', eta: '실행 1~3시간', mergeGate: '모델·seed·normalizer·outcome 보존' },
  { id: 'rl-evaluation', group: 'RL', page: 'Evaluation', purpose: '비용·baseline·negative control 평가', delivery: 'BUILT', evidenceState: 'NO_GO', progress: 96, priority: 'P0', nextAction: 'D1은 train-only 확인으로 제한하고 D2 일반화 gate 추가', eta: '1~2시간', mergeGate: 'control·collapse·실패 공개' },
  { id: 'rl-compare', group: 'RL', page: 'Compare', purpose: '정책·rule·shuffled control 비교', delivery: 'BUILT', evidenceState: 'D1_PRIMARY_COMPARED', progress: 94, priority: 'P1', nextAction: 'D2 episode별 A/B/C 비교', eta: '1시간', mergeGate: 'RULE과 RL 라벨 분리' },
  { id: 'rl-report', group: 'RL', page: 'Report', purpose: '판정·artifact·계보 보고', delivery: 'BUILT', evidenceState: 'D1_PRIMARY_RECEIPT', progress: 96, priority: 'P1', nextAction: 'D2 prereg와 결과 문서 연결', eta: '30~60분', mergeGate: 'SHA·9 outcomes·한계 포함' },
  { id: 'insights', group: 'RESEARCH', page: 'Insights', purpose: '종목·수급·시장 국면 관찰', delivery: 'BUILT', evidenceState: 'OBSERVATION', progress: 72, priority: 'P2', nextAction: '관찰과 정책 증거의 경계 강화', eta: '30~60분', mergeGate: 'alpha 주장 없음' },
  { id: 'lanes', group: 'PLATFORM', page: 'Other Lanes', purpose: '인트라데이·Kronos 보조 연구', delivery: 'BUILT', evidenceState: 'INELIGIBLE_FOR_RL_RANK', progress: 70, priority: 'P2', nextAction: 'RL 점수 제외 사유 유지', eta: '30분', mergeGate: 'RL 성과로 합산 금지' },
  { id: 'settings', group: 'ADVANCED', page: 'Settings', purpose: '테마·화면·로컬 연구 환경', delivery: 'BUILT', evidenceState: 'LOCAL_ONLY', progress: 80, priority: 'HOLD', nextAction: '실행 제어 권한 추가 보류', eta: '15분', mergeGate: '읽기 전용 경계 유지' },
] as const satisfies readonly ProgramPageRow[];

export const PROGRAM_CAPABILITIES = [
  { id: 'type1-review', capability: 'Type1 NO-GO 증거 조회', state: 'AVAILABLE', boundary: '기존 판정을 변경하지 않음' },
  { id: 'd0-smoke', capability: 'D0 4-arm Smoke·Primary 조회', state: 'AVAILABLE', boundary: 'PPO-only 귀속성 미확인' },
  { id: 'd1-primary', capability: 'D1 3-arm × 3-seed Primary', state: 'AVAILABLE', boundary: '합성 train-only 행동·보상 메커니즘 확인' },
  { id: 'resume', capability: 'D1 arm/seed 단위 재개', state: 'AVAILABLE', boundary: 'digest 검증된 완료 단위만 건너뛰며 terminal receipt 이후 불변' },
  { id: 'artifact-audit', capability: 'prereg SHA·receipt·custody 감사', state: 'AVAILABLE', boundary: '로컬 연구 evidence' },
  { id: 'd2-d6', capability: 'D2~D6 연구 사다리', state: 'PARTIAL', boundary: '각 단계는 별도 사전등록과 gate 필요' },
  { id: 'fresh-oos', capability: 'Fresh OOS 조회', state: 'BLOCKED', boundary: 'NOT_RUN_NO_READ' },
  { id: 'live-trading', capability: '브로커 주문·라이브 운영', state: 'BLOCKED', boundary: '권한·검증·운영 준비 없음' },
] as const satisfies readonly ProgramCapability[];

export function programOverallScore(lanes: readonly ProgramLane[]): number {
  return Math.round(lanes.reduce((total, lane) => total + lane.score * lane.weight / 100, 0));
}
