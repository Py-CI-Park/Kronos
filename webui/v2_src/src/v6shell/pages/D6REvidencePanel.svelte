<script lang="ts">
  import type { D6REvidence } from '../discovery/d6rEvidence';

  let { evidence }: { evidence: D6REvidence } = $props();
  const pct = (value: number) => `${(value * 100).toFixed(1)}%`;
  const signed = (value: number) => `${value >= 0 ? '+' : ''}${value.toFixed(3)}`;
  const isCandidate = $derived(evidence.verdict.endsWith('_CANDIDATE'));
  const primaryRows = $derived(
    evidence.evaluations.filter((row) => row.profile === 'TURNOVER_10BP' && row.rewardArm === 'NATIVE'),
  );
  const gates = $derived([
    ['Native accuracy', pct(evidence.nativeMedianAccuracy), '≥ 20.0%', evidence.nativeMedianAccuracy >= .2],
    ['23bp reward ratio', signed(evidence.nativeMedianRewardRatio), '≥ 0.000', evidence.nativeMedianRewardRatio >= 0],
    ['23bp total reward', signed(evidence.nativeMedianTotalReward), '≥ 0.000', evidence.nativeMedianTotalReward >= 0],
    ['Native − shuffled', signed(evidence.nativeRewardDeltaVsShuffled), '≥ +0.100', evidence.nativeRewardDeltaVsShuffled >= .1],
    ['Positive folds', pct(evidence.positiveFoldFraction), '≥ 80.0%', evidence.positiveFoldFraction >= .8],
    ['Positive seeds', pct(evidence.positiveSeedFraction), '≥ 66.7%', evidence.positiveSeedFraction >= 2 / 3],
    ['Native trade rate', pct(evidence.nativeMedianTradeRate), '≤ 65.0%', evidence.nativeMedianTradeRate <= .65],
    ['Trade-rate reduction', pct(evidence.tradeRateReductionVsCostOnly), '≥ 15.0%p', evidence.tradeRateReductionVsCostOnly >= .15],
    ['Median drawdown', evidence.nativeMedianDrawdown.toFixed(3), '≤ 0.250', evidence.nativeMedianDrawdown <= .25],
    ['Invalid actions', String(evidence.invalidActionCount), '= 0', evidence.invalidActionCount === 0],
  ] as const);
</script>

<section class:candidate={isCandidate} class="verdict">
  <div><p>D6R // TRAIN_ONLY FALSIFICATION</p><h2>{evidence.verdict}</h2><span>3,000,000 RL steps · 5 expanding folds · 3 seeds · Native/Shuffled control</span></div>
  <div class="stamps"><strong>{evidence.passedGateCount} / {evidence.totalGateCount} GATES PASS</strong><b>D7 {evidence.d7}</b><em>후보 ≠ 확인</em></div>
</section>

<section class="metrics" aria-label="D6R 주요 성과 지표">
  <article><span>23BP REWARD RATIO</span><strong>{signed(evidence.nativeMedianRewardRatio)}</strong><small>TURNOVER_10BP · Native median</small></article>
  <article><span>ACCURACY</span><strong>{pct(evidence.nativeMedianAccuracy)}</strong><small>6-action random reference 16.7%</small></article>
  <article><span>CONTROL SEPARATION</span><strong>{signed(evidence.nativeRewardDeltaVsShuffled)}</strong><small>Native − shuffled ratio</small></article>
  <article><span>TRADE RATE</span><strong>{pct(evidence.nativeMedianTradeRate)}</strong><small>{pct(evidence.tradeRateReductionVsCostOnly)}p lower vs cost-only</small></article>
  <article><span>FOLD / SEED STABILITY</span><strong>{pct(evidence.positiveFoldFraction)} / {pct(evidence.positiveSeedFraction)}</strong><small>positive median total reward</small></article>
  <article><span>DRAWDOWN</span><strong>{evidence.nativeMedianDrawdown.toFixed(3)}</strong><small>23bp reward drawdown</small></article>
</section>

