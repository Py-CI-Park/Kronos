<aside class="research-context" aria-label="일봉 강화학습 공통 연구 상태">
  <div class="stamp"><span>CURRENT RESEARCH STAGE</span><strong>D0/D1 · A1</strong><em>VALIDATION CANDIDATE · AUTHORITY BLOCKED</em></div>
  <dl>
    <div><dt>신규 검증</dt><dd>TRAIN 76 · VAL 24 · TEST FEATURES CONSUMED</dd></div><div><dt>행동 궤적</dt><dd>2,432 TRANSITIONS</dd></div>
    <div><dt>모델 계보</dt><dd>이전 20 NO-GO · 신규 10 VAL</dd></div><div><dt>Fresh OOS</dt><dd>NOT_RUN_NO_READ</dd></div>
  </dl>
  <p>이전 이진 CQL 20개는 historical TEST 중앙값 -10.19%로 NO-GO입니다. 4행동 001/002도 TEST feature를 파싱해 historical TEST는 이미 오염됐고 reward·체결만 미열람입니다. 최종 경제 판단은 새 Fresh OOS만 사용합니다.</p>
</aside>
<style>
  .research-context{display:grid;grid-template-columns:auto minmax(0,1fr) minmax(260px,.6fr);gap:14px;align-items:center;border:1px solid var(--border-strong);border-left:4px solid var(--danger);padding:11px 14px;background:linear-gradient(105deg,color-mix(in srgb,var(--danger) 11%,transparent),var(--surface-raised) 42%);min-width:0}.stamp{display:grid;grid-template-columns:auto auto;align-items:end;gap:5px 8px;min-width:0}.stamp span{grid-column:1/-1;color:var(--danger);font:800 .58rem ui-monospace,monospace;letter-spacing:.11em}.stamp strong{font:900 1.85rem/.9 ui-monospace,monospace}.stamp em{border:1px solid var(--danger);padding:2px 5px;color:var(--danger);font:900 .6rem ui-monospace,monospace;font-style:normal;overflow-wrap:anywhere}dl{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:0;min-width:0}dl div{min-width:0;border-left:1px solid var(--border);padding-left:8px}dt{color:var(--dim);font:800 .58rem ui-monospace,monospace;overflow-wrap:anywhere}dd{margin:3px 0 0;font:700 .66rem ui-monospace,monospace;overflow-wrap:anywhere}.research-context p{margin:0;color:var(--muted);font-size:.68rem;line-height:1.45}@media(max-width:1180px){.research-context{grid-template-columns:1fr}dl{grid-template-columns:repeat(4,minmax(0,1fr))}}@media(max-width:620px){dl{grid-template-columns:1fr 1fr}}
</style>
