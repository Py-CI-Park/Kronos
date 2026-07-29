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

export type ProgramScoreCriterion = {
  readonly id: string;
  readonly points: number;
  readonly achieved: boolean;
  readonly evidence: string;
};

export const PROGRAM_SCORE_RUBRIC: Readonly<Record<ProgramLaneId, readonly ProgramScoreCriterion[]>> = {
  platform: [
    { id: 'twelve-pages', points: 25, achieved: true, evidence: '12개 V6 사용자 페이지' },
    { id: 'd3-api', points: 20, achieved: true, evidence: 'D3 API 및 tamper BLOCK' },
    { id: 'reviewed-snapshot', points: 20, achieved: true, evidence: '24-model custody snapshot' },
    { id: 'global-failure-ux', points: 17, achieved: true, evidence: '전 페이지 NO-GO/OOS 경계' },
    { id: 'evidence-viewer', points: 15, achieved: true, evidence: '비용·control·split 조회' },
    { id: 'broker-operations', points: 3, achieved: false, evidence: '브로커 운영 UI 범위 밖' },
  ],
  'rl-evidence': [
    { id: 'real-rl-models', points: 25, achieved: true, evidence: '실제 PPO 24/24 model ZIP' },
    { id: 'negative-control', points: 20, achieved: true, evidence: 'NATIVE 대 SHUFFLED 3-seed' },
    { id: 'representation-ablation', points: 15, achieved: true, evidence: '4개 policy arm' },
    { id: 'cost-diagnostic', points: 10, achieved: true, evidence: '0bp 학습·23bp 진단' },
    { id: 'preregistered-gates', points: 10, achieved: true, evidence: '실행 전 gate 고정' },
    { id: 'fresh-oos', points: 10, achieved: false, evidence: 'NOT_RUN_NO_READ' },
    { id: 'confirmed-arm', points: 10, achieved: false, evidence: '0/4 arm 통과' },
  ],
  engineering: [
    { id: 'held-inputs', points: 20, achieved: true, evidence: 'held-handle 입력 검증' },
    { id: 'atomic-artifacts', points: 20, achieved: true, evidence: 'atomic artifact 발행' },
    { id: 'terminalization', points: 15, achieved: true, evidence: '실패·중단 receipt' },
    { id: 'matrix-identity', points: 15, achieved: true, evidence: '고유 24-unit gate' },
    { id: 'tests-build', points: 15, achieved: true, evidence: '회귀검증·production build' },
    { id: 'signed-snapshot', points: 10, achieved: true, evidence: 'HMAC·held snapshot' },
    { id: 'cross-process-resume', points: 5, achieved: false, evidence: 'seed 자동 resume 미구현' },
  ],
  governance: [
    { id: 'prereg-first', points: 25, achieved: true, evidence: 'prereg commit 선행' },
    { id: 'custody', points: 20, achieved: true, evidence: 'commit/tree/artifact SHA' },
    { id: 'failure-honesty', points: 15, achieved: true, evidence: 'NO-GO·수익성 금지' },
    { id: 'controls', points: 15, achieved: true, evidence: 'shuffle control·3-seed' },
    { id: 'rule-rl-separation', points: 13, achieved: true, evidence: 'RULE과 RL 분리' },
    { id: 'd3-release-lineage', points: 12, achieved: false, evidence: 'D3 main PR·tag 완료 전' },
  ],
  live: [
    { id: 'fresh-oos-pass', points: 30, achieved: false, evidence: 'Fresh OOS 미실행' },
    { id: 'paper-gate', points: 20, achieved: false, evidence: 'paper/live 승격 금지' },
    { id: 'broker', points: 30, achieved: false, evidence: '브로커 권한 없음' },
    { id: 'risk-operations', points: 20, achieved: false, evidence: '운영 리스크 체계 없음' },
  ],
};

export function programRubricScore(laneId: ProgramLaneId): number {
  return PROGRAM_SCORE_RUBRIC[laneId].reduce(
    (total, criterion) => total + (criterion.achieved ? criterion.points : 0),
    0,
  );
}

