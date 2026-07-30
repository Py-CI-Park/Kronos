<script lang="ts">
  import { summarizeDiscoveryArms } from '../discovery/discoveryEvidence';
  import { D5S_PRESENTATION, formatD5SCheckpointSteps, type D5SEvidence } from '../discovery/d5sEvidence';

  let { evidence }: { evidence: D5SEvidence } = $props();
  const aggregates = $derived(summarizeDiscoveryArms(evidence.arms));
  const pct = (value: number) => `${(value * 100).toFixed(1)}%`;
  const selected = (id: string) => id.endsWith(`/${evidence.selectedSteps}`);
  const passMin = (value: number, threshold: number) => value >= threshold;
  const passMax = (value: number, threshold: number) => value <= threshold;
  const armLabel = (id: string) => id.includes('/SHUFFLED/') ? 'SHUFFLED CONTROL' : 'NATIVE';
  const checkpointLabel = (id: string) => {
    const steps = Number(id.split('/').at(-1));
    return formatD5SCheckpointSteps(steps);
  };
</script>

<section class="verdict" class:confirmed={evidence.verdict === 'D5S_STABILITY_CONFIRMED'}>
  <div>
    <p>D5S // GLOBAL EARLY-STOP STABILITY</p>
    <h2>{D5S_PRESENTATION.claimBoundary} / {evidence.verdict}</h2>
    <span>실제 DQN · 573 TRAIN_ONLY · 36 / 36 checkpoint units</span>
  </div>
  <div class="headline">
    <article><span>GLOBAL SELECTED</span><strong>{formatD5SCheckpointSteps(evidence.selectedSteps)}</strong><small>모든 seed·arm에 동일 적용</small></article>
    <article><span>NATIVE REWARD</span><strong>{evidence.selectedNativeMedianRewardRatio.toFixed(3)}</strong><small>23bp median</small></article>
    <article><span>NATIVE ACCURACY</span><strong>{pct(evidence.selectedNativeMedianAccuracy)}</strong><small>selected checkpoint</small></article>
    <article><span>NATIVE − SHUFFLE</span><strong>{evidence.nativeDeltaVsShuffled.toFixed(3)}</strong><small>negative control</small></article>
  </div>
</section>

<section class="boundary" aria-label="D5S research boundaries">
  <article><span>LINEAGE</span><strong>0 → 50K … 400K</strong><small>6 checkpoints · replay continuity</small></article>
  <article><span>COST</span><strong>23BP PRIMARY</strong><small>0bp is diagnostic only</small></article>
  <article><span>SELECTION</span><strong>ONE GLOBAL STEP</strong><small>seed별 선택·재학습 금지</small></article>
  <article><span>REUSED VALIDATION</span><strong>{evidence.reusedValidation}</strong><small>{D5S_PRESENTATION.d6Seal}</small></article>
  <article><span>FRESH OOS</span><strong>{evidence.freshOos}</strong><small>{D5S_PRESENTATION.d7Seal}</small></article>
</section>

<section class="panel gate-panel">
  <header><div><p>PREREGISTERED GATE</p><h2>안정성 판정표</h2></div><span>artifact에서 재계산된 값</span></header>
  <div class="table-wrap">
    <table>
      <thead><tr><th>항목</th><th>실측</th><th>기준</th><th>판정</th></tr></thead>
      <tbody>
        <tr><td>Selected native accuracy</td><td>{pct(evidence.selectedNativeMedianAccuracy)}</td><td>≥ 71.2%</td><td class:ok={passMin(evidence.selectedNativeMedianAccuracy, .7120418848167539)}>{passMin(evidence.selectedNativeMedianAccuracy, .7120418848167539) ? 'PASS' : 'FAIL'}</td></tr>
        <tr><td>Selected native reward</td><td>{evidence.selectedNativeMedianRewardRatio.toFixed(3)}</td><td>≥ 0.873</td><td class:ok={passMin(evidence.selectedNativeMedianRewardRatio, .8727793884825973)}>{passMin(evidence.selectedNativeMedianRewardRatio, .8727793884825973) ? 'PASS' : 'FAIL'}</td></tr>
        <tr><td>Native − shuffled</td><td>{evidence.nativeDeltaVsShuffled.toFixed(3)}</td><td>≥ 0.200</td><td class:ok={passMin(evidence.nativeDeltaVsShuffled, .2)}>{passMin(evidence.nativeDeltaVsShuffled, .2) ? 'PASS' : 'FAIL'}</td></tr>
        <tr><td>400K accuracy degradation</td><td>{pct(evidence.accuracyDegradationAt400k)}</td><td>≤ 5.0%</td><td class:ok={passMax(evidence.accuracyDegradationAt400k, .05)}>{passMax(evidence.accuracyDegradationAt400k, .05) ? 'PASS' : 'FAIL'}</td></tr>
        <tr><td>400K reward degradation</td><td>{evidence.rewardRatioDegradationAt400k.toFixed(3)}</td><td>≤ 0.050</td><td class:ok={passMax(evidence.rewardRatioDegradationAt400k, .05)}>{passMax(evidence.rewardRatioDegradationAt400k, .05) ? 'PASS' : 'FAIL'}</td></tr>
        <tr><td>Preserved native seeds</td><td>{pct(evidence.preservedNativeSeedFraction)}</td><td>≥ 66.7%</td><td class:ok={passMin(evidence.preservedNativeSeedFraction, 2 / 3)}>{passMin(evidence.preservedNativeSeedFraction, 2 / 3) ? 'PASS' : 'FAIL'}</td></tr>
        <tr><td>Invalid actions</td><td>{evidence.invalidActionCount}</td><td>= 0</td><td class:ok={evidence.invalidActionCount === 0}>{evidence.invalidActionCount === 0 ? 'PASS' : 'FAIL'}</td></tr>
      </tbody>
    </table>
  </div>
