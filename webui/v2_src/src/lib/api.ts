// /api/training/* 엔드포인트 fetch 헬퍼.
// readonly only — 새 endpoint 도입 0건, 기존 응답 구조만 사용.

export interface TrainingStatus {
  run_name?: string;
  status: string;
  overall_percent?: number;
  stage_count?: number;
  stages: TrainingStage[];
  latest_stage?: TrainingStage;
  dataset_summary?: DatasetSummary;
  readiness?: {
    level: 'waiting' | 'training' | 'ready';
    label: string;
    message: string;
    predictor_started?: boolean;
    predictor_complete?: boolean;
    checkpoint_ready?: boolean;
  };
  updated_at?: string;
  default_training_refresh_seconds?: number;
  generated_at?: string;
}

export interface DatasetSplitSummary {
  name: 'train' | 'val' | 'test' | string;
  sessions?: number;
  first_session?: string | null;
  last_session?: string | null;
  groups?: number | null;
  rows?: number | null;
  possible_samples?: number | null;
  current_target_samples?: number | null;
}

export interface DatasetSummary {
  available: boolean;
  dataset_dir?: string | null;
  report_path?: string | null;
  source_db?: string | null;
  freq?: string | null;
  regularize_1s?: boolean;
  price_mode?: string | null;
  horizon_seconds?: number | null;
  lookback_window?: number | null;
  predict_window?: number | null;
  sample_window?: number | null;
  features?: string[];
  time_features?: string[];
  range?: {
    session_start?: string | null;
    session_end?: string | null;
    actual_start?: string | null;
    actual_end?: string | null;
    time_start?: string | null;
    time_end?: string | null;
  };
  counts?: {
    selected_table_count?: string | number | null;
    table_count?: number | null;
    tables_with_rows?: number | null;
    tables_zero_rows?: number | null;
    exported_group_count?: number | null;
    exported_row_count?: number | null;
    regularized_groups?: number | null;
    regularized_inserted_rows?: number | null;
  };
  splits?: Record<string, DatasetSplitSummary>;
  current_targets?: {
    train_samples?: number | null;
    val_samples?: number | null;
  };
  warnings?: string[];
  message?: string;
}

export interface TrainingStage {
  train_stage: string;
  stage_index?: number;
  stage_count?: number;
  step?: number;
  total_steps?: number;
  overall_percent?: number;
  stage_percent?: number;
  eta_seconds?: number;
  samples_per_second?: number;
  last_loss?: number | null;
  last_validation_loss?: number | null;
  phase?: string | null;
  validation_step?: number | null;
  validation_total_steps?: number | null;
  validation_samples?: number | null;
  validation_fraction?: number | null;
  epoch?: number | null;
  epochs?: number | null;
  status?: string;
  updated_at?: string;
}

export interface HistoryPoint {
  step: number;
  loss: number;
  learning_rate?: number;
  epoch?: number;
  epochs?: number;
}

export interface HistoryResponse {
  points: HistoryPoint[];
  latest_point?: HistoryPoint & { line?: string };
  latest_progress?: {
    eta_seconds?: number;
    samples_per_second?: number;
    last_loss?: number;
    step?: number;
    overall_percent?: number;
    stage_percent?: number;
    updated_at?: string;
  };
  run_name?: string;
  stage?: string;
  source_log_path?: string;
}

export interface ArtifactsResponse {
  checkpoint_file_count: number;
  model_weight_file_count: number;
  checkpoint_ready: boolean;
  predictor_started: boolean;
  label: string;
  message: string;
  recent_checkpoint_files: Array<{ path?: string; name?: string } | string>;
  recent_model_weight_files: Array<{ path?: string; name?: string } | string>;
  stages?: {
    tokenizer?: { checkpoint_ready: boolean };
    predictor?: { checkpoint_ready: boolean };
  };
  run_name?: string;
}

