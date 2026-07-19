<script lang="ts">
  import { onMount } from 'svelte';
  import { getV6RunDetail, getV6Runs, type V6RunDetail, type V6Runs } from '../v6Api';

  let runsData = $state<V6Runs | null>(null);
  let detail = $state<V6RunDetail | null>(null);
  let selected = $state('');
  let error = $state<string | null>(null);
  let loading = $state(true);
  let detailLoading = $state(false);

  function runKey(dataset: string | undefined, train: string | undefined): string { return `${dataset ?? ''}\u0000${train ?? ''}`; }
  function text(value: unknown): string { return value === undefined || value === null || value === '' ? 'MISSING' : String(value); }
  function number(value: unknown): number | undefined { return typeof value === 'number' && Number.isFinite(value) ? value : undefined; }
  function won(value: unknown): string { const amount = number(value); return amount === undefined ? 'MISSING' : `₩${new Intl.NumberFormat('ko-KR').format(amount)}`; }
  function percent(value: unknown): string { const amount = number(value); return amount === undefined ? 'MISSING' : `${amount.toFixed(2)}%`; }
  function seed0() { return detail?.manifest?.per_seed?.['0'] ?? Object.values(detail?.manifest?.per_seed ?? {})[0]; }
  function policyNav(): number | undefined { return number(seed0()?.final_val_metrics?.nav); }
  function baselineNav(name: string): number | undefined { return number(detail?.manifest?.baselines?.[name]?.nav); }
  function delta(name: string): string { const policy = policyNav(); const baseline = baselineNav(name); return policy === undefined || baseline === undefined ? 'MISSING' : won(policy - baseline); }
  function shuffledNav(): number | undefined { return number(detail?.manifest?.shuffled_label_control?.['0']?.final_val_metrics?.nav); }
  function shuffledDelta(): string { const control = shuffledNav(); const baseline = baselineNav('no_trade'); return control === undefined || baseline === undefined ? 'MISSING' : won(control - baseline); }

  async function load(): Promise<void> { loading = true; error = null; const result = await getV6Runs(); loading = false; if (result.ok && result.data) runsData = result.data; else error = result.error ?? '알 수 없는 오류가 발생했습니다.'; }
  async function selectRun(): Promise<void> { const [dataset, train] = selected.split('\u0000'); if (!dataset || !train) return; detailLoading = true; detail = null; error = null; const result = await getV6RunDetail(dataset, train); detailLoading = false; if (result.ok && result.data) detail = result.data; else error = result.error ?? '알 수 없는 오류가 발생했습니다.'; }
  onMount(load);
</script>

