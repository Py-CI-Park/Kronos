export const EVIDENCE_UI_STATES = [
  'loading',
  'empty',
  'error',
  'stale',
  'live',
  'replay',
  'completed',
  'missing',
  'no-go',
] as const;

export type EvidenceUiState = (typeof EVIDENCE_UI_STATES)[number];

export type EvidenceStateTone = 'neutral' | 'info' | 'positive' | 'warning' | 'danger';

export interface EvidenceStateMeta {
  state: EvidenceUiState;
  label: string;
  tone: EvidenceStateTone;
  blocking: boolean;
  showContent: boolean;
  title: string;
  detail: string;
  statusText: string;
}

const STATE_SET = new Set<string>(EVIDENCE_UI_STATES);
type StateRecord = Record<string, unknown>;

const STATE_OBJECT_KEYS = [
  'state',
  'lifecycleState',
  'status',
  'value',
  'lifecycle',
  'freshness_status',
  'run_status',
] as const;

function asStateRecord(value: unknown): StateRecord | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as StateRecord)
    : null;
}

function hasOwn(record: StateRecord, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(record, key);
}

function stateText(source: unknown, depth: number = 0, seen: Set<StateRecord> = new Set()): string | null {
  if (typeof source === 'string') {
    return source;
  }

  const record = asStateRecord(source);
  if (!record || depth >= 5 || seen.has(record)) {
    return null;
  }
  seen.add(record);

  for (const key of STATE_OBJECT_KEYS) {
    if (!hasOwn(record, key)) {
      continue;
    }
    const value = record[key];
    if (value === null || value === undefined) {
      continue;
    }
    return stateText(value, depth + 1, seen);
  }

  return null;
}

function normalizeEvidenceStateText(text: string): EvidenceUiState {
  if (STATE_SET.has(text)) {
    return text as EvidenceUiState;
  }

  const normalized = text.trim().toUpperCase().replace(/[\s-]+/g, '_');
  if (normalized === 'COMPLETED' || normalized === 'COMPLETE' || normalized === 'DONE') {
    return 'completed';
  }
  if (normalized === 'STALE' || normalized === 'EXPIRED') {
    return 'stale';
  }
  if (normalized === 'REPLAY' || normalized === 'REPLAYED') {
    return 'replay';
  }
  if (normalized === 'IDLE' || normalized === 'EMPTY') {
    return 'empty';
  }
  if (normalized === 'MISSING' || normalized === 'NOT_RUN') {
    return 'missing';
  }
  if (
    normalized === 'NO_GO' ||
    normalized === 'CONFLICT_BLOCKED' ||
    normalized === 'FAILED' ||
    normalized === 'STOPPED'
  ) {
    return 'no-go';
  }
  return 'missing';
}


const EVIDENCE_STATE_META: Record<EvidenceUiState, EvidenceStateMeta> = {
  loading: {
    state: 'loading',
    label: '로딩',
    tone: 'neutral',
    blocking: true,
    showContent: false,
    title: '증거를 불러오는 중',
    detail: '기록된 실행 증거를 확인하는 동안 판단을 보류합니다.',
    statusText: '로딩 · 판단 보류',
  },
  empty: {
    state: 'empty',
    label: '비어 있음',
    tone: 'neutral',
    blocking: true,
    showContent: false,
    title: '표시할 증거가 없음',
    detail: '이 화면에 필요한 기록된 증거가 아직 없습니다.',
    statusText: '비어 있음 · GO 아님',
  },
  error: {
    state: 'error',
    label: '오류',
    tone: 'danger',
    blocking: true,
    showContent: false,
    title: '증거 로드 오류',
    detail: '증거를 검증할 수 없어 안전하게 잠금 상태로 표시합니다.',
    statusText: '오류 · 잠금',
  },
  stale: {
    state: 'stale',
    label: '오래됨',
    tone: 'warning',
    blocking: true,
    showContent: true,
    title: '오래된 증거',
    detail: '기록은 볼 수 있지만 최신 판단이나 GO 근거로 사용하지 않습니다.',
    statusText: '오래됨 · 참고 전용',
  },
  live: {
    state: 'live',
    label: '실시간',
    tone: 'info',
    blocking: false,
    showContent: true,
    title: '실시간 관측',
    detail: '명시적으로 live로 선언된 관측 화면입니다. 수익성 주장이 아닙니다.',
    statusText: '실시간 · 관측 전용',
  },
  replay: {
    state: 'replay',
    label: '리플레이',
    tone: 'info',
    blocking: false,
    showContent: true,
    title: '리플레이 증거',
    detail: '기록된 실행을 재생 중입니다. 라이브 주문 증거가 아닙니다.',
    statusText: '리플레이 · 기록 재생',
  },
  completed: {
    state: 'completed',
    label: '완료',
    tone: 'positive',
    blocking: false,
    showContent: true,
    title: '완료된 증거',
    detail: '기록된 증거가 완료 상태입니다. 별도 잠금이 있으면 그 판단을 우선합니다.',
    statusText: '완료 · 기록됨',
  },
  missing: {
    state: 'missing',
    label: '누락',
    tone: 'danger',
    blocking: true,
    showContent: false,
    title: '증거 누락',
    detail: '필수 증거가 MISSING/NOT_RECORDED 상태이므로 GO로 표시하지 않습니다.',
    statusText: '누락 · 잠금',
  },
  'no-go': {
    state: 'no-go',
    label: 'NO-GO',
    tone: 'danger',
    blocking: true,
    showContent: true,
    title: 'NO-GO',
    detail: '기록된 판단이 승격 또는 실행을 허용하지 않습니다.',
    statusText: 'NO-GO · 잠금',
  },
};

export function normalizeEvidenceState(source: unknown): EvidenceUiState {
  const text = stateText(source);
  return text === null ? 'missing' : normalizeEvidenceStateText(text);
}

export function evidenceStateMeta(source: unknown): EvidenceStateMeta {
  return EVIDENCE_STATE_META[normalizeEvidenceState(source)];
}
