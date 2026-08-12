<script lang="ts">
  import { V6_BRAND, V6_NAV_GROUPS, V6_PAGES } from '../../registry';

  interface Props {
    readonly activePageId: string;
    readonly onSelect: (id: string) => void;
  }

  let { activePageId, onSelect }: Props = $props();
</script>

<aside class="sidebar" data-unified-sidebar aria-label="Kronos 연구 탐색">
  <header class="brand">
    <span class="signal" aria-hidden="true"></span>
    <div><p>{V6_BRAND.subtitle}</p><h1>{V6_BRAND.name}</h1><small>{V6_BRAND.version} · {V6_BRAND.updateDate}</small></div>
  </header>
  <nav>
    {#each V6_NAV_GROUPS as group}
      <section aria-label={group}>
        <h2>{group}</h2>
        {#each V6_PAGES.filter((item) => item.group === group) as item}
          <button type="button" class:active={activePageId === item.id} aria-current={activePageId === item.id ? 'page' : undefined} aria-label={`${item.labelKo} (${item.label})`} onclick={() => onSelect(item.id)}>
            <span class="monogram" aria-hidden="true">{item.step ?? item.label.slice(0, 1)}</span>
            <span class="label"><strong>{item.labelKo}</strong><small>{item.label}</small></span>
          </button>
        {/each}
      </section>
    {/each}
  </nav>
  <footer><span></span>READ-ONLY RESEARCH</footer>
</aside>

<style>
  .sidebar{position:sticky;top:0;height:100vh;min-width:0;display:flex;flex-direction:column;border-right:1px solid var(--border);padding:18px 12px;background:color-mix(in srgb,var(--surface-raised) 94%,transparent);backdrop-filter:blur(18px)}
  .brand{display:flex;gap:10px;align-items:flex-start;padding:4px 8px 18px;border-bottom:1px solid var(--border)}
  .signal{flex:0 0 4px;height:48px;border-radius:999px;background:linear-gradient(var(--accent),var(--success));box-shadow:0 0 18px color-mix(in srgb,var(--accent) 38%,transparent)}
  .brand div{min-width:0}.brand p,.brand h1,.brand small{overflow-wrap:anywhere}.brand p{margin:0;color:var(--accent);font-size:.58rem;font-weight:900;letter-spacing:.11em;text-transform:uppercase}.brand h1{margin:5px 0;color:var(--fg-strong);font-size:1.02rem;line-height:1.18}.brand small{color:var(--muted);font:.64rem var(--font-mono)}
  nav{margin-top:12px;overflow-y:auto;overflow-x:clip;scrollbar-width:thin}section+section{margin-top:12px}h2{margin:0 9px 4px;color:var(--dim);font:.58rem var(--font-mono);letter-spacing:.12em}
  button{width:100%;min-width:0;min-height:44px;display:flex;align-items:center;gap:9px;margin:2px 0;padding:8px;border:1px solid transparent;border-radius:10px;background:transparent;color:var(--muted);font:inherit;text-align:left;cursor:pointer;touch-action:manipulation;transition:transform 160ms ease,border-color 160ms ease,background 160ms ease}
  button:hover{transform:translateX(2px);border-color:var(--border-strong);background:var(--surface-overlay)}button.active{border-color:var(--accent);background:var(--accent-soft);color:var(--fg-strong);box-shadow:inset 3px 0 var(--accent)}button:focus-visible{outline:2px solid var(--warn);outline-offset:2px}
  .monogram{flex:0 0 26px;height:26px;display:grid;place-items:center;border:1px solid var(--border-strong);border-radius:8px;color:var(--accent-strong);font:800 .68rem var(--font-mono)}
  .label{min-width:0;max-width:100%;display:flex;flex-direction:column;gap:1px}.label strong,.label small{display:block;max-width:100%;overflow-wrap:anywhere}.label strong{font-size:.8rem}.label small{color:var(--muted);font:.59rem var(--font-mono)}
  footer{margin-top:auto;padding:12px 8px 0;display:flex;align-items:center;gap:7px;color:var(--dim);font:700 .55rem var(--font-mono);letter-spacing:.08em}footer span{width:7px;height:7px;border-radius:50%;background:var(--warn);box-shadow:0 0 8px var(--warn)}
  @media(max-width:920px){.sidebar[data-unified-sidebar]{width:auto;transform:none}.sidebar{padding:12px 8px}.brand{justify-content:center;padding:4px 0 14px}.brand div,.label,h2,footer{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}.signal{height:32px}.sidebar button{justify-content:center;padding:8px 3px}.monogram{flex-basis:28px}}
  @media(max-width:680px){.sidebar[data-unified-sidebar]{width:auto;transform:none}.sidebar{position:fixed;z-index:50;inset:auto 0 0;height:auto;padding:6px 8px calc(6px + env(safe-area-inset-bottom));border:1px solid var(--border-strong);border-width:1px 0 0;background:color-mix(in srgb,var(--surface-raised) 97%,transparent);box-shadow:0 -10px 28px color-mix(in srgb,var(--bg) 38%,transparent)}.brand,footer{display:none}.sidebar nav{display:flex;gap:4px;margin:0;overflow-x:auto;overflow-y:hidden;scrollbar-width:thin}.sidebar section{display:contents}.sidebar button{flex:0 0 78px;min-height:58px;justify-content:center;flex-direction:column;gap:3px;margin:0;padding:5px 4px;text-align:center}.sidebar .label{position:static;width:auto;height:auto;overflow:visible;clip-path:none;white-space:normal;display:block}.label strong{display:block;font-size:.62rem;line-height:1.2}.label small{display:none}.monogram{flex:0 0 24px;width:24px;height:24px}.sidebar button.active{box-shadow:inset 0 3px var(--accent)}}
  @media(prefers-reduced-motion:reduce){button{transition:none}button:hover{transform:none}}
</style>
