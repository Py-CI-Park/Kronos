<script lang="ts">
  import { onMount } from 'svelte';
  import { getV6DataReadiness, getV6Universe, type V6DataReadiness, type V6Universe } from '../v6Api';
  import { TYPE1_FACTS, classifyType1State, type1StateLabel } from '../type1Presentation';
  let readiness = $state<V6DataReadiness | null>(null); let universe = $state<V6Universe | null>(null);
  let loading = $state(true); let errors = $state<Record<string, string>>({});
  const text = (value: unknown) => value === undefined || value === null || value === '' ? 'MISSING' : typeof value === 'string' ? value : JSON.stringify(value);
  const number = (value: number | undefined) => typeof value === 'number' ? new Intl.NumberFormat('ko-KR').format(value) : 'MISSING';
  const bytes = (value: number | undefined) => typeof value === 'number' ? `${new Intl.NumberFormat('ko-KR').format(value)} bytes` : 'MISSING';
  const present = (item: { present?: boolean; state?: string }) => item.present === true || item.state === 'PRESENT';
  const unavailable = (resource: string) => loading ? 'LOADING' : errors[resource] ? 'UNAVAILABLE' : 'MISSING';
  const type1SourceState = $derived.by(() => {
    const label = type1StateLabel(classifyType1State(readiness?.fivemin_db, loading));
    return label === 'EMPTY' ? 'MISSING' : label;
  });
  async function load(): Promise<void> { loading = true; errors = {}; const [readinessResult, universeResult] = await Promise.all([getV6DataReadiness(), getV6Universe(20)]); const next: Record<string, string> = {}; if (readinessResult.ok && readinessResult.data) readiness = readinessResult.data; else next.readiness = readinessResult.error ?? '데이터 준비 상태 API를 불러오지 못했습니다.'; if (universeResult.ok && universeResult.data) universe = universeResult.data; else next.universe = universeResult.error ?? 'universe API를 불러오지 못했습니다.'; errors = next; loading = false; }
  onMount(() => { void load(); });
</script>

