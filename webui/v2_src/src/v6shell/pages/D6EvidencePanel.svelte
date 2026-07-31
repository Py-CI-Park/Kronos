<script lang="ts">
  import { D6_PRESENTATION, type D6Evidence } from '../discovery/d6Evidence';

  let { evidence }: { evidence: D6Evidence } = $props();
  const pct = (value: number) => `${(value * 100).toFixed(1)}%`;
  const signed = (value: number) => `${value >= 0 ? '+' : ''}${value.toFixed(3)}`;
  const gates = $derived([
    ['Native accuracy', pct(evidence.nativeMedianAccuracy), '≥ 20.0%', evidence.nativeMedianAccuracy >= .2],
    ['Native reward ratio', signed(evidence.nativeMedianRewardRatio), '≥ 0.000', evidence.nativeMedianRewardRatio >= 0],
    ['Native total reward', signed(evidence.nativeMedianTotalReward), '≥ 0.000', evidence.nativeMedianTotalReward >= 0],
    ['Native − shuffled', signed(evidence.nativeRewardDeltaVsShuffled), '≥ +0.100', evidence.nativeRewardDeltaVsShuffled >= .1],
    ['Passing seeds', pct(evidence.nativePassingSeedFraction), '≥ 66.7%', evidence.nativePassingSeedFraction >= 2 / 3],
    ['Median drawdown', evidence.nativeMedianDrawdown.toFixed(3), '≤ 0.250', evidence.nativeMedianDrawdown <= .25],
    ['Invalid actions', String(evidence.invalidActionCount), '= 0', evidence.invalidActionCount === 0],
  ] as const);
</script>

<section class="verdict">
  <div>
    <p>D6 // REUSED VALIDATION</p>
    <h2>{evidence.verdict}</h2>
    <span>동결 D5S 100K 정책 · 128 validation episodes · 실제 DQN 6개 평가</span>
  </div>
  <div class="stamps"><strong>{D6_PRESENTATION.gateStatus}</strong><b>{D6_PRESENTATION.d7Seal}</b><em>{D6_PRESENTATION.claimBoundary}</em></div>
</section>

<section class="comparison" aria-label="D5S train to D6 validation comparison">
  <article class="train"><span>D5S TRAIN_ONLY</span><strong>82.7%</strong><small>accuracy · selected policy</small></article>
  <i>→</i>
  <article class="fail"><span>D6 VALIDATION</span><strong>{pct(evidence.nativeMedianAccuracy)}</strong><small>accuracy · near random 16.7%</small></article>
  <article class="train"><span>D5S TRAIN REWARD</span><strong>+0.971</strong><small>median ratio</small></article>
  <i>→</i>
  <article class="fail"><span>D6 VALIDATION REWARD</span><strong>{signed(evidence.nativeMedianRewardRatio)}</strong><small>23bp median ratio</small></article>
</section>

