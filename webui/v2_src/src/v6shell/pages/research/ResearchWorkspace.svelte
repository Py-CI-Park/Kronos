<script lang="ts">
  import { onMount } from 'svelte';
  import ResearchLibraryPage from './ResearchLibraryPage.svelte';
  import RunDetailPage from './RunDetailPage.svelte';

  let selectedRunId = $state<string | null>(null);

  function readLocation(): void {
    const params = new URLSearchParams(window.location.search);
    selectedRunId = params.get('run');
  }

  function selectRun(runId: string): void {
    const params = new URLSearchParams({ ui: 'v6', tab: 'research' });
    params.set('run', runId);
    history.pushState(history.state, '', `/?${params.toString()}`);
    selectedRunId = runId;
  }

  function showLibrary(): void {
    history.pushState(history.state, '', '/?ui=v6&tab=research');
    selectedRunId = null;
  }

  onMount(() => {
    readLocation();
    window.addEventListener('popstate', readLocation);
    return () => window.removeEventListener('popstate', readLocation);
  });
</script>

<section data-research-workspace>
  {#if selectedRunId === null}
    <ResearchLibraryPage onSelect={selectRun} />
  {:else}
    <RunDetailPage runId={selectedRunId} onBack={showLibrary} />
  {/if}
</section>

<style>
  section{min-width:0;width:100%}
</style>
