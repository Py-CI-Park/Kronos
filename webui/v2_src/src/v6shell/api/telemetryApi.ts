import ky, { HTTPError, TimeoutError } from 'ky';
import { z, ZodError } from 'zod';
import type { ResearchApiResult } from './researchApi';

const TelemetryRunSchema = z.object({
  run_id: z.string().min(1),
  name: z.string().min(1),
  lane: z.string().min(1),
  status: z.string().min(1),
  algorithm: z.string().min(1),
  event_bytes: z.number().int().nonnegative(),
  updated_at: z.string().min(1),
}).readonly();

export const TelemetryRunsSchema = z.object({
  schema_version: z.literal('kronos_v6_telemetry_runs.v1'),
  status: z.literal('OK'),
  items: z.array(TelemetryRunSchema).readonly(),
  total: z.number().int().nonnegative(),
}).readonly();

export const TelemetryPointSchema = z.object({
  step: z.number().int().nonnegative(),
  phase: z.string().min(1),
  reward: z.number().nullable(),
  equity: z.number().nullable(),
  loss: z.number().nullable(),
  exploration: z.number().nullable(),
  action_name: z.string().min(1),
  timestamp: z.string().min(1),
  reward_kind: z.enum(['raw_reward', 'return_fraction', 'return_percent', 'nav_delta', 'cumulative_pnl']).nullable().default(null),
  reward_unit: z.enum(['score', 'fraction', 'percent', 'krw', 'normalized', 'unknown']).nullable().default(null),
  equity_kind: z.enum(['normalized_nav', 'krw_nav', 'cumulative_pnl', 'raw_equity']).nullable().default(null),
  equity_unit: z.enum(['score', 'fraction', 'percent', 'krw', 'normalized', 'unknown']).nullable().default(null),
  action_recorded: z.boolean().nullable().default(null),
}).readonly();

export const TelemetrySnapshotSchema = z.object({
  schema_version: z.literal('kronos_v6_run_telemetry.v1'),
  status: z.literal('OK'),
  run_id: z.string().min(1),
  follow_mode: z.enum(['FOLLOWING_FILE', 'HISTORICAL_SNAPSHOT']),
  sampling: z.enum(['FULL_FILE', 'HEAD_TAIL_SAMPLE']),
  event_bytes: z.number().int().nonnegative(),
  invalid_lines: z.number().int().nonnegative(),
  updated_at: z.string().min(1),
  points: z.array(TelemetryPointSchema).readonly(),
  claims: z.object({ live_stream: z.boolean(), profitability: z.literal(false) }).readonly(),
}).readonly();

export type TelemetryRun = z.infer<typeof TelemetryRunSchema>;
export type TelemetryRuns = z.infer<typeof TelemetryRunsSchema>;
export type TelemetryPoint = z.infer<typeof TelemetryPointSchema>;
export type TelemetrySnapshot = z.infer<typeof TelemetrySnapshotSchema>;

const client = ky.create({
  timeout: 8_000,
  retry: { limit: 1, methods: ['get'], statusCodes: [408, 429, 500, 502, 503, 504] },
  headers: { Accept: 'application/json' },
});

function encodedRunPath(runId: string): string {
  return runId.split('/').map((segment) => encodeURIComponent(segment)).join('/');
}

export function buildTelemetryUrl(runId: string, limit: number): string {
  return `/api/v6/research-runs/${encodedRunPath(runId)}/telemetry?limit=${limit}`;
}

async function requestParsed<T>(path: string, schema: z.ZodType<T>): Promise<ResearchApiResult<T>> {
  try {
    const payload = await client.get(path).json();
    return { ok: true, data: schema.parse(payload) };
  } catch (error) {
    if (error instanceof TimeoutError) return { ok: false, kind: 'timeout', message: '텔레메트리 응답 시간이 초과됐습니다.' };
    if (error instanceof HTTPError) return { ok: false, kind: 'http', message: `텔레메트리 API HTTP ${error.response.status}` };
    if (error instanceof ZodError) return { ok: false, kind: 'schema', message: '텔레메트리 응답 계약이 일치하지 않습니다.' };
    if (error instanceof TypeError) return { ok: false, kind: 'network', message: '텔레메트리 API에 연결할 수 없습니다.' };
    throw error;
  }
}

export const loadTelemetryRuns = (): Promise<ResearchApiResult<TelemetryRuns>> =>
  requestParsed('/api/v6/telemetry-runs', TelemetryRunsSchema);

export const loadTelemetry = (runId: string, limit = 500): Promise<ResearchApiResult<TelemetrySnapshot>> =>
  requestParsed(buildTelemetryUrl(runId, limit), TelemetrySnapshotSchema);
