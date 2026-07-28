<script lang="ts">
  import { REVIEWED_DISCOVERY_SNAPSHOT } from './discovery/reviewedDiscoverySnapshot';

  const evidence = REVIEWED_DISCOVERY_SNAPSHOT;
</script>

<aside class="d2-context" aria-label="D2 실제 일봉 강화학습 공통 상태">
  <div class="stamp"><span>CURRENT RL EVIDENCE</span><strong>D2</strong></div>
  <dl>
    <div><dt>판정</dt><dd>{evidence.verdict}</dd></div>
    <div><dt>실제 모델</dt><dd>{evidence.arms.length}/24 COMPLETE</dd></div>
    <div><dt>확인 규모</dt><dd>{evidence.maximumConfirmedEpisodeCount} / 128 EPISODES</dd></div>
    <div><dt>@128 분리</dt><dd>+{evidence.nativeDeltaVsShuffled?.toFixed(3)}× NATIVE−SHUFFLE</dd></div>
    <div><dt>비용</dt><dd>{evidence.primaryRoundTripCostBp}bp TRAIN · {evidence.diagnosticRoundTripCostBp}bp DIAGNOSTIC</dd></div>
  </dl>
  <p>아래 페이지의 Type1·일반 API 증거와 D2 train-only 결과를 합산하지 않습니다. Fresh OOS·수익성·라이브는 계속 차단됩니다.</p>
</aside>

<style>
  .d2-context{display:grid;grid-template-columns:auto minmax(0,1fr) minmax(220px,.55fr);gap:14px;align-items:center;border:1px solid var(--border-strong);border-left:4px solid var(--warn);padding:10px 14px;background:linear-gradient(100deg,var(--warn-soft),var(--surface-raised) 38%);min-width:0}.stamp{display:grid;grid-template-columns:auto auto;align-items:end;gap:6px}.stamp span{grid-column:1/-1;color:var(--warn);font:800 .58rem ui-monospace,monospace;letter-spacing:.1em}.stamp strong{color:var(--fg-strong);font:900 1.8rem/.9 ui-monospace,monospace}dl{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin:0;min-width:0}dl div{border-left:1px solid var(--border);padding-left:8px;min-width:0}dt{color:var(--dim);font:800 .58rem ui-monospace,monospace}dd{margin:3px 0 0;color:var(--fg);font:700 .66rem ui-monospace,monospace;overflow-wrap:anywhere}.d2-context p{margin:0;color:var(--muted);font-size:.67rem;line-height:1.45}@media(max-width:1100px){.d2-context{grid-template-columns:auto 1fr}.d2-context p{grid-column:1/-1}dl{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:700px){.d2-context{grid-template-columns:1fr}dl{grid-template-columns:1fr 1fr}.d2-context p{grid-column:auto}}@media(max-width:430px){dl{grid-template-columns:1fr}}
</style>
