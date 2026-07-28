import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { test } from 'node:test';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import type {
  Event,
  MatrixCell,
  V5ArtifactsRoot,
  V5D0Root,
  V5D1Root,
  V5ErrorRoot,
  V5EventsRoot,
  V5FixtureRoot,
  V5LedgerRoot,
  V5MatrixRoot,
  V5RunDetailRoot,
  V5RunsRoot,
} from './kronosRlApiV2';
import * as generatedValidators from './kronosRlApiV2.validators';
import { V5SemanticError, validateV5Semantic } from './kronosRlApiV2.semantic';
import { canonicalizeV5Json } from '../jcs';
import {
  validateArtifactsRoot,
  validateD0Root,
  validateD1Root,
  validateErrorRoot,
  validateEventsRoot,
  validateFixtureRoot,
  validateLedgerRoot,
  validateMatrixRoot,
  validateRunDetailRoot,
  validateRunsRoot,
} from './kronosRlApiV2.validators';

type StandaloneValidator = {
  (data: unknown): boolean;
  errors?: readonly unknown[] | null;
};

const sha256 = 'a'.repeat(64);
const utc = '2026-07-15T00:00:00Z';
const locks = {
  promotion_allowed: false,
  model_build_allowed: false,
  paper_forward_allowed: false,
  live_broker_order_allowed: false,
  profitability_claim_allowed: false,
  go_summary_allowed: false,
} satisfies V5RunsRoot['locks'];
const source = { source_sha256: sha256, generated_at: utc } satisfies V5RunsRoot['source'];
const progress = { step: 0, total_steps: 1, percent: 0 } satisfies V5RunsRoot['list']['items'][number]['state']['progress'];
const run = {
  run_id: 'run-1',
  state: { status: 'QUEUED', progress, updated_at: utc, started_at: null, finished_at: null },
  source_sha256: sha256,
  created_at: utc,
} satisfies V5RunsRoot['list']['items'][number];
const list = { items: [], next_cursor: null };
const matrixCells: MatrixCell[] = (['seed-01', 'seed-02', 'seed-03', 'seed-04', 'seed-05'] as const).flatMap((row_id) =>
  ([
    'fold-01:baseline',
    'fold-01:cost-00bp',
    'fold-01:cost-23bp',
    'fold-01:cost-46bp',
    'fold-01:no-trade',
    'fold-02:baseline',
    'fold-02:cost-00bp',
    'fold-02:cost-23bp',
    'fold-02:cost-46bp',
    'fold-02:no-trade',
  ] as const).map((column_id) => ({ row_id, column_id, state: 'PENDING' as const })),
);
type ArtifactItem = V5ArtifactsRoot['list']['items'][number];
type ArtifactMediaType = ArtifactItem['artifact']['media_type'];
const artifactMediaCases = [
  ['json', 'application/json'],
  ['csv', 'text/csv'],
  ['jsonl', 'application/jsonl'],
  ['md', 'text/markdown'],
  ['png', 'image/png'],
] as const;

function artifactItem({
  artifactId = 'artifact-1',
  filename = 'report.json',
  mediaType = 'application/json',
  downloadUrl,
  portableFilename,
  runId,
  runRevision,
}: {
  artifactId?: string;
  filename?: string;
  mediaType?: string;
  downloadUrl?: string;
  portableFilename?: string;
  runId?: string;
  runRevision?: number;
} = {}): ArtifactItem {
  const item = {
    artifact: {
      artifact_id: artifactId,
      filename,
      media_type: mediaType as ArtifactMediaType,
      byte_length: 1,
      sha256,
      created_at: utc,
    },
    download_url: downloadUrl ?? `/api/v5/rl/artifacts/${artifactId}/download`,
    portable_filename: portableFilename ?? filename,
  } as ArtifactItem;
  if (runId !== undefined) item.run_id = runId;
  if (runRevision !== undefined) item.run_revision = runRevision;
  return item;
}

