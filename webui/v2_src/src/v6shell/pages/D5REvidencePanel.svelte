<script lang="ts">
  import { summarizeDiscoveryArms, type DiscoveryEvidence } from '../discovery/discoveryEvidence';

  let { evidence }: { evidence: DiscoveryEvidence } = $props();
  const aggregates = $derived(summarizeDiscoveryArms(evidence.arms));
  const pct = (value: number | undefined) => `${((value ?? 0) * 100).toFixed(1)}%`;
  const signedPct = (value: number | undefined) => `${((value ?? 0) * 100).toFixed(2)} pp`;
  const pass = (value: number | undefined, threshold: number) => (value ?? -Infinity) >= threshold;
  const rewardLabel = (id: string) => id.includes('/SHUFFLED/') ? 'SHUFFLED CONTROL' : 'NATIVE';
</script>

<section class="verdict" class:confirmed={evidence.verdict === 'D5R_CAPACITY_CONFIRMED'}>
  <div><p>D5R // CAPACITY + OBJECTIVE</p><h2>RESEARCH ONLY / {evidence.verdict}</h2><span>실제 DQN · 573 TRAIN_ONLY · 12 / 12 checkpoint units</span></div>
  <dl>
    <div><dt>Accuracy lift</dt><dd class:ok={pass(evidence.nativeAccuracyLift, .03)}>{signedPct(evidence.nativeAccuracyLift)}<small>gate ≥ 3.00 pp</small></dd></div>
    <div><dt>Reward lift</dt><dd class:ok={pass(evidence.nativeRewardRatioLift, .02)}>{signedPct(evidence.nativeRewardRatioLift)}<small>gate ≥ 2.00 pp</small></dd></div>
    <div><dt>Native − shuffle</dt><dd class:ok={pass(evidence.nativeDeltaVsShuffled, .2)}>{evidence.nativeDeltaVsShuffled?.toFixed(3)}<small>gate ≥ 0.200</small></dd></div>
    <div><dt>Improving seeds</dt><dd class:ok={pass(evidence.improvingSeedFraction, 2 / 3)}>{pct(evidence.improvingSeedFraction)}<small>gate ≥ 66.7%</small></dd></div>
  </dl>
</section>

<section class="boundary" aria-label="D5R research boundaries">
  <article><span>LINEAGE</span><strong>0 → 400K → 800K</strong><small>replay preserved in-process</small></article>
  <article><span>COST</span><strong>23BP PRIMARY</strong><small>0bp is diagnostic only</small></article>
  <article><span>REUSED VALIDATION</span><strong>{evidence.reusedValidation ?? 'NOT_RUN_NO_READ'}</strong><small>D6 remains sealed</small></article>
  <article><span>FRESH OOS</span><strong>{evidence.freshOos}</strong><small>D7 remains sealed</small></article>
  <article><span>D5 VERDICT</span><strong>UNCHANGED NO-GO</strong><small>capacity result is not promotion</small></article>
</section>