<section class="data-page" aria-labelledby="data-title">
  <header><p class="eyebrow">DATA READINESS</p><h1 id="data-title">데이터 준비 상태</h1><p>아래 행렬은 읽기 전용 API가 반환한 사실만 표시합니다. 요청 실패는 UNAVAILABLE입니다.</p></header>
  {#if loading}<p class="notice" role="status">데이터 준비 상태를 확인하고 있습니다.</p>{/if}
  {#if Object.keys(errors).length}<section class="notice error" role="alert"><strong>일부 데이터 API를 사용할 수 없습니다.</strong><span>{Object.values(errors).join(' ')}</span><button type="button" onclick={() => void load()}>다시 시도</button></section>{/if}
  <div class="matrix" aria-label="API 사실 기반 데이터 준비 행렬">
    <section class="card"><h2>일봉 DB 신선도</h2><dl><div><dt>상태</dt><dd>{readiness ? (present(readiness.daily_db) ? 'PRESENT' : text(readiness.daily_db.state)) : unavailable('readiness')}</dd></div><div><dt>수정 시각</dt><dd>{readiness ? text(readiness.daily_db.mtime ?? readiness.daily_db.mtime_epoch) : unavailable('readiness')}</dd></div><div><dt>테이블</dt><dd>{readiness ? number(readiness.daily_db.table_count) : unavailable('readiness')}</dd></div><div><dt>크기</dt><dd>{readiness ? bytes(readiness.daily_db.size_bytes) : unavailable('readiness')}</dd></div></dl></section>
    <section class="card"><h2>5분봉 DB</h2><dl><div><dt>상태</dt><dd>{readiness ? (present(readiness.fivemin_db) ? 'PRESENT' : text(readiness.fivemin_db.state)) : unavailable('readiness')}</dd></div><div><dt>크기</dt><dd>{readiness ? bytes(readiness.fivemin_db.size_bytes) : unavailable('readiness')}</dd></div></dl></section>
    <section class="card"><h2>감사 모집단·필터</h2><dl><div><dt>감사 상태</dt><dd>{readiness ? text(readiness.audit.state) : unavailable('readiness')}</dd></div><div><dt>모집단</dt><dd>{readiness ? text(readiness.audit.population) : unavailable('readiness')}</dd></div><div><dt>필터</dt><dd>{readiness ? text(readiness.audit.filters) : unavailable('readiness')}</dd></div><div><dt>종목 유형</dt><dd>{readiness ? text(readiness.audit.disclaimers?.instrument_type) : unavailable('readiness')}</dd></div></dl></section>
    <section class="card"><h2>가격 기준</h2><dl><div><dt>상태</dt><dd>{readiness ? text(readiness.price_basis.status) : unavailable('readiness')}</dd></div><div><dt>의사결정 등급 수익률</dt><dd>{readiness ? text(readiness.price_basis.decision_grade_returns) : unavailable('readiness')}</dd></div><div><dt>주의 사항</dt><dd>{readiness ? text(readiness.price_basis.caveat) : unavailable('readiness')}</dd></div></dl></section>
    <section class="card"><h2>universe manifest</h2><dl><div><dt>상태</dt><dd>{universe ? text(universe.status) : unavailable('universe')}</dd></div><div><dt>경로</dt><dd>{universe ? text(universe.manifest) : unavailable('universe')}</dd></div><div><dt>SHA-256</dt><dd>{universe ? text(universe.sha256) : unavailable('universe')}</dd></div><div><dt>모집단</dt><dd>{universe ? number(universe.total) : unavailable('universe')}</dd></div></dl></section>
    <section class="card"><h2>지수 coverage·차단</h2><dl><div><dt>상태</dt><dd>{readiness ? text(readiness.index.state) : unavailable('readiness')}</dd></div><div><dt>차단 사유</dt><dd>{readiness ? text(readiness.index.reason) : unavailable('readiness')}</dd></div>{#if readiness}{#each Object.entries(readiness.index.markets ?? {}) as [market, detail]}<div><dt>{market}</dt><dd>{text(detail.actual_start_date)} ~ {text(detail.actual_end_date)} · {number(detail.row_count)} rows · SHA {text(detail.normalized_sha256)}</dd></div>{/each}{/if}</dl></section>
  </div>
  <section class="card type1-data" aria-labelledby="type1-data-title">
    <p class="eyebrow">TYPE1 DATA AUTHORITY</p>
    <h2 id="type1-data-title">순차 RL 입력 경계</h2>
    <div class="type1-grid">
      <dl><div><dt>anchor universe</dt><dd>{universe ? text(universe.manifest) : unavailable('universe')}</dd></div><div><dt>calendar authority</dt><dd>MISSING</dd></div><div><dt>public split authority</dt><dd>MISSING</dd></div><div><dt>stable slots</dt><dd>500 · fixed contract, eligibility evidence는 별도</dd></div></dl>
      <dl><div><dt>decision price</dt><dd>{TYPE1_FACTS.execution.priceBasis}</dd></div><div><dt>official close</dt><dd>{String(TYPE1_FACTS.execution.officialClose)} · {TYPE1_FACTS.execution.officialCloseStatement}</dd></div><div><dt>leading-zero codes</dt><dd>문자열로 표시·보존 (예: 000250)</dd></div><div><dt>source integrity</dt><dd>{errors.readiness ? 'UNAVAILABLE' : type1SourceState}</dd></div></dl>
    </div>
    <p class="blocker"><strong>차단:</strong> tampered/blocked source의 승인 증거는 MISSING이며 fail-closed입니다. historical dataset이 invalid로 표시된 경우 Type1 학습·평가·OOS에 적격하지 않습니다. 이 화면의 DB 존재 또는 manifest는 적격·수익성·fresh OOS를 의미하지 않습니다.</p>
  </section>
  <section class="card wide"><h2>연구 universe <span class="chip">{universe ? number(universe.total) : unavailable('universe')}</span></h2><div class="table-wrap"><table><caption>API가 반환한 상위 20개 universe 행</caption><thead><tr><th scope="col">table</th><th scope="col">code</th><th scope="col">rows</th><th scope="col">first_date</th><th scope="col">last_date</th></tr></thead><tbody>{#if universe?.universe?.length}{#each universe.universe as row}<tr><td>{text(row.table)}</td><td>{text(row.code)}</td><td>{number(row.rows)}</td><td>{text(row.first_date)}</td><td>{text(row.last_date)}</td></tr>{/each}{:else}<tr><td colspan="5">{universe ? 'EMPTY' : unavailable('universe')}</td></tr>{/if}</tbody></table></div></section>
</section>

<style>
  .data-page { width:100%; min-width:0; border:1px solid var(--border); border-radius:14px; padding:clamp(18px,4vw,32px); background:var(--surface); color:var(--fg) }.matrix { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr)); gap:16px; margin-top:16px }.card { min-width:0; border:1px solid var(--border-strong); border-radius:10px; padding:16px; background:var(--surface-raised) }.wide { margin-top:16px }.eyebrow { margin:0;color:var(--accent);font-size:.82rem;font-weight:800;letter-spacing:.1em }h1 { margin:7px 0;color:var(--fg-strong);font-size:clamp(1.8rem,6vw,2.6rem) }h2 { margin:0 0 12px;color:var(--fg-strong);font-size:1.15rem }header>p,dt,caption { color:var(--muted) }.notice { margin-top:16px;padding:12px;border:1px solid var(--border-strong);border-radius:10px;color:var(--muted) }.error { display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;border-color:var(--danger);color:var(--danger) }dl { margin:0;display:grid;gap:10px }dt { font-size:.78rem }dd { margin:2px 0 0;overflow-wrap:anywhere }.chip { display:inline-block;border:1px solid var(--info);border-radius:999px;padding:2px 6px;color:var(--accent-strong);font-size:.78rem }.table-wrap { overflow-x:auto }table { width:100%;min-width:550px;border-collapse:collapse;font-size:.85rem }caption { padding:12px 0 6px;text-align:left }th,td { border-top:1px solid var(--border);padding:8px;text-align:left;overflow-wrap:anywhere }th { color:var(--muted) }button { border:1px solid var(--accent);border-radius:6px;padding:6px 10px;background:transparent;color:var(--accent-strong);font:inherit;cursor:pointer }button:focus-visible { outline:2px solid var(--accent);outline-offset:2px }
  .type1-data { margin-top:16px;border-color:var(--warn) }.type1-grid { display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));gap:16px }.type1-grid dl { min-width:0 }.type1-grid dt { color:var(--muted);font-size:.78rem }.type1-grid dd { margin:2px 0 0;overflow-wrap:anywhere }.blocker { margin:14px 0 0;color:var(--muted);line-height:1.55 }.blocker strong { color:var(--warn) }
</style>
