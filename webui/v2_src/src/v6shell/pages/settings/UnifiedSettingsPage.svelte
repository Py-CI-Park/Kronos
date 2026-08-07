<script lang="ts">
  import { theme, toggleTheme } from '$lib/stores';
  import PageHeader from '../../components/shell/PageHeader.svelte';
  import ResearchPanel from '../../components/shell/ResearchPanel.svelte';
  import StateMatrix, { type StateItem } from '../../components/shell/StateMatrix.svelte';
  import { V6_SCALES, V6_THEMES, v6Scale, v6Theme, type V6Scale, type V6ThemeId } from '../../v6Theme';

  const safety: readonly StateItem[] = [
    { label: 'DATA MUTATION', state: 'BLOCKED', detail: '표시 설정은 DB·artifact·연구 결과를 변경하지 않습니다.', tone: 'ok' },
    { label: 'FRESH OOS', state: 'SEALED', detail: '설정 화면에서 개봉하거나 승인할 수 없습니다.', tone: 'warning' },
    { label: '주문 권한', state: 'NOT AVAILABLE', detail: '브로커 연결·매수·매도 기능은 제공하지 않습니다.', tone: 'danger' },
    { label: 'PREFERENCE STORAGE', state: 'LOCAL ONLY', detail: '테마와 화면 배율만 브라우저 로컬 저장소에 보관합니다.', tone: 'neutral' },
  ];
  const selectTheme = (id: V6ThemeId): void => v6Theme.set(id);
  const selectScale = (scale: V6Scale): void => v6Scale.set(scale);
</script>

<div class="settings v6-page" data-unified-settings>
  <PageHeader eyebrow="DISPLAY & ACCESSIBILITY" title="설정" description="연구 근거는 건드리지 않고 테마, 글자 배율과 과거 화면 접근만 관리합니다." status="LOCAL PREFERENCE" />
  <div class="grid">
    <ResearchPanel title="V6 테마" description="통합 8개 페이지에 같은 디자인 토큰을 적용합니다.">
      <div class="choices" role="group" aria-label="V6 테마 선택">{#each V6_THEMES as item}<button type="button" class:chosen={$v6Theme === item.id} aria-pressed={$v6Theme === item.id} onclick={() => selectTheme(item.id)}><span class="swatch {item.id}"></span>{item.labelKo}</button>{/each}</div>
    </ResearchPanel>
    <ResearchPanel title="글자·화면 배율" description="작은 화면 또는 고해상도 모니터에 맞춰 조절합니다.">
      <div class="choices" role="group" aria-label="V6 화면 배율 선택">{#each V6_SCALES as scale}<button type="button" class:chosen={$v6Scale === scale} aria-pressed={$v6Scale === scale} onclick={() => selectScale(scale)}>{Math.round(scale * 100)}%</button>{/each}</div>
      <p class="scale-preview" aria-live="polite"><span>현재 적용</span><strong>{Math.round($v6Scale * 100)}%</strong><small>선택 즉시 8개 공식 페이지의 rem 기반 글자와 간격에 적용됩니다.</small></p>
    </ResearchPanel>
    <ResearchPanel title="전역 명암" description={`현재 ${$theme === 'light' ? '라이트' : '다크'} 테마입니다.`}><button type="button" class="wide" onclick={toggleTheme} aria-pressed={$theme === 'dark'}>{$theme === 'light' ? '다크 테마로 전환' : '라이트 테마로 전환'}</button></ResearchPanel>
    <ResearchPanel title="과거 화면" description="V3·V5.1은 비교·복구용이며 V6가 공식 연구 뷰어입니다."><nav><a href="/?ui=v6">V6 통합 대시보드</a><a href="/?ui=v3">V3 복구 화면</a><a href="/?ui=v5">V5.1 연구 뷰어</a></nav></ResearchPanel>
  </div>
  <ResearchPanel title="안전 경계" description="UI preference와 연구·운영 권한을 분리합니다."><StateMatrix items={safety} /></ResearchPanel>
</div>

<style>
  .settings{display:flex;flex-direction:column;gap:16px;min-width:0}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.choices,nav{display:flex;flex-wrap:wrap;gap:9px}button,a{display:inline-flex;align-items:center;gap:8px;max-width:100%;border:1px solid var(--border-strong);border-radius:8px;padding:10px 12px;background:var(--surface-sunken);color:var(--fg);font:700 .72rem inherit;text-decoration:none;cursor:pointer}button.chosen,.wide{border-color:var(--accent);background:var(--accent-soft);color:var(--accent-strong)}button:focus-visible,a:focus-visible{outline:2px solid var(--warn);outline-offset:2px}.swatch{width:15px;height:15px;border:1px solid var(--border-strong);border-radius:50%}.swatch.inherit{background:linear-gradient(135deg,#fff 50%,#1c2534 50%)}.swatch.dark{background:#232a3a}.swatch.ocean{background:linear-gradient(135deg,#0d3550,#4cc9f0)}.swatch.forest{background:linear-gradient(135deg,#0a281d,#52d19b)}.swatch.quant-terminal{background:linear-gradient(135deg,#0a0a0a,#00e08a)}
  .scale-preview{display:grid;grid-template-columns:1fr auto;gap:4px 12px;margin:14px 0 0;border-top:1px solid var(--border);padding-top:12px}.scale-preview span,.scale-preview small{color:var(--muted);font-size:.66rem}.scale-preview strong{color:var(--accent-strong);font:900 1rem var(--font-mono)}.scale-preview small{grid-column:1/-1}
  @media(max-width:800px){.grid{grid-template-columns:1fr}}@media(max-width:420px){.choices,nav{display:grid;grid-template-columns:1fr}.choices button,nav a,.wide{width:100%}}
</style>
