import ky, { HTTPError, TimeoutError, type KyInstance } from 'ky';
import { z, ZodError } from 'zod';

export const ResearchRunSchema = z.object({
  run_id: z.string().min(1),
  name: z.string().min(1),
  lane: z.string().min(1),
  status: z.string().min(1),
  algorithm: z.string().min(1),
  dataset_id: z.string().min(1),
  updated_at: z.string().min(1),
  source_file: z.string().min(1),
  artifact_count: z.number().int().nonnegative(),
  detail_url: z.string().startsWith('/api/v6/research-runs/'),
}).readonly();

const ProgramScoresSchema = z.object({
  maturity_score: z.number().min(0).max(100),
  implementation_score: z.number().min(0).max(100),
  economic_model_score: z.number().min(0).max(100),
  live_readiness_score: z.number().min(0).max(100),
}).readonly();

export const ResearchSummarySchema = z.object({
  schema_version: z.literal('kronos_v6_research_summary.v1'),
  status: z.literal('OK'),
  generated_at: z.string().min(1),
  program: ProgramScoresSchema,
  catalog: z.object({
    total: z.number().int().nonnegative(),
    by_status: z.record(z.string(), z.number().int().nonnegative()),
    latest_run: ResearchRunSchema.nullable(),
  }).readonly(),
  claims: z.object({ profitability: z.literal(false), live_ready: z.literal(false), fresh_oos_opened: z.literal(false) }).readonly(),
}).readonly();

export const ResearchPageSchema = z.object({
  schema_version: z.literal('kronos_v6_research_runs.v1'),
  status: z.literal('OK'),
  items: z.array(ResearchRunSchema).readonly(),
  total: z.number().int().nonnegative(),
  page: z.number().int().positive(),
  page_size: z.number().int().positive(),
}).readonly();

const ArtifactSchema = z.object({
  name: z.string().min(1),
  relative_path: z.string().min(1),
  size_bytes: z.number().int().nonnegative(),
  modified_at: z.string().min(1),
}).readonly();

export const ResearchRunDetailSchema = z.object({
  schema_version: z.literal('kronos_v6_research_run_detail.v1'),
  status: z.literal('OK'),
  run: ResearchRunSchema,
  artifacts: z.array(ArtifactSchema).readonly(),
  evidence_scope: z.literal('DIRECT_DIRECTORY_METADATA_ONLY'),
}).readonly();

export type ResearchRun = z.infer<typeof ResearchRunSchema>;
export type ResearchSummary = z.infer<typeof ResearchSummarySchema>;
export type ResearchPage = z.infer<typeof ResearchPageSchema>;
export type ResearchRunDetail = z.infer<typeof ResearchRunDetailSchema>;

export type ResearchFilters = {
  readonly search: string;
  readonly lane: string;
  readonly status: string;
  readonly page: number;
  readonly pageSize: number;
};

export type ResearchApiErrorKind = 'http' | 'timeout' | 'network' | 'schema';
export type ResearchApiResult<T> =
  | { readonly ok: true; readonly data: T }
  | { readonly ok: false; readonly kind: ResearchApiErrorKind; readonly message: string };

const RESEARCH_SUMMARY_TIMEOUT_MS = 20_000;

const researchClient = ky.create({
  timeout: 8_000,
  retry: { limit: 1, methods: ['get'], statusCodes: [408, 429, 500, 502, 503, 504] },
  headers: { Accept: 'application/json' },
});

export function buildResearchRunsUrl(filters: ResearchFilters): string {
  const params = new URLSearchParams();
  if (filters.search) params.set('search', filters.search);
  if (filters.lane) params.set('lane', filters.lane);
  if (filters.status) params.set('status', filters.status);
  params.set('page', String(filters.page));
  params.set('page_size', String(filters.pageSize));
  return `/api/v6/research-runs?${params.toString()}`;
}

function encodedRunPath(runId: string): string {
  return runId.split('/').map((segment) => encodeURIComponent(segment)).join('/');
}

async function requestParsed<T>(path: string, schema: z.ZodType<T>, timeoutMs = 8_000, client: KyInstance = researchClient): Promise<ResearchApiResult<T>> {
  try {
    const payload = await client.get(path, { timeout: timeoutMs }).json();
    return { ok: true, data: schema.parse(payload) };
  } catch (error) {
    if (error instanceof TimeoutError) return { ok: false, kind: 'timeout', message: '응답 제한 시간을 초과했습니다.' };
    if (error instanceof HTTPError) return { ok: false, kind: 'http', message: `API HTTP ${error.response.status}` };
    if (error instanceof ZodError) return { ok: false, kind: 'schema', message: 'API 응답 계약이 일치하지 않습니다.' };
    if (error instanceof TypeError) return { ok: false, kind: 'network', message: '대시보드 API에 연결할 수 없습니다.' };
    throw error;
  }
}

export const loadResearchSummary = (timeoutMs = RESEARCH_SUMMARY_TIMEOUT_MS, client: KyInstance = researchClient, path = '/api/v6/summary'): Promise<ResearchApiResult<ResearchSummary>> =>
  requestParsed(path, ResearchSummarySchema, timeoutMs, client);

export const loadResearchRuns = (filters: ResearchFilters): Promise<ResearchApiResult<ResearchPage>> =>
  requestParsed(buildResearchRunsUrl(filters), ResearchPageSchema);

export const loadResearchRunDetail = (runId: string): Promise<ResearchApiResult<ResearchRunDetail>> =>
  requestParsed(`/api/v6/research-runs/${encodedRunPath(runId)}`, ResearchRunDetailSchema);