function artifactsPayload(item: ArtifactItem): V5ArtifactsRoot {
  return { route_id: 'ARTIFACTS', source, list: { items: [item], next_cursor: null }, locks };
}
const validators: readonly (readonly [StandaloneValidator, unknown])[] = [
  [validateRunsRoot, { route_id: 'RUNS', source, list: { ...list, items: [run] }, locks }],
  [validateRunDetailRoot, { route_id: 'RUN_DETAIL', source, run, locks }],
  [
    validateEventsRoot,
    {
      route_id: 'EVENTS',
      source,
      run_id: 'run-1',
      list: {
        ...list,
        items: [
          {
            event_type: 'PROGRESS',
            event_id: 'event-1',
            occurred_at: utc,
            payload_sha256: sha256,
            progress,
          },
        ],
      },
      locks,
    },
  ],
  [
    validateMatrixRoot,
    {
      route_id: 'MATRIX',
      source,
      cells: matrixCells,
      summary: { total_cells: 50, pass_count: 0, fail_count: 0, blocked_count: 0, pending_count: 50 },
      locks,
    },
  ],
  [
    validateLedgerRoot,
    {
      route_id: 'LEDGER',
      source,
      list: {
        ...list,
        items: [
          {
            entry_id: 'entry-1',
            occurred_at: utc,
            kind: 'DEBIT',
            amount: 1,
            currency: 'KRONOS_CREDIT',
            source_sha256: sha256,
          },
        ],
      },
      locks,
    },
  ],
  [
    validateArtifactsRoot,
    {
      route_id: 'ARTIFACTS',
      source,
      list: {
        ...list,
        items: [
          {
            artifact: {
              artifact_id: 'artifact-1',
              filename: 'report.json',
              media_type: 'application/json',
              byte_length: 1,
              sha256,
              created_at: utc,
            },
            download_url: '/api/v5/rl/artifacts/artifact-1/download',
            portable_filename: 'report.json',
          },
        ],
      },
      locks,
    },
  ],
  [
    validateD0Root,
    {
      route_id: 'D0',
      source,
      d0: { status: 'PASS', price_basis: 'ADJUSTED', source_sha256: sha256, updated_at: utc },
      locks,
    },
  ],
  [
    validateD1Root,
    {
      route_id: 'D1',
      source,
      d1: { status: 'PASS', universe: 'OFFICIAL', source_sha256: sha256, updated_at: utc },
      locks,
    },
  ],
  [
    validateFixtureRoot,
    { route_id: 'FIXTURE', source, fixture: { fixture_id: 'fixture-1', run, source_sha256: sha256, created_at: utc }, locks },
  ],
  [validateErrorRoot, { route_id: 'RUNS', error: { code: 'BAD_REQUEST', message: 'Invalid request' } }],
];

