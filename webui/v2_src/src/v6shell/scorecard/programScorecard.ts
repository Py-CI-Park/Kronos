export type ProgramLaneId = 'platform' | 'rl-evidence' | 'engineering' | 'governance' | 'live';
export type ProgramState = 'STRONG' | 'PARTIAL' | 'BLOCKED';
export type CapabilityState = 'AVAILABLE' | 'PARTIAL' | 'BLOCKED';
export type PagePriority = 'P0' | 'P1' | 'P2' | 'HOLD';
export type ProgramScoreCriterion = { readonly id: string; readonly points: number; readonly achieved: boolean; readonly evidence: string };
export type ProgramLane = { readonly id: ProgramLaneId; readonly label: string; readonly labelKo: string; readonly score: number; readonly weight: number; readonly state: ProgramState; readonly evidence: string; readonly nextAction: string };
export type ProgramPageRow = { readonly id: string; readonly group: string; readonly page: string; readonly purpose: string; readonly delivery: 'BUILT'; readonly evidenceState: string; readonly progress: number; readonly priority: PagePriority; readonly nextAction: string; readonly eta: string; readonly mergeGate: string };
export type ProgramCapability = { readonly id: string; readonly capability: string; readonly state: CapabilityState; readonly boundary: string };

export const PROGRAM_SCORE_RUBRIC: Readonly<Record<ProgramLaneId, readonly ProgramScoreCriterion[]>> = {
  platform: [
    { id: 'twelve-pages', points: 20, achieved: true, evidence: 'V6 사용자 페이지 12개' },
    { id: 'd4-api', points: 20, achieved: true, evidence: 'D4 읽기 전용 API와 tamper 차단' },
    { id: 'reviewed-snapshot', points: 20, achieved: true, evidence: '24-model custody snapshot' },
    { id: 'global-research-ux', points: 18, achieved: true, evidence: '전 페이지 train-only/OOS 경계' },
    { id: 'evidence-viewer', points: 20, achieved: true, evidence: '알고리즘·비용·control·split 조회' },
    { id: 'broker-operations', points: 2, achieved: false, evidence: '브로커 운영 UI 범위 밖' },
  ],
  'rl-evidence': [
    { id: 'real-rl-models', points: 20, achieved: true, evidence: 'D4 실제 RL 모델 18개와 진단 모델 6개' },
    { id: 'negative-control', points: 18, achieved: true, evidence: 'NATIVE 대 SHUFFLED, 3 seeds' },
    { id: 'algorithm-ablation', points: 15, achieved: true, evidence: 'PPO·DQN·auxiliary PPO 비교' },
    { id: 'supervised-ceiling', points: 12, achieved: true, evidence: '비-RL supervised 상한 분리' },
    { id: 'cost-diagnostic', points: 12, achieved: true, evidence: '0bp 학습과 23bp 진단' },
    { id: 'confirmed-rl-arm', points: 15, achieved: true, evidence: 'DQN native 2/3·shuffled 2/3 seed train-only gate 통과' },
    { id: 'fresh-oos', points: 8, achieved: false, evidence: 'NOT_RUN_NO_READ' },
  ],
  engineering: [
    { id: 'held-inputs', points: 20, achieved: true, evidence: 'held input hash 검증' },
    { id: 'atomic-artifacts', points: 20, achieved: true, evidence: '원자적 summary·outcome·receipt 발행' },
    { id: 'terminalization', points: 15, achieved: true, evidence: '실패·완료 terminal receipt' },
    { id: 'matrix-identity', points: 15, achieved: true, evidence: '고유 24-unit matrix' },
    { id: 'tests-build', points: 15, achieved: true, evidence: 'Python·Svelte 검증' },
    { id: 'signed-approval', points: 12, achieved: true, evidence: 'Smoke HMAC 승인' },
    { id: 'cross-process-resume', points: 3, achieved: false, evidence: '자동 cross-process resume 미구현' },
  ],
  governance: [
    { id: 'prereg-first', points: 25, achieved: true, evidence: '실행 전 prereg commit' },
    { id: 'custody', points: 20, achieved: true, evidence: 'commit·tree·artifact SHA' },
    { id: 'failure-honesty', points: 15, achieved: true, evidence: '실패 run 및 한계 공개' },
    { id: 'controls', points: 15, achieved: true, evidence: 'shuffle control·3 seeds' },
    { id: 'claim-separation', points: 17, achieved: true, evidence: 'RULE·supervised·RL 라벨 분리' },
    { id: 'd4-release-lineage', points: 8, achieved: true, evidence: 'D4 research PR #15·master integration·v1.14 tag' },
  ],
  live: [
    { id: 'fresh-oos-pass', points: 30, achieved: false, evidence: 'Fresh OOS 미실행' },
    { id: 'paper-gate', points: 20, achieved: false, evidence: 'paper gate 잠금' },
    { id: 'broker', points: 30, achieved: false, evidence: '브로커 권한 없음' },
    { id: 'risk-operations', points: 20, achieved: false, evidence: '운영 리스크 체계 없음' },
  ],
};

