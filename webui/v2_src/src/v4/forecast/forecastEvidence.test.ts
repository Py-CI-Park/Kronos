import assert from 'node:assert/strict';
import { test } from 'node:test';
import type * as ForecastEvidence from './forecastEvidence';

const evidencePath = ['./forecastEvidence.ts'].join('/');
const {
  FORECAST_LIMITS,
  buildForecastPredictPayload,
  validateForecastDevice,
  validateForecastPredictionResponse,
}: typeof ForecastEvidence = await import(evidencePath);

const models = { mini: { name: 'Mini' }, base: { name: 'Base' } };
const files = ['data/000123/series.csv', { path: 'data/research/kline.csv', name: 'kline.csv' }];

function validInput(overrides: Partial<ForecastEvidence.ForecastPredictInput> = {}): ForecastEvidence.ForecastPredictInput {
  return {
    selectedModel: 'mini',
    availableModels: models,
    modelLoaded: true,
    selectedDataFile: 'data/000123/series.csv',
    dataFiles: files,
    dataLoaded: true,
    lookback: 400,
    predLen: 120,
    sampleCount: 1,
    temperature: 1,
    topP: 0.9,
    seedFixed: true,
    seed: 42,
    device: 'cpu',
    ...overrides,
  };
}

test('builds valid /api/predict payload without legacy n_samples', () => {
  const result = buildForecastPredictPayload(validInput({ sampleCount: 16, device: 'cuda' }));
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.deepEqual(result.value, {
    file_path: 'data/000123/series.csv',
    sample_count: 16,
    lookback: 400,
    pred_len: 120,
    temperature: 1,
    top_p: 0.9,
    seed: 42,
    device: 'cuda',
  });
  assert.equal(Object.prototype.hasOwnProperty.call(result.value, 'n_samples'), false);
});

test('preserves exact file_path text including leading-zero-like segments', () => {
  const path = 'research/000001/000007.csv';
  const result = buildForecastPredictPayload(validInput({ selectedDataFile: path, dataFiles: [path] }));
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.value.file_path, path);
});

test('accepts exact lower and upper boundaries independently', () => {
  for (const overrides of [
    { lookback: FORECAST_LIMITS.lookback.min },
    { lookback: FORECAST_LIMITS.lookback.max },
    { predLen: FORECAST_LIMITS.predLen.min },
    { predLen: FORECAST_LIMITS.predLen.max },
    { sampleCount: FORECAST_LIMITS.sampleCount.min },
    { sampleCount: FORECAST_LIMITS.sampleCount.max },
    { temperature: FORECAST_LIMITS.temperature.min },
    { temperature: FORECAST_LIMITS.temperature.max },
    { topP: FORECAST_LIMITS.topP.min },
    { topP: FORECAST_LIMITS.topP.max },
  ]) {
    const result = buildForecastPredictPayload(validInput(overrides));
    assert.equal(result.ok, true, JSON.stringify(overrides));
  }
});

test('rejects values outside every boundary', () => {
  for (const overrides of [
    { lookback: 0 },
    { lookback: 4097 },
    { predLen: 0 },
    { predLen: 1025 },
    { sampleCount: 0 },
    { sampleCount: 17 },
    { temperature: 0.09 },
    { temperature: 2.01 },
    { topP: 0.09 },
    { topP: 1.01 },
  ]) {
    const result = buildForecastPredictPayload(validInput(overrides));
    assert.equal(result.ok, false, JSON.stringify(overrides));
  }
});

test('rejects strings and non-integer numeric caps', () => {
  for (const overrides of [
    { lookback: '400' },
    { predLen: '120' },
    { sampleCount: '1' },
    { lookback: 1.5 },
    { predLen: 2.25 },
    { sampleCount: 1.1 },
  ]) {
    const result = buildForecastPredictPayload(validInput(overrides));
    assert.equal(result.ok, false, JSON.stringify(overrides));
  }
});

test('rejects missing or unloaded model/data before payload construction', () => {
  for (const overrides of [
    { selectedModel: '' },
    { selectedModel: 'missing' },
    { modelLoaded: false },
    { selectedDataFile: '' },
    { selectedDataFile: 'unapproved.csv' },
    { dataLoaded: false },
  ]) {
    const result = buildForecastPredictPayload(validInput(overrides));
    assert.equal(result.ok, false, JSON.stringify(overrides));
  }
});

test('rejects invalid device values', () => {
  assert.deepEqual(validateForecastDevice('cpu'), { ok: true, value: 'cpu' });
  assert.deepEqual(validateForecastDevice('cuda'), { ok: true, value: 'cuda' });
  assert.equal(validateForecastDevice('gpu').ok, false);
  assert.equal(buildForecastPredictPayload(validInput({ device: 'gpu' })).ok, false);
});

test('accepts only the documented /api/predict response schema', () => {
  const valid = validateForecastPredictionResponse({
    success: true,
    prediction_type: 'Kronos model forecast',
    prediction_results: [{ timestamp: '2026-01-01T09:00:00', close: 101.5 }],
    actual_data: [{ timestamp: '2026-01-01T09:00:00', close: 100.5 }],
    has_comparison: true,
    message: 'complete',
  });
  assert.equal(valid.ok, true);

  for (const malformed of [
    { success: true, predicted: [{ timestamp: '2026-01-01', close: 1 }], actual: [] },
    { success: true, prediction_type: 'x', prediction_results: [], actual_data: [], has_comparison: false, message: 'x' },
    { success: true, prediction_type: 'x', prediction_results: [{ timestamp: '2026-01-01', close: 1 }], actual_data: [], has_comparison: true, message: 'x' },
    { success: true, prediction_type: 'x', prediction_results: [{ timestamp: '2026-01-01', close: 1 }], actual_data: [{ timestamp: '2026-01-01', close: 1 }], has_comparison: false, message: 'x' },
    { success: true, prediction_type: 'x', prediction_results: [{ timestamp: '', close: 1 }], actual_data: [], has_comparison: false, message: 'x' },
    { success: true, prediction_type: 'x', prediction_results: [{ timestamp: '2026-01-01', close: Number.NaN }], actual_data: [], has_comparison: false, message: 'x' },
  ]) {
    assert.equal(validateForecastPredictionResponse(malformed).ok, false);
  }
});
