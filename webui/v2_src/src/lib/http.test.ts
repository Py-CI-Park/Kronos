import { test } from 'node:test';
import assert from 'node:assert/strict';

import type * as Http from './http';

const httpPath = ['.', 'http.ts'].join('/');
const { requireJsonPayload }: typeof Http = await import(httpPath);

test('requireJsonPayload resolves object payloads unchanged', async () => {
  const payload = { status: 'ok', count: 3 };

  await assert.doesNotReject(async () => {
    assert.equal(await requireJsonPayload('object source', Promise.resolve(payload)), payload);
  });
});

test('requireJsonPayload rejects null payloads with a label-specific error', async () => {
  await assert.rejects(
    requireJsonPayload('rliable stats', Promise.resolve(null)),
    (caught) => caught instanceof Error && caught.message === 'rliable stats payload unavailable'
  );
});

test('requireJsonPayload preserves upstream rejections', async () => {
  const upstream = new Error('network exploded');

  await assert.rejects(
    requireJsonPayload('events', Promise.reject(upstream)),
    (caught) => caught === upstream
  );
});
