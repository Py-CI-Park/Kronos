import type {
  JsonObject,
  RlProgressResponse,
  RlRliableStatsResponse,
  RlRunDetail,
  RlRunRecord,
  RlTableRow,
} from '$lib/rlApi';
import { adaptMetricValue, adaptRunEvidence, PROMOTION_LOCK_KEYS, type MetricValue, type RunEvidence } from '../evidence';

export type RlEvidenceLaneKind = 'RULE' | 'RL' | 'SUPERVISED_GATE' | 'EVIDENCE';

export interface RlEvidenceLane {
  kind: RlEvidenceLaneKind;
  label: string;
  isRl: boolean;
  posture: 'baseline_not_rl' | 'research_only_rl' | 'supervised_gate_not_rl' | 'audit_evidence';
  reason: string;
}

export interface CockpitMetric {
  key: string;
  label: string;
  metric: MetricValue;
  display: string;
  behavior: 'recorded' | 'not_recorded' | 'incompatible_unit' | 'inapplicable';
}

export interface CockpitMetadata {
  key: string;
  label: string;
  value: string;
  source: string;
  behavior: 'recorded' | 'not_recorded';
}

export interface RlCockpitEvidence {
  run: RunEvidence;
  lane: RlEvidenceLane;
  metrics: readonly CockpitMetric[];
  metadata: readonly CockpitMetadata[];
  neverTradeStatus: 'NEVER_TRADE' | 'TRADED' | 'NOT_RECORDED';
}

export interface DocumentedRlFact {
  key: string;
  status: 'COMPLETE' | 'NOT_PROMOTED' | 'NO-GO' | 'TUNING_HARMFUL' | 'SEED_NOISE_NO_GO' | 'DOCUMENTED_RESEARCH_POSTURE';
  label: string;
  detail: string;
  staticResearchPosture: boolean;
}

export const DOCUMENTED_RL_FACTS: readonly DocumentedRlFact[] = [
  {
    key: 'smoke_plumbing_complete',
    status: 'COMPLETE',
    label: 'Smoke plumbing complete',
    detail: 'SB3 smoke/plumbing evidence can be complete without promoting a full model.',
    staticResearchPosture: true,
  },
  {
    key: 'full_model_not_promoted',
    status: 'NOT_PROMOTED',
    label: 'Full model not promoted',
    detail: 'No full RL model promotion, live trading, broker order, or profitability claim is declared.',
    staticResearchPosture: true,
  },
  {
    key: 'r5_tuning_harmful',
    status: 'TUNING_HARMFUL',
    label: 'R5 TUNING_HARMFUL',
    detail: 'Documented R5 posture remains harmful tuning, not a GO signal.',
    staticResearchPosture: true,
  },
  {
    key: 'close_slot_no_go',
    status: 'NO-GO',
    label: 'Close-slot NO-GO',
    detail: 'Close-slot research remains explicitly blocked from promotion.',
    staticResearchPosture: true,
  },
  {
    key: 'd4_seed_noise_no_go',
    status: 'SEED_NOISE_NO_GO',
    label: 'D4 SEED_NOISE_NO_GO',
    detail: 'D4 seed noise is documented as NO-GO rather than robust model evidence.',
    staticResearchPosture: true,
  },
  {
    key: 'documented_research_posture',
    status: 'DOCUMENTED_RESEARCH_POSTURE',
    label: 'Documented research posture',
    detail: 'Static facts are labeled as documented posture, not live market data.',
    staticResearchPosture: true,
  },
] as const;


const NOT_RECORDED = 'NOT_RECORDED';
const INCOMPATIBLE_UNIT = 'INCOMPATIBLE_UNIT';

export const CONFLICT_BLOCKED = 'CONFLICT_BLOCKED' as const;

export type RlIdentityFieldStatus = 'recorded' | 'missing' | 'invalid';
export type RlRunIdentityReconciliationStatus = 'MATCHED' | typeof CONFLICT_BLOCKED;
export type RlRunIdentityConflictCode =
  | 'LIST_RECORD_MISSING'
  | 'DETAIL_RECORD_MISSING'
  | 'DETAIL_RECORD_MALFORMED'
  | 'LIST_RUN_UID_MISSING'
  | 'LIST_RUN_UID_INVALID'
  | 'DETAIL_RUN_UID_MISSING'
  | 'DETAIL_RUN_UID_INVALID'
  | 'RUN_UID_MISMATCH'
  | 'LIST_UID_COLLISION'
  | 'LIST_REVISION_MISSING'
  | 'LIST_REVISION_INVALID'
  | 'DETAIL_REVISION_MISSING'
  | 'DETAIL_REVISION_INVALID'
  | 'REVISION_MISMATCH_STALE_DETAIL'
  | 'REVISION_MISMATCH_NEWER_DETAIL'
  | 'LIST_SOURCE_SHA_MISSING'
  | 'LIST_SOURCE_SHA_INVALID'
  | 'DETAIL_SOURCE_SHA_MISSING'
  | 'DETAIL_SOURCE_SHA_INVALID'
  | 'SOURCE_SHA_CONFLICT'
  | 'LIST_PROTOCOL_MISSING'
  | 'LIST_PROTOCOL_INVALID'
  | 'DETAIL_PROTOCOL_MISSING'
  | 'DETAIL_PROTOCOL_INVALID'
  | 'PROTOCOL_CONFLICT'
  | 'REQUESTED_NAME_MISMATCH'
  | 'NAME_MISMATCH'
  | 'ARTIFACT_TYPE_MISMATCH'
  | 'LANE_MISMATCH';