export function programRubricScore(laneId: ProgramLaneId): number { return PROGRAM_SCORE_RUBRIC[laneId].reduce((sum, item) => sum + (item.achieved ? item.points : 0), 0); }

export const PROGRAM_LANES = [
  { id: 'platform', label: 'Platform', labelKo: '플랫폼', score: programRubricScore('platform'), weight: 30, state: 'STRONG', evidence: '12개 페이지, D4 API, 24-unit reviewed snapshot', nextAction: 'D5 결과도 동일 custody 흐름으로 연결' },
  { id: 'rl-evidence', label: 'RL Evidence', labelKo: '강화학습 증거', score: programRubricScore('rl-evidence'), weight: 30, state: 'STRONG', evidence: 'DQN native 2/3·shuffled 2/3 seed train-only gate 통과; PPO 계열 실패', nextAction: 'D5 full-train 비용·control 사전등록' },
  { id: 'engineering', label: 'Engineering', labelKo: '엔지니어링', score: programRubricScore('engineering'), weight: 20, state: 'STRONG', evidence: '24/24 실행, HMAC 승인, 실패 receipt, 모델·outcome 보존', nextAction: 'cross-process resume 자동화' },
  { id: 'governance', label: 'Governance', labelKo: '개발 거버넌스', score: programRubricScore('governance'), weight: 10, state: 'STRONG', evidence: 'prereg 우선, immutable run, custody, research→master→tag 계보', nextAction: 'D5도 동일 계보 유지' },
  { id: 'live', label: 'Live Readiness', labelKo: '라이브 준비도', score: programRubricScore('live'), weight: 10, state: 'BLOCKED', evidence: 'train-only 연구; Fresh OOS 봉인; 브로커 권한 없음', nextAction: 'D5~D7 gate 전 진행 금지' },
] as const satisfies readonly ProgramLane[];

