import assert from 'node:assert/strict';
import { test } from 'node:test';

import type * as EvidenceState from './evidenceState';

const evidenceStatePath = ['.', 'evidenceState.ts'].join('/');
const {
  EVIDENCE_UI_STATES,
  evidenceStateMeta,
  normalizeEvidenceState,
}: typeof EvidenceState = await import(evidenceStatePath);

test('normalizeEvidenceState accepts every canonical state unchanged', () => {
  for (const state of EVIDENCE_UI_STATES) {
    assert.equal(normalizeEvidenceState(state), state);
  }
});

test('normalizeEvidenceState fails closed to missing for unknown input', () => {
  for (const source of ['unknown', 'LIVE', '', null, undefined, false, 0, {}, []]) {
    assert.equal(normalizeEvidenceState(source), 'missing');
  }
});

test('evidenceStateMeta returns deterministic Korean-first metadata for every state', () => {
  const expected = {
    loading: { label: '로딩', tone: 'neutral', blocking: true, showContent: false },
    empty: { label: '비어 있음', tone: 'neutral', blocking: true, showContent: false },
    error: { label: '오류', tone: 'danger', blocking: true, showContent: false },
    stale: { label: '오래됨', tone: 'warning', blocking: true, showContent: true },
    live: { label: '실시간', tone: 'info', blocking: false, showContent: true },
    replay: { label: '리플레이', tone: 'info', blocking: false, showContent: true },
    completed: { label: '완료', tone: 'positive', blocking: false, showContent: true },
    missing: { label: '누락', tone: 'danger', blocking: true, showContent: false },
    'no-go': { label: 'NO-GO', tone: 'danger', blocking: true, showContent: true },
  } as const;

  for (const state of EVIDENCE_UI_STATES) {
    assert.deepEqual(
      {
        label: evidenceStateMeta(state).label,
        tone: evidenceStateMeta(state).tone,
        blocking: evidenceStateMeta(state).blocking,
        showContent: evidenceStateMeta(state).showContent,
      },
      expected[state],
    );
    assert.equal(evidenceStateMeta(state).state, state);
    assert.ok(evidenceStateMeta(state).title.length > 0);
    assert.ok(evidenceStateMeta(state).detail.length > 0);
    assert.ok(evidenceStateMeta(state).statusText.length > 0);
  }
});

test('evidenceStateMeta never labels unknown or missing input as live', () => {
  assert.equal(evidenceStateMeta('not-live').state, 'missing');
  assert.equal(evidenceStateMeta('not-live').label, '누락');
  assert.equal(evidenceStateMeta(undefined).state, 'missing');
  assert.notEqual(evidenceStateMeta(undefined).label, '실시간');
});
