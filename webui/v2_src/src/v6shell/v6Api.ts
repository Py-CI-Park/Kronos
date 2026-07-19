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
