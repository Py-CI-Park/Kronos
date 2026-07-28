import assert from 'node:assert/strict';
import { test } from 'node:test';

import type * as V5DefaultGate from './v5DefaultGate';

const gatePath = ['.', 'v5DefaultGate.ts'].join('/');
const {
  V5_DEFAULT_GATE_EQUATION,
  V5_DEFAULT_GATE_EQUATION_TERMS,
  V5_DEFAULT_GATE_FALSE_LOCKS,
  V5_DEFAULT_GATE_GLOBAL_KEY,
  V5_DEFAULT_GATE_PASS_GATES,
  V5_DEFAULT_GATE_SCHEMA,
  V5_DEFAULT_GATE_STORAGE_KEY,
  V5_TERMINAL_REPORT_SCHEMA,
  evaluateV5DefaultGateReceipt,
  isV5DefaultGateAllowed,
  parseV5DefaultGateReceiptJson,
  readLocalV5DefaultGateReceipt,
}: typeof V5DefaultGate = await import(gatePath);

type MutableDefaultGate = {
  schema: string;
  default_equation: string;
  release_eligible: boolean;
  default_eligible: boolean;
  default_decision: string;
  terminal_result: string;
  blocking_codes: string[];
  equation_terms: Record<string, boolean>;
  point_score: Record<string, unknown>;
  identity_gate: Record<string, unknown>;
  source_gate: Record<string, unknown>;
  rollback_gate: Record<string, unknown>;
  browser_gate: Record<string, unknown>;
  security_gate: Record<string, unknown>;
  six_locks_false: Record<string, boolean>;
  model_verdict?: string;
  d0?: string;
  d1?: string;
  oos?: string;
  not_run?: string;
};

function allEquationTerms(value: boolean): Record<string, boolean> {
  return Object.fromEntries(V5_DEFAULT_GATE_EQUATION_TERMS.map((term) => [term, value]));
}

function falseLocks(): Record<string, boolean> {
  return Object.fromEntries(V5_DEFAULT_GATE_FALSE_LOCKS.map((lock) => [lock, false]));
}

function validDefaultGate(overrides: Partial<MutableDefaultGate> = {}): MutableDefaultGate {
  return {
    schema: V5_DEFAULT_GATE_SCHEMA,
    default_equation: V5_DEFAULT_GATE_EQUATION,
    release_eligible: true,
    default_eligible: true,
    default_decision: 'SWITCH_TO_V5',
    terminal_result: 'CLOSED',
    blocking_codes: [],
    equation_terms: allEquationTerms(true),
    point_score: {
      a_valid: true,
      b_valid: true,
      a_gate_passed: true,
      b_gate_passed: true,
      model_verdict_point_bearing: false,
      model_verdict_observed: 'NO-GO',
    },
    identity_gate: {
      passed: true,
      head_match: true,
      tree_match: true,
      dist_match: true,
      config_match: true,
      worktree_clean: true,
    },
    source_gate: { passed: true, source_identity_bound: true },
    rollback_gate: { passed: true, v3_available: true, query_contract_passed: true },
    browser_gate: {
      passed: true,
      browser_live: true,
      browser_synthetic: false,
      browser_matrix_passed: true,
      browser_distinct_from_synthetic: true,
      browser_reused_synthetic_artifact: false,
      dry_run_fixture_mode: false,
    },
    security_gate: { passed: true, publication_actions: [] },
    six_locks_false: falseLocks(),
    ...overrides,
  };
}