const typedListFixture: V5RunsRoot['list'] = { items: [], next_cursor: null };
// @ts-expect-error Generated closed lists reject undeclared properties.
const closedListFixture: V5RunsRoot['list'] = { items: [], next_cursor: null, unexpected: true };
void typedListFixture;
void closedListFixture;
const typedMatrixCells: MatrixCell[] = matrixCells;
const typedProgressEvent: Event = {
  event_type: 'PROGRESS',
  event_id: 'event-1',
  occurred_at: utc,
  payload_sha256: sha256,
  progress,
};
// @ts-expect-error Closed event variants reject payload fields from another kind.
const invalidTypedEvent: Event = { ...typedProgressEvent, message: 'not-progress' };
// @ts-expect-error Matrix cells reject undeclared properties.
const invalidTypedCell: MatrixCell = { ...typedMatrixCells[0], extra: true };
const typedRoots = [
  {
    route_id: 'RUNS',
    source,
    list: { items: [run], next_cursor: null },
    locks,
  } satisfies V5RunsRoot,
  { route_id: 'RUN_DETAIL', source, run, locks } satisfies V5RunDetailRoot,
  {
    route_id: 'EVENTS',
    source,
    run_id: 'run-1',
    list: { items: [typedProgressEvent], next_cursor: null },
    locks,
  } satisfies V5EventsRoot,
  {
    route_id: 'MATRIX',
    source,
    cells: matrixCells,
    summary: { total_cells: 50, pass_count: 0, fail_count: 0, blocked_count: 0, pending_count: 50 },
    locks,
  } satisfies V5MatrixRoot,
  {
    route_id: 'LEDGER',
    source,
    list: { items: [{ entry_id: 'entry-1', occurred_at: utc, kind: 'DEBIT', amount: 1, currency: 'KRONOS_CREDIT', source_sha256: sha256 }], next_cursor: null },
    locks,
  } satisfies V5LedgerRoot,
  {
    route_id: 'ARTIFACTS',
    source,
    list: { items: [{ artifact: { artifact_id: 'artifact-1', filename: 'report.json', media_type: 'application/json', byte_length: 1, sha256, created_at: utc }, download_url: '/api/v5/rl/artifacts/artifact-1/download', portable_filename: 'report.json' }], next_cursor: null },
    locks,
  } satisfies V5ArtifactsRoot,
  { route_id: 'D0', source, d0: { status: 'PASS', price_basis: 'ADJUSTED', source_sha256: sha256, updated_at: utc }, locks } satisfies V5D0Root,
  { route_id: 'D1', source, d1: { status: 'PASS', universe: 'OFFICIAL', source_sha256: sha256, updated_at: utc }, locks } satisfies V5D1Root,
  { route_id: 'FIXTURE', source, fixture: { fixture_id: 'fixture-1', run, source_sha256: sha256, created_at: utc }, locks } satisfies V5FixtureRoot,
  { route_id: 'RUNS', error: { code: 'BAD_REQUEST', message: 'Invalid request' } } satisfies V5ErrorRoot,
] as const;
// @ts-expect-error RUNS may not claim RUN_DETAIL's NOT_FOUND error.
const invalidRouteError: V5ErrorRoot = { route_id: 'RUNS', error: { code: 'NOT_FOUND', message: 'wrong route' } };
// @ts-expect-error MATRIX may only claim INTERNAL_ERROR.
const invalidMatrixError: V5ErrorRoot = { route_id: 'MATRIX', error: { code: 'BAD_REQUEST', message: 'wrong matrix error' } };
void invalidTypedEvent;
void invalidTypedCell;
void invalidRouteError;
void invalidMatrixError;
void typedRoots;

test('standalone validators accept every route root in Bun', () => {
  for (const [validate, fixture] of validators) {
    assert.equal(validate(fixture), true);
    assert.equal(validate.errors, null);
  }
});