export interface RlRunIdentityProvenance {
  origin: 'list' | 'detail';
  run_uid: string;
  run_uid_status: RlIdentityFieldStatus;
  name: string;
  name_status: RlIdentityFieldStatus;
  revision: string;
  revision_number: number | null;
  revision_status: RlIdentityFieldStatus;
  source_sha256: string;
  source_sha256_status: RlIdentityFieldStatus;
  protocol: string;
  protocol_status: RlIdentityFieldStatus;
  artifact_type: string;
  artifact_type_status: RlIdentityFieldStatus;
  lane: RlEvidenceLaneKind;
  endpoint: string;
}

export interface RlRunIdentityConflict {
  code: RlRunIdentityConflictCode;
  detail: string;
}

export interface RlRunIdentityReconciliation {
  status: RlRunIdentityReconciliationStatus;
  usable: boolean;
  selected_run_uid: string;
  selected_name: string;
  list: RlRunIdentityProvenance;
  detail: RlRunIdentityProvenance;
  conflicts: readonly RlRunIdentityConflict[];
  source: RlRunRecord | RlRunDetail | JsonObject | null;
}

type UnknownRecord = Record<string, unknown>;

function asRecord(value: unknown): UnknownRecord | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? (value as UnknownRecord) : null;
}

function stringValue(value: unknown): string | null {
  if (typeof value === 'string' && value.trim() !== '') return value;
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return null;
}

function numberValue(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function validNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim() !== '';
}

function metadataString(value: unknown): string | null {
  return validNonEmptyString(value) ? value : null;
}

function metadataSeed(value: unknown): string | null {
  if (validNonEmptyString(value)) return value;
  return numberValue(value) === null ? null : String(value);
}

function lower(value: unknown): string {
  return stringValue(value)?.trim().toLowerCase().replace(/[\s-]+/g, '_') ?? '';
}

function first(records: readonly (UnknownRecord | null)[], keys: readonly string[]): unknown {
  for (const record of records) {
    if (!record) continue;
    for (const key of keys) {
      if (Object.prototype.hasOwnProperty.call(record, key)) return record[key];
    }
  }
  return undefined;
}

function nested(record: UnknownRecord | null, keys: readonly string[]): UnknownRecord | null {
  for (const key of keys) {
    const child = asRecord(record?.[key]);
    if (child) return child;
  }
  return null;
}

function unitOf(value: unknown): string | null {
  return stringValue(asRecord(value)?.unit ?? asRecord(value)?.units);
}

function valueOf(value: unknown): unknown {
  const record = asRecord(value);
  return record && Object.prototype.hasOwnProperty.call(record, 'value') ? record.value : value;
}

function sourceRecord(source: RlRunRecord | RlRunDetail | JsonObject | null | undefined): UnknownRecord | null {
  return asRecord(source);
}

type PresentValue = { found: boolean; value: unknown };

const SHA256_PATTERN = /^[a-f0-9]{64}$/i;
const RUN_UID_NOT_RECORDED = 'RUN_UID_NOT_RECORDED';
const REVISION_NOT_RECORDED = 'REVISION_NOT_RECORDED';
const SOURCE_SHA_NOT_RECORDED = 'SOURCE_SHA_NOT_RECORDED';
const PROTOCOL_NOT_RECORDED = 'PROTOCOL_NOT_RECORDED';

function firstPresent(records: readonly (UnknownRecord | null)[], keys: readonly string[]): PresentValue {
  for (const record of records) {
    if (!record) continue;
    for (const key of keys) {
      if (Object.prototype.hasOwnProperty.call(record, key)) return { found: true, value: record[key] };
    }
  }
  return { found: false, value: undefined };
}

function requiredText(
  records: readonly (UnknownRecord | null)[],
  keys: readonly string[],
  fallback: string,
  validate?: (value: string) => boolean,
): { value: string; status: RlIdentityFieldStatus } {
  const present = firstPresent(records, keys);
  if (!present.found || present.value === null || present.value === undefined) {
    return { value: fallback, status: 'missing' };
  }
  if (typeof present.value !== 'string' || present.value.trim() === '') {
    return { value: fallback, status: 'invalid' };
  }
  const value = present.value.trim();
  if (validate && !validate(value)) {
    return { value: fallback, status: 'invalid' };
  }
  return { value, status: 'recorded' };
}

