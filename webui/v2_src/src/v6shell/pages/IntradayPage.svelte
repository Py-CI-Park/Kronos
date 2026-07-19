<section class="page" aria-labelledby="intraday-title">
  <header>
    <p class="eyebrow">SEPARATE RESEARCH LANE</p>
    <h1 id="intraday-title">인트라데이 RL</h1>
    <p>V6는 일봉 종가매매 연구에 집중합니다. 인트라데이 연구의 기존 증거와 판정은 별도 레인에서 확인합니다.</p>
  </header>

  <section class="notice" aria-labelledby="intraday-boundary-title">
    <h2 id="intraday-boundary-title">판정 경계</h2>
    <p>기존 판정(NO-GO 등)은 그대로 유지됩니다. V6의 일봉 종가매매 연구 결과와 병합하거나 대체하지 않습니다.</p>
  </section>

  <div class="links" aria-label="기존 인트라데이 연구 레인">
    <a class="lane-card" href="/?tab=rl&amp;ui=v5">
      <span class="card-label">EXISTING EVIDENCE LANE</span>
      <h2>V5 RL Trading Evidence</h2>
      <p>기존 판정(NO-GO 등)은 그대로 유지됩니다.</p>
      <span class="destination">증거 레인 열기 →</span>
    </a>
    <a class="lane-card" href="/?tab=daily-ohlcv&amp;ui=v5">
      <span class="card-label">EXISTING DAILY CLOSE LANE</span>
      <h2>V5 Daily Close RL</h2>
      <p>기존 판정(NO-GO 등)은 그대로 유지됩니다.</p>
      <span class="destination">일봉 종가 레인 열기 →</span>
    </a>
  </div>
</section>

<style>
  .page { max-width: 980px; color: #e5e7eb; }
  header, .notice, .lane-card { border: 1px solid #334155; border-radius: 14px; padding: clamp(16px, 4vw, 28px); background: #111827; }
  .eyebrow, .card-label { margin: 0; color: #7dd3fc; font-size: .72rem; font-weight: 800; letter-spacing: .1em; }
  h1 { margin: 7px 0; color: #f8fafc; font-size: clamp(1.7rem, 6vw, 2.5rem); }
  h2 { margin: 0 0 10px; color: #f8fafc; font-size: 1.1rem; }
  header > p:last-child, .lane-card p { color: #cbd5e1; line-height: 1.6; }
  .notice { margin-top: 16px; border-color: #a16207; background: #1c1910; color: #fde68a; }
  .notice p { margin-bottom: 0; line-height: 1.6; }
  .links { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-top: 16px; }
  .lane-card { display: block; min-width: 0; color: inherit; text-decoration: none; }
  .lane-card:hover { border-color: #38bdf8; background: #082f49; }
  .lane-card:focus-visible { outline: 2px solid #fef08a; outline-offset: 3px; }
  .destination { color: #bae6fd; font-weight: 800; }
  @media (max-width: 700px) { .links { grid-template-columns: 1fr; } }
</style>