test('standalone validators reject one-leaf-invalid fixtures without mutation', () => {
  for (const [validate, fixture] of validators) {
    const invalid = structuredClone(fixture) as Record<string, unknown>;
    if ('source' in invalid) {
      (invalid.source as { source_sha256: string }).source_sha256 = 'not-a-sha256';
    } else {
      (invalid.error as { message: string }).message = '';
    }
    assert.equal(validate(invalid), false);
    assert.ok(validate.errors?.length);
  }
});
test('error root is closed to each route descriptor allowed-errors set', () => {
  const allowed: Record<string, readonly string[]> = {
    RUNS: ['BAD_REQUEST', 'INVALID_CURSOR', 'INTERNAL_ERROR'],
    RUN_DETAIL: ['NOT_FOUND', 'INTERNAL_ERROR'],
    EVENTS: ['NOT_FOUND', 'INVALID_CURSOR', 'INTERNAL_ERROR'],
    MATRIX: ['INTERNAL_ERROR'],
    LEDGER: ['INVALID_CURSOR', 'INTERNAL_ERROR'],
    ARTIFACTS: ['INVALID_CURSOR', 'INTERNAL_ERROR'],
    D0: ['INTERNAL_ERROR'],
    D1: ['INTERNAL_ERROR'],
    FIXTURE: ['INTERNAL_ERROR'],
  };
  for (const [route_id, codes] of Object.entries(allowed)) {
    for (const code of codes) assert.equal(validateErrorRoot({ route_id, error: { code, message: 'known' } }), true);
    const disallowed = codes.includes('BAD_REQUEST') ? 'NOT_FOUND' : 'BAD_REQUEST';
    assert.equal(validateErrorRoot({ route_id, error: { code: disallowed, message: 'unknown' } }), false);
  }
});
test('semantic validator rejects valid-schema progress and path-binding violations', async () => {
  const payload = {
    route_id: 'RUN_DETAIL',
    source,
    run: { ...run, state: { ...run.state, progress: { step: 1, total_steps: 2, percent: 49 } } },
    locks,
  };
  await assert.rejects(
    validateV5Semantic('RUN_DETAIL', payload, {
      method: 'GET',
      path: '/api/v5/rl/runs/run-1',
      pathParams: { run_id: 'run-1' },
    }),
    V5SemanticError,
  );
  await assert.rejects(
    validateV5Semantic('RUN_DETAIL', { ...payload, run: { ...payload.run, state: run.state } }, {
      path: '/api/v5/rl/runs/other',
      pathParams: { run_id: 'run-1' },
    }),
    V5SemanticError,
  );
});
test('semantic artifacts cover exact extension MIME set without txt zip drift', async () => {
  for (const [extension, mediaType] of artifactMediaCases) {
    const payload = artifactsPayload(artifactItem({ filename: `report.${extension}`, mediaType }));
    assert.equal(validateArtifactsRoot(payload), true, extension);
    await validateV5Semantic('ARTIFACTS', payload);

    const wrongMediaType = mediaType === 'text/csv' ? 'application/json' : 'text/csv';
    const mismatched = artifactsPayload(artifactItem({ filename: `report.${extension}`, mediaType: wrongMediaType }));
    assert.equal(validateArtifactsRoot(mismatched), true, extension);
    await assert.rejects(validateV5Semantic('ARTIFACTS', mismatched), V5SemanticError, extension);
  }

  for (const [filename, mediaType] of [['report.txt', 'text/plain'], ['report.zip', 'application/zip']] as const) {
    const payload = artifactsPayload(artifactItem({ filename, mediaType }));
    assert.equal(validateArtifactsRoot(payload), false, filename);
    await assert.rejects(validateV5Semantic('ARTIFACTS', payload), V5SemanticError, filename);
  }
});

test('semantic artifact download URLs bind optional query run identity exactly', async () => {
  const bare = artifactsPayload(artifactItem());
  assert.equal(validateArtifactsRoot(bare), true);
  await validateV5Semantic('ARTIFACTS', bare);

  for (const revisionName of ['revision', 'run_revision'] as const) {
    const payload = artifactsPayload(artifactItem({
      downloadUrl: `/api/v5/rl/artifacts/artifact-1/download?run_id=run-1&${revisionName}=7`,
      runId: 'run-1',
      runRevision: 7,
    }));
    assert.equal(validateArtifactsRoot(payload), true, revisionName);
    await validateV5Semantic('ARTIFACTS', payload);
  }

  const invalidPayloads = [
    artifactItem({ downloadUrl: '/api/v5/rl/artifacts/other/download' }),
    artifactItem({ downloadUrl: '/api/v5/rl/artifacts/artifact-1/download?run_id=run-2&revision=7', runId: 'run-1', runRevision: 7 }),
    artifactItem({ downloadUrl: '/api/v5/rl/artifacts/artifact-1/download?run_id=run-1&revision=8', runId: 'run-1', runRevision: 7 }),
    artifactItem({ downloadUrl: '/api/v5/rl/artifacts/artifact-1/download?run_id=run-1&revision=7&extra=1', runId: 'run-1', runRevision: 7 }),
    artifactItem({ downloadUrl: '/api/v5/rl/artifacts/artifact-1/download?run_id=run-1&revision=7' }),
    artifactItem({ runId: 'run-1' }),
    artifactItem({ runRevision: 7 }),
  ];

  for (const item of invalidPayloads) {
    await assert.rejects(validateV5Semantic('ARTIFACTS', artifactsPayload(item)), V5SemanticError);
  }
});

