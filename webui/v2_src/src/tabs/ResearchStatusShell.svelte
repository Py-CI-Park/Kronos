<script lang="ts">
  interface StatusMetric {
    label: string;
    value: string;
    tone?: 'pass' | 'warn' | 'danger' | 'neutral';
  }

  export let pageId = 'research';
  export let eyebrow = 'Research Command Center';
  export let title = 'Research-only status';
  export let verdict = 'RESEARCH_ONLY';
  export let summary = '';
  export let locks: readonly StatusMetric[] = [];
  export let blockers: readonly string[] = [];
  export let nextActions: readonly string[] = [];
</script>

<section class="research-status-shell" data-research-status-shell data-research-status-page={pageId} aria-label={`${title} status shell`}>
  <div class="status-main">
    <div class="row" style="gap:10px; flex-wrap:wrap">
      <span class="text-eyebrow">{eyebrow}</span>
      <span class="pill warn" data-research-only-lock><span class="dot"></span>RESEARCH_ONLY · READ_ONLY</span>
      <span class="pill danger" data-no-live-profit-lock><span class="dot"></span>NO LIVE · NO BROKER · NO PROFIT CLAIM</span>
    </div>
    <h2>{title}</h2>
    <p>{summary}</p>
    <div class="verdict" data-status-verdict>{verdict}</div>
  </div>

  <div class="status-grid" data-research-lock-grid>
    {#each locks as item}
      <div class="status-tile" data-tone={item.tone ?? 'neutral'}>
        <span>{item.label}</span>
        <strong>{item.value}</strong>
      </div>
    {/each}
  </div>

  <div class="status-columns">
    <div class="status-column" data-current-blockers>
      <div class="text-eyebrow">현재 blocker</div>
      {#if blockers.length}
        <ul>
          {#each blockers as blocker}
            <li>{blocker}</li>
          {/each}
        </ul>
      {:else}
        <p class="text-muted">등록된 blocker가 없습니다. 그래도 live/model/paper/profit 잠금은 유지됩니다.</p>
      {/if}
    </div>
    <div class="status-column" data-next-inspection>
      <div class="text-eyebrow">다음 확인</div>
      <ol>
        {#each nextActions as action}
          <li>{action}</li>
        {/each}
      </ol>
    </div>
  </div>
</section>

<style>
  .research-status-shell {
    border: 1px solid rgba(20, 184, 166, 0.26);
    border-radius: 24px;
    background:
      linear-gradient(135deg, rgba(20, 184, 166, 0.12), rgba(59, 130, 246, 0.08)),
      var(--card);
    padding: 20px;
    box-shadow: var(--shadow-card);
    display: grid;
    gap: 16px;
  }
  .status-main h2 {
    margin: 10px 0 6px;
    font-size: clamp(22px, 3vw, 34px);
    letter-spacing: -0.04em;
  }
  .status-main p {
    margin: 0;
    color: var(--text-muted);
    max-width: 860px;
    line-height: 1.65;
  }
  .verdict {
    margin-top: 14px;
    display: inline-flex;
    border-radius: 999px;
    padding: 8px 12px;
    background: rgba(245, 158, 11, 0.14);
    color: #92400e;
    font-weight: 800;
    font-size: 12px;
    letter-spacing: 0.04em;
  }
  .status-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 10px;
  }
  .status-tile {
    border: 1px solid var(--border);
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.72);
    padding: 12px;
  }
  .status-tile span {
    display: block;
    color: var(--text-muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .status-tile strong {
    display: block;
    margin-top: 6px;
    font-size: 15px;
  }
  .status-tile[data-tone='pass'] strong { color: #047857; }
  .status-tile[data-tone='warn'] strong { color: #b45309; }
  .status-tile[data-tone='danger'] strong { color: #b91c1c; }
  .status-columns {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 14px;
  }
  .status-column {
    border: 1px solid var(--border);
    border-radius: 18px;
    background: rgba(248, 250, 252, 0.78);
    padding: 14px;
  }
  .status-column ul,
  .status-column ol {
    margin: 8px 0 0;
    padding-left: 18px;
    color: var(--text);
    line-height: 1.6;
  }
  @media (max-width: 760px) {
    .status-columns {
      grid-template-columns: 1fr;
    }
  }
</style>
