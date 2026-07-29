<script lang="ts">
  import { onMount } from 'svelte';
  import { rlApi } from '$lib/rlApi';
  import { parseDiscoveryEvidence, summarizeDiscoveryArms, type DiscoveryEvidence } from '../discovery/discoveryEvidence';
  import D5EvidencePanel from './D5EvidencePanel.svelte';

  const LADDER = [
    ['D0', 'PPO attribution', 'NO-GO closed'], ['D1', 'action / reward', 'train-only confirmed'],
    ['D2', 'historical scale', 'partial capacity'], ['D3', 'representation / action', 'NO-GO closed'],
    ['D4', 'algorithm / objective', 'train-only confirmed'], ['D5', 'full train + cost', 'next'],
    ['D6', 'reused validation', 'locked'], ['D7', 'Fresh OOS', 'external approval'],
  ] as const;
  const LABELS: Readonly<Record<string, string>> = {
    'D5-C_DQN_DISCRETE/NATIVE': 'D5 · DQN · native · 23bp trained',
    'D5-C_DQN_DISCRETE/SHUFFLED': 'D5 · DQN · shuffled control · 23bp trained',
    'D4-A_SUPERVISED_CEILING/NATIVE': 'A · supervised ceiling · native (NOT RL)',
    'D4-A_SUPERVISED_CEILING/SHUFFLED': 'A · supervised ceiling · shuffled (NOT RL)',
    'D4-B_PPO_BASELINE/NATIVE': 'B · MaskablePPO · native',
    'D4-B_PPO_BASELINE/SHUFFLED': 'B · MaskablePPO · shuffled',
    'D4-C_DQN_DISCRETE/NATIVE': 'C · DQN · native',
    'D4-C_DQN_DISCRETE/SHUFFLED': 'C · DQN · shuffled',
    'D4-D_AUXILIARY_PPO/NATIVE': 'D · auxiliary PPO · native',
    'D4-D_AUXILIARY_PPO/SHUFFLED': 'D · auxiliary PPO · shuffled',
  };
  let evidence = $state<DiscoveryEvidence | null>(null);
  let loading = $state(true);
  let notice = $state<string | null>(null);
  const isD5 = $derived(evidence?.verdict.startsWith('D5_FULL_TRAIN_COST_') === true);
  const pct = (value: number) => `${(value * 100).toFixed(1)}%`;
  const cls = (value: number) => value >= .9 ? 'pass' : value > 0 ? 'warn' : 'fail';

  async function load(): Promise<void> {
    loading = true; notice = null;
    try {
      const runs = await rlApi.rlRuns(100);
      const record = runs?.runs.find((run) => String(run.summary?.verdict ?? '').startsWith('D5_FULL_TRAIN_COST_'))
        ?? runs?.runs.find((run) => run.summary?.verdict === 'D4_ALGORITHM_OBJECTIVE_CONFIRMED');
      if (!record) { evidence = null; notice = '검증 가능한 D5/D4 evidence가 없습니다. BLOCK 상태입니다.'; return; }
      const detail = await rlApi.rlRun(record.name);
      evidence = detail ? parseDiscoveryEvidence(detail) : null;
      if (!detail || !evidence) notice = 'D5/D4 evidence 검증에 실패했습니다. BLOCK 상태입니다.';
    } catch {
      evidence = null;
      notice = 'Discovery API 연결에 실패했습니다. EVIDENCE_UNAVAILABLE / BLOCK.';
    } finally { loading = false; }
  }
  onMount(() => { void load(); });
</script>

