import { adaptPromotionLocks, PROMOTION_LOCK_KEYS, type PromotionLocksResult } from '../evidence';

export { PROMOTION_LOCK_KEYS } from '../evidence';

export type AdminSurface = 'settings' | 'docs';

export type TrackingDetectionStatus =
  | 'disabled'
  | 'file_uri_detected'
  | 'rejected_remote_uri'
  | 'rejected_credentials'
  | 'rejected_unsupported_scheme';

export type TrackingPosture = 'READ_ONLY_LOCAL_FILE' | 'DISABLED' | 'REJECTED_UNSAFE_SOURCE';

/**
 * Mutation/action verbs that this admin surface must never imply it can perform.
 * Any candidate string containing one of these tokens is rejected before display
 * rather than rendered as an available capability.
 */
export const MUTATION_VERBS = [
  'start',
  'stop',
  'restart',
  'launch',
  'spawn',
  'kill',
  'create',
  'delete',
  'remove',
  'archive',
  'unarchive',
  'promote',
  'deploy',
  'setenv',
  'mutate',
  'write',
  'upload',
  'push',
  'register',
  'execute',
  'provision',
] as const;

const MUTATION_VERB_SET = new Set<string>(MUTATION_VERBS);
const TOKEN_SPLIT_PATTERN = /[^a-z0-9]+/i;

/**
 * Credential/token/secret indicators. Any candidate string matching one of these
 * patterns is treated as unsafe and never surfaced, regardless of scheme.
 */
const CREDENTIAL_PATTERNS: readonly RegExp[] = [
  /:\/\/[^/@\s]+:[^/@\s]+@/i, // userinfo@ embedded basic-auth in a URI
  /\b(token|api[_-]?key|apikey|secret|password|passwd|access[_-]?key|authorization|bearer|client[_-]?secret)\b\s*[:=]/i,
  /\bbearer\s+[a-z0-9._-]+/i,
];

const REMOTE_SCHEME_PATTERN = /^(https?|s3|gs|azure|ftp|ftps|ssh|wss?):\/\//i;
const FILE_SCHEME_PATTERN = /^file:\/\//i;

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim() !== '';
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function containsCredentials(text: string): boolean {
  return CREDENTIAL_PATTERNS.some((pattern) => pattern.test(text));
}

function containsMutationVerb(text: string): boolean {
  const tokens = text.toLowerCase().split(TOKEN_SPLIT_PATTERN).filter(Boolean);
  return tokens.some((token) => MUTATION_VERB_SET.has(token));
}

export interface TrackingUriEvaluation {
  raw: string | null;
  sanitizedUri: string | null;
  status: TrackingDetectionStatus;
  reason: string;
}

/**
 * Evaluate a candidate MLflow (or similar) tracking URI in strict fail-closed mode.
 * - Missing/empty input stays disabled.
 * - http(s) and other remote schemes are always rejected, never detected.
 * - Any credential/token indicator anywhere in the string is always rejected,
 *   even for a `file:` scheme.
 * - Only a credential-free `file:` URI is accepted as a safe, read-only local
 *   tracking source.
 */
export function evaluateTrackingUri(raw: unknown): TrackingUriEvaluation {
  if (!isNonEmptyString(raw)) {
    return { raw: null, sanitizedUri: null, status: 'disabled', reason: 'MLFLOW_TRACKING_URI_NOT_RECORDED' };
  }

  const text = raw.trim();

  if (containsCredentials(text)) {
    return { raw: text, sanitizedUri: null, status: 'rejected_credentials', reason: 'CREDENTIALS_OR_TOKEN_REJECTED' };
  }

  if (REMOTE_SCHEME_PATTERN.test(text)) {
    return { raw: text, sanitizedUri: null, status: 'rejected_remote_uri', reason: 'REMOTE_TRACKING_URI_REJECTED' };
  }

  if (FILE_SCHEME_PATTERN.test(text)) {
    return { raw: text, sanitizedUri: text, status: 'file_uri_detected', reason: 'SAFE_LOCAL_FILE_URI_DETECTED' };
  }

  return { raw: text, sanitizedUri: null, status: 'rejected_unsupported_scheme', reason: 'UNSUPPORTED_TRACKING_SCHEME_REJECTED' };
}

export interface SanitizedLabel {
  text: string;
  rejected: boolean;
  reason: string | null;
}

/**
 * Sanitize an arbitrary display-only string (doc titles, experiment labels, etc.).
 * Rejects mutation/action verbs and credential-shaped substrings so this
 * read-only surface never renders anything that reads like an available action
 * or leaks a secret. Never returns raw HTML; callers must always render as text.
 */
export function sanitizeAdminLabel(raw: unknown): SanitizedLabel {
  if (!isNonEmptyString(raw)) {
    return { text: 'NOT_RECORDED', rejected: false, reason: null };
  }
  const text = raw.trim();
  if (containsCredentials(text)) {
    return { text: 'REDACTED', rejected: true, reason: 'CREDENTIALS_OR_TOKEN_REJECTED' };
  }
  if (containsMutationVerb(text)) {
    return { text: 'REDACTED', rejected: true, reason: 'MUTATION_ACTION_VERB_REJECTED' };
  }
  return { text, rejected: false, reason: null };
}