export const PROGRAM_LANES = [
  { id: 'platform', label: 'Platform', labelKo: '플랫폼', score: programRubricScore('platform'), weight: 30, state: 'STRONG', evidence: 'V6 전체 페이지, D3 읽기 전용 API, 24-model reviewed snapshot과 terminal receipt', nextAction: 'D4 결과를 같은 evidence 흐름에 연결' },
  { id: 'rl-evidence', label: 'RL Evidence', labelKo: '강화학습 증거', score: programRubricScore('rl-evidence'), weight: 30, state: 'PARTIAL', evidence: 'D3 PPO 24/24 완료; top-5 context와 4× budget 개선; 0/4 arm gate 통과', nextAction: 'D4 algorithm/objective ablation 사전등록' },
  { id: 'engineering', label: 'Engineering', labelKo: '엔지니어링', score: programRubricScore('engineering'), weight: 20, state: 'STRONG', evidence: '438MB held streaming, custody hash, 2/6 action PPO, Smoke→Primary 승인, 중단 receipt', nextAction: 'D4 resume 단위를 policy/reward/seed까지 유지' },
  { id: 'governance', label: 'Governance', labelKo: '개발 거버넌스', score: programRubricScore('governance'), weight: 10, state: 'PARTIAL', evidence: '실행 전 prereg commit, immutable runs, shuffled control, research→master 계보', nextAction: 'D3 research tag와 master 통합 PR 검증' },
  { id: 'live', label: 'Live Readiness', labelKo: '라이브 준비도', score: programRubricScore('live'), weight: 10, state: 'BLOCKED', evidence: 'train-only 연구; Fresh OOS 봉인; 브로커 주문 권한 없음', nextAction: 'D4~D6 연구 gate 전에는 진행 금지' },
] as const satisfies readonly ProgramLane[];

export const PROGRAM_PAGE_MATRIX = [
  { id: 'home', group: 'COMMAND', page: 'Home', purpose: '전체 연구 상태와 안전 경계 요약', delivery: 'BUILT', evidenceState: 'D3_NO_GO_VISIBLE', progress: 100, priority: 'P1', nextAction: 'D4 질문과 Fresh OOS 봉인 연결', eta: '20분', mergeGate: '상태·판정·증거 일치' },
  { id: 'scorecard', group: 'COMMAND', page: 'Program Scorecard', purpose: '점수와 페이지 진행률 감사', delivery: 'BUILT', evidenceState: 'D3_AUDITED_81', progress: 100, priority: 'P1', nextAction: 'D4 완료 후 증거 기반 재채점', eta: '15분', mergeGate: '가중치 100%와 근거 명시' },
  { id: 'rl-discovery', group: 'RL', page: 'Discovery Lab', purpose: 'D0~D7 연구 질문과 arm 귀속성', delivery: 'BUILT', evidenceState: 'D3_PRIMARY_24_OF_24', progress: 100, priority: 'P0', nextAction: 'D4 algorithm/objective ablation', eta: '설계 2~4시간', mergeGate: '24/24 + terminal receipt + control' },
  { id: 'rl-data', group: 'RL', page: 'Data', purpose: '데이터 split·비용·Fresh OOS 경계', delivery: 'BUILT', evidenceState: 'TOP5_128_BOUND', progress: 97, priority: 'P0', nextAction: 'D4 입력 표현을 동일 episode로 고정', eta: '1~2시간', mergeGate: 'rows/normalizer/episode SHA 고정' },
  { id: 'rl-experiment', group: 'RL', page: 'Experiment', purpose: '가설·arm·seed·gate 사전등록', delivery: 'BUILT', evidenceState: 'D3_PREREG_COMPLETE', progress: 100, priority: 'P0', nextAction: 'D4 prereg 신규 작성', eta: '2~4시간', mergeGate: '실행 전 prereg SHA 고정' },
  { id: 'rl-training', group: 'RL', page: 'Training', purpose: '학습 진행·모델·resume 상태', delivery: 'BUILT', evidenceState: 'PRIMARY_COMPLETE', progress: 100, priority: 'P1', nextAction: 'D4 Smoke 후 조건부 Primary', eta: '실행 4~8시간', mergeGate: 'policy·reward·seed·model 보존' },
  { id: 'rl-evaluation', group: 'RL', page: 'Evaluation', purpose: '비용·baseline·negative control 평가', delivery: 'BUILT', evidenceState: 'D3_NO_GO_EXPLAINED', progress: 100, priority: 'P0', nextAction: 'PPO 목적함수·모델군 실패 원인 분리', eta: '3~6시간', mergeGate: 'fit/native/23bp를 분리 공개' },
  { id: 'rl-compare', group: 'RL', page: 'Compare', purpose: '정책·rule·shuffled control 비교', delivery: 'BUILT', evidenceState: 'D3_FOUR_ARM_COMPARED', progress: 100, priority: 'P1', nextAction: 'PPO·A2C·supervised ceiling 비교', eta: '2~4시간', mergeGate: 'RULE과 RL 라벨 분리' },
  { id: 'rl-report', group: 'RL', page: 'Report', purpose: '판정·artifact·거버넌스 보고', delivery: 'BUILT', evidenceState: 'D3_PRIMARY_RECEIPT', progress: 100, priority: 'P1', nextAction: 'D4 prereg와 결과 문서 연결', eta: '30~60분', mergeGate: 'SHA·24 outcomes·한계 포함' },
  { id: 'insights', group: 'RESEARCH', page: 'Insights', purpose: '종목·수급·시장 국면 관찰', delivery: 'BUILT', evidenceState: 'OBSERVATION_ONLY', progress: 74, priority: 'P2', nextAction: '정책 입력과 관찰 카드의 경계 강화', eta: '30~60분', mergeGate: 'alpha 주장 없음' },
  { id: 'lanes', group: 'PLATFORM', page: 'Other Lanes', purpose: '인트라데이·Kronos 보조 연구', delivery: 'BUILT', evidenceState: 'INELIGIBLE_FOR_RL_RANK', progress: 72, priority: 'P2', nextAction: 'D3 점수 제외 사유 유지', eta: '30분', mergeGate: 'RL 성과로 합산 금지' },
  { id: 'settings', group: 'ADVANCED', page: 'Settings', purpose: '테마·화면·로컬 연구 환경', delivery: 'BUILT', evidenceState: 'LOCAL_ONLY', progress: 82, priority: 'HOLD', nextAction: '실행 제어 권한 추가 보류', eta: '15분', mergeGate: '읽기 전용 경계 유지' },
] as const satisfies readonly ProgramPageRow[];

