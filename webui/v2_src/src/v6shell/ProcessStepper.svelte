<script lang="ts">
  import type { V6StepDef } from './registry';

  let { steps, active, states, onSelect }: {
    steps: readonly V6StepDef[];
    active: string;
    states: Record<string, string | undefined>;
    onSelect: (id: string) => void;
  } = $props();

  function stateOf(id: string): string { return states[id] ?? 'MISSING'; }
  function stateClass(state: string): string {
    if (state === 'FROZEN' || state === 'HAS_RUNS' || state === 'HAS_REPORTS' || state === 'OK' || state === 'PARTIAL') return 'complete';
    if (state === 'NOT_RUN' || state === 'NOT_FROZEN') return 'waiting';
    if (state === 'MISSING' || state.startsWith('BLOCKED')) return 'blocked';
    return 'neutral';
  }
</script>

<div class="stepper" aria-label="강화학습 연구 단계">
  {#each steps as step, index}
    {@const state = stateOf(step.statusKey)}
    <button
      type="button"
      class:active={active === step.id}
      class={stateClass(state)}
      aria-current={active === step.id ? 'step' : undefined}
      onclick={() => onSelect(step.id)}
    >
      <span class="step-number">STEP {index + 1}</span>
      <strong>{step.labelKo}</strong>
      <span class="chip">{state}</span>
    </button>
  {/each}
</div>

<style>
  .stepper { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 10px; width: 100%; }
  button { min-width: 0; min-height: 118px; display: flex; flex-direction: column; align-items: flex-start; gap: 9px; border: 1px solid var(--border-strong); border-radius: 12px; padding: 14px; background: var(--surface-raised); color: var(--fg); font: inherit; text-align: left; cursor: pointer; transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease; }
  button:hover { transform: translateY(-2px); box-shadow: 0 8px 18px var(--shadow); }
  button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  button.active { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-soft), 0 8px 18px var(--shadow); transform: translateY(-2px); }
  .step-number { color: var(--muted); font-size: .68rem; font-weight: 800; letter-spacing: .09em; }
  strong { color: var(--fg-strong); font-size: 1rem; line-height: 1.25; }
  .chip { margin-top: auto; border: 1px solid currentColor; border-radius: 999px; padding: 3px 7px; font-size: .68rem; font-weight: 800; overflow-wrap: anywhere; }
  .complete { border-color: var(--success); background: var(--success-soft); }
  .complete .chip { color: var(--success); }
  .waiting .chip, .neutral .chip { color: var(--muted); }
  .blocked { border-color: var(--danger); background: var(--danger-soft); }
  .blocked .chip { color: var(--danger); }
  @media (max-width: 900px) { .stepper { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
  @media (max-width: 560px) { .stepper { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