export interface GpuResponse {
  gpus: Array<{
    name?: string;
    utilization_gpu_percent?: number;
    temperature_c?: number;
    memory_used_mib?: number;
    memory_total_mib?: number;
    memory_used_percent?: number;
    power_limit_watts?: number;
    power_draw_watts?: number;
    power_draw_available?: boolean;
  }>;
  total_memory_used_percent?: number;
  generated_at?: string;
  available: boolean;
}

export interface SystemResponse {
  available: boolean;
  cpu?: {
    utilization_percent?: number | null;
    temperature_c?: number | null;
    temperature_limit_c?: number | null;
    temperature_percent?: number | null;
    temperature_available?: boolean;
    temperature_source?: string | null;
    utilization_source?: string | null;
  };
  memory?: {
    used_percent?: number | null;
    total_bytes?: number | null;
    available_bytes?: number | null;
  };
  generated_at?: string;
}

export interface RlRunRecord {
  name: string;
  artifact_type: 'contextual_bandit' | 'cost_gate' | 'baseline' | 'episode_manifest' | string;
  modified_at?: string;
  summary?: Record<string, any>;
  policies?: string[];
}

export interface RlRunsResponse {
  runs: RlRunRecord[];
}

export interface RlRunDetail extends RlRunRecord {
  artifacts?: Array<{
    name: string;
    suffix?: string;
    size_bytes?: number;
    modified_at?: string;
  }>;
  detail?: Record<string, any>;
  model?: {
    model_type?: string;
    feature_columns?: string[];
    train_summary?: Record<string, any>;
  };
}

export interface RlTableResponse {
  run?: string;
  artifact_type?: string;
  table?: string;
  policy?: string | null;
  source_file?: string;
  rows: Array<Record<string, any>>;
  row_count?: number;
  truncated?: boolean;
  policies?: string[];
}

export interface RlCostGateResponse {
  run?: string;
  artifact_type?: string;
  summary?: Record<string, any>;
  gate?: RlTableResponse;
  scenario?: RlTableResponse;
  rolling?: RlTableResponse;
}

async function fetchJson<T>(url: string): Promise<T | null> {
  try {
    const r = await fetch(url);
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch {
    return null;
  }
}

export const api = {
  status: () => fetchJson<TrainingStatus>('/api/training/status'),
  history: (limit: number = 200) => fetchJson<HistoryResponse>(`/api/training/history?limit=${limit}`),
  artifacts: () => fetchJson<ArtifactsResponse>('/api/training/artifacts'),
  gpu: () => fetchJson<GpuResponse>('/api/training/gpu'),
  system: () => fetchJson<SystemResponse>('/api/training/system'),
  rlRuns: (limit: number = 20) => fetchJson<RlRunsResponse>(`/api/rl/runs?limit=${limit}`),
  rlRun: (run: string) => fetchJson<RlRunDetail>(`/api/rl/runs/${encodeURIComponent(run)}`),
  rlActions: (run: string, limit: number = 500) =>
    fetchJson<RlTableResponse>(`/api/rl/runs/${encodeURIComponent(run)}/actions?limit=${limit}`),
  rlTrades: (run: string, limit: number = 500) =>
    fetchJson<RlTableResponse>(`/api/rl/runs/${encodeURIComponent(run)}/trades?limit=${limit}`),
  rlEquity: (run: string, limit: number = 500) =>
    fetchJson<RlTableResponse>(`/api/rl/runs/${encodeURIComponent(run)}/equity?limit=${limit}`),
  rlEpisodes: (run: string, limit: number = 500) =>
    fetchJson<RlTableResponse>(`/api/rl/runs/${encodeURIComponent(run)}/episodes?limit=${limit}`),
  rlTable: (run: string, table: string, limit: number = 500) =>
    fetchJson<RlTableResponse>(
      `/api/rl/runs/${encodeURIComponent(run)}/table/${encodeURIComponent(table)}?limit=${limit}`
    ),
  rlCostGate: (run: string, limit: number = 500) =>
    fetchJson<RlCostGateResponse>(`/api/rl/runs/${encodeURIComponent(run)}/cost-gate?limit=${limit}`),
};
