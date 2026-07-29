<script lang="ts">
  import { onMount } from 'svelte';
  import { rlApi } from '$lib/rlApi';
  import {
    parseDiscoveryEvidence,
    summarizeDiscoveryArms,
    type DiscoveryEvidence,
  } from '../discovery/discoveryEvidence';
  import { REVIEWED_DISCOVERY_SNAPSHOT } from '../discovery/reviewedDiscoverySnapshot';

  const LADDER = [
    ['D0', 'PPO attribution', 'NO-GO closed'],
    ['D1', 'action / reward', 'train-only confirmed'],
    ['D2', 'historical scale', 'partial capacity confirmed'],
    ['D3', 'representation / action', '24 models · NO-GO'],
    ['D4', 'algorithm / objective', 'decision next'],
    ['D5', 'full train + control', 'waiting'],
    ['D6', 'reused validation', 'locked'],
    ['D7', 'Fresh OOS', 'external approval'],
  ] as const;
  const ARM_LABELS: Readonly<Record<string, string>> = {
    A_PPO_ONLY: 'A · PPO only',
    B_BC_THEN_PPO: 'B · BC → PPO',
    C_BC_ONLY: 'C · BC only',
    D_SHUFFLED_REWARD_PPO: 'D · shuffled PPO',
    A_BINARY_NATIVE: 'A · binary native',
    B_BINARY_DIAGNOSTIC: 'B · binary diagnostic',
    C_BINARY_SHUFFLED: 'C · binary shuffled',
    'D3-A_TOP1_CONTEXT_1X/NATIVE': 'A · top-1 context · native',
    'D3-A_TOP1_CONTEXT_1X/SHUFFLED': 'A · top-1 context · shuffled',
    'D3-B_TOP5_PLAIN_1X/NATIVE': 'B · top-5 plain · native',
    'D3-B_TOP5_PLAIN_1X/SHUFFLED': 'B · top-5 plain · shuffled',
    'D3-C_TOP5_CONTEXT_1X/NATIVE': 'C · top-5 context · native',
    'D3-C_TOP5_CONTEXT_1X/SHUFFLED': 'C · top-5 context · shuffled',
    'D3-D_TOP5_CONTEXT_4X/NATIVE': 'D · top-5 context 4× · native',
    'D3-D_TOP5_CONTEXT_4X/SHUFFLED': 'D · top-5 context 4× · shuffled',
  };

  let evidence = $state<DiscoveryEvidence | null>(REVIEWED_DISCOVERY_SNAPSHOT);
  let loading = $state(true);
  let notice = $state<string | null>(null);

  const pct = (value: number) => `${(value * 100).toFixed(1)}%`;
  const ratioWidth = (value: number) => `${Math.max(0, Math.min(100, value * 100))}%`;
  const outcomeClass = (value: number) => value >= .9 ? 'pass' : value > 0 ? 'warn' : 'fail';
  const armLabel = (id: string) => ARM_LABELS[id] ?? id;
  const phaseLabel = (value: DiscoveryEvidence) => value.verdict.startsWith('D3_')
    ? 'D3 representation / action'
    : value.verdict.startsWith('D2_')
    ? 'D2 historical scale'
    : value.arms.some((arm) => arm.id.startsWith('A_BINARY')) ? 'D1 action / reward' : 'D0 attribution';

  async function load(): Promise<void> {
    loading = true;
    notice = null;
    try {
      const runs = await rlApi.rlRuns(100);
      const discoveryRuns = runs?.runs.filter((run) => run.summary?.research_lane === 'rl_discovery') ?? [];
      const record = discoveryRuns.find((run) => run.name === REVIEWED_DISCOVERY_SNAPSHOT.runName);
      if (!record) {
        evidence = REVIEWED_DISCOVERY_SNAPSHOT;
        notice = '검토·보관된 Primary snapshot을 표시합니다.';
        return;
      }
      const detail = await rlApi.rlRun(record.name);
      evidence = detail ? parseDiscoveryEvidence(detail) : REVIEWED_DISCOVERY_SNAPSHOT;
      if (!detail || !evidence) notice = '로컬 artifact를 읽지 못해 검토된 snapshot을 표시합니다.';
    } catch {
      evidence = REVIEWED_DISCOVERY_SNAPSHOT;
      notice = 'Discovery API에 연결할 수 없어 검토된 snapshot을 표시합니다.';
    } finally {
      loading = false;
    }
  }

  onMount(() => { void load(); });
</script>

