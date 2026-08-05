<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    readonly eyebrow?: string;
    readonly title: string;
    readonly description?: string;
    readonly actions?: Snippet;
    readonly children?: Snippet;
  }

  let { eyebrow, title, description, actions, children }: Props = $props();
</script>

<section class="panel" data-research-panel>
  <header>
    <div>{#if eyebrow}<p>{eyebrow}</p>{/if}<h2>{title}</h2>{#if description}<span>{description}</span>{/if}</div>
    {#if actions}<aside>{@render actions()}</aside>{/if}
  </header>
  <div class="body">{@render children?.()}</div>
</section>

<style>
  .panel{min-width:0;border:1px solid var(--border);border-radius:14px;background:var(--surface-raised);box-shadow:var(--shadow-sm);overflow:hidden}.panel>header{display:flex;align-items:end;justify-content:space-between;gap:16px;padding:16px 18px;border-bottom:1px solid var(--border)}.panel header div{min-width:0}.panel p{margin:0 0 5px;color:var(--accent);font:900 .58rem var(--font-mono);letter-spacing:.1em}.panel h2{margin:0;color:var(--fg-strong);font-size:1.05rem}.panel header span{display:block;margin-top:4px;color:var(--muted);font-size:.72rem}.panel aside{flex:0 0 auto}.body{min-width:0;padding:18px}
  @media(max-width:620px){.panel>header{align-items:start;flex-direction:column}.panel aside{width:100%}.body{padding:14px}}
</style>
