<script lang="ts">
  import { onMount } from 'svelte';
  import { getV6DataReadiness, getV6Universe, type V6DataReadiness, type V6Universe } from '../v6Api';

  const INDEX_COMMAND = 'py -3.11 scripts/collect_korean_index_artifact.py --market KOSPI --start-date 2018-01-01 --end-date 2026-06-12 --output-dir artifacts/korean_index';
  let readiness = $state<V6DataReadiness | null>(null);
  let universe = $state<V6Universe | null>(null);
  let error = $state<string | null>(null);
  let loading = $state(true);

  function bytes(value: number | undefined): string {
    return typeof value === 'number' ? `${new Intl.NumberFormat('ko-KR').format(value)} bytes` : 'MISSING';
  }
  function number(value: number | undefined): string {
    return typeof value === 'number' ? new Intl.NumberFormat('ko-KR').format(value) : 'MISSING';
  }
  function value(value: unknown): string {
    if (value === undefined || value === null || value === '') return 'MISSING';
    return typeof value === 'string' ? value : JSON.stringify(value);
  }
  function presence(present: boolean | undefined, state: string | undefined): string {
    return present === true || state === 'PRESENT' ? 'PRESENT' : 'MISSING';
  }

  async function load(): Promise<void> {
    loading = true;
    error = null;
    const [readinessResult, universeResult] = await Promise.all([getV6DataReadiness(), getV6Universe(20)]);
    loading = false;
    if (!readinessResult.ok || !readinessResult.data) { error = readinessResult.error ?? '알 수 없는 오류가 발생했습니다.'; return; }
    if (!universeResult.ok || !universeResult.data) { error = universeResult.error ?? '알 수 없는 오류가 발생했습니다.'; return; }
    readiness = readinessResult.data;
    universe = universeResult.data;
  }

  onMount(load);
</script>

