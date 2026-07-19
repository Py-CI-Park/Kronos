<script lang="ts">
  import { onMount } from 'svelte';
  import { getV6RunDetail, getV6Runs, type V6RunDetail, type V6Runs, type V6RunSeed } from '../v6Api';

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
  function seeds(): readonly [string, V6RunSeed][] { return Object.entries(detail?.manifest?.per_seed ?? {}); }
  function verdict(): string { return text(detail?.manifest?.verdict_candidate?.value); }
  function verdictClass(): string { return verdict() === 'NO_GO' ? 'no-go' : verdict() === 'GO_CANDIDATE_VALIDATION_ONLY' ? 'candidate' : 'inconclusive'; }
  function eventRows(): readonly { episode?: unknown; val_nav?: unknown }[] { return Array.isArray(detail?.events_tail) ? detail.events_tail.slice(-10) : []; }

  async function load(): Promise<void> {
    loading = true; error = null;
    const result = await getV6Runs();
    loading = false;
    if (result.ok && result.data) runsData = result.data;
    else error = result.error ?? '알 수 없는 오류가 발생했습니다.';
  }

  async function selectRun(): Promise<void> {
    const [dataset, train] = selected.split('\u0000');
    if (!dataset || !train) return;
    detailLoading = true; detail = null; error = null;
    const result = await getV6RunDetail(dataset, train);
    detailLoading = false;
    if (result.ok && result.data) detail = result.data;
    else error = result.error ?? '알 수 없는 오류가 발생했습니다.';
  }

  onMount(load);
</script>

