import assert from 'node:assert/strict';
import { test } from 'node:test';

import type * as ShellMode from './shellMode';
import type * as V5DefaultGate from './v5DefaultGate';

const shellModePath = ['.', 'shellMode.ts'].join('/');
const {
  SHELL_STORAGE_KEY,
  dashboardShell,
  initializeDashboardShell,
  preserveShellQuery,
  resolveDashboardShell,
  setDashboardShell,
  shellSwitchUrl,
}: typeof ShellMode = await import(shellModePath);

const v5DefaultGatePath = ['.', 'v5DefaultGate.ts'].join('/');
const {
  V5_DEFAULT_GATE_EQUATION,
  V5_DEFAULT_GATE_SCHEMA,
  V5_DEFAULT_GATE_STORAGE_KEY,
}: typeof V5DefaultGate = await import(v5DefaultGatePath);

type GlobalKey = 'window' | 'localStorage' | 'location' | 'history' | 'document';

function restoreGlobals(snapshot: Map<GlobalKey, PropertyDescriptor | undefined>): void {
  for (const [key, descriptor] of snapshot) {
    if (descriptor) {
      Object.defineProperty(globalThis, key, descriptor);
    } else {
      delete (globalThis as Record<GlobalKey, unknown>)[key];
    }
  }
}

function snapshotGlobals(): Map<GlobalKey, PropertyDescriptor | undefined> {
  return new Map<GlobalKey, PropertyDescriptor | undefined>(
    (['window', 'localStorage', 'location', 'history', 'document'] as const).map((key) => [
      key,
      Object.getOwnPropertyDescriptor(globalThis, key),
    ]),
  );
}

function installClientGlobals(options: {
  search?: string;
  pathname?: string;
  hash?: string;
  stored?: string | null;
  gateReceipt?: unknown | null;
  throwStorage?: boolean;
  throwStorageGetter?: boolean;
  throwGetItem?: boolean;
  throwSetItem?: boolean;
  throwHistory?: boolean;
  throwDocument?: boolean;
} = {}): { storageWrites: string[]; historyUrls: string[]; markerWrites: string[] } {
  const storageWrites: string[] = [];
  const historyUrls: string[] = [];
  const markerWrites: string[] = [];
  let storedValue = options.stored ?? null;
  const gateReceipt = options.gateReceipt ?? null;

  if (options.throwStorageGetter) {
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      get(): unknown {
        throw new Error('storage acquisition unavailable');
      },
    });
  } else {
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      value: {
        getItem(key: string): string | null {
          if (options.throwStorage || options.throwGetItem) {
            throw new Error('storage read unavailable');
          }
          if (key === SHELL_STORAGE_KEY) {
            return storedValue;
          }
          if (key === V5_DEFAULT_GATE_STORAGE_KEY) {
            return gateReceipt === null ? null : JSON.stringify(gateReceipt);
          }
          assert.fail(`unexpected storage key: ${key}`);
        },
        setItem(key: string, value: string): void {
          if (options.throwStorage || options.throwSetItem) {
            throw new Error('storage write unavailable');
          }
          assert.equal(key, SHELL_STORAGE_KEY);
          storedValue = value;
          storageWrites.push(value);
        },
      },
    });
  }

  Object.defineProperty(globalThis, 'location', {
    configurable: true,
    value: {
      pathname: options.pathname ?? '/dashboard',
      search: options.search ?? '',
      hash: options.hash ?? '',
    },
  });

  Object.defineProperty(globalThis, 'history', {
    configurable: true,
    value: {
      state: { existing: true },
      pushState(_state: unknown, _title: string, url: string): void {
        if (options.throwHistory) {
          throw new Error('history unavailable');
        }
        historyUrls.push(`push:${url}`);
      },
      replaceState(_state: unknown, _title: string, url: string): void {
        if (options.throwHistory) {
          throw new Error('history unavailable');
        }
        historyUrls.push(`replace:${url}`);
      },
    },
  });

  Object.defineProperty(globalThis, 'document', {
    configurable: true,
    value: {
      documentElement: {
        setAttribute(name: string, value: string): void {
          if (options.throwDocument) {
            throw new Error('document unavailable');
          }
          markerWrites.push(`${name}:${value}`);
        },
      },
    },
  });

  return { storageWrites, historyUrls, markerWrites };
}

