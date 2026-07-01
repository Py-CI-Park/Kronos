import type { CommandCard, ExperimentPreset, JsonValue } from './tradingTypes';

export const D9_RESEARCH_GATE_LABEL = '연구 검토 / NO-GO 게이트';

export const REQUIRED_CARD_ORDER = [
  'selected_run_verdict',
  'cost_baseline_delta_23bp',
  'drawdown',
  'trade_count_turnover',
  'job_progress',
  'd0_d9_gate_status',
];

export const STATUS_LOCK_ORDER = ['live', 'broker', 'order', 'account', 'paper', 'model', 'profit'];

export const NAV_ITEMS = [
  ['연구 홈', 'NO-GO 판정'],
  ['실험 설정', '연구 전용'],
  ['연구 큐', '의도 기록'],
  ['결과 비교', '차트'],
  ['증거 감사', '증거 묶음'],
  ['사용 가이드', '잠금 유지'],
] as const;

export const EXPERIMENT_PRESETS: ExperimentPreset[] = [
  {
    id: 'ts_imb_rule_baseline',
    nameKo: 'ts_imb 룰 기준선',
    nameEn: 'RULE baseline',
    description: '현재 메인 기준선입니다. 강화학습 모델이 아니라 비교 기준입니다.',
    status: 'MAINLINE_RULE',
    safeAction: '증거 비교만 가능',
  },
  {
    id: 'dqn_ppo_research_compare',
    nameKo: 'DQN/PPO 연구 비교',
    nameEn: 'RL experiment',
    description: '실패/반증 포함 연구 산출물만 검토합니다. 수익성·실거래 판정이 아닙니다.',
    status: 'RESEARCH_ONLY',
    safeAction: '연구 의도 기록',
  },
  {
    id: 'orderbook_falsification',
    nameKo: '호가창 RL 반증 실험',
    nameEn: 'Orderbook falsification',
    description: 'market_buy/market_exit 같은 행동 설계를 확인하는 격리 실험입니다.',
    status: 'NO_GO_REVIEW',
    safeAction: '결과 시각화 검토',
  },
];

export const CARD_COPY: Record<string, { title: string; help: string }> = {
  selected_run_verdict: { title: '선택 산출물 판정', help: 'GO/NO-GO와 연구 전용 여부를 먼저 확인합니다.' },
  cost_baseline_delta_23bp: { title: '23bp 비용·기준선 차이', help: '23bp 비용과 ts_imb 룰 기준선 대비 차이를 봅니다.' },
  drawdown: { title: '최대 낙폭', help: '신선한 drawdown 증거가 없으면 통과하지 않습니다.' },
  trade_count_turnover: { title: '거래 수·회전율', help: '표본 수와 과도한 회전율을 같이 봅니다.' },
  job_progress: { title: '연구 의도 진행', help: '이 화면에서는 연구 의도만 기록하고 실제 주문/학습 실행은 열지 않습니다.' },
  d0_d9_gate_status: { title: 'D0-D9 증거 게이트', help: '데이터부터 최종 연구 검토까지 빠진 증거를 확인합니다.' },
};

export const LOCK_COPY: Record<string, string> = {
  live: '실거래',
  broker: '브로커 연결',
  order: '주문 전송',
  account: '계좌 접근',
  paper: '페이퍼 트레이딩',
  model: '모델 빌드',
  profit: '수익 주장 경로',
};

export const STAGE_COPY: Record<string, string> = {
  D0: '데이터·증거 발견',
  D1: '룰 기준선 비교',
  D2: '23bp 비용 게이트',
  D3: '낙폭 검토',
  D4: '거래 수·회전율',
  D5: '음성/셔플 통제',
  D6: 'OOS 분리 검토',
  D7: '감사 증거 묶음',
  D8: '사람 연구 검토',
  D9: D9_RESEARCH_GATE_LABEL,
};

export const GLOSSARY = [
  ['ts_imb', '강화학습이 아니라 룰 기준선입니다. RL 후보는 이 기준선과 비용 반영 후 비교합니다.'],
  ['23bp', '기본 왕복 비용 가정입니다. 결과 차트와 판정에서 임의로 낮추지 않습니다.'],
  ['NO-GO', '실패를 숨기지 않고 보여주는 연구 판정입니다. 이 화면은 실거래 대상이 아닙니다.'],
  ['API 미연결', 'live/broker/order/account/profit 경로를 열지 않는 안전 잠금 상태입니다.'],
];

export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

export function hasString(value: Record<string, unknown>, key: string): boolean {
  return typeof value[key] === 'string';
}

export function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

export function stringifyValue(value: JsonValue): string {
  if (value == null || value === '') return '—';
  if (Array.isArray(value)) return value.map(stringifyValue).join(', ');
  if (typeof value === 'object') {
    return Object.entries(value)
      .map(([key, item]) => `${key}: ${stringifyValue(item)}`)
      .join(' · ');
  }
  return String(value);
}

export function statusLabel(status: string): string {
  const normalized = status.toUpperCase();
  if (normalized === 'API_UNAVAILABLE') return 'API 미연결(안전 잠금)';
  if (normalized === 'NO_GO') return 'NO-GO';
  if (normalized === 'NOT_STARTED') return '대기';
  if (normalized === 'STALE') return '오래됨';
  if (normalized === 'MISSING') return '증거 없음';
  if (normalized === 'MALFORMED') return '형식 문제';
  if (normalized === 'EMPTY') return '비어 있음';
  if (normalized === 'PATH_REJECTED') return '경로 차단';
  if (normalized === 'FRESH') return '신선함';
  if (normalized === 'VALID') return '스키마 통과';
  if (normalized === 'RECORDED_RESEARCH_INTENT') return '연구 의도 기록됨';
  return status.replaceAll('_', ' ');
}

export function compactCardValue(card: CommandCard): string {
  if (card.id === 'job_progress' && card.value && typeof card.value === 'object' && !Array.isArray(card.value)) {
    const value = card.value as Record<string, JsonValue>;
    return `기록 ${stringifyValue(value.recorded_intent_count)} · 실행 ${stringifyValue(value.active_job_count)} · ${statusLabel(stringifyValue(value.latest_status))}`;
  }
  if (card.id === 'trade_count_turnover' && card.value && typeof card.value === 'object' && !Array.isArray(card.value)) {
    const value = card.value as Record<string, JsonValue>;
    return `거래 ${stringifyValue(value.trade_count)} · 회전율 ${stringifyValue(value.turnover)}`;
  }
  return stringifyValue(card.value);
}

export function statusTone(status: string): string {
  const normalized = status.toUpperCase();
  if (normalized.includes('NO') || normalized.includes('MISSING') || normalized.includes('MALFORMED') || normalized.includes('UNAVAILABLE') || normalized.includes('REJECTED') || normalized.includes('EMPTY')) return 'danger';
  if (normalized.includes('STALE') || normalized.includes('NOT_STARTED')) return 'warn';
  return 'research';
}

export function evidenceScore(status: string): number {
  const normalized = status.toUpperCase();
  if (normalized.includes('FRESH') || normalized.includes('VALID')) return 86;
  if (normalized.includes('NO')) return 18;
  if (normalized.includes('MISSING')) return 24;
  if (normalized.includes('MALFORMED')) return 30;
  if (normalized.includes('EMPTY')) return 12;
  if (normalized.includes('STALE')) return 42;
  return 68;
}

export function splitSymbols(raw: string): string[] {
  return raw
    .split(',')
    .map((symbol) => symbol.trim())
    .filter(Boolean);
}
