import type { ArtifactsResponse, GpuResponse, HistoryResponse, SystemResponse, TrainingStatus } from '$lib/api';
import { adaptPromotionLocks, type PromotionLocksResult } from '../evidence';
import type { EvidenceUiState } from '../evidenceState';

export const OPS_NOT_RECORDED = 'NOT_RECORDED';
export const OPS_MISSING = 'MISSING';
export const OPS_DISCLOSURE = 'READ_ONLY_POSTURE_NOT_A_PROMOTION_CLAIM';

const STALE_AFTER_SECONDS = 120;

type UnknownRecord = Record<string, unknown>;

export interface LoadState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  loaded: boolean;
}

function asRecord(value: unknown): UnknownRecord | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? (value as UnknownRecord) : null;
}

function stringValue(value: unknown): string | null {
  if (typeof value === 'string' && value.trim() !== '') return value;
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return null;
}

function finiteNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function finitePercent(value: unknown): number | null {
  const next = finiteNumber(value);
  return next !== null && next >= 0 && next <= 100 ? next : null;
}

function normalizeStatusToken(value: unknown): string {
  const text = stringValue(value);
  if (text === null) return 'MISSING';
  return text.trim().toUpperCase().replace(/[\s-]+/g, '_');
}

function mapStatusToLifecycle(token: string): EvidenceUiState {
  if (token === 'RUNNING' || token === 'TRAINING' || token === 'ACTIVE') return 'live';
  if (token === 'COMPLETED' || token === 'COMPLETE' || token === 'DONE' || token === 'FINISHED') return 'completed';
  if (token === 'REPLAY' || token === 'REPLAYED') return 'replay';
  if (token === 'STALE' || token === 'EXPIRED' || token === 'IDLE' || token === 'PAUSED' || token === 'WAITING') return 'stale';
  return 'missing';
}

function freshnessFor(timestamp: unknown, now: number = Date.now()): string {
  const text = stringValue(timestamp);
  if (text === null) return OPS_MISSING;
  const epoch = Date.parse(text);
  if (!Number.isFinite(epoch)) return OPS_MISSING;
  const ageSeconds = Math.max(0, Math.floor((now - epoch) / 1000));
  return ageSeconds > STALE_AFTER_SECONDS ? 'STALE' : 'FRESH';
}

// ---------------------------------------------------------------------------
// Training ops evidence
// ---------------------------------------------------------------------------

export type TrainingAuthorityLevel = 'declared' | 'missing';
export type TrainingAuthoritySource = 'status' | 'history' | 'missing';

export interface TrainingAuthority {
  level: TrainingAuthorityLevel;
  label: string;
  source: TrainingAuthoritySource;
  reason: string;
}

export interface TrainingRunSnapshot {
  runName: string;
  stage: string;
  status: string;
  overallPercent: number | null;
  freshness: string;
}

export interface ModelHealthPosture {
  status: 'RECORDED' | 'NOT_RECORDED';
  checkpointReady: boolean;
  predictorStarted: boolean;
  label: string;
  message: string;
  disclosure: string;
}

export interface TrainingOpsEvidence {
  authority: TrainingAuthority;
  run: TrainingRunSnapshot;
  modelHealth: ModelHealthPosture;
  promotionLocks: PromotionLocksResult;
  lifecycleState: EvidenceUiState;
  blockers: string[];
}

function runNameSource(
  status: TrainingStatus | null,
  history: HistoryResponse | null,
): { runName: string; source: TrainingAuthoritySource } {
  const statusName = stringValue(status?.run_name);
  if (statusName !== null) return { runName: statusName, source: 'status' };
  const historyName = stringValue(history?.run_name);
  if (historyName !== null) return { runName: historyName, source: 'history' };
  return { runName: OPS_MISSING, source: 'missing' };
}

export function adaptTrainingAuthority(
  status: TrainingStatus | null | undefined,
  history: HistoryResponse | null | undefined,
): TrainingAuthority {
  const { runName, source } = runNameSource(status ?? null, history ?? null);
  if (source === 'missing') {
    return {
      level: 'missing',
      label: OPS_MISSING,
      source: 'missing',
      reason: 'Neither /api/training/status nor /api/training/history declared a run_name.',
    };
  }
  return {
    level: 'declared',
    label: runName,
    source,
    reason: `run_name declared by ${source === 'status' ? '/api/training/status' : '/api/training/history'}.`,
  };
}