function readShell(): ShellMode.DashboardShell {
  let value: ShellMode.DashboardShell = 'v3';
  const unsubscribe = dashboardShell.subscribe((next) => {
    value = next;
  });
  unsubscribe();
  return value;
}

function validV5GateReceipt(): Record<string, unknown> {
  return {
    schema: V5_DEFAULT_GATE_SCHEMA,
    default_equation: V5_DEFAULT_GATE_EQUATION,
    release_eligible: true,
    default_eligible: true,
    default_decision: 'SWITCH_TO_V5',
    terminal_result: 'CLOSED',
    blocking_codes: [],
    equation_terms: {
      release_closed: true,
      point_score_a_eq_b: true,
      engineering_90_pass: true,
      assurance_eligible: true,
      prior_chains_resolved: true,
      head_match: true,
      tree_match: true,
      dist_match: true,
      config_match: true,
      worktree_clean: true,
      source_identity_bound: true,
      rollback_v3_available: true,
      rollback_query_pass: true,
      live_browser_distinct: true,
      security_clear: true,
      six_locks_false: true,
      no_publication_action: true,
      not_dry_run_fixture: true,
    },
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
    six_locks_false: {
      promotion_allowed: false,
      model_build_allowed: false,
      paper_forward_allowed: false,
      live_broker_order_allowed: false,
      profitability_claim_allowed: false,
      go_summary_allowed: false,
    },
  };
}

test('resolveDashboardShell defaults to released V6 without valid query or storage', () => {
  assert.deepEqual(resolveDashboardShell('', null), {
    shell: 'v6',
    source: 'default',
    shouldPersist: false,
  });
  assert.deepEqual(resolveDashboardShell('?ui=v9', 'unexpected', { invalid: true }), {
    shell: 'v6',
    source: 'default',
    shouldPersist: false,
  });
});

test('released V6 supersedes the historical local V5 default gate', () => {
  assert.deepEqual(resolveDashboardShell('', null, validV5GateReceipt()), {
    shell: 'v6',
    source: 'default',
    shouldPersist: false,
  });
  assert.deepEqual(resolveDashboardShell('', 'v5', { invalid: true }), {
    shell: 'v6',
    source: 'default',
    shouldPersist: false,
  });
});

test('valid query wins the current load but does not persist by default', () => {
  assert.deepEqual(resolveDashboardShell('?ui=v4', 'v3', validV5GateReceipt()), {
    shell: 'v4',
    source: 'query',
    shouldPersist: false,
  });
  assert.deepEqual(resolveDashboardShell('?ui=v3', 'v4', validV5GateReceipt()), {
    shell: 'v3',
    source: 'query',
    shouldPersist: false,
  });
  assert.deepEqual(resolveDashboardShell('?ui=v5', 'v3', { invalid: true }), {
    shell: 'v5',
    source: 'query',
    shouldPersist: false,
  });
});

test('invalid query falls back to valid storage', () => {
  assert.deepEqual(resolveDashboardShell('?ui=legacy', 'v4', validV5GateReceipt()), {
    shell: 'v4',
    source: 'storage',
    shouldPersist: false,
  });
});

test('stored V5 reload is honored only while the local closure gate remains valid', () => {
  assert.deepEqual(resolveDashboardShell('', 'v5', validV5GateReceipt()), {
    shell: 'v5',
    source: 'storage',
    shouldPersist: false,
  });
  assert.deepEqual(resolveDashboardShell('', 'v5', null), {
    shell: 'v6',
    source: 'default',
    shouldPersist: false,
  });
});

test('ui_persist=1 explicitly persists a valid query selection', () => {
  assert.deepEqual(resolveDashboardShell('?ui=v5&ui_persist=1', 'v3'), {
    shell: 'v5',
    source: 'query',
    shouldPersist: true,
  });
});

test('initializeDashboardShell applies a non-persisting query without writing storage', () => {
  const snapshot = snapshotGlobals();
  try {
    const { storageWrites, markerWrites } = installClientGlobals({ search: '?ui=v4', stored: 'v3' });

    assert.equal(initializeDashboardShell(), 'v4');
    assert.equal(readShell(), 'v4');
    assert.deepEqual(storageWrites, []);
    assert.deepEqual(markerWrites, ['data-kronos-shell:v4']);
  } finally {
    restoreGlobals(snapshot);
    dashboardShell.set('v3');
  }
});

