export interface V6ApiResult<T> {
  readonly ok: boolean;
  readonly data?: T;
  readonly error?: string;
}

export interface V6JourneyStep {
  readonly state?: string;
}

export interface V6Status {
  readonly schema_version?: string;
  readonly status?: string;
  readonly journey: {
    readonly data: V6JourneyStep & {
      readonly universe_manifest?: string;
      readonly universe_size?: number;
      readonly index_overlay?: string;
      readonly index_blocker_reason?: string;
    };
    readonly experiment: V6JourneyStep;
    readonly training: V6JourneyStep;
    readonly evaluation: V6JourneyStep;
    readonly report: V6JourneyStep;
  };
  readonly locks: Record<string, boolean>;
}

export interface V6UniverseRow {
  readonly table?: string;
  readonly code?: string;
  readonly rows?: number;
  readonly first_date?: string;
  readonly last_date?: string;
}

export interface V6Universe {
  readonly status?: string;
  readonly manifest?: string;
  readonly sha256?: string;
  readonly universe: readonly V6UniverseRow[];
  readonly total?: number;
  readonly filters?: unknown;
  readonly instrument_type?: string;
  readonly price_basis?: string;
}

export interface V6DataReadiness {
  readonly daily_db: {
    readonly present?: boolean;
    readonly state?: string;
    readonly size_bytes?: number;
    readonly mtime?: string;
    readonly mtime_epoch?: number;
    readonly table_count?: number;
  };
  readonly fivemin_db: {
    readonly present?: boolean;
    readonly state?: string;
    readonly size_bytes?: number;
  };
  readonly audit: {
    readonly population?: unknown;
    readonly filters?: unknown;
    readonly disclaimers?: unknown;
  };
  readonly index: {
    readonly state?: string;
    readonly reason?: string;
  };
  readonly price_basis: {
    readonly status?: string;
    readonly decision_grade_returns?: boolean;
  };
}
export interface V6Experiment {
  readonly prereg?: {
    readonly state?: string;
    readonly path?: string;
    readonly sha256?: string;
  };
  readonly planned?: {
    readonly strategy?: string;
    readonly horizons?: { readonly primary?: unknown; readonly validation?: unknown };
    readonly execution?: { readonly price_basis?: unknown; readonly official_close?: boolean };
    readonly capital?: {
      readonly initial_krw?: number;
      readonly slots?: number;
      readonly slot_budget_krw?: number;
      readonly reserve_krw?: number;
    };
    readonly costs?: { readonly primary?: unknown; readonly zero_control?: unknown; readonly stress?: unknown };
    readonly universe?: { readonly manifest?: unknown; readonly size?: unknown };
    readonly dataset_contract?: unknown;
    readonly seeds?: unknown;
    readonly constraints?: unknown;
  };
  readonly locks?: Record<string, boolean>;
}

export interface V6DatasetRun {
  readonly run_id?: string;
  readonly path?: string;
  readonly generated_utc?: string;
  readonly split_row_counts?: unknown;
  readonly sha256?: string;
}

export interface V6TrainingRun {
  readonly run_id?: string;
  readonly path?: string;
  readonly state?: string;
  readonly seeds?: unknown;
  readonly generated_utc?: string;
  readonly dataset_run_id?: string;
  readonly verdict_candidate?: { readonly value?: string; readonly reasons?: readonly unknown[] };
}
export interface V6Runs {
  readonly datasets?: readonly V6DatasetRun[];
  readonly runs?: readonly V6TrainingRun[];
  readonly training_state?: string;
}
export interface V6RunSeed {
  readonly episodes_ran?: number;
  readonly best_episode?: number;
  readonly final_val_metrics?: {
    readonly nav?: number;
    readonly total_net_return_pct?: number;
    readonly max_drawdown?: number;
    readonly trade_count?: number;
    readonly cost_scenario_navs?: Record<string, number>;
  };
}

export interface V6RunDetail {
  readonly status?: string;
  readonly dataset_run_id?: string;
  readonly train_run_id?: string;
  readonly manifest?: {
    readonly per_seed?: Record<string, V6RunSeed>;
    readonly baselines?: Record<string, { readonly nav?: number }>;
    readonly shuffled_label_control?: Record<string, V6RunSeed>;
    readonly verdict_candidate?: { readonly value?: string; readonly reasons?: readonly unknown[] };
    readonly test?: { readonly state?: string };
    readonly seeds?: unknown;
    readonly false_research_locks?: unknown;
  };
  readonly manifest_sha256?: string;
  readonly events_tail?: readonly { readonly episode?: unknown; readonly val_nav?: unknown }[];
  readonly reason?: string;
}


async function getV6<T>(path: string): Promise<V6ApiResult<T>> {
  try {
    const response = await fetch(path, { headers: { Accept: 'application/json' } });
    if (!response.ok) return { ok: false, error: `요청 실패 (${response.status})` };
    return { ok: true, data: await response.json() as T };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : '네트워크 요청에 실패했습니다.' };
  }
}

export const getV6Status = (): Promise<V6ApiResult<V6Status>> => getV6('/api/v6/status');
export const getV6Universe = (limit: number): Promise<V6ApiResult<V6Universe>> =>
  getV6(`/api/v6/universe?limit=${encodeURIComponent(String(limit))}`);
export const getV6DataReadiness = (): Promise<V6ApiResult<V6DataReadiness>> => getV6('/api/v6/data-readiness');
export const getV6Experiment = (): Promise<V6ApiResult<V6Experiment>> => getV6('/api/v6/experiment');
export const getV6Runs = (): Promise<V6ApiResult<V6Runs>> => getV6('/api/v6/runs');
export const getV6RunDetail = (dataset: string, train: string): Promise<V6ApiResult<V6RunDetail>> =>
  getV6(`/api/v6/run-detail?dataset=${encodeURIComponent(dataset)}&train=${encodeURIComponent(train)}`);
