<section class="page" aria-labelledby="kronos-title">
  <header>
    <p class="eyebrow">INDEPENDENT RESEARCH LANE</p>
    <h1 id="kronos-title">Kronos 예측</h1>
    <p>Kronos 예측은 강화학습과 독립된 연구 레인입니다. 예측 레인의 판정은 RL 판정과 병합하지 않습니다.</p>
  </header>

  <section class="notice" aria-labelledby="kronos-boundary-title">
    <h2 id="kronos-boundary-title">판정 경계</h2>
    <p>예측 결과, 진단, 기존 판정은 해당 레인 안에서만 해석합니다. RL 연구의 GO/NO-GO를 변경하거나 대신하지 않습니다.</p>
  </section>

  <div class="links" aria-label="Kronos 예측 연구 레인">
    <a class="lane-card" href="/?tab=forecast&amp;ui=v5">
      <span class="card-label">PREDICTION WORKBENCH</span>
      <h2>예측 워크벤치</h2>
      <p>독립된 예측 연구의 입력, 결과, 검토 흐름을 확인합니다.</p>
      <span class="destination">워크벤치 열기 →</span>
    </a>
    <a class="lane-card" href="/?tab=stom&amp;ui=v5">
      <span class="card-label">PREDICTION DIAGNOSTICS</span>
      <h2>예측 진단</h2>
      <p>예측 연구의 진단 정보와 근거를 별도 레인에서 확인합니다.</p>
      <span class="destination">진단 열기 →</span>
    </a>
  </div>
</section>

<style>
  .page { max-width: 980px; color: var(--fg); }
  header, .notice, .lane-card { border: 1px solid var(--border); border-radius: 14px; padding: clamp(16px, 4vw, 28px); background: var(--surface); }
  .eyebrow, .card-label { margin: 0; color: var(--accent); font-size: .72rem; font-weight: 800; letter-spacing: .1em; }
  h1 { margin: 7px 0; color: var(--fg-strong); font-size: clamp(1.7rem, 6vw, 2.5rem); }
  h2 { margin: 0 0 10px; color: var(--fg-strong); font-size: 1.1rem; }
  header > p:last-child, .lane-card p { color: var(--muted); line-height: 1.6; }
  .notice { margin-top: 16px; border-color: var(--warn); background: var(--warn-soft); color: var(--warn); }
  .notice p { margin-bottom: 0; line-height: 1.6; }
  .links { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-top: 16px; }
  .lane-card { display: block; min-width: 0; color: inherit; text-decoration: none; }
  .lane-card:hover { border-color: var(--accent); background: var(--accent-soft); }
  .lane-card:focus-visible { outline: 2px solid var(--warn); outline-offset: 3px; }
  .destination { color: var(--accent-strong); font-weight: 800; }
  @media (max-width: 700px) { .links { grid-template-columns: 1fr; } }
</style>