test('initializeDashboardShell explicitly persists a query when ui_persist=1', () => {
  const snapshot = snapshotGlobals();
  try {
    const { storageWrites } = installClientGlobals({ search: '?ui=v4&ui_persist=1', stored: 'v3' });

    assert.equal(initializeDashboardShell(), 'v4');
    assert.deepEqual(storageWrites, ['v4']);
  } finally {
    restoreGlobals(snapshot);
    dashboardShell.set('v3');
  }
});

test('initializeDashboardShell defaults to released V6 even with a historical V5 closure gate', () => {
  const snapshot = snapshotGlobals();
  try {
    const { markerWrites, storageWrites } = installClientGlobals({ gateReceipt: validV5GateReceipt() });

    assert.equal(initializeDashboardShell(), 'v6');
    assert.equal(readShell(), 'v6');
    assert.deepEqual(storageWrites, []);
    assert.deepEqual(markerWrites, ['data-kronos-shell:v6']);
  } finally {
    restoreGlobals(snapshot);
    dashboardShell.set('v3');
  }
});

test('initializeDashboardShell reloads stored V5 only while the local closure gate is valid', () => {
  const snapshot = snapshotGlobals();
  try {
    installClientGlobals({ stored: 'v5', gateReceipt: validV5GateReceipt() });

    assert.equal(initializeDashboardShell(), 'v5');
    assert.equal(readShell(), 'v5');

    restoreGlobals(snapshot);
    dashboardShell.set('v3');

    const snapshotWithoutGate = snapshotGlobals();
    try {
      installClientGlobals({ stored: 'v5', gateReceipt: null });

      assert.equal(initializeDashboardShell(), 'v6');
      assert.equal(readShell(), 'v6');
    } finally {
      restoreGlobals(snapshotWithoutGate);
      dashboardShell.set('v3');
    }
  } finally {
    restoreGlobals(snapshot);
    dashboardShell.set('v3');
  }
});

test('initializeDashboardShell rolls back to V3 from query over stored V4 without persistence', () => {
  const snapshot = snapshotGlobals();
  try {
    const { storageWrites } = installClientGlobals({ search: '?ui=v3', stored: 'v4' });

    assert.equal(initializeDashboardShell(), 'v3');
    assert.equal(readShell(), 'v3');
    assert.deepEqual(storageWrites, []);
  } finally {
    restoreGlobals(snapshot);
    dashboardShell.set('v3');
  }
});

test('initializeDashboardShell persists explicit V3 rollback over stored V4', () => {
  const snapshot = snapshotGlobals();
  try {
    const { storageWrites } = installClientGlobals({ search: '?ui=v3&ui_persist=1', stored: 'v4' });

    assert.equal(initializeDashboardShell(), 'v3');
    assert.equal(readShell(), 'v3');
    assert.deepEqual(storageWrites, ['v3']);
  } finally {
    restoreGlobals(snapshot);
    dashboardShell.set('v3');
  }
});

test('shellSwitchUrl preserves path, tab, section, other query parameters, and hash while setting ui', () => {
  assert.equal(
    shellSwitchUrl('v4', {
      pathname: '/dashboard',
      search: '?tab=rl-trading&section=runs&mode=dense&ui=v3',
      hash: '#ledger',
    }),
    '/dashboard?tab=rl-trading&section=runs&mode=dense&ui=v4#ledger',
  );
});
test('shellSwitchUrl supports V5 Learning Now URLs', () => {
  assert.equal(
    shellSwitchUrl('v5', {
      pathname: '/learning-now',
      search: '?tab=learning-now&ui=v4',
      hash: '',
    }),
    '/learning-now?tab=learning-now&ui=v5',
  );
});

test('preserveShellQuery keeps non-persisting V4 query on canonical dashboard URLs', () => {
  assert.equal(preserveShellQuery('/', '?ui=v4'), '/?ui=v4');
  assert.equal(preserveShellQuery('/?tab=rl', '?ui=v4'), '/?tab=rl&ui=v4');
});

test('preserveShellQuery keeps V3 rollback query durable when persistence is explicit', () => {
  assert.equal(preserveShellQuery('/?tab=settings', '?ui=v3&ui_persist=1'), '/?tab=settings&ui=v3&ui_persist=1');
});

test('preserveShellQuery preserves target query and hash while merging only shell query from current search', () => {
  assert.equal(
    preserveShellQuery('/?tab=rl&section=evidence#ledger', '?ui=v4&ui_persist=1&tab=settings&extra=drop'),
    '/?tab=rl&section=evidence&ui=v4&ui_persist=1#ledger',
  );
});

