<script lang="ts">
  import { onMount } from 'svelte';
  import { rlApi, type RlRunDetail } from '$lib/rlApi';
  import { parseDiscoveryEvidence, type DiscoveryEvidence } from '../discovery/discoveryEvidence';

  const LADDER = [
    ['D0', 'PPO 귀속성', '실행 완료'], ['D1', '역사 1 episode 암기', '대기'],
    ['D2', '8→32→128 확장', '대기'], ['D3', 'reward/action ablation', '대기'],
    ['D4', '0→46bp 비용 사다리', '대기'], ['D5', '전체 train + control', '대기'],
    ['D6', 'reused validation', '잠금'],
  ] as const;
  const ARM_LABELS: Readonly<Record<string, string>> = {
    A_PPO_ONLY: 'A · PPO only', B_BC_THEN_PPO: 'B · BC → PPO',
    C_BC_ONLY: 'C · BC only', D_SHUFFLED_REWARD_PPO: 'D · shuffled PPO',
  };
  let evidence = $state<DiscoveryEvidence | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  const pct = (value: number) => `${(value * 100).toFixed(1)}%`;
  const ratioWidth = (value: number) => `${Math.max(0, Math.min(100, value * 100))}%`;
  const outcomeClass = (value: number) => value >= .9 ? 'pass' : value > 0 ? 'warn' : 'fail';
  const armLabel = (id: string) => ARM_LABELS[id] ?? id;

  async function load(): Promise<void> {
    loading = true;
    error = null;
    const runs = await rlApi.rlRuns(100);
    const record = runs?.runs.find((run) => run.summary?.research_lane === 'rl_discovery');
    if (!record) { loading = false; return; }
    const detail = await rlApi.rlRun(record.name);
    evidence = detail ? parseDiscoveryEvidence(detail as RlRunDetail) : null;
    if (!evidence) error = 'Discovery 아티팩트 계약을 읽을 수 없습니다.';
    loading = false;
  }
  onMount(() => { void load(); });
</script>