function revisionText(records: readonly (UnknownRecord | null)[]): {
  value: string;
  number: number | null;
  status: RlIdentityFieldStatus;
} {
  const present = firstPresent(records, [
    'revision',
    'source_revision',
    'evidence_revision',
    'provenance_revision',
    'artifact_revision',
    'detail_revision',
    'list_revision',
  ]);
  if (!present.found || present.value === null || present.value === undefined) {
    return { value: REVISION_NOT_RECORDED, number: null, status: 'missing' };
  }
  if (typeof present.value === 'number' && Number.isInteger(present.value) && present.value >= 0) {
    return { value: String(present.value), number: present.value, status: 'recorded' };
  }
  if (typeof present.value === 'string' && /^\d+$/.test(present.value.trim())) {
    const value = Number(present.value.trim());
    return Number.isSafeInteger(value)
      ? { value: present.value.trim(), number: value, status: 'recorded' }
      : { value: REVISION_NOT_RECORDED, number: null, status: 'invalid' };
  }
  return { value: REVISION_NOT_RECORDED, number: null, status: 'invalid' };
}

function provenanceRecords(record: UnknownRecord | null): readonly (UnknownRecord | null)[] {
  const provenance = nested(record, ['provenance', 'source_provenance', 'identity_provenance']);
  const summary = nested(record, ['summary']);
  const detail = nested(record, ['detail']);
  return [record, provenance, summary, detail];
}

function identityEndpoint(origin: 'list' | 'detail', record: UnknownRecord | null, name: string): string {
  const endpoint = stringValue(record?.source_endpoint ?? record?.endpoint);
  if (endpoint) return endpoint;
  return origin === 'detail' && name !== 'NAME_NOT_RECORDED'
    ? `/api/rl/runs/${encodeURIComponent(name)}`
    : '/api/rl/runs';
}

export function rlRunIdentityProvenance(
  source: RlRunRecord | RlRunDetail | JsonObject | null | undefined,
  origin: 'list' | 'detail',
): RlRunIdentityProvenance {
  const record = sourceRecord(source);
  const records = provenanceRecords(record);
  const runUid = requiredText(records, ['run_uid', 'immutable_run_uid', 'uid'], RUN_UID_NOT_RECORDED);
  const name = requiredText([record], ['name'], 'NAME_NOT_RECORDED');
  const artifactType = requiredText([record], ['artifact_type', 'kind', 'type'], 'ARTIFACT_TYPE_NOT_RECORDED');
  const revision = revisionText(records);
  const sourceSha = requiredText(
    records,
    ['source_sha256', 'source_sha', 'source_hash', 'candidate_source_sha256'],
    SOURCE_SHA_NOT_RECORDED,
    (value) => SHA256_PATTERN.test(value),
  );
  const protocol = requiredText(
    records,
    ['source_protocol', 'evidence_protocol', 'provenance_protocol', 'protocol'],
    PROTOCOL_NOT_RECORDED,
  );
  return {
    origin,
    run_uid: runUid.value,
    run_uid_status: runUid.status,
    name: name.value,
    name_status: name.status,
    revision: revision.value,
    revision_number: revision.number,
    revision_status: revision.status,
    source_sha256: sourceSha.status === 'recorded' ? sourceSha.value.toLowerCase() : sourceSha.value,
    source_sha256_status: sourceSha.status,
    protocol: protocol.value,
    protocol_status: protocol.status,
    artifact_type: artifactType.value,
    artifact_type_status: artifactType.status,
    lane: classifyRlEvidenceLane(source).kind,
    endpoint: identityEndpoint(origin, record, name.value),
  };
}

export function rlRunIdentityKey(source: RlRunRecord | RlRunDetail | JsonObject | null | undefined): string {
  const provenance = rlRunIdentityProvenance(source, 'list');
  return provenance.run_uid_status === 'recorded'
    ? provenance.run_uid
    : `${RUN_UID_NOT_RECORDED}:${provenance.name}`;
}

function conflict(code: RlRunIdentityConflictCode, detail: string): RlRunIdentityConflict {
  return { code, detail };
}