{#if loading}
  <section class="panel" aria-live="polite"><p>비교할 실행 기록을 확인하고 있습니다.</p></section>
{:else if error && !runsData}
  <section class="panel error" aria-live="assertive"><h1>비교 실행 기록을 불러오지 못했습니다</h1><p>{error}</p><button type="button" onclick={load}>다시 시도</button></section>
{:else if runsData}
  <section class="compare-page" aria-labelledby="compare-title">
    <header><p class="eyebrow">RESEARCH COMPARISON</p><h1 id="compare-title">비교</h1><p>같은 실행 manifest의 검증 결과만 비교합니다.</p></header>
    {#if !(runsData.runs?.length)}
      <section class="empty-state"><h2>비교할 실행이 없습니다</h2><p>학습 페이지에서 데이터셋과 학습 실행 기록을 먼저 확인하세요.</p></section>
    {:else}
      <section class="card picker"><h2>실행 선택</h2><div class="run-list">{#each runsData.runs ?? [] as run}<button type="button" class:chosen={selected === runKey(run.dataset_run_id, run.run_id)} onclick={() => { selected = runKey(run.dataset_run_id, run.run_id); selectRun(); }}><span>{text(run.dataset_run_id)} · {text(run.run_id)}</span><span class="chip">{text(run.verdict_candidate?.value)}</span></button>{/each}</div></section>
      {#if detailLoading}<section class="card" aria-live="polite">선택한 실행 manifest를 읽고 있습니다.</section>
      {:else if error}<section class="card error" aria-live="assertive"><p>{error}</p><button type="button" onclick={selectRun}>다시 시도</button></section>
      {:else if detail?.reason}<section class="card error"><h2>실행 상세를 표시할 수 없습니다</h2><p>{detail.reason}</p></section>
      {:else if detail?.manifest}
        <section class="card"><h2>전략 비교</h2><div class="table-wrap"><table><thead><tr><th>지표</th><th>policy seed0</th><th>no_trade</th><th>rule_topk_ret5</th><th>random_topk</th><th>shuffled_control</th><th>KOSPI / KOSDAQ</th></tr></thead><tbody><tr><th>val NAV</th><td>{won(policyNav())}</td><td>{won(baselineNav('no_trade'))}</td><td>{won(baselineNav('rule_topk_ret5'))}</td><td>{won(baselineNav('random_topk'))}</td><td>{won(shuffledNav())}</td><td rowspan="3" class="blocked"><span class="chip">BLOCKED_INDEX_SERIES_SOURCE · KRX 자격증명 필요</span></td></tr><tr><th>return %</th><td>{percent(seed0()?.final_val_metrics?.total_net_return_pct)}</td><td>MISSING</td><td>MISSING</td><td>MISSING</td><td>{percent(detail.manifest.shuffled_label_control?.['0']?.final_val_metrics?.total_net_return_pct)}</td></tr><tr><th>vs no_trade delta</th><td>{delta('no_trade')}</td><td>₩0</td><td>{delta('rule_topk_ret5')}</td><td>{delta('random_topk')}</td><td>{shuffledDelta()}</td></tr></tbody></table></div></section>
        <section class="card"><h2>수수료 민감도 · policy seed0</h2><div class="costs">{#each [['0.0000', '0.00%'], ['0.0023', '0.23%'], ['0.0046', '0.46%']] as [key, label]}<article><h3>{label}</h3><p>{won(seed0()?.final_val_metrics?.cost_scenario_navs?.[key])}</p></article>{/each}</div></section>
        <section class="card"><h2>변형 검증</h2><div class="table-wrap"><table><tbody><tr><th>H3 / H5</th><td>NOT_RUN · 변형 검증 대기</td></tr></tbody></table></div></section>
        <footer>이 비교는 연구 검증용이며 수익·실거래 주장이 아닙니다.</footer>
      {/if}
    {/if}
  </section>
{/if}

<style>
  .compare-page, .panel { max-width: 980px; border: 1px solid var(--surface-border, #334155); border-radius: 14px; padding: clamp(18px, 4vw, 32px); background: var(--surface, #111827); color: #e5e7eb; } .eyebrow { margin: 0; color: #7dd3fc; font-size: .72rem; font-weight: 800; letter-spacing: .1em; } h1 { margin: 7px 0; color: #f8fafc; font-size: clamp(1.7rem, 6vw, 2.5rem); } header > p { color: #cbd5e1; } .card, .empty-state { margin-top: 16px; border: 1px solid #475569; border-radius: 10px; padding: 16px; background: #0f172a; } .empty-state { border-color: #a16207; background: #1c1910; } h2 { margin: 0 0 12px; color: #f8fafc; font-size: 1.05rem; } .run-list { display: grid; gap: 7px; } .run-list button { width: 100%; display: flex; justify-content: space-between; gap: 8px; border: 1px solid #475569; border-radius: 6px; padding: 8px; background: #020617; color: #e2e8f0; font: inherit; text-align: left; cursor: pointer; overflow-wrap: anywhere; } .run-list button.chosen { border-color: #38bdf8; } .table-wrap { max-width: 100%; overflow-x: auto; } table { width: 100%; min-width: 720px; border-collapse: collapse; font-size: .78rem; } th, td { border-top: 1px solid #334155; padding: 7px; overflow-wrap: anywhere; text-align: left; vertical-align: top; } th { color: #94a3b8; } .chip { display: inline-block; border: 1px solid #a16207; border-radius: 999px; padding: 2px 6px; color: #fde68a; font-size: .68rem; overflow-wrap: anywhere; } .blocked { min-width: 165px; background: #1c1910; } .costs { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; } article { min-width: 0; border: 1px solid #334155; border-radius: 8px; padding: 12px; } h3, article p { margin: 0; } h3 { color: #94a3b8; font-size: .8rem; } article p { margin-top: 6px; overflow-wrap: anywhere; } footer { margin-top: 18px; color: #fde68a; font-size: .84rem; } .error { border-color: #b91c1c; color: #fecaca; } button { border: 1px solid #7dd3fc; border-radius: 6px; padding: 6px 10px; background: transparent; color: #e0f2fe; font: inherit; cursor: pointer; } @media (max-width: 500px) { .costs { grid-template-columns: 1fr; } }
</style>
