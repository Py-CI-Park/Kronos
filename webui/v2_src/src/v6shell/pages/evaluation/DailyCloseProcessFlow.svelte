<script lang="ts">
  import { onDestroy } from 'svelte';

  const steps = [
    { code: 'CLOSE', title: 'D일 공식 종가 확인', detail: '장 마감 후 공식 close snapshot을 관측합니다.', input: '거래일·종목코드·공식 OHLCV', output: 'D일 close snapshot', gate: '공식 종가와 가용시각이 모두 존재' },
    { code: 'PIT', title: 'PIT·available-at gate', detail: '시점별 종목군·가격 의미·가용시각이 없으면 즉시 BLOCK합니다.', input: '상장 이력·가격 의미·available_at', output: '시점 적격 종목군', gate: '미래 정보·상폐 생존 편향 없음' },
    { code: 'FREEZE', title: '특징 snapshot 고정', detail: 'feature 수·기간·source hash를 run identity에 묶습니다.', input: '적격 데이터·특징 사양', output: '불변 dataset identity', gate: '재현 가능한 source hash' },
    { code: 'POLICY', title: 'DQN/CQL 정책 추론', detail: '상태에서 cash·buy·hold·exit 행동 점수를 계산합니다.', input: '시장 상태·보유 슬롯·현금', output: '행동 점수와 선택', gate: '행동 마스크·정책 버전 고정' },
    { code: 'ALLOCATE', title: '6천만원·최대 10슬롯', detail: '주식 5천만원, 현금 1천만원, 슬롯당 약 5백만원을 유지합니다.', input: '선택 행동·현재 NAV', output: '주문 후보와 목표 금액', gate: '현금·슬롯·집중도 한도 준수' },
    { code: 'FILL', title: 'D+1 시가 체결', detail: 'D일 종가를 본 뒤 같은 종가에 체결하지 않습니다.', input: 'D일 결정·D+1 거래 가능성', output: '시장가정 체결 기록', gate: '동일 종가 체결과 체결 불가 종목 차단' },
    { code: 'COST', title: '비용 0.230% 반영', detail: '수수료·세금·슬리피지를 공통 % 단위로 차감합니다.', input: '매수·매도 체결 금액', output: '비용 차감 현금흐름', gate: '비용 가정과 적용 방향 명시' },
    { code: 'REWARD', title: 'reward·NAV 계산', detail: '경제 NAV 변화와 학습 reward를 분리 기록합니다.', input: '비용 반영 포트폴리오 경로', output: 'reward·NAV·drawdown', gate: 'reward와 경제 수익률을 별도 필드로 기록' },
    { code: 'EVIDENCE', title: 'event·metric·artifact 저장', detail: '실행 상세·비교·거버넌스 화면으로 증거를 연결합니다.', input: '실행 event·평가 metric', output: '검증 가능한 artifact 묶음', gate: 'OOS·대조군·해시·판정 보존' },
  ] as const;

  let active = $state(0);
  let playing = $state(false);
  let timer: ReturnType<typeof setInterval> | null = null;
  const selected = $derived(steps[active]);

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

  function selectStep(index: number): void {
    stop();
    active = index;
  }

  function focusStep(index: number): void {
    selectStep(index);
    requestAnimationFrame(() => {
      document.querySelector<HTMLButtonElement>(`[data-flow-step="${index}"]`)?.focus();
    });
  }

  function handleStepKey(event: KeyboardEvent, index: number): void {
    let target: number | null = null;
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') target = (index + 1) % steps.length;
    else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') target = (index - 1 + steps.length) % steps.length;
    else if (event.key === 'Home') target = 0;
    else if (event.key === 'End') target = steps.length - 1;
    if (target === null) return;
    event.preventDefault();
    focusStep(target);
  }

  onDestroy(stop);
</script>