export interface RawTrackingSource {
  trackingUri?: unknown;
  label?: unknown;
  capabilities?: unknown;
}

export interface TrackingEvidence {
  backend: 'mlflow';
  /**
   * Always derived from a verified safe local `file:` URI. A caller-claimed
   * `enabled: true` flag is never trusted on its own (no optimistic defaults).
   */
  enabled: boolean;
  detectionStatus: TrackingDetectionStatus;
  posture: TrackingPosture;
  sanitizedUri: string | null;
  label: SanitizedLabel;
  reasons: string[];
  rejectedCapabilities: string[];
}

function evaluateCapabilities(value: unknown): { rejected: string[] } {
  if (!Array.isArray(value)) {
    return { rejected: [] };
  }
  const rejected: string[] = [];
  for (const item of value) {
    if (typeof item !== 'string') continue;
    if (containsMutationVerb(item) || containsCredentials(item)) {
      rejected.push(item);
    }
  }
  return { rejected };
}

function postureFor(status: TrackingDetectionStatus, hasRejectedCapabilities: boolean): TrackingPosture {
  if (status === 'disabled') return 'DISABLED';
  if (status === 'file_uri_detected' && !hasRejectedCapabilities) return 'READ_ONLY_LOCAL_FILE';
  return 'REJECTED_UNSAFE_SOURCE';
}

/**
 * Derive independent, fail-closed local tracking (MLflow) evidence from
 * caller-supplied props/data only. Never fetches a network URL and never
 * inspects environment variables; the caller is responsible for sourcing
 * `source` from safe local metadata already available to the UI.
 */
export function evaluateTrackingEvidence(source: unknown): TrackingEvidence {
  const record = asRecord(source);
  const uriEvaluation = evaluateTrackingUri(record?.trackingUri);
  const label = sanitizeAdminLabel(record?.label);
  const { rejected: rejectedCapabilities } = evaluateCapabilities(record?.capabilities);

  const reasons: string[] = [uriEvaluation.reason];
  if (label.rejected && label.reason) reasons.push(label.reason);
  if (rejectedCapabilities.length > 0) reasons.push('CAPABILITY_DECLARATIONS_IGNORED');

  const enabled = uriEvaluation.status === 'file_uri_detected' && rejectedCapabilities.length === 0;

  return {
    backend: 'mlflow',
    enabled,
    detectionStatus: uriEvaluation.status,
    posture: enabled ? 'READ_ONLY_LOCAL_FILE' : postureFor(uriEvaluation.status, rejectedCapabilities.length > 0),
    sanitizedUri: enabled ? uriEvaluation.sanitizedUri : null,
    label,
    reasons,
    rejectedCapabilities,
  };
}

export interface DocsSanitizationFact {
  key: string;
  label: string;
  detail: string;
}

/** Static, documented sanitization posture facts for the docs surface. Never live data. */
export const DOCS_SANITIZATION_FACTS: readonly DocsSanitizationFact[] = [
  {
    key: 'no_raw_html',
    label: 'No raw HTML rendering',
    detail: 'Docs/settings content is always rendered as text; {@html} is never used on this surface.',
  },
  {
    key: 'no_egress',
    label: 'No network egress',
    detail: 'This surface never fetches external URLs and never reads environment variables at render time.',
  },
  {
    key: 'read_only_local_tracking',
    label: 'Read-only local tracking only',
    detail: 'MLflow-style tracking is only ever detected from a caller-supplied, credential-free local file: URI.',
  },
  {
    key: 'no_mutation_actions',
    label: 'No mutation actions',
    detail: 'This surface cannot start servers, set env vars, or create/delete/archive/promote anything.',
  },
] as const;

export interface ReadOnlyPosture {
  readOnly: true;
  noEgress: true;
  noServerControl: true;
  noMutation: true;
}

export const READ_ONLY_NO_EGRESS_POSTURE: ReadOnlyPosture = {
  readOnly: true,
  noEgress: true,
  noServerControl: true,
  noMutation: true,
};

export interface AdminWorkspaceModel {
  surface: AdminSurface;
  locks: PromotionLocksResult;
  tracking: TrackingEvidence;
  posture: ReadOnlyPosture;
  docsSanitization: readonly DocsSanitizationFact[];
}

/**
 * Derive the full fail-closed admin/local-tracking model. Promotion locks are
 * always evaluated against an empty source so this surface can never display
 * an unlocked state, independent of any caller-supplied data.
 */
export function deriveAdminWorkspaceModel(surface: AdminSurface, trackingSource: unknown = undefined): AdminWorkspaceModel {
  return {
    surface,
    locks: adaptPromotionLocks(undefined),
    tracking: evaluateTrackingEvidence(trackingSource),
    posture: READ_ONLY_NO_EGRESS_POSTURE,
    docsSanitization: DOCS_SANITIZATION_FACTS,
  };
}

export function assertExactSixLocksFalse(locks: PromotionLocksResult): boolean {
  return PROMOTION_LOCK_KEYS.length === 6 && PROMOTION_LOCK_KEYS.every((key) => locks.locks[key] === false) && locks.allLocked;
}