export const PROGRAM_CAPABILITIES = [
  { id: 'type1-review', capability: 'Type1 NO-GO 증거 조회', state: 'AVAILABLE', boundary: '기존 판정을 변경하지 않음' },
  { id: 'd0-smoke', capability: 'D0 4-arm Smoke·Primary 조회', state: 'AVAILABLE', boundary: 'PPO-only 귀속성 미확인' },
  { id: 'd1-primary', capability: 'D1 3-arm × 3-seed Primary', state: 'AVAILABLE', boundary: '합성 train-only 행동·보상 메커니즘 확인' },
  { id: 'd2-primary', capability: 'D2 실제 일봉 4-scale × 2-arm × 3-seed', state: 'AVAILABLE', boundary: '8 episodes까지만 PPO-only 과적합 확인; 수익성 근거 아님' },
  { id: 'd3-primary', capability: 'D3 실제 일봉 4-policy × 2-reward × 3-seed', state: 'AVAILABLE', boundary: '24/24 모델 완료; 4× 개선에도 0/4 arm gate 통과' },
  { id: 'artifact-audit', capability: 'prereg SHA·receipt·custody 감사', state: 'AVAILABLE', boundary: '로컬 연구 evidence' },
  { id: 'd4-d6', capability: 'D4~D6 연구 사다리', state: 'PARTIAL', boundary: 'algorithm/objective, cost, reused validation은 별도 사전등록 필요' },
  { id: 'fresh-oos', capability: 'Fresh OOS 조회', state: 'BLOCKED', boundary: 'NOT_RUN_NO_READ' },
  { id: 'live-trading', capability: '브로커 주문·라이브 운영', state: 'BLOCKED', boundary: '권한·검증·운영 준비 없음' },
] as const satisfies readonly ProgramCapability[];

export function programOverallScore(lanes: readonly ProgramLane[]): number {
  return Math.round(lanes.reduce((total, lane) => total + lane.score * lane.weight / 100, 0));
}