<section class="panel gate-panel">
  <header><div><p>PREREGISTERED GATES</p><h2>Validation 판정표</h2></div><span>실패를 숨기지 않는 재계산 값</span></header>
  <div class="gates">
    {#each gates as gate}
      <article class:ok={gate[3]}><span>{gate[0]}</span><strong>{gate[1]}</strong><small>{gate[2]}</small><b>{gate[3] ? 'PASS' : 'FAIL'}</b></article>
    {/each}
  </div>
</section>

<section class="panel">
  <header><div><p>EXACT VALIDATION MATRIX</p><h2>Reward arm × seed</h2></div><span>{evidence.evaluations.length} authenticated evaluations</span></header>
  <div class="matrix">
    {#each evidence.evaluations as row}
      <article class:control={row.rewardArm === 'SHUFFLED'}>
        <div class="identity"><span>{row.rewardArm}{row.rewardArm === 'SHUFFLED' ? ' CONTROL' : ''}</span><b>SEED {row.seed}</b></div>
        <strong>{signed(row.rewardRatio)}</strong>
        <dl>
          <div><dt>Accuracy</dt><dd>{pct(row.accuracy)}</dd></div>
          <div><dt>Total reward</dt><dd>{signed(row.totalReward)}</dd></div>
          <div><dt>0bp ratio</dt><dd>{signed(row.zeroCostRewardRatio)}</dd></div>
          <div><dt>Trade rate</dt><dd>{pct(row.tradeRate)}</dd></div>
          <div><dt>Max drawdown</dt><dd>{row.maximumDrawdown.toFixed(3)}</dd></div>
        </dl>
      </article>
    {/each}
  </div>
</section>

<section class="diagnosis">
  <div><p>WHY NO-GO?</p><h2>비용 문제가 아니라 일반화 실패입니다</h2></div>
  <ul>
    <li>Native median accuracy <b>{pct(evidence.nativeMedianAccuracy)}</b>는 무작위 6-action 기준 16.7%에 가깝습니다.</li>
    <li>23bp를 제거한 Native median reward ratio도 <b>{signed(evidence.nativeMedianZeroCostRewardRatio)}</b>이므로 비용만으로 실패를 설명할 수 없습니다.</li>
    <li>Native가 shuffled control보다 <b>{Math.abs(evidence.nativeRewardDeltaVsShuffled).toFixed(3)}</b> 낮아 control separation이 역전됐습니다.</li>
    <li>다음 단계는 이미 읽은 validation에 재튜닝하는 것이 아니라 D6R train-only 반증 연구입니다. D7 Fresh OOS는 계속 봉인합니다.</li>
  </ul>
</section>

<section class="custody">
  <div><span>RUN</span><strong>{evidence.runName}</strong></div>
  <div><span>VALIDATION SNAPSHOT</span><strong>{evidence.validationEpisodeSha}</strong></div>
  <div><span>RECOVERY</span><strong>{evidence.recoveryRun} · READ COUNT {evidence.validationReadCount}</strong></div>
  <div><span>PREREG / MANIFEST</span><strong>{evidence.preregSha} / {evidence.manifestSha}</strong></div>
  <p>{evidence.validationOrigin}에서 동일한 128-episode snapshot을 복구해 평가했습니다. Promotion·profitability·live claim은 모두 차단됩니다.</p>
</section>

<style>
  .verdict,.panel,.custody,.diagnosis{border:1px solid var(--border);background:var(--surface-raised)}.verdict{display:grid;grid-template-columns:1.4fr 1fr;gap:18px;border-left:5px solid var(--danger);padding:18px;background:linear-gradient(110deg,color-mix(in srgb,var(--danger) 12%,transparent),var(--surface-raised) 48%)}p{margin:0;color:var(--accent);font:800 .65rem ui-monospace,monospace;letter-spacing:.12em}h2{margin:5px 0;color:var(--fg-strong);font-size:1.15rem}.verdict span,header>span{color:var(--muted)}.stamps{display:grid;grid-template-columns:1fr 1fr;gap:7px;align-content:center}.stamps>*{border:1px solid var(--danger);padding:8px;color:var(--danger);font:900 .68rem ui-monospace,monospace;text-align:center}.stamps strong{grid-column:1/-1;background:color-mix(in srgb,var(--danger) 10%,transparent)}.stamps em{font-style:normal}
  .comparison{display:grid;grid-template-columns:1fr auto 1fr 1fr auto 1fr;gap:8px;align-items:stretch}.comparison article{display:flex;flex-direction:column;gap:4px;border:1px solid var(--border);border-top:3px solid var(--success);padding:11px;background:var(--surface-sunken)}.comparison article.fail{border-top-color:var(--danger)}.comparison i{align-self:center;color:var(--dim);font-style:normal}.comparison span,.custody span{color:var(--dim);font:800 .58rem ui-monospace,monospace}.comparison strong{font:900 1.2rem ui-monospace,monospace}.comparison small{color:var(--muted)}
  .panel{padding:17px}.panel header{display:flex;justify-content:space-between;align-items:end;margin-bottom:12px}.gates{display:grid;grid-template-columns:repeat(7,1fr);gap:7px}.gates article{display:flex;flex-direction:column;gap:5px;border:1px solid var(--danger);padding:10px;background:color-mix(in srgb,var(--danger) 6%,var(--surface-sunken))}.gates article.ok{border-color:var(--success)}.gates span{color:var(--dim);font-size:.66rem}.gates strong{font:900 1rem ui-monospace,monospace}.gates small{color:var(--muted)}.gates b{margin-top:auto;color:var(--danger);font:900 .6rem ui-monospace,monospace}.gates .ok b{color:var(--success)}
  .matrix{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.matrix article{border:1px solid var(--border-strong);border-top:3px solid var(--danger);padding:11px;background:var(--surface-sunken)}.matrix article.control{border-top-color:var(--info)}.identity{display:flex;justify-content:space-between;color:var(--dim);font:800 .6rem ui-monospace,monospace}.matrix>article>strong{display:block;margin:10px 0;color:var(--danger);font:900 1.3rem ui-monospace,monospace}.matrix dl{display:grid;gap:5px;margin:0;font-size:.7rem}.matrix dl div{display:flex;justify-content:space-between;gap:8px}dt{color:var(--dim)}dd{margin:0}
  .diagnosis{display:grid;grid-template-columns:.7fr 1.3fr;gap:18px;border-left:4px solid var(--danger);padding:17px}.diagnosis ul{margin:0;padding-left:20px}.diagnosis li{margin-bottom:7px;line-height:1.45}.custody{display:grid;gap:7px;padding:14px}.custody div{display:grid;grid-template-columns:170px 1fr;gap:10px}.custody strong{overflow-wrap:anywhere;font:700 .64rem ui-monospace,monospace}.custody p{margin-top:5px;color:var(--muted);font:inherit;line-height:1.5;letter-spacing:0}
  @media(max-width:1100px){.comparison{grid-template-columns:1fr auto 1fr}.gates{grid-template-columns:repeat(4,1fr)}}@media(max-width:700px){.verdict,.diagnosis,.matrix,.gates,.comparison{grid-template-columns:1fr}.comparison i{display:none}.custody div{grid-template-columns:1fr}}
</style>
