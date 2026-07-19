export const FORECAST_LIMITS = {
  lookback: { min: 1, max: 4096 },
  predLen: { min: 1, max: 1024 },
  sampleCount: { min: 1, max: 16 },
  temperature: { min: 0.1, max: 2 },
  topP: { min: 0.1, max: 1 },
} as const;

export type ForecastDevice = 'cpu' | 'cuda';

export interface ForecastPredictPayload {
  file_path: string;
  sample_count: number;
  lookback: number;
  pred_len: number;
  temperature: number;
  top_p: number;
  device: ForecastDevice;
  seed?: number;
}
export interface ForecastPoint {
  timestamp: string;
  close: number;
}

export interface ForecastPredictionResponse {
  success: true;
  prediction_type: string;
  prediction_results: ForecastPoint[];
  actual_data: ForecastPoint[];
  has_comparison: boolean;
  message: string;
}

export interface ForecastPredictInput {
  selectedModel: unknown;
  availableModels: unknown;
  modelLoaded: boolean;
  selectedDataFile: unknown;
  dataFiles: readonly unknown[];
  dataLoaded: boolean;
  lookback: unknown;
  predLen: unknown;
  sampleCount: unknown;
  temperature: unknown;
  topP: unknown;
  seedFixed: boolean;
  seed: unknown;
  device: unknown;
}

export type ForecastValidationResult<T> =
  | { ok: true; value: T }
  | { ok: false; error: string };

type ModelCatalog = Record<string, unknown>;

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function dataFilePath(file: unknown): string | null {
  if (typeof file === 'string') return file;
  if (!isRecord(file)) return null;
  const path = file.path ?? file.name;
  return typeof path === 'string' ? path : null;
}

function integerInRange(value: unknown, label: string, min: number, max: number): ForecastValidationResult<number> {
  if (typeof value !== 'number' || !Number.isInteger(value)) {
    return { ok: false, error: `${label} must be an integer between ${min} and ${max}.` };
  }
  if (value < min || value > max) {
    return { ok: false, error: `${label} must be between ${min} and ${max}.` };
  }
  return { ok: true, value };
}
function numberInRange(value: unknown, label: string, min: number, max: number): ForecastValidationResult<number> {
  const finite = finiteNumber(value, label);
  if (finite.ok === false) return finite;
  if (finite.value < min || finite.value > max) {
    return { ok: false, error: `${label} must be between ${min} and ${max}.` };
  }
  return finite;
}

function forecastPoint(value: unknown, label: string): ForecastValidationResult<ForecastPoint> {
  if (!isRecord(value) || typeof value.timestamp !== 'string' || value.timestamp.trim() === '') {
    return { ok: false, error: `${label} must contain a recorded timestamp.` };
  }
  if (typeof value.close !== 'number' || !Number.isFinite(value.close)) {
    return { ok: false, error: `${label} must contain a finite close value.` };
  }
  return { ok: true, value: { timestamp: value.timestamp, close: value.close } };
}

function forecastPoints(value: unknown, label: string): ForecastValidationResult<ForecastPoint[]> {
  if (!Array.isArray(value)) return { ok: false, error: `${label} must be an array.` };
  const points: ForecastPoint[] = [];
  for (let index = 0; index < value.length; index += 1) {
    const point = forecastPoint(value[index], `${label}[${index}]`);
    if (point.ok === false) return point;
    points.push(point.value);
  }
  return { ok: true, value: points };
}

export function validateForecastPredictionResponse(value: unknown): ForecastValidationResult<ForecastPredictionResponse> {
  if (!isRecord(value) || value.success !== true) {
    return { ok: false, error: 'Prediction response must declare success=true.' };
  }
  if (typeof value.prediction_type !== 'string' || value.prediction_type.trim() === '') {
    return { ok: false, error: 'Prediction response is missing prediction_type.' };
  }
  if (typeof value.has_comparison !== 'boolean' || typeof value.message !== 'string') {
    return { ok: false, error: 'Prediction response is missing comparison/message metadata.' };
  }
  const predicted = forecastPoints(value.prediction_results, 'prediction_results');
  if (predicted.ok === false) return predicted;
  if (predicted.value.length === 0) {
    return { ok: false, error: 'prediction_results must contain at least one recorded point.' };
  }
  const actual = forecastPoints(value.actual_data, 'actual_data');
  if (actual.ok === false) return actual;
  if (value.has_comparison !== (actual.value.length > 0)) {
    return { ok: false, error: 'has_comparison must match recorded actual_data.' };
  }
  return {
    ok: true,
    value: {
      success: true,
      prediction_type: value.prediction_type,
      prediction_results: predicted.value,
      actual_data: actual.value,
      has_comparison: value.has_comparison,
      message: value.message,
    },
  };
}

