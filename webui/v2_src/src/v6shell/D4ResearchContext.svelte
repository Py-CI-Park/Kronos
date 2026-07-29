<script lang="ts">
  import { REVIEWED_DISCOVERY_SNAPSHOT } from './discovery/reviewedDiscoverySnapshot';
  const evidence = REVIEWED_DISCOVERY_SNAPSHOT;
</script>

<aside class="research-context" aria-label="D4 강화학습 공통 연구 상태">
  <div class="stamp"><span>CURRENT RL EVIDENCE</span><strong>D4</strong><em>TRAIN-ONLY</em></div>
  <dl>
    <div><dt>판정</dt><dd>{evidence.verdict}</dd></div>
    <div><dt>실제 모델</dt><dd>{evidence.arms.length}/24 COMPLETE</dd></div>
    <div><dt>최선 RL</dt><dd>{evidence.bestRlArm}</dd></div>
    <div><dt>상한 격차</dt><dd>{evidence.bestRlGapToSupervisedCeiling?.toFixed(3)}</dd></div>
    <div><dt>통과 RL arm</dt><dd>{evidence.confirmedRlArmCount} / 3</dd></div>
  </dl>
  <p>DQN이 128개 train episode에서 학습 가능성을 확인했습니다. 이는 과적합 진단이며 Fresh OOS·수익성·실거래 근거가 아닙니다.</p>
</aside>

<style>
  .research-context{display:grid;grid-template-columns:auto minmax(0,1fr) minmax(260px,.6fr);gap:14px;align-items:center;border:1px solid var(--border-strong);border-left:4px solid var(--success);padding:11px 14px;background:linear-gradient(105deg,color-mix(in srgb,var(--success) 13%,transparent),var(--surface-raised) 42%);min-width:0}.stamp{display:grid;grid-template-columns:auto auto;align-items:end;gap:5px 8px}.stamp span{grid-column:1/-1;color:var(--success);font:800 .58rem "IBM Plex Mono",ui-monospace,monospace;letter-spacing:.11em}.stamp strong{color:var(--fg-strong);font:900 1.85rem/.9 "IBM Plex Mono",ui-monospace,monospace}.stamp em{border:1px solid var(--success);padding:2px 5px;color:var(--success);font:900 .6rem "IBM Plex Mono",ui-monospace,monospace;font-style:normal}dl{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin:0;min-width:0}dl div{border-left:1px solid var(--border);padding-left:8px;min-width:0}dt{color:var(--dim);font:800 .58rem "IBM Plex Mono",ui-monospace,monospace}dd{margin:3px 0 0;color:var(--fg);font:700 .66rem "IBM Plex Mono",ui-monospace,monospace;overflow-wrap:anywhere}.research-context p{margin:0;color:var(--muted);font-size:.68rem;line-height:1.45}@media(max-width:1100px){.research-context{grid-template-columns:auto 1fr}.research-context p{grid-column:1/-1}dl{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:700px){.research-context{grid-template-columns:1fr}dl{grid-template-columns:1fr 1fr}.research-context p{grid-column:auto}}@media(max-width:430px){dl{grid-template-columns:1fr}}
</style>
