import type { AuditPayload, DrilldownPayload, EvidenceArtifact, EvidencePayload, JsonValue, StatusPayload } from '../tradingTypes';
import { FALLBACK_STATUS } from '../tradingApi';
import { statusLabel } from '../tradingFormat';

export function IntentHistory({
  audit,
  evidence,
  status,
  fetchBanner,
  jobMessage,
  allowedWorkflowLabel,
  primaryAuditArtifact,
  drilldown,
}: {
  audit: AuditPayload;
  evidence: EvidencePayload;
  status: StatusPayload;
  fetchBanner: string;
  jobMessage: string;
  allowedWorkflowLabel: string;
  primaryAuditArtifact: EvidenceArtifact;
  drilldown: DrilldownPayload;
}) {
  const intentTab = drilldown.tabs.find((tab) => tab.id === 'research_intents');
  const intentRows = (intentTab?.rows ?? []).filter((row): row is Record<string, JsonValue> => Boolean(row) && typeof row === 'object' && !Array.isArray(row));
  return (
    <article className="panel audit-panel">
      <div className="panel-heading">
        <p className="eyebrow">감사 로그</p>
        <h2>무엇이 기록됐는지</h2>
      </div>
      <p className="status-line" role="status" aria-live="polite">{fetchBanner}</p>
      <div className="queue-summary" data-research-queue-summary="true" role="status" aria-live="polite" title="허용된 workflow만 연구 의도로 기록됩니다.">
        <span>연구 큐</span>
        <strong>기록 {status.queue_summary?.recorded_intent_count ?? 0} · 실행 {status.queue_summary?.active_job_count ?? 0}</strong>
        <small>{statusLabel(status.queue_summary?.latest_status ?? 'NOT_STARTED')} · 허용 workflow {allowedWorkflowLabel} · active count zero</small>
      </div>
      <div className="queue-guardrail-matrix" aria-label="연구 큐 안전 경계">
        <div>
          <span>허용 workflow</span>
          <strong>{allowedWorkflowLabel}</strong>
          <small>기록만 허용 · 실행/학습/주문 시작 없음</small>
        </div>
        <div>
          <span>차단 workflow</span>
          <strong>live · broker · order · account · paper · model_build · profit_claim</strong>
          <small>unsafe_controls_allowed {String(status.queue_summary?.unsafe_controls_allowed ?? false)}</small>
        </div>
        <div>
          <span>active job count</span>
          <strong>{status.queue_summary?.active_job_count ?? 0}</strong>
          <small>0이 아니면 이 화면은 NO-GO로 봅니다.</small>
        </div>
      </div>
      <div className="audit-source-grid" aria-label="감사 로그 증거 출처">
        <span>audit run <strong>{audit.run_id}</strong></span>
        <span>evidence run <strong>{evidence.run_id}</strong></span>
        <span>hash <strong>{primaryAuditArtifact.hash ?? '없음'}</strong></span>
        <span>{statusLabel(primaryAuditArtifact.freshness)} / {statusLabel(primaryAuditArtifact.schema_status)}</span>
        <span>{primaryAuditArtifact.blocker_reason}</span>
      </div>
      <div className="intent-history-grid" data-research-intent-history="true">
        <div className="intent-history-head">
          <span>recorded-only jobs</span>
          <strong>active {drilldown.safe_preview_policy.active_job_count}</strong>
          <small>hash-backed {String(drilldown.safe_preview_policy.hash_backed)} · path-safe {String(drilldown.safe_preview_policy.path_safe)}</small>
        </div>
        {intentRows.length === 0 ? (
          <p>아직 기록된 연구 의도가 없습니다. recorded-only jobs · idempotent false · config_hash 없음 · audit_status 대기 · active count zero. 이 화면은 실행·학습·주문을 시작하지 않습니다.</p>
        ) : (
          intentRows.slice(0, 5).map((job) => (
            <article key={String(job.job_id ?? job.idempotency_key ?? job.config_hash)}>
              <span>{String(job.status ?? 'RECORDED_RESEARCH_INTENT')}</span>
              <strong>{String(job.workflow ?? 'record_research_intent')}</strong>
              <p>symbols {Array.isArray(job.symbols) ? job.symbols.join(', ') : '—'} · audit {String(job.audit_status ?? 'AUDIT_NOT_RECORDED')}</p>
              <small>idempotent {String(job.idempotent ?? false)} · config_hash {String(job.config_hash ?? '없음')} · job {String(job.job_id ?? '없음')}</small>
            </article>
          ))
        )}
      </div>
      <div className="audit-log">
        {audit.events.map((entry, index) => (
          <article key={`${entry.event}-${index}`}>
            <span>{statusLabel(entry.status ?? 'AUDITED')}</span>
            <strong>{entry.event}</strong>
            <p>{entry.details ?? entry.workflow ?? entry.job_id ?? '백엔드 감사 이벤트'}</p>
            <small>{entry.workflow ?? entry.job_id ?? audit.run_id} · {primaryAuditArtifact.source_stage} · hash {primaryAuditArtifact.hash ?? '없음'}</small>
          </article>
        ))}
      </div>
      <p className="danger-note" role="status" aria-live="polite">{jobMessage} 이 UI는 실거래/브로커/주문/모델/수익 경로를 열지 않습니다.</p>
    </article>
  );
}

export const FALLBACK_QUEUE_SUMMARY = FALLBACK_STATUS.queue_summary;