function terminalReport(defaultGate: MutableDefaultGate = validDefaultGate(), overrides: Record<string, unknown> = {}): Record<string, unknown> {
  const closed = defaultGate.default_eligible === true;
  return {
    schema: V5_TERMINAL_REPORT_SCHEMA,
    run_nonce: 'fixture-run',
    terminal_status: closed ? 'TERMINAL_CLOSED' : 'TERMINAL_BLOCKED',
    default_gate: defaultGate,
    default_decision: defaultGate.default_decision,
    release_eligible: defaultGate.release_eligible,
    default_eligible: defaultGate.default_eligible,
    blocking_codes: [...defaultGate.blocking_codes],
    bound_identity: {
      head_sha256: '0'.repeat(64),
      tree_sha256: '1'.repeat(64),
      dist_manifest_sha256: '2'.repeat(64),
      config_sha256: '3'.repeat(64),
    },
    publication_actions_attempted: false,
    mutated_tracked_files: false,
    completed_at: '2026-07-15T00:00:00Z',
    ...overrides,
  };
}

function currentBlockedTerminalReport(): Record<string, unknown> {
  const blocked = validDefaultGate({
    release_eligible: false,
    default_eligible: false,
    default_decision: 'RETAIN_V3',
    terminal_result: 'BLOCKED',
    blocking_codes: ['BROWSER_EVIDENCE_NOT_LIVE', 'BROWSER_EVIDENCE_SYNTHETIC', 'DRY_RUN_FIXTURE_NOT_RELEASABLE'],
    equation_terms: {
      ...allEquationTerms(true),
      release_closed: false,
      live_browser_distinct: false,
      not_dry_run_fixture: false,
    },
    browser_gate: {
      passed: false,
      browser_live: false,
      browser_synthetic: true,
      browser_matrix_passed: true,
      browser_distinct_from_synthetic: false,
      browser_reused_synthetic_artifact: false,
      dry_run_fixture_mode: true,
    },
  });
  return terminalReport(blocked);
}

test('evaluateV5DefaultGateReceipt permits the closure terminal-report/default_gate shape', () => {
  const gate = validDefaultGate();
  const report = terminalReport(gate);

  assert.deepEqual(evaluateV5DefaultGateReceipt(gate), { allowV5Default: true, reasons: [] });
  assert.deepEqual(evaluateV5DefaultGateReceipt(report), { allowV5Default: true, reasons: [] });
  assert.equal(isV5DefaultGateAllowed(report), true);
});

test('evaluateV5DefaultGateReceipt fails closed without an available valid receipt', () => {
  assert.deepEqual(evaluateV5DefaultGateReceipt(null).reasons, ['RECEIPT_UNAVAILABLE']);
  assert.deepEqual(evaluateV5DefaultGateReceipt('not-json').reasons, ['RECEIPT_INVALID']);
  assert.equal(isV5DefaultGateAllowed({}), false);
  assert.equal(parseV5DefaultGateReceiptJson('{'), null);
});

test('current blocked terminal receipt cannot enable V5 by default', () => {
  const result = evaluateV5DefaultGateReceipt(currentBlockedTerminalReport());

  assert.equal(result.allowV5Default, false);
  assert.ok(result.reasons.includes('TERMINAL_STATUS_NOT_CLOSED'));
  assert.ok(result.reasons.includes('DEFAULT_ELIGIBLE_NOT_TRUE'));
  assert.ok(result.reasons.includes('RELEASE_ELIGIBLE_NOT_TRUE'));
  assert.ok(result.reasons.includes('TERMINAL_RESULT_NOT_CLOSED'));
  assert.ok(result.reasons.includes('BLOCKING_CODES_PRESENT'));
  assert.ok(result.reasons.includes('EQUATION_TERM_LIVE_BROWSER_DISTINCT_NOT_TRUE'));
  assert.ok(result.reasons.includes('BROWSER_GATE_NOT_PASS'));
  assert.ok(result.reasons.includes('BROWSER_EVIDENCE_NOT_LIVE'));
  assert.ok(result.reasons.includes('SYNTHETIC_BROWSER_EVIDENCE'));
  assert.ok(result.reasons.includes('DRY_RUN_FIXTURE_ACTIVE'));
});

