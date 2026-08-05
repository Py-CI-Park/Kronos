import { v6CompatibilityTarget } from '$lib/routes';

export type V6PageStatus = 'BUILT' | 'NOT_BUILT';
export type V6PageGroup = 'COMMAND' | 'RESEARCH' | 'EVIDENCE' | 'GOVERNANCE' | 'ADVANCED';

export interface V6PageDef {
  readonly id: string;
  readonly label: string;
  readonly labelKo: string;
  readonly group: V6PageGroup;
  readonly step: number | null;
  readonly status: V6PageStatus;
  readonly description: string;
}

export interface V6Location {
  readonly tab: string;
  readonly step?: string;
  readonly sub?: string;
}

export interface V6StepDef {
  readonly id: string;
  readonly label: string;
  readonly labelKo: string;
  readonly statusKey: 'data' | 'experiment' | 'training' | 'evaluation' | 'compare' | 'report' | 'discovery';
}

export const V6_BRAND = {
  name: 'Kronos Reinforcement Learning',
  subtitle: 'Evidence-first Quant Research Command Center',
  version: 'v1.28.0-dev',
  updateDate: '2026-08-05',
} as const;

export const V6_NAV_GROUPS: readonly V6PageGroup[] = ['COMMAND', 'RESEARCH', 'EVIDENCE', 'GOVERNANCE', 'ADVANCED'];

export const V6_RL_STEPS: readonly V6StepDef[] = [
  { id: 'discovery', label: 'Discovery Lab', labelKo: 'RL 발견 실험실', statusKey: 'discovery' },
  { id: 'data', label: 'Data', labelKo: '데이터', statusKey: 'data' },
  { id: 'experiment', label: 'Experiment', labelKo: '실험 설계', statusKey: 'experiment' },
  { id: 'training', label: 'Training', labelKo: '학습', statusKey: 'training' },
  { id: 'evaluation', label: 'Evaluation', labelKo: '평가', statusKey: 'evaluation' },
  { id: 'compare', label: 'Compare', labelKo: '비교', statusKey: 'compare' },
  { id: 'report', label: 'Report', labelKo: '보고서', statusKey: 'report' },
];

export const V6_INSIGHT_SUBTABS = [
  { id: 'symbol', labelKo: '종목 관찰' },
  { id: 'flow', labelKo: '수급 흐름' },
  { id: 'regime', labelKo: '시장 국면' },
] as const;

export const V6_PAGES: readonly V6PageDef[] = [
  { id: 'command', label: 'Command Center', labelKo: '통합 현황', group: 'COMMAND', step: 1, status: 'BUILT', description: '현재 연구, 성과, 차단 사유와 다음 행동을 한 화면에서 확인합니다.' },
  { id: 'research', label: 'Research Library', labelKo: '연구 라이브러리', group: 'RESEARCH', step: 2, status: 'BUILT', description: '모든 experiment와 run을 같은 기준으로 찾고 추적합니다.' },
  { id: 'live', label: 'Live Training', labelKo: '실시간 학습', group: 'RESEARCH', step: 3, status: 'BUILT', description: '학습 진행, metric, event와 stale 상태를 확인합니다.' },
  { id: 'evaluation', label: 'Evaluation', labelKo: '평가·비교', group: 'RESEARCH', step: 4, status: 'BUILT', description: '비용 후 성과를 기준선, seed, fold와 비교합니다.' },
  { id: 'evidence', label: 'Data & Evidence', labelKo: '데이터·증거', group: 'EVIDENCE', step: null, status: 'BUILT', description: '데이터 범위, PIT, 가용시각, 원본 증거를 검토합니다.' },
  { id: 'models', label: 'Models & Artifacts', labelKo: '모델·산출물', group: 'EVIDENCE', step: null, status: 'BUILT', description: '모델, checkpoint, dataset과 artifact 계보를 확인합니다.' },
  { id: 'governance', label: 'Reports & Governance', labelKo: '보고서·거버넌스', group: 'GOVERNANCE', step: null, status: 'BUILT', description: '사전등록, 판정, 승인, Git 계보와 보고서를 확인합니다.' },
  { id: 'settings', label: 'Settings', labelKo: '설정', group: 'ADVANCED', step: null, status: 'BUILT', description: '표시 밀도, 단위, refresh와 접근성을 설정합니다.' },
];

