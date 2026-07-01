export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export type CommandCard = {
  id: string;
  title: string;
  value: JsonValue;
  status: string;
  label: string;
};

export type StatusLock = {
  locked: boolean;
  status: string;
  label: string;
  allowed?: boolean;
  enabled?: boolean;
  capability_state?: 'BLOCKED' | string;
  reason?: string;
};

export type StatusPayload = {
  api_status: string;
  mode: string;
  labels: string[];
  cost_assumption_bps: number;
  claim_locks: Record<string, boolean>;
  status_locks: Record<string, StatusLock>;
  controls?: {
    research_intent_record_allowed?: boolean;
    unsafe_trading_controls_allowed?: boolean;
    job_post_endpoint: string;
    allowed_workflows?: string[];
  };
  first_viewport: {
    sections: string[];
    cards: CommandCard[];
  };
  evidence_health: Record<string, { present: boolean; status: string; fields: string[] }>;
  artifact_manifest_schema?: {
    required_fields: string[];
    symbols_are_strings: boolean;
    capability_state: string;
    row_count_required_when_applicable?: boolean;
    accepted_research_evidence_kinds?: Record<string, unknown>;
  };
  queue_summary?: {
    mode: string;
    active_job_count: number;
    recorded_intent_count: number;
    latest_status: string;
    latest_job_id: string | null;
    status_counts: Record<string, number>;
    allowed_workflows: string[];
    unsafe_controls_allowed: boolean;
  };
};

export type WorkflowStep = {
  step: string;
  name: string;
  status: string;
  allowed: boolean;
  enabled?: boolean;
  review_allowed?: boolean;
  capability_state?: 'BLOCKED' | string;
  blocker_reason?: string;
  source_run_id?: string;
  artifact_refs?: string[];
  updated_at?: string | null;
};

export type WorkflowPayload = {
  workflow_id: string;
  status: string;
  labels: string[];
  process_map: WorkflowStep[];
  forbidden_work: string[];
};

export type AuditPayload = {
  status: string;
  labels: string[];
  run_id: string;
  events: Array<Record<string, string>>;
};

export type EvidenceArtifact = {
  artifact_id: string;
  run_id?: string;
  kind: string;
  series_source?: string;
  hash: string | null;
  path: string | null;
  timestamp: string | null;
  freshness: string;
  schema_status: string;
  status: string;
  blocker_reason: string;
  source_stage: string;
  source_run_id: string;
  symbols: string[];
  row_count?: number;
};

export type EvidencePayload = {
  run_id: string;
  status: string;
  labels: string[];
  symbols: string[];
  artifact_schema?: {
    required_fields: string[];
    row_count_required_when_applicable?: boolean;
    accepted_research_evidence_kinds?: Record<string, unknown>;
    allowed_roots?: string[];
  };
  artifacts: EvidenceArtifact[];
};
export type DrilldownTab = {
  id: string;
  title: string;
  description: string;
  source: string;
  preview_hash: string;
  path_safe: boolean;
  hash_backed: boolean;
  row_count: number;
  rows: JsonValue[];
  raw_json: JsonValue;
};

export type DrilldownPayload = {
  run_id: string;
  status: string;
  labels: string[];
  safe_preview_policy: {
    max_preview_chars: number;
    path_safe: boolean;
    hash_backed: boolean;
    allowed_roots?: string[];
    active_job_count: number;
    unsafe_controls_allowed: boolean;
  };
  queue_summary: StatusPayload['queue_summary'];
  tabs: DrilldownTab[];
};

export type ApiState<T> = {
  data: T;
  failedClosed: boolean;
};

export type ExperimentPreset = {
  id: string;
  nameKo: string;
  nameEn: string;
  description: string;
  status: string;
  safeAction: string;
};

export type RunComparisonRow = {
  metric: string;
  value: string;
  status: string;
  evidence: string;
  source: string;
};

export type AuditTimelineRow = {
  index: string;
  event: string;
  status: string;
  details: string;
};
