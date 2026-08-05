<script lang="ts">
  import { PROGRAM_EXECUTION } from '../../scorecard/programExecution';
</script>

<section class="rail" data-system-status-rail aria-label="시스템 연구 상태">
  <div class="score"><span>PROGRAM</span><strong>{PROGRAM_EXECUTION.overallScore}</strong><small>/100</small></div>
  <div class="status"><span class="blocked">NO-GO</span><span>READ-ONLY</span><span>FRESH OOS SEALED</span></div>
  <dl>
    <div><dt>제품 구현·UX</dt><dd>{PROGRAM_EXECUTION.implementationScore}/100</dd></div>
    <div><dt>경제 모델</dt><dd>{PROGRAM_EXECUTION.economicModelScore}/100 · 미생성</dd></div>
    <div><dt>개발선</dt><dd>{PROGRAM_EXECUTION.developmentVersion}</dd></div>
  </dl>
  <details>
    <summary>판정·다음 행동</summary>
    <div><b>{PROGRAM_EXECUTION.stage}</b><p>{PROGRAM_EXECUTION.nextAction}</p><small>NO LIVE · NO PROFIT CLAIM · 근거가 없는 상태는 MISSING으로 표시합니다.</small></div>
  </details>
</section>

<style>
  .rail{min-width:0;display:grid;grid-template-columns:auto auto minmax(300px,1fr) auto;gap:14px;align-items:center;border:1px solid var(--border-strong);border-left:4px solid var(--accent);border-radius:12px;padding:10px 12px;background:color-mix(in srgb,var(--surface-raised) 92%,transparent);box-shadow:var(--shadow-sm)}
  .score{display:grid;grid-template-columns:auto auto;align-items:end}.score span{grid-column:1/-1;color:var(--dim);font:800 .55rem var(--font-mono);letter-spacing:.1em}.score strong{color:var(--fg-strong);font:800 1.65rem/.9 var(--font-mono)}.score small{color:var(--muted);font:700 .62rem var(--font-mono)}
  .status{display:flex;flex-wrap:wrap;gap:5px}.status span{border:1px solid var(--border-strong);border-radius:999px;padding:3px 7px;color:var(--muted);font:800 .56rem var(--font-mono)}.status .blocked{border-color:var(--danger);color:var(--danger)}
  dl{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:0}dl div{min-width:0;border-left:1px solid var(--border);padding-left:9px}dt{color:var(--dim);font:700 .56rem var(--font-mono)}dd{margin:2px 0 0;color:var(--fg-strong);font-size:.68rem;overflow-wrap:anywhere}
  details{position:relative}summary{cursor:pointer;border:1px solid var(--border-strong);border-radius:8px;padding:6px 8px;color:var(--fg);font-size:.66rem;font-weight:800;list-style:none}summary:focus-visible{outline:2px solid var(--warn);outline-offset:2px}details>div{position:absolute;z-index:20;right:0;top:calc(100% + 8px);width:min(430px,80vw);border:1px solid var(--border-strong);border-radius:12px;padding:14px;background:var(--surface-raised);box-shadow:var(--shadow-lg)}details b{display:block;color:var(--warn);font:.7rem var(--font-mono);overflow-wrap:anywhere}details p{margin:8px 0;color:var(--fg);font-size:.75rem}details small{color:var(--muted);font-size:.66rem}
  @media(max-width:1100px){.rail{grid-template-columns:auto minmax(0,1fr) auto}.rail dl{grid-column:1/-1;grid-row:2}.status{align-self:center}}
  @media(max-width:680px){.rail{grid-template-columns:auto minmax(0,1fr)}details{grid-column:1/-1}.rail dl{grid-template-columns:1fr}.status span:nth-child(n+3){display:none}details>div{left:0;right:auto;width:min(330px,calc(100vw - 92px))}}
</style>
