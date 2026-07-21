<script lang="ts">
  import { theme, toggleTheme } from '$lib/stores';
  import { V6_SCALES, V6_THEMES, v6Scale, v6Theme, type V6Scale, type V6ThemeId } from '../v6Theme';
  let currentTheme = $state<'light' | 'dark'>('light');
  theme.subscribe((value) => (currentTheme = value));
  function selectTheme(id: V6ThemeId): void { v6Theme.set(id); }
  function selectScale(scale: V6Scale): void { v6Scale.set(scale); }
</script>

<section class="page" aria-labelledby="settings-title">
  <header><p class="eyebrow">V6 RESEARCH ENVIRONMENT</p><h1 id="settings-title">설정</h1><p>표시 환경과 연구 레인 안내만 제공합니다. 이 화면은 서버 상태나 연구 기록을 변경하지 않습니다.</p></header>
  <div class="cards">
    <section class="card" aria-labelledby="v6-theme-title"><h2 id="v6-theme-title">V6 테마</h2><p>V6 화면에만 적용되는 색 구성입니다. V3/V5 화면은 영향을 받지 않습니다.</p><div class="choices" role="group" aria-label="V6 테마 선택">{#each V6_THEMES as item}<button type="button" class:chosen={$v6Theme === item.id} aria-pressed={$v6Theme === item.id} onclick={() => selectTheme(item.id)}><span class="swatch {item.id}"></span>{item.labelKo}</button>{/each}</div></section>
    <section class="card" aria-labelledby="v6-scale-title"><h2 id="v6-scale-title">글자·요소 크기</h2><p>넓은 모니터에서 시야 거리에 맞춰 V6 전체 배율을 조절합니다.</p><div class="choices" role="group" aria-label="V6 배율 선택">{#each V6_SCALES as scale}<button type="button" class:chosen={$v6Scale === scale} aria-pressed={$v6Scale === scale} onclick={() => selectScale(scale)}>{Math.round(scale * 100)}%</button>{/each}</div></section>
    <section class="card" aria-labelledby="theme-title"><h2 id="theme-title">전역 테마</h2><p>현재 상태: <strong>{currentTheme === 'light' ? '라이트' : '다크'} 테마</strong> · V6 테마가 "전역 따름"일 때 적용됩니다.</p><button type="button" class="wide" onclick={toggleTheme} aria-pressed={currentTheme === 'dark'}>{currentTheme === 'light' ? '다크 테마로 전환' : '라이트 테마로 전환'}</button></section>
    <section class="card" aria-labelledby="shell-title"><h2 id="shell-title">Shell 안내</h2><p>V6가 8122 기본 대시보드입니다. 과거 V3/V5 화면은 검증·비교를 위한 명시적 rollback 경로로 유지됩니다.</p><div class="shell-links"><a href="/?ui=v6&tab=home">V6 기본</a><a href="/?ui=v3">V3 rollback</a><a href="/?ui=v5">V5.1 연구 뷰어</a></div></section>
    <section class="card safety" aria-labelledby="safety-title"><h2 id="safety-title">안전 안내</h2><p>V6는 read-only 연구 플랫폼입니다. 주문·브로커·수익 기능이 없으며, 투자 실행이나 수익을 제공하지 않습니다.</p></section>
  </div>
</section>

<style>
  .page { width: 100%; color: var(--fg); } header, .card { border: 1px solid var(--border); border-radius: 14px; padding: clamp(18px, 4vw, 30px); background: var(--surface); } .eyebrow { margin: 0; color: var(--accent); font-size: .82rem; font-weight: 800; letter-spacing: .1em; } h1 { margin: 7px 0; color: var(--fg-strong); font-size: clamp(1.9rem, 6vw, 2.7rem); } h2 { margin: 0 0 10px; color: var(--fg-strong); font-size: 1.2rem; } header > p:last-child, .card > p { color: var(--muted); line-height: 1.6; font-size: 1.05rem; } .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; margin-top: 18px; } button, .shell-links a { border: 1px solid var(--accent); border-radius: 7px; padding: 12px 16px; background: transparent; color: var(--accent-strong); font: inherit; font-size: 1.02rem; font-weight: 700; text-decoration: none; cursor: pointer; } .wide, .shell-links a { background: var(--accent-soft); } button:hover, .shell-links a:hover { border-color: var(--warn); } button:focus-visible, .shell-links a:focus-visible { outline: 2px solid var(--warn); outline-offset: 3px; } .shell-links { display: flex; flex-wrap: wrap; gap: 10px; } .safety { border-color: var(--warn); background: var(--warn-soft); } .safety p { color: var(--warn); }
  .choices { display: flex; flex-wrap: wrap; gap: 10px; } .choices button { display: inline-flex; align-items: center; gap: 8px; border-color: var(--border-strong); color: var(--fg); } .choices button.chosen { border-color: var(--accent); background: var(--accent-soft); color: var(--accent-strong); box-shadow: 0 0 0 2px var(--accent-soft); }
  .swatch { width: 16px; height: 16px; border: 1px solid var(--border-strong); border-radius: 50%; } .swatch.inherit { background: linear-gradient(135deg, #ffffff 50%, #1c2534 50%); } .swatch.dark { background: #232a3a; } .swatch.ocean { background: linear-gradient(135deg, #0d3550, #4cc9f0); } .swatch.forest { background: linear-gradient(135deg, #0a281d, #52d19b); } .swatch.quant-terminal { background: linear-gradient(135deg, #0a0a0a, #00e08a); }
</style>
