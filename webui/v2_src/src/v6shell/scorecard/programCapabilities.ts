import type { ProgramCapability } from './programTypes';

export const PROGRAM_CAPABILITIES = [
  { id: 'history-evidence', capability: '과거 연구 증거 조회', state: 'AVAILABLE', boundary: '이전 NO-GO 판정을 변경하지 않음' },
  { id: 'daily-close-contracts', capability: '주식·ETF 비용과 종가 체결 계약', state: 'AVAILABLE', boundary: '주식 KRX 0.230%, ETF KRX 0.030%' },
  { id: 'portfolio-environment', capability: '6천만원·정수주·최대 10종목 환경', state: 'AVAILABLE', boundary: '주문 기능이 아닌 로컬 연구 환경' },
  { id: 'offline-cql-calibration', capability: 'DQN·CQL 합성 보정 모델', state: 'AVAILABLE', boundary: '3/3 seed, 시장 수익 모델 아님' },
  { id: 'robust-controls', capability: 'shuffle·random·IQM·bootstrap 검증', state: 'AVAILABLE', boundary: 'negative control 분리 확인' },
  { id: 'research-receipt', capability: 'G1~G6 통합 runner와 JSON receipt', state: 'AVAILABLE', boundary: '실패와 차단을 그대로 보존' },
  { id: 'all-page-control-room', capability: '13개 페이지 연구 결정 레일', state: 'AVAILABLE', boundary: '화면에서 GO를 생성할 수 없음' },
  { id: 'daily-close-foundation', capability: '일봉 종가매매 G1~G6 연구 기반', state: 'PARTIAL', boundary: '구현 78/100, G2 외부 권위 차단' },
  { id: 'diagnostic-signal', capability: '5·10·20일 지도학습 신호 바닥', state: 'PARTIAL', boundary: '4/4 fold지만 관리 미검증 진단용' },
  { id: 'insight-observation', capability: '종목·수급·시장 국면 관찰', state: 'PARTIAL', boundary: '현재 universe 관찰이며 매수 추천 아님' },
  { id: 'kronos-model', capability: 'Kronos foundation 모델 상태 조회', state: 'PARTIAL', boundary: 'AVAILABLE_NOT_LOADED, RL 정책 아님' },
  { id: 'point-in-time-custody', capability: 'PIT universe·available_at·수정주가·source hash', state: 'BLOCKED', boundary: '원천 SHA 통과, 외부 권위 4개 미확보' },
  { id: 'economic-market-model', capability: '실제 시장 6-action offline RL 모델', state: 'BLOCKED', boundary: 'G2 통과 전 생성 금지' },
  { id: 'fresh-oos', capability: 'G7 Fresh OOS', state: 'BLOCKED', boundary: 'NOT_RUN_NO_READ·별도 승인 필요' },
  { id: 'paper-forward', capability: 'G8 paper-forward', state: 'BLOCKED', boundary: 'G7 통과 후 가능' },
  { id: 'live-trading', capability: '브로커 주문·실거래 운영', state: 'BLOCKED', boundary: '권한·검증·위험 통제가 없음' },
] as const satisfies readonly ProgramCapability[];