const LEGACY_COMMAND_TABS = new Set(['overview', 'home', 'scorecard']);
const LEGACY_RESEARCH_TABS = new Set(['rl', 'discovery', 'data', 'experiment', 'lanes', 'intraday']);
const LEGACY_LIVE_TABS = new Set(['training', 'live-training']);
const LEGACY_EVALUATION_TABS = new Set(['evaluation', 'compare']);
const LEGACY_EVIDENCE_TABS = new Set(['insight', 'insight-symbol', 'insight-flow', 'insight-regime']);
const LEGACY_MODEL_TABS = new Set(['kronos']);
const LEGACY_GOVERNANCE_TABS = new Set(['report']);

function insightSubtab(tab: string): string | undefined {
  if (tab === 'insight-symbol') return 'symbol';
  if (tab === 'insight-flow') return 'flow';
  if (tab === 'insight-regime') return 'regime';
  return undefined;
}

function compatibilityLocation(tab: string | null, pathname: string): V6Location | null {
  const search = tab === null ? '' : `?tab=${encodeURIComponent(tab)}`;
  const target = v6CompatibilityTarget({ pathname, search });
  if (target === null) return null;
  const [targetTab = 'command', query = ''] = target.split('?', 2);
  const params = new URLSearchParams(query);
  const targetStep = params.get('step');
  if (targetStep === 'training') return { tab: 'live' };
  if (targetStep === 'evaluation' || targetStep === 'compare') return { tab: 'evaluation' };
  if (targetStep === 'report') return { tab: 'governance' };
  return resolveV6Location(targetTab, targetStep, params.get('sub'));
}

export function resolveV6Location(tab: string | null, step: string | null, sub: string | null, pathname = '/'): V6Location {
  if (tab !== null && LEGACY_COMMAND_TABS.has(tab)) return { tab: 'command' };
  if (tab !== null && LEGACY_LIVE_TABS.has(tab)) return { tab: 'live' };
  if (tab !== null && LEGACY_EVALUATION_TABS.has(tab)) return { tab: 'evaluation' };
  if (tab !== null && LEGACY_MODEL_TABS.has(tab)) return { tab: 'models' };
  if (tab !== null && LEGACY_GOVERNANCE_TABS.has(tab)) return { tab: 'governance' };
  if (tab !== null && LEGACY_EVIDENCE_TABS.has(tab)) {
    const resolvedSub = insightSubtab(tab) ?? (V6_INSIGHT_SUBTABS.some((item) => item.id === sub) ? sub ?? undefined : undefined);
    return { tab: 'evidence', ...(resolvedSub === undefined ? {} : { sub: resolvedSub }) };
  }
  if (tab !== null && LEGACY_RESEARCH_TABS.has(tab)) {
    const resolvedStep = V6_RL_STEPS.some((item) => item.id === step) ? step ?? undefined : undefined;
    return { tab: 'research', ...(resolvedStep === undefined ? {} : { step: resolvedStep }) };
  }
  if (tab === null || !V6_PAGES.some((page) => page.id === tab)) {
    const compatibility = compatibilityLocation(tab, pathname);
    return compatibility ?? { tab: 'command' };
  }
  return { tab, ...(step === null ? {} : { step }), ...(sub === null ? {} : { sub }) };
}

export function resolveV6Page(tab: string | null): V6PageDef {
  const location = resolveV6Location(tab, null, null);
  return V6_PAGES.find((page) => page.id === location.tab) ?? V6_PAGES[0];
}

export function v6PageUrl(id: string): string {
  const location = resolveV6Location(id, null, null);
  return location.tab === 'command' ? '/?ui=v6' : `/?ui=v6&tab=${encodeURIComponent(location.tab)}`;
}
