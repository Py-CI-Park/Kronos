import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';

import {
  canonicalizeV5,
  canonicalizeV5Json,
  canonicalizeV5JsonUtf8,
  canonicalizeV5Utf8,
  JcsProfileError,
  parseV5Json,
  parseV5JsonUtf8,
} from './jcs';

type JcsVectors = {
  profile: 'kronos-jcs-profile-v1';
  encoding: 'UTF-8';
  accepted: Array<{
    id: string;
    input_utf8: string;
    canonical_utf8: string;
    sha256: string;
  }>;
  rejected: Array<{
    id: string;
    input_utf8: string;
    stage: 'parse' | 'canonicalize';
    rejection: string;
  }>;
};

const vectorPath = new URL('../../../../tests/data/kronos_jcs_rfc8785_v1_vectors.json', import.meta.url);
const vectors = JSON.parse(await readFile(vectorPath, 'utf8')) as JcsVectors;

function expectCode(action: () => unknown, code: JcsProfileError['code']): void {
  try {
    action();
    assert.fail(`expected JcsProfileError with code ${code}`);
  } catch (error) {
    if (!(error instanceof JcsProfileError)) {
      throw error;
    }
    assert.equal(error.code, code);
  }
}

test('V5 JCS raw canonicalization consumes shared RFC 8785 vectors', () => {
  assert.equal(vectors.profile, 'kronos-jcs-profile-v1');
  assert.equal(vectors.encoding, 'UTF-8');

  for (const vector of vectors.accepted) {
    const actual = canonicalizeV5Json(vector.input_utf8);
    const actualBytes = canonicalizeV5JsonUtf8(new TextEncoder().encode(vector.input_utf8));
    const expectedBytes = new TextEncoder().encode(vector.canonical_utf8);

    assert.equal(actual, vector.canonical_utf8, `${vector.id} canonical JSON`);
    assert.deepEqual(actualBytes, expectedBytes, `${vector.id} canonical UTF-8 bytes`);
    assert.equal(
      createHash('sha256').update(actualBytes).digest('hex'),
      vector.sha256,
      `${vector.id} canonical SHA-256`
    );
  }

  const expectedCodes: Record<string, JcsProfileError['code']> = {
    'duplicate-member-name': 'duplicate_member',
    'utf8-bom': 'utf8_bom',
    'lone-surrogate': 'invalid_unicode',
    nan: 'malformed_json',
    'positive-infinity': 'malformed_json',
    'negative-infinity': 'malformed_json',
    'exponent-overflow': 'non_finite_number',
    'unsafe-integer': 'unsafe_integer',
    'unsafe-negative-integer': 'unsafe_integer',
  };

  for (const vector of vectors.rejected) {
    const code = expectedCodes[vector.id];
    assert.notEqual(code, undefined, `${vector.id} has an exact error code assertion`);
    const action =
      vector.stage === 'parse'
        ? () => parseV5Json(vector.input_utf8)
        : () => canonicalizeV5Json(vector.input_utf8);
    expectCode(action, code);
  }
});

test('V5 JCS raw and direct entry points preserve their number contracts', () => {
  const source = '{"b":2,"a":1}';
  const bytes = new TextEncoder().encode(source);

  assert.equal((parseV5Json(source) as { b: number }).b, 2);
  assert.equal((parseV5JsonUtf8(bytes) as { b: number }).b, 2);
  assert.equal(canonicalizeV5({ b: 2, a: 1 }), '{"a":1,"b":2}');
  assert.deepEqual(canonicalizeV5Utf8({ b: 2, a: 1 }), new TextEncoder().encode('{"a":1,"b":2}'));

  assert.equal(canonicalizeV5Json('{"value":1e30}'), '{"value":1e+30}');
  assert.equal(canonicalizeV5Json('{"value":9007199254740992.0}'), '{"value":9007199254740992}');
  expectCode(() => canonicalizeV5Json('{"value":9007199254740992}'), 'unsafe_integer');
  expectCode(() => canonicalizeV5(1e30), 'unsafe_integer');
  expectCode(() => canonicalizeV5(9007199254740992), 'unsafe_integer');
  expectCode(() => canonicalizeV5Utf8(1e30), 'unsafe_integer');
});

test('V5 JCS raw byte entry points reject BOMs and invalid UTF-8', () => {
  const bom = new Uint8Array([0xef, 0xbb, 0xbf, 0x7b, 0x7d]);
  const invalidUtf8 = new Uint8Array([0xc3, 0x28]);

  expectCode(() => parseV5Json('\ufeff{}'), 'utf8_bom');
  expectCode(() => parseV5JsonUtf8(bom), 'utf8_bom');
  expectCode(() => canonicalizeV5JsonUtf8(bom), 'utf8_bom');
  expectCode(() => parseV5JsonUtf8(invalidUtf8), 'malformed_json');
  expectCode(() => canonicalizeV5JsonUtf8(invalidUtf8), 'malformed_json');
});

test('V5 JCS direct values reject unsupported and structurally unsafe inputs', () => {
  const cyclic: { self?: unknown } = {};
  cyclic.self = cyclic;
  const sparse = [1, , 3];
  const accessorArray = [1];
  Object.defineProperty(accessorArray, '0', { enumerable: true, get: () => 1 });
  const symbolProperty = { value: 1 };
  Object.defineProperty(symbolProperty, Symbol('value'), { enumerable: true, value: 1 });
  const accessorObject = {};
  Object.defineProperty(accessorObject, 'value', { enumerable: true, get: () => 1 });

  for (const value of [undefined, Symbol('value'), () => 1, 1n]) {
    expectCode(() => canonicalizeV5(value), 'unsupported_value');
  }
  for (const value of [NaN, Infinity, -Infinity]) {
    expectCode(() => canonicalizeV5(value), 'non_finite_number');
  }
  expectCode(() => canonicalizeV5('\ud800'), 'invalid_unicode');
  expectCode(() => canonicalizeV5(cyclic), 'cyclic_value');
  expectCode(() => canonicalizeV5(sparse), 'unsupported_value');
  expectCode(() => canonicalizeV5(accessorArray), 'non_json_object');
  expectCode(() => canonicalizeV5(symbolProperty), 'non_json_object');
  expectCode(() => canonicalizeV5(accessorObject), 'non_json_object');
  expectCode(() => canonicalizeV5(new Date()), 'non_json_object');
  expectCode(() => canonicalizeV5(new Map()), 'non_json_object');
});
