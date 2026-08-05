<script lang="ts">
  import { onDestroy } from 'svelte';

  const steps = [
    { code: 'CLOSE', title: 'D일 공식 종가 확인', detail: '장 마감 후 공식 close snapshot을 관측합니다.' },
    { code: 'PIT', title: 'PIT·available-at gate', detail: '시점별 종목군·가격 의미·가용시각이 없으면 즉시 BLOCK합니다.' },
    { code: 'FREEZE', title: '특징 snapshot 고정', detail: 'feature 수·기간·source hash를 run identity에 묶습니다.' },
    { code: 'POLICY', title: 'DQN/CQL 정책 추론', detail: '상태에서 cash·buy·hold·exit 행동 점수를 계산합니다.' },
    { code: 'ALLOCATE', title: '6천만원·최대 10슬롯', detail: '주식 5천만원, 현금 1천만원, 슬롯당 약 5백만원을 유지합니다.' },
    { code: 'FILL', title: 'D+1 시가 체결', detail: 'D일 종가를 본 뒤 같은 종가에 체결하지 않습니다.' },
    { code: 'COST', title: '비용 0.230% 반영', detail: '수수료·세금·슬리피지를 공통 % 단위로 차감합니다.' },
    { code: 'REWARD', title: 'reward·NAV 계산', detail: '경제 NAV 변화와 학습 reward를 분리 기록합니다.' },
    { code: 'EVIDENCE', title: 'event·metric·artifact 저장', detail: '실행 상세·비교·거버넌스 화면으로 증거를 연결합니다.' },
  ] as const;

  let active = $state(0);
  let playing = $state(false);
  let timer: ReturnType<typeof setInterval> | null = null;

  function stop(): void {
    if (timer !== null) clearInterval(timer);
    timer = null;
    playing = false;
  }

  function next(): void {
    active = (active + 1) % steps.length;
  }

  function play(): void {
    if (typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches) {
      next();
      return;
    }
    stop();
    playing = true;
    timer = setInterval(next, 950);
  }

  function reset(): void {
    stop();
    active = 0;
  }

  onDestroy(stop);
</script>

<section class="flow" data-daily-close-flow>
  <header><div><p>TARGET CONTRACT · EXPLAINER</p><h2>POST_CLOSE_NEXT_OPEN</h2><span>당일 공식 종가 관측 후 같은 종가 체결 금지 · 교육용 계약 흐름이며 실제 실행 진행률이나 수익 모델 성공 증거가 아님</span></div><nav aria-label="프로세스 재생"><button type="button" onclick={playing ? stop : play}>{playing ? '일시정지' : '계약 재생'}</button><button type="button" onclick={next}>한 단계</button><button type="button" onclick={reset}>처음</button></nav></header>
  <ol>
    {#each steps as step, index}
      <li class:active={active === index} class:complete={index < active} aria-current={active === index ? 'step' : undefined}>
        <span>{String(index + 1).padStart(2, '0')}</span><div><code>{step.code}</code><strong>{step.title}</strong><small>{step.detail}</small></div>
      </li>
    {/each}
  </ol>
</section>

<style>
  .flow{min-width:0;border:1px solid var(--border);border-radius:14px;background:var(--surface-raised);overflow:hidden}.flow>header{display:flex;align-items:end;justify-content:space-between;gap:16px;padding:16px 18px;border-bottom:1px solid var(--border)}header p{margin:0;color:var(--accent);font:900 .58rem var(--font-mono);letter-spacing:.1em}header h2{margin:4px 0;color:var(--fg-strong);font-size:1.1rem}header span{color:var(--muted);font-size:.7rem}nav{display:flex;gap:7px}button{border:1px solid var(--border-strong);border-radius:7px;padding:7px 9px;background:var(--surface-sunken);color:var(--fg);font-weight:800;cursor:pointer}ol{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0;margin:0;padding:0;list-style:none}li{position:relative;display:grid;grid-template-columns:auto 1fr;gap:10px;min-width:0;padding:14px;border-right:1px solid var(--border);border-bottom:1px solid var(--border);opacity:.62;transition:background .25s ease,opacity .25s ease}li:nth-child(3n){border-right:0}li:nth-last-child(-n+3){border-bottom:0}li.active{opacity:1;background:color-mix(in srgb,var(--accent) 12%,var(--surface-raised))}li.complete{opacity:.82}li>span{display:grid;place-items:center;width:28px;height:28px;border:1px solid var(--border-strong);border-radius:50%;color:var(--muted);font:800 .62rem var(--font-mono)}li.active>span{border-color:var(--accent);background:var(--accent);color:var(--on-accent);animation:pulse 1s ease-in-out infinite}li div{min-width:0;display:flex;flex-direction:column;gap:3px}code{color:var(--accent);font-size:.56rem}strong{color:var(--fg-strong);font-size:.77rem}small{color:var(--muted);font-size:.64rem;line-height:1.45}@keyframes pulse{50%{transform:scale(1.08)}}
  @media(max-width:900px){ol{grid-template-columns:1fr 1fr}li:nth-child(3n){border-right:1px solid var(--border)}li:nth-child(2n){border-right:0}li:nth-last-child(-n+3){border-bottom:1px solid var(--border)}li:last-child{border-bottom:0}.flow>header{align-items:start;flex-direction:column}}
  @media(max-width:560px){ol{grid-template-columns:1fr}li,li:nth-child(3n){border-right:0}.flow>header nav{width:100%}.flow>header button{flex:1}}
  @media(prefers-reduced-motion:reduce){li{transition:none}li.active>span{animation:none}}
</style>