function addFieldStatusConflicts(
  conflicts: RlRunIdentityConflict[],
  provenance: RlRunIdentityProvenance,
): void {
  const prefix = provenance.origin === 'list' ? 'LIST' : 'DETAIL';
  if (provenance.run_uid_status !== 'recorded') {
    conflicts.push(conflict(
      `${prefix}_RUN_UID_${provenance.run_uid_status === 'missing' ? 'MISSING' : 'INVALID'}` as RlRunIdentityConflictCode,
      `${provenance.origin} run_uid ${provenance.run_uid_status}`,
    ));
  }
  if (provenance.revision_status !== 'recorded') {
    conflicts.push(conflict(
      `${prefix}_REVISION_${provenance.revision_status === 'missing' ? 'MISSING' : 'INVALID'}` as RlRunIdentityConflictCode,
      `${provenance.origin} revision ${provenance.revision_status}`,
    ));
  }
  if (provenance.source_sha256_status !== 'recorded') {
    conflicts.push(conflict(
      `${prefix}_SOURCE_SHA_${provenance.source_sha256_status === 'missing' ? 'MISSING' : 'INVALID'}` as RlRunIdentityConflictCode,
      `${provenance.origin} source_sha256 ${provenance.source_sha256_status}`,
    ));
  }
  if (provenance.protocol_status !== 'recorded') {
    conflicts.push(conflict(
      `${prefix}_PROTOCOL_${provenance.protocol_status === 'missing' ? 'MISSING' : 'INVALID'}` as RlRunIdentityConflictCode,
      `${provenance.origin} protocol ${provenance.protocol_status}`,
    ));
  }
}

function sameRecordedText(left: RlIdentityFieldStatus, right: RlIdentityFieldStatus): boolean {
  return left === 'recorded' && right === 'recorded';
}

function hasListUidCollision(
  listProvenance: RlRunIdentityProvenance,
  records: readonly (RlRunRecord | JsonObject)[],
): boolean {
  if (listProvenance.run_uid_status !== 'recorded') return false;
  let matches = 0;
  for (const record of records) {
    const candidate = rlRunIdentityProvenance(record, 'list');
    if (candidate.run_uid_status === 'recorded' && candidate.run_uid === listProvenance.run_uid) {
      matches += 1;
    }
  }
  return matches > 1;
}

function promotionLocksFalse(): JsonObject {
  const locks: Record<string, boolean> = {};
  for (const key of PROMOTION_LOCK_KEYS) {
    locks[key] = false;
  }
  return locks as JsonObject;
}

function conflictSource(
  list: RlRunRecord | JsonObject | null | undefined,
  detail: RlRunDetail | JsonObject | null | undefined,
  listProvenance: RlRunIdentityProvenance,
  detailProvenance: RlRunIdentityProvenance,
  conflicts: readonly RlRunIdentityConflict[],
): JsonObject {
  const base = sourceRecord(detail) ?? sourceRecord(list);
  const strategy = nested(base, ['strategy_context', 'strategy', 'summary']);
  const selectedName = detailProvenance.name_status === 'recorded' ? detailProvenance.name : listProvenance.name;
  const selectedUid = detailProvenance.run_uid_status === 'recorded' ? detailProvenance.run_uid : listProvenance.run_uid;
  const conflictDetails = conflicts.map((item) => `${item.code}: ${item.detail}`);
  return {
    name: selectedName,
    run_id: selectedName,
    run_uid: selectedUid,
    artifact_type: stringValue(base?.artifact_type ?? base?.kind ?? base?.type) ?? listProvenance.artifact_type,
    lifecycle: CONFLICT_BLOCKED,
    status: CONFLICT_BLOCKED,
    freshness_status: CONFLICT_BLOCKED,
    verdict: CONFLICT_BLOCKED,
    source_endpoint: detailProvenance.endpoint,
    source_sha256: detailProvenance.source_sha256_status === 'recorded' ? detailProvenance.source_sha256 : listProvenance.source_sha256,
    source_protocol: detailProvenance.protocol_status === 'recorded' ? detailProvenance.protocol : listProvenance.protocol,
    revision: detailProvenance.revision_status === 'recorded' ? detailProvenance.revision : listProvenance.revision,
    blocking_reasons: [CONFLICT_BLOCKED, ...conflictDetails],
    promotion_locks: promotionLocksFalse(),
    summary: {
      status: CONFLICT_BLOCKED,
      identity_reconciliation: CONFLICT_BLOCKED,
      list_revision: listProvenance.revision,
      detail_revision: detailProvenance.revision,
      conflicts: conflictDetails,
    },
    detail: {
      status: CONFLICT_BLOCKED,
      stage: CONFLICT_BLOCKED,
      identity_reconciliation: CONFLICT_BLOCKED,
      conflicts: conflictDetails,
    },
    strategy_context: {
      line: stringValue(strategy?.line ?? base?.line ?? base?.strategy_line) ?? 'research_only',
      label: stringValue(strategy?.label ?? base?.strategy_label ?? selectedName) ?? CONFLICT_BLOCKED,
      is_reinforcement_learning: strategy?.is_reinforcement_learning === true || base?.is_reinforcement_learning === true,
    },
  };
}

