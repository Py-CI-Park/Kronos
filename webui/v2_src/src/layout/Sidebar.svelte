<script lang="ts">
  import { activeTab } from '$lib/stores';

  const groups: { label: string; items: { id: string; label: string; icon: string }[] }[] = [
    {
      label: '학습',
      items: [
        { id: 'live-training', label: '실시간 학습', icon: '📡' },
        { id: 'forecast', label: '예측 워크벤치', icon: '🤖' },
      ],
    },
    {
      label: '분석',
      items: [
        { id: 'stom', label: 'STOM 진단', icon: '📊' },
        { id: 'artifacts', label: '아티팩트 & 모델', icon: '📁' },
        { id: 'history', label: '기록 & 런', icon: '📜' },
      ],
    },
    {
      label: '시스템',
      items: [
        { id: 'system-health', label: '시스템 상태', icon: '🖥' },
        { id: 'settings', label: '설정', icon: '⚙️' },
      ],
    },
  ];

  let current = $state('live-training');
  activeTab.subscribe((v) => (current = v));

  function pick(id: string) {
    activeTab.set(id);
  }
</script>

<nav class="md:w-[200px] w-full md:border-r md:border-b-0 border-b border-border bg-card-raised flex md:flex-col flex-row md:overflow-y-auto overflow-x-auto md:py-5 py-2 md:px-0 px-3 md:gap-0 gap-1 shrink-0">
  {#each groups as g}
    <div class="hidden md:block px-[18px] pb-2 text-[10px] uppercase tracking-wide text-text-faint font-bold mt-2">
      {g.label}
    </div>
    {#each g.items as item}
      <button
        data-tab={item.id}
        aria-current={current === item.id ? 'page' : undefined}
        class="text-left flex items-center gap-2 md:py-[10px] py-[8px] md:px-[18px] px-3 text-[13px] font-semibold border-l-[3px] md:border-b-0 border-b-2 border-transparent transition-colors duration-base whitespace-nowrap shrink-0
          {current === item.id ? 'text-accent md:border-l-accent border-b-accent bg-accent/[.08]' : 'text-text-muted hover:text-text hover:bg-accent/[.05]'}"
        onclick={() => pick(item.id)}
      >
        <span class="text-[15px] w-[18px] text-center">{item.icon}</span>
        <span>{item.label}</span>
      </button>
    {/each}
  {/each}
</nav>
