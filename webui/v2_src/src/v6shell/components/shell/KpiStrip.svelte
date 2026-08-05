<script lang="ts">
  export interface KpiItem {
    readonly label: string;
    readonly value: string;
    readonly detail: string;
    readonly tone?: 'neutral' | 'positive' | 'warning' | 'danger';
  }

  interface Props {
    readonly items: readonly KpiItem[];
  }

  let { items }: Props = $props();
</script>

<section class="kpis" data-kpi-strip aria-label="핵심 지표">
  {#each items as item}
    <article data-tone={item.tone ?? 'neutral'}><span>{item.label}</span><strong>{item.value}</strong><small>{item.detail}</small></article>
  {/each}
</section>

<style>
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,170px),1fr));gap:10px;min-width:0}.kpis article{min-width:0;border:1px solid var(--border);border-top:3px solid var(--border-strong);border-radius:10px;padding:12px;background:var(--surface-raised)}.kpis article[data-tone=positive]{border-top-color:var(--success)}.kpis article[data-tone=warning]{border-top-color:var(--warn)}.kpis article[data-tone=danger]{border-top-color:var(--danger)}span,small{display:block;color:var(--muted)}span{font:800 .6rem var(--font-mono);letter-spacing:.06em}strong{display:block;margin:7px 0 4px;color:var(--fg-strong);font:800 clamp(1.15rem,2vw,1.7rem) var(--font-mono);overflow-wrap:anywhere}small{font-size:.67rem;line-height:1.45}
</style>
