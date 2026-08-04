<script lang="ts">
  import { programPageById } from './scorecard/programPages';

  let { pageId }: { readonly pageId: string } = $props();
  const page = $derived(programPageById(pageId));
  const tone = $derived(page?.evidenceState.includes('BLOCKED') || page?.evidenceState.includes('NO_GO') || page?.evidenceState.includes('NOT_CREATED') ? 'blocked' : 'active');
</script>

{#if page}
  <section class={`decision-rail ${tone}`} aria-label={`${page.page} 목적과 다음 행동`}>
    <header><span>{page.group} · {page.priority}</span><strong>{page.page}</strong><em>{page.progress}% 화면 완료</em></header>
    <dl>
      <div><dt>목적</dt><dd>{page.purpose}</dd></div>
      <div><dt>현재 증거</dt><dd><code>{page.evidenceState}</code></dd></div>
      <div class="next"><dt>다음 행동</dt><dd>{page.nextAction}</dd></div>
      <div><dt>완료 기준 · 예상</dt><dd>{page.mergeGate}<small>{page.eta}</small></dd></div>
    </dl>
  </section>
{/if}

<style>
  .decision-rail{min-width:0;border:1px solid var(--border-strong);border-left:4px solid var(--accent);background:var(--surface-raised);color:var(--fg)}.decision-rail.blocked{border-left-color:var(--warn)}header{display:flex;align-items:center;gap:10px;border-bottom:1px solid var(--border);padding:9px 12px}header span,header em{color:var(--muted);font:700 .64rem ui-monospace,monospace;letter-spacing:.05em}header strong{color:var(--fg-strong);font-size:.85rem}header em{margin-left:auto;font-style:normal}dl{display:grid;grid-template-columns:1fr 1.15fr 1.35fr 1.2fr;margin:0}dl>div{min-width:0;border-right:1px solid var(--border);padding:10px 12px}dl>div:last-child{border-right:0}dt{color:var(--muted);font-size:.66rem}dd{margin:4px 0 0;color:var(--fg);font-size:.76rem;line-height:1.45;overflow-wrap:anywhere}.next dd{color:var(--accent-strong);font-weight:750}code{color:var(--warn);font-size:.68rem;white-space:normal}small{display:block;margin-top:3px;color:var(--muted)}@media(max-width:900px){dl{grid-template-columns:1fr 1fr}dl>div:nth-child(2){border-right:0}dl>div:nth-child(-n+2){border-bottom:1px solid var(--border)}}@media(max-width:520px){header{align-items:flex-start;flex-wrap:wrap}header em{width:100%;margin:0}dl{grid-template-columns:1fr}dl>div,dl>div:nth-child(2){border-right:0;border-bottom:1px solid var(--border)}dl>div:last-child{border-bottom:0}}
</style>