<section class="discovery-page" aria-labelledby="discovery-title">
  <header class="hero">
    <div><p class="eyebrow">RL DISCOVERY LAB // ATTRIBUTION</p><h1 id="discovery-title">강화학습 발견 실험실</h1><p>수익성보다 먼저 “PPO가 reward로 실제 학습하는가”를 분해합니다.</p></div>
    <button type="button" onclick={load} disabled={loading}>증거 새로고침</button>
  </header>

  <section class="safety" aria-label="연구 안전 상태">
    <article><span>TYPE1</span><strong>COMPLETE / NO_GO</strong><small>기존 판정 보존</small></article>
    <article><span>FRESH OOS</span><strong>NOT_RUN / NO_READ</strong><small>봉인 유지</small></article>
    <article><span>PROMOTION</span><strong>BLOCKED</strong><small>smoke 승격 금지</small></article>
    <article><span>CLAIMS</span><strong>RESEARCH ONLY</strong><small>수익성·실거래 아님</small></article>
  </section>

  <section class="ladder" aria-labelledby="ladder-title"><div class="section-title"><p>PROGRAM MAP</p><h2 id="ladder-title">Discovery 사다리</h2></div><ol>{#each LADDER as stage, index}<li class:active={index === 0} class:locked={stage[2] === '잠금'}><span>{stage[0]}</span><strong>{stage[1]}</strong><small>{stage[2]}</small></li>{/each}</ol></section>

  {#if loading}<section class="state" aria-live="polite">실험 레지스트리에서 최신 증거를 읽는 중입니다.</section>
  {:else if error}<section class="state error" role="alert"><strong>아티팩트 오류</strong><p>{error}</p></section>
  {:else if !evidence}<section class="state"><strong>아직 Discovery 실행이 없습니다.</strong><p>Type2-D0 smoke 실행 후 네 arm의 귀속성 결과가 표시됩니다.</p></section>
  {:else}
    {@const ppo = evidence.arms.find((arm) => arm.id === 'A_PPO_ONLY')}
    {@const bcPpo = evidence.arms.find((arm) => arm.id === 'B_BC_THEN_PPO')}
    {@const bcOnly = evidence.arms.find((arm) => arm.id === 'C_BC_ONLY')}
    {@const shuffled = evidence.arms.find((arm) => arm.id === 'D_SHUFFLED_REWARD_PPO')}
    <section class="verdict-grid">
      <article class="verdict-card"><p>TERMINAL VERDICT</p><strong>{evidence.verdict}</strong><span>{evidence.status} · {evidence.profile}</span></article>
      <article class="receipt"><dl><div><dt>Run</dt><dd>{evidence.runName}</dd></div><div><dt>Prereg SHA</dt><dd>{evidence.preregSha256.slice(0, 16)}…</dd></div><div><dt>Fresh OOS</dt><dd>{evidence.freshOos}</dd></div></dl></article>
    </section>

    <section class="arms" aria-labelledby="arms-title"><div class="section-title"><p>CONTROL MATRIX</p><h2 id="arms-title">D0 arm 비교</h2></div><div class="arm-grid">{#each evidence.arms as arm}<article><div class="arm-head"><span>{armLabel(arm.id)}</span><strong class={outcomeClass(arm.oracleRewardRatio)}>{arm.oracleRewardRatio.toFixed(3)}×</strong></div><div class="meter" aria-label={`${arm.id} oracle reward ratio`}><i style:width={ratioWidth(arm.oracleRewardRatio)}></i></div><dl><div><dt>Oracle reward</dt><dd>{arm.oracleRewardRatio.toFixed(3)}×</dd></div><div><dt>Basket accuracy</dt><dd>{pct(arm.exactBasketAccuracy)}</dd></div><div><dt>Dominant action</dt><dd class:danger={arm.dominantActionRate >= .95}>{pct(arm.dominantActionRate)}</dd></div><div><dt>Train steps</dt><dd>{arm.trainingTimesteps.toLocaleString()}</dd></div></dl><p class="validity">invalid {arm.invalidActionCount} · block {arm.blockCount} · no-fill {arm.noFillCount}</p>{#if arm.shuffledReward}<span class="control">NEGATIVE CONTROL</span>{/if}</article>{/each}</div></section>

    <section class="interpretation"><div><p>SMOKE READOUT</p><h2>현재 결과의 의미</h2></div><ul><li>PPO-only <b>{ppo?.oracleRewardRatio.toFixed(3) ?? 'MISSING'}×</b>, shuffled PPO <b>{shuffled?.oracleRewardRatio.toFixed(3) ?? 'MISSING'}×</b>로 현재 budget의 reward 학습 분리를 확인합니다.</li><li>BC→PPO <b>{bcPpo?.oracleRewardRatio.toFixed(3) ?? 'MISSING'}×</b>, BC-only <b>{bcOnly?.oracleRewardRatio.toFixed(3) ?? 'MISSING'}×</b>이며 95% 이상 행동 집중은 붕괴 신호로 표시됩니다.</li><li>각 arm의 invalid/block/no-fill 수치를 함께 노출해 환경·마스크·정산 배선을 확인합니다.</li><li>이 결과는 실행 가능성 확인이며 Primary 104k×3 seed 판정을 대신하지 않습니다.</li></ul></section>
  {/if}
</section>

<style>
  .discovery-page{display:flex;flex-direction:column;gap:18px;width:100%;color:var(--fg)}.hero{display:flex;justify-content:space-between;align-items:end;gap:20px;border-bottom:1px solid var(--border-strong);padding-bottom:18px}.eyebrow,.section-title p,.verdict-card p,.interpretation>div p{margin:0;color:var(--accent);font:800 .7rem/1.2 ui-monospace,monospace;letter-spacing:.12em}.hero h1{margin:7px 0 4px;color:var(--fg-strong);font-size:clamp(1.8rem,5vw,3rem)}.hero p:last-child{margin:0;color:var(--muted)}button{border:1px solid var(--accent);border-radius:5px;padding:9px 13px;background:var(--accent-soft);color:var(--accent-strong);font:700 .82rem ui-monospace,monospace;cursor:pointer}button:focus-visible{outline:2px solid var(--accent);outline-offset:3px}.safety{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--border-strong);background:var(--surface-sunken)}.safety article{display:flex;min-width:0;flex-direction:column;gap:5px;border-right:1px solid var(--border);padding:13px}.safety article:last-child{border:0}.safety span,.safety small{color:var(--muted);font:700 .65rem ui-monospace,monospace;letter-spacing:.08em}.safety strong{color:var(--warn);font:800 .83rem ui-monospace,monospace;overflow-wrap:anywhere}.ladder,.arms,.interpretation,.state,.verdict-card,.receipt{border:1px solid var(--border);background:var(--surface-raised)}.ladder,.arms,.interpretation,.state{padding:18px}.section-title h2,.interpretation h2{margin:4px 0 14px;color:var(--fg-strong);font-size:1.15rem}.ladder ol{display:grid;grid-template-columns:repeat(7,1fr);gap:7px;margin:0;padding:0;list-style:none}.ladder li{display:flex;min-height:92px;flex-direction:column;gap:5px;border:1px solid var(--border);padding:10px;background:var(--surface-sunken)}.ladder li.active{border-color:var(--accent);box-shadow:inset 3px 0 var(--accent)}.ladder li.locked{opacity:.55}.ladder span{color:var(--accent);font:800 .74rem ui-monospace,monospace}.ladder strong{font-size:.76rem}.ladder small{margin-top:auto;color:var(--muted)}.verdict-grid{display:grid;grid-template-columns:1.1fr 1.9fr;gap:12px}.verdict-card,.receipt{padding:18px}.verdict-card{border-left:4px solid var(--warn)}.verdict-card strong{display:block;margin:7px 0;color:var(--warn);font:800 clamp(1rem,3vw,1.5rem) ui-monospace,monospace}.verdict-card span{color:var(--muted);font-size:.8rem}.receipt dl,.arms dl{margin:0}.receipt dl{display:grid;gap:9px}.receipt dl div,.arms dl div{display:flex;justify-content:space-between;gap:12px}.receipt dt,.arms dt{color:var(--muted)}.receipt dd,.arms dd{margin:0;text-align:right;overflow-wrap:anywhere}.arm-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.arm-grid article{position:relative;min-width:0;border:1px solid var(--border-strong);padding:14px;background:var(--surface-sunken)}.arm-head{display:flex;justify-content:space-between;gap:8px;font:800 .78rem ui-monospace,monospace}.pass{color:var(--success)}.warn{color:var(--warn)}.fail{color:var(--danger)}.meter{height:7px;margin:12px 0 15px;background:var(--border)}.meter i{display:block;height:100%;background:var(--accent)}.arms dl{display:grid;gap:8px;font-size:.78rem}.danger{color:var(--danger)}.validity{border-top:1px solid var(--border);margin:12px 0 0;padding-top:9px;color:var(--muted);font:700 .68rem ui-monospace,monospace}.control{display:inline-block;margin-top:9px;border:1px solid var(--info);padding:3px 6px;color:var(--info);font:800 .63rem ui-monospace,monospace}.interpretation{display:grid;grid-template-columns:minmax(180px,.6fr) 1.4fr;gap:20px}.interpretation ul{margin:0;padding-left:20px}.interpretation li{margin:0 0 9px;line-height:1.55}.state{text-align:center;color:var(--muted)}.state.error{border-color:var(--danger);color:var(--danger)}
  @media(max-width:1000px){.safety,.arm-grid{grid-template-columns:repeat(2,1fr)}.ladder ol{grid-template-columns:repeat(4,1fr)}.safety article:nth-child(2){border-right:0}}
  @media(max-width:620px){.hero{align-items:start;flex-direction:column}.safety,.arm-grid,.verdict-grid,.interpretation{grid-template-columns:1fr}.ladder ol{display:flex;overflow-x:auto;scroll-snap-type:x mandatory}.ladder li{min-width:150px;scroll-snap-align:start}.safety article{border-right:0;border-bottom:1px solid var(--border)}}
  @media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style>
