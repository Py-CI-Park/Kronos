<script lang="ts">
  import { onMount } from 'svelte';
  import { rlApi, type V5ReadonlyRouteRootMap } from '$lib/rlApi';
  import {
    LEARNING_NOW_ACCOUNTING_LABELS,
    LEARNING_NOW_COST_COMPONENTS,
    LEARNING_NOW_GOVERNANCE_LABELS,
    LEARNING_NOW_ROUTE_PATHS,
    LEARNING_NOW_UX_REVISION,
    LEARNING_NOW_SOURCE_PROTOCOL_LABEL,
    LOCK_KEYS,
    V5_MATRIX_COLUMNS,
    assessRunLiveness,
    auditProgress,
    buildDownloadPolicy,
    bindLearningNowIdentityRevision,
    buildEvidenceReceipt,
    classifyLearningNowFailure,
    createLearningNowLoadStamp,
    extractRunIdentity,
    findScorecardArtifactSha256,
    formatPercent,
    formatBasisPoints,
    reconcileLedger,
    isLearningNowRunUid,
    parseLearningNowRevision,
    selectLearningNowCandidate,
    shouldApplyLearningNowResult,
    summarizeGovernance,
    summarizeMatrix,
    type LearningNowFailure,
    type LearningNowRunCandidate,
    type LearningNowLoadStamp,
    type LearningNowRunIdentity,
  } from './learningNow';

  type RunsRoot = V5ReadonlyRouteRootMap['RUNS'];
  type RunDetailRoot = V5ReadonlyRouteRootMap['RUN_DETAIL'];
  type EventsRoot = V5ReadonlyRouteRootMap['EVENTS'];
  type MatrixRoot = V5ReadonlyRouteRootMap['MATRIX'];
  type LedgerRoot = V5ReadonlyRouteRootMap['LEDGER'];
  type ArtifactsRoot = V5ReadonlyRouteRootMap['ARTIFACTS'];
  type D0Root = V5ReadonlyRouteRootMap['D0'];
  type D1Root = V5ReadonlyRouteRootMap['D1'];
  type FixtureRoot = V5ReadonlyRouteRootMap['FIXTURE'];

  type CardKey = 'runs' | 'fixture' | 'matrix' | 'ledger' | 'd0' | 'd1' | 'detail' | 'events' | 'artifacts';
  type CardStatus = 'idle' | 'loading' | 'ready' | 'blocked' | 'error' | 'conflict';
  type CardState = {
    readonly status: CardStatus;
    readonly code: string;
    readonly message: string;
    readonly retryable: boolean;
  };

  const cardLabels: Record<CardKey, string> = {
    runs: 'runs list',
    fixture: 'fixture loopback',
    matrix: 'seed/fold matrix',
    ledger: 'ledger',
    d0: 'D0 price basis',
    d1: 'D1 universe',
    detail: 'run detail',
    events: 'run events',
    artifacts: 'artifact boundary',
  };

  const idleCard = (message = 'Not requested yet.'): CardState => ({
    status: 'idle',
    code: 'IDLE',
    message,
    retryable: false,
  });
  const loadingCard = (): CardState => ({ status: 'loading', code: 'LOADING', message: 'Loading V5 route.', retryable: false });
  const readyCard = (message = 'V5 route validated and frozen.'): CardState => ({
    status: 'ready',
    code: 'READY',
    message,
    retryable: false,
  });
  const blockedCard = (code: string, message: string): CardState => ({ status: 'blocked', code, message, retryable: false });
  const failedCard = (failure: LearningNowFailure): CardState => ({
    status: failure.code === 'CONFLICT_409' ? 'conflict' : 'error',
    code: failure.code,
    message: failure.message,
    retryable: failure.retryable,
  });
  const initialCards = (): Record<CardKey, CardState> => ({
    runs: idleCard(),
    fixture: idleCard(),
    matrix: idleCard('Blocked until an immutable run revision is present.'),
    ledger: idleCard('Blocked until an immutable run revision is present.'),
    d0: idleCard(),
    d1: idleCard(),
    detail: idleCard('Blocked until an immutable run revision is present.'),
    events: idleCard('Blocked until an immutable run revision is present.'),
    artifacts: idleCard('Blocked until an immutable run revision is present.'),
  });
  const runScopedCardKeys = ['detail', 'events', 'matrix', 'ledger', 'artifacts'] as const;

  let runsRoot = $state<RunsRoot | null>(null);
  let fixtureRoot = $state<FixtureRoot | null>(null);
  let detailRoot = $state<RunDetailRoot | null>(null);
  let eventsRoot = $state<EventsRoot | null>(null);
  let matrixRoot = $state<MatrixRoot | null>(null);
  let ledgerRoot = $state<LedgerRoot | null>(null);
  let artifactsRoot = $state<ArtifactsRoot | null>(null);
  let d0Root = $state<D0Root | null>(null);
  let d1Root = $state<D1Root | null>(null);
  let requestedUid = $state<string | null>(null);
  let selectedRunId = $state<string | null>(null);
  let requestedRevision = $state<number | null>(null);
  let cards = $state<Record<CardKey, CardState>>(initialCards());
  let copyStatus = $state('Evidence receipt not copied.');
  let receiptPreview = $state('');
  let baseSequence = 0;
  let runSequence = 0;
  let activeRunStamp = $state<LearningNowLoadStamp | null>(null);

  const selection = $derived(selectLearningNowCandidate(runsRoot, fixtureRoot, { uid: requestedUid, runId: selectedRunId, revision: requestedRevision }));
  const selectedCandidate = $derived(selection.selected);
  const candidateIdentity = $derived(bindLearningNowIdentityRevision(selectedCandidate?.identity ?? extractRunIdentity(null), requestedRevision));
  const selectedRun = $derived(detailRoot?.run ?? selectedCandidate?.run ?? null);
  const selectedIdentity = $derived(
    detailRoot
      ? bindLearningNowIdentityRevision(extractRunIdentity(detailRoot.run, detailRoot), candidateIdentity.revision)
      : candidateIdentity,
  );
  const sourceSha256 = $derived(
    detailRoot?.source.source_sha256
      ?? artifactsRoot?.source.source_sha256
      ?? ledgerRoot?.source.source_sha256
      ?? matrixRoot?.source.source_sha256
      ?? selectedCandidate?.sourceSha256
      ?? runsRoot?.source.source_sha256
      ?? fixtureRoot?.source.source_sha256
      ?? d0Root?.source.source_sha256
      ?? d1Root?.source.source_sha256
      ?? null,
  );
  const generatedAt = $derived(
    detailRoot?.source.generated_at
      ?? artifactsRoot?.source.generated_at
      ?? ledgerRoot?.source.generated_at
      ?? matrixRoot?.source.generated_at
      ?? runsRoot?.source.generated_at
      ?? fixtureRoot?.source.generated_at
      ?? d0Root?.source.generated_at
      ?? d1Root?.source.generated_at
      ?? null,
  );
  const locks = $derived(detailRoot?.locks ?? artifactsRoot?.locks ?? ledgerRoot?.locks ?? matrixRoot?.locks ?? runsRoot?.locks ?? fixtureRoot?.locks ?? d0Root?.locks ?? d1Root?.locks ?? null);
  const selectedFixtureUid = $derived(selectedCandidate?.fixtureUid ?? fixtureRoot?.fixture.fixture_id ?? null);
  const liveness = $derived(assessRunLiveness(selectedRun));
  const progress = $derived(auditProgress(selectedRun?.state.progress));
  const matrixSummary = $derived(summarizeMatrix(matrixRoot));
  const ledger = $derived(reconcileLedger(ledgerRoot));
  const governance = $derived(summarizeGovernance(d0Root, d1Root, locks));
  const scorecardArtifactSha256 = $derived(findScorecardArtifactSha256(artifactsRoot));
  const downloadPolicy = $derived(buildDownloadPolicy(artifactsRoot, selectedIdentity));
  const costComponentsLabel = $derived(`${LEARNING_NOW_COST_COMPONENTS.map((component) => `${component.id}=${formatBasisPoints(component.basisPoints)}`).join(' + ')} = ${formatBasisPoints(LEARNING_NOW_COST_COMPONENTS.reduce((total, component) => total + component.basisPoints, 0))}`);
  const evidenceReceipt = $derived(buildEvidenceReceipt({
    identity: selectedIdentity,
    sourceSha256,
    generatedAt,
    governance,
    matrix: matrixSummary,
    ledger,
    scorecardArtifactSha256,
  }));
  const instrumentEvidenceRows = $derived([
    { fact: 'Source protocol', value: LEARNING_NOW_SOURCE_PROTOCOL_LABEL, source: 'Learning Now API client contract' },
    { fact: 'Source identity SHA-256', value: sourceSha256 ?? 'SOURCE_UNAVAILABLE', source: 'V5 source.source_sha256 metadata' },
    { fact: 'Economic NAV vs reward', value: `${LEARNING_NOW_ACCOUNTING_LABELS.economicNavFormula}; ${LEARNING_NOW_ACCOUNTING_LABELS.shapedRewardBoundary}`, source: 'LEDGER route + accounting labels' },
    { fact: 'Exact five-component 23bp vector', value: costComponentsLabel, source: 'Learning Now instrument objective constants' },
    { fact: 'Fresh OOS governance', value: LEARNING_NOW_GOVERNANCE_LABELS.notRunNonResult, source: governance.freshOosCode },
    { fact: 'Matrix controls', value: `${LEARNING_NOW_GOVERNANCE_LABELS.matrixControls}; focus=${matrixSummary.focusCell.rowId}/${matrixSummary.focusCell.columnId}/${matrixSummary.focusCell.state}`, source: 'MATRIX route cells/summary' },
    { fact: 'Scorecard artifact SHA-256', value: scorecardArtifactSha256 ?? 'SCORECARD_ARTIFACT_NOT_IN_API_METADATA', source: 'ARTIFACTS route metadata; never hard-coded' },
    { fact: 'Retry/focus and rollback', value: `${LEARNING_NOW_GOVERNANCE_LABELS.retryFocus}; ${LEARNING_NOW_GOVERNANCE_LABELS.rollback}`, source: 'load stamp and retry controls' },
  ]);
  const routeRows = $derived((Object.entries(cardLabels) as [CardKey, string][]).map(([key, label]) => ({ key, label, state: cards[key] })));


  function setCard(key: CardKey, state: CardState): void {
    cards = { ...cards, [key]: state };
  }

  function clearRunScopedState(): void {
    detailRoot = null;
    eventsRoot = null;
    matrixRoot = null;
    ledgerRoot = null;
    artifactsRoot = null;
    receiptPreview = '';
    copyStatus = 'Evidence receipt not copied.';
  }

  function beginRunScopedLoad(identity: LearningNowRunIdentity | null): LearningNowLoadStamp {
    clearRunScopedState();
    const stamp = createLearningNowLoadStamp(++runSequence, identity);
    activeRunStamp = stamp;
    runScopedCardKeys.forEach((key) => setCard(key, loadingCard()));
    return stamp;
  }

  function applySettled<T>(
    key: CardKey,
    result: PromiseSettledResult<T | null>,
    applyValue: (value: T) => void,
    clearValue: () => void,
  ): T | null {
    if (result.status === 'rejected') {
      clearValue();
      setCard(key, failedCard(classifyLearningNowFailure(result.reason)));
      return null;
    }
    if (result.value === null) {
      clearValue();
      setCard(key, failedCard(classifyLearningNowFailure(null)));
      return null;
    }
    applyValue(result.value);
    setCard(key, readyCard());
    return result.value;
  }

  function blockedRunScopedCards(identity = selectedIdentity): void {
    const message = `${identity.blockerCode}: detail, events, matrix, ledger and downloads require validated run_uid + safe run_revision.`;
    clearRunScopedState();
    runScopedCardKeys.forEach((key) => setCard(key, blockedCard('BLOCKED_BY_REVISION', message)));
  }

  async function loadRunScoped(candidate: LearningNowRunCandidate | null, identityOverride?: LearningNowRunIdentity): Promise<void> {
    const identity = identityOverride ?? bindLearningNowIdentityRevision(candidate?.identity ?? selectedIdentity, requestedRevision);
    const stamp = beginRunScopedLoad(identity);
    if (!candidate || !identity.canRequestDetail || !identity.uid || identity.revision === null) {
      blockedRunScopedCards(identity);
      return;
    }
    const revision = identity.revision;
    const runUid = identity.uid;
    const [detailResult, eventsResult, matrixResult, ledgerResult, artifactsResult] = await Promise.allSettled([
      rlApi.v5LearningRunDetail(runUid, revision),
      rlApi.v5LearningEvents(runUid, revision),
      rlApi.v5LearningMatrix(runUid, revision),
      rlApi.v5LearningLedger(runUid, revision),
      rlApi.v5LearningArtifacts(runUid, revision),
    ]);
    if (!shouldApplyLearningNowResult(activeRunStamp, stamp)) return;

    applySettled('detail', detailResult, (value) => (detailRoot = value), () => (detailRoot = null));
    applySettled('events', eventsResult, (value) => (eventsRoot = value), () => (eventsRoot = null));
    applySettled('matrix', matrixResult, (value) => (matrixRoot = value), () => (matrixRoot = null));
    applySettled('ledger', ledgerResult, (value) => (ledgerRoot = value), () => (ledgerRoot = null));
    applySettled('artifacts', artifactsResult, (value) => (artifactsRoot = value), () => (artifactsRoot = null));
  }

  async function loadBase(): Promise<void> {
    const sequence = ++baseSequence;
    beginRunScopedLoad(selectedIdentity);
    (['runs', 'fixture', 'd0', 'd1'] as const).forEach((key) => setCard(key, loadingCard()));
    const [runsResult, fixtureResult, d0Result, d1Result] = await Promise.allSettled([
      rlApi.v5LearningRuns(),
      rlApi.v5LearningFixture(),
      rlApi.v5LearningD0(),
      rlApi.v5LearningD1(),
    ]);
    if (sequence !== baseSequence) return;

    const nextRuns = applySettled('runs', runsResult, (value) => (runsRoot = value), () => (runsRoot = null));
    const nextFixture = applySettled('fixture', fixtureResult, (value) => (fixtureRoot = value), () => (fixtureRoot = null));
    applySettled('d0', d0Result, (value) => (d0Root = value), () => (d0Root = null));
    applySettled('d1', d1Result, (value) => (d1Root = value), () => (d1Root = null));

    const nextSelection = selectLearningNowCandidate(nextRuns ?? runsRoot, nextFixture ?? fixtureRoot, { uid: requestedUid, runId: selectedRunId, revision: requestedRevision });
    if (nextSelection.selected && !selectedRunId) selectedRunId = nextSelection.selected.run.run_id;
    const nextIdentity = bindLearningNowIdentityRevision(nextSelection.selected?.identity ?? extractRunIdentity(null), requestedRevision);
    await loadRunScoped(nextSelection.selected, nextIdentity);
  }

  async function retryCard(key: CardKey): Promise<void> {
    if (key === 'detail' || key === 'events' || key === 'matrix' || key === 'ledger' || key === 'artifacts') {
      await loadRunScoped(selectedCandidate);
      return;
    }
    await loadBase();
  }

  async function selectRun(candidate: LearningNowRunCandidate): Promise<void> {
    const shareUid = candidate.identity.uid ?? candidate.fixtureUid;
    requestedUid = shareUid;
    selectedRunId = candidate.run.run_id;
    requestedRevision = candidate.identity.revision;
    if (typeof window !== 'undefined' && shareUid) {
      const url = new URL(window.location.href);
      url.searchParams.set('run_id', shareUid);
      url.searchParams.delete('uid');
      if (candidate.identity.revision !== null) {
        url.searchParams.set('revision', String(candidate.identity.revision));
      } else {
        url.searchParams.delete('revision');
      }
      window.history.replaceState({ tab: 'learning-now', uid: shareUid, revision: candidate.identity.revision }, '', `${url.pathname}${url.search}`);
    }
    await loadRunScoped(candidate, candidate.identity);
  }

  async function copyEvidence(): Promise<void> {
    const payload = JSON.stringify(evidenceReceipt, null, 2);
    receiptPreview = payload;
    try {
      await navigator.clipboard.writeText(payload);
      copyStatus = 'Evidence receipt copied.';
    } catch {
      copyStatus = 'Clipboard unavailable; receipt is rendered below.';
    }
  }

  onMount(() => {
    const params = new URLSearchParams(window.location.search);
    const runIdParam = params.get('run_id');
    const uidParam = params.get('run_uid') ?? params.get('uid');
    requestedUid = uidParam ?? (isLearningNowRunUid(runIdParam) ? runIdParam : null);
    selectedRunId = runIdParam && !isLearningNowRunUid(runIdParam) ? runIdParam : null;
    requestedRevision = parseLearningNowRevision(params.get('revision') ?? params.get('run_revision'));
    void loadBase();
  });
