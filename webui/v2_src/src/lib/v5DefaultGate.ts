export const V5_DEFAULT_GATE_SCHEMA = 'kronos_v5_default_gate.v1';
export const V5_TERMINAL_REPORT_SCHEMA = 'kronos_release_terminal_report.v1';
export const V5_DEFAULT_GATE_GLOBAL_KEY = '__KRONOS_V5_DEFAULT_GATE_RECEIPT__';
export const V5_DEFAULT_GATE_STORAGE_KEY = 'kronos-v5-default-gate-receipt';
export const V5_DEFAULT_GATE_DOCUMENT_ID = 'kronos-v5-default-gate';

export const V5_DEFAULT_GATE_EQUATION = 'V5_DEFAULT := RELEASE_CLOSED && POINT_SCORE_A_EQ_B && ENGINEERING_90_PASS && ASSURANCE_ELIGIBLE && PRIOR_CHAINS_RESOLVED && HEAD_MATCH && TREE_MATCH && DIST_MATCH && CONFIG_MATCH && WORKTREE_CLEAN && SOURCE_IDENTITY_BOUND && ROLLBACK_V3_AVAILABLE && ROLLBACK_QUERY_PASS && LIVE_BROWSER_DISTINCT && SECURITY_CLEAR && SIX_LOCKS_FALSE && NO_PUBLICATION_ACTION && !DRY_RUN_FIXTURE';

export const V5_DEFAULT_GATE_EQUATION_TERMS = [
  'release_closed',
  'point_score_a_eq_b',
  'engineering_90_pass',
  'assurance_eligible',
  'prior_chains_resolved',
  'head_match',
  'tree_match',
  'dist_match',
  'config_match',
  'worktree_clean',
  'source_identity_bound',
  'rollback_v3_available',
  'rollback_query_pass',
  'live_browser_distinct',
  'security_clear',
  'six_locks_false',
  'no_publication_action',
  'not_dry_run_fixture',
] as const;
export type V5DefaultGateEquationTerm = (typeof V5_DEFAULT_GATE_EQUATION_TERMS)[number];

export const V5_DEFAULT_GATE_FALSE_LOCKS = [
  'promotion_allowed',
  'model_build_allowed',
  'paper_forward_allowed',
  'live_broker_order_allowed',
  'profitability_claim_allowed',
  'go_summary_allowed',
] as const;
export type V5DefaultGateFalseLock = (typeof V5_DEFAULT_GATE_FALSE_LOCKS)[number];

export const V5_DEFAULT_GATE_PASS_GATES = ['rollback_gate', 'browser_gate', 'security_gate', 'source_gate', 'identity_gate'] as const;
export type V5DefaultGatePassGate = (typeof V5_DEFAULT_GATE_PASS_GATES)[number];

type V5DefaultGateEquationBlockerCode = `EQUATION_TERM_${Uppercase<V5DefaultGateEquationTerm>}_NOT_TRUE`;
type V5DefaultGateLockBlockerCode = `LOCK_${Uppercase<V5DefaultGateFalseLock>}_NOT_FALSE`;
type V5DefaultGatePassGateBlockerCode = `${Uppercase<V5DefaultGatePassGate>}_NOT_PASS`;

export type V5DefaultGateBlockerCode =
  | 'RECEIPT_UNAVAILABLE'
  | 'RECEIPT_INVALID'
  | 'SCHEMA_INVALID'
  | 'DEFAULT_EQUATION_INVALID'
  | 'DEFAULT_ELIGIBLE_NOT_TRUE'
  | 'RELEASE_ELIGIBLE_NOT_TRUE'
  | 'DEFAULT_DECISION_NOT_SWITCH_TO_V5'
  | 'TERMINAL_RESULT_NOT_CLOSED'
  | 'TERMINAL_STATUS_NOT_CLOSED'
  | 'BLOCKING_CODES_PRESENT'
  | 'PUBLICATION_ACTIONS_PRESENT'
  | 'PUBLICATION_ACTIONS_INVALID'
  | 'PUBLICATION_ACTION_ATTEMPTED'
  | 'MUTATED_TRACKED_FILES_NOT_FALSE'
  | 'EQUATION_TERMS_INVALID'
  | 'SIX_LOCKS_INVALID'
  | 'DRY_RUN_FIXTURE_ACTIVE'
  | 'SYNTHETIC_BROWSER_EVIDENCE'
  | 'BROWSER_EVIDENCE_NOT_LIVE'
  | 'BROWSER_REUSED_SYNTHETIC_EVIDENCE'
  | V5DefaultGateEquationBlockerCode
  | V5DefaultGateLockBlockerCode
  | V5DefaultGatePassGateBlockerCode;

export interface V5DefaultGateEvaluation {
  allowV5Default: boolean;
  reasons: readonly V5DefaultGateBlockerCode[];
}

type AnyRecord = Record<string, unknown>;