function stageName(status: TrainingStatus | null): string {
  const latest = asRecord(status?.latest_stage);
  return stringValue(latest?.train_stage) ?? OPS_NOT_RECORDED;
}

function stageStatus(status: TrainingStatus | null): string {
  const latest = asRecord(status?.latest_stage);
  return stringValue(latest?.status) ?? stringValue(status?.status) ?? OPS_NOT_RECORDED;
}

export function adaptTrainingRunSnapshot(
  status: TrainingStatus | null | undefined,
  authority: TrainingAuthority,
): TrainingRunSnapshot {
  const record = status ?? null;
  return {
    runName: authority.label,
    stage: stageName(record),
    status: stageStatus(record),
    overallPercent: finitePercent(record?.overall_percent),
    freshness: freshnessFor(record?.updated_at ?? record?.generated_at ?? null),
  };
}

export function adaptModelHealth(artifacts: ArtifactsResponse | null | undefined): ModelHealthPosture {
  const record = asRecord(artifacts);
  if (!record) {
    return {
      status: 'NOT_RECORDED',
      checkpointReady: false,
      predictorStarted: false,
      label: OPS_NOT_RECORDED,
      message: 'GET /api/training/artifacts did not return a recorded payload.',
      disclosure: OPS_DISCLOSURE,
    };
  }
  return {
    status: 'RECORDED',
    checkpointReady: record.checkpoint_ready === true,
    predictorStarted: record.predictor_started === true,
    label: stringValue(record.label) ?? OPS_NOT_RECORDED,
    message: stringValue(record.message) ?? OPS_NOT_RECORDED,
    disclosure: OPS_DISCLOSURE,
  };
}

export function deriveTrainingLifecycleState(
  state: LoadState<TrainingStatus>,
): EvidenceUiState {
  if (state.loading) return 'loading';
  if (state.error) return 'error';
  if (!state.loaded) return 'loading';
  const record = asRecord(state.data);
  if (!record) return 'missing';
  const hasStages = Array.isArray(record.stages) && record.stages.length > 0;
  const hasRunName = stringValue(record.run_name) !== null;
  const statusToken = normalizeStatusToken(record.status);
  if (!hasStages && !hasRunName && statusToken === 'MISSING') return 'empty';
  return mapStatusToLifecycle(statusToken);
}

function trainingBlockers(status: TrainingStatus | null, modelHealth: ModelHealthPosture): string[] {
  const blockers: string[] = [];
  if (modelHealth.status === 'NOT_RECORDED') blockers.push('ARTIFACTS_NOT_RECORDED');
  if (!modelHealth.checkpointReady) blockers.push('CHECKPOINT_NOT_READY');
  if (!modelHealth.predictorStarted) blockers.push('PREDICTOR_NOT_STARTED');
  const readiness = asRecord(status?.readiness);
  const readinessLevel = stringValue(readiness?.level);
  if (readinessLevel !== 'ready') {
    blockers.push(`READINESS_${normalizeStatusToken(readinessLevel)}`);
  }
  return blockers.length > 0 ? blockers : [OPS_NOT_RECORDED];
}

export function adaptTrainingOpsEvidence(
  status: TrainingStatus | null | undefined,
  history: HistoryResponse | null | undefined,
  artifacts: ArtifactsResponse | null | undefined,
  statusLoadState: LoadState<TrainingStatus>,
): TrainingOpsEvidence {
  const authority = adaptTrainingAuthority(status, history);
  const run = adaptTrainingRunSnapshot(status, authority);
  const modelHealth = adaptModelHealth(artifacts);
  return {
    authority,
    run,
    modelHealth,
    promotionLocks: adaptPromotionLocks(status ?? {}),
    lifecycleState: deriveTrainingLifecycleState(statusLoadState),
    blockers: trainingBlockers(status ?? null, modelHealth),
  };
}

// ---------------------------------------------------------------------------
// System ops evidence
// ---------------------------------------------------------------------------

export type SourceAvailability = 'RECORDED' | 'NOT_RECORDED' | 'ERROR';
export type SystemSourceKey = 'gpu' | 'cpuMemory';

