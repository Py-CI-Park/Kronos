<script lang="ts">
  import type { EvidenceIdentity, RunEvidence } from '../evidence';

  interface Props {
    identity: EvidenceIdentity;
    run?: RunEvidence | null;
    eyebrow?: string;
    title?: string;
    description?: string;
  }

  let { identity, run = null, eyebrow = 'Evidence identity', title = 'Typed evidence', description }: Props = $props();

  const identityAge = $derived(identity.artifact_age_seconds === null ? 'AGE_UNKNOWN' : String(identity.artifact_age_seconds));
  const runCostText = $derived(run?.cost_bps !== null && run?.cost_bps !== undefined ? `${run.cost_bps} bps declared` : null);
</script>

<header class="evidence-header" data-v4-evidence-header>
  <div class="copy">
    <p class="eyebrow">{eyebrow}</p>
    <h2>{title}</h2>
    {#if description}
      <p class="description">{description}</p>
    {/if}
  </div>

  <dl class="identity-grid" aria-label="Evidence identity details">
    <div>
      <dt>ID</dt>
      <dd>{identity.id}</dd>
    </div>
    <div>
      <dt>Kind</dt>
      <dd>{identity.kind}</dd>
    </div>
    <div>
      <dt>Label</dt>
      <dd>{identity.label}</dd>
    </div>
    <div>
      <dt>Source endpoint</dt>
      <dd>{identity.source_endpoint}</dd>
    </div>
    <div>
      <dt>Source path</dt>
      <dd>{identity.source_path}</dd>
    </div>
    <div>
      <dt>SHA-256</dt>
      <dd>{identity.sha256}</dd>
    </div>
    <div>
      <dt>Modified at</dt>
      <dd>{identity.modified_at}</dd>
    </div>
    <div>
      <dt>Artifact age seconds</dt>
      <dd>{identityAge}</dd>
    </div>
    <div>
      <dt>Freshness</dt>
      <dd>{identity.freshness_status}</dd>
    </div>
  </dl>

  {#if run}
    <section class="run-card" aria-label="Run evidence details">
      <dl class="run-grid">
        <div>
          <dt>Run ID</dt>
          <dd>{run.run_id}</dd>
        </div>
        <div>
          <dt>Artifact type</dt>
          <dd>{run.artifact_type}</dd>
        </div>
        <div>
          <dt>Line</dt>
          <dd>{run.line}</dd>
        </div>
        <div>
          <dt>Is reinforcement learning</dt>
          <dd>{run.is_reinforcement_learning ? 'true' : 'false'}</dd>
        </div>
        <div>
          <dt>Strategy</dt>
          <dd>{run.strategy_label}</dd>
        </div>
        <div>
          <dt>Baseline</dt>
          <dd>{run.baseline_label}</dd>
        </div>
        <div>
          <dt>Cost</dt>
          <dd>{runCostText ?? 'MISSING'}</dd>
        </div>
        <div>
          <dt>Seed</dt>
          <dd>{run.seed}</dd>
        </div>
        <div>
          <dt>Split</dt>
          <dd>{run.split}</dd>
        </div>
        <div>
          <dt>Split hash</dt>
          <dd>{run.split_hash}</dd>
        </div>
        <div>
          <dt>Prereg doc</dt>
          <dd>{run.prereg_doc}</dd>
        </div>
        <div>
          <dt>Lifecycle</dt>
          <dd>{run.lifecycle}</dd>
        </div>
        <div>
          <dt>Verdict</dt>
          <dd>{run.verdict}</dd>
        </div>
      </dl>
      <div class="blockers">
        <span>Blocking reasons</span>
        {#if run.blocking_reasons.length > 0}
          <ul>
            {#each run.blocking_reasons as blocker}
              <li>{blocker}</li>
            {/each}
          </ul>
        {:else}
          <p>NOT_RECORDED</p>
        {/if}
      </div>
    </section>
  {/if}
</header>

<style>
  .evidence-header {
    container-type: inline-size;
    display: grid;
    gap: 18px;
    padding: 20px;
    border: 1px solid var(--border-faint);
    border-radius: 22px;
    background: color-mix(in oklab, var(--surface) 92%, transparent);
    box-shadow: var(--shadow-sm);
    color: var(--fg);
    font-family: var(--font-body);
    overflow-wrap: anywhere;
    word-break: auto-phrase;
  }

  .copy {
    max-width: 72ch;
  }

  .eyebrow {
    margin: 0 0 6px;
    color: var(--accent-strong);
    font: 750 11px/1.2 var(--font-mono);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  h2 {
    margin: 0;
    color: var(--fg-strong);
    font: 760 clamp(22px, 4cqi, 34px) / 1.05 var(--font-display);
    letter-spacing: -0.04em;
    text-wrap: balance;
  }

  .description {
    margin: 8px 0 0;
    color: var(--muted);
    line-height: 1.55;
  }

  .identity-grid,
  .run-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr));
    gap: 10px;
    margin: 0;
    padding: 0;
  }

  .identity-grid div,
  .run-grid div,
  .run-card {
    min-width: 0;
    padding: 12px;
    border: 1px solid var(--border-faint);
    border-radius: 16px;
    background: color-mix(in oklab, var(--surface-raised) 72%, transparent);
  }

  dt,
  .blockers span {
    color: var(--muted);
    font: 700 10px/1.2 var(--font-mono);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  dd {
    margin: 5px 0 0;
    color: var(--fg-strong);
    font: 650 12px/1.35 var(--font-mono);
  }

  .run-card {
    display: grid;
    gap: 10px;
  }

  .run-card p {
    margin: 0;
    color: var(--fg-strong);
    font: 650 13px/1.45 var(--font-mono);
  }


  .blockers ul {
    margin: 7px 0 0;
    padding-inline-start: 18px;
    color: var(--muted);
    line-height: 1.45;
  }

  @media (prefers-reduced-motion: reduce) {
    .evidence-header,
    .evidence-header * {
      scroll-behavior: auto;
    }
  }
</style>
