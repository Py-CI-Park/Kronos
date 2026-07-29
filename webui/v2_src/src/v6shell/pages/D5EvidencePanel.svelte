<script lang="ts">
  import { summarizeDiscoveryArms, type DiscoveryEvidence } from '../discovery/discoveryEvidence';

  let { evidence }: { evidence: DiscoveryEvidence } = $props();
  const aggregates = $derived(summarizeDiscoveryArms(evidence.arms));
  const native = $derived(aggregates.find((row) => row.id.endsWith('/NATIVE')));
  const shuffled = $derived(aggregates.find((row) => row.id.endsWith('/SHUFFLED')));
  const pct = (value: number | undefined) => `${((value ?? 0) * 100).toFixed(0)}%`;
  const ratioTone = (value: number | undefined) => (value ?? 0) >= .9 ? 'pass' : (value ?? 0) > 0 ? 'warn' : 'fail';
</script>

<section class="d5-verdict" class:confirmed={evidence.verdict === 'D5_FULL_TRAIN_COST_CONFIRMED'}>
  <div>
    <p>D5 // FULL TRAIN + COST</p>
    <h2>{evidence.verdict}</h2>
    <span>실제 DQN · 573 TRAIN EPISODES · 10 / 10 model units</span>
  </div>
  <dl>
    <div><dt>Native pass</dt><dd>{pct(evidence.nativePassingSeedFraction)} <small>gate ≥60%</small></dd></div>
    <div><dt>Shuffle pass</dt><dd>{pct(evidence.shuffledPassingSeedFraction)} <small>gate ≥60%</small></dd></div>
    <div><dt>Native delta</dt><dd>{evidence.nativeDeltaVsShuffled?.toFixed(3)} <small>gate ≥0.20</small></dd></div>
    <div><dt>Cost contract</dt><dd>23BP TRAIN / PRIMARY</dd></div>
  </dl>
</section>

<section class="boundary" aria-label="D5 evidence boundaries">
  <article><span>DATA</span><strong>573 TRAIN_ONLY</strong><small>278,097 eligible rows</small></article>
  <article><span>REUSED VALIDATION</span><strong>{evidence.reusedValidation ?? 'NOT_RUN_NO_READ'}</strong><small>D6 별도 승인 전 봉인</small></article>
  <article><span>FRESH OOS</span><strong>{evidence.freshOos}</strong><small>D7 외부 승인 전 봉인</small></article>
  <article><span>CLAIMS</span><strong>RESEARCH ONLY</strong><small>profit / promotion blocked</small></article>
</section>

<section class="panel">
  <header><div><p>CONTROL SEPARATION</p><h2>Native 대 shuffled · 5 seed 평균</h2></div><span>0.90 fit gate</span></header>
  <div class="aggregate-grid">
    <article>
      <span>NATIVE REWARD</span>
      <strong class={ratioTone(native?.meanOracleRewardRatio)}>{native?.meanOracleRewardRatio.toFixed(3)}</strong>
      <small>fit accuracy {pct(native?.meanExactBasketAccuracy)} · {native?.seedCount ?? 0} seeds</small>
    </article>
    <article class="negative">
      <span>SHUFFLED REWARD CONTROL</span>
      <strong class={ratioTone(shuffled?.meanOracleRewardRatio)}>{shuffled?.meanOracleRewardRatio.toFixed(3)}</strong>
      <small>native replay · {shuffled?.seedCount ?? 0} seeds</small>
    </article>
  </div>
</section>