export interface SystemSourceEvidence {
  key: SystemSourceKey;
  label: string;
  availability: SourceAvailability;
  lifecycleState: EvidenceUiState;
  freshness: string;
  detail: string;
}

export interface GpuSnapshot {
  available: boolean;
  utilizationPercent: number | null;
  memoryUsedPercent: number | null;
  temperatureC: number | null;
  generatedAt: string;
}

export interface CpuMemorySnapshot {
  available: boolean;
  cpuUtilizationPercent: number | null;
  memoryUsedPercent: number | null;
  generatedAt: string;
}

export interface SystemOpsEvidence {
  sources: readonly SystemSourceEvidence[];
  gpu: GpuSnapshot;
  cpuMemory: CpuMemorySnapshot;
  promotionLocks: PromotionLocksResult;
}

export function adaptGpuSnapshot(gpu: GpuResponse | null | undefined): GpuSnapshot {
  const record = asRecord(gpu);
  const gpusList = Array.isArray(record?.gpus) ? record.gpus : [];
  const first = asRecord(gpusList[0]);
  return {
    available: record?.available === true,
    utilizationPercent: finitePercent(first?.utilization_gpu_percent),
    memoryUsedPercent: finitePercent(first?.memory_used_percent),
    temperatureC: finiteNumber(first?.temperature_c),
    generatedAt: stringValue(record?.generated_at) ?? OPS_MISSING,
  };
}

export function adaptCpuMemorySnapshot(system: SystemResponse | null | undefined): CpuMemorySnapshot {
  const record = asRecord(system);
  const cpu = asRecord(record?.cpu);
  const memory = asRecord(record?.memory);
  return {
    available: record?.available === true,
    cpuUtilizationPercent: finitePercent(cpu?.utilization_percent),
    memoryUsedPercent: finitePercent(memory?.used_percent),
    generatedAt: stringValue(record?.generated_at) ?? OPS_MISSING,
  };
}

function sourceAvailability<T>(state: LoadState<T>): SourceAvailability {
  if (state.error) return 'ERROR';
  if (state.data !== null && state.data !== undefined) return 'RECORDED';
  return 'NOT_RECORDED';
}

function sourceLifecycleState<T>(state: LoadState<T>, availability: SourceAvailability, freshness: string): EvidenceUiState {
  if (state.loading) return 'loading';
  if (availability === 'ERROR') return 'error';
  if (!state.loaded) return 'loading';
  if (availability === 'NOT_RECORDED') return 'missing';
  if (freshness === 'STALE') return 'stale';
  if (freshness === OPS_MISSING) return 'missing';
  return 'live';
}

export function adaptSystemOpsEvidence(
  gpu: GpuResponse | null | undefined,
  gpuState: LoadState<GpuResponse>,
  system: SystemResponse | null | undefined,
  systemState: LoadState<SystemResponse>,
): SystemOpsEvidence {
  const gpuSnapshot = adaptGpuSnapshot(gpu);
  const cpuMemorySnapshot = adaptCpuMemorySnapshot(system);
  const gpuAvailability = sourceAvailability(gpuState);
  const systemAvailability = sourceAvailability(systemState);
  const gpuFreshness = freshnessFor(gpuSnapshot.generatedAt);
  const systemFreshness = freshnessFor(cpuMemorySnapshot.generatedAt);

  const sources: SystemSourceEvidence[] = [
    {
      key: 'gpu',
      label: 'GPU telemetry',
      availability: gpuAvailability,
      lifecycleState: sourceLifecycleState(gpuState, gpuAvailability, gpuFreshness),
      freshness: gpuFreshness,
      detail: gpuState.error ?? (gpuSnapshot.available ? 'GET /api/training/gpu' : 'GPU_NOT_AVAILABLE'),
    },
    {
      key: 'cpuMemory',
      label: 'CPU / memory telemetry',
      availability: systemAvailability,
      lifecycleState: sourceLifecycleState(systemState, systemAvailability, systemFreshness),
      freshness: systemFreshness,
      detail: systemState.error ?? (cpuMemorySnapshot.available ? 'GET /api/training/system' : 'SYSTEM_NOT_AVAILABLE'),
    },
  ];

  return {
    sources,
    gpu: gpuSnapshot,
    cpuMemory: cpuMemorySnapshot,
    promotionLocks: adaptPromotionLocks({}),
  };
}