test('shared Python vectors cover JCS, event hashes, progress boundaries, opaque cursors, and Windows filenames', async () => {
  const generatedDirectory = dirname(fileURLToPath(import.meta.url));
  const repositoryRoot = resolve(generatedDirectory, '../../../../..');
  const vectors = JSON.parse(readFileSync(join(repositoryRoot, 'tests/data/kronos_rl_api_v2_vectors.json'), 'utf8'));
  const jcsVectors = JSON.parse(readFileSync(join(repositoryRoot, 'tests/data', vectors.jcs_vector_file), 'utf8'));

  for (const vector of jcsVectors.accepted) {
    assert.equal(canonicalizeV5Json(vector.input_utf8), vector.canonical_utf8, vector.id);
  }
  for (const progressCase of vectors.progress_cases) {
    const validation = () => validateV5Semantic('RUN_DETAIL', {
      route_id: 'RUN_DETAIL',
      source: vectors.source,
      run: {
        ...vectors.run,
        state: {
          ...vectors.run.state,
          progress: { step: progressCase.step, total_steps: progressCase.total_steps, percent: progressCase.percent },
        },
      },
      locks: vectors.locks,
    }, { method: 'GET', path: '/api/v5/rl/runs/run-1', pathParams: { run_id: 'run-1' } });
    if (progressCase.accepted === false) {
      await assert.rejects(validation(), V5SemanticError, progressCase.id);
    } else {
      await validation();
    }
  }
  const earlyYears = vectors.early_year_timestamp_order;
  await validateV5Semantic(earlyYears.route, {
    route_id: earlyYears.route,
    source: vectors.source,
    list: { items: earlyYears.items, next_cursor: null },
    locks: vectors.locks,
  });
  const paginationCases = vectors.pagination_cases;
  const chronological = paginationCases.whole_vs_fractional;
  await validateV5Semantic(chronological.route, {
    route_id: chronological.route,
    source: vectors.source,
    list: { items: chronological.items, next_cursor: null },
    locks: vectors.locks,
  });
  await assert.rejects(validateV5Semantic(chronological.route, {
    route_id: chronological.route,
    source: vectors.source,
    list: { items: [...chronological.items].reverse(), next_cursor: null },
    locks: vectors.locks,
  }), V5SemanticError, 'fractional timestamps must retain chronological order');

  const duplicate = paginationCases.duplicate_complete_key;
  await assert.rejects(validateV5Semantic(duplicate.route, {
    route_id: duplicate.route,
    source: vectors.source,
    list: { items: duplicate.items, next_cursor: null },
    locks: vectors.locks,
  }), V5SemanticError, 'normalized complete pagination keys must be unique');

  const artifacts = paginationCases.artifacts_pages;
  const artifactItems = artifacts.pages.flat();
  for (const page of artifacts.pages) {
    await validateV5Semantic(artifacts.route, {
      route_id: artifacts.route,
      source: vectors.source,
      list: { items: page, next_cursor: null },
      locks: vectors.locks,
    });
  }
  await validateV5Semantic(artifacts.route, {
    route_id: artifacts.route,
    source: vectors.source,
    list: { items: artifactItems, next_cursor: null },
    locks: vectors.locks,
  });
  assert.deepEqual(artifactItems.map((item: { artifact: { artifact_id: string } }) => item.artifact.artifact_id), artifacts.expected_artifact_ids);
  await assert.rejects(validateV5Semantic(artifacts.route, {
    route_id: artifacts.route,
    source: vectors.source,
    list: { items: [...artifactItems].reverse(), next_cursor: null },
    locks: vectors.locks,
  }), V5SemanticError, 'ARTIFACTS pagination must use nested artifact keys');
  await validateV5Semantic('EVENTS', {
    route_id: 'EVENTS',
    source: vectors.source,
    run_id: vectors.run.run_id,
    list: { items: vectors.events, next_cursor: 'opaque-server-token' },
    locks: vectors.locks,
  }, { method: 'GET', path: '/api/v5/rl/runs/run-1/events', pathParams: { run_id: 'run-1' } });
  for (const filenameCase of vectors.portable_filename_cases) {
    const mediaType = artifactMediaCases.find(([extension]) => filenameCase.filename.endsWith(`.${extension}`))?.[1] ?? 'application/json';
    const payload = {
      route_id: 'ARTIFACTS',
      source: vectors.source,
      list: {
        items: [{
          artifact: { artifact_id: 'artifact-1', filename: filenameCase.filename, media_type: mediaType, byte_length: 1, sha256, created_at: utc },
          download_url: '/api/v5/rl/artifacts/artifact-1/download',
          portable_filename: filenameCase.filename,
        }],
        next_cursor: null,
      },
      locks: vectors.locks,
    };
    if (filenameCase.accepted) await validateV5Semantic('ARTIFACTS', payload);
    else await assert.rejects(validateV5Semantic('ARTIFACTS', payload), V5SemanticError);
  }
});

