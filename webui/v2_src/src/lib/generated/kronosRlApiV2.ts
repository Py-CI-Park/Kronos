/* Generated from docs/schemas/kronos_rl_api_v2.schema.json; schema-sha256: 2ab539e23ad4df9ea7c48428068ae0859d57acdeb1fbed28e739f23349cdc004; json-schema-to-typescript@15.0.4. Do not edit. */

export type KronosRLAPIV2CanonicalWireContract =
  | RunsRoot
  | RunDetailRoot
  | EventsRoot
  | MatrixRoot
  | LedgerRoot
  | ArtifactsRoot
  | D0Root
  | D1Root
  | FixtureRoot
  | ErrorRoot;
export type Sha256 = string;
export type Utc = string;
export type RunId = string;
export type RunRevision = number;
export type Cursor = string;
export type Event =
  | { event_type: "PROGRESS"; event_id: string; occurred_at: Utc; payload_sha256: Sha256; progress: Progress }
  | { event_type: "MESSAGE"; event_id: string; occurred_at: Utc; payload_sha256: Sha256; level: "DEBUG" | "INFO" | "WARNING" | "ERROR"; message: string }
  | { event_type: "ARTIFACT"; event_id: string; occurred_at: Utc; payload_sha256: Sha256; artifact_id: ArtifactId }
  | { event_type: "STATE"; event_id: string; occurred_at: Utc; payload_sha256: Sha256; state: RunState };
export type ArtifactId = string;
/**
 * @minItems 50
 * @maxItems 50
 */
export type MatrixCells = MatrixCell[];
export type D0 = {
  [k: string]: unknown;
} & {
  status: 'PASS' | 'FAIL' | 'BLOCKED' | 'PENDING';
  price_basis: 'ADJUSTED' | 'RAW' | 'UNKNOWN';
  source_sha256: Sha256;
  updated_at: Utc;
};
export type D1 = {
  [k: string]: unknown;
} & {
  status: 'PASS' | 'FAIL' | 'BLOCKED' | 'PENDING';
  universe: 'OFFICIAL' | 'MANUAL_REVIEWED' | 'UNKNOWN';
  source_sha256: Sha256;
  updated_at: Utc;
};
export type ErrorRoot =
  | { route_id: "RUNS"; error: Omit<Error, "code"> & { code: "BAD_REQUEST" | "INVALID_CURSOR" | "INTERNAL_ERROR" } }
  | { route_id: "RUN_DETAIL"; error: Omit<Error, "code"> & { code: "NOT_FOUND" | "INTERNAL_ERROR" } }
  | { route_id: "EVENTS"; error: Omit<Error, "code"> & { code: "NOT_FOUND" | "INVALID_CURSOR" | "INTERNAL_ERROR" } }
  | { route_id: "MATRIX"; error: Omit<Error, "code"> & { code: "INTERNAL_ERROR" } }
  | { route_id: "LEDGER"; error: Omit<Error, "code"> & { code: "INVALID_CURSOR" | "INTERNAL_ERROR" } }
  | { route_id: "ARTIFACTS"; error: Omit<Error, "code"> & { code: "INVALID_CURSOR" | "INTERNAL_ERROR" } }
  | { route_id: "D0"; error: Omit<Error, "code"> & { code: "INTERNAL_ERROR" } }
  | { route_id: "D1"; error: Omit<Error, "code"> & { code: "INTERNAL_ERROR" } }
  | { route_id: "FIXTURE"; error: Omit<Error, "code"> & { code: "INTERNAL_ERROR" } };
export type RouteId =
  'RUNS' | 'RUN_DETAIL' | 'EVENTS' | 'MATRIX' | 'LEDGER' | 'ARTIFACTS' | 'D0' | 'D1' | 'FIXTURE';