export const PROGRAM_PAGE_MATRIX = [
  { id: 'home', group: 'COMMAND', page: 'Home', purpose: '전체 연구 상태와 안전 경계', delivery: 'BUILT', evidenceState: 'D4_TRAIN_ONLY_VISIBLE', progress: 100, priority: 'P1', nextAction: 'D5 질문 연결', eta: '완료', mergeGate: '판정·증거 일치' },
  { id: 'scorecard', group: 'COMMAND', page: 'Program Scorecard', purpose: '점수와 페이지 감사', delivery: 'BUILT', evidenceState: 'D4_AUDITED_86', progress: 100, priority: 'P1', nextAction: 'release 계보 반영', eta: '완료', mergeGate: '가중치 100%' },
  { id: 'rl-discovery', group: 'RL', page: 'Discovery Lab', purpose: 'D0~D7 질문과 arm 귀속성', delivery: 'BUILT', evidenceState: 'D4_PRIMARY_24_OF_24', progress: 100, priority: 'P0', nextAction: 'D5 full-train', eta: '완료', mergeGate: '24/24+receipt+control' },
  { id: 'rl-data', group: 'RL', page: 'Data', purpose: 'split·비용·Fresh OOS 경계', delivery: 'BUILT', evidenceState: 'TOP5_CONTEXT_128_BOUND', progress: 98, priority: 'P0', nextAction: 'D5 입력 동결', eta: '1~2시간', mergeGate: 'input SHA 고정' },
  { id: 'rl-experiment', group: 'RL', page: 'Experiment', purpose: '가설·arm·seed·gate 사전등록', delivery: 'BUILT', evidenceState: 'D4_PREREG_COMPLETE', progress: 100, priority: 'P0', nextAction: 'D5 prereg', eta: '2~4시간', mergeGate: '실행 전 SHA 고정' },
  { id: 'rl-training', group: 'RL', page: 'Training', purpose: '학습·모델·resume 상태', delivery: 'BUILT', evidenceState: 'D4_PRIMARY_COMPLETE', progress: 100, priority: 'P1', nextAction: 'D5 Smoke→Primary', eta: '4~8시간', mergeGate: 'algorithm·reward·seed 보존' },
  { id: 'rl-evaluation', group: 'RL', page: 'Evaluation', purpose: '비용·상한·negative control', delivery: 'BUILT', evidenceState: 'D4_DQN_CONFIRMED_TRAIN_ONLY', progress: 100, priority: 'P0', nextAction: '비용 포함 재현', eta: '3~6시간', mergeGate: 'fit/native/23bp 분리' },
  { id: 'rl-compare', group: 'RL', page: 'Compare', purpose: '알고리즘·control 비교', delivery: 'BUILT', evidenceState: 'D4_FOUR_ARM_COMPARED', progress: 100, priority: 'P1', nextAction: 'DQN 비용 ablation', eta: '2~4시간', mergeGate: 'supervised와 RL 분리' },
  { id: 'rl-report', group: 'RL', page: 'Report', purpose: '판정·artifact·거버넌스', delivery: 'BUILT', evidenceState: 'D4_PRIMARY_RECEIPT', progress: 100, priority: 'P1', nextAction: 'D5 문서 연결', eta: '완료', mergeGate: 'SHA·24 outcomes·한계' },
  { id: 'insights', group: 'RESEARCH', page: 'Insights', purpose: '종목·수급·시장 국면 관찰', delivery: 'BUILT', evidenceState: 'OBSERVATION_ONLY', progress: 76, priority: 'P2', nextAction: '정책 입력 경계 강화', eta: '30~60분', mergeGate: 'alpha 주장 없음' },
  { id: 'lanes', group: 'PLATFORM', page: 'Other Lanes', purpose: '인트라데이·Kronos 보조 연구', delivery: 'BUILT', evidenceState: 'INELIGIBLE_FOR_RL_RANK', progress: 73, priority: 'P2', nextAction: 'D4 점수 제외 유지', eta: '30분', mergeGate: 'RL 성과 합산 금지' },
  { id: 'settings', group: 'ADVANCED', page: 'Settings', purpose: '테마·화면·로컬 연구 환경', delivery: 'BUILT', evidenceState: 'LOCAL_ONLY', progress: 84, priority: 'HOLD', nextAction: '실행 권한 추가 보류', eta: '15분', mergeGate: '읽기 전용 경계' },
] as const satisfies readonly ProgramPageRow[];

export const PROGRAM_CAPABILITIES = [
  { id: 'd0-d3-history', capability: 'D0~D3 검토 증거 조회', state: 'AVAILABLE', boundary: '기존 판정은 변경하지 않음' },
  { id: 'd4-primary', capability: 'D4 4-algorithm × 2-reward × 3-seed', state: 'AVAILABLE', boundary: 'DQN train-only 확인; 수익성 근거 아님' },
  { id: 'artifact-audit', capability: 'prereg·receipt·custody 감사', state: 'AVAILABLE', boundary: '로컬 연구 evidence' },
  { id: 'd5-d6', capability: 'D5~D6 연구 사다리', state: 'PARTIAL', boundary: 'full train·cost·reused validation 별도 prereg 필요' },
  { id: 'fresh-oos', capability: 'Fresh OOS 조회', state: 'BLOCKED', boundary: 'NOT_RUN_NO_READ' },
  { id: 'live-trading', capability: '브로커 주문·라이브 운영', state: 'BLOCKED', boundary: '권한·검증·운영체계 없음' },
] as const satisfies readonly ProgramCapability[];

export function programOverallScore(lanes: readonly ProgramLane[]): number { return Math.round(lanes.reduce((sum, lane) => sum + lane.score * lane.weight / 100, 0)); }