test('generated artifacts have exact exports, resolved-version banners, and deterministic bytes', { timeout: 30_000 }, () => {
  const generatedDirectory = dirname(fileURLToPath(import.meta.url));
  const projectRoot = resolve(generatedDirectory, '../../..');
  const repositoryRoot = resolve(projectRoot, '../..');
  const schemaText = readFileSync(join(repositoryRoot, 'docs/schemas/kronos_rl_api_v2.schema.json'), 'utf8').replace(/\r\n?/g, '\n');
  const schemaSha256 = createHash('sha256').update(schemaText).digest('hex');
  const types = readFileSync(join(generatedDirectory, 'kronosRlApiV2.ts'), 'utf8');
  const validatorSource = readFileSync(join(generatedDirectory, 'kronosRlApiV2.validators.ts'), 'utf8');
  const semanticSource = readFileSync(join(generatedDirectory, 'kronosRlApiV2.semantic.ts'), 'utf8');
  const packageLock = JSON.parse(readFileSync(join(projectRoot, 'package-lock.json'), 'utf8'));
  const expectedExports = [
    'v5RouteDescriptors',
    'validateArtifactsRoot',
    'validateD0Root',
    'validateD1Root',
    'validateErrorRoot',
    'validateEventsRoot',
    'validateFixtureRoot',
    'validateLedgerRoot',
    'validateMatrixRoot',
    'validateRunDetailRoot',
    'validateRunsRoot',
  ].sort();

  assert.match(types, new RegExp(`schema-sha256: ${schemaSha256}`));
  assert.match(types, new RegExp(`json-schema-to-typescript@${packageLock.packages['node_modules/json-schema-to-typescript'].version}`));
  assert.match(validatorSource, new RegExp(`schema-sha256: ${schemaSha256}`));
  assert.match(
    validatorSource,
    new RegExp(
      `ajv@${packageLock.packages['node_modules/ajv'].version} \\+ ajv-formats@${packageLock.packages['node_modules/ajv-formats'].version}`,
    ),
  );
  assert.deepEqual(Object.keys(generatedValidators).sort(), expectedExports);
  assert.match(validatorSource, /import formats from "ajv-formats\/dist\/formats\.js";/);
  assert.match(validatorSource, /import ucs2length from "ajv\/dist\/runtime\/ucs2length\.js";/);
  assert.doesNotMatch(validatorSource, /\brequire\s*\(|\beval\s*\(/);
  assert.match(validatorSource, /export type V5Validator<T> = \(\(data: unknown\) => data is T\)/);
  assert.match(validatorSource, /export const v5RouteDescriptors =/);
  assert.match(semanticSource, /export async function validateV5Semantic/);
  assert.match(semanticSource, new RegExp(`schema-sha256: ${schemaSha256}`));
  assert.deepEqual(readdirSync(generatedDirectory).sort(), [
    'kronosRlApiV2.semantic.ts',
    'kronosRlApiV2.test.ts',
    'kronosRlApiV2.ts',
    'kronosRlApiV2.validators.ts',
  ]);
  assert.match(semanticSource, /canonicalizeV5Utf8/);
  assert.doesNotMatch(semanticSource, /atob\(|token\.replace|cursor is bound/);

  const result = spawnSync('node', ['../../scripts/generate_kronos_v5_api_types.mjs', '--check'], {
    cwd: projectRoot,
  });
  assert.equal(result.status, 0, result.stderr.toString());
});
