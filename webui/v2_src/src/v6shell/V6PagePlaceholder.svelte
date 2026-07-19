<script lang="ts">
  import type { V6PageDef } from './registry';

  let { page }: { page: V6PageDef } = $props();
  const workflowSteps = [1, 2, 3, 4, 5, 6, 7];
</script>

<section class="placeholder" aria-labelledby="v6-page-title">
  <p class="eyebrow">{page.label}</p>
  <h1 id="v6-page-title">{page.labelKo} <span>/ {page.label}</span></h1>
  <p class="description">{page.description}</p>
  <p class="status"><strong>NOT_BUILT</strong></p>
  <p class="notice">이 페이지는 V6 계획의 해당 세션에서 구현됩니다. 지금 상태는 미구현이며 어떤 결과도 생성되지 않았습니다.</p>

  {#if page.step !== null}
    <section class="stepper" aria-label="7단계 워크플로">
      <h2>7단계 워크플로</h2>
      <ol>
        {#each workflowSteps as step}
          <li class:current={step === page.step}>
            <span class="step-number">{step}</span>
            <span>{step === page.step ? '현재 페이지' : `단계 ${step}`}</span>
            <small>NOT_BUILT</small>
          </li>
        {/each}
      </ol>
    </section>
  {/if}
</section>

<style>
  .placeholder { max-width: 920px; border: 1px solid #334155; border-radius: 14px; padding: clamp(20px, 4vw, 40px); background: #111827; color: #e5e7eb; }
  .eyebrow { margin: 0; color: #94a3b8; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase; }
  h1 { margin: 8px 0 12px; font-size: clamp(1.65rem, 5vw, 2.5rem); line-height: 1.15; color: #f8fafc; }
  h1 span { color: #94a3b8; font-size: 0.56em; font-weight: 500; white-space: nowrap; }
  .description, .notice { max-width: 690px; line-height: 1.6; }
  .description { color: #cbd5e1; }
  .notice { color: #fde68a; }
  .status strong { display: inline-block; border: 1px solid #f59e0b; border-radius: 999px; padding: 3px 8px; color: #fcd34d; font-size: 0.75rem; letter-spacing: 0.06em; }
  .stepper { margin-top: 28px; padding-top: 18px; border-top: 1px solid #334155; }
  h2 { margin: 0 0 12px; font-size: 1rem; }
  ol { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 6px; margin: 0; padding: 0; list-style: none; }
  li { min-width: 0; padding: 8px 4px; border: 1px solid #475569; border-radius: 8px; text-align: center; color: #94a3b8; font-size: 0.7rem; }
  li.current { border-color: #38bdf8; background: #0c4a6e; color: #e0f2fe; }
  .step-number, small { display: block; }
  .step-number { font-weight: 800; font-size: 1rem; }
  small { margin-top: 4px; color: #fbbf24; font-size: 0.59rem; }
  @media (max-width: 520px) {
    ol { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  }
</style>
