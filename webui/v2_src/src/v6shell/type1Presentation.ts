export type Type1PresentationState = 'NO_GO' | 'NOT_RUN' | 'BLOCKED' | 'TAMPERED' | 'LOADING' | 'EMPTY';

export const TYPE1_FACTS = Object.freeze({
  identity: Object.freeze({
    family: 'TYPE1',
    algorithm: 'Sequential MaskablePPO',
    m3e: 'M3E is LinUCB contextual-bandit and is not Type1.',
  }),
  execution: Object.freeze({
    priceBasis: 'Exact 15:20 close proxy',
    officialClose: false,
    officialCloseStatement: 'The 15:20 proxy is not the official close.',
    roundTripCost: '23bp',
  }),
  accounting: Object.freeze({
    initialNav: '60M fixed-notional NAV',
    slotNotional: '5M',
    maxSlots: 10,
    maxExposure: '50M',
    reserve: '10M',
  }),
  evaluation: Object.freeze({
    fixedSeeds: 5,
    validationReuse: 'Reused validation cannot yield GO.',
    freshOos: 'NOT_RUN',
    freshOosLifecycle: 'ACCUMULATING_NOT_RUN',
  }),
  claims: Object.freeze({
    liveOrProfitabilityClaim: false,
    statement: 'No live or profitability claim.',
  }),
});

type Type1IdentitySource = string | object | null | undefined;

function normalized(value: string): string {
  return value.toUpperCase().replace(/[^A-Z0-9]+/g, '');
}

function identityValues(source: Type1IdentitySource): readonly string[] {
  if (typeof source === 'string') return [source];
  if (source === null || typeof source !== 'object') return [];
  const record = source as Readonly<Record<string, unknown>>;
  return ['schema', 'schema_version', 'family', 'model_family', 'algorithm', 'strategy', 'type']
    .map((key) => record[key])
    .filter((value): value is string => typeof value === 'string');
}

/** Returns true only for the frozen Type1 family, never for M3E/LinUCB. */
export function isType1Identity(source: Type1IdentitySource): boolean {
  const values = identityValues(source).map(normalized);
  if (values.some((value) => value.includes('M3E') || value.includes('LINUCB'))) return false;
  return values.some((value) => value.includes('TYPE1'))
    || values.some((value) => value.includes('SEQUENTIAL') && value.includes('MASKABLEPPO'));
}

function stateTokens(value: unknown): readonly string[] {
  if (typeof value === 'string') return [value.toUpperCase()];
  if (value === null || typeof value !== 'object') return [];
  const record = value as Readonly<Record<string, unknown>>;
  return ['status', 'state', 'report_state', 'integrity', 'test_state', 'verdict', 'reason', 'failures', 'integrity_reasons']
    .flatMap((key) => {
      const item = record[key];
      return Array.isArray(item) ? item : [item];
    })
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.toUpperCase());
}

/** Classifies only evidenced lifecycle states; unrecognized evidence remains EMPTY. */
export function classifyType1State(value: unknown, loading = false): Type1PresentationState {
  if (loading) return 'LOADING';
  const tokens = stateTokens(value);
  if (tokens.length === 0) return 'EMPTY';
  const joined = tokens.join(' ');
  if (/TAMPER|HASH[ _-]?(MISMATCH|FAIL)|INTEGRITY[ _-]?(FAIL|ERROR)/.test(joined)) return 'TAMPERED';
  if (/BLOCKED|MISSING[ _-]?(EVIDENCE|ARTIFACT|LINEAGE|PREREG)/.test(joined)) return 'BLOCKED';
  if (/NO[ _-]?GO|INCONCLUSIVE/.test(joined)) return 'NO_GO';
  if (/ACCUMULATING[ _-]?NOT[ _-]?RUN|NOT[ _-]?RUN/.test(joined)) return 'NOT_RUN';
  return 'EMPTY';
}

export function type1StateLabel(state: Type1PresentationState): string {
  return state.replaceAll('_', ' ');
}
