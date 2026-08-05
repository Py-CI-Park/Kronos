<script lang="ts">
  export interface StateItem {
    readonly label: string;
    readonly state: string;
    readonly detail: string;
    readonly tone: 'ok' | 'warning' | 'danger' | 'neutral';
  }

  interface Props {
    readonly items: readonly StateItem[];
  }

  let { items }: Props = $props();
</script>

<div class="states" data-state-matrix>
  {#each items as item}<article data-tone={item.tone}><span>{item.label}</span><strong>{item.state}</strong><p>{item.detail}</p></article>{/each}
</div>

<style>
  .states{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr));gap:10px;min-width:0}.states article{min-width:0;border:1px solid var(--border);border-left:4px solid var(--border-strong);border-radius:9px;padding:12px;background:var(--surface-sunken)}.states article[data-tone=ok]{border-left-color:var(--success)}.states article[data-tone=warning]{border-left-color:var(--warn)}.states article[data-tone=danger]{border-left-color:var(--danger)}span{display:block;color:var(--muted);font:800 .58rem var(--font-mono);letter-spacing:.06em}strong{display:block;margin:6px 0;color:var(--fg-strong);font:.78rem var(--font-mono);overflow-wrap:anywhere}p{margin:0;color:var(--muted);font-size:.67rem;line-height:1.5}
</style>
