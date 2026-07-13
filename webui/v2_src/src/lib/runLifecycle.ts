// Todo 6 — truthful RL lifecycle status end to end (client-side derivation).
//
// The backend (_run_lifecycle in webui/rl_dashboard_runs.py) emits a single-read
// snapshot per run: COMPLETED | REPLAY | IDLE | MISSING. It NEVER emits RUNNING
// or STALE and `is_live` is always false — a single read cannot observe an
// advancing step. RUNNING/STALE must be derived on the client by observing
// `global_step` advance (or fail to advance) across polls of a live source.

export type LifecycleStatus = 'RUNNING' | 'COMPLETED' | 'STALE' | 'REPLAY' | 'IDLE' | 'MISSING';

export interface RunLifecycle {
  readonly status: LifecycleStatus;
  readonly is_live: boolean;
  readonly event_file: string | null;
  readonly event_count: number;
  readonly last_step: number | null;
  readonly event_mtime_age_sec: number | null;
  readonly last_phase: string | null;
  readonly is_replay: boolean;
  readonly poll_interval_seconds: number;
}

export interface LiveObservation {
  readonly prevStep: number | null;
  readonly currentStep: number | null;
  readonly polling: boolean;
  readonly wasRunning: boolean;
}

/**
 * Derive the honest display status for a run by combining the backend's
 * single-read snapshot (`lc`) with a client-side cross-poll observation
 * (`obs`) of whether `global_step` is actually advancing.
 *
 * - `lc == null` -> 'MISSING'.
 * - `lc.status` in {'MISSING','IDLE','REPLAY'} -> passed through as-is; these
 *   states are never LIVE regardless of polling/step observation.
 * - Otherwise (backend reports 'COMPLETED', which is the only status a fresh
 *   run can carry) — compute freshness from `event_mtime_age_sec` vs.
 *   `2 * poll_interval_seconds`, and advancing from `currentStep > prevStep`.
 *   - polling && advancing && fresh -> 'RUNNING'.
 *   - polling && wasRunning && !advancing -> 'STALE' (was live, stopped advancing).
 *   - otherwise -> 'COMPLETED'.
 */
export function deriveDisplayStatus(lc: RunLifecycle | null, obs: LiveObservation): LifecycleStatus {
  if (lc == null) return 'MISSING';
  if (lc.status === 'MISSING' || lc.status === 'IDLE' || lc.status === 'REPLAY') return lc.status;

  const fresh = lc.event_mtime_age_sec != null && lc.event_mtime_age_sec <= 2 * lc.poll_interval_seconds;
  const advancing = obs.prevStep != null && obs.currentStep != null && obs.currentStep > obs.prevStep;

  if (obs.polling && advancing && fresh) return 'RUNNING';
  if (obs.polling && obs.wasRunning && !advancing) return 'STALE';
  return 'COMPLETED';
}

export function isLive(status: LifecycleStatus): boolean {
  return status === 'RUNNING';
}

export function statusLabel(status: LifecycleStatus): string {
  switch (status) {
    case 'RUNNING':
      return 'LIVE';
    case 'COMPLETED':
      return 'COMPLETED';
    case 'STALE':
      return 'STALE';
    case 'REPLAY':
      return 'REPLAY';
    case 'IDLE':
      return 'IDLE';
    case 'MISSING':
      return 'MISSING';
    default:
      return status;
  }
}

export function statusTone(status: LifecycleStatus): 'accent' | 'warn' | 'ok' | 'danger' | 'idle' {
  switch (status) {
    case 'RUNNING':
      return 'accent';
    case 'STALE':
      return 'warn';
    case 'IDLE':
      return 'idle';
    case 'COMPLETED':
      return 'ok';
    case 'REPLAY':
      return 'warn';
    case 'MISSING':
      return 'danger';
    default:
      return 'idle';
  }
}
