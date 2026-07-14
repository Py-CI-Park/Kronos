<script lang="ts">
  import type { Snippet } from 'svelte';
  import EvidenceDisclosure from '../components/EvidenceDisclosure.svelte';
  import { FORECAST_LIMITS } from './forecastEvidence';

  interface Props {
    children?: Snippet;
  }

  let { children }: Props = $props();
</script>

<section class="forecast-studio" data-v4-forecast-studio aria-labelledby="v4-forecast-studio-title">
  <div class="studio-intro">
    <p class="eyebrow">V4 Forecast Studio · research only</p>
    <h2 id="v4-forecast-studio-title">예측 스튜디오는 권한·근거를 먼저 잠그고 워크벤치를 마지막 raw surface로 둡니다</h2>
    <p>
      /api/predict는 읽기 전용 연구용 시계열 출력입니다. 이 화면은 broker, live order, profit, model promotion,
      trading recommendation을 선언하지 않으며 backend route를 추가하지 않습니다.
    </p>
  </div>

  <section class="contract-grid" aria-label="Forecast authority and caps">
    <article>
      <span>Authority</span>
      <strong>FAIL-CLOSED CLIENT VALIDATION</strong>
      <p>모델 key, 승인된 file_path, 로드된 model/data, device cpu|cuda가 유효할 때만 /api/predict 요청을 만들 수 있습니다.</p>
    </article>
    <article>
      <span>Caps</span>
      <strong>lookback {FORECAST_LIMITS.lookback.min}..{FORECAST_LIMITS.lookback.max}</strong>
      <p>pred_len {FORECAST_LIMITS.predLen.min}..{FORECAST_LIMITS.predLen.max}, sample_count {FORECAST_LIMITS.sampleCount.min}..{FORECAST_LIMITS.sampleCount.max}, temperature {FORECAST_LIMITS.temperature.min}..{FORECAST_LIMITS.temperature.max}, top_p {FORECAST_LIMITS.topP.min}..{FORECAST_LIMITS.topP.max}; legacy n_samples는 전송하지 않습니다.</p>
    </article>
    <article>
      <span>Status</span>
      <strong>V4 OPT-IN · V3 AVAILABLE</strong>
      <p>기존 workbench의 model/data load, result, chart surface를 자식으로 보존하고 V4 계약 설명만 앞에 둡니다.</p>
    </article>
    <article>
      <span>Posture</span>
      <strong>READ_ONLY RESEARCH</strong>
      <p>출력은 research time-series forecast이며 매매/수익 근거가 아닙니다. TEST OOS, 비용, promotion lock을 대체하지 않습니다.</p>
    </article>
  </section>

  <EvidenceDisclosure summary="Raw provenance/results · repaired Forecast workbench" meta="last surface" open lazy>
    <div class="workbench-child" data-v4-forecast-workbench-child data-v4-raw-audit>
      {#if children}
        {@render children()}
      {:else}
        <p class="empty-child">Forecast workbench child surface not supplied. No synthetic evidence is generated.</p>
      {/if}
    </div>
  </EvidenceDisclosure>
</section>

<style>
  .forecast-studio {
    display: grid;
    gap: 16px;
    width: min(100%, var(--content-max));
    margin-inline: auto;
    color: var(--fg);
  }

  .studio-intro,
  .contract-grid article,
  .workbench-child {
    border: 1px solid var(--border-faint);
    border-radius: 22px;
    background: color-mix(in oklab, var(--surface) 92%, transparent);
    box-shadow: var(--shadow-sm);
  }

  .studio-intro,
  .contract-grid article,
  .workbench-child {
    padding: 18px 20px;
  }

  .eyebrow,
  .contract-grid span {
    color: var(--accent-strong);
    font: 760 11px/1.2 var(--font-mono);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  h2,
  p {
    margin: 0;
  }

  h2,
  strong {
    color: var(--fg-strong);
  }

  h2 {
    margin-top: 6px;
    font: 780 clamp(24px, 4vw, 38px) / 1.05 var(--font-display);
    letter-spacing: -0.05em;
  }

  p {
    color: var(--muted);
    line-height: 1.55;
  }

  .studio-intro p {
    max-width: 88ch;
    margin-top: 10px;
  }

  .contract-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
  }

  .contract-grid article {
    display: grid;
    gap: 8px;
    align-content: start;
  }

  .contract-grid strong {
    font: 760 15px/1.2 var(--font-display);
  }

  .contract-grid p,
  .empty-child {
    font-size: 13px;
  }

  @media (max-width: 1100px) {
    .contract-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 720px) {
    .contract-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