test('evaluateV5DefaultGateReceipt rejects closed-shape counterfactuals', () => {
  const cases: readonly [string, MutableDefaultGate | Record<string, unknown>, string][] = [
    ['schema drift', validDefaultGate({ schema: 'kronos_dashboard_v5_default_gate.v1' }), 'SCHEMA_INVALID'],
    ['default equation drift', validDefaultGate({ default_equation: 'V5_DEFAULT := SCORE_ONLY' }), 'DEFAULT_EQUATION_INVALID'],
    ['default eligibility false', validDefaultGate({ default_eligible: false }), 'DEFAULT_ELIGIBLE_NOT_TRUE'],
    ['release eligibility false', validDefaultGate({ release_eligible: false }), 'RELEASE_ELIGIBLE_NOT_TRUE'],
    ['default decision retain', validDefaultGate({ default_decision: 'RETAIN_V3' }), 'DEFAULT_DECISION_NOT_SWITCH_TO_V5'],
    ['terminal result blocked', validDefaultGate({ terminal_result: 'BLOCKED' }), 'TERMINAL_RESULT_NOT_CLOSED'],
    ['blocking codes present', validDefaultGate({ blocking_codes: ['POINT_SCORE_FAIL'] }), 'BLOCKING_CODES_PRESENT'],
    ['publication action present', validDefaultGate({ security_gate: { passed: true, publication_actions: ['push'] } }), 'PUBLICATION_ACTIONS_PRESENT'],
    ['publication actions invalid', validDefaultGate({ security_gate: { passed: true } }), 'PUBLICATION_ACTIONS_INVALID'],
    ['browser not live', validDefaultGate({ browser_gate: { ...validDefaultGate().browser_gate, browser_live: false } }), 'BROWSER_EVIDENCE_NOT_LIVE'],
    ['synthetic browser evidence', validDefaultGate({ browser_gate: { ...validDefaultGate().browser_gate, browser_synthetic: true } }), 'SYNTHETIC_BROWSER_EVIDENCE'],
    [
      'reused synthetic browser evidence',
      validDefaultGate({ browser_gate: { ...validDefaultGate().browser_gate, browser_reused_synthetic_artifact: true } }),
      'BROWSER_REUSED_SYNTHETIC_EVIDENCE',
    ],
    ['dry-run fixture', validDefaultGate({ browser_gate: { ...validDefaultGate().browser_gate, dry_run_fixture_mode: true } }), 'DRY_RUN_FIXTURE_ACTIVE'],
    ['terminal report publication action attempted', terminalReport(validDefaultGate(), { publication_actions_attempted: true }), 'PUBLICATION_ACTION_ATTEMPTED'],
    ['terminal report mutated tracked files', terminalReport(validDefaultGate(), { mutated_tracked_files: true }), 'MUTATED_TRACKED_FILES_NOT_FALSE'],
  ];

  for (const [name, receipt, expected] of cases) {
    const result = evaluateV5DefaultGateReceipt(receipt);
    assert.equal(result.allowV5Default, false, name);
    assert.ok(result.reasons.includes(expected as V5DefaultGate.V5DefaultGateBlockerCode), name);
  }

  for (const term of V5_DEFAULT_GATE_EQUATION_TERMS) {
    const result = evaluateV5DefaultGateReceipt(
      validDefaultGate({
        equation_terms: { ...allEquationTerms(true), [term]: false },
      }),
    );
    assert.equal(result.allowV5Default, false, term);
    assert.ok(
      result.reasons.includes(`EQUATION_TERM_${term.toUpperCase()}_NOT_TRUE` as V5DefaultGate.V5DefaultGateBlockerCode),
      term,
    );
  }

  for (const passGate of V5_DEFAULT_GATE_PASS_GATES) {
    const result = evaluateV5DefaultGateReceipt(
      validDefaultGate({
        [passGate]: { passed: false },
      } as Partial<MutableDefaultGate>),
    );
    assert.equal(result.allowV5Default, false, passGate);
    assert.ok(result.reasons.includes(`${passGate.toUpperCase()}_NOT_PASS` as V5DefaultGate.V5DefaultGateBlockerCode), passGate);
  }

  for (const lock of V5_DEFAULT_GATE_FALSE_LOCKS) {
    const result = evaluateV5DefaultGateReceipt(
      validDefaultGate({
        six_locks_false: { ...falseLocks(), [lock]: true },
      }),
    );
    assert.equal(result.allowV5Default, false, lock);
    assert.ok(result.reasons.includes(`LOCK_${lock.toUpperCase()}_NOT_FALSE` as V5DefaultGate.V5DefaultGateBlockerCode), lock);
  }
});