function finiteNumber(value: unknown, label: string): ForecastValidationResult<number> {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return { ok: false, error: `${label} must be a finite number.` };
  }
  return { ok: true, value };
}

export function validateForecastDevice(device: unknown): ForecastValidationResult<ForecastDevice> {
  if (device === 'cpu' || device === 'cuda') return { ok: true, value: device };
  return { ok: false, error: 'device must be cpu or cuda.' };
}

export function validateForecastModelKey(selectedModel: unknown, availableModels: unknown): ForecastValidationResult<string> {
  if (typeof selectedModel !== 'string' || selectedModel.trim().length === 0) {
    return { ok: false, error: 'Select a forecast model before loading or predicting.' };
  }
  const catalog: ModelCatalog = isRecord(availableModels) ? availableModels : {};
  if (!Object.prototype.hasOwnProperty.call(catalog, selectedModel)) {
    return { ok: false, error: `Selected model key is not available: ${selectedModel}` };
  }
  return { ok: true, value: selectedModel };
}

export function validateForecastFilePath(selectedDataFile: unknown, dataFiles: readonly unknown[]): ForecastValidationResult<string> {
  if (typeof selectedDataFile !== 'string' || selectedDataFile.trim().length === 0) {
    return { ok: false, error: 'Select a non-empty data file before loading or predicting.' };
  }
  const approvedPaths = new Set(dataFiles.map(dataFilePath).filter((path): path is string => typeof path === 'string'));
  if (!approvedPaths.has(selectedDataFile)) {
    return { ok: false, error: `Selected data file is not in the approved catalog: ${selectedDataFile}` };
  }
  return { ok: true, value: selectedDataFile };
}

export function validateForecastModelSelection(
  selectedModel: unknown,
  availableModels: unknown,
  device: unknown,
): ForecastValidationResult<{ modelKey: string; device: ForecastDevice }> {
  const modelKey = validateForecastModelKey(selectedModel, availableModels);
  if (modelKey.ok === false) return modelKey;
  const selectedDevice = validateForecastDevice(device);
  if (selectedDevice.ok === false) return selectedDevice;
  return { ok: true, value: { modelKey: modelKey.value, device: selectedDevice.value } };
}

export function validateForecastDataSelection(
  selectedDataFile: unknown,
  dataFiles: readonly unknown[],
): ForecastValidationResult<string> {
  return validateForecastFilePath(selectedDataFile, dataFiles);
}

export function buildForecastPredictPayload(input: ForecastPredictInput): ForecastValidationResult<ForecastPredictPayload> {
  const model = validateForecastModelSelection(input.selectedModel, input.availableModels, input.device);
  if (model.ok === false) return model;
  if (!input.modelLoaded) return { ok: false, error: 'Load the selected forecast model before predicting.' };

  const filePath = validateForecastFilePath(input.selectedDataFile, input.dataFiles);
  if (filePath.ok === false) return filePath;
  if (!input.dataLoaded) return { ok: false, error: 'Load the selected data file before predicting.' };

  const lookback = integerInRange(input.lookback, 'lookback', FORECAST_LIMITS.lookback.min, FORECAST_LIMITS.lookback.max);
  if (lookback.ok === false) return lookback;
  const predLen = integerInRange(input.predLen, 'pred_len', FORECAST_LIMITS.predLen.min, FORECAST_LIMITS.predLen.max);
  if (predLen.ok === false) return predLen;
  const sampleCount = integerInRange(input.sampleCount, 'sample_count', FORECAST_LIMITS.sampleCount.min, FORECAST_LIMITS.sampleCount.max);
  if (sampleCount.ok === false) return sampleCount;
  const temperature = numberInRange(input.temperature, 'temperature', FORECAST_LIMITS.temperature.min, FORECAST_LIMITS.temperature.max);
  if (temperature.ok === false) return temperature;
  const topP = numberInRange(input.topP, 'top_p', FORECAST_LIMITS.topP.min, FORECAST_LIMITS.topP.max);
  if (topP.ok === false) return topP;

  const payload: ForecastPredictPayload = {
    file_path: filePath.value,
    sample_count: sampleCount.value,
    lookback: lookback.value,
    pred_len: predLen.value,
    temperature: temperature.value,
    top_p: topP.value,
    device: model.value.device,
  };

  if (input.seedFixed) {
    const seed = integerInRange(input.seed, 'seed', 0, 2147483647);
    if (seed.ok === false) return seed;
    payload.seed = seed.value;
  }

  return { ok: true, value: payload };
}
