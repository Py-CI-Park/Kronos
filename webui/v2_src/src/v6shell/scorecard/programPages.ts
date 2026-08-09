import type { ProgramPageRow } from './programTypes';

export const PROGRAM_PAGE_MATRIX = [
  { id: 'home', group: 'COMMAND', page: '통합 현황', purpose: '8개 공식 페이지의 판정과 다음 행동 확인', delivery: 'BUILT', evidenceState: 'UNIFIED_COMMAND_8_PAGES_PRODUCT_94', progress: 100, priority: 'P0', nextAction: '일봉 CQL NO-GO와 20개 체크포인트를 분리 확인', eta: '화면 완료', mergeGate: '구현·경제·OOS·live 점수 분리 표시' },
  { id: 'scorecard', group: 'COMMAND', page: '프로그램 점수', purpose: '연구 프로그램과 제품 구현 성숙도 분리 감사', delivery: 'BUILT', evidenceState: 'PROGRAM_71_IMPLEMENTATION_94_ECONOMIC_20_LIVE_0', progress: 100, priority: 'P0', nextAction: 'v1.29.0-dev 95점 계획과 증거 연결', eta: '개발 진행 중', mergeGate: '100점 rubric과 직접 검증 증거 일치' },
  { id: 'rl-discovery', group: 'RL', page: 'RL 발견 실험실', purpose: '과거 실패와 G1~G6 가설 비교', delivery: 'BUILT', evidenceState: 'HISTORY_PRESERVED_DAILY_CLOSE_V2_ACTIVE', progress: 100, priority: 'P1', nextAction: '과거 D계열과 CQL 근거 혼합 금지', eta: '화면 완료', mergeGate: '규칙·지도학습·RL 분리' },
  { id: 'rl-data', group: 'RL', page: '데이터', purpose: 'PIT·가용시각·수정주가·원천 관리', delivery: 'BUILT', evidenceState: 'G2_LOCAL_ANCHOR_19_STABLE_1_EXCLUDED_4_EXTERNAL_BLOCKERS', progress: 100, priority: 'P0', nextAction: 'KRX·OpenDART 키로 날짜별 universe, available_at, 공식 가격, 기업행사 등록', eta: '키 승인 후 1~2일', mergeGate: '5개 관리 gate 모두 PASS' },
  { id: 'rl-experiment', group: 'RL', page: '실험 설계', purpose: '자금·행동·보상·종료 조건 사전등록', delivery: 'BUILT', evidenceState: 'DAILY_MARKET_CQL_2026_08_09_001_PREREGISTERED_AND_EXECUTED', progress: 100, priority: 'P0', nextAction: '소비된 TEST에 맞추지 않고 새 가설 amendment 동결', eta: '다음 연구 1~2시간', mergeGate: 'Fresh OOS 자동 개봉 금지' },
  { id: 'rl-training', group: 'RL', page: '학습', purpose: '모델 범위·학습 진행·artifact 확인', delivery: 'BUILT', evidenceState: 'MARKET_DQN_CQL_20_CHECKPOINTS_CREATED_RESEARCH_ONLY', progress: 100, priority: 'P1', nextAction: '체크포인트 존재와 경제 모델 성공을 분리하고 모델 metadata 검토', eta: '현재 실행 완료', mergeGate: 'NO-GO 체크포인트를 경제 모델 GO로 표시 금지' },
  { id: 'rl-evaluation', group: 'RL', page: '평가', purpose: 'fold·seed·비용·통제군 경제성 검증', delivery: 'BUILT', evidenceState: 'MARKET_CQL_TEST_NO_GO_MEDIAN_NEG_10_19155', progress: 100, priority: 'P0', nextAction: '동일 TEST 재튜닝 금지·다중 시장국면 새 검증 구간 확보', eta: '데이터 확보 후 0.5~1일', mergeGate: 'seed-3 +3.22% 사후 선택 금지' },
  { id: 'rl-compare', group: 'RL', page: '비교', purpose: 'DQN·CQL·shuffle·random 비교', delivery: 'BUILT', evidenceState: 'NATIVE_CQL_BEATS_SHUFFLES_BUT_NO_TRADE_WINS', progress: 100, priority: 'P1', nextAction: '기대 edge 기반 abstention과 top-k 행동을 TRAIN/VAL에서만 설계', eta: '새 가설 0.5~1일', mergeGate: '통제군·5시드·비용 stress 유지' },
  { id: 'rl-report', group: 'RL', page: '보고서', purpose: '판정·artifact·계보·다음 행동 전달', delivery: 'BUILT', evidenceState: 'DAILY_MARKET_CQL_RESULT_DOCUMENTATION_IN_PROGRESS', progress: 100, priority: 'P1', nextAction: '5시드·gate·hash·실패 원인 결과 문서 연결', eta: '이번 단계 완료', mergeGate: 'Fresh OOS NOT_RUN_NO_READ 유지' },
  { id: 'insights', group: 'RESEARCH', page: '인사이트', purpose: '종목·수급·시장 국면 관찰', delivery: 'BUILT', evidenceState: 'CURRENT_UNIVERSE_DIAGNOSTIC_NOT_PIT', progress: 100, priority: 'P1', nextAction: 'PIT top-20 전까지 추천 표현 금지', eta: 'G2와 동시', mergeGate: '관찰과 매매 의사결정 분리' },
  { id: 'lanes', group: 'PLATFORM', page: '다른 레인', purpose: '인트라데이와 과거 연구 증거 보존', delivery: 'BUILT', evidenceState: 'SEPARATE_LANES_NO_CLAIM_TRANSFER', progress: 100, priority: 'P2', nextAction: '레인 간 성과 전이를 금지하고 독립 증거를 유지한다', eta: '화면 완료', mergeGate: '과거 NO-GO 유지' },
  { id: 'kronos', group: 'PLATFORM', page: 'Kronos 모델', purpose: '예측 모델과 RL 정책 경계 관리', delivery: 'BUILT', evidenceState: 'AVAILABLE_NOT_LOADED_NOT_RL_POLICY', progress: 100, priority: 'P2', nextAction: 'embedding은 별도 사전등록 전 아이디어로만 유지', eta: '별도 연구 1~2일', mergeGate: 'Kronos 출력을 RL 수익으로 귀속 금지' },
  { id: 'settings', group: 'ADVANCED', page: '설정', purpose: '표시·증거·안전 경계 확인', delivery: 'BUILT', evidenceState: 'READ_ONLY_ARTIFACT_ROOT_VISIBLE', progress: 100, priority: 'P2', nextAction: '표시 설정만 허용', eta: '화면 완료', mergeGate: '읽기 전용·무주문 경계 유지' },
] as const satisfies readonly ProgramPageRow[];

export function programPageById(id: string): ProgramPageRow | undefined {
  return PROGRAM_PAGE_MATRIX.find((page) => page.id === id);
}