{#if loading}
  <section class="panel" aria-live="polite"><p>데이터 준비 상태를 확인하고 있습니다.</p></section>
{:else if error}
  <section class="panel error" aria-live="assertive">
    <h1>데이터 준비 상태를 불러오지 못했습니다</h1><p>{error}</p><button type="button" onclick={load}>다시 시도</button>
  </section>
{:else if readiness && universe}
  <section class="data-page" aria-labelledby="data-title">
    <header><p class="eyebrow">DATA READINESS</p><h1 id="data-title">데이터 준비 상태</h1><p>표시된 값은 읽기 전용 API 응답에서만 가져옵니다.</p></header>

    <section class="card" aria-labelledby="daily-title">
      <h2 id="daily-title">일봉 DB <span class={`chip ${readiness.daily_db.present === true || readiness.daily_db.state === 'PRESENT' ? '' : 'missing'}`}>{presence(readiness.daily_db.present, readiness.daily_db.state)}</span></h2>
      <dl><div><dt>크기</dt><dd>{bytes(readiness.daily_db.size_bytes)}</dd></div><div><dt>테이블 수</dt><dd>{number(readiness.daily_db.table_count)}</dd></div><div><dt>수정 시각</dt><dd>{value(readiness.daily_db.mtime ?? readiness.daily_db.mtime_epoch)}</dd></div></dl>
      <p class="caveat">기간과 모집단은 감사 응답의 범위에 한정됩니다: {value(readiness.audit.disclaimers)}</p>
    </section>

    <section class="card" aria-labelledby="universe-title">
      <h2 id="universe-title">연구 universe <span class="chip">{number(universe.total)}</span></h2>
      <dl><div><dt>필터</dt><dd>{value(universe.filters)}</dd></div><div><dt>종목 유형</dt><dd>{value(universe.instrument_type)}</dd></div><div><dt>모집단</dt><dd>{value(readiness.audit.population)}</dd></div></dl>
      <p class="warning"><strong>UNVERIFIED:</strong> instrument_type은 검증되지 않았습니다. {value(universe.instrument_type)}</p>
      <div class="table-wrap"><table><caption>상위 20개 universe 행</caption><thead><tr><th>table</th><th>code</th><th>rows</th><th>first_date</th><th>last_date</th></tr></thead><tbody>{#if universe.universe.length}{#each universe.universe as row}<tr><td>{value(row.table)}</td><td>{value(row.code)}</td><td>{number(row.rows)}</td><td>{value(row.first_date)}</td><td>{value(row.last_date)}</td></tr>{/each}{:else}<tr><td colspan="5">MISSING</td></tr>{/if}</tbody></table></div>
    </section>

    <section class="card" aria-labelledby="fivemin-title">
      <h2 id="fivemin-title">5분봉 DB <span class={`chip ${readiness.fivemin_db.present === true || readiness.fivemin_db.state === 'PRESENT' ? '' : 'missing'}`}>{presence(readiness.fivemin_db.present, readiness.fivemin_db.state)}</span></h2>
      <dl><div><dt>크기</dt><dd>{bytes(readiness.fivemin_db.size_bytes)}</dd></div></dl>
      <p class="caveat">15:20 체결가는 장중 기준 시점의 권위 있는 체결가로만 취급하며, 종가 또는 수익률 근거로 대체하지 않습니다.</p>
    </section>

    <section class="card blocked" aria-labelledby="index-title">
      <h2 id="index-title">지수 overlay <span class="chip">{value(readiness.index.state)}</span></h2>
      <p>{value(readiness.index.reason)}</p>
      {#if readiness.index.state === 'BLOCKED'}<code>{INDEX_COMMAND}</code>{/if}
    </section>

    <section class="card warning" aria-labelledby="basis-title">
      <h2 id="basis-title">price basis <span class="chip">{value(readiness.price_basis.status)}</span></h2>
      <p><strong>UNKNOWN_CONFIRMED:</strong> 수정주가 여부 미검증 → 수익률 증거 사용 금지</p>
      <p>decision_grade_returns: {readiness.price_basis.decision_grade_returns === undefined ? 'MISSING' : String(readiness.price_basis.decision_grade_returns)}</p>
    </section>
  </section>
{/if}

<style>
  .data-page, .panel { max-width: 980px; border: 1px solid var(--surface-border, #334155); border-radius: 14px; padding: clamp(18px, 4vw, 32px); background: var(--surface, #111827); color: #e5e7eb; }
  .eyebrow { margin: 0; color: #7dd3fc; font-size: .72rem; font-weight: 800; letter-spacing: .1em; } h1 { margin: 7px 0; color: #f8fafc; font-size: clamp(1.7rem, 6vw, 2.5rem); } header > p { color: #cbd5e1; }
  .card { margin-top: 16px; border: 1px solid #475569; border-radius: 10px; padding: 16px; background: #0f172a; } h2 { margin: 0 0 12px; color: #f8fafc; font-size: 1.05rem; } .chip { display: inline-block; margin-left: 5px; border: 1px solid #0369a1; border-radius: 999px; padding: 2px 6px; color: #bae6fd; font-size: .68rem; vertical-align: middle; } .missing, .blocked .chip { border-color: #b91c1c; color: #fecaca; }
  dl { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 0; } dl div { min-width: 0; } dt { color: #94a3b8; font-size: .74rem; } dd { margin: 3px 0 0; overflow-wrap: anywhere; color: #e2e8f0; font-size: .86rem; } .caveat, .warning { color: #fde68a; line-height: 1.55; } .blocked { border-color: #991b1b; background: #1c1012; } code { display: block; overflow-wrap: anywhere; border: 1px solid #7f1d1d; border-radius: 6px; padding: 9px; color: #fecaca; font-size: .75rem; line-height: 1.5; }
  .table-wrap { max-width: 100%; overflow-x: auto; } table { width: 100%; min-width: 550px; border-collapse: collapse; font-size: .78rem; } caption { padding: 12px 0 6px; color: #cbd5e1; text-align: left; } th, td { border-top: 1px solid #334155; padding: 7px; overflow-wrap: anywhere; text-align: left; } th { color: #94a3b8; } .error { border-color: #b91c1c; color: #fecaca; } button { border: 1px solid #7dd3fc; border-radius: 6px; padding: 6px 10px; background: transparent; color: #e0f2fe; font: inherit; cursor: pointer; }
  @media (max-width: 600px) { dl { grid-template-columns: 1fr; } }
</style>
