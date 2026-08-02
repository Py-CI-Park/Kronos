import assert from 'node:assert/strict';
import test from 'node:test';
import {
  classifyV6ModelStatus,
  getV6Runs,
  insightQuickPickCodes,
  nextDraftPresentation,
  observedV6TrainingState,
  type1TrainingSummary,
  v6ProjectReportHtmlUrl,
  v6ReportHtmlUrl,
} from './v6Api';

test('Type1 run summary exposes model counts without opening heavy detail', () => {
  assert.deepEqual(type1TrainingSummary({
    state: 'COMPLETE',
    training_state: 'COMPLETE',
    seed_counts: { primary: 5, shuffled_reward: 5 },
    timesteps_per_seed: 200_000,
  }), {
    state: 'COMPLETE',
    primarySeedCount: 5,
    shuffledSeedCount: 5,
    timestepsPerSeed: 200_000,
  });
});

test('training completion uses lifecycle state instead of transport status', () => {
  assert.equal(observedV6TrainingState(
    { status: 'OK', state: 'COMPLETE', manifest: { training_state: 'COMPLETE' } },
    { state: 'MISSING' },
    'NOT_RUN',
  ), 'COMPLETE');
  assert.equal(observedV6TrainingState(
    { status: 'OK', manifest: { training_state: 'COMPLETE' } },
    { state: 'MISSING' },
    'NOT_RUN',
  ), 'COMPLETE');
});

test('concurrent runs readers share one integrity request but later reads refresh', async () => {
  const originalFetch = globalThis.fetch;
  let calls = 0;
  let release: (() => void) | undefined;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  globalThis.fetch = async () => {
    calls += 1;
    await gate;
    return new Response(JSON.stringify({ status: 'OK', runs: [] }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  };
  try {
    const first = getV6Runs();
    const second = getV6Runs();
    await Promise.resolve();
    assert.equal(calls, 1);
    release?.();
    await Promise.all([first, second]);
    await getV6Runs();
    assert.equal(calls, 2);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('project report URL separates inline viewing from download', () => {
  assert.equal(
    v6ProjectReportHtmlUrl('project id/한글'),
    '/api/v6/project-report-html?project=project%20id%2F%ED%95%9C%EA%B8%80',
  );
  assert.equal(
    v6ProjectReportHtmlUrl('project id/한글', true),
    '/api/v6/project-report-html?project=project%20id%2F%ED%95%9C%EA%B8%80&download=1',
  );
});

test('single-run report URL keeps the same view and download contract', () => {
  assert.equal(
    v6ReportHtmlUrl('dataset 1', 'train/1'),
    '/api/v6/report-html?dataset=dataset%201&train=train%2F1',
  );
  assert.equal(
    v6ReportHtmlUrl('dataset 1', 'train/1', true),
    '/api/v6/report-html?dataset=dataset%201&train=train%2F1&download=1',
  );
});

test('next preregistration distinguishes an empty queue from missing API fields', () => {
  const presentation = nextDraftPresentation({
    status: 'OK',
    preregistrations: [
      { prereg_id: 'KRONOS-V8', status: 'FROZEN', frozen_utc: '2026-07-21T00:00:00Z' },
      { prereg_id: 'KRONOS-V7', status: 'FROZEN', frozen_utc: '2026-07-20T00:00:00Z' },
    ],
  });

  assert.deepEqual(presentation, {
    kind: 'empty',
    frozenCount: 2,
    latestFrozenId: 'KRONOS-V8',
  });
});

test('insight quick picks expose several valid symbols without duplicates', () => {
  const codes = insightQuickPickCodes({
    top_inst_buy: [{ code: '005930' }, { code: '000660' }],
    top_inst_sell: [{ code: '005930' }, { code: '035420' }],
    top_foreign_gain: [{ code: 'bad' }, { code: '000660' }],
  }, 8);

  assert.deepEqual(codes, ['005930', '000660', '035420']);
});

test('Kronos model status separates availability from eager loading', () => {
  assert.deepEqual(
    classifyV6ModelStatus({ available: true, loaded: false }),
    { state: 'AVAILABLE_NOT_LOADED', label: '사용 가능 · 아직 미로드' },
  );
  assert.deepEqual(
    classifyV6ModelStatus({ available: true, loaded: true }),
    { state: 'LOADED', label: '로드됨' },
  );
});
