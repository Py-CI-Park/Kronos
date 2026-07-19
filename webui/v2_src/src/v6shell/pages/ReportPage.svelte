<script lang="ts">
  import { onMount } from 'svelte';
  import { getV6Experiment, getV6RunDetail, getV6Runs, getV6Status, type V6Experiment, type V6RunDetail, type V6Runs, type V6Status } from '../v6Api';
  let status = $state<V6Status | null>(null);
  let experiment = $state<V6Experiment | null>(null);
  let runs = $state<V6Runs | null>(null);
  let detail = $state<V6RunDetail | null>(null);
  let error = $state<string | null>(null);
  let loading = $state(true);
  function text(value: unknown): string { return value === undefined || value === null || value === '' ? 'MISSING' : String(value); }
  function reasons(value: unknown): string[] { return Array.isArray(value) ? value.map((item) => text(item)) : []; }
  function newest() { return runs?.runs?.[0]; }
  function verdict(): { value: string; reasons: string[] } { const candidate = detail?.manifest?.verdict_candidate ?? newest()?.verdict_candidate; return { value: text(candidate?.value), reasons: reasons(candidate?.reasons) }; }
  function dataset() { const run = newest(); return runs?.datasets?.find((item) => item.run_id === run?.dataset_run_id); }
  async function load(): Promise<void> {
    loading = true; error = null; detail = null;
    const [statusResult, experimentResult, runsResult] = await Promise.all([getV6Status(), getV6Experiment(), getV6Runs()]);
    if (!statusResult.ok || !statusResult.data || !experimentResult.ok || !experimentResult.data || !runsResult.ok || !runsResult.data) { error = statusResult.error ?? experimentResult.error ?? runsResult.error ?? '알 수 없는 오류가 발생했습니다.'; loading = false; return; }
    status = statusResult.data; experiment = experimentResult.data; runs = runsResult.data;
    const run = runsResult.data.runs?.[0];
    if (run?.dataset_run_id && run.run_id) { const detailResult = await getV6RunDetail(run.dataset_run_id, run.run_id); if (detailResult.ok && detailResult.data) detail = detailResult.data; else error = detailResult.error ?? '최신 실행 상세를 불러오지 못했습니다.'; }
    loading = false;
  }
  onMount(load);
</script>

<section class="page" aria-labelledby="report-title">
  <header><p class="eyebrow">RESEARCH PROVENANCE</p><h1 id="report-title">보고서</h1><p>판정과 근거의 연결만 기록합니다. 이 화면은 투자 권유나 수익 주장이 아닙니다.</p></header>
  {#if loading}<section class="panel" aria-live="polite">판정과 증거 체인을 확인하고 있습니다.</section>
  {:else if error && !status}<section class="panel error" aria-live="assertive"><h2>보고서를 불러오지 못했습니다</h2><p>{error}</p><button type="button" onclick={load}>다시 시도</button></section>
  {:else}
    {@const currentVerdict = verdict()}
    <section class:danger={currentVerdict.value === 'NO_GO'} class="verdict"><p class="eyebrow">현재 판정</p><h2>{currentVerdict.value}</h2>{#if currentVerdict.reasons.length}<ul>{#each currentVerdict.reasons as reason}<li>{reason}</li>{/each}</ul>{:else}<p>판정 사유가 기록되지 않았습니다.</p>{/if}</section>
    {#if error}<section class="panel error" aria-live="assertive"><p>일부 최신 실행 상세를 읽지 못했습니다: {error}</p><button type="button" onclick={load}>다시 시도</button></section>{/if}
    {#if !(runs?.runs?.length)}<section class="panel empty"><h2>증거 체인이 비어 있습니다</h2><p>학습 실행이 없으므로 데이터셋·학습 manifest·판정을 연결할 수 없습니다.</p></section>
    {:else}<section class="card"><h2>증거 체인</h2><div class="table-wrap"><table><tbody><tr><th>Universe manifest</th><td><code>{text(status?.journey.data.universe_manifest)}</code></td><td>{text(status?.journey.data.universe_size)} rows</td></tr><tr><th>Preregistration</th><td><code>{text(experiment?.prereg?.path)}</code></td><td><code>{text(experiment?.prereg?.sha256)}</code></td></tr><tr><th>Dataset run</th><td><code>{text(dataset()?.run_id)}</code></td><td><code>{text(dataset()?.sha256)}</code></td></tr><tr><th>Training run</th><td><code>{text(newest()?.run_id)}</code></td><td><code>{text(detail?.manifest_sha256)}</code></td></tr></tbody></table></div></section>{/if}
    <section class="card rules"><h2>보고 규칙</h2><p>GO/NO-GO/INCONCLUSIVE/NOT_RUN은 그대로 기록되며 완화되지 않습니다</p></section>
    <section class="card"><h2>관련 문서</h2><ul class="docs"><li><code>requirements.txt</code></li><li><code>docs/kronos_v6_prereg_h1_2026-07-19.json</code></li><li><code>docs/kronos_v6_universe_manifest_2026-07-19.json</code></li><li><code>docs/kronos_v6_goal_review_and_plan_2026-07-19.md</code></li></ul></section>
  {/if}
</section>

<style>
  .page { max-width: 980px; color: var(--fg); } header, .panel, .card, .verdict { border: 1px solid var(--border); border-radius: 14px; padding: clamp(16px, 4vw, 28px); background: var(--surface); } .eyebrow { margin: 0; color: var(--accent); font-size: .72rem; font-weight: 800; letter-spacing: .1em; } h1 { margin: 7px 0; color: var(--fg-strong); font-size: clamp(1.7rem, 6vw, 2.5rem); } h2 { margin: 0 0 12px; color: var(--fg-strong); font-size: 1.1rem; } header > p:last-child { color: var(--muted); } .verdict, .card, .panel { margin-top: 16px; } .verdict h2 { color: var(--info); font-size: clamp(2rem, 8vw, 3.5rem); }.verdict.danger { border-color: var(--danger); background: var(--danger-soft); } .verdict.danger h2 { color: var(--danger); } ul { margin: 0; padding-left: 20px; } li + li { margin-top: 6px; } .table-wrap { max-width: 100%; overflow-x: auto; } table { width: 100%; min-width: 680px; border-collapse: collapse; font-size: .82rem; } th, td { border-top: 1px solid var(--border); padding: 9px; text-align: left; vertical-align: top; overflow-wrap: anywhere; } th { color: var(--muted); } code { overflow-wrap: anywhere; color: var(--accent-strong); } .rules { border-color: var(--warn); background: var(--warn-soft); color: var(--warn); } .docs { list-style: none; padding: 0; } .docs li { border-top: 1px solid var(--border); padding: 8px 0; } .error { border-color: var(--danger); color: var(--danger); } .empty { border-color: var(--warn); background: var(--warn-soft); } button { border: 1px solid var(--accent); border-radius: 6px; padding: 8px 12px; background: transparent; color: var(--accent-strong); font: inherit; cursor: pointer; }
</style>
