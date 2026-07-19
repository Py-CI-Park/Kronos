<script lang="ts">
  import { theme, toggleTheme } from '$lib/stores';

  let currentTheme = $state<'light' | 'dark'>('light');
  theme.subscribe((value) => (currentTheme = value));
</script>

<section class="page" aria-labelledby="settings-title">
  <header>
    <p class="eyebrow">V6 RESEARCH ENVIRONMENT</p>
    <h1 id="settings-title">설정</h1>
    <p>표시 환경과 연구 레인 안내만 제공합니다. 이 화면은 서버 상태나 연구 기록을 변경하지 않습니다.</p>
  </header>

  <section class="card" aria-labelledby="theme-title">
    <h2 id="theme-title">테마</h2>
    <p>현재 상태: <strong>{currentTheme === 'light' ? '라이트' : '다크'} 테마</strong></p>
    <button type="button" onclick={toggleTheme} aria-pressed={currentTheme === 'dark'}>
      {currentTheme === 'light' ? '다크 테마로 전환' : '라이트 테마로 전환'}
    </button>
  </section>

  <section class="card" aria-labelledby="shell-title">
    <h2 id="shell-title">Shell 안내</h2>
    <p>V3가 기본 대시보드입니다. V6는 연구 워크플로를 분리해 살펴보는 읽기 전용 레인입니다.</p>
    <div class="shell-links">
      <a href="/">V3 기본</a>
      <a href="/?ui=v5">V5.1 연구 뷰어</a>
    </div>
  </section>

  <section class="card safety" aria-labelledby="safety-title">
    <h2 id="safety-title">안전 안내</h2>
    <p>V6는 read-only 연구 플랫폼입니다. 주문·브로커·수익 기능이 없으며, 투자 실행이나 수익을 제공하지 않습니다.</p>
  </section>
</section>

<style>
  .page { max-width: 880px; color: var(--fg); }
  header, .card { border: 1px solid var(--border); border-radius: 14px; padding: clamp(16px, 4vw, 28px); background: var(--surface); }
  .eyebrow { margin: 0; color: var(--accent); font-size: .72rem; font-weight: 800; letter-spacing: .1em; }
  h1 { margin: 7px 0; color: var(--fg-strong); font-size: clamp(1.7rem, 6vw, 2.5rem); }
  h2 { margin: 0 0 10px; color: var(--fg-strong); font-size: 1.1rem; }
  header > p:last-child, .card > p { color: var(--muted); line-height: 1.6; }
  .card { margin-top: 16px; }
  button, .shell-links a { border: 1px solid var(--accent); border-radius: 7px; padding: 9px 12px; background: var(--accent-soft); color: var(--accent-strong); font: inherit; font-weight: 700; text-decoration: none; cursor: pointer; }
  button:hover, .shell-links a:hover { border-color: var(--warn); background: var(--accent-soft); }
  button:focus-visible, .shell-links a:focus-visible { outline: 2px solid var(--warn); outline-offset: 3px; }
  .shell-links { display: flex; flex-wrap: wrap; gap: 10px; }
  .safety { border-color: var(--warn); background: var(--warn-soft); }
  .safety p { color: var(--warn); }
</style>