<section class="panel">
  <header><div><p>PREREGISTERED DECISION</p><h2>10개 연구 게이트</h2></div><span>결과 이후 기준 변경 없음</span></header>
  <div class="gates">{#each gates as gate}<article class:ok={gate[3]}><span>{gate[0]}</span><strong>{gate[1]}</strong><small>{gate[2]}</small><b>{gate[3] ? 'PASS' : 'FAIL'}</b></article>{/each}</div>
</section>

<section class="panel">
  <header><div><p>CHRONOLOGICAL REPLAY</p><h2>TURNOVER_10BP · Native · fold × seed</h2></div><span>{primaryRows.length} / 15 authenticated evaluations</span></header>
  <div class="matrix">
    {#each primaryRows as row}
      <article class:positive={row.totalReward > 0}>
        <div><span>FOLD {row.foldId}</span><b>SEED {row.seed}</b></div><strong>{signed(row.rewardRatio)}</strong>
        <dl><div><dt>Total reward</dt><dd>{signed(row.totalReward)}</dd></div><div><dt>Accuracy</dt><dd>{pct(row.accuracy)}</dd></div><div><dt>Trade rate</dt><dd>{pct(row.tradeRate)}</dd></div><div><dt>Drawdown</dt><dd>{row.maximumDrawdown.toFixed(3)}</dd></div><div><dt>0bp diagnostic</dt><dd>{signed(row.zeroCostRewardRatio)}</dd></div></dl>
      </article>
    {/each}
  </div>
</section>

<section class="boundary">
  <div><p>INTERPRETATION BOUNDARY</p><h2>{isCandidate ? '후속 확인 연구 후보입니다.' : '현재 거래회전율 가설은 확인되지 않았습니다.'}</h2></div>
  <ul><li>D6 validation과 D7 Fresh OOS는 학습·선택에 사용하지 않았습니다.</li><li>기존 573일 전체 TRAIN_ONLY normalizer를 사용했으므로 통과해도 확인 결과가 아닙니다.</li><li>Promotion, 수익성 주장, paper-forward, 실거래 주문은 모두 차단됩니다.</li><li>다음 연구는 이 결과의 실패 게이트를 근거로 새 가설을 사전등록해야 합니다.</li></ul>
</section>

<section class="custody">
  <div><span>RUN</span><strong>{evidence.runName}</strong></div><div><span>PREREG</span><strong>{evidence.preregSha}</strong></div><div><span>MANIFEST</span><strong>{evidence.manifestSha}</strong></div><div><span>DATA BOUNDARY</span><strong>{evidence.trainingPartition} · {evidence.reusedValidation} · FRESH OOS {evidence.freshOos}</strong></div><div><span>NORMALIZER</span><strong>{evidence.normalizer}</strong></div>
</section>

<style>
  .verdict,.panel,.boundary,.custody{border:1px solid var(--border);background:var(--surface-raised)}.verdict{display:grid;grid-template-columns:1.4fr 1fr;gap:18px;border-left:5px solid var(--danger);padding:18px;background:linear-gradient(110deg,color-mix(in srgb,var(--danger) 12%,transparent),var(--surface-raised) 48%)}.verdict.candidate{border-left-color:var(--warn);background:linear-gradient(110deg,color-mix(in srgb,var(--warn) 12%,transparent),var(--surface-raised) 48%)}p{margin:0;color:var(--accent);font:800 .65rem ui-monospace,monospace;letter-spacing:.12em}h2{margin:5px 0;color:var(--fg-strong);font-size:1.15rem}.verdict span,header>span{color:var(--muted)}.stamps{display:grid;grid-template-columns:1fr 1fr;gap:7px;align-content:center}.stamps>*{border:1px solid var(--danger);padding:8px;color:var(--danger);font:900 .68rem ui-monospace,monospace;text-align:center}.candidate .stamps>*{border-color:var(--warn);color:var(--warn)}.stamps strong{grid-column:1/-1}.stamps em{font-style:normal}
  .metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.metrics article{display:flex;flex-direction:column;gap:5px;border:1px solid var(--border);border-top:3px solid var(--accent);padding:12px;background:var(--surface-sunken)}.metrics span,.custody span{color:var(--dim);font:800 .58rem ui-monospace,monospace}.metrics strong{font:900 1.18rem ui-monospace,monospace}.metrics small{color:var(--muted)}.panel{padding:17px}.panel header{display:flex;justify-content:space-between;align-items:end;margin-bottom:12px}.gates{display:grid;grid-template-columns:repeat(5,1fr);gap:7px}.gates article{display:flex;min-height:104px;flex-direction:column;gap:5px;border:1px solid var(--danger);padding:10px;background:color-mix(in srgb,var(--danger) 6%,var(--surface-sunken))}.gates article.ok{border-color:var(--success)}.gates span{color:var(--dim);font-size:.66rem}.gates strong{font:900 1rem ui-monospace,monospace}.gates small{color:var(--muted)}.gates b{margin-top:auto;color:var(--danger);font:900 .6rem ui-monospace,monospace}.gates .ok b{color:var(--success)}
  .matrix{display:grid;grid-template-columns:repeat(5,1fr);gap:7px}.matrix article{border:1px solid var(--border-strong);border-top:3px solid var(--danger);padding:10px;background:var(--surface-sunken)}.matrix article.positive{border-top-color:var(--success)}.matrix article>div{display:flex;justify-content:space-between;color:var(--dim);font:800 .58rem ui-monospace,monospace}.matrix article>strong{display:block;margin:9px 0;color:var(--danger);font:900 1.15rem ui-monospace,monospace}.matrix article.positive>strong{color:var(--success)}dl{display:grid;gap:4px;margin:0;font-size:.68rem}dl div{display:flex;justify-content:space-between;gap:8px}dt{color:var(--dim)}dd{margin:0}.boundary{display:grid;grid-template-columns:.75fr 1.25fr;gap:18px;border-left:4px solid var(--warn);padding:17px}.boundary ul{margin:0;padding-left:20px}.boundary li{margin-bottom:7px;line-height:1.45}.custody{display:grid;gap:7px;padding:14px}.custody div{display:grid;grid-template-columns:150px 1fr;gap:10px}.custody strong{overflow-wrap:anywhere;font:700 .64rem ui-monospace,monospace}
  @media(max-width:1100px){.gates,.matrix{grid-template-columns:repeat(3,1fr)}}@media(max-width:720px){.verdict,.boundary,.metrics,.gates,.matrix{grid-template-columns:1fr}.custody div{grid-template-columns:1fr}}
</style>
