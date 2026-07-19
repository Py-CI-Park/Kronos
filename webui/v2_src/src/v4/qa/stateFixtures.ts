/**
 * Canonical V4 all-tab QA fixtures: the 12 App.svelte tab ids crossed with the
 * 9 required lifecycle states, each carrying typed Korean-first fixture
 * metadata plus fail-closed validation helpers.
 *
 * This module is presentation-agnostic (no fetch, no DOM, no Svelte import)
 * so it can be exercised from plain node:test files and from
 * V4LegacyDomainFrame.svelte alike.
 */

/** Canonical 12 V4 tab ids, matching the route-to-tab mapping in src/App.svelte. */
export const V4_QA_TAB_IDS = [
  'mission-control',
  'live-training',
  'forecast',
  'stom',
  'rl',
  'daily-ohlcv',
  'daily-rl-guide',
  'artifacts',
  'history',
  'system-health',
  'settings',
  'docs',
] as const;

export type V4QaTabId = (typeof V4_QA_TAB_IDS)[number];

/** Required per-tab lifecycle states. Every canonical tab MUST declare all nine. */
export const V4_QA_STATE_IDS = [
  'loading',
  'empty',
  'error',
  'stale',
  'live',
  'replay',
  'completed',
  'missing',
  'no_go',
] as const;

export type V4QaStateId = (typeof V4_QA_STATE_IDS)[number];

/** The exact six false locks shared across every V4 domain frame surface. */
export const V4_QA_FALSE_LOCK_KEYS = [
  'promotion_allowed',
  'model_build_allowed',
  'paper_forward_allowed',
  'live_broker_order_allowed',
  'profitability_claim_allowed',
  'go_summary_allowed',
] as const;

export type V4QaFalseLockKey = (typeof V4_QA_FALSE_LOCK_KEYS)[number];

export type V4QaStateTone = 'neutral' | 'info' | 'positive' | 'warning' | 'danger';

const TAB_LABELS_KO: Record<V4QaTabId, string> = {
  'mission-control': '미션 컨트롤',
  'live-training': '실시간 학습',
  forecast: '예측 스튜디오',
  stom: 'STOM 진단',
  rl: '강화학습 트레이딩',
  'daily-ohlcv': '일간 OHLCV 리서치',
  'daily-rl-guide': '일간 RL 가이드',
  artifacts: '아티팩트 · 모델',
  history: '히스토리 · 실행',
  'system-health': '시스템 상태',
  settings: '설정',
  docs: '문서',
};

interface StateMeta {
  labelKo: string;
  tone: V4QaStateTone;
  blocking: boolean;
  claimsLive: boolean;
  detailTemplateKo: string;
  safetyNoteKo: string;
}

/** Phrases a `live` claim's safety note MUST contain to be accepted as safe. */
export const V4_QA_LIVE_SAFETY_PHRASES = ['수익성 주장 아님', '주문 실행 아님'] as const;

const RESEARCH_ONLY_NOTE_KO = '연구용 read-only 증거이며 숨겨진 증거나 승격 판단은 포함하지 않습니다.';
const LIVE_SAFETY_NOTE_KO = `${RESEARCH_ONLY_NOTE_KO} 실시간 관측이며 ${V4_QA_LIVE_SAFETY_PHRASES[0]}·${V4_QA_LIVE_SAFETY_PHRASES[1]}·관측 전용입니다.`;

const STATE_META: Record<V4QaStateId, StateMeta> = {
  loading: {
    labelKo: '로딩',
    tone: 'neutral',
    blocking: true,
    claimsLive: false,
    detailTemplateKo: '{tab} 증거를 불러오는 중이며 판단을 보류합니다.',
    safetyNoteKo: RESEARCH_ONLY_NOTE_KO,
  },
  empty: {
    labelKo: '비어 있음',
    tone: 'neutral',
    blocking: true,
    claimsLive: false,
    detailTemplateKo: '{tab}에 표시할 기록된 증거가 아직 없습니다.',
    safetyNoteKo: RESEARCH_ONLY_NOTE_KO,
  },
  error: {
    labelKo: '오류',
    tone: 'danger',
    blocking: true,
    claimsLive: false,
    detailTemplateKo: '{tab} 증거 로드 오류로 안전하게 잠금 상태로 표시합니다.',
    safetyNoteKo: RESEARCH_ONLY_NOTE_KO,
  },
  stale: {
    labelKo: '오래됨',
    tone: 'warning',
    blocking: true,
    claimsLive: false,
    detailTemplateKo: '{tab} 기록은 볼 수 있지만 최신 판단이나 GO 근거로 사용하지 않습니다.',
    safetyNoteKo: RESEARCH_ONLY_NOTE_KO,
  },
  live: {
    labelKo: '실시간',
    tone: 'info',
    blocking: false,
    claimsLive: true,
    detailTemplateKo: '{tab}은 명시적으로 live로 선언된 관측 화면입니다.',
    safetyNoteKo: LIVE_SAFETY_NOTE_KO,
  },
  replay: {
    labelKo: '리플레이',
    tone: 'info',
    blocking: false,
    claimsLive: false,
    detailTemplateKo: '{tab}은 기록된 실행을 재생 중이며 라이브 주문 증거가 아닙니다.',
    safetyNoteKo: RESEARCH_ONLY_NOTE_KO,
  },
  completed: {
    labelKo: '완료',
    tone: 'positive',
    blocking: false,
    claimsLive: false,
    detailTemplateKo: '{tab} 기록된 증거가 완료 상태이며 별도 잠금이 있으면 그 판단을 우선합니다.',
    safetyNoteKo: RESEARCH_ONLY_NOTE_KO,
  },
  missing: {
    labelKo: '누락',
    tone: 'danger',
    blocking: true,
    claimsLive: false,
    detailTemplateKo: '{tab} 필수 증거가 누락되어 GO로 표시하지 않습니다.',
    safetyNoteKo: RESEARCH_ONLY_NOTE_KO,
  },
  no_go: {
    labelKo: 'NO-GO',
    tone: 'danger',
    blocking: true,
    claimsLive: false,
    detailTemplateKo: '{tab} 기록된 판단이 승격 또는 실행을 허용하지 않습니다.',
    safetyNoteKo: RESEARCH_ONLY_NOTE_KO,
  },
};