<section class="panel">
  <header><div><p>EXACT MATRIX</p><h2>DQN · reward × seed 상세 증거</h2></div><span>{evidence.arms.length} artifacts</span></header>
  <div class="matrix">
    {#each evidence.arms as row}
      <article class:negative={row.shuffledReward}>
        <div class="identity"><span>{row.shuffledReward ? 'SHUFFLED' : 'NATIVE'}</span><b>SEED {row.seed}</b></div>
        <strong class={ratioTone(row.fitRewardRatio)}>{row.fitRewardRatio?.toFixed(3)}</strong>
        <dl>
          <div><dt>Fit 23bp</dt><dd>{row.fitRewardRatio?.toFixed(3)}</dd></div>
          <div><dt>Native 23bp</dt><dd>{row.oracleRewardRatio.toFixed(3)}</dd></div>
          <div><dt>Native 0bp</dt><dd>{row.diagnosticCostRewardRatio?.toFixed(3)}</dd></div>
          <div><dt>Accuracy</dt><dd>{pct(row.exactBasketAccuracy)}</dd></div>
          <div><dt>Invalid</dt><dd>{row.invalidActionCount}</dd></div>
          <div><dt>Steps</dt><dd>{row.trainingTimesteps.toLocaleString()}</dd></div>
        </dl>
      </article>
    {/each}
  </div>
</section>

<section class="custody">
  <div><span>RUN</span><strong>{evidence.runName}</strong></div>
  <div><span>PREREG SHA</span><strong>{evidence.preregSha256}</strong></div>
  <div><span>ARTIFACT MANIFEST</span><strong>{evidence.evidenceManifest ?? 'HMAC VERIFIED IN PROCESS'}</strong></div>
  <p>D5는 종가 매매 DQN의 TRAIN_ONLY 비용 포함 학습 확인 단계입니다. 이 화면은 수익성, 재사용 검증, Fresh OOS, 실거래 준비를 주장하지 않습니다.</p>
</section>

<style>
  .d5-verdict,.panel,.custody{border:1px solid var(--border);background:var(--surface-raised)}
  .d5-verdict{display:grid;grid-template-columns:1.1fr 1.9fr;gap:20px;border-left:5px solid var(--warn);padding:18px;background:linear-gradient(110deg,color-mix(in srgb,var(--warn) 10%,transparent),var(--surface-raised) 46%)}
  .d5-verdict.confirmed{border-left-color:var(--success);background:linear-gradient(110deg,color-mix(in srgb,var(--success) 10%,transparent),var(--surface-raised) 46%)}
  p{margin:0;color:var(--accent);font:800 .65rem ui-monospace,monospace;letter-spacing:.12em}h2{margin:5px 0;color:var(--fg-strong);font-size:1.15rem}.d5-verdict span,.panel header>span{color:var(--muted)}
  dl{display:grid;gap:7px;margin:0}.d5-verdict dl{grid-template-columns:repeat(2,1fr)}dl div{display:flex;justify-content:space-between;gap:8px}dt{color:var(--dim)}dd{margin:0;text-align:right}dd small{display:block;color:var(--muted)}
  .boundary{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--border-strong);background:var(--surface-sunken)}.boundary article{display:flex;flex-direction:column;gap:5px;border-right:1px solid var(--border);padding:12px}.boundary article:last-child{border:0}.boundary span{color:var(--dim);font:800 .58rem ui-monospace,monospace}.boundary strong{color:var(--warn);font:800 .7rem ui-monospace,monospace}.boundary small{color:var(--muted)}
  .panel{padding:17px}.panel header{display:flex;justify-content:space-between;align-items:end;margin-bottom:12px}.aggregate-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.aggregate-grid article{display:flex;flex-direction:column;gap:7px;border:1px solid var(--border-strong);border-left:4px solid var(--success);padding:14px;background:var(--surface-sunken)}.aggregate-grid article.negative{border-left-color:var(--info)}.aggregate-grid strong{font:900 1.8rem ui-monospace,monospace}.aggregate-grid small{color:var(--muted)}
  .matrix{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}.matrix article{border:1px solid var(--border-strong);border-top:3px solid var(--success);padding:11px;background:var(--surface-sunken)}.matrix article.negative{border-top-color:var(--info)}.identity{display:flex;justify-content:space-between;color:var(--dim);font:800 .62rem ui-monospace,monospace}.matrix>article>strong{display:block;margin:9px 0;font:900 1.3rem ui-monospace,monospace}.matrix dl{font-size:.68rem}
  .custody{display:grid;gap:7px;padding:14px}.custody div{display:grid;grid-template-columns:150px 1fr;gap:10px}.custody span{color:var(--dim);font:800 .6rem ui-monospace,monospace}.custody strong{overflow-wrap:anywhere;font:700 .65rem ui-monospace,monospace}.custody p{margin-top:5px;color:var(--muted);font:inherit;line-height:1.5;letter-spacing:0}
  .pass{color:var(--success)}.warn{color:var(--warn)}.fail{color:var(--danger)}
  @media(max-width:1050px){.matrix{grid-template-columns:repeat(2,1fr)}.boundary{grid-template-columns:repeat(2,1fr)}}
  @media(max-width:650px){.d5-verdict,.aggregate-grid{grid-template-columns:1fr}.d5-verdict dl{grid-template-columns:1fr}.matrix,.boundary{grid-template-columns:1fr}.custody div{grid-template-columns:1fr}}
</style>