function blockedV4PromotionLocks(source: RunEvidence['promotion_locks']): RunEvidence['promotion_locks'] {
  const locks = {} as RunEvidence['promotion_locks']['locks'];
  const states = {} as RunEvidence['promotion_locks']['states'];

  for (const key of PROMOTION_LOCK_KEYS) {
    const original = source.states[key];
    const sourceStatus = original?.sourceStatus ?? 'missing';
    const fallbackReason = sourceStatus === 'invalid'
      ? 'LOCK_SOURCE_INVALID'
      : sourceStatus === 'missing'
        ? 'LOCK_SOURCE_MISSING'
        : 'LOCKED_BY_SOURCE';
    const reason = original?.reason ?? fallbackReason;

    locks[key] = false;
    states[key] = {
      key,
      allowed: false,
      sourceStatus,
      reason,
    };
  }

  return {
    locks,
    states,
    allLocked: true,
    hasInvalidSource: PROMOTION_LOCK_KEYS.some((key) => states[key].sourceStatus === 'invalid'),
  };
}

function withV4EffectiveLocksBlocked(run: RunEvidence): RunEvidence {
  const sourceUnlockAttempts = PROMOTION_LOCK_KEYS.filter((key) => run.promotion_locks.states[key]?.allowed === true);
  const blocking_reasons = sourceUnlockAttempts.length === 0
    ? run.blocking_reasons
    : [
        ...run.blocking_reasons,
        `SOURCE_TRUE_UNLOCK_PROVENANCE_ATTEMPT_BLOCKED:${sourceUnlockAttempts.join(',')}`,
      ];

  return {
    ...run,
    blocking_reasons,
    promotion_locks: blockedV4PromotionLocks(run.promotion_locks),
  };
}

export function reconcileRlRunIdentity(
  list: RlRunRecord | JsonObject | null | undefined,
  detail: RlRunDetail | JsonObject | null | undefined,
  options: {
    selectedRunUid?: string;
    selectedName?: string;
    listRecords?: readonly (RlRunRecord | JsonObject)[];
    detailRecorded?: boolean;
  } = {},
): RlRunIdentityReconciliation {
  const listRecord = sourceRecord(list);
  const detailRecord = sourceRecord(detail);
  const listProvenance = rlRunIdentityProvenance(list, 'list');
  const detailProvenance = rlRunIdentityProvenance(detail, 'detail');
  const conflicts: RlRunIdentityConflict[] = [];

  if (!listRecord) conflicts.push(conflict('LIST_RECORD_MISSING', 'selected list record missing'));
  if (!detailRecord) conflicts.push(conflict('DETAIL_RECORD_MISSING', 'selected detail record missing'));
  if (detailRecord && options.detailRecorded === false) conflicts.push(conflict('DETAIL_RECORD_MALFORMED', 'selected detail payload malformed'));
  addFieldStatusConflicts(conflicts, listProvenance);
  addFieldStatusConflicts(conflicts, detailProvenance);

  if (sameRecordedText(listProvenance.run_uid_status, detailProvenance.run_uid_status) && listProvenance.run_uid !== detailProvenance.run_uid) {
    conflicts.push(conflict('RUN_UID_MISMATCH', `list ${listProvenance.run_uid} detail ${detailProvenance.run_uid}`));
  }
  if (options.selectedRunUid && listProvenance.run_uid_status === 'recorded' && options.selectedRunUid !== listProvenance.run_uid) {
    conflicts.push(conflict('RUN_UID_MISMATCH', `selected ${options.selectedRunUid} list ${listProvenance.run_uid}`));
  }
  if (hasListUidCollision(listProvenance, options.listRecords ?? (list ? [list] : []))) {
    conflicts.push(conflict('LIST_UID_COLLISION', `run_uid ${listProvenance.run_uid} appears more than once in the list payload`));
  }
  if (options.selectedName && detailProvenance.name_status === 'recorded' && options.selectedName !== detailProvenance.name) {
    conflicts.push(conflict('REQUESTED_NAME_MISMATCH', `requested ${options.selectedName} detail ${detailProvenance.name}`));
  }
  if (sameRecordedText(listProvenance.name_status, detailProvenance.name_status) && listProvenance.name !== detailProvenance.name) {
    conflicts.push(conflict('NAME_MISMATCH', `list ${listProvenance.name} detail ${detailProvenance.name}`));
  }
  if (
    sameRecordedText(listProvenance.artifact_type_status, detailProvenance.artifact_type_status) &&
    listProvenance.artifact_type !== detailProvenance.artifact_type
  ) {
    conflicts.push(conflict('ARTIFACT_TYPE_MISMATCH', `list ${listProvenance.artifact_type} detail ${detailProvenance.artifact_type}`));
  }
  if (listProvenance.lane !== detailProvenance.lane) {
    conflicts.push(conflict('LANE_MISMATCH', `list ${listProvenance.lane} detail ${detailProvenance.lane}`));
  }
  if (
    sameRecordedText(listProvenance.revision_status, detailProvenance.revision_status) &&
    listProvenance.revision_number !== null &&
    detailProvenance.revision_number !== null &&
    listProvenance.revision_number !== detailProvenance.revision_number
  ) {
    const code = detailProvenance.revision_number < listProvenance.revision_number
      ? 'REVISION_MISMATCH_STALE_DETAIL'
      : 'REVISION_MISMATCH_NEWER_DETAIL';
    conflicts.push(conflict(code, `list revision ${listProvenance.revision} detail revision ${detailProvenance.revision}`));
  }
  if (
    sameRecordedText(listProvenance.source_sha256_status, detailProvenance.source_sha256_status) &&
    listProvenance.source_sha256 !== detailProvenance.source_sha256
  ) {
    conflicts.push(conflict('SOURCE_SHA_CONFLICT', `list ${listProvenance.source_sha256} detail ${detailProvenance.source_sha256}`));
  }
  if (
    sameRecordedText(listProvenance.protocol_status, detailProvenance.protocol_status) &&
    listProvenance.protocol !== detailProvenance.protocol
  ) {
    conflicts.push(conflict('PROTOCOL_CONFLICT', `list ${listProvenance.protocol} detail ${detailProvenance.protocol}`));
  }

  const status: RlRunIdentityReconciliationStatus = conflicts.length > 0 ? CONFLICT_BLOCKED : 'MATCHED';
  return {
    status,
    usable: status === 'MATCHED',
    selected_run_uid: options.selectedRunUid ?? listProvenance.run_uid,
    selected_name: options.selectedName ?? listProvenance.name,
    list: listProvenance,
    detail: detailProvenance,
    conflicts,
    source: status === 'MATCHED' ? detail ?? list ?? null : conflictSource(list, detail, listProvenance, detailProvenance, conflicts),
  };
}