test('preserveShellQuery keeps V5 query durable when persistence is explicit', () => {
  assert.equal(
    preserveShellQuery('/learning-now?tab=learning-now#run', '?ui=v5&ui_persist=1'),
    '/learning-now?tab=learning-now&ui=v5&ui_persist=1#run',
  );
});

test('preserveShellQuery leaves targets unchanged without a valid shell query', () => {
  assert.equal(preserveShellQuery('/?tab=history#runs', ''), '/?tab=history#runs');
  assert.equal(preserveShellQuery('/?tab=history#runs', '?ui=v9&ui_persist=1'), '/?tab=history#runs');
});

test('setDashboardShell updates client-only state, URL, and optional persistence', () => {
  const snapshot = snapshotGlobals();
  try {
    const { storageWrites, historyUrls, markerWrites } = installClientGlobals({
      pathname: '/dashboard',
      search: '?tab=home&section=paper-ops',
      hash: '#top',
      stored: null,
    });

    setDashboardShell('v4', { persist: true, replace: false });

    assert.equal(readShell(), 'v4');
    assert.deepEqual(storageWrites, ['v4']);
    assert.deepEqual(historyUrls, ['push:/dashboard?tab=home&section=paper-ops&ui=v4#top']);
    assert.deepEqual(markerWrites, ['data-kronos-shell:v4']);
  } finally {
    restoreGlobals(snapshot);
    dashboardShell.set('v3');
  }
});

test('setDashboardShell can roll back to V3 and replaces history by default without persisting', () => {
  const snapshot = snapshotGlobals();
  try {
    const { storageWrites, historyUrls } = installClientGlobals({
      pathname: '/dashboard',
      search: '?ui=v4&tab=home&section=overview',
      hash: '',
      stored: 'v4',
    });

    setDashboardShell('v3');

    assert.equal(readShell(), 'v3');
    assert.deepEqual(storageWrites, []);
    assert.deepEqual(historyUrls, ['replace:/dashboard?ui=v3&tab=home&section=overview']);
  } finally {
    restoreGlobals(snapshot);
    dashboardShell.set('v3');
  }
});

test('storage getItem/setItem, history, and document failures fail closed without throwing', () => {
  const snapshot = snapshotGlobals();
  try {
    installClientGlobals({
      search: '?ui=v4&ui_persist=1',
      stored: 'v3',
      throwGetItem: true,
      throwSetItem: true,
      throwHistory: true,
      throwDocument: true,
    });

    assert.doesNotThrow(() => initializeDashboardShell());
    assert.equal(readShell(), 'v4');
    assert.doesNotThrow(() => setDashboardShell('v3', { persist: true }));
    assert.equal(readShell(), 'v3');
  } finally {
    restoreGlobals(snapshot);
    dashboardShell.set('v3');
  }
});

test('localStorage acquisition getter failures fail closed during read and persistence', () => {
  const snapshot = snapshotGlobals();
  try {
    const { storageWrites } = installClientGlobals({
      search: '?ui=v4&ui_persist=1',
      stored: 'v3',
      throwStorageGetter: true,
    });

    assert.doesNotThrow(() => initializeDashboardShell());
    assert.equal(readShell(), 'v4');
    assert.deepEqual(storageWrites, []);
    assert.doesNotThrow(() => setDashboardShell('v3', { persist: true }));
    assert.equal(readShell(), 'v3');
    assert.deepEqual(storageWrites, []);
  } finally {
    restoreGlobals(snapshot);
    dashboardShell.set('v3');
  }
});

test('unavailable window and storage globals do not block load or local shell changes', () => {
  const snapshot = snapshotGlobals();
  try {
    for (const key of ['window', 'localStorage', 'location', 'history', 'document'] as const) {
      const descriptor = Object.getOwnPropertyDescriptor(globalThis, key);
      if (!descriptor || descriptor.configurable) {
        Object.defineProperty(globalThis, key, { configurable: true, value: undefined });
      }
    }

    assert.doesNotThrow(() => initializeDashboardShell());
    assert.equal(readShell(), 'v6');
    assert.doesNotThrow(() => setDashboardShell('v4', { persist: true }));
    assert.equal(readShell(), 'v4');
  } finally {
    restoreGlobals(snapshot);
    dashboardShell.set('v3');
  }
});