export interface V4QaStateFixture {
  tabId: V4QaTabId;
  stateId: V4QaStateId;
  tabLabelKo: string;
  stateLabelKo: string;
  tone: V4QaStateTone;
  blocking: boolean;
  detailKo: string;
  evidenceLabel: string;
  optimisticLock: boolean;
  claimsLive: boolean;
  claimsProfit: boolean;
  claimsOrder: boolean;
  safetyNoteKo: string;
}

function buildFixture(tabId: V4QaTabId, stateId: V4QaStateId): V4QaStateFixture {
  const tabLabelKo = TAB_LABELS_KO[tabId];
  const meta = STATE_META[stateId];
  return {
    tabId,
    stateId,
    tabLabelKo,
    stateLabelKo: meta.labelKo,
    tone: meta.tone,
    blocking: meta.blocking,
    detailKo: meta.detailTemplateKo.replace('{tab}', tabLabelKo),
    evidenceLabel: `${tabId}:${stateId}:evidence`,
    optimisticLock: false,
    claimsLive: meta.claimsLive,
    claimsProfit: false,
    claimsOrder: false,
    safetyNoteKo: meta.safetyNoteKo,
  };
}

/** Canonical, valid 12x9 = 108 fixture matrix. Passes {@link validateFixtureSet}. */
export const V4_QA_STATE_FIXTURES: readonly V4QaStateFixture[] = V4_QA_TAB_IDS.flatMap((tabId) =>
  V4_QA_STATE_IDS.map((stateId) => buildFixture(tabId, stateId)),
);

export interface V4QaStateLegendEntry {
  stateId: V4QaStateId;
  labelKo: string;
  tone: V4QaStateTone;
  blocking: boolean;
  safetyNoteKo: string;
}

/** Tab-agnostic 9-row state legend for rendering in domain frames. */
export const V4_QA_STATE_LEGEND: readonly V4QaStateLegendEntry[] = V4_QA_STATE_IDS.map((stateId) => ({
  stateId,
  labelKo: STATE_META[stateId].labelKo,
  tone: STATE_META[stateId].tone,
  blocking: STATE_META[stateId].blocking,
  safetyNoteKo: STATE_META[stateId].safetyNoteKo,
}));

export const V4_QA_REQUIRED_TAB_COUNT = V4_QA_TAB_IDS.length;
export const V4_QA_REQUIRED_STATE_COUNT = V4_QA_STATE_IDS.length;
export const V4_QA_REQUIRED_FIXTURE_COUNT = V4_QA_REQUIRED_TAB_COUNT * V4_QA_REQUIRED_STATE_COUNT;

export type V4QaValidationIssueCode =
  | 'UNKNOWN_TAB_ID'
  | 'UNKNOWN_STATE_ID'
  | 'DUPLICATE_FIXTURE'
  | 'MISSING_STATE'
  | 'OPTIMISTIC_LOCK_REJECTED'
  | 'UNLABELLED_EVIDENCE'
  | 'UNSAFE_LIVE_CLAIM'
  | 'UNSAFE_PROFIT_CLAIM'
  | 'UNSAFE_ORDER_CLAIM';

export interface V4QaValidationIssue {
  code: V4QaValidationIssueCode;
  tabId?: string;
  stateId?: string;
  detail: string;
}

export interface V4QaValidationResult {
  ok: boolean;
  issues: V4QaValidationIssue[];
  fixtureCount: number;
}

const TAB_ID_SET = new Set<string>(V4_QA_TAB_IDS);
const STATE_ID_SET = new Set<string>(V4_QA_STATE_IDS);

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim() !== '';
}