export function classifyRlEvidenceLane(source: RlRunRecord | RlRunDetail | JsonObject | null | undefined): RlEvidenceLane {
  const record = sourceRecord(source);
  const strategy = nested(record, ['strategy_context', 'strategy', 'summary']);
  const artifact = lower(record?.artifact_type ?? record?.kind ?? record?.type);
  const line = lower(strategy?.line ?? record?.line ?? record?.strategy_line);
  const label = stringValue(strategy?.label ?? record?.name ?? record?.run_id ?? record?.id) ?? 'UNLABELED';
  const explicitRl = strategy?.is_reinforcement_learning === true || record?.is_reinforcement_learning === true;
  const explicitNonRl = strategy?.is_reinforcement_learning === false || record?.is_reinforcement_learning === false;

  if (line.includes('rule') || artifact === 'baseline' || artifact.includes('rule_filter')) {
    return {
      kind: 'RULE',
      label: `${label} · RULE baseline / NOT RL`,
      isRl: false,
      posture: 'baseline_not_rl',
      reason: 'RULE lane is a baseline/control surface and is never re-labeled as RL.',
    };
  }

  if (
    !explicitNonRl &&
    (explicitRl ||
      line === 'rl' ||
      line === 'reinforcement_learning' ||
      artifact.includes('rl_workflow') ||
      artifact.includes('sb3') ||
      artifact.includes('reinforcement'))
  ) {
    return {
      kind: 'RL',
      label: `${label} · RL experiment / research-only`,
      isRl: true,
      posture: 'research_only_rl',
      reason: 'RL evidence is research-only unless independent promotion locks explicitly unlock, which this console does not infer.',
    };
  }

  if (
    line.includes('supervised') ||
    artifact.includes('calibration') ||
    artifact.includes('lineage') ||
    artifact.includes('sizing') ||
    artifact.includes('risk_policy') ||
    artifact.includes('session') ||
    artifact.includes('factory')
  ) {
    return {
      kind: 'SUPERVISED_GATE',
      label: `${label} · supervised gate / NOT RL`,
      isRl: false,
      posture: 'supervised_gate_not_rl',
      reason: 'Supervised/factory gates can block or contextualize RL, but are not RL returns.',
    };
  }

  return {
    kind: 'EVIDENCE',
    label: `${label} · audit evidence / NOT RL unless declared`,
    isRl: false,
    posture: 'audit_evidence',
    reason: 'No explicit RL lane declaration was recorded.',
  };
}

function rowCount(rows: readonly RlTableRow[] | undefined): number | null {
  return rows && rows.length > 0 ? rows.length : null;
}
export type RlCollectionStatus = 'recorded' | 'empty' | 'not_recorded';
export interface NormalizedRlProgress {
  status: RlCollectionStatus;
  progress: RlProgressResponse | null;
}

function validProgressPage(value: unknown): boolean {
  const page = asRecord(value);
  return page !== null &&
    validNonEmptyString(page.page) &&
    numberValue(page.progress_pct) !== null &&
    validNonEmptyString(page.status) &&
    (page.criteria === undefined || Array.isArray(page.criteria));
}

