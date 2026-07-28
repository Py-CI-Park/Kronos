<script lang="ts">
  import { PROGRAM_EXECUTION } from './scorecard/programExecution';
</script>

<aside class="execution" aria-label="프로그램 실행 상태">
  <div class="score"><span>RESEARCH PROGRAM COMPLETENESS</span><strong>{PROGRAM_EXECUTION.overallScore}</strong><small>/100</small></div>
  <dl>
    <div><dt>검토 스냅샷</dt><dd>{PROGRAM_EXECUTION.stage}</dd></div>
    <div><dt>전달 흐름</dt><dd>{PROGRAM_EXECUTION.deliveryLane}</dd></div>
    <div><dt>다음 실행</dt><dd>{PROGRAM_EXECUTION.nextAction}</dd></div>
    <div><dt>예상 시간</dt><dd>{PROGRAM_EXECUTION.eta}</dd></div>
  </dl>
  <div class="guards"><span>{PROGRAM_EXECUTION.authority}</span><span>RUN: {PROGRAM_EXECUTION.reviewedRun}</span><span>{PROGRAM_EXECUTION.pageCount} PAGES</span><span>NOT LIVE ARTIFACT STATE</span><span>NOT MODEL PERFORMANCE</span><span>FRESH OOS: SEALED</span><span>LIVE: BLOCKED</span></div>
</aside>

<style>
  .execution{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:16px;align-items:center;border:1px solid var(--border-strong);border-left:4px solid var(--accent);padding:10px 14px;background:var(--surface-raised);min-width:0}.score{display:grid;grid-template-columns:auto auto;align-items:end}.score span{grid-column:1/-1;color:var(--muted);font:800 .62rem ui-monospace,monospace;letter-spacing:.1em}.score strong{color:var(--fg-strong);font:800 2rem/.9 ui-monospace,monospace}.score small{color:var(--muted);font:700 .7rem ui-monospace,monospace}dl{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:0;min-width:0}dl div{min-width:0;border-left:1px solid var(--border);padding-left:10px}dt{color:var(--dim);font:800 .62rem ui-monospace,monospace}dd{margin:3px 0 0;color:var(--fg);font-size:.72rem;overflow-wrap:anywhere}.guards{display:flex;flex-direction:column;align-items:flex-end;gap:3px}.guards span{color:var(--warn);font:800 .6rem ui-monospace,monospace}@media(max-width:1100px){.execution{grid-template-columns:auto minmax(0,1fr)}.guards{grid-column:1/-1;flex-direction:row;align-items:center;flex-wrap:wrap}}@media(max-width:720px){.execution{grid-template-columns:1fr}.score{width:max-content}dl{grid-template-columns:1fr 1fr}.guards{grid-column:auto}}@media(max-width:430px){dl{grid-template-columns:1fr}}
</style>