<section class="discovery-page" aria-labelledby="discovery-title">
  <header class="hero">
    <div>
      <p class="eyebrow">RL DISCOVERY LAB // EVIDENCE CONSOLE</p>
      <h1 id="discovery-title">강화학습 발견 실험실</h1>
      <p>정책이 보상 신호를 학습했는지 arm과 seed 단위로 분해하고, 실패와 안전 경계를 함께 공개합니다.</p>
    </div>
    <button type="button" onclick={load} disabled={loading}>증거 새로고침</button>
  </header>

  <section class="safety" aria-label="연구 안전 상태">
    <article><span>TYPE1</span><strong>COMPLETE / NO-GO</strong><small>기존 판정 보존</small></article>
    <article><span>FRESH OOS</span><strong>NOT_RUN / NO_READ</strong><small>봉인 유지</small></article>
    <article><span>PROMOTION</span><strong>BLOCKED</strong><small>train-only 확인은 승격 근거가 아님</small></article>
    <article><span>CLAIMS</span><strong>RESEARCH ONLY</strong><small>수익·실거래 주장 금지</small></article>
    <article><span>TRAIN / DIAGNOSTIC COST</span><strong>{evidence?.primaryRoundTripCostBp ?? 0} / {evidence?.diagnosticRoundTripCostBp ?? 23} BP</strong><small>23bp diagnostic, 승격 게이트 아님</small></article>
  </section>
  {#if notice}<section class="state notice" aria-live="polite">{notice}</section>{/if}

  <section class="ladder" aria-labelledby="ladder-title">
    <div class="section-title"><p>PROGRAM MAP</p><h2 id="ladder-title">Discovery 연구 사다리</h2></div>
    <ol>{#each LADDER as stage, index}<li class:active={index === 3} class:next={index === 4} class:locked={index >= 6}><span>{stage[0]}</span><strong>{stage[1]}</strong><small>{stage[2]}</small></li>{/each}</ol>
  </section>

  {#if loading}
    <section class="state" aria-live="polite">최신 Primary 증거를 확인하는 중입니다.</section>
  {:else if !evidence}
    <section class="state"><strong>아직 Discovery 실행이 없습니다.</strong><p>실행 후 arm·seed 귀속성 결과가 표시됩니다.</p></section>
  {:else}
    {@const aggregates = summarizeDiscoveryArms(evidence.arms)}
    {@const disposition = evidence.verdict === 'D3_REPRESENTATION_ACTION_NOT_CONFIRMED' ? 'NO-GO / RESEARCH-ONLY' : evidence.verdict === 'D2_PARTIAL_CAPACITY_CONFIRMED' ? 'PARTIAL CAPACITY / RESEARCH-ONLY' : evidence.verdict === 'D1_ACTION_REWARD_CONFIRMED' ? 'TRAIN_ONLY_CONFIRMED / RESEARCH-ONLY' : evidence.verdict === 'PPO_ONLY_OVERFIT_NOT_CONFIRMED' ? 'NO-GO' : 'RESEARCH-ONLY'}
    <section class="verdict-grid">
      <article class="verdict-card"><p>{evidence.authority} VERDICT</p><strong>{evidence.verdict}</strong><span>{evidence.status} · {evidence.profile} · {evidence.arms.length}/{evidence.arms.length} units</span></article>
      <article class="receipt"><dl><div><dt>Authority</dt><dd>{evidence.authority}</dd></div><div><dt>Run</dt><dd>{evidence.runName}</dd></div><div><dt>Manifest</dt><dd>{evidence.evidenceManifest?.slice(0, 16) ?? 'LIVE SCAN'}…</dd></div><div><dt>Prereg SHA</dt><dd>{evidence.preregSha256.slice(0, 16)}…</dd></div><div><dt>Train / diagnostic cost</dt><dd>{evidence.primaryRoundTripCostBp} / {evidence.diagnosticRoundTripCostBp ?? 23} bp</dd></div><div><dt>Best policy arm</dt><dd>{evidence.bestPolicyArm || 'N/A'}</dd></div><div><dt>4× budget lift</dt><dd>{evidence.budget4xNativeLift?.toFixed(3) ?? 'N/A'}×</dd></div><div><dt>Confirmed arms</dt><dd>{evidence.confirmedPolicyArmCount ?? 'N/A'} / 4</dd></div><div><dt>Best native − shuffle</dt><dd>{evidence.nativeDeltaVsShuffled?.toFixed(3) ?? 'N/A'}×</dd></div><div><dt>Fresh OOS</dt><dd>{evidence.freshOos}</dd></div></dl></article>
    </section>

    <section class="aggregates" aria-labelledby="aggregate-title">
      <div class="section-title"><p>ARTIFACT AGGREGATES</p><h2 id="aggregate-title">Arm 평균 비교</h2></div>
      <div class="aggregate-grid">{#each aggregates as arm}<article><span>{armLabel(arm.id)}</span><strong class={outcomeClass(arm.meanOracleRewardRatio)}>{arm.meanOracleRewardRatio.toFixed(3)}×</strong><small>{arm.seedCount} seeds · 정확도 {pct(arm.meanExactBasketAccuracy)} · 지배행동 {pct(arm.meanDominantActionRate)}</small></article>{/each}</div>
    </section>

    <section class="arms" aria-labelledby="arms-title">
      <div class="section-title"><p>CONTROL MATRIX</p><h2 id="arms-title">{phaseLabel(evidence)} · arm × seed 상세</h2></div>
      <div class="arm-grid">{#each evidence.arms as arm}<article><div class="arm-head"><span>{armLabel(arm.id)} <b>SEED {arm.seed}</b></span><strong class={outcomeClass(arm.oracleRewardRatio)}>{arm.oracleRewardRatio.toFixed(3)}×</strong></div><div class="meter" aria-label={`${arm.id} seed ${arm.seed} oracle reward ratio`}><i style:width={ratioWidth(arm.oracleRewardRatio)}></i></div><dl>{#if arm.episodeCount !== undefined}<div><dt>Episodes</dt><dd>{arm.episodeCount}</dd></div>{/if}<div><dt>Fit reward</dt><dd>{(arm.fitRewardRatio ?? arm.oracleRewardRatio).toFixed(3)}×</dd></div><div><dt>Native reward</dt><dd>{arm.oracleRewardRatio.toFixed(3)}×</dd></div>{#if arm.diagnosticCostRewardRatio !== undefined}<div><dt>23bp diagnostic</dt><dd>{arm.diagnosticCostRewardRatio.toFixed(3)}×</dd></div>{/if}<div><dt>Fit accuracy</dt><dd>{pct(arm.exactBasketAccuracy)}</dd></div><div><dt>Dominant action</dt><dd class:danger={arm.dominantActionRate >= .95}>{pct(arm.dominantActionRate)}</dd></div><div><dt>Train steps</dt><dd>{arm.trainingTimesteps.toLocaleString()}</dd></div></dl><p class="validity">invalid {arm.invalidActionCount} · block {arm.blockCount} · no-fill {arm.noFillCount}</p>{#if arm.shuffledReward}<span class="control">NEGATIVE CONTROL</span>{/if}</article>{/each}</div>
    </section>

    <section class="interpretation">
      <div><p>PRIMARY RECEIPT</p><h2>Artifact 기반 판정</h2></div>
      <ul><li>화면의 평균과 seed 값은 선택된 artifact에서 계산되며 고정 결론을 덮어쓰지 않습니다.</li><li>Receipt 판정: <b>{evidence.verdict} / {disposition}</b>.</li><li>D3는 top-5 문맥과 4× budget에서 개선을 확인했지만 <b>{evidence.confirmedPolicyArmCount ?? 0}/4 arms</b>만 0.90 게이트를 통과했습니다.</li><li>Promotion <b>{evidence.promotionAllowed ? 'ALLOWED' : 'BLOCKED'}</b>, profitability claim <b>{evidence.profitabilityClaimAllowed ? 'ALLOWED' : 'BLOCKED'}</b>.</li><li>다음 D4는 비용 민감도 확장이 아니라 <b>알고리즘·목적함수 변경 여부</b>를 별도 사전등록하며 Fresh OOS는 열지 않습니다.</li></ul>
    </section>
  {/if}
</section>

<style>
  .discovery-page{display:flex;flex-direction:column;gap:18px;width:100%;color:var(--fg)}.hero{display:flex;justify-content:space-between;align-items:end;gap:20px;border-bottom:1px solid var(--border-strong);padding-bottom:18px}.eyebrow,.section-title p,.verdict-card p,.interpretation>div p{margin:0;color:var(--accent);font:800 .7rem/1.2 ui-monospace,monospace;letter-spacing:.12em}.hero h1{margin:7px 0 4px;color:var(--fg-strong);font-size:clamp(1.8rem,5vw,3rem)}.hero p:last-child{margin:0;color:var(--muted)}button{border:1px solid var(--accent);border-radius:5px;padding:9px 13px;background:var(--accent-soft);color:var(--accent-strong);font:700 .82rem ui-monospace,monospace;cursor:pointer}.safety{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--border-strong);background:var(--surface-sunken)}.safety article{display:flex;min-width:0;flex-direction:column;gap:5px;border-right:1px solid var(--border);padding:13px}.safety article:last-child{border:0}.safety span,.safety small{color:var(--muted);font:700 .65rem ui-monospace,monospace;letter-spacing:.08em}.safety strong{color:var(--warn);font:800 .83rem ui-monospace,monospace}.ladder,.arms,.aggregates,.interpretation,.state,.verdict-card,.receipt{border:1px solid var(--border);background:var(--surface-raised)}.ladder,.arms,.aggregates,.interpretation,.state{padding:18px}.section-title h2,.interpretation h2{margin:4px 0 14px;color:var(--fg-strong);font-size:1.15rem}.ladder ol{display:grid;grid-template-columns:repeat(7,1fr);gap:7px;margin:0;padding:0;list-style:none}.ladder li{display:flex;min-height:92px;flex-direction:column;gap:5px;border:1px solid var(--border);padding:10px;background:var(--surface-sunken)}.ladder li.active{border-color:var(--success);box-shadow:inset 3px 0 var(--success)}.ladder li.next{border-color:var(--accent);box-shadow:inset 3px 0 var(--accent)}.ladder li.locked{opacity:.55}.ladder span{color:var(--accent);font:800 .74rem ui-monospace,monospace}.ladder strong{font-size:.76rem}.ladder small{margin-top:auto;color:var(--muted)}.verdict-grid{display:grid;grid-template-columns:1.1fr 1.9fr;gap:12px}.verdict-card,.receipt{padding:18px}.verdict-card{border-left:4px solid var(--success)}.verdict-card strong{display:block;margin:7px 0;color:var(--success);font:800 clamp(1rem,3vw,1.5rem) ui-monospace,monospace}.verdict-card span{color:var(--muted);font-size:.8rem}.receipt dl,.arms dl{margin:0}.receipt dl{display:grid;gap:9px}.receipt dl div,.arms dl div{display:flex;justify-content:space-between;gap:12px}.receipt dt,.arms dt{color:var(--muted)}.receipt dd,.arms dd{margin:0;text-align:right;overflow-wrap:anywhere}.aggregate-grid,.arm-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.aggregate-grid article{display:flex;flex-direction:column;gap:7px;border-left:3px solid var(--accent);padding:12px;background:var(--surface-sunken)}.aggregate-grid span,.arm-head{font:800 .72rem ui-monospace,monospace}.aggregate-grid strong{font:800 1.35rem ui-monospace,monospace}.aggregate-grid small{color:var(--muted);line-height:1.45}.arm-grid article{position:relative;min-width:0;border:1px solid var(--border-strong);padding:14px;background:var(--surface-sunken)}.arm-head{display:flex;justify-content:space-between;gap:8px}.arm-head b{color:var(--accent);font-size:.62rem}.pass{color:var(--success)}.warn{color:var(--warn)}.fail{color:var(--danger)}.meter{height:7px;margin:12px 0 15px;background:var(--border)}.meter i{display:block;height:100%;background:var(--accent)}.arms dl{display:grid;gap:8px;font-size:.78rem}.danger{color:var(--danger)}.validity{border-top:1px solid var(--border);margin:12px 0 0;padding-top:9px;color:var(--muted);font:700 .68rem ui-monospace,monospace}.control{display:inline-block;margin-top:9px;border:1px solid var(--info);padding:3px 6px;color:var(--info);font:800 .63rem ui-monospace,monospace}.interpretation{display:grid;grid-template-columns:minmax(180px,.6fr) 1.4fr;gap:20px}.interpretation ul{margin:0;padding-left:20px}.interpretation li{margin:0 0 9px;line-height:1.55}.state{text-align:center;color:var(--muted)}.state.notice{border-color:var(--info);color:var(--info);text-align:left}
  .safety{grid-template-columns:repeat(5,1fr)}.ladder ol{grid-template-columns:repeat(8,1fr)}
  @media(max-width:1000px){.safety,.arm-grid,.aggregate-grid{grid-template-columns:repeat(2,1fr)}.ladder ol{grid-template-columns:repeat(4,1fr)}}
  @media(max-width:620px){.hero{align-items:start;flex-direction:column}.safety,.arm-grid,.aggregate-grid,.verdict-grid,.interpretation{grid-template-columns:1fr}.ladder ol{display:flex;overflow-x:auto}.ladder li{min-width:150px}.safety article{border-right:0;border-bottom:1px solid var(--border)}}
  @media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style>
