import type { ResearchRun } from '../../api/researchApi';

export type ResultEvidenceHealth = {
  readonly observed: number;
  readonly total: number;
  readonly percent: number;
  readonly missing: readonly string[];
};

export function resultEvidenceHealth(run: ResearchRun): ResultEvidenceHealth {
  const fields = [
    ['알고리즘', run.algorithm !== 'MISSING'],
    ['데이터셋', run.dataset_id !== 'MISSING'],
    ['근거 파일', run.source_file !== 'MISSING'],
    ['산출물', run.artifact_count > 0],
  ] as const;
  const missing = fields.filter(([, observed]) => !observed).map(([label]) => label);
  const observed = fields.length - missing.length;
  return { observed, total: fields.length, percent: (observed / fields.length) * 100, missing };
}
