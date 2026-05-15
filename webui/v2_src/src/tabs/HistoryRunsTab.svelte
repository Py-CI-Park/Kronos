<script lang="ts">
  import { activeTab } from '$lib/stores';
</script>

<div class="bg-card border border-border rounded-lg p-4">
  <h2 class="text-accent-subtle text-[15px] font-semibold m-0 mb-3">기록 & 런</h2>
  <div class="text-text-muted text-[12px] leading-relaxed">
    현재 손실 곡선은
    <button type="button" class="text-info hover:underline" onclick={() => activeTab.set('live-training')}>실시간 학습</button>
    탭에서 확인할 수 있습니다.<br>
    전체 런 목록과 기록 패널은 <strong>P2</strong>에서 정식 추가됩니다. 그 전에는
    <a class="text-info hover:underline" href="/training">기존 학습 모니터</a>를 이용하세요.
  </div>
</div>