export function normalizeRlProgress(payload: unknown): NormalizedRlProgress {
  const record = asRecord(payload);
  if (!record || numberValue(record.overall_progress_pct) === null || !validNonEmptyString(record.status) ||
      !Array.isArray(record.pages) || !record.pages.every(validProgressPage)) {
    return { status: 'not_recorded', progress: null };
  }
  const progress = record as unknown as RlProgressResponse;
  return { status: progress.pages.length === 0 ? 'empty' : 'recorded', progress };
}

export interface NormalizedRlRunDetail {
  status: RlCollectionStatus;
  detail: RlRunDetail | null;
}

function validArtifact(value: unknown): boolean {
  const artifact = asRecord(value);
  return artifact !== null && validNonEmptyString(artifact.name);
}

export function normalizeRlRunDetail(payload: unknown, requestedName: string): NormalizedRlRunDetail {
  const record = asRecord(payload);
  if (!record || !validNonEmptyString(record.name) || record.name !== requestedName ||
      !validNonEmptyString(record.artifact_type) ||
      (record.artifacts !== undefined && (!Array.isArray(record.artifacts) || !record.artifacts.every(validArtifact)))) {
    return { status: 'not_recorded', detail: null };
  }
  return { status: 'recorded', detail: record as unknown as RlRunDetail };
}

export interface NormalizedRlRuns {
  status: RlCollectionStatus;
  runs: readonly RlRunRecord[];
}

export function normalizeRlRuns(payload: unknown): NormalizedRlRuns {
  const record = asRecord(payload);
  const runs = record?.runs;
  if (!Array.isArray(runs) || !runs.every((run) => {
    const item = asRecord(run);
    return item !== null && typeof item.name === 'string' && item.name.trim() !== '';
  })) {
    return { status: 'not_recorded', runs: [] };
  }
  return { status: runs.length === 0 ? 'empty' : 'recorded', runs: runs as readonly RlRunRecord[] };
}

export interface NormalizedRlRows {
  status: RlCollectionStatus;
  rows: readonly RlTableRow[];
}

export function normalizeRlRows(payload: unknown): NormalizedRlRows {
  const record = asRecord(payload);
  if (!record || !Array.isArray(record.rows) || !record.rows.every((row) => asRecord(row) !== null)) {
    return { status: 'not_recorded', rows: [] };
  }
  return { status: record.rows.length === 0 ? 'empty' : 'recorded', rows: record.rows as readonly RlTableRow[] };
}

export interface NormalizedRliableCollections {
  status: RlCollectionStatus;
  algorithms: number;
  aggregates: number;
}

export function normalizeRliableCollections(payload: unknown): NormalizedRliableCollections {
  const record = asRecord(payload);
  if (!record || !Array.isArray(record.algorithms) || !record.algorithms.every((item) => typeof item === 'string') || !asRecord(record.aggregates)) {
    return { status: 'not_recorded', algorithms: 0, aggregates: 0 };
  }
  const algorithms = record.algorithms.length;
  const aggregates = Object.keys(record.aggregates).length;
  return { status: algorithms === 0 && aggregates === 0 ? 'empty' : 'recorded', algorithms, aggregates };
}

function makeMetric(
  key: string,
  label: string,
  raw: unknown,
  options: { unit: string; source: string; precision?: number; expectedUnits?: readonly string[] },
): CockpitMetric {
  const declaredUnit = unitOf(raw) ?? options.unit;
  const compatible = !options.expectedUnits || options.expectedUnits.includes(declaredUnit);
  const rawValue = valueOf(raw);
  const numeric = numberValue(rawValue);
  const metric = adaptMetricValue(compatible ? numeric : null, {
    kind: key,
    unit: compatible ? declaredUnit : `${declaredUnit}:${INCOMPATIBLE_UNIT}`,
    source: options.source,
    precision: options.precision,
    availability: compatible ? undefined : 'INAPPLICABLE',
  });
  const behavior = !compatible
    ? 'incompatible_unit'
    : metric.availability === 'INAPPLICABLE'
      ? 'inapplicable'
      : metric.availability === 'NOT_RECORDED'
        ? 'not_recorded'
        : 'recorded';
  const display = behavior === 'incompatible_unit'
    ? `${INCOMPATIBLE_UNIT} (${declaredUnit})`
    : metric.value === null
      ? NOT_RECORDED
      : `${metric.value}${declaredUnit === 'count' ? '' : ` ${declaredUnit}`}`;
  return { key, label, metric, display, behavior };
}

function makeMetadata(key: string, label: string, raw: unknown, notRecorded: string, source: string): CockpitMetadata {
  const value = stringValue(raw) ?? notRecorded;
  return {
    key,
    label,
    value,
    source,
    behavior: value === notRecorded ? 'not_recorded' : 'recorded',
  };
}

