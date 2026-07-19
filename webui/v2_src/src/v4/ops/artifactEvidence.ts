import type { ArtifactsResponse, HistoryResponse, TrainingStatus } from '$lib/api';
import {
  adaptEvidenceIdentity,
  adaptPromotionLocks,
  adaptRunEvidence,
  type EvidenceIdentity,
  type PromotionLocksResult,
  type RunEvidence,
} from '../evidence';

export const NOT_RECORDED = 'NOT_RECORDED';

type UnknownRecord = Record<string, unknown>;

function asRecord(value: unknown): UnknownRecord | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? (value as UnknownRecord) : null;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function stringValue(value: unknown): string | null {
  return typeof value === 'string' && value.trim() !== '' ? value : null;
}

function finiteNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function finiteNonNegativeInteger(value: unknown): number | null {
  const next = finiteNumber(value);
  return next !== null && Number.isInteger(next) && next >= 0 ? next : null;
}

// ─────────────────────────── Artifacts ───────────────────────────

export type ArtifactCategory = 'checkpoint' | 'pretrained_weight' | 'predictor_output';
export type ArtifactCollectionStatus = 'recorded' | 'empty' | 'not_recorded';
export type BooleanSourceStatus = 'declared' | 'missing' | 'invalid';

export interface ArtifactFileEvidence {
  category: ArtifactCategory;
  name: string;
  path: string;
  sizeLabel: string;
  modifiedLabel: string;
  hash: string;
  authority: string;
}

export interface ArtifactCategoryEvidence {
  status: ArtifactCollectionStatus;
  declaredCount: number | null;
  files: readonly ArtifactFileEvidence[];
}

export interface BooleanAuthority {
  declared: boolean;
  sourceStatus: BooleanSourceStatus;
}

export interface ArtifactsEvidence {
  status: ArtifactCollectionStatus;
  checkpoints: ArtifactCategoryEvidence;
  pretrainedWeights: ArtifactCategoryEvidence;
  predictorOutputs: ArtifactCategoryEvidence;
  checkpointReady: BooleanAuthority;
  predictorStarted: BooleanAuthority;
  predictorComplete: BooleanAuthority;
  label: string;
  message: string;
  promotionLocks: PromotionLocksResult;
}

const SHA256_PATTERN = /^[a-f0-9]{64}$/i;

function fileEntryPath(entry: unknown): string {
  if (typeof entry === 'string' && entry.trim() !== '') {
    return entry;
  }
  const record = asRecord(entry);
  return stringValue(record?.path) ?? stringValue(record?.name) ?? NOT_RECORDED;
}

function fileEntryName(entry: unknown): string {
  const path = fileEntryPath(entry);
  if (path === NOT_RECORDED) {
    return NOT_RECORDED;
  }
  const segments = path.split(/[/\\]/).filter((segment) => segment !== '');
  return segments.length > 0 ? segments[segments.length - 1] : path;
}

function fileEntrySizeLabel(entry: unknown): string {
  const record = asRecord(entry);
  if (!record) {
    return NOT_RECORDED;
  }
  const sizeMib = finiteNumber(record.size_mib);
  if (sizeMib !== null && sizeMib >= 0) {
    return `${sizeMib.toFixed(2)} MiB`;
  }
  const sizeBytes = finiteNumber(record.size);
  if (sizeBytes !== null && sizeBytes >= 0) {
    return `${(sizeBytes / (1024 * 1024)).toFixed(2)} MiB`;
  }
  return NOT_RECORDED;
}

function fileEntryModifiedLabel(entry: unknown): string {
  const record = asRecord(entry);
  return stringValue(record?.modified) ?? stringValue(record?.mtime) ?? stringValue(record?.modified_at) ?? NOT_RECORDED;
}

function fileEntryHash(entry: unknown): string {
  const record = asRecord(entry);
  const candidate = stringValue(record?.sha256) ?? stringValue(record?.hash) ?? stringValue(record?.digest);
  return candidate !== null && SHA256_PATTERN.test(candidate) ? candidate.toLowerCase() : NOT_RECORDED;
}