/**
 * Validate an arbitrary fixture list in strict fail-closed mode. Rejects:
 * missing states (every tab must declare all 9), duplicate tab/state ids,
 * optimistic locks (`optimisticLock: true`), unlabelled evidence (empty
 * `evidenceLabel`), and unsafe live/profit/order claims.
 */
export function validateFixtureSet(fixtures: readonly V4QaStateFixture[]): V4QaValidationResult {
  const issues: V4QaValidationIssue[] = [];
  const seen = new Set<string>();
  const seenByTab = new Map<V4QaTabId, Set<V4QaStateId>>();

  for (const fixture of fixtures) {
    const tabKnown = TAB_ID_SET.has(fixture.tabId);
    const stateKnown = STATE_ID_SET.has(fixture.stateId);
    if (!tabKnown) {
      issues.push({ code: 'UNKNOWN_TAB_ID', tabId: fixture.tabId, detail: `unknown tab id: ${fixture.tabId}` });
    }
    if (!stateKnown) {
      issues.push({ code: 'UNKNOWN_STATE_ID', stateId: fixture.stateId, detail: `unknown state id: ${fixture.stateId}` });
    }
    if (!tabKnown || !stateKnown) {
      continue;
    }

    const key = `${fixture.tabId}::${fixture.stateId}`;
    if (seen.has(key)) {
      issues.push({
        code: 'DUPLICATE_FIXTURE',
        tabId: fixture.tabId,
        stateId: fixture.stateId,
        detail: `duplicate fixture for ${key}`,
      });
    }
    seen.add(key);

    const perTab = seenByTab.get(fixture.tabId) ?? new Set<V4QaStateId>();
    perTab.add(fixture.stateId);
    seenByTab.set(fixture.tabId, perTab);

    if (fixture.optimisticLock === true) {
      issues.push({
        code: 'OPTIMISTIC_LOCK_REJECTED',
        tabId: fixture.tabId,
        stateId: fixture.stateId,
        detail: `${key} declares an optimistic lock; locks must always fail closed`,
      });
    }

    if (!isNonEmptyString(fixture.evidenceLabel)) {
      issues.push({
        code: 'UNLABELLED_EVIDENCE',
        tabId: fixture.tabId,
        stateId: fixture.stateId,
        detail: `${key} is missing a labelled evidence source`,
      });
    }

    if (fixture.claimsProfit === true) {
      issues.push({
        code: 'UNSAFE_PROFIT_CLAIM',
        tabId: fixture.tabId,
        stateId: fixture.stateId,
        detail: `${key} makes a profitability claim, which is never safe in a research fixture`,
      });
    }

    if (fixture.claimsOrder === true) {
      issues.push({
        code: 'UNSAFE_ORDER_CLAIM',
        tabId: fixture.tabId,
        stateId: fixture.stateId,
        detail: `${key} makes a live order/broker claim, which is never safe in a research fixture`,
      });
    }

    if (fixture.claimsLive === true) {
      const hasSafetyNote =
        isNonEmptyString(fixture.safetyNoteKo) && V4_QA_LIVE_SAFETY_PHRASES.every((phrase) => fixture.safetyNoteKo.includes(phrase));
      if (fixture.stateId !== 'live' || !hasSafetyNote) {
        issues.push({
          code: 'UNSAFE_LIVE_CLAIM',
          tabId: fixture.tabId,
          stateId: fixture.stateId,
          detail: `${key} claims live without an explicit, labelled non-profit/non-order safety note`,
        });
      }
    }
  }

  for (const tabId of V4_QA_TAB_IDS) {
    const declared = seenByTab.get(tabId) ?? new Set<V4QaStateId>();
    for (const stateId of V4_QA_STATE_IDS) {
      if (!declared.has(stateId)) {
        issues.push({ code: 'MISSING_STATE', tabId, stateId, detail: `${tabId} is missing required state ${stateId}` });
      }
    }
  }

  return { ok: issues.length === 0, issues, fixtureCount: fixtures.length };
}

/**
 * Validate and return the fixture set, throwing a single aggregated error when
 * validation fails. Fail closed: callers MUST NOT render a fixture set that
 * did not pass validation.
 */
export function assertValidFixtureSet(fixtures: readonly V4QaStateFixture[] = V4_QA_STATE_FIXTURES): readonly V4QaStateFixture[] {
  const result = validateFixtureSet(fixtures);
  if (!result.ok) {
    const summary = result.issues.map((issue) => `[${issue.code}] ${issue.detail}`).join('; ');
    throw new Error(`V4 QA fixture validation failed (${result.issues.length} issue(s)): ${summary}`);
  }
  return fixtures;
}

export function getFixture(tabId: V4QaTabId, stateId: V4QaStateId): V4QaStateFixture {
  const found = V4_QA_STATE_FIXTURES.find((fixture) => fixture.tabId === tabId && fixture.stateId === stateId);
  if (!found) {
    throw new Error(`no canonical V4 QA fixture for ${tabId}::${stateId}`);
  }
  return found;
}