</section>

<section class="panel">
  <header><div><p>STABILITY CURVE</p><h2>Reward arm × checkpoint</h2></div><span>cell당 deterministic seed 3개</span></header>
  <div class="curve-grid">
    {#each aggregates as row}
      <article class:control={row.id.includes('/SHUFFLED/')} class:selected={selected(row.id)}>
        <div><span>{armLabel(row.id)}</span><b>{checkpointLabel(row.id)}</b></div>
        <strong>{row.meanOracleRewardRatio.toFixed(3)}</strong>
        <small>accuracy {pct(row.meanExactBasketAccuracy)} · {row.seedCount} seeds</small>
        {#if selected(row.id)}<em>GLOBAL SELECTED</em>{/if}
      </article>
    {/each}
  </div>
</section>

<section class="panel">
  <header><div><p>EXACT MATRIX</p><h2>모든 D5S checkpoint 증거</h2></div><span>{evidence.arms.length} authenticated outcomes</span></header>
  <div class="matrix">
    {#each evidence.arms as row}
      <article class:control={row.shuffledReward} class:selected={row.trainingTimesteps === evidence.selectedSteps}>
        <div class="identity"><span>{row.shuffledReward ? 'SHUFFLED' : 'NATIVE'}</span><b>SEED {row.seed} · {formatD5SCheckpointSteps(row.trainingTimesteps)}</b></div>
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
  <p>D5S는 TRAIN_ONLY에서 전역 조기종료 지점과 400K 안정성을 진단합니다. CONFIRMED여도 수익성·promotion·paper forward·실거래를 허용하지 않으며, D6 validation과 D7 Fresh OOS는 별도 승인 전까지 봉인됩니다.</p>
</section>

<style>
  .verdict,.panel,.custody{border:1px solid var(--border);background:var(--surface-raised)}.verdict{display:grid;grid-template-columns:.9fr 2.1fr;gap:18px;border-left:5px solid var(--warn);padding:18px;background:linear-gradient(110deg,color-mix(in srgb,var(--warn) 10%,transparent),var(--surface-raised) 46%)}.verdict.confirmed{border-left-color:var(--success)}p{margin:0;color:var(--accent);font:800 .65rem ui-monospace,monospace;letter-spacing:.12em}h2{margin:5px 0;color:var(--fg-strong);font-size:1.15rem}.verdict span,header>span{color:var(--muted)}
  .headline{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.headline article{display:flex;flex-direction:column;gap:5px;border-left:2px solid var(--accent);padding:8px 10px;background:var(--surface-sunken)}.headline span,.boundary span,.custody span{color:var(--dim);font:800 .58rem ui-monospace,monospace}.headline strong{font:900 1.2rem ui-monospace,monospace}.headline small,.boundary small{color:var(--muted)}
  .boundary{display:grid;grid-template-columns:repeat(5,1fr);border:1px solid var(--border-strong);background:var(--surface-sunken)}.boundary article{display:flex;flex-direction:column;gap:5px;border-right:1px solid var(--border);padding:12px}.boundary article:last-child{border:0}.boundary strong{color:var(--warn);font:800 .7rem ui-monospace,monospace}
  .panel{padding:17px}.panel header{display:flex;justify-content:space-between;align-items:end;margin-bottom:12px}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:.76rem}th,td{border-bottom:1px solid var(--border);padding:9px;text-align:left}th{color:var(--dim);font:800 .62rem ui-monospace,monospace}td:last-child{color:var(--danger);font-weight:900}.ok{color:var(--success)!important}
  .curve-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}.curve-grid article,.matrix article{position:relative;border:1px solid var(--border-strong);border-top:3px solid var(--success);padding:11px;background:var(--surface-sunken)}.curve-grid article.control,.matrix article.control{border-top-color:var(--info)}.curve-grid article.selected,.matrix article.selected{outline:1px solid var(--accent);box-shadow:inset 0 0 0 1px var(--accent-soft)}.curve-grid article>div,.identity{display:flex;justify-content:space-between;color:var(--dim);font:800 .58rem ui-monospace,monospace}.curve-grid strong,.matrix>article>strong{display:block;margin:9px 0;font:900 1.25rem ui-monospace,monospace}.curve-grid small{color:var(--muted)}em{display:inline-block;margin-top:8px;color:var(--accent);font:800 .55rem ui-monospace,monospace;font-style:normal}
  .matrix{display:grid;grid-template-columns:repeat(6,1fr);gap:7px}.matrix dl{display:grid;gap:5px;margin:0;font-size:.65rem}.matrix dl div{display:flex;justify-content:space-between;gap:6px}dt{color:var(--dim)}dd{margin:0}.custody{display:grid;gap:7px;padding:14px}.custody div{display:grid;grid-template-columns:150px 1fr;gap:10px}.custody strong{overflow-wrap:anywhere;font:700 .65rem ui-monospace,monospace}.custody p{margin-top:5px;color:var(--muted);font:inherit;line-height:1.5;letter-spacing:0}
  @media(max-width:1200px){.curve-grid,.matrix{grid-template-columns:repeat(3,1fr)}.headline{grid-template-columns:repeat(2,1fr)}.boundary{grid-template-columns:repeat(2,1fr)}}@media(max-width:650px){.verdict,.headline,.curve-grid,.matrix,.boundary{grid-template-columns:1fr}.custody div{grid-template-columns:1fr}}
</style>
