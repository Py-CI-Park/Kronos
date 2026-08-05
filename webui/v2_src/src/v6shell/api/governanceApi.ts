import ky, { HTTPError, TimeoutError } from 'ky';
import { z, ZodError } from 'zod';
import type { ResearchApiResult } from './researchApi';

const Sha256Schema = z.string().regex(/^[0-9a-f]{64}$/u);

const GovernancePreregistrationSchema = z.object({
  prereg_id: z.string().min(1),
  doc: z.string().min(1),
  status: z.string().min(1),
  frozen_utc: z.string().min(1),
  family: z.string().min(1),
  sha256: Sha256Schema,
  linkage_state: z.literal('DETAIL_DEFERRED'),
}).readonly();

const GovernanceResultDocSchema = z.object({
  doc: z.string().min(1),
  size_bytes: z.number().int().nonnegative(),
  sha256: Sha256Schema,
}).readonly();

export const GovernanceSummarySchema = z.object({
  schema_version: z.literal('kronos_v6_governance_summary.v1'),
  status: z.literal('OK'),
  generated_at: z.string().min(1),
  preregistrations: z.array(GovernancePreregistrationSchema).readonly(),
  result_docs: z.array(GovernanceResultDocSchema).readonly(),
  claims: z.object({
    fresh_oos_opened: z.literal(false),
    promotion_allowed: z.literal(false),
    human_approval_required: z.literal(true),
  }).readonly(),
}).readonly();

export type GovernanceSummary = z.infer<typeof GovernanceSummarySchema>;

const client = ky.create({
  timeout: 8_000,
  retry: { limit: 1, methods: ['get'], statusCodes: [408, 429, 500, 502, 503, 504] },
  headers: { Accept: 'application/json' },
});

export async function loadGovernanceSummary(): Promise<ResearchApiResult<GovernanceSummary>> {
  try {
    const payload = await client.get('/api/v6/governance-summary').json();
    return { ok: true, data: GovernanceSummarySchema.parse(payload) };
  } catch (error) {
    if (error instanceof TimeoutError) return { ok: false, kind: 'timeout', message: '거버넌스 요약 응답 시간이 초과됐습니다.' };
    if (error instanceof HTTPError) return { ok: false, kind: 'http', message: `거버넌스 API HTTP ${error.response.status}` };
    if (error instanceof ZodError) return { ok: false, kind: 'schema', message: '거버넌스 요약 계약이 일치하지 않습니다.' };
    if (error instanceof TypeError) return { ok: false, kind: 'network', message: '거버넌스 API에 연결할 수 없습니다.' };
    throw error;
  }
}
