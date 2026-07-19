<script lang="ts">
  import type { Snippet } from 'svelte';
  import EvidenceDisclosure from '../components/EvidenceDisclosure.svelte';
  import PromotionLocksGrid from '../components/PromotionLocksGrid.svelte';
  import { deriveAdminWorkspaceModel } from './adminEvidence';

  interface Props {
    surface: 'settings' | 'docs';
    trackingSource?: unknown;
    children?: Snippet;
  }

  let { surface, trackingSource = undefined, children }: Props = $props();

  const model = $derived(deriveAdminWorkspaceModel(surface, trackingSource));

  const surfaceCopy = $derived(
    surface === 'docs'
      ? {
          eyebrow: 'Docs · reference only',
          title: '문서 표면은 정적 참고용이며 어떤 것도 실행하지 않습니다',
          description: '이 화면은 텍스트만 렌더링하고, 외부 URL을 가져오지 않으며, 환경 변수를 읽지 않습니다.',
        }
      : {
          eyebrow: 'Settings · reference only',
          title: '설정 표면은 서버 시작/중지, 환경 설정, 승격을 수행할 수 없습니다',
          description: '표시되는 모든 상태는 호출자가 넘긴 안전한 로컬 메타데이터에서만 파생됩니다.',
        }
  );
</script>

