<script lang="ts">
  import { PROGRAM_CAPABILITIES, PROGRAM_LANES, PROGRAM_PAGE_MATRIX, programOverallScore } from '../scorecard/programScorecard';
  import { PROGRAM_EXECUTION } from '../scorecard/programExecution';
  import DailyCloseResearchStatus from '../DailyCloseResearchStatus.svelte';
  import PageDecisionRail from '../PageDecisionRail.svelte';
  import { V6_PAGES } from '../registry';
  const overall = programOverallScore(PROGRAM_LANES);
  const officialPageCount = V6_PAGES.length;
  const capabilityCount = PROGRAM_PAGE_MATRIX.length;
  const capabilityLabel = (id: string, label: string) => id === 'all-page-control-room' ? `${capabilityCount}개 기능·워크플로 항목 결정 레일` : label;
  const stateClass = (state: string) => state === 'STRONG' || state === 'AVAILABLE' ? 'good' : state === 'BLOCKED' ? 'blocked' : 'partial';
</script>

<section class="scorecard" aria-labelledby="program-score-title">
  <PageDecisionRail pageId="scorecard" />
  <DailyCloseResearchStatus />
  <aside class="snapshot-note"><strong>REVIEWED SNAPSHOT</strong><span>{PROGRAM_EXECUTION.reviewedRun} · {PROGRAM_EXECUTION.reviewedEvidenceManifest}</span></aside>
  <header class="masthead">
    <div><p class="eyebrow">PROGRAM CONTROL // AUDITED 2026-08-04</p><h1 id="program-score-title">Kronos 프로그램 점수표</h1><p>화면 구현, 연구 증거, 실제 경제 모델, 운영 준비도를 분리해 평가합니다.</p></div>
    <div class="score-cluster"><div><span>PROGRAM</span><strong>{overall}</strong><small>/100</small></div><div><span>IMPLEMENTATION</span><strong>{PROGRAM_EXECUTION.implementationScore}</strong><small>/100</small></div><div class="danger"><span>ECONOMIC MODEL</span><strong>{PROGRAM_EXECUTION.economicModelScore}</strong><small>/100</small></div></div>
  </header>

  <section class="score-grid" aria-label="영역별 점수">
    {#each PROGRAM_LANES as lane}
      <article><div class="score-head"><span>{lane.labelKo}</span><strong>{lane.score}</strong></div><div class="track"><i style:width={`${lane.score}%`}></i></div><p>{lane.evidence}</p><footer><span class={stateClass(lane.state)}>{lane.state}</span><small>가중치 {lane.weight}% · 다음: {lane.nextAction}</small></footer></article>
    {/each}
  </section>

  <section class="panel" aria-labelledby="page-matrix-title">
    <header><div><p class="eyebrow">CAPABILITY DELIVERY TABLE</p><h2 id="page-matrix-title">{capabilityCount}개 기능·워크플로 단계 진행·증거·남은 행동</h2></div><span>공식 탐색은 <code>V6_PAGES</code>에 정의된 {officialPageCount}개 registry 페이지입니다. 아래 항목은 별도 페이지가 아닌 기능 또는 워크플로 단계입니다.</span></header>
    <div class="table-wrap"><table><thead><tr><th>우선</th><th>기능·단계</th><th>목적</th><th>진행</th><th>현재 증거</th><th>다음 행동</th><th>예상 시간</th><th>병합 조건</th></tr></thead><tbody>
      {#each PROGRAM_PAGE_MATRIX as row}
        <tr><td><span class="priority">{row.priority}</span></td><td><small>{row.group}</small><strong>{row.page}</strong></td><td>{row.purpose}</td><td><div class="progress"><span><i style:width={`${row.progress}%`}></i></span><b>{row.progress}%</b></div></td><td><code>{row.evidenceState}</code></td><td>{row.nextAction}</td><td>{row.eta}</td><td>{row.mergeGate}</td></tr>
      {/each}
    </tbody></table></div>
  </section>

  <div class="split">
    <section class="panel"><header><div><p class="eyebrow">CAPABILITY BOUNDARY</p><h2>현재 가능한 것과 차단된 것</h2></div></header><div class="capabilities">{#each PROGRAM_CAPABILITIES as item}<article><div><strong>{capabilityLabel(item.id, item.capability)}</strong><p>{item.boundary}</p></div><span class={stateClass(item.state)}>{item.state}</span></article>{/each}</div></section>
    <section class="panel release"><header><div><p class="eyebrow">DELIVERY LINEAGE</p><h2>브랜치·PR·버전 흐름</h2></div></header><dl><div><dt>개발 버전</dt><dd>{PROGRAM_EXECUTION.developmentVersion}</dd></div><div><dt>개발 계보</dt><dd>{PROGRAM_EXECUTION.deliveryLane}</dd></div><div><dt>브랜치 보존</dt><dd>{PROGRAM_EXECUTION.branchRetentionPolicy}</dd></div><div><dt>최근 릴리즈</dt><dd>{PROGRAM_EXECUTION.latestRelease}</dd></div><div><dt>Fresh OOS</dt><dd>{PROGRAM_EXECUTION.freshOos}</dd></div></dl><ol><li>v1.28.0 연구 플랫폼은 원격 태그와 GitHub Release로 게시했습니다.</li><li>다음 개발선은 develop/v1.29.0-dev이며 작업별 codex 브랜치를 만듭니다.</li><li>검증 후 develop에 비FF 병합하며, 병합된 작업 브랜치는 MERGED 이력으로 보존합니다.</li><li>v1.28.0 태그는 연구 플랫폼 릴리즈이며 모델 GO를 뜻하지 않습니다.</li></ol><p class="warning">버전 태그는 연구 플랫폼 릴리스만 표시하며 모델 GO 또는 실거래 준비를 뜻하지 않습니다.</p></section>
  </div>
</section>

<style>
  .scorecard{display:flex;flex-direction:column;gap:18px;min-width:0;color:var(--fg)}.masthead{display:grid;grid-template-columns:1fr auto;gap:24px;align-items:end;border:1px solid var(--border-strong);padding:clamp(18px,3vw,30px);background:var(--surface-raised)}.eyebrow{margin:0;color:var(--accent);font:800 .68rem/1.2 ui-monospace,monospace;letter-spacing:.13em}.masthead h1{margin:8px 0 5px;color:var(--fg-strong);font-size:clamp(1.9rem,5vw,3.2rem)}.masthead p:last-child{margin:0;color:var(--muted)}.score-cluster{display:flex;gap:10px;flex-wrap:wrap;justify-content:flex-end}.score-cluster>div{display:grid;grid-template-columns:auto auto;align-items:end;border-left:4px solid var(--accent);padding:8px 12px}.score-cluster span{grid-column:1/-1;color:var(--muted);font:800 .6rem ui-monospace,monospace}.score-cluster strong{color:var(--fg-strong);font:800 2.7rem/.9 ui-monospace,monospace}.score-cluster small{color:var(--muted);font:700 .7rem ui-monospace,monospace}.score-cluster .danger{border-color:var(--danger)}.score-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:9px}.score-grid article,.panel{border:1px solid var(--border);background:var(--surface-raised)}.score-grid article{display:flex;min-width:0;flex-direction:column;padding:14px}.score-head{display:flex;justify-content:space-between;gap:8px}.score-head span{font-weight:800}.score-head strong{font:800 1.35rem ui-monospace,monospace}.track{height:6px;margin:12px 0;background:var(--border)}.track i{display:block;height:100%;background:var(--accent)}.score-grid p{min-height:56px;margin:0;color:var(--muted);font-size:.76rem;line-height:1.45}.score-grid footer{display:flex;flex-direction:column;gap:7px;margin-top:auto;padding-top:12px}.score-grid small{color:var(--dim);font-size:.68rem}.good,.partial,.blocked{display:inline-block;width:max-content;border:1px solid currentColor;padding:2px 6px;font:800 .65rem ui-monospace,monospace}.good{color:var(--success)}.partial{color:var(--warn)}.blocked{color:var(--danger)}.panel{min-width:0;padding:18px}.panel>header{display:flex;align-items:end;justify-content:space-between;gap:12px;margin-bottom:14px}.panel h2{margin:4px 0 0;color:var(--fg-strong);font-size:1.2rem}.panel>header>span{max-width:360px;color:var(--muted);font-size:.72rem;text-align:right}.table-wrap{overflow-x:auto}table{width:100%;min-width:1420px;border-collapse:collapse;font-size:.76rem}th,td{border-top:1px solid var(--border);padding:10px;text-align:left;vertical-align:top}th{color:var(--muted);font:800 .66rem ui-monospace,monospace;letter-spacing:.05em}td:nth-child(2){min-width:130px}td:nth-child(2) small{display:block;color:var(--dim);font:700 .6rem ui-monospace,monospace}td code{color:var(--accent);font-size:.67rem}.priority{display:inline-block;border:1px solid var(--warn);padding:2px 5px;color:var(--warn);font:800 .65rem ui-monospace,monospace}.progress{display:flex;align-items:center;gap:7px;min-width:110px}.progress>span{width:70px;height:5px;background:var(--border)}.progress i{display:block;height:100%;background:var(--accent)}.progress b{font:800 .68rem ui-monospace,monospace}.split{display:grid;grid-template-columns:1.2fr .8fr;gap:12px}.capabilities{display:grid;gap:7px}.capabilities article{display:flex;align-items:center;justify-content:space-between;gap:12px;border-top:1px solid var(--border);padding:9px 0}.capabilities p{margin:3px 0 0;color:var(--muted);font-size:.75rem}.release dl{display:grid;gap:10px;margin:0}.release dl div{display:grid;grid-template-columns:90px minmax(0,1fr);gap:10px;border-top:1px solid var(--border);padding-top:9px}.release dt{color:var(--muted)}.release dd{margin:0;overflow-wrap:anywhere;font:700 .72rem ui-monospace,monospace}.release ol{padding-left:20px;color:var(--muted);font-size:.76rem;line-height:1.6}.warning{border-left:3px solid var(--warn);margin:16px 0 0;padding:8px 10px;background:var(--warn-soft);color:var(--warn);font-size:.75rem}.snapshot-note{display:flex;justify-content:space-between;gap:12px;border:1px solid var(--warn);padding:9px 12px;background:var(--warn-soft);color:var(--warn);font:700 .72rem ui-monospace,monospace}.snapshot-note span{text-align:right;overflow-wrap:anywhere}@media(max-width:1200px){.masthead{grid-template-columns:1fr}.score-cluster{justify-content:flex-start}.score-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.split{grid-template-columns:1fr}}@media(max-width:640px){.score-grid{grid-template-columns:1fr}.score-grid p{min-height:0}.panel>header{align-items:start;flex-direction:column}.panel>header>span{text-align:left}.capabilities article{align-items:start;flex-direction:column}.release dl div{grid-template-columns:1fr}.snapshot-note{flex-direction:column}.snapshot-note span{text-align:left}}
</style>