export function deriveRlCockpitEvidence(
  source: RlRunRecord | RlRunDetail | JsonObject | null | undefined,
  rows: { trades?: readonly RlTableRow[]; events?: readonly RlTableRow[] } = {},
): RlCockpitEvidence {
  const record = sourceRecord(source);
  const detail = nested(record, ['detail', 'summary', 'risk_policy']);
  const strategy = nested(record, ['strategy_context', 'strategy']);
  const sourceName = stringValue(record?.name ?? record?.run_id ?? record?.id) ?? 'selected-run';
  const run = withV4EffectiveLocksBlocked(adaptRunEvidence(record, { source_endpoint: `/api/rl/runs/${encodeURIComponent(sourceName)}` }));
  const lane = classifyRlEvidenceLane(source);
  const declaredTradeCount = first([record, detail], ['trade_count', 'trades', 'num_trades', 'executed_trades']);
  const tradeCountRaw = declaredTradeCount ?? rowCount(rows.trades);
  const validTradeCount = (() => {
    const value = valueOf(tradeCountRaw);
    return typeof value === 'number' && Number.isInteger(value) && value >= 0 ? tradeCountRaw : null;
  })();
  const tradeMetric = makeMetric('trade_count', 'Trade count', validTradeCount, {
    unit: 'count',
    source: sourceName,
    precision: 0,
    expectedUnits: ['count'],
  });
  const tradeCount = tradeMetric.behavior === 'recorded' ? numberValue(tradeMetric.metric.value) : null;
  const neverTradeStatus = tradeCount === 0 ? 'NEVER_TRADE' : tradeCount === null ? 'NOT_RECORDED' : 'TRADED';

  return {
    run,
    lane,
    neverTradeStatus,
    metadata: [
      makeMetadata('split', 'Split', metadataString(first([record, detail], ['split', 'split_policy', 'train_test_split'])), 'SPLIT_NOT_RECORDED', sourceName),
      makeMetadata('split_hash', 'Split hash', run.split_hash, 'SPLIT_HASH_NOT_RECORDED', sourceName),
      makeMetadata('seed', 'Seed', metadataSeed(first([record, detail], ['seed', 'random_seed'])), 'SEED_NOT_RECORDED', sourceName),
      makeMetadata('baseline', 'Baseline', metadataString(first([record, detail, strategy], ['baseline_label', 'primary_baseline', 'baseline'])), 'BASELINE_NOT_RECORDED', sourceName),
    ],
    metrics: [
      makeMetric('test_oos', 'TEST OOS', first([record, detail], ['test_oos', 'test_oos_score', 'oos_return', 'oos_metric']), {
        unit: 'score',
        source: sourceName,
        precision: 4,
        expectedUnits: ['score', 'ratio', 'pct', 'percent'],
      }),
      makeMetric('declared_cost_bps', 'Declared cost', run.cost_bps, {
        unit: 'bps',
        source: sourceName,
        precision: 2,
        expectedUnits: ['bps'],
      }),
      makeMetric('uncertainty', 'Uncertainty', first([record, detail], ['uncertainty', 'ci95', 'stderr', 'std_error']), {
        unit: 'score',
        source: sourceName,
        precision: 4,
        expectedUnits: ['score', 'ratio', 'pct', 'percent'],
      }),
      makeMetric('max_drawdown', 'MDD', first([record, detail], ['mdd', 'max_drawdown', 'max_drawdown_pct', 'max_dd_pct']), {
        unit: 'pct',
        source: sourceName,
        precision: 2,
        expectedUnits: ['pct', 'percent', 'ratio'],
      }),
      tradeMetric,
    ],
  };
}

export function choosePreferredRlRun(candidates: readonly RlRunRecord[]): RlRunRecord | null {
  return (
    candidates.find((run) => classifyRlEvidenceLane(run).kind === 'RL' && lower(run.lifecycle?.status ?? run.summary?.status) === 'completed') ??
    candidates.find((run) => classifyRlEvidenceLane(run).kind === 'RL') ??
    candidates.find((run) => classifyRlEvidenceLane(run).kind === 'RULE') ??
    candidates.find((run) => run.artifact_type === 'performance_leaderboard') ??
    candidates[0] ??
    null
  );
}

export function summarizeProgress(progress: RlProgressResponse | null): string {
  if (!progress) return 'progress NOT_RECORDED';
  return `${progress.status} · ${progress.overall_progress_pct}% · ${progress.pages.length} pages`;
}

export function summarizeRliable(stats: RlRliableStatsResponse | null): string {
  const normalized = normalizeRliableCollections(stats);
  if (normalized.status === 'not_recorded') return 'rliable NOT_RECORDED';
  return `${stats?.generated_utc ?? 'TIME_NOT_RECORDED'} · ${normalized.algorithms} algos · ${normalized.aggregates} aggregates`;
}
