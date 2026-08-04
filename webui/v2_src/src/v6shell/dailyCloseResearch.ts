export type DailyCloseGateState = 'COMPLETE' | 'DIAGNOSTIC_PASS' | 'BLOCKED' | 'LOCKED';

export interface DailyCloseGate {
  readonly id: string;
  readonly label: string;
  readonly purpose: string;
  readonly state: DailyCloseGateState;
  readonly score: number;
  readonly maximumScore: number;
  readonly result: string;
}

export const DAILY_CLOSE_RESEARCH = {
  reviewedAt: '2026-08-04 KST',
  version: 'v1.27.0-dev',
  targetModel: '국내 개별주식 일봉 종가 의사결정 · 6천만원 · 최대 10종목',
  overallVerdict: 'IMPLEMENTED_CALIBRATED_NO_GO_DATA_CUSTODY',
  modelScope: 'SYNTHETIC_CALIBRATION_ONLY',
  economicModelCreated: false,
  freshOosState: 'NOT_RUN_NO_READ',
  accounting: { initialNavKrw: 60_000_000, maximumExposureKrw: 50_000_000, reserveKrw: 10_000_000, maximumSlots: 10 },
  costs: { stockKrxRoundTripPercent: 0.23, stockNxtRoundTripPercent: 0.229, equityEtfKrxRoundTripPercent: 0.03 },
  signalFloor: {
    evidenceScope: 'DIAGNOSTIC_ONLY_UNVERIFIED_CUSTODY', sampleCount: 131_838, dateCount: 10_462,
    netMeanPercent: 0.7573967543, shuffleMeanPercent: 0.2334738008, nativeMinusShufflePercent: 0.5239229535,
    positiveFolds: 4, foldCount: 4,
  },
  calibration: {
    verdict: 'PASS_SYNTHETIC_OFFLINE_RL', cqlIqmReturn: 0.1195133333,
    shuffledCqlIqmReturn: -0.00524, randomPolicyIqmReturn: -0.0269466667, positiveSeeds: 3, seedCount: 3,
  },
  gates: [
    { id: 'G1', label: '비용 계약', purpose: '주식·ETF 비용 분리', state: 'COMPLETE', score: 15, maximumScore: 15, result: 'KRX 주식 왕복 0.230%' },
    { id: 'G2', label: '데이터 관리', purpose: 'PIT·가용시각·수정주가', state: 'BLOCKED', score: 0, maximumScore: 15, result: '5개 custody 증거 미확인' },
    { id: 'G3', label: '신호 바닥', purpose: '5·10·20일 시간순 검증', state: 'DIAGNOSTIC_PASS', score: 20, maximumScore: 20, result: '4/4 fold 양수, 진단 전용' },
    { id: 'G4', label: '포트폴리오 환경', purpose: '6천만원·정수주·10슬롯', state: 'COMPLETE', score: 15, maximumScore: 15, result: '회계 invariant 통과' },
    { id: 'G5', label: 'DQN·CQL', purpose: '오프라인 학습기 보정', state: 'COMPLETE', score: 20, maximumScore: 20, result: 'CQL 3/3 seed 양수' },
    { id: 'G6', label: '강건성', purpose: 'shuffle·IQM·bootstrap', state: 'COMPLETE', score: 5, maximumScore: 5, result: 'controls 분리 성공' },
    { id: 'G7', label: 'Fresh OOS', purpose: '봉인 검증', state: 'LOCKED', score: 0, maximumScore: 5, result: 'NOT_RUN_NO_READ' },
    { id: 'G8', label: 'Paper forward', purpose: '실시간 모의 관찰', state: 'LOCKED', score: 0, maximumScore: 5, result: 'G7 승인 후 가능' },
  ] as const satisfies readonly DailyCloseGate[],
  blockers: ['POINT_IN_TIME_UNIVERSE', 'AVAILABLE_AT_PROVEN', 'OFFICIAL_PRICE_IDENTITY', 'CORPORATE_ACTION_CONTRACT', 'IMMUTABLE_SOURCE_HASH'],
  nextAction: '시점별 종목군·가용시각·수정주가 정책·원천 해시를 등록한 뒤 같은 G3를 재실행합니다.',
} as const;

export function dailyCloseProgress(gates: readonly DailyCloseGate[]): number {
  return gates.reduce((total, gate) => total + gate.score, 0);
}