<section class="panel">
  <header><div><p>CAPACITY CURVE</p><h2>Reward arm × training steps</h2></div><span>3 deterministic seeds per cell</span></header>
  <div class="capacity-grid">
    {#each aggregates as row}
      <article class:control={row.id.includes('/SHUFFLED/')}>
        <div><span>{rewardLabel(row.id)}</span><b>{row.id.endsWith('/800000') ? '800K' : '400K'}</b></div>
        <strong>{row.meanOracleRewardRatio.toFixed(3)}</strong>
        <small>native 23bp reward · accuracy {pct(row.meanExactBasketAccuracy)} · {row.seedCount} seeds</small>
      </article>
    {/each}
  </div>
</section>

<section class="panel">
  <header><div><p>EXACT MATRIX</p><h2>모든 checkpoint 증거</h2></div><span>{evidence.arms.length} authenticated outcomes</span></header>
  <div class="matrix">
    {#each evidence.arms as row}
      <article class:control={row.shuffledReward}>
        <div class="identity"><span>{row.shuffledReward ? 'SHUFFLED' : 'NATIVE'}</span><b>SEED {row.seed} · {row.trainingTimesteps / 1000}K</b></div>
        <strong>{row.oracleRewardRatio.toFixed(3)}</strong>
        <dl>
          <div><dt>Fit 23bp</dt><dd>{row.fitRewardRatio?.toFixed(3)}</dd></div>
          <div><dt>Native 23bp</dt><dd>{row.oracleRewardRatio.toFixed(3)}</dd></div>
          <div><dt>Native 0bp</dt><dd>{row.diagnosticCostRewardRatio?.toFixed(3)}</dd></div>
          <div><dt>Accuracy</dt><dd>{pct(row.exactBasketAccuracy)}</dd></div>
          <div><dt>Invalid</dt><dd>{row.invalidActionCount}</dd></div>
        </dl>
      </article>
    {/each}
  </div>
</section>

<section class="custody">
  <div><span>RUN</span><strong>{evidence.runName}</strong></div>
  <div><span>PREREG SHA</span><strong>{evidence.preregSha256}</strong></div>
  <div><span>ARTIFACT MANIFEST</span><strong>{evidence.evidenceManifest}</strong></div>
  <p>D5R은 학습 용량 가설만 검증합니다. 결과가 CONFIRMED여도 수익성·promotion·paper forward·실거래를 허용하지 않으며, D6 validation과 D7 Fresh OOS는 별도 승인 전까지 읽지 않습니다.</p>
</section>

<style>
  .verdict,.panel,.custody{border:1px solid var(--border);background:var(--surface-raised)}
  .verdict{display:grid;grid-template-columns:1.1fr 1.9fr;gap:20px;border-left:5px solid var(--warn);padding:18px;background:linear-gradient(110deg,color-mix(in srgb,var(--warn) 10%,transparent),var(--surface-raised) 46%)}.verdict.confirmed{border-left-color:var(--success)}
  p{margin:0;color:var(--accent);font:800 .65rem ui-monospace,monospace;letter-spacing:.12em}h2{margin:5px 0;color:var(--fg-strong);font-size:1.15rem}.verdict span,header>span{color:var(--muted)}
  dl{display:grid;gap:7px;margin:0}.verdict dl{grid-template-columns:repeat(2,1fr)}dl div{display:flex;justify-content:space-between;gap:8px}dt{color:var(--dim)}dd{margin:0;text-align:right;color:var(--warn)}dd.ok{color:var(--success)}dd small{display:block;color:var(--muted)}
  .boundary{display:grid;grid-template-columns:repeat(5,1fr);border:1px solid var(--border-strong);background:var(--surface-sunken)}.boundary article{display:flex;flex-direction:column;gap:5px;border-right:1px solid var(--border);padding:12px}.boundary article:last-child{border:0}.boundary span{color:var(--dim);font:800 .58rem ui-monospace,monospace}.boundary strong{color:var(--warn);font:800 .7rem ui-monospace,monospace}.boundary small{color:var(--muted)}
  .panel{padding:17px}.panel header{display:flex;justify-content:space-between;align-items:end;margin-bottom:12px}.capacity-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}.capacity-grid article,.matrix article{border:1px solid var(--border-strong);border-top:3px solid var(--success);padding:12px;background:var(--surface-sunken)}.capacity-grid article.control,.matrix article.control{border-top-color:var(--info)}.capacity-grid article>div,.identity{display:flex;justify-content:space-between;color:var(--dim);font:800 .62rem ui-monospace,monospace}.capacity-grid strong,.matrix>article>strong{display:block;margin:9px 0;font:900 1.35rem ui-monospace,monospace}.capacity-grid small{color:var(--muted)}
  .matrix{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.matrix dl{font-size:.68rem}.matrix dd{color:var(--fg)}
  .custody{display:grid;gap:7px;padding:14px}.custody div{display:grid;grid-template-columns:150px 1fr;gap:10px}.custody span{color:var(--dim);font:800 .6rem ui-monospace,monospace}.custody strong{overflow-wrap:anywhere;font:700 .65rem ui-monospace,monospace}.custody p{margin-top:5px;color:var(--muted);font:inherit;line-height:1.5;letter-spacing:0}
  @media(max-width:1050px){.capacity-grid,.matrix{grid-template-columns:repeat(2,1fr)}.boundary{grid-template-columns:repeat(2,1fr)}}
  @media(max-width:650px){.verdict,.capacity-grid,.matrix,.boundary{grid-template-columns:1fr}.verdict dl{grid-template-columns:1fr}.custody div{grid-template-columns:1fr}}
</style>
