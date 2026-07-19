<script lang="ts">
  import { runLabel, typeLabel, typeTone } from '$lib/rlRows';
  import type { RlRunRecord } from '$lib/rlApi';

  interface Props {
    readonly runs: readonly RlRunRecord[];
    // Single-select contract (unchanged). Optional so a multi-select instance
    // can omit it, but every existing caller keeps compiling.
    readonly selectedName?: string;
    readonly onSelect?: (name: string) => void;
    // G4 — additive multi-select (compare/overlay picker). Default off keeps the
    // existing single-select behavior byte-identical.
    readonly multi?: boolean;
    readonly selectedNames?: readonly string[];
    readonly onToggle?: (name: string) => void;
    // Optional header overrides so a compare instance can label itself.
    readonly eyebrow?: string;
    readonly title?: string;
  }
  let {
    runs,
    selectedName = '',
    onSelect = () => {},
    multi = false,
    selectedNames = [],
    onToggle = () => {},
    eyebrow = 'RUN SELECTOR',
    title = '강화학습 산출물',
  }: Props = $props();

  const isActive = (name: string): boolean => (multi ? selectedNames.includes(name) : name === selectedName);
  function handleClick(name: string): void {
    if (multi) onToggle(name);
    else onSelect(name);
  }
</script>

<section class="card">
  <div class="card-header"><div><div class="card-eyebrow">{eyebrow}</div><div class="card-title">{title}</div></div></div>
  <div class="run-list">
    {#each runs as run}
      <button
        type="button"
        class:active={isActive(run.name)}
        aria-pressed={multi ? isActive(run.name) : undefined}
        onclick={() => handleClick(run.name)}
      >
        <span>{runLabel(run)}</span>
        <small class="pill {typeTone(run.artifact_type)}">{typeLabel(run.artifact_type)}</small>
      </button>
    {/each}
  </div>
</section>