{#if loading}
  <section class="panel" aria-live="polite"><p>평가 실행 기록을 확인하고 있습니다.</p></section>
{:else if error && !runsData}
  <section class="panel error" aria-live="assertive"><h1>평가 실행 기록을 불러오지 못했습니다</h1><p>{error}</p><button type="button" onclick={load}>다시 시도</button></section>
{:else if runsData}
  <section class="evaluation-page" aria-labelledby="evaluation-title">
    <header><p class="eyebrow">EVALUATION EVIDENCE</p><h1 id="evaluation-title">평가</h1><p>표시된 결과는 선택한 실행의 읽기 전용 manifest에서만 가져옵니다.</p></header>
    {#if !(runsData.runs?.length)}
      <section class="empty-state"><h2>아직 평가할 실행이 없습니다</h2><p>학습 페이지에서 데이터셋과 학습 실행 기록을 먼저 확인하세요.</p></section>
    {:else}
      <section class="card picker"><h2>실행 선택</h2><div class="run-list">{#each runsData.runs ?? [] as run}<button type="button" class:chosen={selected === runKey(run.dataset_run_id, run.run_id)} onclick={() => { selected = runKey(run.dataset_run_id, run.run_id); selectRun(); }}><span>{text(run.dataset_run_id)} · {text(run.run_id)}</span><span class="chip">{text(run.verdict_candidate?.value)}</span></button>{/each}</div></section>
      {#if detailLoading}<section class="card" aria-live="polite">선택한 실행 manifest를 읽고 있습니다.</section>
      {:else if error}<section class="card error" aria-live="assertive"><p>{error}</p><button type="button" onclick={selectRun}>다시 시도</button></section>
      {:else if detail?.reason}<section class="card error"><h2>실행 상세를 표시할 수 없습니다</h2><p>{detail.reason}</p></section>
      {:else if detail?.manifest}
        <section class={`card verdict ${verdictClass()}`}><h2>판정 <span class="chip">{verdict()}</span></h2>{#if verdict() === 'GO_CANDIDATE_VALIDATION_ONLY'}<p>검증 후보 · 수익·실거래 주장 아님</p>{:else if verdict() === 'INCONCLUSIVE'}<p>증거가 결론을 뒷받침하기에 충분하지 않습니다.</p>{/if}{#if Array.isArray(detail.manifest.verdict_candidate?.reasons)}<ul>{#each detail.manifest.verdict_candidate.reasons as reason}<li>{String(reason)}</li>{/each}</ul>{/if}</section>
        <section class="card"><h2>seed별 검증</h2><div class="table-wrap"><table><thead><tr><th>seed</th><th>episodes</th><th>best episode</th><th>val NAV (₩)</th><th>return %</th><th>MDD %</th><th>trades</th></tr></thead><tbody>{#each seeds() as [seed, value]}<tr><th>{seed}</th><td>{text(value.episodes_ran)}</td><td>{text(value.best_episode)}</td><td>{won(value.final_val_metrics?.nav)}</td><td>{percent(value.final_val_metrics?.total_net_return_pct)}</td><td>{percent(value.final_val_metrics?.max_drawdown)}</td><td>{text(value.final_val_metrics?.trade_count)}</td></tr>{/each}</tbody></table></div><h3>수수료 민감도</h3><div class="table-wrap"><table><thead><tr><th>seed</th><th>0.00%</th><th>0.23%</th><th>0.46%</th></tr></thead><tbody>{#each seeds() as [seed, value]}<tr><th>{seed}</th><td>{won(value.final_val_metrics?.cost_scenario_navs?.['0.0000'])}</td><td>{won(value.final_val_metrics?.cost_scenario_navs?.['0.0023'])}</td><td>{won(value.final_val_metrics?.cost_scenario_navs?.['0.0046'])}</td></tr>{/each}</tbody></table></div></section>
        <section class="card"><h2>기준선 NAV vs policy</h2><div class="table-wrap"><table><thead><tr><th>전략</th><th>NAV</th></tr></thead><tbody>{#each ['no_trade', 'rule_topk_ret5', 'random_topk'] as name}<tr><th>{name}</th><td>{won(detail.manifest.baselines?.[name]?.nav)}</td></tr>{/each}</tbody></table></div></section>
        <section class="card"><h2>test 상태</h2>{#if detail.manifest.test?.state === 'NOT_RUN'}<p>untouched test는 아직 읽지 않았습니다 (사전등록상 1회만 허용)</p>{:else}<p>{text(detail.manifest.test?.state)}</p>{/if}</section>
        <section class="card"><h2>최근 validation events</h2>{#if eventRows().length}<ol>{#each eventRows() as event}<li>episode {text(event.episode)} · val NAV {won(event.val_nav)}</li>{/each}</ol>{:else}<p class="absence">표시할 validation event가 없습니다.</p>{/if}</section>
      {/if}
    {/if}
  </section>
{/if}

<style>
  .evaluation-page, .panel { max-width: 980px; border: 1px solid var(--border); border-radius: 14px; padding: clamp(18px, 4vw, 32px); background: var(--surface); color: var(--fg); } .eyebrow { margin: 0; color: var(--accent); font-size: .72rem; font-weight: 800; letter-spacing: .1em; } h1 { margin: 7px 0; color: var(--fg-strong); font-size: clamp(1.7rem, 6vw, 2.5rem); } header > p, .absence { color: var(--muted); } .card, .empty-state { margin-top: 16px; border: 1px solid var(--border-strong); border-radius: 10px; padding: 16px; background: var(--surface-raised); } .empty-state { border-color: var(--warn); background: var(--warn-soft); } h2 { margin: 0 0 12px; color: var(--fg-strong); font-size: 1.05rem; } h3 { margin: 18px 0 8px; color: var(--accent-strong); font-size: .9rem; } .run-list { display: grid; gap: 7px; } .run-list button { width: 100%; display: flex; justify-content: space-between; gap: 8px; border: 1px solid var(--border-strong); border-radius: 6px; padding: 8px; background: var(--surface-sunken); color: var(--fg); font: inherit; text-align: left; cursor: pointer; overflow-wrap: anywhere; } .run-list button.chosen { border-color: var(--accent); } .chip { display: inline-block; margin-left: 5px; border: 1px solid currentColor; border-radius: 999px; padding: 2px 6px; font-size: .68rem; vertical-align: middle; } .verdict.no-go { border-color: var(--danger); background: var(--danger-soft); color: var(--danger); } .verdict.candidate { border-color: var(--warn); background: var(--warn-soft); color: var(--warn); } .verdict.inconclusive { border-color: var(--dim); color: var(--muted); } .table-wrap { max-width: 100%; overflow-x: auto; } table { width: 100%; min-width: 580px; border-collapse: collapse; font-size: .78rem; } th, td { border-top: 1px solid var(--border); padding: 7px; overflow-wrap: anywhere; text-align: left; } th { color: var(--muted); } .error { border-color: var(--danger); color: var(--danger); } button { border: 1px solid var(--accent); border-radius: 6px; padding: 6px 10px; background: transparent; color: var(--accent-strong); font: inherit; cursor: pointer; } li { overflow-wrap: anywhere; }
</style>
