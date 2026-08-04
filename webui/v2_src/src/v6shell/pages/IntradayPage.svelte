<script lang="ts">
  import PageDecisionRail from '../PageDecisionRail.svelte';
</script>

<section class="page" aria-labelledby="intraday-title">
  <header><p class="eyebrow">SEPARATE RESEARCH LANE</p><h1 id="intraday-title">인트라데이 RL</h1><p>V6의 일봉 종가매매 연구와 분리된 과거 레인입니다. 기존 실패와 NO-GO를 새 일봉 결과로 덮어쓰지 않습니다.</p></header>
  <PageDecisionRail pageId="lanes" />
  <section class="notice" aria-labelledby="intraday-boundary-title"><h2 id="intraday-boundary-title">판정 경계</h2><p>인트라데이·orderbook·규칙 전략의 결과는 각자의 데이터·비용·체결 계약 안에서만 해석합니다.</p></section>
  <div class="links" aria-label="기존 연구 레인">
    <a class="lane-card" href="/?tab=rl&amp;ui=v5"><span class="card-label">EXISTING EVIDENCE</span><h2>V5 RL Trading Evidence</h2><p>기존 ts_imb RULE과 RL 실험의 판정을 그대로 보존합니다.</p><dl><dt>기준선</dt><dd>ts_imb RULE baseline</dd><dt>경계</dt><dd>새 CQL 성과 전이 금지</dd></dl><span class="destination">기존 증거 열기 →</span></a>
    <a class="lane-card" href="/?tab=daily-ohlcv&amp;ui=v5"><span class="card-label">DAILY CLOSE ARCHIVE</span><h2>V5 Daily Close RL</h2><p>이전 일봉·orderbook 연구의 실패 조건과 비용 가정을 확인합니다.</p><dl><dt>연구 범위</dt><dd>orderbook RL</dd><dt>상태</dt><dd>research-only</dd></dl><span class="destination">과거 레인 열기 →</span></a>
  </div>
</section>

<style>
  .page{width:100%;min-width:0;display:grid;gap:16px;color:var(--fg)}header,.notice,.lane-card{min-width:0;border:1px solid var(--border);border-radius:14px;padding:clamp(18px,4vw,30px);background:var(--surface)}.eyebrow,.card-label{margin:0;color:var(--accent);font-size:.76rem;font-weight:800;letter-spacing:.1em}h1{margin:7px 0;color:var(--fg-strong);font-size:clamp(1.9rem,6vw,2.7rem)}h2{margin:0 0 10px;color:var(--fg-strong);font-size:1.2rem}header>p:last-child,.lane-card p{color:var(--muted);line-height:1.6}.notice{border-color:var(--warn);background:var(--warn-soft)}.notice p{margin-bottom:0;color:var(--warn);line-height:1.6}.links{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,360px),1fr));gap:16px}.lane-card{display:block;color:inherit;text-decoration:none}.lane-card:hover{border-color:var(--accent);background:var(--accent-soft)}.lane-card:focus-visible{outline:2px solid var(--warn);outline-offset:3px}dl{display:grid;grid-template-columns:auto 1fr;gap:6px 12px;margin:16px 0;padding:12px 0;border-block:1px solid var(--border)}dt{color:var(--muted)}dd{margin:0;color:var(--fg-strong);overflow-wrap:anywhere}.destination{color:var(--accent-strong);font-weight:800}
</style>