function fileEntryAuthority(entry: unknown): string {
  const record = asRecord(entry);
  return stringValue(record?.authority) ?? stringValue(record?.provenance) ?? stringValue(record?.source_authority) ?? NOT_RECORDED;
}

function declaredCategoryHint(entry: unknown): string | null {
  const record = asRecord(entry);
  const hint = stringValue(record?.category) ?? stringValue(record?.artifact_category) ?? stringValue(record?.stage);
  return hint ? hint.trim().toLowerCase() : null;
}

function isPredictorEntry(entry: unknown): boolean {
  const hint = declaredCategoryHint(entry);
  if (hint !== null) {
    return hint.includes('predictor');
  }
  const path = fileEntryPath(entry);
  return path !== NOT_RECORDED && /predictor/i.test(path);
}

function buildFileEvidence(entry: unknown, category: ArtifactCategory): ArtifactFileEvidence {
  return {
    category,
    name: fileEntryName(entry),
    path: fileEntryPath(entry),
    sizeLabel: fileEntrySizeLabel(entry),
    modifiedLabel: fileEntryModifiedLabel(entry),
    hash: fileEntryHash(entry),
    authority: fileEntryAuthority(entry),
  };
}

function buildCategoryEvidence(
  payloadPresent: boolean,
  declaredCountRaw: unknown,
  rawEntries: unknown,
  category: ArtifactCategory,
  include: (entry: unknown) => boolean,
): ArtifactCategoryEvidence {
  if (!payloadPresent) {
    return { status: 'not_recorded', declaredCount: null, files: [] };
  }
  const files = asArray(rawEntries)
    .filter(include)
    .map((entry) => buildFileEvidence(entry, category));
  return {
    status: files.length > 0 ? 'recorded' : 'empty',
    declaredCount: finiteNonNegativeInteger(declaredCountRaw),
    files,
  };
}

function mergeCategoryEvidence(payloadPresent: boolean, parts: readonly ArtifactCategoryEvidence[]): ArtifactCategoryEvidence {
  if (!payloadPresent) {
    return { status: 'not_recorded', declaredCount: null, files: [] };
  }
  const files = parts.flatMap((part) => part.files);
  return { status: files.length > 0 ? 'recorded' : 'empty', declaredCount: null, files };
}

function booleanAuthority(record: UnknownRecord | null, key: string): BooleanAuthority {
  if (!record || !(key in record)) {
    return { declared: false, sourceStatus: 'missing' };
  }
  const value = record[key];
  if (typeof value === 'boolean') {
    return { declared: value, sourceStatus: 'declared' };
  }
  return { declared: false, sourceStatus: 'invalid' };
}

export function normalizeArtifactsEvidence(payload: ArtifactsResponse | UnknownRecord | null | undefined): ArtifactsEvidence {
  const record = asRecord(payload);
  const payloadPresent = record !== null;
  const stagesRecord = asRecord(record?.stages);
  const predictorStage = asRecord(stagesRecord?.predictor);

  const checkpoints = buildCategoryEvidence(
    payloadPresent,
    record?.checkpoint_file_count,
    record?.recent_checkpoint_files,
    'checkpoint',
    (entry) => !isPredictorEntry(entry),
  );

  const predictorFromCheckpoints = buildCategoryEvidence(
    payloadPresent,
    null,
    record?.recent_checkpoint_files,
    'predictor_output',
    (entry) => isPredictorEntry(entry),
  );

  const predictorFromDeclaredList = buildCategoryEvidence(
    payloadPresent,
    null,
    record?.recent_predictor_output_files,
    'predictor_output',
    () => true,
  );

  const predictorOutputs = mergeCategoryEvidence(payloadPresent, [predictorFromCheckpoints, predictorFromDeclaredList]);

  const pretrainedWeights = buildCategoryEvidence(
    payloadPresent,
    record?.model_weight_file_count,
    record?.recent_model_weight_files,
    'pretrained_weight',
    () => true,
  );

  const totalFiles = checkpoints.files.length + pretrainedWeights.files.length + predictorOutputs.files.length;

  return {
    status: !payloadPresent ? 'not_recorded' : totalFiles > 0 ? 'recorded' : 'empty',
    checkpoints,
    pretrainedWeights,
    predictorOutputs,
    checkpointReady: booleanAuthority(record, 'checkpoint_ready'),
    predictorStarted: booleanAuthority(record, 'predictor_started'),
    predictorComplete: booleanAuthority(predictorStage, 'checkpoint_ready'),
    label: stringValue(record?.label) ?? NOT_RECORDED,
    message: stringValue(record?.message) ?? NOT_RECORDED,
    promotionLocks: adaptPromotionLocks(record),
  };
}

