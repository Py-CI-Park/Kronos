export type RunStatusTone = 'danger' | 'warning' | 'neutral';

export function runStatusLabel(status: string | null | undefined): string {
  if (!status) return 'MISSING';
  if (status === 'REPRODUCTION_MISMATCH_VALIDATION_CONSUMED') return 'REPRO FAIL';
  if (status === 'REPRODUCTION_ONLY_VALIDATION_CONSUMED') return 'REPRO ONLY';
  if (status === 'LEGACY_EXPLORATORY_CANDIDATE_TEST_FEATURES_CONSUMED') return 'LEGACY · TEST CONTAMINATED';
  if (status === 'VALIDATION_CANDIDATE') return 'CANDIDATE';
  if (status.includes('NO_GO') || status.includes('NO-GO')) return 'NO-GO';
  return status;
}

export function runStatusTone(status: string | null | undefined): RunStatusTone {
  if (!status) return 'neutral';
  if (
    status === 'REPRODUCTION_MISMATCH_VALIDATION_CONSUMED'
    || status === 'LEGACY_EXPLORATORY_CANDIDATE_TEST_FEATURES_CONSUMED'
    || /NO[_-]?GO|CORRUPT|TOO_LARGE|BLOCKED/u.test(status)
  ) return 'danger';
  if (status === 'REPRODUCTION_ONLY_VALIDATION_CONSUMED' || status.includes('CANDIDATE')) return 'warning';
  return 'neutral';
}