</script>

<svelte:head>
  <title>Kronos Learning Now</title>
</svelte:head>

<section class="learning-now" aria-labelledby="learning-now-title" data-v5-learning-now-route>
  <a class="skip-link" href="#learning-now-evidence">Skip to evidence and downloads</a>

  <header class="hero">
    <div>
      <p class="eyebrow">V5 read-only route · {LEARNING_NOW_UX_REVISION}</p>
      <h1 id="learning-now-title">Learning Now</h1>
      <p class="hero-copy">
        Immutable registry selection is required before run detail, events, matrix, ledger, or artifact downloads are requested.
        The current display never promotes a model, never enables broker actions, and treats all six locks as mandatory false locks.
      </p>
    </div>
    <div class="route-card" role="group" aria-label="direct route">
      <span>Direct routes</span>
      <code>{LEARNING_NOW_ROUTE_PATHS.join(' · ')}</code>
    </div>
  </header>

  <section class="identity-grid" aria-label="immutable selection and provenance">
    <article class="card identity-card" class:blocked={!selectedIdentity.canRequestDetail}>
      <h2>Immutable UID / revision</h2>
      <dl>
        <div><dt>Run UID</dt><dd>{selectedIdentity.uid ?? 'UID_UNAVAILABLE'}</dd></div>
        <div><dt>Fixture UID</dt><dd>{selectedFixtureUid ?? 'FIXTURE_UID_UNAVAILABLE'}</dd></div>
        <div><dt>Run revision</dt><dd>{selectedIdentity.revision ?? 'REVISION_UNAVAILABLE'}</dd></div>
        <div><dt>Display run_id</dt><dd>{selectedIdentity.displayRunId}</dd></div>
        <div><dt>Registry epoch</dt><dd>{selectedIdentity.provenance.registryEpoch ?? 'PROVENANCE_UNAVAILABLE'}</dd></div>
        <div><dt>Snapshot seq</dt><dd>{selectedIdentity.provenance.snapshotGlobalSeq ?? 'PROVENANCE_UNAVAILABLE'}</dd></div>
        <div><dt>Source SHA-256</dt><dd><code>{sourceSha256 ?? 'SOURCE_UNAVAILABLE'}</code></dd></div>
        <div><dt>Source protocol</dt><dd>{LEARNING_NOW_SOURCE_PROTOCOL_LABEL}</dd></div>
      </dl>
      {#if !selectedIdentity.canRequestDetail}
        <p class="status-note" role="status">
          {selectedIdentity.blockerCode}: source_sha256 is shown only as source identity, not as a registry revision.
        </p>
      {/if}
    </article>

    <article class="card selector-card" aria-labelledby="run-selector-title">
      <h2 id="run-selector-title">Run selector</h2>
      {#if selection.status === 'REQUESTED_UID_NOT_FOUND'}
        <p class="status-note blocked">Requested UID was not present in the validated V5 run list.</p>
      {/if}
      {#if selection.candidates.length === 0}
        <p class="muted">No V5 runs were returned.</p>
      {:else}
        <div class="run-list">
          {#each selection.candidates as candidate}
            <button
              type="button"
              class:selected={candidate.run.run_id === selectedCandidate?.run.run_id}
              aria-pressed={candidate.run.run_id === selectedCandidate?.run.run_id}
              onclick={() => void selectRun(candidate)}
            >
              <strong>{candidate.identity.uid ?? candidate.fixtureUid ?? candidate.run.run_id}</strong>
              <span>{candidate.fromFixture ? 'fixture loopback' : 'runs list'} · {candidate.identity.revision ?? 'REVISION_UNAVAILABLE'}</span>
            </button>
          {/each}
        </div>
      {/if}
    </article>
  </section>

  <section class="dashboard-grid" aria-label="Learning Now status cards">
    <article class="card phase-card" aria-labelledby="phase-title">
      <h2 id="phase-title">Phase, liveness, progress</h2>
      <p class="phase-label">{liveness.label}</p>
      <div
        class="progress-track"
        role="progressbar"
        aria-label="Learning progress"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow={progress.reportedPercent ?? 0}
      >
        <span style={`width: ${Math.min(100, Math.max(0, progress.reportedPercent ?? 0))}%`}></span>
      </div>
      <dl class="compact-dl">
        <div><dt>Phase</dt><dd>{liveness.phase}</dd></div>
        <div><dt>Updated</dt><dd>{liveness.updatedAt ?? 'UNAVAILABLE'}</dd></div>
        <div><dt>Age seconds</dt><dd>{liveness.ageSeconds ?? 'UNAVAILABLE'}</dd></div>
        <div><dt>Canonical rounding</dt><dd>{progress.matchesCanonicalRounding ? 'MATCH' : 'FAIL_CLOSED'}</dd></div>
        <div><dt>Focus cell</dt><dd>{matrixSummary.focusCell.rowId};{matrixSummary.focusCell.columnId};step={progress.step ?? 'NA'}</dd></div>
      </dl>
      <table class="alt-table">
        <caption>Phase and progress table alternative</caption>
        <tbody>
          <tr><th scope="row">Step</th><td>{progress.step ?? 'UNAVAILABLE'} / {progress.totalSteps ?? 'UNAVAILABLE'}</td></tr>
          <tr><th scope="row">Percent</th><td>{formatPercent(progress.reportedPercent)}</td></tr>
          <tr><th scope="row">Stale</th><td>{liveness.isStale ? 'STALE_OR_UNKNOWN' : 'FRESH'}</td></tr>
        </tbody>
      </table>
    </article>

    <article class="card accounting-card" aria-labelledby="accounting-title">
      <h2 id="accounting-title">Economic NAV vs shaped reward</h2>
      <div class="two-column">
        <section aria-label="economic NAV label">
          <h3>{LEARNING_NOW_ACCOUNTING_LABELS.economicNavName}</h3>
          <p>{LEARNING_NOW_ACCOUNTING_LABELS.economicNavFormula}</p>
          <p class="muted">Unit: {LEARNING_NOW_ACCOUNTING_LABELS.economicNavUnit}; value is not invented when the V5 route omits it.</p>
        </section>
        <section aria-label="shaped reward label">
          <h3>{LEARNING_NOW_ACCOUNTING_LABELS.shapedRewardName}</h3>
          <p>{LEARNING_NOW_ACCOUNTING_LABELS.shapedRewardBoundary}</p>
          <p class="muted">Reward charts are training diagnostics, not economic NAV.</p>
        </section>
      </div>
      <p class="status-note">Five-component 23bp vector: {costComponentsLabel}. This is research accounting, not a profitability claim.</p>
      <table class="alt-table">
        <caption>Ledger reconciliation table alternative</caption>
        <tbody>
          <tr><th scope="row">Debit</th><td>{ledger.debit}</td></tr>
          <tr><th scope="row">Credit</th><td>{ledger.credit}</td></tr>
          <tr><th scope="row">Adjustment</th><td>{ledger.adjustment}</td></tr>
          <tr><th scope="row">Net credit</th><td>{ledger.net}</td></tr>
          <tr><th scope="row">Currency</th><td>{ledger.currency}</td></tr>
        </tbody>
      </table>
    </article>

    <article class="card matrix-card" aria-labelledby="matrix-title">
      <h2 id="matrix-title">Matrix, missing/stopped, controls</h2>
      <div class="metric-row" role="group" aria-label="matrix summary">
        <span><strong>{matrixSummary.counts.PASS}</strong> pass</span>
        <span><strong>{matrixSummary.counts.FAIL}</strong> fail</span>
        <span><strong>{matrixSummary.counts.BLOCKED}</strong> blocked</span>
        <span><strong>{matrixSummary.counts.PENDING}</strong> pending</span>
        <span><strong>{matrixSummary.missingCount}</strong> missing</span>
      </div>
      <p class="status-note" class:blocked={matrixSummary.failClosedStatus === 'BLOCKED'}>
        Canonical order: {matrixSummary.ordered ? 'seed-major exact' : 'ORDER_FAIL_CLOSED'} · stopped cells: {matrixSummary.stoppedCount} · uncertainty/control label: SEED_NOISE_NO_GO; bootstrap_ci=not_improving.
      </p>
      <div class="table-scroll" role="region" aria-label="seed fold matrix table">
        <table class="matrix-table">
          <caption>Seed/fold/cost matrix table alternative</caption>
          <thead>
            <tr>
              <th scope="col">seed</th>
              {#each V5_MATRIX_COLUMNS as column}
                <th scope="col">{column}</th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each matrixSummary.tableRows as row}
              <tr>
                {#each row as cell, index}
                  {#if index === 0}
                    <th scope="row">{cell}</th>
                  {:else}
                    <td data-state={cell}>{cell}</td>
                  {/if}
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </article>

    <article class="card governance-card" aria-labelledby="governance-title">
      <h2 id="governance-title">D0 / D1 / OOS blockers</h2>
      <ul class="blocker-list">
        <li>{governance.d0Code}</li>
        <li>{governance.d1Code}</li>
        <li>{governance.freshOosCode}</li>
        <li>{governance.modelVerdict}</li>
      </ul>
      <div class="locks-grid" role="group" aria-label="six false locks">
        {#each governance.locks as lock}
          <span class:blocked={lock.status !== 'FALSE_LOCKED'}>
            <code>{lock.key}</code>
            <strong>{String(lock.value)}</strong>
          </span>
        {/each}
      </div>
      <p class="muted">Expected lock set: {LOCK_KEYS.join(', ')}.</p>
    </article>
  </section>

  <section class="card route-health" aria-labelledby="route-health-title">
    <h2 id="route-health-title">Stale, retry, errors</h2>
    <p class="muted">{LEARNING_NOW_GOVERNANCE_LABELS.retryFocus}; {LEARNING_NOW_GOVERNANCE_LABELS.rollback}.</p>
    <div class="route-list" role="list">
      {#each routeRows as row}
        <article role="listitem" class="route-row" data-status={row.state.status}>
          <div>
            <strong>{row.label}</strong>
            <span>{row.state.code}: {row.state.message}</span>
          </div>
          <button type="button" disabled={!row.state.retryable && row.state.status !== 'blocked'} onclick={() => void retryCard(row.key)}>
            Retry card
          </button>
        </article>
      {/each}
    </div>
  </section>

  <section id="learning-now-evidence" class="card evidence-card" aria-labelledby="evidence-title">
    <h2 id="evidence-title">Evidence copy and secure downloads</h2>
    <p class="muted">Only bound V5 artifact URLs are rendered. Raw fresh-OOS material is denied: FRESH_OOS_NOT_RUN.</p>
    <div class="evidence-actions">
      <button type="button" onclick={() => void copyEvidence()}>Copy evidence receipt</button>
      <span role="status" aria-live="polite">{copyStatus}</span>
    </div>
    <div class="table-scroll" role="region" aria-label="Learning Now objective evidence table">
      <table class="evidence-table">
        <caption>Objective facts and source-backed evidence labels</caption>
        <thead>
          <tr><th scope="col">Fact</th><th scope="col">Current value</th><th scope="col">Evidence source</th></tr>
        </thead>
        <tbody>
          {#each instrumentEvidenceRows as row}
            <tr>
              <th scope="row">{row.fact}</th>
              <td>{row.value}</td>
              <td>{row.source}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    {#if downloadPolicy.allowed.length > 0}
      <ul class="download-list">
        {#each downloadPolicy.allowed as bound}
          <li>
            <a href={bound.href} download={bound.download.portable_filename}>
              {bound.download.portable_filename}
            </a>
            <span>run_uid={bound.runUid}; revision={bound.revision}</span>
            <code>{bound.download.artifact.sha256}</code>
          </li>
        {/each}
      </ul>
    {:else}
      <p class="status-note blocked">Downloads blocked or unavailable: {downloadPolicy.denied.map((item) => `${item.id}=${item.reason}`).join('; ')}</p>
    {/if}
    {#if receiptPreview}
      <textarea class="receipt-preview" readonly aria-label="copied evidence receipt preview" value={receiptPreview}></textarea>
    {/if}
  </section>
</section>

<style>
  .learning-now {
    display: grid;
    gap: 20px;
    min-width: 0;
    max-width: 100%;
  }

  .skip-link {
    position: absolute;
    left: -999px;
    top: auto;
    width: 1px;
    height: 1px;
    overflow: hidden;
  }

  .skip-link:focus {
    position: static;
    width: auto;
    height: auto;
    padding: 8px 12px;
    border-radius: var(--r-pill);
    background: var(--accent);
    color: white;
  }

  .hero,
  .identity-grid,
  .dashboard-grid,
  .two-column {
    display: grid;
    gap: 16px;
    min-width: 0;
    width: 100%;
    max-width: 100%;
  }

  .hero {
    grid-template-columns: minmax(0, 1fr) minmax(220px, 320px);
    align-items: stretch;
  }

  .identity-grid {
    grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.65fr);
  }

  .dashboard-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .two-column {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .card,
  .route-card {
    min-width: 0;
    max-width: 100%;
    box-sizing: border-box;
    border: 1px solid var(--border-faint);
    border-radius: 20px;
    background: var(--surface-raised);
    box-shadow: var(--shadow-card);
    padding: 18px;
  }

  .hero-copy,
  .muted,
  .status-note,
  .route-row span,
  caption {
    color: var(--muted);
  }

  .eyebrow {
    margin: 0 0 8px;
    color: var(--accent);
    font: 750 12px/1.2 var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  h1,
  h2,
  h3,
  p {
    margin-top: 0;
  }

  h1 {
    margin-bottom: 10px;
    font: 800 clamp(32px, 6vw, 56px)/0.95 var(--font-display);
  }

  h2 {
    font: 750 18px/1.2 var(--font-display);
  }

  h3 {
    font: 700 14px/1.2 var(--font-display);
  }

  .route-card {
    display: grid;
    align-content: center;
    gap: 8px;
  }

  code,
  .receipt-preview {
    font-family: var(--font-mono);
  }

  dl,
  .compact-dl {
    display: grid;
    gap: 10px;
    margin: 0;
  }

  dl div,
  .compact-dl div {
    display: grid;
    grid-template-columns: 150px minmax(0, 1fr);
    gap: 10px;
  }

  dt {
    color: var(--muted);
    font-weight: 700;
  }

  dd {
    margin: 0;
    overflow-wrap: anywhere;
  }

  .blocked,
  .identity-card.blocked {
    border-color: color-mix(in oklab, var(--danger) 45%, var(--border-faint));
  }

  .status-note {
    margin: 12px 0 0;
    border: 1px solid var(--border-faint);
    border-radius: 14px;
    padding: 10px 12px;
    background: var(--surface-sunken);
  }

  .status-note.blocked,
  .blocked.status-note {
    color: var(--danger);
  }

  .run-list,
  .route-list,
  .download-list,
  .blocker-list {
    display: grid;
    gap: 10px;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .run-list button,
  .route-row button,
  .evidence-actions button {
    border: 1px solid var(--border-faint);
    border-radius: 14px;
    background: var(--surface);
    color: var(--fg-strong);
    cursor: pointer;
    font: inherit;
  }

  .run-list button {
    display: grid;
    gap: 4px;
    padding: 12px;
    text-align: left;
  }

  .run-list button.selected {
    border-color: var(--accent);
    box-shadow: 0 0 0 2px color-mix(in oklab, var(--accent) 25%, transparent);
  }

  button:focus-visible,
  a:focus-visible,
  .table-scroll:focus-visible,
  .receipt-preview:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 3px;
  }

  .phase-label {
    font: 750 15px/1.4 var(--font-mono);
  }

  .progress-track {
    height: 14px;
    border-radius: var(--r-pill);
    background: var(--surface-sunken);
    overflow: hidden;
    border: 1px solid var(--border-faint);
    margin-bottom: 14px;
  }

  .progress-track span {
    display: block;
    height: 100%;
    background: linear-gradient(90deg, var(--accent), color-mix(in oklab, var(--accent) 55%, white));
  }

  .metric-row,
  .locks-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .metric-row span,
  .locks-grid span {
    display: inline-grid;
    gap: 4px;
    border: 1px solid var(--border-faint);
    border-radius: 14px;
    padding: 8px 10px;
    background: var(--surface-sunken);
  }

  .locks-grid span.blocked {
    color: var(--danger);
  }

  .table-scroll {
    overflow-x: auto;
    border: 1px solid var(--border-faint);
    border-radius: 16px;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }

  caption {
    padding: 8px 10px;
    text-align: left;
  }

  th,
  td {
    border-top: 1px solid var(--border-faint);
    padding: 8px 10px;
    text-align: left;
    white-space: nowrap;
  }

  th {
    background: var(--surface-sunken);
    color: var(--fg-strong);
    font-weight: 750;
  }

  td[data-state='FAIL'],
  td[data-state='BLOCKED'],
  td[data-state='MISSING'] {
    color: var(--danger);
    font-weight: 750;
  }

  td[data-state='PASS'] {
    color: var(--success);
    font-weight: 750;
  }

  .route-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 12px;
    border: 1px solid var(--border-faint);
    border-radius: 16px;
    padding: 12px;
  }

  .route-row div {
    display: grid;
    gap: 4px;
  }

  .route-row[data-status='error'],
  .route-row[data-status='conflict'],
  .route-row[data-status='blocked'] {
    border-color: color-mix(in oklab, var(--danger) 40%, var(--border-faint));
  }

  .route-row button,
  .evidence-actions button {
    padding: 8px 12px;
  }

  .route-row button:disabled {
    cursor: not-allowed;
    opacity: 0.55;
  }

  .evidence-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: center;
    margin-bottom: 14px;
  }

  .download-list li {
    display: grid;
    gap: 4px;
    border: 1px solid var(--border-faint);
    border-radius: 14px;
    padding: 10px;
  }

  .receipt-preview {
    width: 100%;
    min-height: 220px;
    overflow: auto;
    border: 1px solid var(--border-faint);
    border-radius: 16px;
    padding: 12px;
    background: var(--surface-sunken);
    color: var(--fg-strong);
    resize: vertical;
    box-sizing: border-box;
  }

  @media (max-width: 980px) {
    .hero,
    .identity-grid,
    .dashboard-grid,
    .two-column {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 640px) {
    .card,
    .route-card {
      padding: 14px;
      border-radius: 16px;
    }

    dl div,
    .compact-dl div,
    .route-row {
      grid-template-columns: 1fr;
    }
  }
</style>