<section class="admin-workspace" data-v4-admin-workspace data-surface={surface} aria-label="V4 admin workspace">
  <div class="workspace-intro">
    <p class="eyebrow">{surfaceCopy.eyebrow}</p>
    <h2>{surfaceCopy.title}</h2>
    <p>{surfaceCopy.description}</p>
  </div>

  <section class="locks" data-v4-admin-locks aria-label="Admin surface promotion locks">
    <PromotionLocksGrid result={model.locks} compact />
  </section>

  <section class="posture" data-v4-admin-posture aria-label="Read-only and no-egress posture">
    <div class="section-head">
      <p class="eyebrow">Posture</p>
      <h3>읽기 전용 · 외부 통신 없음 · 서버 제어 불가</h3>
    </div>
    <dl>
      <div><dt>Read only</dt><dd data-posture-key="readOnly">{model.posture.readOnly ? 'true' : 'false'}</dd></div>
      <div><dt>No egress</dt><dd data-posture-key="noEgress">{model.posture.noEgress ? 'true' : 'false'}</dd></div>
      <div><dt>No server control</dt><dd data-posture-key="noServerControl">{model.posture.noServerControl ? 'true' : 'false'}</dd></div>
      <div><dt>No mutation</dt><dd data-posture-key="noMutation">{model.posture.noMutation ? 'true' : 'false'}</dd></div>
    </dl>
  </section>

  <section
    class="tracking"
    data-v4-admin-tracking
    data-tracking-backend={model.tracking.backend}
    data-tracking-enabled={model.tracking.enabled ? 'true' : 'false'}
    data-tracking-status={model.tracking.detectionStatus}
    aria-label="Independent local tracking state"
  >
    <div class="section-head">
      <p class="eyebrow">Local tracking (MLflow) · independent state</p>
      <h3>기본값은 비활성이며, 안전한 로컬 file: URI 검출 시에만 읽기 전용으로 표시됩니다</h3>
    </div>
    <dl>
      <div><dt>Backend</dt><dd>{model.tracking.backend}</dd></div>
      <div><dt>Enabled</dt><dd>{model.tracking.enabled ? 'true' : 'false'}</dd></div>
      <div><dt>Posture</dt><dd>{model.tracking.posture}</dd></div>
      <div><dt>Tracking URI</dt><dd>{model.tracking.sanitizedUri ?? 'NOT_DETECTED'}</dd></div>
      <div><dt>Label</dt><dd>{model.tracking.label.text}</dd></div>
    </dl>
    {#if model.tracking.rejectedCapabilities.length > 0}
      <p class="rejected-note" role="alert">
        거부된 declared capability: {model.tracking.rejectedCapabilities.join(' · ')}
      </p>
    {/if}
    <ul class="reasons">
      {#each model.tracking.reasons as reason}
        <li>{reason}</li>
      {/each}
    </ul>
  </section>

  <section class="docs-sanitization" data-v4-admin-docs-sanitization aria-label="Docs sanitization posture">
    <div class="section-head">
      <p class="eyebrow">Docs sanitization posture</p>
      <h3>정적 문서화 posture · live data 아님</h3>
    </div>
    <div class="facts-grid">
      {#each model.docsSanitization as fact (fact.key)}
        <article data-fact-key={fact.key}>
          <strong>{fact.label}</strong>
          <p>{fact.detail}</p>
        </article>
      {/each}
    </div>
  </section>

  <EvidenceDisclosure summary="Legacy child · reference only" meta="rendered last" lazy>
    <div data-v4-admin-legacy aria-label="Legacy child content, rendered last">
      {#if children}
        {@render children()}
      {:else}
        <p>LEGACY_CHILD_NOT_PROVIDED</p>
      {/if}
    </div>
  </EvidenceDisclosure>
</section>

<style>
  .admin-workspace {
    width: 100%;
    display: grid;
    gap: 14px;
    color: var(--fg);
  }

  .workspace-intro {
    border: 1px solid var(--border-faint);
    border-radius: var(--r-xl);
    background: var(--surface);
    box-shadow: var(--shadow-sm);
    padding: 18px;
  }

  .eyebrow {
    margin: 0 0 4px;
    color: var(--accent-strong);
    font: 750 var(--t-eyebrow) / 1.2 var(--font-mono);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  h2 {
    margin: 0 0 6px;
    color: var(--fg-strong);
    font: 760 var(--t-h5) / 1.2 var(--font-display);
    letter-spacing: -0.02em;
  }

  .workspace-intro p:last-child,
  .posture p,
  .tracking p {
    margin: 0;
    color: var(--muted);
    line-height: 1.5;
  }

  .locks,
  .posture,
  .tracking,
  .docs-sanitization {
    border: 1px solid var(--border-faint);
    border-radius: var(--r-xl);
    background: var(--surface);
    box-shadow: var(--shadow-sm);
    padding: 16px;
  }

  .section-head {
    margin-bottom: 10px;
  }

  h3 {
    margin: 0;
    color: var(--fg-strong);
    font: 720 12.5px/1.3 var(--font-display);
  }

  dl {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr));
    gap: 10px;
    margin: 0;
    padding: 0;
  }

  dl div {
    min-width: 0;
    padding: 10px;
    border: 1px solid var(--border-faint);
    border-radius: 14px;
    background: color-mix(in oklab, var(--surface-raised) 72%, transparent);
  }

  dt {
    color: var(--muted);
    font: 700 10px/1.2 var(--font-mono);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  dd {
    margin: 5px 0 0;
    color: var(--fg-strong);
    font: 650 12px/1.35 var(--font-mono);
    overflow-wrap: anywhere;
  }

  .rejected-note {
    margin: 10px 0 0;
    border: 1px solid var(--danger);
    border-radius: var(--r-md);
    padding: 9px 11px;
    background: var(--danger-soft);
    color: var(--danger);
    font-weight: 720;
  }

  .reasons {
    margin: 10px 0 0;
    padding-inline-start: 18px;
    color: var(--muted);
    font-size: var(--t-caption);
    line-height: 1.45;
  }

  .facts-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr));
    gap: 10px;
  }

  .facts-grid article {
    min-width: 0;
    padding: 12px;
    border: 1px solid var(--border-faint);
    border-radius: 14px;
    background: color-mix(in oklab, var(--surface-raised) 72%, transparent);
  }

  .facts-grid strong {
    display: block;
    margin-bottom: 4px;
    color: var(--fg-strong);
    font: 720 12px/1.3 var(--font-display);
  }

  .facts-grid p {
    margin: 0;
    color: var(--muted);
    font-size: var(--t-caption);
    line-height: 1.45;
  }
</style>
