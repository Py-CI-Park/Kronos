<script lang="ts">
  let detailsOpen = $state(false);
</script>

<section class="safety-strip" aria-label="V6 안전 상태">
  <div class="strip-line">
    <div class="pills" aria-label="안전 제한">
      <span>NO-GO</span>
      <span>READ-ONLY</span>
      <span>NOT_RUN ≠ RESULT</span>
      <span>NO LIVE / NO PROFIT</span>
    </div>
    <button type="button" aria-expanded={detailsOpen} aria-controls="v6-safety-details" onclick={() => (detailsOpen = !detailsOpen)}>
      안전 상세
    </button>
  </div>
  {#if detailsOpen}
    <div class="details" id="v6-safety-details">
      <p>V6는 연구 전용입니다. 기본 UI는 계속 V3이며, 이 화면은 opt-in으로만 열립니다.</p>
      <p>브로커, 주문, 라이브, 페이퍼 포워드, 수익 또는 GO 주장은 제공하지 않습니다.</p>
      <p>여섯 개의 false lock은 모두 false 상태로 유지됩니다.</p>
    </div>
  {/if}
</section>

<style>
  .safety-strip {
    border: 1px solid #7f1d1d;
    border-radius: 10px;
    background: #1c1012;
    color: #fecaca;
    font-size: 0.78rem;
  }
  .strip-line {
    min-height: 40px;
    padding: 6px 10px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .pills { display: flex; flex-wrap: wrap; gap: 5px; min-width: 0; }
  .pills span {
    border: 1px solid #b91c1c;
    border-radius: 999px;
    padding: 2px 6px;
    color: #fecaca;
    font-weight: 700;
    letter-spacing: 0.02em;
    white-space: nowrap;
  }
  button {
    flex: 0 0 auto;
    border: 1px solid #fca5a5;
    border-radius: 6px;
    padding: 4px 8px;
    background: transparent;
    color: #fee2e2;
    font: inherit;
    cursor: pointer;
  }
  button:focus-visible { outline: 2px solid #fef3c7; outline-offset: 2px; }
  .details { border-top: 1px solid #7f1d1d; padding: 8px 10px; color: #fee2e2; line-height: 1.45; }
  .details p { margin: 0; }
  .details p + p { margin-top: 4px; }
  @media (max-width: 520px) {
    .strip-line { align-items: flex-start; }
    button { margin-top: 1px; }
  }
</style>
