// /api/training/* 엔드포인트 fetch 헬퍼.
// readonly only — 새 endpoint 도입 0건, 기존 응답 구조만 사용.

export interface TrainingStatus {
  status: string;
  stages: TrainingStage[];
  latest_stage?: TrainingStage;
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
}

export interface TrainingStage {
  train_stage: string;
  step?: number;
  total_steps?: number;
  overall_percent?: number;
  stage_percent?: number;
  eta_seconds?: number;
  samples_per_second?: number;
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
};