export interface RunsRoot {
  route_id: 'RUNS';
  source: Source;
  locks: Locks;
  list: {
    /**
     * @maxItems 100
     */
    items: Run[];
    next_cursor: Cursor | null;
  };
}
export interface Source {
  source_sha256: Sha256;
  generated_at: Utc;
}
export interface Locks {
  promotion_allowed: false;
  model_build_allowed: false;
  paper_forward_allowed: false;
  live_broker_order_allowed: false;
  profitability_claim_allowed: false;
  go_summary_allowed: false;
}
export interface Run {
  run_id: RunId;
  run_uid?: RunId;
  run_revision?: RunRevision;
  state: RunState;
  source_sha256: Sha256;
  created_at: Utc;
}
export interface RunState {
  status: 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED';
  progress: Progress;
  updated_at: Utc;
  started_at: Utc | null;
  finished_at: Utc | null;
}
export interface Progress {
  step: number;
  total_steps: number;
  percent: number;
}
export interface RunDetailRoot {
  route_id: 'RUN_DETAIL';
  source: Source;
  run: Run;
  locks: Locks;
}
export interface EventsRoot {
  route_id: 'EVENTS';
  source: Source;
  locks: Locks;
  list: {
    /**
     * @maxItems 100
     */
    items: Event[];
    next_cursor: Cursor | null;
  };
  run_id: RunId;
}
export interface MatrixRoot {
  route_id: 'MATRIX';
  source: Source;
  locks: Locks;
  cells: MatrixCells;
  summary: MatrixSummary;
}
export interface MatrixCell {
  row_id: 'seed-01' | 'seed-02' | 'seed-03' | 'seed-04' | 'seed-05';
  column_id:
    | 'fold-01:baseline'
    | 'fold-01:cost-00bp'
    | 'fold-01:cost-23bp'
    | 'fold-01:cost-46bp'
    | 'fold-01:no-trade'
    | 'fold-02:baseline'
    | 'fold-02:cost-00bp'
    | 'fold-02:cost-23bp'
    | 'fold-02:cost-46bp'
    | 'fold-02:no-trade';
  state: 'PASS' | 'FAIL' | 'BLOCKED' | 'PENDING';
}
export interface MatrixSummary {
  total_cells: 50;
  pass_count: number;
  fail_count: number;
  blocked_count: number;
  pending_count: number;
}
export interface LedgerRoot {
  route_id: 'LEDGER';
  source: Source;
  locks: Locks;
  list: {
    /**
     * @maxItems 100
     */
    items: LedgerEntry[];
    next_cursor: Cursor | null;
  };
}
export interface LedgerEntry {
  entry_id: ArtifactId;
  occurred_at: Utc;
  kind: 'DEBIT' | 'CREDIT' | 'ADJUSTMENT';
  amount: number;
  currency: 'KRONOS_CREDIT';
  source_sha256: Sha256;
}
export interface ArtifactsRoot {
  route_id: 'ARTIFACTS';
  source: Source;
  locks: Locks;
  list: {
    /**
     * @maxItems 100
     */
    items: Download[];
    next_cursor: Cursor | null;
  };
}
export interface Download {
  artifact: Artifact;
  download_url: string;
  portable_filename: string;
  run_id?: RunId;
  run_revision?: RunRevision;
}
export interface Artifact {
  artifact_id: ArtifactId;
  filename: string;
  media_type: 'application/json' | 'text/csv' | 'application/jsonl' | 'text/markdown' | 'image/png';
  byte_length: number;
  sha256: Sha256;
  created_at: Utc;
}
export interface D0Root {
  route_id: 'D0';
  source: Source;
  d0: D0;
  locks: Locks;
}
export interface D1Root {
  route_id: 'D1';
  source: Source;
  d1: D1;
  locks: Locks;
}
export interface FixtureRoot {
  route_id: 'FIXTURE';
  source: Source;
  fixture: Fixture;
  locks: Locks;
}
export interface Fixture {
  fixture_id: ArtifactId;
  run: Run;
  source_sha256: Sha256;
  created_at: Utc;
}
export interface Error {
  code: 'BAD_REQUEST' | 'NOT_FOUND' | 'INVALID_CURSOR' | 'VALIDATION_ERROR' | 'INTERNAL_ERROR';
  message: string;
}

export type V5RouteId = RouteId;
export type V5DeepReadonly<T> = T extends (...args: never[]) => unknown ? T : T extends readonly (infer Item)[] ? readonly V5DeepReadonly<Item>[] : T extends object ? { readonly [K in keyof T]: V5DeepReadonly<T[K]> } : T;

export type V5RunsRoot = RunsRoot;
export type V5RunDetailRoot = RunDetailRoot;
export type V5EventsRoot = EventsRoot;
export type V5MatrixRoot = MatrixRoot;
export type V5LedgerRoot = LedgerRoot;
export type V5ArtifactsRoot = ArtifactsRoot;
export type V5D0Root = D0Root;
export type V5D1Root = D1Root;
export type V5FixtureRoot = FixtureRoot;
export type V5ErrorRoot = ErrorRoot;