function isRecord(value: unknown): value is AnyRecord {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function hasOwn(source: AnyRecord, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(source, key);
}

function firstRecord(source: AnyRecord, key: string): AnyRecord | null {
  const value = source[key];
  return isRecord(value) ? value : null;
}

function equationTermBlocker(term: V5DefaultGateEquationTerm): V5DefaultGateEquationBlockerCode {
  return `EQUATION_TERM_${term.toUpperCase()}_NOT_TRUE` as V5DefaultGateEquationBlockerCode;
}

function lockBlocker(lock: V5DefaultGateFalseLock): V5DefaultGateLockBlockerCode {
  return `LOCK_${lock.toUpperCase()}_NOT_FALSE` as V5DefaultGateLockBlockerCode;
}

function passGateBlocker(gate: V5DefaultGatePassGate): V5DefaultGatePassGateBlockerCode {
  return `${gate.toUpperCase()}_NOT_PASS` as V5DefaultGatePassGateBlockerCode;
}

function arrayIsEmpty(value: unknown): boolean {
  return Array.isArray(value) && value.length === 0;
}

function recordPassed(value: unknown): boolean {
  return isRecord(value) && value.passed === true;
}

function evaluateTerminalReportEnvelope(terminalReport: AnyRecord, reasons: V5DefaultGateBlockerCode[]): AnyRecord | null {
  if (terminalReport.terminal_status !== 'TERMINAL_CLOSED') {
    reasons.push('TERMINAL_STATUS_NOT_CLOSED');
  }
  if (terminalReport.default_eligible !== true) {
    reasons.push('DEFAULT_ELIGIBLE_NOT_TRUE');
  }
  if (terminalReport.release_eligible !== true) {
    reasons.push('RELEASE_ELIGIBLE_NOT_TRUE');
  }
  if (terminalReport.default_decision !== 'SWITCH_TO_V5') {
    reasons.push('DEFAULT_DECISION_NOT_SWITCH_TO_V5');
  }
  if (!arrayIsEmpty(terminalReport.blocking_codes)) {
    reasons.push('BLOCKING_CODES_PRESENT');
  }
  if (terminalReport.publication_actions_attempted !== false) {
    reasons.push('PUBLICATION_ACTION_ATTEMPTED');
  }
  if (terminalReport.mutated_tracked_files !== false) {
    reasons.push('MUTATED_TRACKED_FILES_NOT_FALSE');
  }

  const defaultGate = firstRecord(terminalReport, 'default_gate');
  if (!defaultGate) {
    reasons.push('RECEIPT_INVALID');
  }
  return defaultGate;
}

function selectDefaultGateReceipt(receipt: AnyRecord, reasons: V5DefaultGateBlockerCode[]): AnyRecord | null {
  if (receipt.schema === V5_TERMINAL_REPORT_SCHEMA) {
    return evaluateTerminalReportEnvelope(receipt, reasons);
  }
  return receipt;
}

function evaluateEquationTerms(gate: AnyRecord, reasons: V5DefaultGateBlockerCode[]): void {
  const equationTerms = firstRecord(gate, 'equation_terms');
  if (!equationTerms) {
    reasons.push('EQUATION_TERMS_INVALID');
    return;
  }

  const expected = new Set<string>(V5_DEFAULT_GATE_EQUATION_TERMS);
  for (const term of V5_DEFAULT_GATE_EQUATION_TERMS) {
    if (equationTerms[term] !== true) {
      reasons.push(equationTermBlocker(term));
    }
  }

  for (const [term, value] of Object.entries(equationTerms)) {
    if (!expected.has(term) || value !== true) {
      if (!V5_DEFAULT_GATE_EQUATION_TERMS.includes(term as V5DefaultGateEquationTerm)) {
        reasons.push('EQUATION_TERMS_INVALID');
      }
      break;
    }
  }
}

function evaluateSixLocks(gate: AnyRecord, reasons: V5DefaultGateBlockerCode[]): void {
  const locks = firstRecord(gate, 'six_locks_false');
  if (!locks) {
    reasons.push('SIX_LOCKS_INVALID');
    return;
  }

  const expected = new Set<string>(V5_DEFAULT_GATE_FALSE_LOCKS);
  for (const lock of V5_DEFAULT_GATE_FALSE_LOCKS) {
    if (locks[lock] !== false) {
      reasons.push(lockBlocker(lock));
    }
  }

  for (const key of Object.keys(locks)) {
    if (!expected.has(key)) {
      reasons.push('SIX_LOCKS_INVALID');
      break;
    }
  }
}

function evaluatePassGates(gate: AnyRecord, reasons: V5DefaultGateBlockerCode[]): void {
  for (const passGate of V5_DEFAULT_GATE_PASS_GATES) {
    if (!recordPassed(gate[passGate])) {
      reasons.push(passGateBlocker(passGate));
    }
  }
}

function evaluateBrowserGate(gate: AnyRecord, reasons: V5DefaultGateBlockerCode[]): void {
  const browserGate = firstRecord(gate, 'browser_gate');
  if (!browserGate) {
    return;
  }
  if (browserGate.browser_live !== true) {
    reasons.push('BROWSER_EVIDENCE_NOT_LIVE');
  }
  if (browserGate.browser_synthetic !== false) {
    reasons.push('SYNTHETIC_BROWSER_EVIDENCE');
  }
  if (browserGate.browser_reused_synthetic_artifact !== false) {
    reasons.push('BROWSER_REUSED_SYNTHETIC_EVIDENCE');
  }
  if (browserGate.dry_run_fixture_mode !== false) {
    reasons.push('DRY_RUN_FIXTURE_ACTIVE');
  }
}

function evaluateSecurityGate(gate: AnyRecord, reasons: V5DefaultGateBlockerCode[]): void {
  const securityGate = firstRecord(gate, 'security_gate');
  if (!securityGate) {
    return;
  }
  if (!Array.isArray(securityGate.publication_actions)) {
    reasons.push('PUBLICATION_ACTIONS_INVALID');
  } else if (securityGate.publication_actions.length > 0) {
    reasons.push('PUBLICATION_ACTIONS_PRESENT');
  }
}

export function evaluateV5DefaultGateReceipt(receipt: unknown): V5DefaultGateEvaluation {
  if (!isRecord(receipt)) {
    return {
      allowV5Default: false,
      reasons: [receipt == null ? 'RECEIPT_UNAVAILABLE' : 'RECEIPT_INVALID'],
    };
  }

  const reasons: V5DefaultGateBlockerCode[] = [];
  const gate = selectDefaultGateReceipt(receipt, reasons);
  if (!gate) {
    return {
      allowV5Default: false,
      reasons,
    };
  }

  if (gate.schema !== V5_DEFAULT_GATE_SCHEMA) {
    reasons.push('SCHEMA_INVALID');
  }
  if (gate.default_equation !== V5_DEFAULT_GATE_EQUATION) {
    reasons.push('DEFAULT_EQUATION_INVALID');
  }
  if (gate.default_eligible !== true) {
    reasons.push('DEFAULT_ELIGIBLE_NOT_TRUE');
  }
  if (gate.release_eligible !== true) {
    reasons.push('RELEASE_ELIGIBLE_NOT_TRUE');
  }
  if (gate.default_decision !== 'SWITCH_TO_V5') {
    reasons.push('DEFAULT_DECISION_NOT_SWITCH_TO_V5');
  }
  if (gate.terminal_result !== 'CLOSED') {
    reasons.push('TERMINAL_RESULT_NOT_CLOSED');
  }
  if (!arrayIsEmpty(gate.blocking_codes)) {
    reasons.push('BLOCKING_CODES_PRESENT');
  }

  evaluateEquationTerms(gate, reasons);
  evaluateSixLocks(gate, reasons);
  evaluatePassGates(gate, reasons);
  evaluateBrowserGate(gate, reasons);
  evaluateSecurityGate(gate, reasons);

  return {
    allowV5Default: reasons.length === 0,
    reasons,
  };
}

export function isV5DefaultGateAllowed(receipt: unknown): boolean {
  return evaluateV5DefaultGateReceipt(receipt).allowV5Default;
}

export function parseV5DefaultGateReceiptJson(raw: string | null | undefined): unknown | null {
  if (typeof raw !== 'string' || raw.trim().length === 0) {
    return null;
  }

  try {
    return JSON.parse(raw) as unknown;
  } catch {
    return null;
  }
}

function readInjectedV5DefaultGateReceipt(): unknown | undefined {
  try {
    if (typeof globalThis === 'undefined') {
      return undefined;
    }
    const carrier = globalThis as Record<string, unknown>;
    return hasOwn(carrier, V5_DEFAULT_GATE_GLOBAL_KEY) ? carrier[V5_DEFAULT_GATE_GLOBAL_KEY] : undefined;
  } catch {
    return undefined;
  }
}

function readDocumentV5DefaultGateReceipt(): unknown | undefined {
  try {
    if (typeof document === 'undefined' || typeof document.getElementById !== 'function') {
      return undefined;
    }
    const element = document.getElementById(V5_DEFAULT_GATE_DOCUMENT_ID);
    return element ? parseV5DefaultGateReceiptJson(element.textContent) : undefined;
  } catch {
    return undefined;
  }
}

function getSafeLocalStorage(): Storage | null {
  try {
    if (typeof globalThis === 'undefined') {
      return null;
    }
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

export function readLocalV5DefaultGateReceipt(): unknown | null {
  const injected = readInjectedV5DefaultGateReceipt();
  if (injected !== undefined) {
    return injected;
  }

  const documentReceipt = readDocumentV5DefaultGateReceipt();
  if (documentReceipt !== undefined) {
    return documentReceipt;
  }

  const storage = getSafeLocalStorage();
  if (!storage) {
    return null;
  }

  try {
    return parseV5DefaultGateReceiptJson(storage.getItem(V5_DEFAULT_GATE_STORAGE_KEY));
  } catch {
    return null;
  }
}

export function isLocalV5DefaultGateAllowed(): boolean {
  return isV5DefaultGateAllowed(readLocalV5DefaultGateReceipt());
}