<section class="page" aria-labelledby="discovery-title">
  <header class="hero"><div><p>RL DISCOVERY LAB // D5 + D4 EVIDENCE</p><h1 id="discovery-title">강화학습 발견 실험실</h1><span>알고리즘과 목적함수의 학습 가능성을 실제 모델·seed·negative control로 분리합니다.</span></div><button type="button" onclick={load} disabled={loading}>증거 새로고침</button></header>
  <section class="safety" aria-label="연구 안전 상태"><article><span>TRAIN</span><strong>{isD5 ? '573 EPISODES' : '128 EPISODES'}</strong></article><article><span>FRESH OOS</span><strong>NOT_RUN_NO_READ</strong></article><article><span>PROMOTION</span><strong>BLOCKED</strong></article><article><span>CLAIMS</span><strong>RESEARCH ONLY</strong></article><article><span>COST</span><strong>{isD5 ? '23BP TRAIN / 0BP DIAG' : '0BP TRAIN / 23BP DIAG'}</strong></article></section>
  {#if notice}<div class="notice">{notice}</div>{/if}
  <section class="panel"><div class="title"><p>PROGRAM MAP</p><h2>D0–D7 연구 사다리</h2></div><ol class="ladder">{#each LADDER as stage, index}<li class:active={index === (isD5 ? 5 : 4)} class:next={!isD5 && index === 5} class:locked={index >= 6}><b>{stage[0]}</b><strong>{stage[1]}</strong><small>{index === 5 && isD5 ? 'NOT_CONFIRMED' : stage[2]}</small></li>{/each}</ol></section>

  {#if loading}<div class="notice">최신 D5/D4 Primary 증거를 확인하는 중입니다.</div>
  {:else if evidence?.verdict.startsWith('D5_FULL_TRAIN_COST_')}
    <D5EvidencePanel {evidence} />
  {:else if evidence}
    {@const aggregates = summarizeDiscoveryArms(evidence.arms)}
    {@const dqnNative = aggregates.find((row) => row.id === 'D4-C_DQN_DISCRETE/NATIVE')}
    <section class="verdict"><article><p>REVIEWED VERDICT</p><strong>{evidence.verdict}</strong><span>{evidence.arms.length}/24 units · Fresh OOS {evidence.freshOos}</span></article><dl><div><dt>Run</dt><dd>{evidence.runName}</dd></div><div><dt>Best RL arm</dt><dd>{evidence.bestRlArm}</dd></div><div><dt>RL → supervised gap</dt><dd>{evidence.bestRlGapToSupervisedCeiling?.toFixed(3)}</dd></div><div><dt>Confirmed RL arms</dt><dd>{evidence.confirmedRlArmCount} / 3</dd></div><div><dt>Custody</dt><dd>{evidence.evidenceManifest?.slice(0, 16)}…</dd></div><div><dt>Prereg</dt><dd>{evidence.preregSha256.slice(0, 16)}…</dd></div></dl></section>
    <section class="panel"><div class="title"><p>ARTIFACT AGGREGATES</p><h2>D4 algorithm / objective 평균</h2></div><div class="grid">{#each aggregates as row}<article><span>{LABELS[row.id] ?? row.id}</span><strong class={cls(row.meanOracleRewardRatio)}>{row.meanOracleRewardRatio.toFixed(3)}×</strong><small>{row.seedCount} seeds · fit accuracy {pct(row.meanExactBasketAccuracy)}</small></article>{/each}</div></section>
    <section class="panel"><div class="title"><p>CONTROL MATRIX</p><h2>D4 algorithm / objective · arm × seed 상세</h2></div><div class="arms">{#each evidence.arms as row}<article><header><span>{LABELS[row.id] ?? row.id}</span><b class={cls(row.oracleRewardRatio)}>{row.oracleRewardRatio.toFixed(3)}×</b></header><dl><div><dt>Seed</dt><dd>{row.seed}</dd></div><div><dt>Fit reward</dt><dd>{row.fitRewardRatio?.toFixed(3)}</dd></div><div><dt>Native reward</dt><dd>{row.oracleRewardRatio.toFixed(3)}</dd></div><div><dt>23bp diagnostic</dt><dd>{row.diagnosticCostRewardRatio?.toFixed(3)}</dd></div><div><dt>Fit accuracy</dt><dd>{pct(row.exactBasketAccuracy)}</dd></div><div><dt>Steps / epochs</dt><dd>{row.trainingTimesteps.toLocaleString()}</dd></div></dl>{#if row.shuffledReward}<em>NEGATIVE CONTROL</em>{/if}</article>{/each}</div></section>
    <section class="interpretation"><div><p>PRIMARY RECEIPT</p><h2>검증된 evidence 해석</h2></div><ul><li>Best RL arm은 <b>{evidence.bestRlArm}</b>이며 native 평균 reward ratio는 <b>{dqnNative?.meanOracleRewardRatio.toFixed(3) ?? 'NOT_RECORDED'}</b>, fit accuracy는 <b>{dqnNative ? pct(dqnNative.meanExactBasketAccuracy) : 'NOT_RECORDED'}</b>입니다.</li><li>supervised ceiling은 <b>강화학습이 아니며</b>, 최선 RL과의 격차는 {evidence.bestRlGapToSupervisedCeiling?.toFixed(3) ?? 'NOT_RECORDED'}입니다.</li><li>확인된 RL arm은 {evidence.confirmedRlArmCount ?? 0}/3입니다. 원인 해석은 artifact 지표와 별도 연구 문서를 함께 확인해야 합니다.</li><li>Promotion <b>{evidence.promotionAllowed ? 'ALLOWED' : 'BLOCKED'}</b>, profitability claim <b>{evidence.profitabilityClaimAllowed ? 'ALLOWED' : 'BLOCKED'}</b>. 다음 D5도 사전등록 전에는 실행하지 않습니다.</li></ul></section>
  {:else}
    <section class="notice"><strong>EVIDENCE_UNAVAILABLE / BLOCK</strong><p>HMAC 또는 커밋된 custody와 24-unit matrix 검증을 통과한 D4 Primary만 표시합니다.</p></section>
  {/if}
</section>

<style>
  .page{display:flex;flex-direction:column;gap:16px;color:var(--fg)}.hero{display:flex;justify-content:space-between;align-items:end;border-bottom:1px solid var(--border-strong);padding-bottom:18px;gap:18px}.hero p,.title p,.verdict p,.interpretation p{margin:0;color:var(--accent);font:800 .68rem ui-monospace,monospace;letter-spacing:.12em}.hero h1{margin:6px 0 3px;font-size:clamp(1.8rem,5vw,3rem);color:var(--fg-strong)}.hero span{color:var(--muted)}button{border:1px solid var(--accent);border-radius:4px;padding:9px 13px;background:var(--accent-soft);color:var(--accent-strong);font-weight:800}.safety{display:grid;grid-template-columns:repeat(5,1fr);border:1px solid var(--border-strong);background:var(--surface-sunken)}.safety article{display:flex;flex-direction:column;gap:5px;border-right:1px solid var(--border);padding:12px}.safety article:last-child{border:0}.safety span{color:var(--dim);font:700 .62rem ui-monospace,monospace}.safety strong{color:var(--warn);font:800 .76rem ui-monospace,monospace}.panel,.notice,.verdict,.interpretation{border:1px solid var(--border);padding:17px;background:var(--surface-raised)}.title h2,.interpretation h2{margin:4px 0 13px;font-size:1.1rem}.ladder{display:grid;grid-template-columns:repeat(8,1fr);gap:7px;margin:0;padding:0;list-style:none}.ladder li{display:flex;min-height:82px;flex-direction:column;gap:5px;border:1px solid var(--border);padding:9px;background:var(--surface-sunken)}.ladder b{color:var(--accent)}.ladder small{margin-top:auto;color:var(--muted)}.ladder .active{border-color:var(--success);box-shadow:inset 3px 0 var(--success)}.ladder .next{border-color:var(--accent);box-shadow:inset 3px 0 var(--accent)}.locked{opacity:.55}.verdict{display:grid;grid-template-columns:1fr 2fr;gap:18px;border-left:4px solid var(--success)}.verdict>article>strong{display:block;margin:8px 0;color:var(--success);font:900 1.25rem ui-monospace,monospace}.verdict span,.notice{color:var(--muted)}dl{display:grid;gap:7px;margin:0}dl div{display:flex;justify-content:space-between;gap:10px}dt{color:var(--dim)}dd{margin:0;text-align:right;overflow-wrap:anywhere}.grid,.arms{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}.grid article,.arms article{border:1px solid var(--border-strong);padding:12px;background:var(--surface-sunken)}.grid article{display:flex;flex-direction:column;gap:7px;border-left:3px solid var(--accent)}.grid strong{font:900 1.25rem ui-monospace,monospace}.grid small{color:var(--muted)}.arms header{display:flex;justify-content:space-between;gap:8px;margin-bottom:12px;font:800 .7rem ui-monospace,monospace}.arms dl{font-size:.75rem}.arms em{display:inline-block;margin-top:10px;border:1px solid var(--info);padding:3px 5px;color:var(--info);font:800 .6rem ui-monospace,monospace;font-style:normal}.pass{color:var(--success)}.warn{color:var(--warn)}.fail{color:var(--danger)}.interpretation{display:grid;grid-template-columns:.55fr 1.45fr;gap:20px}.interpretation ul{margin:0;padding-left:20px}.interpretation li{margin-bottom:8px;line-height:1.5}@media(max-width:1050px){.safety,.grid,.arms{grid-template-columns:repeat(2,1fr)}.ladder{grid-template-columns:repeat(4,1fr)}}@media(max-width:650px){.hero{align-items:start;flex-direction:column}.safety,.grid,.arms,.verdict,.interpretation{grid-template-columns:1fr}.ladder{display:flex;overflow:auto}.ladder li{min-width:150px}}
</style>