// ─────────────────────────── Runs ───────────────────────────

export type RunAuthorityLevel = 'canonical' | 'declared' | 'missing';
export type RunAuthoritySource = 'status' | 'history' | 'missing';

export interface RunAuthority {
  level: RunAuthorityLevel;
  source: RunAuthoritySource;
  label: string;
  reason: string;
}

export interface RunSnapshotEvidence {
  identity: EvidenceIdentity;
  run: RunEvidence;
  authority: RunAuthority;
  stage: string;
  statusLabel: string;
}

function deriveRunAuthority(status: unknown, history: unknown): RunAuthority {
  const statusRunName = stringValue(asRecord(status)?.run_name);
  const historyRunName = stringValue(asRecord(history)?.run_name);
  if (statusRunName !== null) {
    return {
      level: 'canonical',
      source: 'status',
      label: 'CANONICAL_STATUS',
      reason: 'training status payload declares run_name',
    };
  }
  if (historyRunName !== null) {
    return {
      level: 'declared',
      source: 'history',
      label: 'DECLARED_HISTORY',
      reason: 'training history payload declares run_name without status confirmation',
    };
  }
  return {
    level: 'missing',
    source: 'missing',
    label: 'MISSING',
    reason: 'no run_name declared by status or history payloads',
  };
}

function deriveStage(status: unknown, history: unknown): string {
  const statusRecord = asRecord(status);
  const latest = asRecord(statusRecord?.latest_stage);
  const stagesArray = Array.isArray(statusRecord?.stages) ? statusRecord?.stages : [];
  const lastStage = asRecord(stagesArray?.[stagesArray.length - 1]);
  const historyRecord = asRecord(history);
  return (
    stringValue(latest?.train_stage) ??
    stringValue(lastStage?.train_stage) ??
    stringValue(historyRecord?.stage) ??
    'STAGE_NOT_RECORDED'
  );
}

export function adaptRunSnapshot(
  status: TrainingStatus | UnknownRecord | null | undefined,
  history: HistoryResponse | UnknownRecord | null | undefined,
  meta: { source_endpoint?: string } = {},
): RunSnapshotEvidence {
  const sourceEndpoint = meta.source_endpoint ?? '/api/training/status';
  const statusRecord = asRecord(status) ?? {};
  const historyRecord = asRecord(history) ?? {};
  const merged: UnknownRecord = { ...historyRecord, ...statusRecord };
  if (merged.run_id === undefined && merged.id === undefined && merged.name === undefined) {
    const runNameCandidate = stringValue(statusRecord.run_name) ?? stringValue(historyRecord.run_name);
    if (runNameCandidate !== null) {
      merged.name = runNameCandidate;
    }
  }
  const run = adaptRunEvidence(merged, { source_endpoint: sourceEndpoint });
  const identity = adaptEvidenceIdentity(merged, { source_endpoint: sourceEndpoint });
  const authority = deriveRunAuthority(status, history);
  const stage = deriveStage(status, history);
  const statusLabel = stringValue(statusRecord.status) ?? run.lifecycle;
  return { identity, run, authority, stage, statusLabel };
}