<section class="flow" data-daily-close-flow>
  <header><div><p>TARGET CONTRACT · EXPLAINER</p><h2>POST_CLOSE_NEXT_OPEN</h2><span><b>1~9는 실행 진행률이 아니라 설계 계약의 순서입니다.</b> 각 단계를 누르면 입력·출력·통과 조건이 아래에 바뀝니다.</span></div><nav aria-label="프로세스 재생"><button type="button" onclick={playing ? stop : play}>{playing ? '일시정지' : '계약 재생'}</button><button type="button" onclick={next}>한 단계</button><button type="button" onclick={reset}>처음</button></nav></header>
  <ol role="tablist" aria-label="종가 매매 강화학습 계약 9단계">
    {#each steps as step, index}
      <li class:active={active === index} class:complete={index < active} aria-current={active === index ? 'step' : undefined}>
        <button class="step-button" data-flow-step={index} id={`flow-step-tab-${index}`} type="button" role="tab" aria-controls="flow-step-panel" aria-label={`${index + 1}단계 ${step.title} 상세 보기`} aria-selected={active === index} tabindex={active === index ? 0 : -1} onclick={() => selectStep(index)} onkeydown={(event) => handleStepKey(event, index)}>
          <span>{String(index + 1).padStart(2, '0')}</span><div><code>{step.code}</code><strong>{step.title}</strong><small>{step.detail}</small>{#if active === index}<em>선택됨 · 아래 상세 확인</em>{/if}</div>
        </button>
      </li>
    {/each}
  </ol>
  <div class="step-detail" id="flow-step-panel" role="tabpanel" aria-labelledby={`flow-step-tab-${active}`} aria-live="polite" aria-label="선택한 단계 상세">
    <div><span>선택 단계</span><strong>{active + 1}. {selected.title}</strong><p>{selected.detail}</p></div>
    <dl><div><dt>입력</dt><dd>{selected.input}</dd></div><div><dt>출력</dt><dd>{selected.output}</dd></div><div><dt>통과 조건</dt><dd>{selected.gate}</dd></div></dl>
  </div>
</section>

<style>
  .flow{min-width:0;border:1px solid var(--border);border-radius:14px;background:var(--surface-raised);overflow:hidden}.flow>header{display:flex;align-items:end;justify-content:space-between;gap:16px;padding:18px 20px;border-bottom:1px solid var(--border)}header p{margin:0;color:var(--accent);font:900 .58rem var(--font-mono);letter-spacing:.1em}header h2{margin:4px 0;color:var(--fg-strong);font-size:1.18rem}header span{display:block;max-width:760px;color:var(--muted);font-size:.72rem;line-height:1.55}header span b{color:var(--fg-strong)}nav{display:flex;gap:7px}button{border:1px solid var(--border-strong);border-radius:7px;padding:7px 9px;background:var(--surface-sunken);color:var(--fg);font-weight:800;cursor:pointer}ol{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0;margin:0;padding:0;list-style:none}li{position:relative;min-width:0;border-right:1px solid var(--border);border-bottom:1px solid var(--border);opacity:.7;transition:background .25s ease,opacity .25s ease}li:nth-child(3n){border-right:0}li:nth-last-child(-n+3){border-bottom:0}li.active{opacity:1;background:color-mix(in srgb,var(--accent) 16%,var(--surface-raised));box-shadow:inset 0 0 0 2px var(--accent)}li.complete{opacity:.84}.step-button{display:grid;grid-template-columns:auto 1fr;gap:11px;width:100%;height:100%;min-height:112px;border:0;border-radius:0;padding:15px;background:transparent;text-align:left}.step-button:hover,.step-button:focus-visible{background:color-mix(in srgb,var(--accent) 10%,transparent);outline:2px solid var(--accent);outline-offset:-3px}.step-button>span{display:grid;place-items:center;width:34px;height:34px;border:1px solid var(--border-strong);border-radius:50%;color:var(--muted);font:900 .7rem var(--font-mono)}li.active .step-button>span{border-color:var(--accent);background:var(--accent);color:var(--on-accent);animation:pulse 1s ease-in-out infinite}.step-button div{min-width:0;display:flex;flex-direction:column;gap:4px}code{color:var(--accent);font-size:.58rem}strong{color:var(--fg-strong);font-size:.8rem}small{color:var(--muted);font-size:.65rem;line-height:1.45}em{width:max-content;border-radius:999px;padding:3px 7px;background:var(--accent);color:var(--on-accent);font-size:.56rem;font-style:normal;font-weight:900}.step-detail{display:grid;grid-template-columns:minmax(220px,.8fr) minmax(0,1.5fr);gap:18px;padding:18px 20px;background:color-mix(in srgb,var(--accent) 9%,var(--surface-sunken));border-top:1px solid var(--border)}.step-detail>div>span{color:var(--accent);font:900 .56rem var(--font-mono)}.step-detail p{margin:5px 0 0;color:var(--muted);font-size:.7rem}.step-detail dl{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:0}.step-detail dl div{border-left:2px solid var(--border-strong);padding-left:9px}.step-detail dt{color:var(--dim);font:.56rem var(--font-mono)}.step-detail dd{margin:3px 0 0;color:var(--fg);font-size:.69rem;line-height:1.45}@keyframes pulse{50%{transform:scale(1.08)}}
  @media(max-width:900px){ol{grid-template-columns:1fr 1fr}li:nth-child(3n){border-right:1px solid var(--border)}li:nth-child(2n){border-right:0}li:nth-last-child(-n+3){border-bottom:1px solid var(--border)}li:last-child{border-bottom:0}.flow>header{align-items:start;flex-direction:column}.step-detail{grid-template-columns:1fr}.step-detail dl{grid-template-columns:1fr 1fr 1fr}}
  @media(max-width:560px){ol{grid-template-columns:1fr}li,li:nth-child(3n){border-right:0}.flow>header nav{width:100%}.flow>header button{flex:1}.step-detail dl{grid-template-columns:1fr}}
  @media(prefers-reduced-motion:reduce){li{transition:none}li.active .step-button>span{animation:none}}
</style>
