<script lang="ts">
  let detailsOpen = $state(false);
</script>

<section class="safety-strip" aria-label="V6 연구 안전 상태">
  <div class="strip-line">
    <div class="pills" aria-label="운영 제한">
      <span>NO-GO</span><span>READ-ONLY</span><span>FRESH OOS: NOT RUN</span><span>NO LIVE / NO PROFIT CLAIM</span>
    </div>
    <button type="button" aria-expanded={detailsOpen} aria-controls="v6-safety-details" onclick={() => (detailsOpen = !detailsOpen)}>안전 경계</button>
  </div>
  {#if detailsOpen}
    <div class="details" id="v6-safety-details">
      <p>이 화면은 로컬 연구 증거를 읽는 대시보드입니다. 주문 실행, 브로커 연결, 실거래 승인을 제공하지 않습니다.</p>
      <p>합성 CQL 보정 성공과 실제 시장 수익 모델 생성은 별개입니다. 현재 경제 모델 점수는 20/100이며 생성되지 않았습니다.</p>
      <p>시점 보존 데이터와 Fresh OOS 검증 전에는 GO, 수익성, 라이브 준비 완료로 승격할 수 없습니다.</p>
    </div>
  {/if}
</section>

<style>
  .safety-strip{border:1px solid var(--danger);border-radius:10px;background:var(--danger-soft);color:var(--danger);font-size:.78rem}.strip-line{min-height:40px;padding:6px 10px;display:flex;align-items:center;justify-content:space-between;gap:8px}.pills{display:flex;flex-wrap:wrap;gap:5px;min-width:0}.pills span{border:1px solid var(--danger);border-radius:999px;padding:2px 6px;color:var(--danger);font-weight:700;letter-spacing:.02em;white-space:nowrap}button{flex:0 0 auto;border:1px solid var(--danger);border-radius:6px;padding:4px 8px;background:transparent;color:var(--danger);font:inherit;cursor:pointer}button:focus-visible{outline:2px solid var(--warn);outline-offset:2px}.details{border-top:1px solid var(--danger);padding:8px 10px;color:var(--danger);line-height:1.45}.details p{margin:0}.details p+p{margin-top:4px}@media(max-width:520px){.strip-line{align-items:flex-start}button{margin-top:1px}}
</style>