test('model, D0, D1, OOS, and NOT_RUN fields are non-operands', () => {
  const noisyReceipt = validDefaultGate({
    model_verdict: 'GO',
    d0: 'D0_PRICE_BASIS_NOT_VERIFIED',
    d1: 'D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED',
    oos: 'NOT_RUN',
    not_run: 'MODEL_NOT_RUN',
    point_score: {
      a_valid: true,
      b_valid: true,
      a_gate_passed: true,
      b_gate_passed: true,
      model_verdict_point_bearing: false,
      model_verdict_observed: 'GO',
    },
  });

  assert.equal(evaluateV5DefaultGateReceipt(noisyReceipt).allowV5Default, true);

  const explicitOperandFailure = evaluateV5DefaultGateReceipt(
    validDefaultGate({
      model_verdict: 'GO',
      d0: 'CLEAR',
      d1: 'CLEAR',
      oos: 'PASS',
      not_run: 'NONE',
      equation_terms: { ...allEquationTerms(true), engineering_90_pass: false },
    }),
  );
  assert.equal(explicitOperandFailure.allowV5Default, false);
  assert.ok(explicitOperandFailure.reasons.includes('EQUATION_TERM_ENGINEERING_90_PASS_NOT_TRUE'));
});

test('readLocalV5DefaultGateReceipt reads injected, document, and storage receipts but fails closed on denial', () => {
  const localStorageDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  const documentDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'document');
  const globalReceiptDescriptor = Object.getOwnPropertyDescriptor(globalThis, V5_DEFAULT_GATE_GLOBAL_KEY);
  const receipt = terminalReport();

  try {
    Object.defineProperty(globalThis, V5_DEFAULT_GATE_GLOBAL_KEY, {
      configurable: true,
      value: receipt,
    });
    assert.equal(readLocalV5DefaultGateReceipt(), receipt);

    delete (globalThis as Record<string, unknown>)[V5_DEFAULT_GATE_GLOBAL_KEY];
    Object.defineProperty(globalThis, 'document', {
      configurable: true,
      value: {
        getElementById(id: string): { textContent: string } | null {
          assert.equal(id, 'kronos-v5-default-gate');
          return { textContent: JSON.stringify(receipt) };
        },
      },
    });
    assert.deepEqual(readLocalV5DefaultGateReceipt(), receipt);

    Object.defineProperty(globalThis, 'document', { configurable: true, value: undefined });
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      value: {
        getItem(key: string): string | null {
          assert.equal(key, V5_DEFAULT_GATE_STORAGE_KEY);
          return JSON.stringify(receipt);
        },
      },
    });
    assert.deepEqual(readLocalV5DefaultGateReceipt(), receipt);

    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      get(): unknown {
        throw new Error('storage denied');
      },
    });
    assert.equal(readLocalV5DefaultGateReceipt(), null);
  } finally {
    if (localStorageDescriptor) {
      Object.defineProperty(globalThis, 'localStorage', localStorageDescriptor);
    } else {
      delete (globalThis as Record<string, unknown>).localStorage;
    }
    if (documentDescriptor) {
      Object.defineProperty(globalThis, 'document', documentDescriptor);
    } else {
      delete (globalThis as Record<string, unknown>).document;
    }
    if (globalReceiptDescriptor) {
      Object.defineProperty(globalThis, V5_DEFAULT_GATE_GLOBAL_KEY, globalReceiptDescriptor);
    } else {
      delete (globalThis as Record<string, unknown>)[V5_DEFAULT_GATE_GLOBAL_KEY];
    }
  }
});
