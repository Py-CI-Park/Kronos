import { v6CompatibilityTarget } from '$lib/routes';

export type V6PageStatus = 'BUILT' | 'NOT_BUILT';

export interface V6PageDef {
  readonly id: string;
  readonly label: string;
  readonly labelKo: string;
  readonly group: 'COMMAND' | 'RESEARCH' | 'PLATFORM' | 'ADVANCED';
  readonly step: number | null;
  readonly status: V6PageStatus;
  readonly description: string;
}

export const V6_BRAND = {
  name: 'AI Quant Reinforcement Learning',
  subtitle: 'V6 Workflow Research Platform',
  version: 'v6.0',
  updateDate: '2026-07-28',
} as const;

export interface V6StepDef {
  readonly id: string;
  readonly label: string;
  readonly labelKo: string;
  readonly statusKey: 'data' | 'experiment' | 'training' | 'evaluation' | 'compare' | 'report' | 'discovery';
}

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
  { id: 'symbol', labelKo: '종목 심층' },
  { id: 'flow', labelKo: '수급 흐름' },
  { id: 'regime', labelKo: '시장 국면' },
] as const;

export const V6_PAGES: readonly V6PageDef[] = [
  { id: 'home', label: 'Home', labelKo: '홈', group: 'COMMAND', step: 1, status: 'BUILT', description: 'V6 연구 상태와 빠른 이동을 확인하는 홈 화면입니다.' },
  { id: 'scorecard', label: 'Program Scorecard', labelKo: '프로그램 점수', group: 'COMMAND', step: null, status: 'BUILT', description: '전체 페이지, 역량, 연구 증거와 개발 거버넌스를 점수로 감사합니다.' },
  { id: 'rl', label: 'Reinforcement Learning', labelKo: '강화학습', group: 'RESEARCH', step: 2, status: 'BUILT', description: '강화학습 연구 여정과 단계별 근거를 다루는 작업공간입니다.' },
  { id: 'insight', label: 'Insights', labelKo: '인사이트', group: 'RESEARCH', step: null, status: 'BUILT', description: '종목, 수급, 시장 국면 관찰을 다루는 작업공간입니다.' },
  { id: 'lanes', label: 'Other Lanes', labelKo: '다른 레인', group: 'PLATFORM', step: null, status: 'BUILT', description: '인트라데이 RL과 Kronos 예측 레인을 함께 확인합니다.' },
  { id: 'settings', label: 'Settings', labelKo: '설정', group: 'ADVANCED', step: null, status: 'BUILT', description: 'V6 연구 환경 설정을 다루는 화면입니다.' },
];
function compatibilityLocation(tab: string | null, pathname: string): { tab: string; step?: string; sub?: string } | null {
  const search = tab == null ? '' : `?tab=${encodeURIComponent(tab)}`;
  const target = v6CompatibilityTarget({ pathname, search });
  if (!target) return null;
  const [targetTab, query = ''] = target.split('?', 2);
  const params = new URLSearchParams(query);
  const location: { tab: string; step?: string; sub?: string } = { tab: targetTab };
  if (params.get('step')) location.step = params.get('step')!;
  if (params.get('sub')) location.sub = params.get('sub')!;
  return location;
}


export function resolveV6Location(tab: string | null, step: string | null, sub: string | null, pathname = '/'): { tab: string; step?: string; sub?: string } {
  if (tab === 'overview') return { tab: 'home' };
  if (V6_RL_STEPS.some((item) => item.id === tab)) return { tab: 'rl', step: tab };
  if (tab === 'insight-symbol') return { tab: 'insight', sub: 'symbol' };
  if (tab === 'insight-flow') return { tab: 'insight', sub: 'flow' };
  if (tab === 'insight-regime') return { tab: 'insight', sub: 'regime' };
  if (tab === 'intraday' || tab === 'kronos') return { tab: 'lanes' };
  if (!V6_PAGES.some((page) => page.id === tab)) {
    const compatibility = compatibilityLocation(tab, pathname);
    if (compatibility) return compatibility;
  }
  const resolvedTab = V6_PAGES.some((page) => page.id === tab) ? tab! : 'home';
  const location: { tab: string; step?: string; sub?: string } = { tab: resolvedTab };
  if (resolvedTab === 'rl' && V6_RL_STEPS.some((item) => item.id === step)) location.step = step!;
  if (resolvedTab === 'insight' && V6_INSIGHT_SUBTABS.some((item) => item.id === sub)) location.sub = sub!;
  return location;
}

export function resolveV6Page(tab: string | null): V6PageDef {
  const location = resolveV6Location(tab, null, null);
  return V6_PAGES.find((page) => page.id === location.tab) ?? V6_PAGES[0];
}

export function v6PageUrl(id: string): string {
  const location = resolveV6Location(id, null, null);
  return location.tab === 'home' ? '/?ui=v6' : `/?ui=v6&tab=${encodeURIComponent(location.tab)}${location.step ? `&step=${encodeURIComponent(location.step)}` : ''}`;
}
