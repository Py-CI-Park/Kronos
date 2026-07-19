export type V6PageStatus = 'BUILT' | 'NOT_BUILT';

export interface V6PageDef {
  readonly id: string;
  readonly label: string;
  readonly labelKo: string;
  readonly group: 'COMMAND' | 'REINFORCEMENT LEARNING' | 'INSIGHT' | 'PLATFORM' | 'ADVANCED';
  readonly step: number | null;
  readonly status: V6PageStatus;
  readonly description: string;
}

export const V6_BRAND = {
  name: 'AI Quant Reinforcement Learning',
  subtitle: 'V6 Workflow Research Platform',
  version: 'v6.0-dev',
  updateDate: '2026-07-19',
} as const;

export const V6_PAGES: readonly V6PageDef[] = [
  { id: 'overview', label: 'Overview', labelKo: '개요', group: 'COMMAND', step: 1, status: 'BUILT', description: 'V6 연구 워크플로의 개요와 현재 구현 상태를 확인하는 화면입니다.' },
  { id: 'data', label: 'Data', labelKo: '데이터', group: 'REINFORCEMENT LEARNING', step: 2, status: 'BUILT', description: '강화학습 연구에 사용할 데이터 범위와 검증 상태를 다루는 화면입니다.' },
  { id: 'experiment', label: 'Experiment', labelKo: '실험 설계', group: 'REINFORCEMENT LEARNING', step: 3, status: 'BUILT', description: '실험 설계와 비교 조건을 명시하는 화면입니다.' },
  { id: 'training', label: 'Training', labelKo: '학습', group: 'REINFORCEMENT LEARNING', step: 4, status: 'BUILT', description: '학습 실행과 검증 경계를 다루는 화면입니다.' },
  { id: 'evaluation', label: 'Evaluation', labelKo: '평가', group: 'REINFORCEMENT LEARNING', step: 5, status: 'BUILT', description: '평가 기준과 실패 조건을 검토하는 화면입니다.' },
  { id: 'compare', label: 'Compare', labelKo: '비교', group: 'REINFORCEMENT LEARNING', step: 6, status: 'BUILT', description: '실험 결과 비교와 기준선 검토를 위한 화면입니다.' },
  { id: 'report', label: 'Report', labelKo: '보고서', group: 'REINFORCEMENT LEARNING', step: 7, status: 'NOT_BUILT', description: '연구 결과를 근거와 함께 보고하는 화면입니다.' },
  { id: 'insight-symbol', label: 'Symbol Drill-down', labelKo: '종목 심층', group: 'INSIGHT', step: null, status: 'NOT_BUILT', description: '개별 종목 연구 근거를 살펴보는 화면입니다.' },
  { id: 'insight-flow', label: 'Flow Ranking', labelKo: '수급 흐름', group: 'INSIGHT', step: null, status: 'NOT_BUILT', description: '수급 흐름 연구를 검토하는 화면입니다.' },
  { id: 'insight-regime', label: 'Market Regime', labelKo: '시장 국면', group: 'INSIGHT', step: null, status: 'NOT_BUILT', description: '시장 국면 연구를 검토하는 화면입니다.' },
  { id: 'intraday', label: 'Intraday RL', labelKo: '인트라데이 RL', group: 'PLATFORM', step: null, status: 'NOT_BUILT', description: '인트라데이 강화학습 연구를 위한 화면입니다.' },
  { id: 'kronos', label: 'Kronos Research', labelKo: 'Kronos 예측', group: 'PLATFORM', step: null, status: 'NOT_BUILT', description: 'Kronos 예측 연구를 검토하는 화면입니다.' },
  { id: 'settings', label: 'Settings', labelKo: '설정', group: 'ADVANCED', step: null, status: 'NOT_BUILT', description: 'V6 연구 환경 설정을 다루는 화면입니다.' },
];

export function resolveV6Page(tab: string | null): V6PageDef {
  return V6_PAGES.find((page) => page.id === tab) ?? V6_PAGES[0];
}

export function v6PageUrl(id: string): string {
  return id === 'overview' ? '/?ui=v6' : `/?ui=v6&tab=${encodeURIComponent(id)}`;
}
