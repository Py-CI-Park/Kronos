<script lang="ts">
  interface Props {
    readonly eyebrow: string;
    readonly title: string;
    readonly description: string;
    readonly status?: string;
  }

  let { eyebrow, title, description, status }: Props = $props();
</script>

<header class="page-header" data-page-header>
  <div><p>{eyebrow}</p><h1>{title}</h1><span>{description}</span></div>
  {#if status}<strong>{status}</strong>{/if}
</header>

<style>
  .page-header{display:flex;align-items:end;justify-content:space-between;gap:20px;min-width:0;padding:4px 2px}.page-header div{min-width:0}.page-header p{margin:0;color:var(--accent);font:900 .66rem var(--font-mono);letter-spacing:.12em}.page-header h1{margin:6px 0 4px;color:var(--fg-strong);font-size:clamp(1.7rem,3vw,2.55rem);line-height:1.05;letter-spacing:-.035em}.page-header span{color:var(--muted);font-size:.84rem}.page-header strong{flex:0 0 auto;border:1px solid var(--border-strong);border-radius:999px;padding:6px 9px;color:var(--warn);font:800 .65rem var(--font-mono)}
  @media(max-width:620px){.page-header{align-items:start;flex-direction:column;gap:10px}.page-header h1{font-size:1.65rem}}
</style>
