import type { ProgramPageRow } from './programTypes';

export const PROGRAM_PAGE_MATRIX = [
  { id: 'home', group: 'COMMAND', page: '홈', purpose: '전체 연구 판정과 다음 행동 확인', delivery: 'BUILT', evidenceState: 'DAILY_CLOSE_G1_G6_IMPLEMENTED_75', progress: 100, priority: 'P0', nextAction: 'G2 데이터 관리 증거 확보', eta: '화면 완료', mergeGate: '구현·경제·OOS 점수 분리 표시' },
  { id: 'scorecard', group: 'COMMAND', page: '프로그램 점수', purpose: '프로그램과 페이지별 성숙도 감사', delivery: 'BUILT', evidenceState: 'PROGRAM_63_IMPLEMENTATION_75_ECONOMIC_20', progress: 100, priority: 'P0', nextAction: '정적 스냅샷을 영수증 API로 교체', eta: 'API 1~2시간', mergeGate: '총점 계산식과 13개 상태 일치' },
  { id: 'rl-discovery', group: 'RL', page: 'RL 발견 실험실', purpose: '과거 실패와 G1~G6 가설 비교', delivery: 'BUILT', evidenceState: 'HISTORY_PRESERVED_DAILY_CLOSE_V2_ACTIVE', progress: 100, priority: 'P1', nextAction: '과거 D계열과 CQL 근거 혼합 금지', eta: '화면 완료', mergeGate: '규칙·지도학습·RL 분리' },
  { id: 'rl-data', group: 'RL', page: '데이터', purpose: 'PIT·가용시각·수정주가·원천 관리', delivery: 'BUILT', evidenceState: 'G2_BLOCKED_5_CUSTODY_GATES', progress: 100, priority: 'P0', nextAction: '날짜별 universe, available_at, 기업행사, source hash 등록', eta: '1~2일', mergeGate: '5개 관리 blocker 모두 PASS' },
  { id: 'rl-experiment', group: 'RL', page: '실험 설계', purpose: '자금·행동·보상·종료 조건 사전등록', delivery: 'BUILT', evidenceState: 'G1_G6_EXECUTED_G7_LOCKED', progress: 100, priority: 'P0', nextAction: 'G2 통과 후 시장 모델 amendment 동결', eta: '동결 후 1~2시간', mergeGate: 'Fresh OOS 자동 개봉 금지' },
  { id: 'rl-training', group: 'RL', page: '학습', purpose: '모델 범위·학습 진행·artifact 확인', delivery: 'BUILT', evidenceState: 'SYNTHETIC_CQL_CREATED_MARKET_MODEL_NOT_CREATED', progress: 100, priority: 'P1', nextAction: 'G2·G3 통과 전 실제 시장 모델 생성 금지', eta: '통과 후 3~6시간', mergeGate: '보정 모델을 경제 모델로 표시 금지' },
  { id: 'rl-evaluation', group: 'RL', page: '평가', purpose: 'fold·seed·비용·통제군 경제성 검증', delivery: 'BUILT', evidenceState: 'G3_DIAGNOSTIC_PASS_4_OF_4_UNVERIFIED_CUSTODY', progress: 100, priority: 'P0', nextAction: '같은 코드를 PIT 데이터에서 재실행', eta: 'G2 후 2~4시간', mergeGate: '+0.7574%를 수익 증명으로 오해 금지' },
  { id: 'rl-compare', group: 'RL', page: '비교', purpose: 'DQN·CQL·shuffle·random 비교', delivery: 'BUILT', evidenceState: 'CQL_IQM_0_1195_SHUFFLED_NEG_0_00524', progress: 100, priority: 'P1', nextAction: '시장 모델에도 같은 negative control 적용', eta: '시장 모델과 동시', mergeGate: '통제군 없는 seed 채택 금지' },
  { id: 'rl-report', group: 'RL', page: '보고서', purpose: '판정·artifact·계보·다음 행동 전달', delivery: 'BUILT', evidenceState: 'IMPLEMENTED_CALIBRATED_NO_GO_DATA_CUSTODY', progress: 100, priority: 'P1', nextAction: '문서와 JSON receipt의 판정 동기화', eta: '화면 완료', mergeGate: 'Fresh OOS NOT_RUN_NO_READ 유지' },
  { id: 'insights', group: 'RESEARCH', page: '인사이트', purpose: '종목·수급·시장 국면 관찰', delivery: 'BUILT', evidenceState: 'CURRENT_UNIVERSE_DIAGNOSTIC_NOT_PIT', progress: 100, priority: 'P1', nextAction: 'PIT top-20 전까지 추천 표현 금지', eta: 'G2와 동시', mergeGate: '관찰과 매매 의사결정 분리' },
  { id: 'lanes', group: 'PLATFORM', page: '다른 레인', purpose: '인트라데이와 과거 연구 증거 보존', delivery: 'BUILT', evidenceState: 'SEPARATE_LANES_NO_CLAIM_TRANSFER', progress: 100, priority: 'P2', nextAction: '레인 간 성과 전이를 금지하고 독립 증거를 유지한다', eta: '화면 완료', mergeGate: '과거 NO-GO 유지' },
  { id: 'kronos', group: 'PLATFORM', page: 'Kronos 모델', purpose: '예측 모델과 RL 정책 경계 관리', delivery: 'BUILT', evidenceState: 'AVAILABLE_NOT_LOADED_NOT_RL_POLICY', progress: 100, priority: 'P2', nextAction: 'embedding은 별도 사전등록 전 아이디어로만 유지', eta: '별도 연구 1~2일', mergeGate: 'Kronos 출력을 RL 수익으로 귀속 금지' },
  { id: 'settings', group: 'ADVANCED', page: '설정', purpose: '표시·증거·안전 경계 확인', delivery: 'BUILT', evidenceState: 'READ_ONLY_ARTIFACT_ROOT_VISIBLE', progress: 100, priority: 'P2', nextAction: '표시 설정만 허용', eta: '화면 완료', mergeGate: '읽기 전용·무주문 경계 유지' },
] as const satisfies readonly ProgramPageRow[];

export function programPageById(id: string): ProgramPageRow | undefined {
  return PROGRAM_PAGE_MATRIX.find((page) => page.id === id);
}
